"""Plain helper functions shared by integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.testclient import TestClient

PASSWORD = "correct horse battery"
CSRF = {"X-LifeExe-CSRF": "1"}

# Sunday 22 Nov 2026, 10:00 UTC == 15:30 in Asia/Kolkata.
DEFAULT_NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)


def new_client(app: Starlette) -> TestClient:
    return TestClient(app, headers=CSRF)


def register(client: TestClient, email: str = "saloni@example.com", timezone: str = "Asia/Kolkata",
             name: str = "Saloni") -> dict[str, Any]:
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": PASSWORD, "display_name": name, "timezone": timezone})
    assert r.status_code == 201, r.text
    return dict(r.json())


def create_quest(client: TestClient, **fields: Any) -> dict[str, Any]:
    body = {"title": "Practice SQL joins", **fields}
    r = client.post("/api/v1/quests", json=body)
    assert r.status_code == 201, r.text
    return dict(r.json())


def start(client: TestClient, quest_id: int) -> dict[str, Any]:
    r = client.post(f"/api/v1/quests/{quest_id}/actions/start")
    assert r.status_code == 200, r.text
    return dict(r.json())


def complete(client: TestClient, quest_id: int) -> dict[str, Any]:
    r = client.post(f"/api/v1/quests/{quest_id}/complete")
    assert r.status_code == 200, r.text
    return dict(r.json())


def total_xp(client: TestClient) -> int:
    return int(client.get("/api/v1/profile").json()["progress"]["total_xp"])
