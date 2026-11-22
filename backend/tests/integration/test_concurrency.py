"""Concurrent duplicate completions must award XP exactly once.

Each thread uses its own HTTP client (and therefore its own DB connection) and
all threads are released at the same instant by a barrier.
"""

from __future__ import annotations

import sqlite3
import threading

from starlette.testclient import TestClient

from tests.helpers import CSRF, create_quest, start, total_xp


def _hammer(app, cookie: str, path: str, n: int) -> list[int]:  # type: ignore[no-untyped-def]
    barrier = threading.Barrier(n)
    statuses: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        c = TestClient(app, headers=CSRF, cookies={"lifeexe_session": cookie})
        barrier.wait()
        code = c.post(path).status_code
        with lock:
            statuses.append(code)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return statuses


def test_concurrent_completion_awards_once(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, difficulty="EPIC")
    start(client, q["id"])
    cookie = client.cookies.get("lifeexe_session")
    assert cookie
    statuses = _hammer(app, cookie, f"/api/v1/quests/{q['id']}/complete", n=12)
    assert sorted(statuses) == [200] + [409] * 11
    assert total_xp(client) == 150
    conn = sqlite3.connect(app.state.services.db.path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM quest_completions WHERE reversed_at IS NULL").fetchone()[0] == 1
        assert conn.execute("SELECT SUM(amount) FROM coin_transactions").fetchone()[0] == 30
    finally:
        conn.close()


def test_concurrent_recurring_completion_awards_once(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, recurrence="DAILY", difficulty="MEDIUM")
    start(client, q["id"])
    statuses = _hammer(app, client.cookies["lifeexe_session"], f"/api/v1/quests/{q['id']}/complete", n=8)
    assert statuses.count(200) == 1
    assert total_xp(client) == 35


def test_concurrent_reopen_reverses_once(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, difficulty="HARD")
    start(client, q["id"])
    client.post(f"/api/v1/quests/{q['id']}/complete")
    statuses = _hammer(app, client.cookies["lifeexe_session"], f"/api/v1/quests/{q['id']}/reopen", n=8)
    assert statuses.count(200) == 1
    assert total_xp(client) == 0


def test_database_unique_index_is_the_last_line_of_defence(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    """Even if application checks were bypassed, the schema rejects a second
    live completion for the same occurrence."""
    q = create_quest(client)
    start(client, q["id"])
    client.post(f"/api/v1/quests/{q['id']}/complete")
    conn = sqlite3.connect(app.state.services.db.path)
    try:
        try:
            conn.execute(
                "INSERT INTO quest_completions (user_id, quest_id, occurrence_key, local_date, completed_at) "
                "VALUES (1, ?, 'once', '2026-11-22', 'x')", (q["id"],))
            raise AssertionError("duplicate live completion was accepted")
        except sqlite3.IntegrityError as exc:
            assert "UNIQUE" in str(exc)
        try:
            conn.execute(
                "INSERT INTO xp_events (user_id, amount, base_amount, reason, source_type, idempotency_key, "
                "local_date, created_at) VALUES (1, 35, 35, 'QUEST_COMPLETED', 'QUEST_COMPLETION', "
                "'quest_completion:1', '2026-11-22', 'x')")
            raise AssertionError("duplicate idempotency key was accepted")
        except sqlite3.IntegrityError as exc:
            assert "UNIQUE" in str(exc)
    finally:
        conn.close()


def test_failed_transaction_leaves_no_partial_rows(client: TestClient, app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """If anything fails after the completion row is written (here: the
    achievement step), the whole unit rolls back — no orphan XP or completion."""
    import lifeexe.services.quests as quests_service

    q = create_quest(client, difficulty="EPIC")
    start(client, q["id"])

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(quests_service, "evaluate_achievements", boom)
    raw = TestClient(app, headers=CSRF, cookies={"lifeexe_session": client.cookies["lifeexe_session"]},
                     raise_server_exceptions=False)
    r = raw.post(f"/api/v1/quests/{q['id']}/complete")
    assert r.status_code == 500 and "simulated" not in r.text  # no internals leaked
    conn = sqlite3.connect(app.state.services.db.path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM quest_completions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM coin_transactions").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM quests").fetchone()[0] == "ACTIVE"
    finally:
        conn.close()
    monkeypatch.undo()
    assert client.post(f"/api/v1/quests/{q['id']}/complete").status_code == 200
