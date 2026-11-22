from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from lifeexe.core.db import Database
from lifeexe.core.errors import BadRequest
from lifeexe.core.timeutil import Clock
from lifeexe.domain.analytics import (
    Rate,
    completion_rate_insight,
    completions_insight,
    fill_daily,
    top_attribute_insight,
)
from lifeexe.domain.habits import week_start
from lifeexe.domain.rewards import Attribute
from lifeexe.repositories import analytics as analytics_repo
from lifeexe.repositories import habits as habits_repo
from lifeexe.repositories import ledger
from lifeexe.repositories import skills as skills_repo
from lifeexe.services.common import user_day

MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 28

METRIC_DEFINITIONS: dict[str, str] = {
    "net_xp": (
        "Sum of XP ledger amounts dated to each local day, including reversals (so a reopened quest nets to zero)."
    ),
    "quest_completions": (
        "Live (not reopened) quest completions, by the local day they were recorded. "
        "A recurring quest counts once per occurrence."
    ),
    "habit_days": "Habit entries that met their daily target, by local day.",
    "activity": "Quest completions plus habit days met, per local day.",
    "completion_rate": (
        "One-off quests due in the week that were completed, divided by those due in the week that are "
        "completed or already past due. Drafts, cancelled quests and quests without a due date are excluded."
    ),
    "xp_by_attribute": (
        "Net XP in the range grouped by the attribute of the linked skill or habit. "
        "'UNASSIGNED' is XP from quests without a linked skill."
    ),
}


def _dense(values: dict[str, int], start: date, end: date) -> list[dict[str, Any]]:
    as_dates = {date.fromisoformat(k): v for k, v in values.items()}
    return [{"date": d.isoformat(), "value": v} for d, v in fill_daily(start, end, as_dates)]


class AnalyticsService:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def summary(self, user_id: int, start: date | None, end: date | None) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            ud = user_day(conn, user_id, self.clock.now())
            end = end or ud.today
            start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
            if start > end:
                raise BadRequest("'from' must be on or before 'to'.")
            if (end - start).days + 1 > MAX_RANGE_DAYS:
                raise BadRequest(f"Date range is limited to {MAX_RANGE_DAYS} days.")
            s, e = start.isoformat(), end.isoformat()

            xp_day = ledger.xp_by_day(conn, user_id, s, e)
            comp_day = analytics_repo.completions_by_day(conn, user_id, s, e)
            habit_day = habits_repo.done_by_day(conn, user_id, s, e)
            activity = {k: comp_day.get(k, 0) + habit_day.get(k, 0) for k in {*comp_day, *habit_day}}

            by_attr = ledger.xp_by_attribute(conn, user_id, s, e)
            attributes = [{"attribute": a.value, "xp": by_attr.get(a.value, 0)} for a in Attribute]
            if by_attr.get("UNASSIGNED"):
                attributes.append({"attribute": "UNASSIGNED", "xp": by_attr["UNASSIGNED"]})

            names = {int(r["id"]): (r["name"], r["tree"]) for r in skills_repo.list_skills(conn, user_id, True)}
            by_skill = sorted(ledger.xp_by_skill(conn, user_id, s, e).items(), key=lambda kv: (-kv[1], kv[0]))
            skills = [
                {
                    "skill_id": sid,
                    "name": names.get(sid, ("Unknown", ""))[0],
                    "tree": names.get(sid, ("", ""))[1],
                    "xp": xp,
                }
                for sid, xp in by_skill
                if xp > 0
            ][:8]

            categories = analytics_repo.completions_by_category(conn, user_id, s, e)

            # Week-over-week comparison is always "this week vs last week",
            # independent of the selected range.
            ws = week_start(ud.today)
            last_ws, last_we = ws - timedelta(days=7), ws - timedelta(days=1)
            this_c = sum(analytics_repo.completions_by_day(conn, user_id, ws.isoformat(), ud.today_iso).values())
            last_c = sum(
                analytics_repo.completions_by_day(conn, user_id, last_ws.isoformat(), last_we.isoformat()).values()
            )
            this_rate = Rate(
                *analytics_repo.due_quest_rate(
                    conn, user_id, ws.isoformat(), (ws + timedelta(days=6)).isoformat(), ud.today_iso
                )
            )
            last_rate = Rate(
                *analytics_repo.due_quest_rate(conn, user_id, last_ws.isoformat(), last_we.isoformat(), ud.today_iso)
            )

            insights = [
                i
                for i in (
                    completions_insight(this_c, last_c),
                    top_attribute_insight(by_attr, "in this range"),
                    completion_rate_insight(this_rate, last_rate),
                )
                if i is not None
            ]

            def rate_dict(r: Rate) -> dict[str, Any]:
                return {
                    "completed": r.achieved,
                    "counted": r.required,
                    "rate": None if r.value is None else round(r.value, 4),
                }

            return {
                "range": {
                    "from": s,
                    "to": e,
                    "days": (end - start).days + 1,
                    "timezone": ud.timezone,
                    "day_start_hour": ud.day_start_hour,
                },
                "totals": {
                    "net_xp": sum(xp_day.values()),
                    "quest_completions": sum(comp_day.values()),
                    "habit_days": sum(habit_day.values()),
                    "active_days": sum(1 for v in activity.values() if v > 0),
                },
                "series": {
                    "net_xp": _dense(xp_day, start, end),
                    "quest_completions": _dense(comp_day, start, end),
                    "habit_days": _dense(habit_day, start, end),
                    "activity": _dense(activity, start, end),
                },
                "xp_by_attribute": attributes,
                "xp_by_skill": skills,
                "completions_by_category": [{"category": k, "count": v} for k, v in sorted(categories.items())],
                "weekly": {
                    "this_week_start": ws.isoformat(),
                    "completions_this_week": this_c,
                    "completions_last_week": last_c,
                    "completion_rate_this_week": rate_dict(this_rate),
                    "completion_rate_last_week": rate_dict(last_rate),
                },
                "insights": [{"kind": i.kind, "text": i.text, "basis": i.basis} for i in insights],
                "definitions": METRIC_DEFINITIONS,
            }
