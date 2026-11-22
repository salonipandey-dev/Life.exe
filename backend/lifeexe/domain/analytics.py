"""Analytics helpers and evidence-backed insights (pure).

Every insight carries the numbers it was derived from (``basis``) so the UI can
show exactly why it was produced. No insight is generated without data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping

#: Minimum number of countable quests in *each* compared week before a
#: completion-rate comparison is reported. Avoids "0% -> 100%" noise.
MIN_QUESTS_FOR_RATE_INSIGHT = 3


@dataclass(frozen=True)
class Insight:
    kind: str
    text: str
    basis: dict[str, int | str] = field(default_factory=dict)


@dataclass(frozen=True)
class Rate:
    achieved: int
    required: int

    @property
    def value(self) -> float | None:
        return None if self.required == 0 else self.achieved / self.required


def percent(numerator: int, denominator: int) -> int:
    """Integer percentage, rounded half-up, computed without floats."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (200 * numerator + denominator) // (2 * denominator)


def fill_daily(start: date, end: date, values: Mapping[date, int]) -> list[tuple[date, int]]:
    """Dense daily series; days without events are explicit zeros."""
    out: list[tuple[date, int]] = []
    day = start
    while day <= end:
        out.append((day, values.get(day, 0)))
        day += timedelta(days=1)
    return out


def completions_insight(this_week: int, last_week: int) -> Insight | None:
    if this_week == 0 and last_week == 0:
        return None
    noun = "quest" if this_week == 1 else "quests"
    if last_week == 0:
        text = f"You completed {this_week} {noun} this week."
    elif this_week == last_week:
        text = f"You completed {this_week} {noun} this week — the same as last week."
    else:
        text = f"You completed {this_week} {noun} this week, compared with {last_week} last week."
    return Insight("quest_completions", text, {"this_week": this_week, "last_week": last_week})


def top_attribute_insight(xp_by_attribute: Mapping[str, int], period_label: str) -> Insight | None:
    positive = {k: v for k, v in xp_by_attribute.items() if v > 0}
    total = sum(positive.values())
    if total <= 0:
        return None
    top, amount = max(sorted(positive.items()), key=lambda kv: kv[1])
    share = percent(amount, total)
    label = top.replace("_", " ").title()
    return Insight(
        "top_attribute",
        f"Most of your XP {period_label} went to {label} ({share}% of {total} XP).",
        {"attribute": top, "xp": amount, "total_xp": total, "percent": share},
    )


def completion_rate_insight(this_week: Rate, last_week: Rate) -> Insight | None:
    if min(this_week.required, last_week.required) < MIN_QUESTS_FOR_RATE_INSIGHT:
        return None
    now = percent(this_week.achieved, this_week.required)
    before = percent(last_week.achieved, last_week.required)
    if now == before:
        verb = f"held steady at {now}%"
    else:
        verb = f"{'increased' if now > before else 'changed'} from {before}% to {now}%"
    return Insight(
        "completion_rate",
        f"Your weekly quest completion rate {verb}.",
        {
            "this_week_completed": this_week.achieved,
            "this_week_counted": this_week.required,
            "last_week_completed": last_week.achieved,
            "last_week_counted": last_week.required,
        },
    )
