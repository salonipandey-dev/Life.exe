"""Character profile, dashboard (Command Center) and account data ownership."""

from __future__ import annotations

from typing import Any

from lifeexe.core.db import Database
from lifeexe.core.errors import BadRequest, Unauthorized
from lifeexe.core.security import hash_password, hash_token, verify_password
from lifeexe.core.timeutil import Clock, normalize_timezone, to_iso
from lifeexe.domain.achievements import BY_KEY
from lifeexe.domain.character import AVATARS, THEMES, TITLES, title_unlock_level, unlocked_titles
from lifeexe.domain.habits import week_start
from lifeexe.domain.leveling import level_for_xp
from lifeexe.domain.quests import PRIORITY_RANK, Priority
from lifeexe.domain.rewards import Attribute, GameConfig
from lifeexe.repositories import achievements as ach_repo
from lifeexe.repositories import analytics as analytics_repo
from lifeexe.repositories import habits as habits_repo
from lifeexe.repositories import ledger
from lifeexe.repositories import quests as quests_repo
from lifeexe.repositories import users as users_repo
from lifeexe.repositories.quests import QuestFilters
from lifeexe.services.common import progress_dict, user_day
from lifeexe.services.habits import load_histories, habit_dict
from lifeexe.services.quests import quest_dict

#: Tables exported for data portability (password hashes and sessions excluded).
EXPORT_TABLES = (
    "profiles", "quests", "quest_completions", "xp_events", "coin_transactions", "habits",
    "habit_pauses", "habit_logs", "skills", "skill_dependencies", "skill_evidence", "user_achievements",
)


class ProfileService:
    def __init__(self, db: Database, clock: Clock, game: GameConfig) -> None:
        self.db = db
        self.clock = clock
        self.game = game

    def get(self, user_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            p = users_repo.get_profile(conn, user_id)
            assert p is not None
            total = ledger.total_xp(conn, user_id)
            level = level_for_xp(max(total, 0))
            by_attr = ledger.xp_by_attribute(conn, user_id)
            return {
                "user_id": user_id,
                "today": user_day(conn, user_id, self.clock.now()).today_iso,
                "email": p["email"],
                "display_name": p["display_name"],
                "title": p["title"],
                "avatar": p["avatar"],
                "theme": p["theme"],
                "timezone": p["timezone"],
                "day_start_hour": p["day_start_hour"],
                "account_created_at": p["account_created_at"],
                "progress": progress_dict(max(total, 0)),
                "coins": ledger.coin_balance(conn, user_id),
                "attributes": [
                    {"attribute": a.value, "xp": max(by_attr.get(a.value, 0), 0),
                     "rank": level_for_xp(max(by_attr.get(a.value, 0), 0))}
                    for a in Attribute
                ],
                "options": {
                    "titles": [{"title": t, "unlock_level": lvl, "unlocked": level >= lvl} for lvl, t in TITLES],
                    "unlocked_titles": unlocked_titles(level),
                    "avatars": list(AVATARS),
                    "themes": list(THEMES),
                },
                "game": {
                    "xp_by_difficulty": {k.value: v for k, v in self.game.xp_by_difficulty.items()},
                    "habit_checkin_xp": self.game.habit_checkin_xp,
                    "daily_xp_cap": self.game.daily_xp_cap,
                    "coin_divisor": self.game.coin_divisor,
                },
            }

    def update(self, user_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            if "timezone" in changes:
                canonical = normalize_timezone(changes["timezone"])
                if canonical is None:
                    raise BadRequest("Unknown time zone.")
                changes = {**changes, "timezone": canonical}
            if "avatar" in changes and changes["avatar"] not in AVATARS:
                raise BadRequest("Unknown avatar.")
            if "theme" in changes and changes["theme"] not in THEMES:
                raise BadRequest("Unknown theme.")
            if "title" in changes:
                need = title_unlock_level(changes["title"])
                level = level_for_xp(max(ledger.total_xp(conn, user_id), 0))
                if need is None:
                    raise BadRequest("Unknown title.")
                if level < need:
                    raise BadRequest(f"The {changes['title']} title unlocks at level {need}.")
            if changes:
                users_repo.update_profile(conn, user_id, {**changes, "updated_at": to_iso(self.clock.now())})
        return self.get(user_id)

    # --- Command Center ------------------------------------------------------

    def dashboard(self, user_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            ud = user_day(conn, user_id, self.clock.now())
            p = users_repo.get_profile(conn, user_id)
            assert p is not None
            total = ledger.total_xp(conn, user_id)
            today_rows = quests_repo.today_candidates(conn, user_id, ud.today_iso, ud.day_key, ud.week_key)
            today_quests = [quest_dict(r, ud, self.game) for r in today_rows]

            open_rows, _ = quests_repo.list_quests(
                conn, user_id,
                QuestFilters(statuses=("ACTIVE", "AVAILABLE", "PAUSED"), sort="-priority", limit=200),
                ud.day_key, ud.week_key,
            )
            open_one_off = [quest_dict(r, ud, self.game) for r in open_rows if r["recurrence"] == "NONE"]

            def urgency(q: dict[str, Any]) -> tuple[int, int, str, int]:
                due = q["due_date"]
                # overdue first, then due today, then by priority; due date breaks ties
                bucket = 0 if q["overdue"] else 1 if due == ud.today_iso else 2
                return (bucket, -PRIORITY_RANK[Priority(q["priority"])], due or "9999-12-31", q["id"])

            priorities = sorted(open_one_off, key=urgency)[:3]

            habits = habits_repo.list_habits(conn, user_id, include_archived=False)
            hist = load_histories(conn, user_id, habits, ud.today)
            habit_items = [habit_dict(h, *hist[int(h["id"])], ud, calendar_days=7) for h in habits]

            ws = week_start(ud.today)
            week_xp = sum(ledger.xp_by_day(conn, user_id, ws.isoformat(), ud.today_iso).values())
            week_completions = sum(
                analytics_repo.completions_by_day(conn, user_id, ws.isoformat(), ud.today_iso).values()
            )
            week_habit_days = sum(habits_repo.done_by_day(conn, user_id, ws.isoformat(), ud.today_iso).values())

            achievements = [
                {"key": r["achievement_key"], "title": BY_KEY[r["achievement_key"]].title,
                 "description": BY_KEY[r["achievement_key"]].description, "unlocked_at": r["unlocked_at"]}
                for r in ach_repo.unlocked(conn, user_id)[:3] if r["achievement_key"] in BY_KEY
            ]
            events = [
                {"id": e["id"], "amount": e["amount"], "reason": e["reason"], "local_date": e["local_date"],
                 "created_at": e["created_at"], "label": e["quest_title"] or e["habit_name"] or e["reason"]}
                for e in ledger.recent_xp_events(conn, user_id, 6)
            ]
            return {
                "today": ud.today_iso,
                "character": {
                    "display_name": p["display_name"],
                    "title": p["title"],
                    "avatar": p["avatar"],
                    "progress": progress_dict(max(total, 0)),
                    "coins": ledger.coin_balance(conn, user_id),
                },
                "priorities": priorities,
                "today_quests": today_quests,
                "habits": habit_items,
                "week": {
                    "start": ws.isoformat(),
                    "net_xp": week_xp,
                    "quest_completions": week_completions,
                    "habit_days": week_habit_days,
                    "xp_today": ledger.net_xp_on(conn, user_id, ud.today_iso),
                    "daily_xp_cap": self.game.daily_xp_cap,
                },
                "recent_achievements": achievements,
                "recent_xp": events,
            }

    # --- account & data ownership ---------------------------------------------

    def change_password(self, user_id: int, current: str, new: str, keep_token: str | None) -> None:
        with self.db.transaction(write=False) as conn:
            user = users_repo.get_user(conn, user_id)
        assert user is not None
        if not verify_password(current, user["password_hash"]):
            raise Unauthorized("Current password is incorrect.")
        new_hash = hash_password(new)
        with self.db.transaction() as conn:
            users_repo.update_password(conn, user_id, new_hash, to_iso(self.clock.now()))
            # Sign out every other device after a password change.
            users_repo.delete_other_sessions(conn, user_id, hash_token(keep_token) if keep_token else None)

    def export(self, user_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            data: dict[str, Any] = {}
            user = users_repo.get_user(conn, user_id)
            assert user is not None
            data["account"] = {"email": user["email"], "created_at": user["created_at"]}
            for table in EXPORT_TABLES:  # fixed whitelist, not user input
                rows = conn.execute(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY 1", (user_id,)).fetchall()
                data[table] = [dict(r) for r in rows]
            return {
                "format": "lifeexe-export",
                "version": 1,
                "exported_at": to_iso(self.clock.now()),
                "data": data,
            }

    def delete_account(self, user_id: int, password: str) -> None:
        with self.db.transaction(write=False) as conn:
            user = users_repo.get_user(conn, user_id)
        assert user is not None
        if not verify_password(password, user["password_hash"]):
            raise Unauthorized("Password is incorrect.")
        with self.db.transaction() as conn:
            users_repo.delete_user(conn, user_id)  # ON DELETE CASCADE removes every owned row

