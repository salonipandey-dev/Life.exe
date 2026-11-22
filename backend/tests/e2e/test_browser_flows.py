"""End-to-end tests: real Chromium driving the real server and built frontend.

Requires `frontend/dist` (run `node frontend/scripts/build.mjs`) and Playwright's
Chromium. Skipped automatically when either is missing.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Iterator

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "frontend" / "dist"
ARTIFACTS = Path(__file__).parent / "artifacts"

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    if not (DIST / "index.html").exists():
        pytest.skip("frontend not built (node frontend/scripts/build.mjs)")
    port = _free_port()
    env = {
        **os.environ,
        "LIFEEXE_DB_PATH": str(tmp_path_factory.mktemp("e2e") / "e2e.db"),
        "LIFEEXE_PORT": str(port),
        "LIFEEXE_FRONTEND_DIST": str(DIST),
        "LIFEEXE_LOG_LEVEL": "WARNING",
        "LIFEEXE_AUTH_RATE_LIMIT": "100",
    }
    proc = subprocess.Popen([sys.executable, "-m", "lifeexe"], cwd=ROOT / "backend", env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/v1/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def page(server: str) -> Iterator["sync_api.Page"]:
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"Chromium unavailable: {exc}")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, base_url=server)
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        # HTTP error statuses are asserted explicitly in the tests; anything else
        # logged as a console error (or any uncaught exception) fails the test.
        pg.on("console", lambda m: errors.append(m.text)
              if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
        yield pg
        ARTIFACTS.mkdir(exist_ok=True)
        assert errors == [], f"browser errors: {errors}"
        ctx.close()
        browser.close()


def sign_up(page: "sync_api.Page", email: str, name: str = "Saloni") -> None:
    page.goto("/")
    page.get_by_role("tab", name="Create account").click()
    page.get_by_label("Display name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill("correct horse battery")
    page.get_by_role("button", name="Create account").last.click()
    page.get_by_role("heading", name="Today's top three").wait_for()


def test_quest_slice_create_start_complete_level_up(page: "sync_api.Page") -> None:
    expect = sync_api.expect
    sign_up(page, "e2e-quest@example.com")
    expect(page.get_by_role("img", name="Level 1. 0 of 100 XP into this level.")).to_be_visible()

    page.get_by_role("button", name="New quest").first.click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Title").fill("Solve two SQL join problems")
    dialog.get_by_label("Difficulty").select_option("EPIC")
    expect(dialog.get_by_text("150 XP")).to_be_visible()  # reward preview is server config, read-only
    dialog.get_by_role("button", name="Create quest").click()
    expect(page.get_by_text("Quest created")).to_be_visible()

    row = page.locator("li", has_text="Solve two SQL join problems").first
    row.get_by_role("button", name="Start: Solve two SQL join problems").click()
    row.get_by_role("button", name="Complete: Solve two SQL join problems").click()
    expect(page.get_by_text("Level 2 reached")).to_be_visible()
    expect(page.get_by_text("Achievement: First Quest Completed")).to_be_visible()
    expect(page.get_by_role("img", name="Level 2. 50 of 183 XP into this level.")).to_be_visible()
    expect(page.get_by_text("150 XP", exact=True).first).to_be_visible()

    # A duplicate completion from the client is refused and changes nothing.
    status = page.evaluate("""async () => {
        const list = await (await fetch('/api/v1/quests?status=COMPLETED')).json();
        const r = await fetch(`/api/v1/quests/${list.items[0].id}/complete`, {method: 'POST', headers: {'X-LifeExe-CSRF': '1'}});
        const p = await (await fetch('/api/v1/profile')).json();
        return [r.status, p.progress.total_xp];
    }""")
    assert status == [409, 150]
    page.screenshot(path=str(ARTIFACTS / "e2e-command-center.png"), full_page=True)


def test_habit_analytics_settings_and_session(page: "sync_api.Page") -> None:
    expect = sync_api.expect
    sign_up(page, "e2e-habit@example.com", name="Tester")

    page.goto("/#/habits")
    page.get_by_role("button", name="New habit").click()
    page.get_by_role("dialog").get_by_label("Name").fill("Walk 20 minutes")
    page.get_by_role("dialog").get_by_role("button", name="Create habit").click()
    page.get_by_role("checkbox", name="Walk 20 minutes: mark done today").click()
    expect(page.get_by_text("Walk 20 minutes: done")).to_be_visible()
    expect(page.get_by_text("1-day streak").first).to_be_visible()

    page.goto("/#/analytics")
    expect(page.get_by_role("heading", name="Net XP per day")).to_be_visible()
    expect(page.get_by_text("Most of your XP in this range went to Discipline")).to_be_visible()
    page.get_by_role("button", name="Show table").click()
    expect(page.get_by_role("table")).to_be_visible()

    page.goto("/#/settings")
    page.get_by_label("Display name").fill("Saloni P")
    page.get_by_label("Time zone").select_option("Asia/Kolkata")
    page.get_by_role("button", name="Save settings").click()
    expect(page.get_by_text("Settings saved")).to_be_visible()
    expect(page.locator("aside").get_by_text("Saloni P")).to_be_visible()

    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_role("tab", name="Sign in")).to_be_visible()
    page.get_by_label("Email").fill("e2e-habit@example.com")
    page.get_by_label("Password").fill("correct horse battery")
    page.get_by_role("button", name="Sign in", exact=True).last.click()
    expect(page.get_by_role("heading", name="Saloni P")).to_be_visible()


def test_mobile_navigation_and_login_errors(server: str) -> None:
    expect = sync_api.expect
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, base_url=server, is_mobile=True)
        page = ctx.new_page()
        page.goto("/")
        page.get_by_label("Email").fill("nobody@example.com")
        page.get_by_label("Password").fill("wrong password")
        page.get_by_role("button", name="Sign in", exact=True).last.click()
        expect(page.get_by_role("alert")).to_have_text("Email or password is incorrect.")
        sign_up(page, "e2e-mobile@example.com")
        nav = page.get_by_role("navigation", name="Main").last
        nav.get_by_role("link", name="Quests").click()
        expect(page.get_by_role("heading", name="Quest board")).to_be_visible()
        nav.get_by_role("link", name="Skills").click()
        expect(page.get_by_role("heading", name="Skill tree")).to_be_visible()
        ctx.close()
        browser.close()
