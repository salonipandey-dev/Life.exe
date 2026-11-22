from __future__ import annotations

import sqlite3

from starlette.testclient import TestClient

from lifeexe.core.timeutil import FixedClock
from tests.helpers import PASSWORD, complete, create_quest, new_client, register, start


def test_analytics_matches_recorded_events(client: TestClient, clock: FixedClock) -> None:
    # Day 1 (Sun 22 Nov local): Epic quest (150) + habit (5)
    q = create_quest(client, difficulty="EPIC", category="MAIN")
    start(client, q["id"])
    complete(client, q["id"])
    hid = client.post("/api/v1/habits", json={"name": "Read"}).json()["id"]
    client.post(f"/api/v1/habits/{hid}/logs", json={})
    # Day 2: Medium quest completed then reopened -> nets to zero
    clock.advance(days=1)
    q2 = create_quest(client, difficulty="MEDIUM", category="SIDE")
    start(client, q2["id"])
    complete(client, q2["id"])
    client.post(f"/api/v1/quests/{q2['id']}/reopen")
    # Day 3: Easy quest
    clock.advance(days=1)
    q3 = create_quest(client, difficulty="EASY", category="SIDE")
    start(client, q3["id"])
    complete(client, q3["id"])

    a = client.get("/api/v1/analytics/summary", params={"from": "2026-11-20", "to": "2026-11-24"}).json()
    assert a["range"] == {"from": "2026-11-20", "to": "2026-11-24", "days": 5, "timezone": "Asia/Kolkata",
                          "day_start_hour": 4}
    xp = {p["date"]: p["value"] for p in a["series"]["net_xp"]}
    assert xp == {"2026-11-20": 0, "2026-11-21": 0, "2026-11-22": 155, "2026-11-23": 0, "2026-11-24": 15}
    assert a["totals"] == {"net_xp": 170, "quest_completions": 2, "habit_days": 1, "active_days": 2}
    assert {c["category"]: c["count"] for c in a["completions_by_category"]} == {"MAIN": 1, "SIDE": 1}
    assert {r["attribute"]: r["xp"] for r in a["xp_by_attribute"]}["UNASSIGNED"] == 165
    assert a["definitions"]["net_xp"]
    # every insight is backed by numbers
    for insight in a["insights"]:
        assert insight["basis"]


def test_analytics_respects_user_timezone(client: TestClient, clock: FixedClock) -> None:
    # 23:00 UTC Sun == 04:30 Mon in Kolkata -> counted on Monday 23 Nov.
    clock.advance(hours=13)
    q = create_quest(client)
    start(client, q["id"])
    complete(client, q["id"])
    a = client.get("/api/v1/analytics/summary", params={"from": "2026-11-22", "to": "2026-11-23"}).json()
    assert [p["value"] for p in a["series"]["quest_completions"]] == [0, 1]


def test_analytics_range_validation(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/summary", params={"from": "2026-11-10", "to": "2026-11-01"}).status_code == 400
    assert client.get("/api/v1/analytics/summary", params={"from": "2024-01-01", "to": "2026-01-01"}).status_code == 400
    assert client.get("/api/v1/analytics/summary", params={"from": "garbage"}).status_code == 422
    empty = client.get("/api/v1/analytics/summary").json()
    assert empty["range"]["days"] == 28 and empty["insights"] == []


def test_profile_settings(client: TestClient) -> None:
    r = client.patch("/api/v1/profile", json={"display_name": "Saloni P", "timezone": "Europe/London",
                                              "day_start_hour": 0, "avatar": "orbit"})
    assert r.status_code == 200
    p = r.json()
    assert (p["display_name"], p["timezone"], p["day_start_hour"], p["avatar"]) == ("Saloni P", "Europe/London", 0, "orbit")
    assert client.patch("/api/v1/profile", json={"timezone": "Nowhere/City"}).status_code == 400
    assert client.patch("/api/v1/profile", json={"day_start_hour": 9}).status_code == 422
    locked = client.patch("/api/v1/profile", json={"title": "Legend"})
    assert locked.status_code == 400 and "level 50" in locked.json()["error"]["message"]
    assert client.patch("/api/v1/profile", json={"avatar": "<script>"}).status_code == 400


def test_title_unlocks_with_level(client: TestClient) -> None:
    for _ in range(2):
        q = create_quest(client, difficulty="EPIC")
        start(client, q["id"])
        complete(client, q["id"])  # 300 XP -> level 3
    assert client.patch("/api/v1/profile", json={"title": "Apprentice"}).status_code == 200


def test_export_contains_data_but_no_secrets(client: TestClient) -> None:
    q = create_quest(client, title="Exportable quest")
    start(client, q["id"])
    complete(client, q["id"])
    r = client.get("/api/v1/account/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["format"] == "lifeexe-export" and data["data"]["quests"][0]["title"] == "Exportable quest"
    assert len(data["data"]["xp_events"]) == 1
    assert "password_hash" not in r.text and "scrypt$" not in r.text and "token_hash" not in r.text


def test_change_password_revokes_other_sessions(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    other = new_client(app)
    assert other.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": PASSWORD}).status_code == 200
    bad = client.post("/api/v1/account/password", json={"current_password": "wrong-wrong", "new_password": "x" * 12})
    assert bad.status_code == 401
    ok = client.post("/api/v1/account/password", json={"current_password": PASSWORD, "new_password": "a brand new passphrase"})
    assert ok.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 200  # this device stays signed in
    assert other.get("/api/v1/auth/me").status_code == 401  # other devices are signed out
    fresh = new_client(app)
    assert fresh.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": "a brand new passphrase"}).status_code == 200


def test_delete_account_removes_every_row(app) -> None:  # type: ignore[no-untyped-def]
    keep, gone = new_client(app), new_client(app)
    register(keep, "keep@example.com")
    register(gone, "gone@example.com")
    for c in (keep, gone):
        q = create_quest(c)
        start(c, q["id"])
        complete(c, q["id"])
        hid = c.post("/api/v1/habits", json={"name": "h"}).json()["id"]
        c.post(f"/api/v1/habits/{hid}/logs", json={})
        sid = c.get("/api/v1/skills").json()["skills"][0]["id"]
        c.post(f"/api/v1/skills/{sid}/evidence", json={"title": "e"})
    assert gone.post("/api/v1/account/delete", json={"password": "wrong", "confirm": "DELETE"}).status_code == 401
    assert gone.post("/api/v1/account/delete", json={"password": PASSWORD, "confirm": "nope"}).status_code == 422
    assert gone.post("/api/v1/account/delete", json={"password": PASSWORD, "confirm": "DELETE"}).status_code == 204
    assert gone.get("/api/v1/auth/me").status_code == 401

    conn = sqlite3.connect(app.state.services.db.path)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('users','schema_migrations')")]
        for t in tables:
            assert conn.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id = 2").fetchone()[0] == 0, t
            # the other account is untouched
        assert conn.execute("SELECT COUNT(*) FROM xp_events WHERE user_id = 1").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    finally:
        conn.close()
    assert keep.get("/api/v1/dashboard").status_code == 200


def test_dashboard_priorities_and_today(client: TestClient) -> None:
    create_quest(client, title="Low later", priority="LOW", due_date="2026-12-10")
    create_quest(client, title="Overdue", priority="LOW", due_date="2026-11-20")
    create_quest(client, title="Critical", priority="CRITICAL")
    create_quest(client, title="Due today", priority="MEDIUM", due_date="2026-11-22")
    daily = create_quest(client, title="Daily Python", recurrence="DAILY")
    start(client, daily["id"])
    d = client.get("/api/v1/dashboard").json()
    assert [q["title"] for q in d["priorities"]] == ["Overdue", "Due today", "Critical"]
    today_titles = {q["title"] for q in d["today_quests"]}
    assert {"Overdue", "Due today", "Daily Python"} <= today_titles and "Low later" not in today_titles
    assert d["week"]["daily_xp_cap"] == 1500
