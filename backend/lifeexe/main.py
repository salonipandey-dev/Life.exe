"""Application factory (composition root).

All dependencies are wired here explicitly, which keeps the rest of the code
free of globals and lets tests inject a temporary database and a fixed clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import lifeexe.api.routes  # noqa: F401  (registers routes)
from lifeexe.api.middleware import SecurityAndLoggingMiddleware
from lifeexe.api.registry import api
from lifeexe.core.config import Settings
from lifeexe.core.db import Database
from lifeexe.core.errors import AppError, RateLimited
from lifeexe.core.logging import configure_logging, get_logger
from lifeexe.core.ratelimit import RateLimiter
from lifeexe.core.timeutil import Clock, SystemClock
from lifeexe.domain.rewards import GameConfig
from lifeexe.services.achievements import AchievementService
from lifeexe.services.analytics import AnalyticsService
from lifeexe.services.auth import AuthService
from lifeexe.services.habits import HabitService
from lifeexe.services.profile import ProfileService
from lifeexe.services.quests import QuestService
from lifeexe.services.skills import SkillService

log = get_logger("app")


@dataclass
class Services:
    settings: Settings
    db: Database
    clock: Clock
    game: GameConfig
    auth_limiter: RateLimiter
    auth: AuthService
    quests: QuestService
    habits: HabitService
    skills: SkillService
    analytics: AnalyticsService
    achievements: AchievementService
    profile: ProfileService


def build_services(settings: Settings, clock: Clock | None = None, game: GameConfig | None = None) -> Services:
    db = Database(settings.db_path)
    db.initialize()
    clock = clock or SystemClock()
    game = game or GameConfig()
    return Services(
        settings=settings,
        db=db,
        clock=clock,
        game=game,
        auth_limiter=RateLimiter(settings.auth_rate_limit_per_minute, 60.0),
        auth=AuthService(db, clock, settings.session_ttl_hours),
        quests=QuestService(db, clock, game),
        habits=HabitService(db, clock, game),
        skills=SkillService(db, clock),
        analytics=AnalyticsService(db, clock),
        achievements=AchievementService(db),
        profile=ProfileService(db, clock, game),
    )


def _error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


async def app_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)
    headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimited) else None
    return JSONResponse(_error_body(exc.code, exc.message, exc.details), status_code=exc.status_code,
                        headers=headers)


async def http_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    if request.url.path.startswith("/api/"):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(_error_body(code, str(exc.detail)), status_code=exc.status_code)
    return Response(str(exc.detail), status_code=exc.status_code)


async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
    log.error("unhandled error", exc_info=exc, extra={"fields": {"path": request.url.path}})
    return JSONResponse(_error_body("internal_error", "Something went wrong on our side."), status_code=500)


def _frontend_routes(dist: str | None) -> list[Route | Mount]:
    if not dist or not (Path(dist) / "index.html").exists():
        return []
    index = Path(dist) / "index.html"

    async def spa(request: Request) -> Response:
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    routes: list[Route | Mount] = [Route("/", spa)]
    if (Path(dist) / "assets").exists():
        routes.append(Mount("/assets", app=StaticFiles(directory=Path(dist) / "assets"), name="assets"))
    return routes


def create_app(settings: Settings | None = None, *, clock: Clock | None = None,
               game: GameConfig | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    services = build_services(settings, clock, game)

    async def api_not_found(request: Request) -> Response:
        return JSONResponse(_error_body("not_found", "Unknown API endpoint."), status_code=404)

    routes: list[Route | Mount] = [
        *api.starlette_routes(services),
        Route("/api/{rest:path}", api_not_found, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
        *_frontend_routes(settings.frontend_dist),
    ]
    app = Starlette(
        routes=routes,
        exception_handlers={
            AppError: app_error_handler,
            HTTPException: http_error_handler,
            Exception: unhandled_error_handler,
        },
    )
    app.state.services = services
    app.add_middleware(SecurityAndLoggingMiddleware, hsts=settings.secure_cookies)
    return app
