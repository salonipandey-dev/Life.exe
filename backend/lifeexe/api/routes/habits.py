from __future__ import annotations

from datetime import date
from typing import Any

from lifeexe.api.registry import api
from lifeexe.api.routing import Ctx
from lifeexe.api.schemas import (
    HabitCreateIn,
    HabitListOut,
    HabitLogIn,
    HabitLogOut,
    HabitOut,
    HabitUpdateIn,
    IncludeArchivedQuery,
)
from lifeexe.core.errors import BadRequest
from lifeexe.domain.habits import weekdays_to_mask

TAGS = ("habits",)


def _to_fields(data: dict[str, Any]) -> dict[str, Any]:
    if "weekdays" in data:
        days = data.pop("weekdays")
        data["weekdays_mask"] = weekdays_to_mask(frozenset(days))
    return data


@api.route("GET", "/habits", summary="Habits with streaks, consistency and a 28-day calendar", tags=TAGS,
           query=IncludeArchivedQuery, response=HabitListOut)
def list_habits(ctx: Ctx, query: IncludeArchivedQuery) -> Any:
    return ctx.services.habits.list(ctx.uid, query.include_archived)


@api.route("POST", "/habits", summary="Create a habit", tags=TAGS, body=HabitCreateIn, response=HabitOut,
           status_code=201)
def create_habit(ctx: Ctx, body: HabitCreateIn) -> Any:
    return ctx.services.habits.create(ctx.uid, _to_fields(body.model_dump(mode="json")))


@api.route("GET", "/habits/{habit_id:int}", summary="Get a habit", tags=TAGS, response=HabitOut)
def get_habit(ctx: Ctx, habit_id: int) -> Any:
    return ctx.services.habits.get(ctx.uid, habit_id)


@api.route("PATCH", "/habits/{habit_id:int}", summary="Edit a habit", tags=TAGS, body=HabitUpdateIn,
           response=HabitOut)
def update_habit(ctx: Ctx, habit_id: int, body: HabitUpdateIn) -> Any:
    changes = _to_fields(body.model_dump(mode="json", include=body.model_fields_set))
    return ctx.services.habits.update(ctx.uid, habit_id, changes)


@api.route("POST", "/habits/{habit_id:int}/logs", summary="Record (or correct) a day: entry or rest day",
           tags=TAGS, body=HabitLogIn, response=HabitLogOut)
def log_habit(ctx: Ctx, habit_id: int, body: HabitLogIn) -> Any:
    return ctx.services.habits.log(ctx.uid, habit_id, body.day, body.entry_type, body.value, body.note)


@api.route("DELETE", "/habits/{habit_id:int}/logs/{day}", summary="Remove a day's entry (reverses its XP)",
           tags=TAGS, response=HabitLogOut)
def delete_habit_log(ctx: Ctx, habit_id: int, day: str) -> Any:
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise BadRequest("Day must be YYYY-MM-DD.") from None
    return ctx.services.habits.delete_log(ctx.uid, habit_id, parsed)


@api.route("POST", "/habits/{habit_id:int}/pause", summary="Pause (days become neutral)", tags=TAGS,
           response=HabitOut)
def pause_habit(ctx: Ctx, habit_id: int) -> Any:
    return ctx.services.habits.pause(ctx.uid, habit_id)


@api.route("POST", "/habits/{habit_id:int}/resume", summary="Resume a paused habit", tags=TAGS,
           response=HabitOut)
def resume_habit(ctx: Ctx, habit_id: int) -> Any:
    return ctx.services.habits.resume(ctx.uid, habit_id)


@api.route("POST", "/habits/{habit_id:int}/archive", summary="Archive a habit", tags=TAGS, response=HabitOut)
def archive_habit(ctx: Ctx, habit_id: int) -> Any:
    return ctx.services.habits.set_archived(ctx.uid, habit_id, True)


@api.route("POST", "/habits/{habit_id:int}/unarchive", summary="Unarchive a habit", tags=TAGS,
           response=HabitOut)
def unarchive_habit(ctx: Ctx, habit_id: int) -> Any:
    return ctx.services.habits.set_archived(ctx.uid, habit_id, False)
