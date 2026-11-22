from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from lifeexe.core.db import Connection
from lifeexe.core.errors import NotFound
from lifeexe.core.timeutil import local_date, to_iso
from lifeexe.domain.quests import Recurrence, occurrence_key
from lifeexe.repositories import users as users_repo


@dataclass(frozen=True)
class UserDay:
    """The user's notion of "now" and "today" for one request."""

    user_id: int
    now: datetime
    timezone: str
    day_start_hour: int
    today: date

    @property
    def now_iso(self) -> str:
        return to_iso(self.now)

    @property
    def today_iso(self) -> str:
        return self.today.isoformat()

    @property
    def day_key(self) -> str:
        return occurrence_key(Recurrence.DAILY, self.today)

    @property
    def week_key(self) -> str:
        return occurrence_key(Recurrence.WEEKLY, self.today)


def user_day(conn: Connection, user_id: int, now: datetime) -> UserDay:
    profile = users_repo.get_profile(conn, user_id)
    if profile is None:
        raise NotFound("Profile not found.")
    tz = profile["timezone"]
    start = int(profile["day_start_hour"])
    return UserDay(user_id, now, tz, start, local_date(now, tz, start))


def progress_dict(total_xp: int) -> dict[str, object]:
    from lifeexe.domain.leveling import level_progress

    p = level_progress(total_xp)
    return {
        "level": p.level,
        "total_xp": p.total_xp,
        "level_floor_xp": p.level_floor_xp,
        "next_level_xp": p.next_level_xp,
        "xp_into_level": p.xp_into_level,
        "xp_span": p.xp_span,
        "xp_to_next_level": p.xp_to_next_level,
        "progress_ratio": round(p.progress_ratio, 4),
    }
