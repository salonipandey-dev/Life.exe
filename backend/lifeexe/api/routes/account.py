"""Profile, settings and data-ownership endpoints."""

from __future__ import annotations

import json
from typing import Any

from starlette.responses import Response

from lifeexe.api.registry import api
from lifeexe.api.routing import SESSION_COOKIE, Ctx
from lifeexe.api.schemas import DeleteAccountIn, PasswordChangeIn, ProfileOut, ProfileUpdateIn

TAGS = ("profile",)


@api.route("GET", "/profile", summary="Player profile, attributes and cosmetic options", tags=TAGS,
           response=ProfileOut)
def get_profile(ctx: Ctx) -> Any:
    return ctx.services.profile.get(ctx.uid)


@api.route("PATCH", "/profile", summary="Update profile and settings (time zone, day start, cosmetics)",
           tags=TAGS, body=ProfileUpdateIn, response=ProfileOut)
def update_profile(ctx: Ctx, body: ProfileUpdateIn) -> Any:
    changes = {k: v for k, v in body.model_dump(include=body.model_fields_set).items() if v is not None}
    return ctx.services.profile.update(ctx.uid, changes)


@api.route("POST", "/account/password", summary="Change password (signs out other sessions)", tags=TAGS,
           body=PasswordChangeIn, status_code=204, rate_limited=True)
def change_password(ctx: Ctx, body: PasswordChangeIn) -> None:
    ctx.services.profile.change_password(ctx.uid, body.current_password, body.new_password, ctx.session_token)


@api.route("GET", "/account/export", summary="Download all of your data as JSON", tags=TAGS)
def export_data(ctx: Ctx) -> Response:
    payload = ctx.services.profile.export(ctx.uid)
    return Response(
        json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="lifeexe-export.json"'},
    )


@api.route("POST", "/account/delete", summary="Permanently delete the account and all data", tags=TAGS,
           body=DeleteAccountIn, status_code=204, rate_limited=True)
def delete_account(ctx: Ctx, body: DeleteAccountIn) -> None:
    ctx.services.profile.delete_account(ctx.uid, body.password)
    ctx.cookies_to_delete.append(SESSION_COOKIE)
