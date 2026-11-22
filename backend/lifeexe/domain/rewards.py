"""Reward rules: XP and coins.

The server is the only place rewards are calculated. Clients never send XP or
coin amounts; request schemas reject such fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class Difficulty(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EPIC = "EPIC"


class Attribute(StrEnum):
    """Character attributes. Values reflect *logged activity only* — they make no
    claim about a person's real intelligence, health or worth."""

    INTELLECT = "INTELLECT"
    DISCIPLINE = "DISCIPLINE"
    CREATIVITY = "CREATIVITY"
    STRENGTH = "STRENGTH"
    KNOWLEDGE = "KNOWLEDGE"
    COMMUNICATION = "COMMUNICATION"
    FINANCIAL_LITERACY = "FINANCIAL_LITERACY"
    CAREER_DEVELOPMENT = "CAREER_DEVELOPMENT"


_DEFAULT_XP: Mapping[Difficulty, int] = MappingProxyType(
    {
        Difficulty.EASY: 15,
        Difficulty.MEDIUM: 35,
        Difficulty.HARD: 70,
        Difficulty.EPIC: 150,
    }
)


@dataclass(frozen=True)
class GameConfig:
    xp_by_difficulty: Mapping[Difficulty, int] = field(default_factory=lambda: _DEFAULT_XP)
    #: coins = awarded XP // coin_divisor  (EASY 3, MEDIUM 7, HARD 14, EPIC 30)
    coin_divisor: int = 5
    #: XP for a completed habit day
    habit_checkin_xp: int = 5
    #: Soft daily ceiling on *net* XP awarded per local day, across all sources.
    #: Completions beyond the cap are still recorded; only the XP is limited.
    daily_xp_cap: int = 1500


@dataclass(frozen=True)
class Reward:
    base_xp: int
    xp: int
    coins: int
    capped: bool


def coins_for_xp(xp: int, config: GameConfig) -> int:
    return max(xp, 0) // config.coin_divisor


def capped_reward(base_xp: int, net_xp_today: int, config: GameConfig) -> Reward:
    """Apply the daily cap to a base XP amount.

    ``net_xp_today`` is the net XP already awarded on the same local day
    (awards minus reversals). The award is reduced to the remaining headroom;
    it is never negative, so a capped completion can earn 0 XP but is never a
    penalty.
    """
    if base_xp < 0:
        raise ValueError("base_xp must be >= 0")
    headroom = max(config.daily_xp_cap - max(net_xp_today, 0), 0)
    xp = min(base_xp, headroom)
    return Reward(base_xp=base_xp, xp=xp, coins=coins_for_xp(xp, config), capped=xp < base_xp)


def quest_base_xp(difficulty: Difficulty, config: GameConfig) -> int:
    return config.xp_by_difficulty[difficulty]
