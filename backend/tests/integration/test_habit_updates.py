from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.integration.test_habits_skills_api import habit


@pytest.mark.parametrize(
    "field",
    ["name", "description", "schedule_kind", "weekdays", "measure", "target_value", "attribute"],
)
def test_habit_update_rejects_null_required_fields(client: TestClient, field: str) -> None:
    original = habit(client)
    response = client.patch(f"/api/v1/habits/{original['id']}", json={field: None})

    assert response.status_code == 422, response.text
    assert client.get(f"/api/v1/habits/{original['id']}").json() == original


@pytest.mark.parametrize("weekdays", [[], [-1], [7], [0, 0]])
def test_habit_update_rejects_invalid_weekdays(client: TestClient, weekdays: list[int]) -> None:
    original = habit(client, schedule_kind="WEEKDAYS", weekdays=[0, 2, 4])
    response = client.patch(f"/api/v1/habits/{original['id']}", json={"weekdays": weekdays})

    assert response.status_code == 422, response.text
    assert client.get(f"/api/v1/habits/{original['id']}").json() == original


def test_habit_partial_update_preserves_omitted_fields(client: TestClient) -> None:
    original = habit(client, measure="COUNT", target_value=3, attribute="INTELLECT")
    response = client.patch(f"/api/v1/habits/{original['id']}", json={"name": "Practice SQL"})

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["name"] == "Practice SQL"
    for field in ("measure", "target_value", "attribute", "schedule_kind", "weekdays"):
        assert updated[field] == original[field]


def test_habit_update_accepts_valid_weekdays_and_optional_null(client: TestClient) -> None:
    original = habit(client, schedule_kind="WEEKLY_COUNT", target_per_week=3)
    response = client.patch(
        f"/api/v1/habits/{original['id']}",
        json={"schedule_kind": "WEEKDAYS", "weekdays": [1, 3, 5], "target_per_week": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["weekdays"] == [1, 3, 5]
    assert response.json()["target_per_week"] is None


def test_habit_update_cannot_clear_required_weekly_target(client: TestClient) -> None:
    original = habit(client, schedule_kind="WEEKLY_COUNT", target_per_week=3)
    response = client.patch(f"/api/v1/habits/{original['id']}", json={"target_per_week": None})

    assert response.status_code == 400, response.text
    assert client.get(f"/api/v1/habits/{original['id']}").json() == original
