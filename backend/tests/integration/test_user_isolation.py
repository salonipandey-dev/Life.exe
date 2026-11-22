"""Broken-access-control tests: user B must never read or change user A's data.

Other users' resources return 404 (not 403) so their existence is not revealed.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from tests.helpers import complete, create_quest, new_client, register, start, total_xp


def two_users(app) -> tuple[TestClient, TestClient]:  # type: ignore[no-untyped-def]
    a, b = new_client(app), new_client(app)
    register(a, "alice@example.com")
    register(b, "bob@example.com")
    return a, b


def test_quests_are_isolated(app) -> None:  # type: ignore[no-untyped-def]
    a, b = two_users(app)
    q = create_quest(a, difficulty="EPIC")
    start(a, q["id"])
    qid = q["id"]
    assert b.get(f"/api/v1/quests/{qid}").status_code == 404
    assert b.patch(f"/api/v1/quests/{qid}", json={"title": "pwned"}).status_code == 404
    assert b.post(f"/api/v1/quests/{qid}/complete").status_code == 404
    assert b.post(f"/api/v1/quests/{qid}/actions/cancel").status_code == 404
    assert b.post(f"/api/v1/quests/{qid}/archive").status_code == 404
    assert b.delete(f"/api/v1/quests/{qid}").status_code == 404
    assert b.get("/api/v1/quests").json()["total"] == 0
    assert total_xp(b) == 0
    complete(a, qid)
    assert b.post(f"/api/v1/quests/{qid}/reopen").status_code == 404
    assert total_xp(a) == 150 and a.get(f"/api/v1/quests/{qid}").json()["title"] != "pwned"


def test_cannot_link_another_users_skill(app) -> None:  # type: ignore[no-untyped-def]
    a, b = two_users(app)
    a_skill = a.get("/api/v1/skills").json()["skills"][0]["id"]
    assert b.post("/api/v1/quests", json={"title": "x", "skill_id": a_skill}).status_code == 404
    assert b.get(f"/api/v1/skills/{a_skill}").status_code == 404
    assert b.post(f"/api/v1/skills/{a_skill}/evidence", json={"title": "fake"}).status_code == 404
    b_skill = b.get("/api/v1/skills").json()["skills"][0]["id"]
    assert b.post(f"/api/v1/skills/{b_skill}/prerequisites", json={"prerequisite_id": a_skill}).status_code == 404


def test_habits_are_isolated(app) -> None:  # type: ignore[no-untyped-def]
    a, b = two_users(app)
    hid = a.post("/api/v1/habits", json={"name": "Read"}).json()["id"]
    assert b.get(f"/api/v1/habits/{hid}").status_code == 404
    assert b.post(f"/api/v1/habits/{hid}/logs", json={}).status_code == 404
    assert b.post(f"/api/v1/habits/{hid}/pause").status_code == 404
    assert b.get("/api/v1/habits").json()["items"] == []


def test_analytics_and_export_only_contain_own_data(app) -> None:  # type: ignore[no-untyped-def]
    a, b = two_users(app)
    q = create_quest(a, title="Alice secret quest")
    start(a, q["id"])
    complete(a, q["id"])
    assert b.get("/api/v1/analytics/summary").json()["totals"]["net_xp"] == 0
    export = b.get("/api/v1/account/export").text
    assert "Alice secret quest" not in export and "alice@example.com" not in export
