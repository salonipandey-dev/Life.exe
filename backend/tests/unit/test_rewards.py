import pytest

from lifeexe.domain.rewards import Difficulty, GameConfig, capped_reward, coins_for_xp, quest_base_xp

CFG = GameConfig()


@pytest.mark.parametrize(
    ("difficulty", "xp", "coins"),
    [(Difficulty.EASY, 15, 3), (Difficulty.MEDIUM, 35, 7), (Difficulty.HARD, 70, 14), (Difficulty.EPIC, 150, 30)],
)
def test_default_rewards(difficulty: Difficulty, xp: int, coins: int) -> None:
    assert quest_base_xp(difficulty, CFG) == xp
    assert coins_for_xp(xp, CFG) == coins


def test_cap_not_reached() -> None:
    r = capped_reward(70, net_xp_today=100, config=CFG)
    assert (r.xp, r.capped, r.coins) == (70, False, 14)


def test_cap_partially_reached() -> None:
    r = capped_reward(70, net_xp_today=1480, config=CFG)
    assert (r.xp, r.base_xp, r.capped) == (20, 70, True)


def test_cap_fully_reached_gives_zero_never_negative() -> None:
    r = capped_reward(150, net_xp_today=5000, config=CFG)
    assert (r.xp, r.coins, r.capped) == (0, 0, True)


def test_negative_net_today_does_not_raise_headroom() -> None:
    # Reversals can make the day's net negative; headroom stays at the cap.
    r = capped_reward(150, net_xp_today=-300, config=CFG)
    assert r.xp == 150


def test_negative_base_rejected() -> None:
    with pytest.raises(ValueError):
        capped_reward(-1, 0, CFG)


def test_custom_config() -> None:
    cfg = GameConfig(daily_xp_cap=50)
    assert capped_reward(35, 30, cfg).xp == 20
