"""Character cosmetics: titles and avatars. Cosmetic only — no gameplay effect."""

from __future__ import annotations

#: (minimum level, title)
TITLES: tuple[tuple[int, str], ...] = (
    (1, "Novice"),
    (3, "Apprentice"),
    (5, "Adept"),
    (10, "Specialist"),
    (20, "Expert"),
    (35, "Architect"),
    (50, "Legend"),
)

AVATARS: tuple[str, ...] = ("sigil", "spark", "compass", "orbit", "crown", "leaf")
THEMES: tuple[str, ...] = ("obsidian", "ivory")


def unlocked_titles(level: int) -> list[str]:
    return [title for min_level, title in TITLES if level >= min_level]


def title_unlock_level(title: str) -> int | None:
    for min_level, t in TITLES:
        if t == title:
            return min_level
    return None
