from __future__ import annotations

import sqlite3

from starlette.testclient import TestClient

from lifeexe.core.timeutil import FixedClock
from tests.helpers import complete, create_quest, start, total_xp


def habit(client: TestClient, **fields) -> dict:  # type: ignore[no-untyped-def,type-arg]
    r = client.post("/api/v1/habits", json={"name": "Walk 20 minutes", **fields})
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_habit_checkin_awards_once_and_undo_reverses(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    h = habit(client, attribute="STRENGTH")
    r = client.post(f"/api/v1/habits/{h['id']}/logs", json={}).json()
    assert r["xp_delta"] == 5 and r["habit"]["today"]["state"] == "DONE"
    assert r["habit"]["stats"]["current_streak"] == 1
    # logging the same day again updates the entry, it does not award twice
    again = client.post(f"/api/v1/habits/{h['id']}/logs", json={"note": "felt good"}).json()
    assert again["xp_delta"] == 0
    assert total_xp(client) == 5
    undo = client.delete(f"/api/v1/habits/{h['id']}/logs/2026-11-22").json()
    assert undo["xp_delta"] == -5 and undo["habit"]["today"]["state"] == "PENDING"
    redo = client.post(f"/api/v1/habits/{h['id']}/logs", json={}).json()
    assert redo["xp_delta"] == 5
    assert total_xp(client) == 5
    conn = sqlite3.connect(app.state.services.db.path)
    rows = conn.execute("SELECT amount, reason FROM xp_events ORDER BY id").fetchall()
    conn.close()
    assert rows == [(5, "HABIT_COMPLETED"), (-5, "HABIT_UNDONE"), (5, "HABIT_COMPLETED")]


def test_count_habit_partial_then_met(client: TestClient) -> None:
    h = habit(client, name="Solve DSA problems", measure="COUNT", target_value=2)
    r = client.post(f"/api/v1/habits/{h['id']}/logs", json={"value": 1}).json()
    assert r["xp_delta"] == 0 and r["habit"]["today"]["state"] == "PARTIAL"
    r = client.post(f"/api/v1/habits/{h['id']}/logs", json={"value": 2}).json()
    assert r["xp_delta"] == 5 and r["habit"]["today"]["state"] == "DONE"
    r = client.post(f"/api/v1/habits/{h['id']}/logs", json={"value": 1}).json()
    assert r["xp_delta"] == -5  # lowering below target removes the award


def test_streak_rest_day_and_missed_day_never_cost_xp(client: TestClient, clock: FixedClock) -> None:
    h = habit(client)
    hid = h["id"]
    client.post(f"/api/v1/habits/{hid}/logs", json={})
    clock.advance(days=1)
    client.post(f"/api/v1/habits/{hid}/logs", json={"entry_type": "REST"})
    clock.advance(days=1)
    r = client.post(f"/api/v1/habits/{hid}/logs", json={}).json()
    assert r["habit"]["stats"]["current_streak"] == 2
    xp_before = total_xp(client)
    clock.advance(days=3)  # two missed days
    h2 = client.get(f"/api/v1/habits/{hid}").json()
    assert h2["stats"]["current_streak"] == 0 and h2["stats"]["longest_streak"] == 2
    assert total_xp(client) == xp_before  # a missed day is never a penalty


def test_backfill_rules(client: TestClient, clock: FixedClock) -> None:
    h = habit(client)
    hid = h["id"]
    assert client.post(f"/api/v1/habits/{hid}/logs", json={"date": "2026-11-23"}).status_code == 400  # future
    assert client.post(f"/api/v1/habits/{hid}/logs", json={"date": "2026-11-21"}).status_code == 400  # before start
    clock.advance(days=2)
    r = client.post(f"/api/v1/habits/{hid}/logs", json={"date": "2026-11-23"})
    assert r.status_code == 200 and r.json()["xp_delta"] == 5
    assert client.post(f"/api/v1/habits/{hid}/logs", json={"value": 3}).status_code == 400  # boolean habit


def test_pause_resume(client: TestClient, clock: FixedClock) -> None:
    hid = habit(client)["id"]
    client.post(f"/api/v1/habits/{hid}/logs", json={})
    clock.advance(days=1)
    assert client.post(f"/api/v1/habits/{hid}/pause").json()["paused"] is True
    assert client.post(f"/api/v1/habits/{hid}/pause").status_code == 409
    clock.advance(days=3)
    resumed = client.post(f"/api/v1/habits/{hid}/resume").json()
    assert resumed["paused"] is False
    r = client.post(f"/api/v1/habits/{hid}/logs", json={}).json()
    assert r["habit"]["stats"]["current_streak"] == 2  # paused days were neutral


def test_weekly_count_habit(client: TestClient) -> None:
    h = habit(client, name="Gym", schedule_kind="WEEKLY_COUNT", target_per_week=3)
    assert h["stats"]["unit"] == "week" and h["stats"]["week_progress"] == [0, 3]
    bad = client.post("/api/v1/habits", json={"name": "x", "schedule_kind": "WEEKLY_COUNT"})
    assert bad.status_code == 422


def test_skill_graph_cycle_rejected_with_path(client: TestClient) -> None:
    skills = {s["name"]: s for s in client.get("/api/v1/skills").json()["skills"]}
    pandas, python = skills["Pandas"], skills["Python"]
    assert python["id"] in pandas["prerequisite_ids"]
    r = client.post(f"/api/v1/skills/{python['id']}/prerequisites", json={"prerequisite_id": pandas["id"]})
    assert r.status_code == 409
    assert "circular" in r.json()["error"]["message"] and "Pandas" in r.json()["error"]["message"]
    assert client.post(f"/api/v1/skills/{python['id']}/prerequisites",
                       json={"prerequisite_id": python["id"]}).status_code == 409
    # roadmap order: prerequisites always come first
    order = [s["name"] for s in client.get("/api/v1/skills").json()["skills"]]
    assert order.index("Python") < order.index("Pandas") < order.index("Data Cleaning")


def test_skill_needs_both_xp_and_evidence(client: TestClient) -> None:
    skills = {s["name"]: s for s in client.get("/api/v1/skills").json()["skills"]}
    sql, joins = skills["SQL"], skills["SQL Joins"]
    assert joins["status"] == "LOCKED"
    r = client.post(f"/api/v1/skills/{sql['id']}/evidence",
                    json={"title": "Wrote a GROUP BY report", "url": "https://github.com/example/sql"})
    assert r.status_code == 201 and r.json()["status"] == "IN_PROGRESS"  # evidence but no XP
    assert [a["key"] for a in r.json()["achievements_unlocked"]] == ["proof_of_work"]
    for _ in range(3):
        q = create_quest(client, skill_id=sql["id"], difficulty="EPIC")
        start(client, q["id"])
        complete(client, q["id"])
    after = {s["name"]: s for s in client.get("/api/v1/skills").json()["skills"]}
    assert after["SQL"]["status"] == "DEMONSTRATED"
    assert after["SQL Joins"]["status"] == "AVAILABLE"
    assert client.post(f"/api/v1/skills/{sql['id']}/evidence",
                       json={"title": "x", "url": "javascript:alert(1)"}).status_code == 422


def test_custom_skill_crud(client: TestClient) -> None:
    r = client.post("/api/v1/skills", json={"name": "Tableau", "tree": "Data Analytics", "xp_required": 100})
    assert r.status_code == 201 and r.json()["slug"] == "tableau"
    dup = client.post("/api/v1/skills", json={"name": "Tableau", "tree": "Data Analytics"}).json()
    assert dup["slug"] == "tableau-2"
    sid = r.json()["id"]
    assert client.patch(f"/api/v1/skills/{sid}", json={"evidence_required": 2}).json()["evidence_required"] == 2
    assert client.post(f"/api/v1/skills/{sid}/archive").status_code == 204
    assert all(s["id"] != sid for s in client.get("/api/v1/skills").json()["skills"])
