"""Time handling: one UTC clock, explicit local-date conversion.

Instants are always stored in UTC. A *local date* is the calendar day the user
experiences, after applying their IANA time zone and their day-start hour
(e.g. with a 04:00 day start, 01:30 on Tuesday still belongs to Monday).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests; can be advanced."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock needs an aware datetime")
        self._now = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, instant: datetime) -> None:
        self._now = instant.astimezone(UTC)

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)


def is_valid_timezone(name: str) -> bool:
    if name not in _TIMEZONES:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


_TIMEZONES = frozenset(available_timezones())


def local_date(instant: datetime, tz_name: str, day_start_hour: int) -> date:
    """Calendar day of ``instant`` for a user.

    Subtracting hours from an aware datetime in the *same* zone is wall-clock
    arithmetic in Python, which is exactly the intent: "01:30 local minus 4h"
    is the previous evening regardless of DST offsets.
    """
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    if not 0 <= day_start_hour <= 6:
        raise ValueError("day_start_hour must be between 0 and 6")
    local = instant.astimezone(ZoneInfo(tz_name))
    return (local - timedelta(hours=day_start_hour)).date()


def to_iso(instant: datetime) -> str:
    """Canonical fixed-width UTC timestamp, sortable as text."""
    return instant.astimezone(UTC).isoformat(timespec="microseconds")


def from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
