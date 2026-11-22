"""Read-mostly views: dashboard, analytics, achievements, health, OpenAPI."""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse

import lifeexe
from lifeexe.api.registry import api
from lifeexe.api.routing import Ctx
from lifeexe.api.schemas import AchievementGalleryOut, AnalyticsOut, AnalyticsQuery, DashboardOut, HealthOut


@api.route("GET", "/dashboard", summary="Command Center: character, priorities, today, habits, week",
           tags=("dashboard",), response=DashboardOut)
def dashboard(ctx: Ctx) -> Any:
    return ctx.services.profile.dashboard(ctx.uid)


@api.route("GET", "/analytics/summary", summary="Metrics, series and evidence-backed insights for a date range",
           tags=("analytics",), query=AnalyticsQuery, response=AnalyticsOut)
def analytics_summary(ctx: Ctx, query: AnalyticsQuery) -> Any:
    return ctx.services.analytics.summary(ctx.uid, query.from_, query.to)


@api.route("GET", "/achievements", summary="Achievement gallery", tags=("achievements",),
           response=AchievementGalleryOut)
def achievements(ctx: Ctx) -> Any:
    return ctx.services.achievements.gallery(ctx.uid)


@api.route("GET", "/health", summary="Liveness and database check", tags=("ops",), response=HealthOut,
           auth=False)
def health(ctx: Ctx) -> Any:
    ok = ctx.services.db.ping()
    return {"status": "ok" if ok else "degraded", "database": "ok" if ok else "error",
            "version": lifeexe.__version__}


@api.route("GET", "/openapi.json", summary="OpenAPI 3.1 document", tags=("ops",), auth=False)
def openapi(ctx: Ctx) -> Any:
    return JSONResponse(api.openapi("LIFE.EXE API", lifeexe.__version__))
