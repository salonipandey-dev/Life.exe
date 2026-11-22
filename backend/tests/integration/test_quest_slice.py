"""The first vertical slice: Create -> Start -> Complete -> Persist -> Award XP -> Level -> Display."""

from __future__ import annotations

import sqlite3

from starlette.testclient import TestClient

from lifeexe.core.timeutil import FixedClock
from lifeexe.domain.rewards import GameConfig
from tests.helpers import complete, create_quest, new_client, register, start, total_xp


def ledger(app, sql: str, *params):  # type: ignore[no-untyped-def]
    conn = sqlite3.connect(app.state.services.db.path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_full_vertical_slice(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, title="Build a SQL query using joins", difficulty="EASY", category="SIDE")
    assert q["status"] == "AVAILABLE" and q["xp_reward"] == 15 and q["coin_reward"] == 3
    assert q["allowed_actions"] == ["start", "cancel", "expire"]

    q = start(client, q["id"])
    assert q["status"] == "ACTIVE" and q["started_at"]

    result = complete(client, q["id"])
    assert result["quest"]["status"] == "COMPLETED"
    assert result["reward"] == {
        "xp_awarded": 15,
        "base_xp": 15,
        "coins_awarded": 3,
        "capped": False,
        "daily_cap": 1500,
        "occurrence_key": "once",
    }
    assert result["progress"]["total_xp"] == 15 and result["progress"]["level"] == 1
    assert result["leveled_up"] is False
    assert [a["key"] for a in result["achievements_unlocked"]] == ["first_quest"]

    # persisted: one completion row, one ledger row with an idempotency key
    rows = ledger(app, "SELECT amount, reason, idempotency_key, local_date FROM xp_events")
    assert rows == [(15, "QUEST_COMPLETED", "quest_completion:1", "2026-11-22")]
    assert ledger(app, "SELECT occurrence_key, reversed_at FROM quest_completions") == [("once", None)]

    # displayed: dashboard and profile read the same ledger
    dash = client.get("/api/v1/dashboard").json()
    assert dash["character"]["progress"]["total_xp"] == 15
    assert dash["character"]["coins"] == 3
    assert dash["recent_xp"][0]["label"] == "Build a SQL query using joins"
    assert total_xp(client) == 15


def test_level_up_crossing_threshold(client: TestClient) -> None:
    first = create_quest(client, difficulty="HARD")
    start(client, first["id"])
    r1 = complete(client, first["id"])
    assert (r1["progress"]["level"], r1["leveled_up"]) == (1, False)  # 70 < 100
    second = create_quest(client, difficulty="MEDIUM")
    start(client, second["id"])
    r2 = complete(client, second["id"])  # 105 >= 100
    assert r2["level_before"] == 1 and r2["progress"]["level"] == 2 and r2["leveled_up"] is True
    assert r2["progress"]["xp_into_level"] == 5 and r2["progress"]["next_level_xp"] == 283


def test_duplicate_completion_rejected_without_extra_xp(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, difficulty="EPIC")
    start(client, q["id"])
    complete(client, q["id"])
    for _ in range(3):
        r = client.post(f"/api/v1/quests/{q['id']}/complete")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "already_completed"
    assert total_xp(client) == 150
    assert ledger(app, "SELECT COUNT(*) FROM xp_events")[0][0] == 1
    assert ledger(app, "SELECT COUNT(*) FROM coin_transactions")[0][0] == 1


def test_cannot_complete_without_starting(client: TestClient) -> None:
    q = create_quest(client)
    r = client.post(f"/api/v1/quests/{q['id']}/complete")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    assert total_xp(client) == 0


def test_client_cannot_supply_xp_or_coins(client: TestClient) -> None:
    for field, value in [("xp_reward", 9999), ("xp", 500), ("coins", 50), ("total_xp", 10**6), ("status", "COMPLETED")]:
        r = client.post("/api/v1/quests", json={"title": "cheat", field: value})
        assert r.status_code == 422, field
        assert r.json()["error"]["code"] == "validation_error"
    q = create_quest(client)
    r = client.patch(f"/api/v1/quests/{q['id']}", json={"xp_reward": 1000})
    assert r.status_code == 422


def test_reopen_reverses_with_ledger_entry_and_recomplete_nets_one_award(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    q = create_quest(client, difficulty="EPIC")
    start(client, q["id"])
    complete(client, q["id"])
    r = client.post(f"/api/v1/quests/{q['id']}/reopen")
    assert r.status_code == 200
    body = r.json()
    assert body["xp_reversed"] == 150 and body["progress"]["total_xp"] == 0 and body["quest"]["status"] == "ACTIVE"
    assert client.post(f"/api/v1/quests/{q['id']}/reopen").status_code == 409  # nothing left to reopen

    again = complete(client, q["id"])
    assert again["reward"]["xp_awarded"] == 150
    rows = ledger(app, "SELECT amount, reason, reverses_event_id FROM xp_events ORDER BY id")
    assert rows == [(150, "QUEST_COMPLETED", None), (-150, "QUEST_REOPENED", 1), (150, "QUEST_COMPLETED", None)]
    assert total_xp(client) == 150
    coins = ledger(app, "SELECT SUM(amount) FROM coin_transactions")[0][0]
    assert coins == 30
    history = client.get(f"/api/v1/quests/{q['id']}").json()["history"]
    assert len(history) == 2 and history[1]["reversed_at"] is not None


def test_daily_recurring_quest_once_per_local_day(client: TestClient, clock: FixedClock) -> None:
    q = create_quest(client, title="45 minutes of Python", recurrence="DAILY", difficulty="MEDIUM")
    start(client, q["id"])
    r = complete(client, q["id"])
    assert r["quest"]["status"] == "ACTIVE" and r["quest"]["occurrence_completed"] is True
    assert r["reward"]["occurrence_key"] == "2026-11-22"
    assert "reopen" in r["quest"]["allowed_actions"] and "complete" not in r["quest"]["allowed_actions"]
    assert client.post(f"/api/v1/quests/{q['id']}/complete").status_code == 409

    # 22:00 UTC is 03:30 next day in Kolkata, still before the 04:00 day start: same day
    clock.advance(hours=12)
    assert client.post(f"/api/v1/quests/{q['id']}/complete").status_code == 409
    clock.advance(hours=1)  # 04:30 local -> a new day
    r2 = complete(client, q["id"])
    assert r2["reward"]["occurrence_key"] == "2026-11-23"
    assert total_xp(client) == 70


def test_weekly_recurring_quest_once_per_iso_week(client: TestClient, clock: FixedClock) -> None:
    q = create_quest(client, recurrence="WEEKLY", difficulty="HARD")
    start(client, q["id"])
    assert complete(client, q["id"])["reward"]["occurrence_key"] == "2026-W47"
    clock.advance(hours=13)  # 04:30 Mon 23 Nov local (after the 04:00 day start) -> new ISO week
    assert complete(client, q["id"])["reward"]["occurrence_key"] == "2026-W48"
    clock.advance(days=2)
    assert client.post(f"/api/v1/quests/{q['id']}/complete").status_code == 409


def test_daily_cap_limits_xp_but_keeps_completion(make_app) -> None:  # type: ignore[no-untyped-def]
    app = make_app(game=GameConfig(daily_xp_cap=200))
    c = new_client(app)
    register(c)
    awarded = []
    for _ in range(3):
        q = create_quest(c, difficulty="EPIC")
        start(c, q["id"])
        r = complete(c, q["id"])
        awarded.append((r["reward"]["xp_awarded"], r["reward"]["capped"]))
        assert r["quest"]["status"] == "COMPLETED"  # the accomplishment is always recorded
    assert awarded == [(150, False), (50, True), (0, True)]
    assert total_xp(c) == 200


def test_edit_rules(client: TestClient) -> None:
    q = create_quest(client, difficulty="EASY")
    r = client.patch(
        f"/api/v1/quests/{q['id']}", json={"title": "Renamed", "due_date": "2026-11-30", "difficulty": "HARD"}
    )
    assert r.status_code == 200 and r.json()["xp_reward"] == 70 and r.json()["due_date"] == "2026-11-30"
    r = client.patch(f"/api/v1/quests/{q['id']}", json={"due_date": None})
    assert r.json()["due_date"] is None
    assert client.patch(f"/api/v1/quests/{q['id']}", json={"title": None}).status_code == 422
    start(client, q["id"])
    assert client.patch(f"/api/v1/quests/{q['id']}", json={"recurrence": "DAILY"}).status_code == 409
    complete(client, q["id"])
    assert client.patch(f"/api/v1/quests/{q['id']}", json={"title": "x"}).status_code == 409


def test_delete_and_archive_rules(client: TestClient) -> None:
    fresh = create_quest(client)
    assert client.delete(f"/api/v1/quests/{fresh['id']}").status_code == 204
    assert client.get(f"/api/v1/quests/{fresh['id']}").status_code == 404

    done = create_quest(client)
    start(client, done["id"])
    complete(client, done["id"])
    r = client.delete(f"/api/v1/quests/{done['id']}")
    assert r.status_code == 409 and "Archive" in r.json()["error"]["message"]

    active = create_quest(client)
    start(client, active["id"])
    assert client.post(f"/api/v1/quests/{active['id']}/archive").status_code == 409

    archived = client.post(f"/api/v1/quests/{done['id']}/archive").json()
    assert archived["archived"] is True and archived["allowed_actions"] == []
    ids = [q["id"] for q in client.get("/api/v1/quests").json()["items"]]
    assert done["id"] not in ids
    ids = [q["id"] for q in client.get("/api/v1/quests?include_archived=true").json()["items"]]
    assert done["id"] in ids
    assert client.post(f"/api/v1/quests/{done['id']}/reopen").status_code == 409
    assert client.post(f"/api/v1/quests/{done['id']}/unarchive").json()["archived"] is False
    assert total_xp(client) == 35  # archiving never touches XP


def test_lifecycle_pause_cancel_restore_expire(client: TestClient) -> None:
    q = create_quest(client, as_draft=True)
    assert q["status"] == "DRAFT"
    seq = [
        ("publish", "AVAILABLE"),
        ("start", "ACTIVE"),
        ("pause", "PAUSED"),
        ("resume", "ACTIVE"),
        ("cancel", "CANCELLED"),
        ("restore", "AVAILABLE"),
        ("expire", "EXPIRED"),
        ("restore", "AVAILABLE"),
    ]
    for action, expected in seq:
        r = client.post(f"/api/v1/quests/{q['id']}/actions/{action}")
        assert r.status_code == 200, (action, r.text)
        assert r.json()["status"] == expected
    assert client.post(f"/api/v1/quests/{q['id']}/actions/complete").status_code == 409
    assert client.post(f"/api/v1/quests/{q['id']}/actions/teleport").status_code == 404
    assert client.post(f"/api/v1/quests/{q['id']}/actions/pause").status_code == 409


def test_overdue_is_flagged_not_punished(client: TestClient, clock: FixedClock) -> None:
    q = create_quest(client, due_date="2026-11-21")
    assert q["overdue"] is True and q["status"] == "AVAILABLE"
    start(client, q["id"])
    assert complete(client, q["id"])["reward"]["xp_awarded"] == 35  # late completion still counts


def test_list_filter_search_sort_paginate(client: TestClient) -> None:
    create_quest(client, title="Alpha SQL", priority="LOW", category="SIDE")
    create_quest(client, title="Beta Python", priority="CRITICAL", category="MAIN", difficulty="HARD")
    create_quest(client, title="Gamma 100% done_", priority="HIGH", category="MAIN")
    r = client.get("/api/v1/quests").json()
    assert [q["title"] for q in r["items"]] == ["Beta Python", "Gamma 100% done_", "Alpha SQL"]
    assert r["total"] == 3
    assert client.get("/api/v1/quests?category=MAIN").json()["total"] == 2
    assert client.get("/api/v1/quests?difficulty=HARD").json()["total"] == 1
    assert client.get("/api/v1/quests?q=python").json()["items"][0]["title"] == "Beta Python"
    # LIKE wildcards in search are treated literally
    assert client.get("/api/v1/quests?q=100%25").json()["total"] == 1
    assert client.get("/api/v1/quests?q=_").json()["total"] == 1
    page = client.get("/api/v1/quests?sort=title&limit=2&offset=1").json()
    assert [q["title"] for q in page["items"]] == ["Beta Python", "Gamma 100% done_"]
    assert client.get("/api/v1/quests?status=ACTIVE").json()["total"] == 0
    assert client.get("/api/v1/quests?status=NOPE").status_code == 422
    assert client.get("/api/v1/quests?sort=id;DROP TABLE quests").status_code == 422
    assert client.get("/api/v1/quests?limit=1000").status_code == 422


def test_linking_skill_routes_xp_to_attribute(client: TestClient) -> None:
    skills = client.get("/api/v1/skills").json()["skills"]
    sql = next(s for s in skills if s["name"] == "SQL")
    q = create_quest(client, skill_id=sql["id"], difficulty="HARD")
    assert q["skill"] == {"id": sql["id"], "name": "SQL", "attribute": "INTELLECT"}
    start(client, q["id"])
    complete(client, q["id"])
    skill = client.get(f"/api/v1/skills/{sql['id']}").json()
    assert skill["xp"] == 70 and skill["status"] == "IN_PROGRESS"  # no evidence yet
    attrs = {a["attribute"]: a["xp"] for a in client.get("/api/v1/profile").json()["attributes"]}
    assert attrs["INTELLECT"] == 70 and attrs["STRENGTH"] == 0
    assert client.post("/api/v1/quests", json={"title": "x", "skill_id": 99999}).status_code == 404
