"""Validates migrations/postgres against a real, throwaway PostgreSQL 16 server.

The runtime uses SQLite (ADR-003); this suite proves the PostgreSQL schema is
valid and enforces the same integrity rules, so the migration to PostgreSQL is
a driver change rather than a redesign. Skipped when PostgreSQL binaries are
not installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres

PG_BIN = Path(os.getenv("LIFEEXE_PG_BIN", "/usr/lib/postgresql/16/bin"))
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "postgres" / "0001_initial.sql"
PORT = "55439"


def _as_postgres(cmd: list[str]) -> list[str]:
    # initdb/postgres refuse to run as root; drop privileges when we are root.
    if os.geteuid() == 0:
        return ["runuser", "-u", "postgres", "--", *cmd]
    return cmd


@pytest.fixture(scope="module")
def pg() -> Iterator[str]:
    if not (PG_BIN / "initdb").exists() or (os.geteuid() == 0 and shutil.which("runuser") is None):
        pytest.skip("PostgreSQL 16 binaries not available")
    base = tempfile.mkdtemp(prefix="lifeexe-pg-")
    if os.geteuid() == 0:
        shutil.chown(base, user="postgres")
    data = os.path.join(base, "data")
    subprocess.run(
        _as_postgres([str(PG_BIN / "initdb"), "-D", data, "-A", "trust", "-U", "postgres"]),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        _as_postgres(
            [
                str(PG_BIN / "pg_ctl"),
                "-D",
                data,
                "-l",
                os.path.join(base, "log"),
                "-w",
                "-o",
                f"-k {base} -p {PORT} -c listen_addresses=''",
                "start",
            ]
        ),
        check=True,
        capture_output=True,
    )
    try:
        yield base
    finally:
        subprocess.run(
            _as_postgres([str(PG_BIN / "pg_ctl"), "-D", data, "-m", "immediate", "stop"]), capture_output=True
        )
        shutil.rmtree(base, ignore_errors=True)


def psql(host: str, sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _as_postgres(
            [
                str(PG_BIN / "psql"),
                "-h",
                host,
                "-p",
                PORT,
                "-U",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-X",
                "-q",
                "-At",
                "-c",
                sql,
            ]
        ),
        capture_output=True,
        text=True,
    )


def ok(host: str, sql: str) -> str:
    r = psql(host, sql)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def fails(host: str, sql: str, fragment: str) -> None:
    r = psql(host, sql)
    assert r.returncode != 0, f"expected failure: {sql}"
    assert fragment in r.stderr, r.stderr


@pytest.fixture(scope="module")
def db(pg: str) -> str:
    r = subprocess.run(
        _as_postgres(
            [
                str(PG_BIN / "psql"),
                "-h",
                pg,
                "-p",
                PORT,
                "-U",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-X",
                "-q",
                "-f",
                "-",
            ]
        ),
        input=MIGRATION.read_text(),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    now = "'2026-11-22T10:00:00Z'"
    ok(
        pg,
        f"""
        INSERT INTO users (email, password_hash, created_at, updated_at) VALUES
          ('alice@example.com', 'x', {now}, {now}), ('bob@example.com', 'x', {now}, {now});
        INSERT INTO skills (user_id, slug, name, tree, attribute, created_at) VALUES
          (1, 'sql', 'SQL', 'Data', 'INTELLECT', {now}), (2, 'sql', 'SQL', 'Data', 'INTELLECT', {now});
        INSERT INTO quests (user_id, title, category, priority, difficulty, status, created_at, updated_at)
          VALUES (1, 'q', 'SIDE', 'MEDIUM', 'MEDIUM', 'ACTIVE', {now}, {now});
    """,
    )
    return pg


def test_all_tables_created(db: str) -> None:
    tables = ok(db, "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
    assert tables == "14"


def test_one_live_completion_per_occurrence(db: str) -> None:
    ins = (
        "INSERT INTO quest_completions (user_id, quest_id, occurrence_key, local_date, completed_at) "
        "VALUES (1, 1, 'once', '2026-11-22', now())"
    )
    ok(db, ins)
    fails(db, ins, "ux_quest_completions_live")
    ok(db, "UPDATE quest_completions SET reversed_at = now() WHERE quest_id = 1")
    ok(db, ins)  # reopened occurrence may be completed again
    assert ok(db, "SELECT count(*) FROM quest_completions WHERE reversed_at IS NULL") == "1"


def test_composite_fk_blocks_cross_user_links(db: str) -> None:
    # quest of user 1 cannot reference skill 2, which belongs to user 2
    fails(db, "UPDATE quests SET skill_id = 2 WHERE id = 1", "foreign key")
    ok(db, "UPDATE quests SET skill_id = 1 WHERE id = 1")


def test_ledger_idempotency_and_reversal_rules(db: str) -> None:
    base = (
        "INSERT INTO xp_events (user_id, amount, base_amount, reason, source_type, idempotency_key, "
        "local_date, created_at{extra_cols}) VALUES (1, {amount}, 35, '{reason}', 'QUEST_COMPLETION', "
        "'{key}', '2026-11-22', now(){extra_vals})"
    )
    ok(db, base.format(amount=35, reason="QUEST_COMPLETED", key="quest_completion:1", extra_cols="", extra_vals=""))
    fails(
        db,
        base.format(amount=35, reason="QUEST_COMPLETED", key="quest_completion:1", extra_cols="", extra_vals=""),
        "duplicate key",
    )
    fails(db, base.format(amount=-35, reason="QUEST_COMPLETED", key="neg", extra_cols="", extra_vals=""), "check")
    rev = base.format(
        amount=-35, reason="QUEST_REOPENED", key="{k}", extra_cols=", reverses_event_id", extra_vals=", 1"
    )
    ok(db, rev.replace("{k}", "reversal:1"))
    fails(db, rev.replace("{k}", "reversal:1b"), "ux_xp_events_single_reversal")
    assert ok(db, "SELECT sum(amount) FROM xp_events WHERE user_id = 1") == "0"


def test_check_constraints(db: str) -> None:
    fails(
        db,
        "INSERT INTO users (email, password_hash, created_at, updated_at) VALUES ('UPPER@x.com', 'x', now(), now())",
        "check",
    )
    fails(db, "UPDATE quests SET status = 'WON' WHERE id = 1", "check")
    ok(
        db,
        "INSERT INTO profiles (user_id, display_name, title, avatar, timezone, created_at, updated_at) "
        "VALUES (1, 'Alice', 'Novice', 'sigil', 'UTC', now(), now())",
    )
    fails(db, "UPDATE profiles SET day_start_hour = 9 WHERE user_id = 1", "check")


def test_delete_user_cascades_everything(db: str) -> None:
    ok(db, "DELETE FROM users WHERE id = 1")
    for table in ("quests", "quest_completions", "xp_events", "skills", "profiles"):
        assert ok(db, f"SELECT count(*) FROM {table} WHERE user_id = 1") == "0", table
    assert ok(db, "SELECT count(*) FROM skills WHERE user_id = 2") == "1"
