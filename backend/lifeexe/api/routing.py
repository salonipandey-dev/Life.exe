"""A small typed routing layer on top of Starlette.

FastAPI is not available in this environment (see ADR-002), so this module
provides the subset we need, explicitly:

- Pydantic validation of JSON bodies and query strings (422 on failure)
- Pydantic validation of responses (a malformed response is a server bug)
- Authentication via opaque session cookie
- CSRF defence for state-changing requests
- Per-route rate limiting
- OpenAPI 3.1 document generation from the registered routes

Handlers are plain synchronous functions run in Starlette's threadpool, because
the database driver (sqlite3) is synchronous.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from lifeexe.core.errors import (
    BadRequest,
    Forbidden,
    PayloadTooLarge,
    RateLimited,
    Unauthorized,
    ValidationFailed,
)

SESSION_COOKIE = "lifeexe_session"
CSRF_HEADER = "x-lifeexe-csrf"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PATH_PARAM = re.compile(r"{(\w+)(?::(\w+))?}")


@dataclass
class Ctx:
    """Per-request context passed to every handler."""

    request: Request
    services: Any
    user_id: int | None = None
    session_token: str | None = None
    cookies_to_set: list[tuple[str, str, int]] = field(default_factory=list)
    cookies_to_delete: list[str] = field(default_factory=list)

    @property
    def uid(self) -> int:
        if self.user_id is None:  # pragma: no cover - guarded by auth=True
            raise Unauthorized("Sign in required.")
        return self.user_id


@dataclass(frozen=True)
class ApiRoute:
    method: str
    path: str
    handler: Callable[..., Any]
    summary: str
    tags: tuple[str, ...]
    body: type[BaseModel] | None
    query: type[BaseModel] | None
    response: type[BaseModel] | None
    status_code: int
    auth: bool
    rate_limited: bool


def _validation_details(exc: ValidationError) -> list[dict[str, Any]]:
    # include_input=False: never echo submitted values (could be passwords)
    return [
        {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
        for e in exc.errors(include_url=False, include_input=False, include_context=False)
    ]


class Api:
    def __init__(self, prefix: str = "/api/v1") -> None:
        self.prefix = prefix
        self.routes: list[ApiRoute] = []

    def route(
        self,
        method: str,
        path: str,
        *,
        summary: str,
        tags: tuple[str, ...] = (),
        body: type[BaseModel] | None = None,
        query: type[BaseModel] | None = None,
        response: type[BaseModel] | None = None,
        status_code: int = 200,
        auth: bool = True,
        rate_limited: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append(
                ApiRoute(method.upper(), self.prefix + path, fn, summary, tags, body, query, response,
                         status_code, auth, rate_limited)
            )
            return fn

        return register

    # --- request pipeline ---------------------------------------------------------

    def starlette_routes(self, services: Any) -> list[Route]:
        out = []
        for r in self.routes:
            out.append(Route(r.path, self._endpoint(r, services), methods=[r.method]))
        return out

    def _endpoint(self, r: ApiRoute, services: Any) -> Callable[[Request], Any]:
        settings = services.settings

        async def endpoint(request: Request) -> Response:
            if r.method in UNSAFE_METHODS:
                _check_csrf(request, settings.allowed_origins)
            if r.rate_limited:
                client = request.client.host if request.client else "unknown"
                allowed, retry = services.auth_limiter.check(f"{client}:{r.path}")
                if not allowed:
                    raise RateLimited("Too many attempts. Please wait and try again.", retry_after=retry)
            kwargs: dict[str, Any] = dict(request.path_params)
            if r.body is not None:
                raw = await request.body()
                if len(raw) > settings.max_body_bytes:
                    raise PayloadTooLarge("Request body is too large.")
                ctype = request.headers.get("content-type", "")
                if not ctype.startswith("application/json"):
                    raise BadRequest("Content-Type must be application/json.")
                try:
                    payload = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    raise BadRequest("Request body is not valid JSON.") from None
                try:
                    kwargs["body"] = r.body.model_validate(payload)
                except ValidationError as exc:
                    raise ValidationFailed("Some fields are invalid.", details=_validation_details(exc)) from None
            if r.query is not None:
                try:
                    kwargs["query"] = r.query.model_validate(dict(request.query_params))
                except ValidationError as exc:
                    raise ValidationFailed("Some query parameters are invalid.",
                                           details=_validation_details(exc)) from None
            ctx = Ctx(request=request, services=services)
            return await run_in_threadpool(self._invoke, r, ctx, kwargs)

        endpoint.__name__ = r.handler.__name__
        return endpoint

    def _invoke(self, r: ApiRoute, ctx: Ctx, kwargs: dict[str, Any]) -> Response:
        token = ctx.request.cookies.get(SESSION_COOKIE)
        ctx.session_token = token
        if r.auth:
            ctx.user_id = ctx.services.auth.authenticate(token)
            if ctx.user_id is None:
                raise Unauthorized("Sign in required.")
        result = r.handler(ctx, **kwargs)
        if isinstance(result, Response):
            response = result
        elif r.status_code == 204:
            response = Response(status_code=204)
        else:
            content = (
                r.response.model_validate(result).model_dump(mode="json", by_alias=True)
                if r.response is not None else result
            )
            response = JSONResponse(content, status_code=r.status_code)
        secure = ctx.services.settings.secure_cookies
        for name, value, max_age in ctx.cookies_to_set:
            response.set_cookie(name, value, max_age=max_age, httponly=True, secure=secure,
                                samesite="lax", path="/")
        for name in ctx.cookies_to_delete:
            response.delete_cookie(name, path="/", httponly=True, secure=secure, samesite="lax")
        return response

    # --- OpenAPI ------------------------------------------------------------------

    def openapi(self, title: str, version: str) -> dict[str, Any]:
        paths: dict[str, dict[str, Any]] = {}
        components: dict[str, Any] = {}

        def schema_ref(model: type[BaseModel]) -> dict[str, Any]:
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}", by_alias=True)
            for name, sub in schema.pop("$defs", {}).items():
                components[name] = sub
            components[model.__name__] = schema
            return {"$ref": f"#/components/schemas/{model.__name__}"}

        for r in self.routes:
            path = _PATH_PARAM.sub(lambda m: "{" + m.group(1) + "}", r.path)
            params = [
                {"name": m.group(1), "in": "path", "required": True,
                 "schema": {"type": "integer" if m.group(2) == "int" else "string"}}
                for m in _PATH_PARAM.finditer(r.path)
            ]
            if r.query is not None:
                qs = r.query.model_json_schema(by_alias=True)
                for name, prop in qs.get("properties", {}).items():
                    params.append({"name": name, "in": "query", "required": name in qs.get("required", []),
                                   "schema": prop})
            op: dict[str, Any] = {
                "summary": r.summary,
                "tags": list(r.tags),
                "operationId": r.handler.__name__,
                "parameters": params,
                "responses": {},
            }
            if r.body is not None:
                op["requestBody"] = {"required": True,
                                     "content": {"application/json": {"schema": schema_ref(r.body)}}}
            ok: dict[str, Any] = {"description": "Success"}
            if r.response is not None:
                ok["content"] = {"application/json": {"schema": schema_ref(r.response)}}
            op["responses"][str(r.status_code)] = ok
            op["responses"]["default"] = {"description": "Error",
                                          "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
            if r.auth:
                op["security"] = [{"sessionCookie": []}]
            paths.setdefault(path, {})[r.method.lower()] = op
        components["Error"] = {
            "type": "object",
            "properties": {"error": {"type": "object", "properties": {
                "code": {"type": "string"}, "message": {"type": "string"}, "details": {}}}},
        }
        return {
            "openapi": "3.1.0",
            "info": {"title": title, "version": version},
            "paths": paths,
            "components": {
                "schemas": components,
                "securitySchemes": {"sessionCookie": {"type": "apiKey", "in": "cookie", "name": SESSION_COOKIE}},
            },
        }


def _check_csrf(request: Request, allowed_origins: tuple[str, ...]) -> None:
    """Custom-header + Origin check (OWASP "custom request header" defence).

    Browsers cannot attach a custom header to a cross-site request without a
    CORS preflight, which this API never approves. Combined with SameSite=Lax
    cookies this blocks CSRF without a token store.
    """
    if request.headers.get(CSRF_HEADER) != "1":
        raise Forbidden("Missing CSRF header.")
    origin = request.headers.get("origin")
    if origin:
        own = f"{request.url.scheme}://{request.url.netloc}"
        if origin != own and origin not in allowed_origins:
            raise Forbidden("Cross-origin request rejected.")
