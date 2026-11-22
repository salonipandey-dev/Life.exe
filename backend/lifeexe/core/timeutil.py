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


_TIMEZONES = frozenset(available_timezones())

#: Legacy IANA names that browsers still report (e.g. Chromium returns
#: "Asia/Calcutta" for India) mapped to their canonical zone. Some tz
#: databases ship without these "backward" links, so we never rely on them.
TIMEZONE_ALIASES: dict[str, str] = {
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Asia/Rangoon": "Asia/Yangon",
    "Asia/Dacca": "Asia/Dhaka",
    "Asia/Thimbu": "Asia/Thimphu",
    "Asia/Ulan_Bator": "Asia/Ulaanbaatar",
    "Asia/Chongqing": "Asia/Shanghai",
    "Asia/Istanbul": "Europe/Istanbul",
    "Europe/Kiev": "Europe/Kyiv",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "America/Godthab": "America/Nuuk",
    "Atlantic/Faeroe": "Atlantic/Faroe",
    "Pacific/Truk": "Pacific/Chuuk",
    "Pacific/Ponape": "Pacific/Pohnpei",
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "Etc/UTC": "UTC",
    "Etc/Universal": "UTC",
}


def normalize_timezone(name: str) -> str | None:
    """Canonical IANA name for ``name``, or None if it is not a known zone.

    Only names in the installed zone list (or the alias table) are accepted,
    so arbitrary strings can never reach the filesystem lookup in ZoneInfo.
    """
    candidate = TIMEZONE_ALIASES.get(name, name)
    if candidate not in _TIMEZONES:
        return None
    try:
        ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return candidate


def is_valid_timezone(name: str) -> bool:
    return normalize_timezone(name) is not None


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
