from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from lifeexe.core.timeutil import FixedClock
from tests.helpers import PASSWORD, total_xp
from tests.integration.test_habits_skills_api import habit


@pytest.mark.parametrize("days_elapsed", [0, 30])
def test_habit_log_deletion_allows_correction_window(client: TestClient, clock: FixedClock, days_elapsed: int) -> None:
    original = habit(client)
    url = f"/api/v1/habits/{original['id']}/logs/{original['start_date']}"
    assert client.post(f"/api/v1/habits/{original['id']}/logs", json={}).status_code == 200
    clock.advance(days=days_elapsed)
    # Renew the 14-day session so the test reaches the habit correction rule.
    assert (
        client.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": PASSWORD}).status_code == 200
    )

    response = client.delete(url)

    assert response.status_code == 200, response.text
    assert response.json()["xp_delta"] == -5
    assert response.json()["habit"]["stats"]["total_done"] == 0
    assert total_xp(client) == 0
    assert client.delete(url).status_code == 404
    assert total_xp(client) == 0


def test_habit_log_deletion_rejects_old_entry_without_reversing_xp(client: TestClient, clock: FixedClock) -> None:
    original = habit(client)
    hid = original["id"]
    assert client.post(f"/api/v1/habits/{hid}/logs", json={}).status_code == 200
    clock.advance(days=31)
    assert (
        client.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": PASSWORD}).status_code == 200
    )

    response = client.delete(f"/api/v1/habits/{hid}/logs/{original['start_date']}")

    assert response.status_code == 400, response.text
    assert "last 30 days" in response.json()["error"]["message"]
    assert client.get(f"/api/v1/habits/{hid}").json()["stats"]["total_done"] == 1
    assert total_xp(client) == 5


def test_habit_log_deletion_requires_unarchiving(client: TestClient) -> None:
    original = habit(client)
    hid = original["id"]
    url = f"/api/v1/habits/{hid}/logs/{original['start_date']}"
    assert client.post(f"/api/v1/habits/{hid}/logs", json={}).status_code == 200
    assert client.post(f"/api/v1/habits/{hid}/archive").status_code == 200

    response = client.delete(url)

    assert response.status_code == 409, response.text
    assert total_xp(client) == 5
    assert client.get(f"/api/v1/habits/{hid}").json()["stats"]["total_done"] == 1
    assert client.post(f"/api/v1/habits/{hid}/unarchive").status_code == 200
    assert client.delete(url).json()["xp_delta"] == -5
    assert total_xp(client) == 0


@pytest.mark.parametrize("day", ["2026-11-21", "2026-11-23"])
def test_habit_log_deletion_rejects_days_outside_habit_lifetime(client: TestClient, day: str) -> None:
    hid = habit(client)["id"]

    response = client.delete(f"/api/v1/habits/{hid}/logs/{day}")

    assert response.status_code == 400, response.text
    assert total_xp(client) == 0
