"""Persistence layer: SQL lives here and only here.

Every query that touches user data takes ``user_id`` and filters on it. This is
the primary authorization boundary; composite foreign keys in the schema are a
second, database-level guarantee that rows cannot be linked across users.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_update(table: str, allowed: Iterable[str], fields: Mapping[str, Any]) -> tuple[str, list[Any]]:
    """Build ``UPDATE <table> SET a = ?, b = ?`` from a whitelist of columns.

    Column names come only from ``allowed`` (never from user input), so the
    dynamic SQL cannot be used for injection; values are always bound.
    """
    allowed_set = set(allowed)
    unknown = set(fields) - allowed_set
    if unknown:
        raise ValueError(f"columns not updatable: {sorted(unknown)}")
    assignments = ", ".join(f"{col} = ?" for col in fields)
    return f"UPDATE {table} SET {assignments}", list(fields.values())


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
