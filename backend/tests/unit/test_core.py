"""Time, security, rate limiting, migrations, analytics and achievement rules."""

import sqlite3
from datetime import UTC, date, datetime

import pytest

from lifeexe.core import migrations
from lifeexe.core.ratelimit import RateLimiter
from lifeexe.core.security import hash_password, hash_token, needs_rehash, verify_password
from lifeexe.core.timeutil import is_valid_timezone, local_date
from lifeexe.domain.achievements import AchievementStats, earned_keys
from lifeexe.domain.analytics import (
    Rate,
    completion_rate_insight,
    completions_insight,
    fill_daily,
    percent,
    top_attribute_insight,
)

# --- time -----------------------------------------------------------------------


def test_day_start_shifts_early_hours_to_previous_day() -> None:
    # 20:30 UTC Sun == 02:00 Mon in Kolkata; with a 04:00 day start it's still Sunday.
    instant = datetime(2026, 11, 22, 20, 30, tzinfo=UTC)
    assert local_date(instant, "Asia/Kolkata", 4) == date(2026, 11, 22)
    assert local_date(instant, "Asia/Kolkata", 0) == date(2026, 11, 23)


def test_dst_spring_forward_new_york() -> None:
    # 2026-03-08 02:00 local does not exist; 07:30 UTC == 03:30 EDT.
    instant = datetime(2026, 3, 8, 7, 30, tzinfo=UTC)
    assert local_date(instant, "America/New_York", 4) == date(2026, 3, 7)  # before 04:00 local
    assert local_date(datetime(2026, 3, 8, 8, 30, tzinfo=UTC), "America/New_York", 4) == date(2026, 3, 8)


def test_dst_fall_back_new_york() -> None:
    # 2026-11-01 01:30 happens twice locally; both are before the 04:00 day start.
    first = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)  # 01:30 EDT
    second = datetime(2026, 11, 1, 6, 30, tzinfo=UTC)  # 01:30 EST
    assert local_date(first, "America/New_York", 4) == date(2026, 10, 31)
    assert local_date(second, "America/New_York", 4) == date(2026, 10, 31)
    assert local_date(datetime(2026, 11, 1, 9, 0, tzinfo=UTC), "America/New_York", 4) == date(2026, 11, 1)


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        local_date(datetime(2026, 1, 1), "UTC", 0)


def test_timezone_validation() -> None:
    assert is_valid_timezone("Asia/Kolkata")
    assert not is_valid_timezone("Mars/Olympus")
    assert not is_valid_timezone("../../etc/passwd")


# --- security -------------------------------------------------------------------


def test_password_hash_roundtrip() -> None:
    h = hash_password("a long passphrase")
    assert h.startswith("scrypt$") and "a long passphrase" not in h
    assert verify_password("a long passphrase", h)
    assert not verify_password("a long passphrasE", h)


def test_same_password_different_salts() -> None:
    assert hash_password("same password!") != hash_password("same password!")


@pytest.mark.parametrize("stored", ["", "bcrypt$x", "scrypt$1$2$3", "scrypt$a$b$c$d$e", "plaintext"])
def test_malformed_hashes_fail_closed(stored: str) -> None:
    assert verify_password("anything", stored) is False


def test_needs_rehash_on_weaker_params() -> None:
    assert needs_rehash(hash_password("pw-1234567890", n=2**10))
    assert not needs_rehash(hash_password("pw-1234567890"))


def test_token_hash_is_deterministic_and_not_identity() -> None:
    assert hash_token("abc") == hash_token("abc") != "abc"


# --- rate limiter ---------------------------------------------------------------


def test_rate_limiter_window() -> None:
    now = [0.0]
    rl = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert rl.check("k") == (True, 0)
    assert rl.check("k") == (True, 0)
    allowed, retry = rl.check("k")
    assert not allowed and retry > 0
    assert rl.check("other")[0]
    now[0] = 61
    assert rl.check("k")[0]


# --- migrations -----------------------------------------------------------------


def test_statement_splitter_handles_semicolons_in_strings() -> None:
    sql = "CREATE TABLE t (x TEXT DEFAULT 'a;b');\n-- comment;\nINSERT INTO t VALUES ('c;d');\n"
    assert len(migrations._split_statements(sql)) == 2


def test_changed_migration_is_detected(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "sqlite"
    folder.mkdir()
    (folder / "0001_a.sql").write_text("CREATE TABLE a (id INTEGER);")
    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", tmp_path)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    assert migrations.apply_migrations(conn) == ["0001_a"]
    assert migrations.apply_migrations(conn) == []
    (folder / "0001_a.sql").write_text("CREATE TABLE a (id INTEGER, y TEXT);")
    with pytest.raises(migrations.MigrationError):
        migrations.apply_migrations(conn)


def test_failed_migration_rolls_back(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "sqlite"
    folder.mkdir()
    (folder / "0001_bad.sql").write_text("CREATE TABLE ok (id INTEGER);\nCREATE TABLE ok (id INTEGER);\n")
    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", tmp_path)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    with pytest.raises(sqlite3.OperationalError):
        migrations.apply_migrations(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "ok" not in tables
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


# --- analytics rules --------------------------------------------------------------


@pytest.mark.parametrize(("n", "d", "pct"), [(1, 3, 33), (2, 3, 67), (1, 2, 50), (1, 8, 13), (0, 5, 0), (5, 5, 100)])
def test_percent_half_up(n: int, d: int, pct: int) -> None:
    assert percent(n, d) == pct


def test_fill_daily_makes_gaps_explicit() -> None:
    series = fill_daily(date(2026, 1, 1), date(2026, 1, 3), {date(2026, 1, 2): 5})
    assert series == [(date(2026, 1, 1), 0), (date(2026, 1, 2), 5), (date(2026, 1, 3), 0)]


def test_insights_require_data() -> None:
    assert completions_insight(0, 0) is None
    assert top_attribute_insight({}, "this week") is None
    assert top_attribute_insight({"INTELLECT": 0, "DISCIPLINE": -5}, "this week") is None
    assert completion_rate_insight(Rate(2, 2), Rate(1, 2)) is None  # below minimum sample


def test_insight_text_and_basis() -> None:
    i = completions_insight(6, 4)
    assert i is not None and "6 quests" in i.text and i.basis == {"this_week": 6, "last_week": 4}
    t = top_attribute_insight({"INTELLECT": 300, "DISCIPLINE": 100}, "this week")
    assert t is not None and "Intellect (75% of 400 XP)" in t.text
    r = completion_rate_insight(Rate(3, 4), Rate(3, 5))
    assert r is not None and r.text == "Your weekly quest completion rate increased from 60% to 75%."


# --- achievements -----------------------------------------------------------------


def test_achievement_conditions() -> None:
    base = AchievementStats(0, 0, 0, 1, 0, 0, 0, 0)
    assert earned_keys(base) == set()
    s = AchievementStats(quests_completed=10, epic_quests_completed=1, boss_quests_completed=0, level=5,
                         habit_days_done=1, best_daily_streak=7, evidence_count=1, skills_demonstrated=0)
    assert earned_keys(s) == {"first_quest", "ten_quests", "epic_quest", "level_5", "first_checkin",
                              "streak_7", "proof_of_work"}
