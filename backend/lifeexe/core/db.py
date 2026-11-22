"""Database access: explicit connections and transactions.

The runtime engine is SQLite (stdlib ``sqlite3``) — see ADR-003. Every write
runs inside ``BEGIN IMMEDIATE``, which takes SQLite's write lock up front, so
read-check-write sequences (e.g. "is this occurrence already completed?",
"how much XP was awarded today?") are serialised and cannot race. The
equivalent on PostgreSQL is a ``SELECT ... FOR UPDATE`` on the user's profile
row at the start of the transaction (documented in docs/04-database-design.md).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lifeexe.core.migrations import apply_migrations

Row = sqlite3.Row
Connection = sqlite3.Connection


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    def initialize(self) -> list[str]:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            return apply_migrations(conn)
        finally:
            conn.close()

    @contextmanager
    def transaction(self, *, write: bool = True) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN DEFERRED")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def ping(self) -> bool:
        conn = self.connect()
        try:
            return bool(conn.execute("SELECT 1").fetchone()[0] == 1)
        finally:
            conn.close()


def is_unique_violation(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.IntegrityError) and "UNIQUE constraint failed" in str(exc)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {k: row[k] for k in row.keys()}  # noqa: SIM118 (sqlite3.Row is not a dict)
