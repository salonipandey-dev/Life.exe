from datetime import date, timedelta

import pytest

from lifeexe.domain.habits import (
    DayState,
    HabitHistory,
    Schedule,
    ScheduleKind,
    calendar,
    habit_stats,
    mask_to_weekdays,
    paused_days,
    weekdays_to_mask,
)

TODAY = date(2026, 11, 22)  # Sunday
DAILY = Schedule(ScheduleKind.DAILY)


def d(offset: int) -> date:
    """Day relative to TODAY (0 = today, -1 = yesterday)."""
    return TODAY + timedelta(days=offset)


def days(*offsets: int) -> frozenset[date]:
    return frozenset(d(o) for o in offsets)


def history(schedule: Schedule = DAILY, start: int = -20, **sets: frozenset[date]) -> HabitHistory:
    return HabitHistory(schedule=schedule, start=d(start), today=TODAY, **sets)


def test_consecutive_days_build_streak() -> None:
    s = habit_stats(history(done=days(-3, -2, -1, 0)))
    assert (s.current_streak, s.longest_streak) == (4, 4)


def test_today_pending_does_not_break_streak() -> None:
    s = habit_stats(history(done=days(-3, -2, -1)))
    assert s.current_streak == 3
    assert s.today_state is DayState.PENDING


def test_missed_day_breaks_current_but_keeps_longest() -> None:
    s = habit_stats(history(done=days(-10, -9, -8, -7, -5, -4)))
    assert s.longest_streak == 4
    assert s.current_streak == 0  # -3..-1 missed


def test_rest_day_is_neutral() -> None:
    s = habit_stats(history(done=days(-3, -1), rest=days(-2)))
    assert s.current_streak == 2  # rest neither extends nor breaks


def test_paused_days_are_neutral() -> None:
    s = habit_stats(history(done=days(-6, -5, -1), paused=days(-4, -3, -2)))
    assert s.current_streak == 3


def test_partial_past_day_breaks_but_partial_today_does_not() -> None:
    s = habit_stats(history(done=days(-3, -1), partial=days(-2)))
    assert s.current_streak == 1
    s2 = habit_stats(history(done=days(-2, -1), partial=days(0)))
    assert s2.current_streak == 2 and s2.today_state is DayState.PARTIAL


def test_weekday_schedule_skips_unscheduled_days() -> None:
    mwf = Schedule(ScheduleKind.WEEKDAYS, weekdays=frozenset({0, 2, 4}))
    # Mon 16, Wed 18, Fri 20 Nov done; Tue/Thu/Sat/Sun unscheduled.
    s = habit_stats(history(mwf, start=-6, done=days(-6, -4, -2)))
    assert s.current_streak == 3
    cal = dict(calendar(history(mwf, start=-6, done=days(-6, -4, -2)), days=7))
    assert cal[d(-5)] is DayState.NOT_SCHEDULED


def test_days_before_start_are_ignored() -> None:
    s = habit_stats(history(start=-2, done=days(-2, -1, 0)))
    assert s.current_streak == 3
    assert calendar(history(start=-2), days=5)[0][1] is DayState.BEFORE_START


def test_consistency_windows_and_unknown_when_no_data() -> None:
    fresh = habit_stats(history(start=0))
    assert fresh.windows[0].required == 0 and fresh.windows[0].rate is None

    s = habit_stats(history(start=-20, done=days(-6, -5, -3, -1), rest=days(-4)))
    w7 = s.windows[0]
    # last 7 days: -6..0; rest on -4 excluded; today pending excluded -> 5 required
    assert (w7.achieved, w7.required) == (4, 5)
    assert w7.rate == pytest.approx(0.8)


def test_weekly_count_streak_in_weeks() -> None:
    sched = Schedule(ScheduleKind.WEEKLY_COUNT, target_per_week=2)
    # weeks start Mondays: 2 Nov, 9 Nov, 16 Nov; current week starts 16 Nov (today Sun 22).
    done = frozenset({date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 10), date(2026, 11, 12)})
    h = HabitHistory(sched, start=date(2026, 11, 2), today=TODAY, done=done)
    s = habit_stats(h)
    assert s.unit == "week"
    assert s.current_streak == 2  # current week (0 so far) is still in progress
    assert s.week_progress == (0, 2)


def test_weekly_count_missed_week_breaks() -> None:
    sched = Schedule(ScheduleKind.WEEKLY_COUNT, target_per_week=2)
    done = frozenset({date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 17), date(2026, 11, 18)})
    s = habit_stats(HabitHistory(sched, start=date(2026, 11, 2), today=TODAY, done=done))
    assert s.longest_streak == 1 and s.current_streak == 1  # week of 9 Nov missed


def test_weekly_count_requires_target() -> None:
    with pytest.raises(ValueError):
        Schedule(ScheduleKind.WEEKLY_COUNT)


def test_mask_roundtrip() -> None:
    assert weekdays_to_mask(frozenset({0, 2, 4})) == 0b10101
    assert mask_to_weekdays(0b10101) == frozenset({0, 2, 4})
    with pytest.raises(ValueError):
        mask_to_weekdays(0)


def test_paused_days_expansion() -> None:
    result = paused_days([(d(-3), d(-2)), (d(-1), None)], TODAY)
    assert result == days(-3, -2, -1, 0)


def test_future_day_rejected() -> None:
    from lifeexe.domain.habits import day_state

    with pytest.raises(ValueError):
        day_state(history(), d(1))
