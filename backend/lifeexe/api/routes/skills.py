from __future__ import annotations

from typing import Any

from lifeexe.api.registry import api
from lifeexe.api.routing import Ctx
from lifeexe.api.schemas import (
    DependencyIn,
    EvidenceIn,
    SkillCreateIn,
    SkillDetailOut,
    SkillListOut,
    SkillUpdateIn,
)

TAGS = ("skills",)


@api.route("GET", "/skills", summary="Skill graph in roadmap (topological) order", tags=TAGS,
           response=SkillListOut)
def list_skills(ctx: Ctx) -> Any:
    return ctx.services.skills.list(ctx.uid)


@api.route("POST", "/skills", summary="Create a skill", tags=TAGS, body=SkillCreateIn,
           response=SkillDetailOut, status_code=201)
def create_skill(ctx: Ctx, body: SkillCreateIn) -> Any:
    return ctx.services.skills.create(ctx.uid, body.model_dump(mode="json"))


@api.route("GET", "/skills/{skill_id:int}", summary="Skill detail with evidence", tags=TAGS,
           response=SkillDetailOut)
def get_skill(ctx: Ctx, skill_id: int) -> Any:
    return ctx.services.skills.get(ctx.uid, skill_id)


@api.route("PATCH", "/skills/{skill_id:int}", summary="Edit a skill", tags=TAGS, body=SkillUpdateIn,
           response=SkillDetailOut)
def update_skill(ctx: Ctx, skill_id: int, body: SkillUpdateIn) -> Any:
    return ctx.services.skills.update(ctx.uid, skill_id, body.model_dump(mode="json", include=body.model_fields_set))


@api.route("POST", "/skills/{skill_id:int}/archive", summary="Archive a skill", tags=TAGS, status_code=204)
def archive_skill(ctx: Ctx, skill_id: int) -> None:
    ctx.services.skills.archive(ctx.uid, skill_id)


@api.route("POST", "/skills/{skill_id:int}/prerequisites",
           summary="Add a prerequisite (rejected with 409 if it would create a cycle)", tags=TAGS,
           body=DependencyIn, response=SkillDetailOut, status_code=201)
def add_prerequisite(ctx: Ctx, skill_id: int, body: DependencyIn) -> Any:
    return ctx.services.skills.add_dependency(ctx.uid, skill_id, body.prerequisite_id)


@api.route("DELETE", "/skills/{skill_id:int}/prerequisites/{prerequisite_id:int}",
           summary="Remove a prerequisite", tags=TAGS, status_code=204)
def remove_prerequisite(ctx: Ctx, skill_id: int, prerequisite_id: int) -> None:
    ctx.services.skills.remove_dependency(ctx.uid, skill_id, prerequisite_id)


@api.route("POST", "/skills/{skill_id:int}/evidence", summary="Record evidence of competency", tags=TAGS,
           body=EvidenceIn, response=SkillDetailOut, status_code=201)
def add_evidence(ctx: Ctx, skill_id: int, body: EvidenceIn) -> Any:
    return ctx.services.skills.add_evidence(ctx.uid, skill_id, body.model_dump(mode="json"))


@api.route("DELETE", "/skills/{skill_id:int}/evidence/{evidence_id:int}", summary="Delete evidence",
           tags=TAGS, status_code=204)
def delete_evidence(ctx: Ctx, skill_id: int, evidence_id: int) -> None:
    ctx.services.skills.delete_evidence(ctx.uid, skill_id, evidence_id)
