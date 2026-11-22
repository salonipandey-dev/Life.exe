from __future__ import annotations

from typing import Any

from lifeexe.core.db import Connection, Database
from lifeexe.core.timeutil import from_iso
from lifeexe.domain.achievements import BY_KEY, CATALOG, AchievementStats, earned_keys
from lifeexe.domain.leveling import level_for_xp
from lifeexe.repositories import achievements as ach_repo
from lifeexe.repositories import habits as habits_repo
from lifeexe.repositories import ledger
from lifeexe.repositories import skills as skills_repo


def _stats(conn: Connection, user_id: int, now_iso: str) -> AchievementStats:
    from lifeexe.services.common import user_day
    from lifeexe.services.habits import best_daily_streak
    from lifeexe.services.skills import demonstrated_count

    today = user_day(conn, user_id, from_iso(now_iso)).today

    completed, epic, boss = ach_repo.quest_completion_stats(conn, user_id)
    return AchievementStats(
        quests_completed=completed,
        epic_quests_completed=epic,
        boss_quests_completed=boss,
        level=level_for_xp(max(ledger.total_xp(conn, user_id), 0)),
        habit_days_done=habits_repo.done_days_count(conn, user_id),
        best_daily_streak=best_daily_streak(conn, user_id, today),
        evidence_count=skills_repo.evidence_count(conn, user_id),
        skills_demonstrated=demonstrated_count(conn, user_id),
    )


def evaluate_achievements(conn: Connection, user_id: int, now_iso: str) -> list[dict[str, Any]]:
    """Idempotent: safe to call after any event, any number of times."""
    newly = []
    for key in sorted(earned_keys(_stats(conn, user_id, now_iso))):
        if ach_repo.insert_if_missing(conn, user_id, key, now_iso):
            a = BY_KEY[key]
            newly.append({"key": a.key, "title": a.title, "description": a.description})
    return newly


class AchievementService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def gallery(self, user_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            unlocked = {r["achievement_key"]: r["unlocked_at"] for r in ach_repo.unlocked(conn, user_id)}
        items = []
        for a in CATALOG:
            got = a.key in unlocked
            hidden = a.hidden and not got
            items.append(
                {
                    "key": a.key,
                    "title": "Hidden achievement" if hidden else a.title,
                    "description": "Keep playing to discover this one." if hidden else a.description,
                    "category": a.category,
                    "hidden": hidden,
                    "unlocked": got,
                    "unlocked_at": unlocked.get(a.key),
                }
            )
        return {"achievements": items, "unlocked_count": len(unlocked), "total": len(CATALOG)}
