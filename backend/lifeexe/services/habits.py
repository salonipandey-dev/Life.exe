from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from lifeexe.core.db import Connection, Database, Row
from lifeexe.core.errors import BadRequest, Conflict, NotFound
from lifeexe.core.timeutil import Clock, to_iso
from lifeexe.domain.habits import (
    HabitHistory,
    Measure,
    Schedule,
    ScheduleKind,
    calendar,
    habit_stats,
    mask_to_weekdays,
    paused_days,
)
from lifeexe.domain.rewards import GameConfig, capped_reward
from lifeexe.repositories import habits as habits_repo
from lifeexe.repositories import ledger
from lifeexe.repositories.ledger import NewXpEvent
from lifeexe.services.achievements import evaluate_achievements
from lifeexe.services.common import UserDay, progress_dict, user_day

#: How far back a user may log or correct entries.
BACKFILL_DAYS = 30


def _schedule(h: Row) -> Schedule:
    return Schedule(
        kind=ScheduleKind(h["schedule_kind"]),
        weekdays=mask_to_weekdays(int(h["weekdays_mask"])),
        target_per_week=h["target_per_week"],
    )


def load_histories(
    conn: Connection, user_id: int, habits: list[Row], today: date
) -> dict[int, tuple[HabitHistory, dict[str, Row]]]:
    ids = [int(h["id"]) for h in habits]
    logs_by: dict[int, list[Row]] = defaultdict(list)
    for log in habits_repo.logs_for_habits(conn, user_id, ids):
        logs_by[int(log["habit_id"])].append(log)
    pauses_by: dict[int, list[tuple[date, date | None]]] = defaultdict(list)
    for p in habits_repo.pauses_for_habits(conn, user_id, ids):
        end = date.fromisoformat(p["end_date"]) if p["end_date"] else None
        pauses_by[int(p["habit_id"])].append((date.fromisoformat(p["start_date"]), end))
    out = {}
    for h in habits:
        hid = int(h["id"])
        target = int(h["target_value"])
        logs = logs_by[hid]
        done = frozenset(
            date.fromisoformat(entry["local_date"])
            for entry in logs
            if entry["entry_type"] == "ENTRY" and int(entry["value"]) >= target
        )
        partial = frozenset(
            date.fromisoformat(entry["local_date"])
            for entry in logs
            if entry["entry_type"] == "ENTRY" and 0 < int(entry["value"]) < target
        )
        rest = frozenset(date.fromisoformat(entry["local_date"]) for entry in logs if entry["entry_type"] == "REST")
        history = HabitHistory(
            schedule=_schedule(h),
            start=date.fromisoformat(h["start_date"]),
            today=today,
            done=done,
            partial=partial,
            rest=rest,
            paused=paused_days(pauses_by[hid], today),
        )
        out[hid] = (history, {entry["local_date"]: entry for entry in logs})
    return out


def best_daily_streak(conn: Connection, user_id: int, today: date) -> int:
    habits = [
        h
        for h in habits_repo.list_habits(conn, user_id, include_archived=True)
        if h["schedule_kind"] != ScheduleKind.WEEKLY_COUNT.value
    ]
    if not habits:
        return 0
    return max(habit_stats(hist).longest_streak for hist, _ in load_histories(conn, user_id, habits, today).values())


def habit_dict(
    h: Row, history: HabitHistory, logs: dict[str, Row], ud: UserDay, calendar_days: int = 28
) -> dict[str, Any]:
    stats = habit_stats(history)
    today_log = logs.get(ud.today_iso)
    paused = ud.today in history.paused
    return {
        "id": h["id"],
        "name": h["name"],
        "description": h["description"],
        "schedule_kind": h["schedule_kind"],
        "weekdays": sorted(mask_to_weekdays(int(h["weekdays_mask"]))),
        "target_per_week": h["target_per_week"],
        "measure": h["measure"],
        "target_value": h["target_value"],
        "attribute": h["attribute"],
        "start_date": h["start_date"],
        "archived": h["archived_at"] is not None,
        "paused": paused,
        "scheduled_today": history.schedule.is_scheduled(ud.today),
        "today": {
            "state": stats.today_state.value,
            "value": int(today_log["value"]) if today_log else 0,
            "entry_type": today_log["entry_type"] if today_log else None,
        },
        "stats": {
            "unit": stats.unit,
            "current_streak": stats.current_streak,
            "longest_streak": stats.longest_streak,
            "total_done": stats.total_done,
            "week_progress": list(stats.week_progress) if stats.week_progress else None,
            "windows": [
                {
                    "label": w.label,
                    "achieved": w.achieved,
                    "required": w.required,
                    "rate": None if w.rate is None else round(w.rate, 4),
                }
                for w in stats.windows
            ],
        },
        "calendar": [
            {
                "date": d.isoformat(),
                "state": s.value,
                "value": int(logs[d.isoformat()]["value"]) if d.isoformat() in logs else 0,
            }
            for d, s in calendar(history, calendar_days)
        ],
    }


class HabitService:
    def __init__(self, db: Database, clock: Clock, game: GameConfig) -> None:
        self.db = db
        self.clock = clock
        self.game = game

    def _one(self, conn: Connection, ud: UserDay, habit_id: int) -> dict[str, Any]:
        h = habits_repo.get(conn, ud.user_id, habit_id)
        if h is None:
            raise NotFound("Habit not found.")
        history, logs = load_histories(conn, ud.user_id, [h], ud.today)[habit_id]
        return habit_dict(h, history, logs, ud)

    def list(self, user_id: int, include_archived: bool = False) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            ud = user_day(conn, user_id, self.clock.now())
            habits = habits_repo.list_habits(conn, user_id, include_archived)
            hist = load_histories(conn, user_id, habits, ud.today)
            items = [habit_dict(h, *hist[int(h["id"])], ud) for h in habits]
            return {"items": items, "today": ud.today_iso}

    def get(self, user_id: int, habit_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            return self._one(conn, user_day(conn, user_id, self.clock.now()), habit_id)

    def create(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            fields = {**data, "start_date": ud.today_iso, "created_at": ud.now_iso, "updated_at": ud.now_iso}
            habit_id = habits_repo.insert(conn, user_id, fields)
            return self._one(conn, ud, habit_id)

    def update(self, user_id: int, habit_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            h = habits_repo.get(conn, user_id, habit_id)
            if h is None:
                raise NotFound("Habit not found.")
            merged = {**dict(h), **changes}
            if merged["measure"] == Measure.BOOLEAN.value:
                changes["target_value"] = 1
            if merged["schedule_kind"] == ScheduleKind.WEEKLY_COUNT.value and not merged["target_per_week"]:
                raise BadRequest("Weekly-count habits need target_per_week.")
            if changes:
                habits_repo.update(conn, user_id, habit_id, {**changes, "updated_at": ud.now_iso})
            return self._one(conn, ud, habit_id)

    def set_archived(self, user_id: int, habit_id: int, archived: bool) -> dict[str, Any]:
        return self.update(user_id, habit_id, {"archived_at": to_iso(self.clock.now()) if archived else None})

    def pause(self, user_id: int, habit_id: int) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            if habits_repo.get(conn, user_id, habit_id) is None:
                raise NotFound("Habit not found.")
            if habits_repo.open_pause(conn, user_id, habit_id) is not None:
                raise Conflict("Habit is already paused.")
            habits_repo.start_pause(conn, user_id, habit_id, ud.today_iso)
            return self._one(conn, ud, habit_id)

    def resume(self, user_id: int, habit_id: int) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            if habits_repo.get(conn, user_id, habit_id) is None:
                raise NotFound("Habit not found.")
            pause = habits_repo.open_pause(conn, user_id, habit_id)
            if pause is None:
                raise Conflict("Habit is not paused.")
            start = date.fromisoformat(pause["start_date"])
            # Paused and resumed on the same day -> the pause never covered a full day.
            end = None if start >= ud.today else (ud.today - timedelta(days=1)).isoformat()
            habits_repo.end_pause(conn, user_id, int(pause["id"]), end)
            return self._one(conn, ud, habit_id)

    def log(
        self, user_id: int, habit_id: int, day: date | None, entry_type: str, value: int | None, note: str
    ) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            h = habits_repo.get(conn, user_id, habit_id)
            if h is None:
                raise NotFound("Habit not found.")
            if h["archived_at"] is not None:
                raise Conflict("Archived habits cannot be logged.")
            day = day or ud.today
            self._check_day(h, ud, day)
            target = int(h["target_value"])
            if entry_type == "REST":
                value = 0
            elif value is None:
                value = target if h["measure"] == Measure.BOOLEAN.value else 0
            if h["measure"] == Measure.BOOLEAN.value and entry_type == "ENTRY" and value not in (0, 1):
                raise BadRequest("Yes/no habits take a value of 0 or 1.")
            existing = habits_repo.get_log(conn, user_id, habit_id, day.isoformat())
            if existing is None:
                log_id = habits_repo.insert_log(
                    conn, user_id, habit_id, day.isoformat(), entry_type, value, note, ud.now_iso
                )
                award_event_id = None
            else:
                log_id = int(existing["id"])
                award_event_id = existing["award_event_id"]
                habits_repo.update_log(conn, user_id, log_id, entry_type, value, note, ud.now_iso)
            done = entry_type == "ENTRY" and value >= target
            xp_delta = self._sync_award(conn, ud, h, log_id, award_event_id, done, day)
            unlocked = evaluate_achievements(conn, user_id, ud.now_iso)
            return {
                "habit": self._one(conn, ud, habit_id),
                "xp_delta": xp_delta,
                "progress": progress_dict(max(ledger.total_xp(conn, user_id), 0)),
                "achievements_unlocked": unlocked,
            }

    def delete_log(self, user_id: int, habit_id: int, day: date) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            h = habits_repo.get(conn, user_id, habit_id)
            if h is None:
                raise NotFound("Habit not found.")
            existing = habits_repo.get_log(conn, user_id, habit_id, day.isoformat())
            if existing is None:
                raise NotFound("No entry for that day.")
            xp_delta = self._sync_award(conn, ud, h, int(existing["id"]), existing["award_event_id"], False, day)
            habits_repo.delete_log(conn, user_id, int(existing["id"]))
            return {
                "habit": self._one(conn, ud, habit_id),
                "xp_delta": xp_delta,
                "progress": progress_dict(max(ledger.total_xp(conn, user_id), 0)),
                "achievements_unlocked": [],
            }

    def _check_day(self, h: Row, ud: UserDay, day: date) -> None:
        if day > ud.today:
            raise BadRequest("You cannot log a future day.")
        if day < date.fromisoformat(h["start_date"]):
            raise BadRequest("That day is before this habit started.")
        if day < ud.today - timedelta(days=BACKFILL_DAYS):
            raise BadRequest(f"Entries can only be changed for the last {BACKFILL_DAYS} days.")

    def _sync_award(
        self, conn: Connection, ud: UserDay, h: Row, log_id: int, award_event_id: int | None, done: bool, day: date
    ) -> int:
        """Keep the ledger consistent with the entry: exactly one live award
        while the day is done, none otherwise. Returns the XP delta."""
        user_id = ud.user_id
        if done and award_event_id is None:
            seq = ledger.count_awards_for_source(conn, user_id, "HABIT_LOG", log_id)
            reward = capped_reward(
                self.game.habit_checkin_xp, ledger.net_xp_on(conn, user_id, day.isoformat()), self.game
            )
            event_id = ledger.insert_xp_event(
                conn,
                NewXpEvent(
                    user_id=user_id,
                    amount=reward.xp,
                    base_amount=reward.base_xp,
                    reason="HABIT_COMPLETED",
                    source_type="HABIT_LOG",
                    source_id=log_id,
                    skill_id=None,
                    attribute=h["attribute"],
                    idempotency_key=f"habit_log:{log_id}:award:{seq}",
                    local_date=day.isoformat(),
                    created_at=ud.now_iso,
                ),
            )
            habits_repo.set_award(conn, user_id, log_id, event_id)
            return reward.xp
        if not done and award_event_id is not None:
            award = ledger.get_xp_event(conn, user_id, int(award_event_id))
            assert award is not None
            ledger.insert_xp_event(
                conn,
                NewXpEvent(
                    user_id=user_id,
                    amount=-int(award["amount"]),
                    base_amount=0,
                    reason="HABIT_UNDONE",
                    source_type="HABIT_LOG",
                    source_id=log_id,
                    skill_id=None,
                    attribute=award["attribute"],
                    idempotency_key=f"reversal:{award['id']}",
                    local_date=award["local_date"],
                    created_at=ud.now_iso,
                    reverses_event_id=int(award["id"]),
                ),
            )
            habits_repo.set_award(conn, user_id, log_id, None)
            return -int(award["amount"])
        return 0
