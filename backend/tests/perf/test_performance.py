"""Latency budget checks on a realistically large single-user dataset.

Dataset: 2,000 quests, 6,000 completions/ledger rows over 365 days, 5 habits
with a year of logs. Requests run in-process (Starlette TestClient), so the
numbers measure application + SQLite time, not network time.

Targets (p95): dashboard < 250 ms, quest list < 150 ms, analytics (90 days)
< 250 ms, quest completion < 150 ms. Results are written to
tests/perf/results.json for the test-execution report.
"""

from __future__ import annotations

import json
import platform
import sqlite3
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from tests.helpers import create_quest, start

pytestmark = pytest.mark.perf

TARGETS_MS = {"dashboard": 250, "quest_list": 150, "analytics_90d": 250, "complete_quest": 150}
RESULTS = Path(__file__).parent / "results.json"


def _seed(db_path: str, today: date) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("BEGIN")
    now = "2026-11-22T10:00:00.000000+00:00"
    diffs = ["EASY", "MEDIUM", "HARD", "EPIC"]
    xp = {"EASY": 15, "MEDIUM": 35, "HARD": 70, "EPIC": 150}
    quest_rows = []
    for i in range(2000):
        status = "COMPLETED" if i < 1500 else "AVAILABLE"
        due = (today - timedelta(days=i % 365)).isoformat() if i % 3 else None
        quest_rows.append(
            (1, f"Quest {i}", "SIDE", ["LOW", "MEDIUM", "HIGH"][i % 3], diffs[i % 4], status, due, now, now)
        )
    conn.executemany(
        "INSERT INTO quests (user_id, title, category, priority, difficulty, status, due_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        quest_rows,
    )
    for n in range(6000):
        qid = 1 + (n % 1500)
        day = (today - timedelta(days=n % 365)).isoformat()
        cur = conn.execute(
            "INSERT INTO quest_completions (user_id, quest_id, occurrence_key, local_date, completed_at) "
            "VALUES (1, ?, ?, ?, ?)",
            (qid, f"seed-{n}", day, now),
        )
        amount = xp[diffs[(qid - 1) % 4]]
        conn.execute(
            "INSERT INTO xp_events (user_id, amount, base_amount, reason, source_type, source_id, attribute, "
            "idempotency_key, local_date, created_at) VALUES (1, ?, ?, 'QUEST_COMPLETED', 'QUEST_COMPLETION', ?, "
            "'INTELLECT', ?, ?, ?)",
            (amount, amount, cur.lastrowid, f"seed:{n}", day, now),
        )
    for h in range(5):
        hid = conn.execute(
            "INSERT INTO habits (user_id, name, schedule_kind, measure, start_date, created_at, updated_at) "
            "VALUES (1, ?, 'DAILY', 'BOOLEAN', ?, ?, ?)",
            (f"Habit {h}", (today - timedelta(days=364)).isoformat(), now, now),
        ).lastrowid
        conn.executemany(
            "INSERT INTO habit_logs (user_id, habit_id, local_date, entry_type, value, created_at, updated_at) "
            "VALUES (1, ?, ?, 'ENTRY', 1, ?, ?)",
            [(hid, (today - timedelta(days=d)).isoformat(), now, now) for d in range(365) if (d * (h + 3)) % 7],
        )
    conn.execute("COMMIT")
    conn.close()


def _measure(fn, n: int = 30) -> dict[str, float]:  # type: ignore[no-untyped-def]
    fn()  # warm-up
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[int(0.95 * (n - 1))], 2),
        "max_ms": round(samples[-1], 2),
        "n": n,
    }


def test_latency_budgets(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    today = date(2026, 11, 22)
    _seed(app.state.services.db.path, today)

    def ok(r):  # type: ignore[no-untyped-def]
        assert r.status_code == 200, r.text
        return r

    results = {
        "dashboard": _measure(lambda: ok(client.get("/api/v1/dashboard"))),
        "quest_list": _measure(lambda: ok(client.get("/api/v1/quests?limit=50&status=AVAILABLE,ACTIVE"))),
        "analytics_90d": _measure(lambda: ok(client.get("/api/v1/analytics/summary?from=2026-08-25&to=2026-11-22"))),
    }
    ids = []
    for _ in range(31):
        q = create_quest(client, difficulty="EASY")
        start(client, q["id"])
        ids.append(q["id"])
    it = iter(ids)
    results["complete_quest"] = _measure(lambda: ok(client.post(f"/api/v1/quests/{next(it)}/complete")))

    RESULTS.write_text(
        json.dumps(
            {
                "environment": {
                    "python": platform.python_version(),
                    "sqlite": sqlite3.sqlite_version,
                    "platform": platform.platform(),
                    "processor": platform.machine(),
                    "mode": "in-process TestClient, single user, file-backed SQLite (WAL)",
                },
                "dataset": {"quests": 2031, "completions": 6000, "xp_events": 6000, "habit_logs": "~1,300"},
                "targets_p95_ms": TARGETS_MS,
                "results": results,
            },
            indent=2,
        )
    )
    for name, target in TARGETS_MS.items():
        assert results[name]["p95_ms"] < target, (name, results[name])
