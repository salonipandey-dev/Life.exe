"""Habit scheduling, streak and consistency rules (pure, no I/O).

All dates here are *local dates* — already shifted by the user's time zone and
day-start hour (see ``lifeexe.core.timeutil.local_date``). Because the rules
operate on calendar dates, daylight-saving transitions cannot create or drop a
day.

Principles
- A missed day ends a streak; it never removes XP or lowers an attribute.
- Rest days, paused periods and unscheduled days are *neutral*: they neither
  extend nor break a streak and are excluded from consistency denominators.
- Today is never counted as missed — it is still in progress.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum


class ScheduleKind(StrEnum):
    DAILY = "DAILY"
    WEEKDAYS = "WEEKDAYS"  # specific days of the week
    WEEKLY_COUNT = "WEEKLY_COUNT"  # N times per ISO week, any days


class Measure(StrEnum):
    BOOLEAN = "BOOLEAN"
    COUNT = "COUNT"
    DURATION = "DURATION"  # minutes


class DayState(StrEnum):
    DONE = "DONE"
    PARTIAL = "PARTIAL"  # logged, below target
    REST = "REST"
    PAUSED = "PAUSED"
    MISSED = "MISSED"
    PENDING = "PENDING"  # today, not yet done
    OPEN = "OPEN"  # weekly-count habit day without an entry (not a miss)
    NOT_SCHEDULED = "NOT_SCHEDULED"
    BEFORE_START = "BEFORE_START"


ALL_WEEKDAYS = frozenset(range(7))  # 0 = Monday ... 6 = Sunday


def weekdays_to_mask(days: frozenset[int]) -> int:
    if not days or any(d < 0 or d > 6 for d in days):
        raise ValueError("weekdays must be a non-empty subset of 0..6")
    return sum(1 << d for d in days)


def mask_to_weekdays(mask: int) -> frozenset[int]:
    if not 1 <= mask <= 127:
        raise ValueError("weekday mask must be in 1..127")
    return frozenset(d for d in range(7) if mask & (1 << d))


@dataclass(frozen=True)
class Schedule:
    kind: ScheduleKind
    weekdays: frozenset[int] = ALL_WEEKDAYS
    target_per_week: int | None = None

    def __post_init__(self) -> None:
        if self.kind is ScheduleKind.WEEKLY_COUNT and not (self.target_per_week and 1 <= self.target_per_week <= 7):
            raise ValueError("WEEKLY_COUNT habits need target_per_week in 1..7")
        if not self.weekdays:
            raise ValueError("at least one weekday is required")

    def is_scheduled(self, day: date) -> bool:
        if self.kind is ScheduleKind.WEEKDAYS:
            return day.weekday() in self.weekdays
        return True


@dataclass(frozen=True)
class HabitHistory:
    schedule: Schedule
    start: date
    today: date
    done: frozenset[date] = field(default_factory=frozenset)
    partial: frozenset[date] = field(default_factory=frozenset)
    rest: frozenset[date] = field(default_factory=frozenset)
    paused: frozenset[date] = field(default_factory=frozenset)

    @property
    def unit(self) -> str:
        return "week" if self.schedule.kind is ScheduleKind.WEEKLY_COUNT else "day"


@dataclass(frozen=True)
class ConsistencyWindow:
    label: str
    achieved: int
    required: int

    @property
    def rate(self) -> float | None:
        """None means "not enough data" — shown as such, never as 0%."""
        return None if self.required == 0 else self.achieved / self.required


@dataclass(frozen=True)
class HabitStats:
    unit: str
    current_streak: int
    longest_streak: int
    total_done: int
    today_state: DayState
    windows: tuple[ConsistencyWindow, ...]
    week_progress: tuple[int, int] | None  # (done this week, target) for weekly-count


def _days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def day_state(h: HabitHistory, day: date) -> DayState:
    if day < h.start:
        return DayState.BEFORE_START
    if day > h.today:
        raise ValueError("cannot evaluate a future day")
    if day in h.done:
        return DayState.DONE
    if day in h.paused:
        return DayState.PAUSED
    if day in h.rest:
        return DayState.REST
    if day in h.partial:
        return DayState.PARTIAL
    if h.schedule.kind is ScheduleKind.WEEKLY_COUNT:
        return DayState.PENDING if day == h.today else DayState.OPEN
    if not h.schedule.is_scheduled(day):
        return DayState.NOT_SCHEDULED
    return DayState.PENDING if day == h.today else DayState.MISSED


def _breaks_daily_streak(h: HabitHistory, day: date, state: DayState) -> bool:
    if day == h.today:
        return False
    if state is DayState.MISSED:
        return True
    # a below-target entry on a scheduled past day did not meet the habit
    return state is DayState.PARTIAL and h.schedule.is_scheduled(day)


def _daily_streaks(h: HabitHistory) -> tuple[int, int]:
    run = longest = 0
    for day in _days(h.start, h.today):
        state = day_state(h, day)
        if state is DayState.DONE:
            run += 1
            longest = max(longest, run)
        elif _breaks_daily_streak(h, day, state):
            run = 0
    return run, longest


def _week_met(h: HabitHistory, ws: date) -> tuple[bool, bool]:
    """(met, neutral) for the ISO week starting ``ws``."""
    target = h.schedule.target_per_week or 1
    days = [d for d in _days(ws, ws + timedelta(days=6)) if h.start <= d <= h.today]
    done = sum(1 for d in days if d in h.done)
    met = done >= target
    is_current = ws == week_start(h.today)
    first_partial_week = ws < h.start
    any_paused = any(d in h.paused for d in days)
    neutral = not met and (is_current or first_partial_week or any_paused)
    return met, neutral


def _weeks(h: HabitHistory) -> Iterator[date]:
    ws = week_start(h.start)
    last = week_start(h.today)
    while ws <= last:
        yield ws
        ws += timedelta(days=7)


def _weekly_streaks(h: HabitHistory) -> tuple[int, int]:
    run = longest = 0
    for ws in _weeks(h):
        met, neutral = _week_met(h, ws)
        if met:
            run += 1
            longest = max(longest, run)
        elif not neutral:
            run = 0
    return run, longest


def _daily_window(h: HabitHistory, days: int, label: str) -> ConsistencyWindow:
    first = max(h.start, h.today - timedelta(days=days - 1))
    achieved = required = 0
    for day in _days(first, h.today):
        is_done = day in h.done
        excused = day in h.paused or day in h.rest
        # Unscheduled days are neutral (a bonus entry on one is not counted);
        # rest/paused days are neutral unless the habit was done anyway.
        if not h.schedule.is_scheduled(day) or (excused and not is_done):
            continue
        if day == h.today and not is_done:
            continue  # today is still in progress
        required += 1
        achieved += int(is_done)
    return ConsistencyWindow(label=label, achieved=achieved, required=required)


def _weekly_window(h: HabitHistory, weeks: int, label: str) -> ConsistencyWindow:
    first = max(week_start(h.start), week_start(h.today) - timedelta(days=7 * (weeks - 1)))
    achieved = required = 0
    for ws in _weeks(h):
        if ws < first:
            continue
        met, neutral = _week_met(h, ws)
        if neutral:
            continue
        required += 1
        achieved += int(met)
    return ConsistencyWindow(label=label, achieved=achieved, required=required)


def habit_stats(h: HabitHistory) -> HabitStats:
    total_done = sum(1 for d in h.done if h.start <= d <= h.today)
    if h.schedule.kind is ScheduleKind.WEEKLY_COUNT:
        current, longest = _weekly_streaks(h)
        windows = (
            _weekly_window(h, 4, "Last 4 weeks"),
            _weekly_window(h, 12, "Last 12 weeks"),
        )
        ws = week_start(h.today)
        this_week = sum(1 for d in _days(ws, h.today) if d in h.done and d >= h.start)
        week_progress: tuple[int, int] | None = (this_week, h.schedule.target_per_week or 1)
    else:
        current, longest = _daily_streaks(h)
        windows = (
            _daily_window(h, 7, "Last 7 days"),
            _daily_window(h, 30, "Last 30 days"),
        )
        week_progress = None
    today = day_state(h, h.today) if h.today >= h.start else DayState.BEFORE_START
    return HabitStats(
        unit=h.unit,
        current_streak=current,
        longest_streak=longest,
        total_done=total_done,
        today_state=today,
        windows=windows,
        week_progress=week_progress,
    )


def calendar(h: HabitHistory, days: int = 28) -> list[tuple[date, DayState]]:
    first = h.today - timedelta(days=days - 1)
    return [(d, day_state(h, d)) for d in _days(first, h.today)]


def paused_days(intervals: list[tuple[date, date | None]], today: date) -> frozenset[date]:
    """Expand pause intervals (inclusive; open end == still paused) into dates."""
    result: set[date] = set()
    for start, end in intervals:
        result.update(_days(start, min(end or today, today)))
    return frozenset(result)
