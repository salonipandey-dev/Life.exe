"""Quest use cases, including the transactional, idempotent reward flow.

complete():
  BEGIN IMMEDIATE                                   -- serialises writers
    validate transition (domain state machine)
    derive occurrence key (once / local date / ISO week)
    reject if a live completion exists for it       -- 409, no XP
    INSERT quest_completions                        -- partial UNIQUE index guard
    compute reward = capped(base XP, net XP today)  -- domain rules
    INSERT xp_events  (idempotency_key = quest_completion:<id>)
    INSERT coin_transactions
    UPDATE quests status
    evaluate achievements (idempotent)
  COMMIT
Any failure rolls back every row above: XP can never exist without the
completion that justified it, and vice versa.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from lifeexe.core.db import Connection, Database, Row, is_unique_violation
from lifeexe.core.errors import AlreadyCompleted, Conflict, NotFound
from lifeexe.core.timeutil import Clock
from lifeexe.domain.leveling import level_for_xp
from lifeexe.domain.quests import (
    EDITABLE_STATUSES,
    TERMINAL_STATUSES,
    QuestAction,
    QuestStatus,
    Recurrence,
    allowed_actions,
    is_overdue,
    next_status,
    occurrence_key,
)
from lifeexe.domain.rewards import Difficulty, GameConfig, capped_reward, coins_for_xp, quest_base_xp
from lifeexe.repositories import ledger
from lifeexe.repositories import quests as quests_repo
from lifeexe.repositories import skills as skills_repo
from lifeexe.repositories.ledger import NewXpEvent
from lifeexe.repositories.quests import QuestFilters
from lifeexe.services.achievements import evaluate_achievements
from lifeexe.services.common import UserDay, progress_dict, user_day

#: Actions handled by the generic transition endpoint (no reward side effects).
SIMPLE_ACTIONS = frozenset(
    {
        QuestAction.PUBLISH,
        QuestAction.START,
        QuestAction.PAUSE,
        QuestAction.RESUME,
        QuestAction.CANCEL,
        QuestAction.EXPIRE,
        QuestAction.RESTORE,
    }
)


def quest_dict(row: Row, ud: UserDay, game: GameConfig) -> dict[str, Any]:
    status = QuestStatus(row["status"])
    recurrence = Recurrence(row["recurrence"])
    due = date.fromisoformat(row["due_date"]) if row["due_date"] else None
    occurrence_done = bool(row["occurrence_completed"])
    base = quest_base_xp(Difficulty(row["difficulty"]), game)
    archived = row["archived_at"] is not None
    actions = [] if archived else [a.value for a in allowed_actions(status, recurrence, occurrence_done)]
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "category": row["category"],
        "priority": row["priority"],
        "difficulty": row["difficulty"],
        "status": status.value,
        "recurrence": recurrence.value,
        "estimated_minutes": row["estimated_minutes"],
        "due_date": row["due_date"],
        "completion_criteria": row["completion_criteria"],
        "skill": (
            {"id": row["skill_id"], "name": row["skill_name"], "attribute": row["skill_attribute"]}
            if row["skill_id"] is not None
            else None
        ),
        "xp_reward": base,
        "coin_reward": coins_for_xp(base, game),
        "occurrence_completed": occurrence_done,
        "completion_count": int(row["completion_count"]),
        "overdue": is_overdue(status, due, ud.today) and recurrence is Recurrence.NONE,
        "archived": archived,
        "allowed_actions": actions,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


class QuestService:
    def __init__(self, db: Database, clock: Clock, game: GameConfig) -> None:
        self.db = db
        self.clock = clock
        self.game = game

    # --- reads -------------------------------------------------------------

    def _load(self, conn: Connection, ud: UserDay, quest_id: int) -> Row:
        row = quests_repo.get(conn, ud.user_id, quest_id, ud.day_key, ud.week_key)
        if row is None:
            raise NotFound("Quest not found.")  # also for other users' quests: no existence leak
        return row

    def get(self, user_id: int, quest_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            ud = user_day(conn, user_id, self.clock.now())
            q = quest_dict(self._load(conn, ud, quest_id), ud, self.game)
            q["history"] = [
                {
                    "id": c["id"],
                    "occurrence_key": c["occurrence_key"],
                    "local_date": c["local_date"],
                    "completed_at": c["completed_at"],
                    "reversed_at": c["reversed_at"],
                    "xp_awarded": c["xp_awarded"] or 0,
                }
                for c in quests_repo.completion_history(conn, user_id, quest_id)
            ]
            return q

    def list(self, user_id: int, filters: QuestFilters) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            ud = user_day(conn, user_id, self.clock.now())
            rows, total = quests_repo.list_quests(conn, user_id, filters, ud.day_key, ud.week_key)
            return {
                "items": [quest_dict(r, ud, self.game) for r in rows],
                "total": total,
                "limit": filters.limit,
                "offset": filters.offset,
            }

    # --- writes ------------------------------------------------------------

    def _check_skill(self, conn: Connection, user_id: int, skill_id: int | None) -> None:
        if skill_id is not None and skills_repo.get(conn, user_id, skill_id) is None:
            raise NotFound("Skill not found.")

    def create(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            self._check_skill(conn, user_id, data.get("skill_id"))
            as_draft = bool(data.pop("as_draft", False))
            fields = {
                **data,
                "status": (QuestStatus.DRAFT if as_draft else QuestStatus.AVAILABLE).value,
                "created_at": ud.now_iso,
                "updated_at": ud.now_iso,
            }
            quest_id = quests_repo.insert(conn, user_id, fields)
            return quest_dict(self._load(conn, ud, quest_id), ud, self.game)

    def update(self, user_id: int, quest_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            row = self._load(conn, ud, quest_id)
            status = QuestStatus(row["status"])
            if row["archived_at"] is not None:
                raise Conflict("Unarchive the quest before editing it.")
            if status not in EDITABLE_STATUSES:
                raise Conflict(f"A {status.value} quest cannot be edited. Reopen or restore it first.")
            recurrence_changed = "recurrence" in changes and changes["recurrence"] != row["recurrence"]
            started = status not in (QuestStatus.DRAFT, QuestStatus.AVAILABLE) or int(row["completion_count"])
            if recurrence_changed and started:
                raise Conflict("Recurrence can only change before a quest is started.")
            if "skill_id" in changes:
                self._check_skill(conn, user_id, changes["skill_id"])
            if changes:
                quests_repo.update(conn, user_id, quest_id, {**changes, "updated_at": ud.now_iso})
            return quest_dict(self._load(conn, ud, quest_id), ud, self.game)

    def delete(self, user_id: int, quest_id: int) -> None:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            self._load(conn, ud, quest_id)
            if quests_repo.has_any_completion(conn, user_id, quest_id):
                raise Conflict(
                    "This quest has completion history that backs your XP. Archive it instead of deleting it."
                )
            quests_repo.delete(conn, user_id, quest_id)

    def set_archived(self, user_id: int, quest_id: int, archived: bool) -> dict[str, Any]:
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            row = self._load(conn, ud, quest_id)
            status = QuestStatus(row["status"])
            if archived and status not in TERMINAL_STATUSES and status is not QuestStatus.DRAFT:
                raise Conflict("Only drafts and finished, cancelled or expired quests can be archived.")
            quests_repo.update(
                conn,
                user_id,
                quest_id,
                {"archived_at": ud.now_iso if archived else None, "updated_at": ud.now_iso},
            )
            return quest_dict(self._load(conn, ud, quest_id), ud, self.game)

    def transition(self, user_id: int, quest_id: int, action: QuestAction) -> dict[str, Any]:
        if action not in SIMPLE_ACTIONS:
            raise Conflict(f"Use the dedicated endpoint to {action.value} a quest.")
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            row = self._load(conn, ud, quest_id)
            if row["archived_at"] is not None:
                raise Conflict("Unarchive the quest first.")
            new = next_status(QuestStatus(row["status"]), action, Recurrence(row["recurrence"]))
            fields: dict[str, Any] = {"status": new.value, "updated_at": ud.now_iso}
            if action is QuestAction.START and row["started_at"] is None:
                fields["started_at"] = ud.now_iso
            quests_repo.update(conn, user_id, quest_id, fields)
            return quest_dict(self._load(conn, ud, quest_id), ud, self.game)

    def complete(self, user_id: int, quest_id: int) -> dict[str, Any]:
        try:
            with self.db.transaction() as conn:
                return self._complete(conn, user_id, quest_id)
        except Exception as exc:
            # Defence in depth: if two writers ever got past the existence check,
            # the partial unique index rejects the second completion.
            if is_unique_violation(exc):
                raise AlreadyCompleted("This quest occurrence is already completed.") from None
            raise

    def _complete(self, conn: Connection, user_id: int, quest_id: int) -> dict[str, Any]:
        ud = user_day(conn, user_id, self.clock.now())
        row = self._load(conn, ud, quest_id)
        if row["archived_at"] is not None:
            raise Conflict("Unarchive the quest first.")
        status = QuestStatus(row["status"])
        recurrence = Recurrence(row["recurrence"])
        occ = occurrence_key(recurrence, ud.today)
        if quests_repo.live_completion(conn, user_id, quest_id, occ) is not None:
            raise AlreadyCompleted("This quest occurrence is already completed.")
        new_status = next_status(status, QuestAction.COMPLETE, recurrence)

        total_before = ledger.total_xp(conn, user_id)
        completion_id = quests_repo.insert_completion(conn, user_id, quest_id, occ, ud.today_iso, ud.now_iso)
        base = quest_base_xp(Difficulty(row["difficulty"]), self.game)
        reward = capped_reward(base, ledger.net_xp_on(conn, user_id, ud.today_iso), self.game)
        event_id = ledger.insert_xp_event(
            conn,
            NewXpEvent(
                user_id=user_id,
                amount=reward.xp,
                base_amount=base,
                reason="QUEST_COMPLETED",
                source_type="QUEST_COMPLETION",
                source_id=completion_id,
                skill_id=row["skill_id"],
                attribute=row["skill_attribute"],
                idempotency_key=f"quest_completion:{completion_id}",
                local_date=ud.today_iso,
                created_at=ud.now_iso,
            ),
        )
        if reward.coins:
            ledger.insert_coin_tx(
                conn, user_id, reward.coins, "QUEST_REWARD", event_id, f"coins:xp_event:{event_id}", ud.now_iso
            )
        fields: dict[str, Any] = {"status": new_status.value, "updated_at": ud.now_iso}
        if recurrence is Recurrence.NONE:
            fields["completed_at"] = ud.now_iso
        quests_repo.update(conn, user_id, quest_id, fields)

        total_after = ledger.total_xp(conn, user_id)
        unlocked = evaluate_achievements(conn, user_id, ud.now_iso)
        level_before = level_for_xp(max(total_before, 0))
        progress = progress_dict(max(total_after, 0))
        return {
            "quest": quest_dict(self._load(conn, ud, quest_id), ud, self.game),
            "reward": {
                "xp_awarded": reward.xp,
                "base_xp": reward.base_xp,
                "coins_awarded": reward.coins,
                "capped": reward.capped,
                "daily_cap": self.game.daily_xp_cap,
                "occurrence_key": occ,
            },
            "progress": progress,
            "level_before": level_before,
            "leveled_up": progress["level"] != level_before,
            "achievements_unlocked": unlocked,
        }

    def reopen(self, user_id: int, quest_id: int) -> dict[str, Any]:
        """Undo the current occurrence's completion with compensating ledger rows.

        The original award is never edited or deleted; a reversal event with
        the negated amount is appended (idempotency key ``reversal:<event>``,
        plus a unique index allowing one reversal per event). The reversal is
        dated to the original award's local date so daily analytics stay net.
        """
        with self.db.transaction() as conn:
            ud = user_day(conn, user_id, self.clock.now())
            row = self._load(conn, ud, quest_id)
            if row["archived_at"] is not None:
                raise Conflict("Unarchive the quest first.")
            recurrence = Recurrence(row["recurrence"])
            new_status = next_status(QuestStatus(row["status"]), QuestAction.REOPEN, recurrence)
            occ = occurrence_key(recurrence, ud.today)
            completion = quests_repo.live_completion(conn, user_id, quest_id, occ)
            if completion is None:
                raise Conflict("There is no completion to reopen for the current occurrence.")
            total_before = ledger.total_xp(conn, user_id)
            quests_repo.reverse_completion(conn, user_id, int(completion["id"]), ud.now_iso)
            award = ledger.award_for_source(conn, user_id, "QUEST_COMPLETION", int(completion["id"]))
            reversed_xp = 0
            if award is not None:
                reversed_xp = int(award["amount"])
                ledger.insert_xp_event(
                    conn,
                    NewXpEvent(
                        user_id=user_id,
                        amount=-reversed_xp,
                        base_amount=0,
                        reason="QUEST_REOPENED",
                        source_type="QUEST_COMPLETION",
                        source_id=int(completion["id"]),
                        skill_id=award["skill_id"],
                        attribute=award["attribute"],
                        idempotency_key=f"reversal:{award['id']}",
                        local_date=award["local_date"],
                        created_at=ud.now_iso,
                        reverses_event_id=int(award["id"]),
                    ),
                )
                coins = ledger.coin_tx_for_xp_event(conn, user_id, int(award["id"]))
                if coins is not None:
                    ledger.insert_coin_tx(
                        conn,
                        user_id,
                        -int(coins["amount"]),
                        "QUEST_REWARD_REVERSED",
                        int(award["id"]),
                        f"coins:reversal:{award['id']}",
                        ud.now_iso,
                    )
            fields: dict[str, Any] = {"status": new_status.value, "updated_at": ud.now_iso}
            if recurrence is Recurrence.NONE:
                fields["completed_at"] = None
            quests_repo.update(conn, user_id, quest_id, fields)
            total_after = ledger.total_xp(conn, user_id)
            return {
                "quest": quest_dict(self._load(conn, ud, quest_id), ud, self.game),
                "xp_reversed": reversed_xp,
                "progress": progress_dict(max(total_after, 0)),
                "level_before": level_for_xp(max(total_before, 0)),
            }
