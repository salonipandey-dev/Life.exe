"""Create a demo account with three weeks of plausible history.

For local demos and screenshots only — it writes to the database given by
LIFEEXE_DB_PATH (default: data/demo.db) and refuses to run in production.
All activity goes through the public API, so the demo data obeys exactly the
same rules (idempotency, caps, streaks) as real use.

    python scripts/seed_demo.py            # demo@lifeexe.local / demo passphrase 123
"""

from __future__ import annotations

import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.testclient import TestClient  # noqa: E402

from lifeexe.core.config import REPO_DIR, Settings  # noqa: E402
from lifeexe.core.timeutil import FixedClock  # noqa: E402
from lifeexe.main import create_app  # noqa: E402

EMAIL, PASSWORD = "demo@lifeexe.local", "demo passphrase 123"
DAYS = 21


def main() -> None:
    if os.getenv("LIFEEXE_ENV") == "production":
        raise SystemExit("Refusing to seed demo data in production.")
    db_path = os.getenv("LIFEEXE_DB_PATH", str(REPO_DIR / "data" / "demo.db"))
    Path(db_path).unlink(missing_ok=True)
    rng = random.Random(7)  # noqa: S311 - deterministic demo data, not security
    now = datetime.now(UTC).replace(microsecond=0)
    clock = FixedClock(now - timedelta(days=DAYS) + timedelta(hours=1))
    app = create_app(
        Settings(env="demo", db_path=db_path, frontend_dist=None, log_level="WARNING", session_ttl_hours=24 * 60),
        clock=clock,
    )
    c = TestClient(app, headers={"X-LifeExe-CSRF": "1"})
    r = c.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Saloni", "timezone": "Asia/Kolkata"},
    )
    r.raise_for_status()
    skills = {s["name"]: s["id"] for s in c.get("/api/v1/skills").json()["skills"]}

    walk = c.post("/api/v1/habits", json={"name": "Walk 20 minutes", "attribute": "STRENGTH"}).json()["id"]
    dsa = c.post(
        "/api/v1/habits",
        json={"name": "Solve DSA problems", "measure": "COUNT", "target_value": 2, "attribute": "INTELLECT"},
    ).json()["id"]
    read = c.post(
        "/api/v1/habits", json={"name": "Read 10 pages", "schedule_kind": "WEEKDAYS", "weekdays": [0, 1, 2, 3, 4]}
    ).json()["id"]
    python_daily = c.post(
        "/api/v1/quests",
        json={
            "title": "45 minutes of Python practice",
            "recurrence": "DAILY",
            "difficulty": "MEDIUM",
            "category": "DAILY",
            "skill_id": skills["Python"],
        },
    ).json()["id"]
    c.post(f"/api/v1/quests/{python_daily}/actions/start")

    backlog = [
        ("Solve two SQL join problems", "MEDIUM", "SIDE", "SQL Joins", "HIGH"),
        ("Clean the sales CSV with pandas", "HARD", "MAIN", "Data Cleaning", "MEDIUM"),
        ("Write a GROUP BY report for monthly revenue", "MEDIUM", "SIDE", "SQL", "MEDIUM"),
        ("Review monthly expenses", "EASY", "SIDE", "Expense Tracking", "LOW"),
        ("Publish a project update on GitHub", "EASY", "SIDE", "GitHub", "MEDIUM"),
        ("Descriptive statistics notebook", "HARD", "MAIN", "Statistics", "MEDIUM"),
        ("Excel pivot table practice", "MEDIUM", "SIDE", "Excel", "LOW"),
        ("Mock interview: explain a project in 3 minutes", "MEDIUM", "CHALLENGE", "Interview Communication", "HIGH"),
    ]
    for _day in range(DAYS):
        if rng.random() < 0.8:
            c.post(f"/api/v1/habits/{walk}/logs", json={})
        elif rng.random() < 0.5:
            c.post(f"/api/v1/habits/{walk}/logs", json={"entry_type": "REST"})
        c.post(f"/api/v1/habits/{dsa}/logs", json={"value": rng.choice([0, 1, 2, 2, 3])})
        if rng.random() < 0.7:
            c.post(f"/api/v1/habits/{read}/logs", json={})
        if rng.random() < 0.75:
            c.post(f"/api/v1/quests/{python_daily}/complete")
        if backlog and rng.random() < 0.45:
            title, diff, cat, skill, prio = backlog.pop(0)
            q = c.post(
                "/api/v1/quests",
                json={"title": title, "difficulty": diff, "category": cat, "skill_id": skills[skill], "priority": prio},
            )
            assert q.status_code == 201, q.text
            q = q.json()
            c.post(f"/api/v1/quests/{q['id']}/actions/start")
            c.post(f"/api/v1/quests/{q['id']}/complete")
        clock.advance(days=1)
    clock.set(now)
    c.post(
        f"/api/v1/skills/{skills['SQL']}/evidence",
        json={"title": "Monthly revenue report with GROUP BY", "url": "https://github.com/salonipandey-dev"},
    )
    c.post(f"/api/v1/skills/{skills['Python']}/evidence", json={"title": "CSV cleaning script"})
    today = c.get("/api/v1/profile").json()["today"]
    open_quests = [
        {
            "title": "Build a Power BI sales dashboard",
            "difficulty": "EPIC",
            "category": "MAIN",
            "priority": "HIGH",
            "skill_id": skills["Power BI"],
            "due_date": today,
            "estimated_minutes": 180,
            "completion_criteria": "Dashboard published with three pages and a data model",
        },
        {
            "title": "Apply to two data analyst internships",
            "difficulty": "MEDIUM",
            "category": "MAIN",
            "priority": "CRITICAL",
            "skill_id": skills["Portfolio Projects"],
        },
        {
            "title": "Exploratory analysis of the Zomato dataset",
            "difficulty": "HARD",
            "category": "SIDE",
            "priority": "MEDIUM",
            "skill_id": skills["Exploratory Data Analysis"],
            "due_date": (datetime.fromisoformat(today) + timedelta(days=4)).date().isoformat(),
        },
        {
            "title": "Update resume with SQL project",
            "difficulty": "EASY",
            "category": "SIDE",
            "priority": "MEDIUM",
            "due_date": (datetime.fromisoformat(today) - timedelta(days=1)).date().isoformat(),
        },
        {
            "title": "Weekly boss: Portfolio Builder",
            "difficulty": "EPIC",
            "category": "BOSS",
            "priority": "HIGH",
            "completion_criteria": "Three dev sessions, one milestone, tests run, progress published",
        },
    ]
    for body in open_quests:
        c.post("/api/v1/quests", json=body)
    p = c.get("/api/v1/profile").json()["progress"]
    print(f"demo account ready: {EMAIL} / {PASSWORD} -> level {p['level']}, {p['total_xp']} XP ({db_path})")


if __name__ == "__main__":
    main()
