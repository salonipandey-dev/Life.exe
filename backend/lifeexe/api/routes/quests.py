from __future__ import annotations

from typing import Any

from lifeexe.api.registry import api
from lifeexe.api.routing import Ctx
from lifeexe.api.schemas import (
    CompletionOut,
    QuestCreateIn,
    QuestListOut,
    QuestListQuery,
    QuestOut,
    QuestUpdateIn,
    ReopenOut,
)
from lifeexe.core.errors import NotFound
from lifeexe.domain.quests import QuestAction
from lifeexe.repositories.quests import QuestFilters

TAGS = ("quests",)


@api.route(
    "GET",
    "/quests",
    summary="List, filter, search and sort quests",
    tags=TAGS,
    query=QuestListQuery,
    response=QuestListOut,
)
def list_quests(ctx: Ctx, query: QuestListQuery) -> Any:
    filters = QuestFilters(
        statuses=tuple(query.status.split(",")) if query.status else (),
        category=query.category.value if query.category else None,
        difficulty=query.difficulty.value if query.difficulty else None,
        search=query.q or None,
        include_archived=query.include_archived,
        sort=query.sort,
        limit=query.limit,
        offset=query.offset,
    )
    return ctx.services.quests.list(ctx.uid, filters)


@api.route(
    "POST",
    "/quests",
    summary="Create a quest (XP is derived from difficulty, never supplied)",
    tags=TAGS,
    body=QuestCreateIn,
    response=QuestOut,
    status_code=201,
)
def create_quest(ctx: Ctx, body: QuestCreateIn) -> Any:
    data = body.model_dump(mode="json")
    return ctx.services.quests.create(ctx.uid, data)


@api.route("GET", "/quests/{quest_id:int}", summary="Get a quest with completion history", tags=TAGS, response=QuestOut)
def get_quest(ctx: Ctx, quest_id: int) -> Any:
    return ctx.services.quests.get(ctx.uid, quest_id)


@api.route(
    "PATCH",
    "/quests/{quest_id:int}",
    summary="Edit or reschedule a quest",
    tags=TAGS,
    body=QuestUpdateIn,
    response=QuestOut,
)
def update_quest(ctx: Ctx, quest_id: int, body: QuestUpdateIn) -> Any:
    changes = body.model_dump(mode="json", include=body.model_fields_set)
    return ctx.services.quests.update(ctx.uid, quest_id, changes)


@api.route(
    "DELETE", "/quests/{quest_id:int}", summary="Delete a quest without completion history", tags=TAGS, status_code=204
)
def delete_quest(ctx: Ctx, quest_id: int) -> None:
    ctx.services.quests.delete(ctx.uid, quest_id)


@api.route(
    "POST",
    "/quests/{quest_id:int}/complete",
    summary="Complete the current occurrence; awards XP exactly once",
    tags=TAGS,
    response=CompletionOut,
)
def complete_quest(ctx: Ctx, quest_id: int) -> Any:
    return ctx.services.quests.complete(ctx.uid, quest_id)


@api.route(
    "POST",
    "/quests/{quest_id:int}/reopen",
    summary="Reopen the current occurrence; reverses its XP with a ledger entry",
    tags=TAGS,
    response=ReopenOut,
)
def reopen_quest(ctx: Ctx, quest_id: int) -> Any:
    return ctx.services.quests.reopen(ctx.uid, quest_id)


@api.route(
    "POST",
    "/quests/{quest_id:int}/actions/{action}",
    summary="Lifecycle transition: publish, start, pause, resume, cancel, expire, restore",
    tags=TAGS,
    response=QuestOut,
)
def transition_quest(ctx: Ctx, quest_id: int, action: str) -> Any:
    try:
        parsed = QuestAction(action)
    except ValueError:
        raise NotFound("Unknown quest action.") from None
    return ctx.services.quests.transition(ctx.uid, quest_id, parsed)


@api.route("POST", "/quests/{quest_id:int}/archive", summary="Archive a finished quest", tags=TAGS, response=QuestOut)
def archive_quest(ctx: Ctx, quest_id: int) -> Any:
    return ctx.services.quests.set_archived(ctx.uid, quest_id, True)


@api.route(
    "POST", "/quests/{quest_id:int}/unarchive", summary="Restore an archived quest", tags=TAGS, response=QuestOut
)
def unarchive_quest(ctx: Ctx, quest_id: int) -> Any:
    return ctx.services.quests.set_archived(ctx.uid, quest_id, False)
