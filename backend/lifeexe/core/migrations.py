"""Minimal, versioned SQL migration runner (Alembic-style, no dependencies).

- Migrations are plain ``NNNN_name.sql`` files per dialect, applied in order.
- Each file runs in one transaction together with its ``schema_migrations`` row.
- A SHA-256 checksum is stored; editing an already-applied migration is an
  error (create a new migration instead).
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_ROOT = Path(__file__).resolve().parents[2] / "migrations"


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()


def load_migrations(dialect: str = "sqlite") -> list[Migration]:
    folder = MIGRATIONS_ROOT / dialect
    migrations = []
    for path in sorted(folder.glob("*.sql")):
        version, _, name = path.stem.partition("_")
        if not version.isdigit():
            raise MigrationError(f"bad migration filename: {path.name}")
        migrations.append(Migration(version, name, path.read_text(encoding="utf-8")))
    versions = [m.version for m in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError("duplicate migration versions")
    return migrations


def apply_migrations(conn: sqlite3.Connection, dialect: str = "sqlite") -> list[str]:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version TEXT PRIMARY KEY,
               name TEXT NOT NULL,
               checksum TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )"""
    )
    applied = {
        r[0]: r[1] for r in conn.execute("SELECT version, checksum FROM schema_migrations")
    }
    newly_applied: list[str] = []
    for m in load_migrations(dialect):
        if m.version in applied:
            if applied[m.version] != m.checksum:
                raise MigrationError(
                    f"migration {m.version}_{m.name} changed after being applied"
                )
            continue
        now = datetime.now(UTC).isoformat(timespec="microseconds")
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in _split_statements(m.sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (m.version, m.name, m.checksum, now),
            )
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        newly_applied.append(f"{m.version}_{m.name}")
    return newly_applied


def _split_statements(sql: str) -> list[str]:
    """Split a script into statements using sqlite3.complete_statement, so
    semicolons inside string literals are handled correctly. ``--`` comments
    are kept with their statement (SQLite ignores them)."""
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            stmt = buffer.strip()
            if stmt and not all(
                ln.strip().startswith("--") or not ln.strip() for ln in stmt.splitlines()
            ):
                statements.append(stmt)
            buffer = ""
    if buffer.strip() and not all(
        ln.strip().startswith("--") or not ln.strip() for ln in buffer.splitlines()
    ):
        raise MigrationError("migration ends with an incomplete statement")
    return statements
