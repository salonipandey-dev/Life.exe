from __future__ import annotations

from typing import Any

from lifeexe.api.registry import api
from lifeexe.api.routing import SESSION_COOKIE, Ctx
from lifeexe.api.schemas import LoginIn, ProfileOut, RegisterIn, SessionOut


def _start_session(ctx: Ctx, issued: Any) -> dict[str, Any]:
    max_age = ctx.services.settings.session_ttl_hours * 3600
    ctx.cookies_to_set.append((SESSION_COOKIE, issued.token, max_age))
    return {"user_id": issued.user_id, "expires_at": issued.expires_at}


@api.route(
    "POST",
    "/auth/register",
    summary="Create an account and sign in",
    tags=("auth",),
    body=RegisterIn,
    response=SessionOut,
    status_code=201,
    auth=False,
    rate_limited=True,
)
def register(ctx: Ctx, body: RegisterIn) -> dict[str, Any]:
    issued = ctx.services.auth.register(body.email, body.password, body.display_name, body.timezone)
    return _start_session(ctx, issued)


@api.route(
    "POST",
    "/auth/login",
    summary="Sign in",
    tags=("auth",),
    body=LoginIn,
    response=SessionOut,
    auth=False,
    rate_limited=True,
)
def login(ctx: Ctx, body: LoginIn) -> dict[str, Any]:
    return _start_session(ctx, ctx.services.auth.login(body.email, body.password))


@api.route(
    "POST", "/auth/logout", summary="Sign out (revokes the session)", tags=("auth",), status_code=204, auth=False
)
def logout(ctx: Ctx) -> None:
    if ctx.session_token:
        ctx.services.auth.logout(ctx.session_token)
    ctx.cookies_to_delete.append(SESSION_COOKIE)


@api.route("GET", "/auth/me", summary="Current player profile", tags=("auth",), response=ProfileOut)
def me(ctx: Ctx) -> dict[str, Any]:
    result: dict[str, Any] = ctx.services.profile.get(ctx.uid)
    return result
