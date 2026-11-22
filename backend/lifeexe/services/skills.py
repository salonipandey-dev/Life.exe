from __future__ import annotations

from typing import Any

from lifeexe.core.db import Connection, Database, is_unique_violation
from lifeexe.core.errors import Conflict, NotFound
from lifeexe.core.timeutil import Clock, to_iso
from lifeexe.domain.skills import (
    SkillProgressInput,
    SkillStatus,
    depth_levels,
    find_cycle,
    skill_statuses,
    topological_order,
    would_create_cycle,
)
from lifeexe.repositories import ledger
from lifeexe.repositories import skills as skills_repo
from lifeexe.services.seed import slugify


def compute_skill_states(conn: Connection, user_id: int) -> list[dict[str, Any]]:
    """Read model for the skill tree: XP (engagement) and evidence (competency)
    are reported separately, together with the derived status."""
    rows = skills_repo.list_skills(conn, user_id, include_archived=False)
    ids = [int(r["id"]) for r in rows]
    id_set = set(ids)
    edges = [(s, p) for s, p in skills_repo.dependencies(conn, user_id) if s in id_set and p in id_set]
    xp = ledger.xp_by_skill(conn, user_id)
    progress = {
        int(r["id"]): SkillProgressInput(
            xp=max(xp.get(int(r["id"]), 0), 0),
            xp_required=int(r["xp_required"]),
            evidence_count=int(r["evidence_count"]),
            evidence_required=int(r["evidence_required"]),
        )
        for r in rows
    }
    statuses = skill_statuses(ids, edges, progress)
    tiers = depth_levels(ids, edges)
    order = topological_order(ids, edges, {int(r["id"]): f"{r['tree']}|{r['name']}" for r in rows})
    position = {sid: i for i, sid in enumerate(order)}
    prereqs: dict[int, list[int]] = {sid: [] for sid in ids}
    for skill_id, prereq_id in edges:
        prereqs[skill_id].append(prereq_id)
    out = []
    for r in rows:
        sid = int(r["id"])
        p = progress[sid]
        out.append(
            {
                "id": sid,
                "slug": r["slug"],
                "name": r["name"],
                "tree": r["tree"],
                "attribute": r["attribute"],
                "description": r["description"],
                "xp": p.xp,
                "xp_required": p.xp_required,
                "evidence_count": p.evidence_count,
                "evidence_required": p.evidence_required,
                "status": statuses[sid].value,
                "prerequisite_ids": sorted(prereqs[sid]),
                "tier": tiers[sid],
                "roadmap_position": position[sid],
            }
        )
    out.sort(key=lambda s: s["roadmap_position"])
    return out


def demonstrated_count(conn: Connection, user_id: int) -> int:
    return sum(1 for s in compute_skill_states(conn, user_id) if s["status"] == SkillStatus.DEMONSTRATED.value)


class SkillService:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def list(self, user_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            skills = compute_skill_states(conn, user_id)
        trees = sorted({s["tree"] for s in skills})
        return {"skills": skills, "trees": trees}

    def get(self, user_id: int, skill_id: int) -> dict[str, Any]:
        with self.db.transaction(write=False) as conn:
            return self._detail(conn, user_id, skill_id)

    def _detail(self, conn: Connection, user_id: int, skill_id: int) -> dict[str, Any]:
        state = next((s for s in compute_skill_states(conn, user_id) if s["id"] == skill_id), None)
        if state is None:
            raise NotFound("Skill not found.")
        evidence = [
            {"id": e["id"], "title": e["title"], "url": e["url"], "notes": e["notes"], "created_at": e["created_at"]}
            for e in skills_repo.evidence_for_skill(conn, user_id, skill_id)
        ]
        return {**state, "evidence": evidence}

    def create(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        now = to_iso(self.clock.now())
        with self.db.transaction() as conn:
            base = slugify(data["name"])
            slug, n = base, 2
            while skills_repo.slug_exists(conn, user_id, slug):
                slug, n = f"{base[:55]}-{n}", n + 1
            skill_id = skills_repo.insert(conn, user_id, {**data, "slug": slug, "created_at": now})
            return self._detail(conn, user_id, skill_id)

    def update(self, user_id: int, skill_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            if skills_repo.get(conn, user_id, skill_id) is None:
                raise NotFound("Skill not found.")
            if changes:
                skills_repo.update(conn, user_id, skill_id, changes)
            return self._detail(conn, user_id, skill_id)

    def archive(self, user_id: int, skill_id: int) -> None:
        with self.db.transaction() as conn:
            if skills_repo.get(conn, user_id, skill_id) is None:
                raise NotFound("Skill not found.")
            skills_repo.update(conn, user_id, skill_id, {"archived_at": to_iso(self.clock.now())})

    def add_dependency(self, user_id: int, skill_id: int, prerequisite_id: int) -> dict[str, Any]:
        with self.db.transaction() as conn:
            skill = skills_repo.get(conn, user_id, skill_id)
            prereq = skills_repo.get(conn, user_id, prerequisite_id)
            if skill is None or prereq is None:
                raise NotFound("Skill not found.")
            edges = skills_repo.dependencies(conn, user_id)
            if (skill_id, prerequisite_id) in edges:
                raise Conflict("That prerequisite already exists.")
            if would_create_cycle(edges, (skill_id, prerequisite_id)):
                cycle = find_cycle([], [*edges, (skill_id, prerequisite_id)]) or []
                names = {int(r["id"]): r["name"] for r in skills_repo.list_skills(conn, user_id, True)}
                path = " → ".join(names.get(n, str(n)) for n in cycle)
                raise Conflict(f"That would create a circular dependency: {path}.", details={"cycle": cycle})
            try:
                skills_repo.add_dependency(conn, user_id, skill_id, prerequisite_id, to_iso(self.clock.now()))
            except Exception as exc:
                if is_unique_violation(exc):
                    raise Conflict("That prerequisite already exists.") from None
                raise
            return self._detail(conn, user_id, skill_id)

    def remove_dependency(self, user_id: int, skill_id: int, prerequisite_id: int) -> None:
        with self.db.transaction() as conn:
            if skills_repo.remove_dependency(conn, user_id, skill_id, prerequisite_id) == 0:
                raise NotFound("Dependency not found.")

    def add_evidence(self, user_id: int, skill_id: int, data: dict[str, Any]) -> dict[str, Any]:
        from lifeexe.services.achievements import evaluate_achievements

        with self.db.transaction() as conn:
            if skills_repo.get(conn, user_id, skill_id) is None:
                raise NotFound("Skill not found.")
            now = to_iso(self.clock.now())
            skills_repo.insert_evidence(conn, user_id, skill_id, data["title"], data.get("url"), data.get("notes", ""), now)
            unlocked = evaluate_achievements(conn, user_id, now)
            return {**self._detail(conn, user_id, skill_id), "achievements_unlocked": unlocked}

    def delete_evidence(self, user_id: int, skill_id: int, evidence_id: int) -> None:
        with self.db.transaction() as conn:
            if skills_repo.delete_evidence(conn, user_id, skill_id, evidence_id) == 0:
                raise NotFound("Evidence not found.")
