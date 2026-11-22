import math

import pytest

from lifeexe.domain.leveling import level_for_xp, level_progress, xp_required_for_level

KNOWN = {1: 0, 2: 100, 3: 283, 4: 520, 5: 800, 6: 1118, 10: 2700, 17: 6400, 26: 12500, 101: 100_000}


@pytest.mark.parametrize(("level", "xp"), sorted(KNOWN.items()))
def test_known_thresholds(level: int, xp: int) -> None:
    assert xp_required_for_level(level) == xp


def test_level_one_starts_at_zero() -> None:
    assert xp_required_for_level(1) == 0
    assert level_for_xp(0) == 1


@pytest.mark.parametrize("bad", [0, -1, -100])
def test_invalid_level_rejected(bad: int) -> None:
    with pytest.raises(ValueError):
        xp_required_for_level(bad)


def test_negative_xp_rejected() -> None:
    with pytest.raises(ValueError):
        level_for_xp(-1)


@pytest.mark.parametrize("level", range(2, 60))
def test_boundaries_exact(level: int) -> None:
    threshold = xp_required_for_level(level)
    assert level_for_xp(threshold - 1) == level - 1
    assert level_for_xp(threshold) == level
    assert level_for_xp(threshold + 1) == level


def test_strictly_increasing_and_gaps_grow() -> None:
    values = [xp_required_for_level(L) for L in range(1, 500)]
    gaps = [b - a for a, b in zip(values, values[1:])]
    assert all(g > 0 for g in gaps)
    assert all(b >= a for a, b in zip(gaps, gaps[1:])), "each level should cost at least as much as the last"


@pytest.mark.parametrize("level", list(range(1, 2000, 7)))
def test_integer_formula_matches_float_definition(level: int) -> None:
    # The float version is the spec; the integer version is what we ship.
    assert xp_required_for_level(level) == round(100 * (level - 1) ** 1.5)


def test_integer_formula_exact_for_huge_levels() -> None:
    # Float arithmetic loses precision here; isqrt does not.
    level = 10**7
    n = level - 1
    exact = math.isqrt(10_000 * n**3)
    assert xp_required_for_level(level) in (exact, exact + 1)


def test_level_progress_fields() -> None:
    p = level_progress(150)
    assert (p.level, p.level_floor_xp, p.next_level_xp) == (2, 100, 283)
    assert p.xp_into_level == 50
    assert p.xp_span == 183
    assert p.xp_to_next_level == 133
    assert 0 <= p.progress_ratio < 1


def test_large_xp_has_no_level_cap() -> None:
    assert level_for_xp(10**12) > 1000
