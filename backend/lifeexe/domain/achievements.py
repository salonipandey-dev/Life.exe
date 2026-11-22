"""Achievement catalog and evaluation (pure).

Achievements are derived from recorded events only. Evaluation is idempotent:
it returns the full set of keys whose condition currently holds, and the
persistence layer inserts any that are missing with ON CONFLICT DO NOTHING.

Policy: once unlocked, an achievement is kept even if the event that caused it
is later reversed (e.g. a quest is reopened). It records that the milestone was
reached at that time. Achievements grant no XP, so this cannot inflate levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AchievementStats:
    quests_completed: int
    epic_quests_completed: int
    boss_quests_completed: int
    level: int
    habit_days_done: int
    best_daily_streak: int
    evidence_count: int
    skills_demonstrated: int


@dataclass(frozen=True)
class AchievementDef:
    key: str
    title: str
    description: str
    category: str
    hidden: bool
    condition: Callable[[AchievementStats], bool]


CATALOG: tuple[AchievementDef, ...] = (
    AchievementDef("first_quest", "First Quest Completed", "Complete your first quest.",
                   "Productivity", False, lambda s: s.quests_completed >= 1),
    AchievementDef("ten_quests", "Ten Quests", "Complete ten quest occurrences.",
                   "Productivity", False, lambda s: s.quests_completed >= 10),
    AchievementDef("epic_quest", "Epic Undertaking", "Complete an Epic-difficulty quest.",
                   "Productivity", False, lambda s: s.epic_quests_completed >= 1),
    AchievementDef("boss_slayer", "Boss Slayer", "Complete a boss quest.",
                   "Productivity", True, lambda s: s.boss_quests_completed >= 1),
    AchievementDef("level_5", "Level 5", "Reach level 5.",
                   "Productivity", False, lambda s: s.level >= 5),
    AchievementDef("first_checkin", "First Check-in", "Complete a habit for the first time.",
                   "Consistency", False, lambda s: s.habit_days_done >= 1),
    AchievementDef("streak_7", "Seven-Day Streak", "Keep a daily habit going for seven days.",
                   "Consistency", False, lambda s: s.best_daily_streak >= 7),
    AchievementDef("proof_of_work", "Proof of Work", "Record your first piece of skill evidence.",
                   "Learning", False, lambda s: s.evidence_count >= 1),
    AchievementDef("skill_demonstrated", "Skill Demonstrated",
                   "Meet both the XP and evidence requirements of a skill.",
                   "Learning", False, lambda s: s.skills_demonstrated >= 1),
)

BY_KEY = {a.key: a for a in CATALOG}


def earned_keys(stats: AchievementStats) -> set[str]:
    return {a.key for a in CATALOG if a.condition(stats)}
