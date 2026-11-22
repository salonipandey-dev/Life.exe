"""Level progression rules.

Cumulative XP required to *reach* level L:

    XP_required(L) = round(100 * (L - 1) ** 1.5)

Level 1 starts at 0 XP. The value is computed with integer arithmetic only, so the
result is exact and identical on every machine:

    100 * n**1.5 == sqrt(10_000 * n**3)          (n = L - 1)

We take the exact integer square root f = isqrt(v) and round half-up:
sqrt(v) >= f + 0.5  <=>  v >= f*f + f + 0.25  <=>  v - f*f > f   (v, f integers)
A tie (exactly .5) is impossible because (f + 0.5)**2 is never an integer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

XP_BASE = 100


def xp_required_for_level(level: int) -> int:
    """Total XP needed to reach ``level`` (level 1 == 0 XP)."""
    if level < 1:
        raise ValueError("level must be >= 1")
    n = level - 1
    value = XP_BASE * XP_BASE * n**3
    root = math.isqrt(value)
    return root if value - root * root <= root else root + 1


def level_for_xp(total_xp: int) -> int:
    """Highest level whose threshold is <= ``total_xp``.

    Thresholds are strictly increasing, so an exponential search followed by a
    binary search gives O(log L) without any arbitrary level cap.
    """
    if total_xp < 0:
        raise ValueError("total_xp must be >= 0")
    low, high = 1, 2
    while xp_required_for_level(high) <= total_xp:
        low, high = high, high * 2
    # invariant: threshold(low) <= total_xp < threshold(high)
    while high - low > 1:
        mid = (low + high) // 2
        if xp_required_for_level(mid) <= total_xp:
            low = mid
        else:
            high = mid
    return low


@dataclass(frozen=True)
class LevelProgress:
    level: int
    total_xp: int
    level_floor_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_span: int

    @property
    def xp_to_next_level(self) -> int:
        return self.next_level_xp - self.total_xp

    @property
    def progress_ratio(self) -> float:
        """Display-only ratio in [0, 1). Never used for authoritative decisions."""
        return self.xp_into_level / self.xp_span


def level_progress(total_xp: int) -> LevelProgress:
    level = level_for_xp(total_xp)
    floor_xp = xp_required_for_level(level)
    next_xp = xp_required_for_level(level + 1)
    return LevelProgress(
        level=level,
        total_xp=total_xp,
        level_floor_xp=floor_xp,
        next_level_xp=next_xp,
        xp_into_level=total_xp - floor_xp,
        xp_span=next_xp - floor_xp,
    )
