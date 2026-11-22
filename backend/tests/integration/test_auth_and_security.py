from __future__ import annotations

from starlette.testclient import TestClient

from lifeexe.core.timeutil import FixedClock
from tests.helpers import CSRF, PASSWORD, new_client, register


def test_register_sets_secure_session_cookie(app) -> None:  # type: ignore[no-untyped-def]
    c = new_client(app)
    r = c.post("/api/v1/auth/register", json={"email": "New@Example.com ", "password": PASSWORD,
                                              "display_name": "Saloni", "timezone": "Asia/Kolkata"})
    assert r.status_code == 201
    cookie = r.headers["set-cookie"].lower()
    assert "lifeexe_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    me = c.get("/api/v1/auth/me").json()
    assert me["email"] == "new@example.com"  # normalised
    assert me["progress"]["level"] == 1 and me["title"] == "Novice"


def test_duplicate_email_conflict(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    r = new_client(app).post("/api/v1/auth/register", json={"email": "SALONI@example.com", "password": PASSWORD,
                                                             "display_name": "x"})
    assert r.status_code == 409


def test_registration_validation(app) -> None:  # type: ignore[no-untyped-def]
    c = new_client(app)
    bad = [
        {"email": "not-an-email", "password": PASSWORD, "display_name": "x"},
        {"email": "a@b.co", "password": "short", "display_name": "x"},
        {"email": "a@b.co", "password": PASSWORD, "display_name": ""},
        {"email": "a@b.co", "password": PASSWORD, "display_name": "x", "timezone": "Mars/Base"},
        {"email": "a@b.co", "password": PASSWORD, "display_name": "x", "is_admin": True},
    ]
    for body in bad:
        r = c.post("/api/v1/auth/register", json=body)
        assert r.status_code == 422, body
        assert PASSWORD not in r.text  # submitted values are never echoed


def test_login_logout_and_generic_errors(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    c = new_client(app)
    wrong_pw = c.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": "nope-nope-nope"})
    unknown = c.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()  # no user enumeration
    ok = c.post("/api/v1/auth/login", json={"email": "saloni@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert c.get("/api/v1/auth/me").status_code == 200
    token = c.cookies["lifeexe_session"]
    assert c.post("/api/v1/auth/logout").status_code == 204
    # the old token is revoked server-side, not just deleted client-side
    replay = TestClient(app, headers=CSRF, cookies={"lifeexe_session": token})
    assert replay.get("/api/v1/auth/me").status_code == 401


def test_session_expiry(client: TestClient, clock: FixedClock) -> None:
    assert client.get("/api/v1/dashboard").status_code == 200
    clock.advance(days=15)  # TTL is 14 days
    assert client.get("/api/v1/dashboard").status_code == 401


def test_unauthenticated_access_denied(app) -> None:  # type: ignore[no-untyped-def]
    c = new_client(app)
    for path in ["/api/v1/quests", "/api/v1/dashboard", "/api/v1/profile", "/api/v1/habits",
                 "/api/v1/skills", "/api/v1/analytics/summary", "/api/v1/account/export"]:
        assert c.get(path).status_code == 401, path
    forged = TestClient(app, headers=CSRF, cookies={"lifeexe_session": "forged-token"})
    assert forged.get("/api/v1/quests").status_code == 401


def test_login_rate_limited(make_app) -> None:  # type: ignore[no-untyped-def]
    app = make_app(auth_rate_limit_per_minute=3)
    c = new_client(app)
    codes = [c.post("/api/v1/auth/login", json={"email": "x@y.co", "password": "whatever-123"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    r = c.post("/api/v1/auth/login", json={"email": "x@y.co", "password": "whatever-123"})
    assert int(r.headers["retry-after"]) > 0


def test_csrf_protections(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    cookie = {"lifeexe_session": client.cookies["lifeexe_session"]}
    no_header = TestClient(app, cookies=cookie)
    assert no_header.post("/api/v1/quests", json={"title": "x"}).status_code == 403
    evil = TestClient(app, headers={**CSRF, "Origin": "https://evil.example"}, cookies=cookie)
    assert evil.post("/api/v1/quests", json={"title": "x"}).status_code == 403
    same = TestClient(app, headers={**CSRF, "Origin": "http://testserver"}, cookies=cookie)
    assert same.post("/api/v1/quests", json={"title": "x"}).status_code == 201
    # GET requests stay usable without the header
    assert no_header.get("/api/v1/quests").status_code == 200


def test_content_type_size_and_json_validation(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/quests", content="title=x", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 400
    r = client.post("/api/v1/quests", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    r = client.post("/api/v1/quests", json={"title": "x", "description": "y" * 70_000})
    assert r.status_code == 413


def test_security_headers_and_error_shape(client: TestClient) -> None:
    r = client.get("/api/v1/quests")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "default-src 'self'" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"
    assert h["x-request-id"]
    err = client.get("/api/v1/quests/999").json()
    assert set(err) == {"error"} and err["error"]["code"] == "not_found"
    assert client.get("/api/v1/does-not-exist").json()["error"]["code"] == "not_found"


def test_sql_injection_payloads_are_inert(client: TestClient) -> None:
    payload = "'; DROP TABLE quests; --"
    r = client.post("/api/v1/quests", json={"title": payload, "description": "1' OR '1'='1"})
    assert r.status_code == 201 and r.json()["title"] == payload
    assert client.get("/api/v1/quests", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/v1/quests").json()["total"] == 1


def test_health_and_openapi_are_public(app) -> None:  # type: ignore[no-untyped-def]
    c = new_client(app)
    assert c.get("/api/v1/health").json()["status"] == "ok"
    spec = c.get("/api/v1/openapi.json").json()
    assert spec["openapi"] == "3.1.0"
    assert "/api/v1/quests/{quest_id}/complete" in spec["paths"]
    assert spec["paths"]["/api/v1/quests"]["post"]["security"] == [{"sessionCookie": []}]
