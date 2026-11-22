"""Skill graph rules (pure, no I/O).

Skills form a directed acyclic graph: an edge ``(skill, prerequisite)`` means
"``prerequisite`` must be demonstrated before ``skill`` unlocks".

XP and evidence are deliberately separate:
- XP measures *engagement* (time and effort logged against a skill).
- Evidence measures *demonstrated competency* (a query you wrote, a project,
  a passed assessment). A skill is DEMONSTRATED only when it has enough of
  both — XP alone can never complete a skill.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Hashable, Iterable, Mapping, Sequence, TypeVar

N = TypeVar("N", bound=Hashable)


class SkillStatus(StrEnum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    DEMONSTRATED = "DEMONSTRATED"


def _prereqs(edges: Iterable[tuple[N, N]]) -> dict[N, set[N]]:
    graph: dict[N, set[N]] = defaultdict(set)
    for skill, prereq in edges:
        graph[skill].add(prereq)
    return graph


def find_cycle(nodes: Iterable[N], edges: Iterable[tuple[N, N]]) -> list[N] | None:
    """Return one cycle as a node path (first == last), or None if acyclic.

    Iterative DFS with white/grey/black colouring, so deep graphs cannot hit
    Python's recursion limit.
    """
    graph = _prereqs(edges)
    white, grey, black = 0, 1, 2
    colour: dict[N, int] = defaultdict(int)
    parent: dict[N, N] = {}
    all_nodes = list(dict.fromkeys([*nodes, *graph.keys()]))
    for root in all_nodes:
        if colour[root] != white:
            continue
        stack: list[tuple[N, list[N]]] = [(root, sorted(graph[root], key=repr))]
        colour[root] = grey
        while stack:
            node, children = stack[-1]
            if not children:
                colour[node] = black
                stack.pop()
                continue
            child = children.pop()
            if colour[child] == grey:
                cycle = [child, node]
                cur = node
                while cur != child:
                    cur = parent[cur]
                    cycle.append(cur)
                cycle.reverse()
                return cycle
            if colour[child] == white:
                colour[child] = grey
                parent[child] = node
                stack.append((child, sorted(graph[child], key=repr)))
    return None


def would_create_cycle(edges: Iterable[tuple[N, N]], new_edge: tuple[N, N]) -> bool:
    skill, prereq = new_edge
    if skill == prereq:
        return True
    # Adding skill -> prereq creates a cycle iff skill is already reachable
    # from prereq by following prerequisite edges.
    graph = _prereqs(edges)
    seen: set[N] = set()
    stack = [prereq]
    while stack:
        node = stack.pop()
        if node == skill:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return False


def topological_order(
    nodes: Sequence[N], edges: Iterable[tuple[N, N]], sort_key: Mapping[N, str]
) -> list[N]:
    """Kahn's algorithm; prerequisites come first. Ties are broken by
    ``sort_key`` so the roadmap order is deterministic."""
    edge_list = list(edges)
    dependants: dict[N, list[N]] = defaultdict(list)
    indegree: dict[N, int] = {n: 0 for n in nodes}
    for skill, prereq in edge_list:
        dependants[prereq].append(skill)
        indegree[skill] = indegree.get(skill, 0) + 1
        indegree.setdefault(prereq, 0)
    heap = [(sort_key.get(n, ""), i, n) for i, n in enumerate(indegree) if indegree[n] == 0]
    heapq.heapify(heap)
    index = {n: i for i, n in enumerate(indegree)}
    order: list[N] = []
    while heap:
        _, _, node = heapq.heappop(heap)
        order.append(node)
        for nxt in dependants[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(heap, (sort_key.get(nxt, ""), index[nxt], nxt))
    if len(order) != len(indegree):
        raise ValueError("graph contains a cycle")
    return order


def depth_levels(nodes: Sequence[N], edges: Iterable[tuple[N, N]]) -> dict[N, int]:
    """Tier of each node = length of the longest prerequisite chain below it."""
    edge_list = list(edges)
    order = topological_order(nodes, edge_list, {n: "" for n in nodes})
    prereqs = _prereqs(edge_list)
    depth: dict[N, int] = {}
    for node in order:
        depth[node] = 1 + max((depth[p] for p in prereqs.get(node, ())), default=-1)
    return depth


@dataclass(frozen=True)
class SkillProgressInput:
    xp: int
    xp_required: int
    evidence_count: int
    evidence_required: int


def is_demonstrated(p: SkillProgressInput) -> bool:
    return p.xp >= p.xp_required and p.evidence_count >= p.evidence_required


def skill_statuses(
    nodes: Sequence[N],
    edges: Iterable[tuple[N, N]],
    progress: Mapping[N, SkillProgressInput],
) -> dict[N, SkillStatus]:
    """Evaluate statuses in topological order so locks cascade correctly."""
    edge_list = list(edges)
    prereqs = _prereqs(edge_list)
    statuses: dict[N, SkillStatus] = {}
    for node in topological_order(nodes, edge_list, {n: "" for n in nodes}):
        p = progress[node]
        if any(statuses[q] is not SkillStatus.DEMONSTRATED for q in prereqs.get(node, ())):
            statuses[node] = SkillStatus.LOCKED
        elif is_demonstrated(p):
            statuses[node] = SkillStatus.DEMONSTRATED
        elif p.xp > 0 or p.evidence_count > 0:
            statuses[node] = SkillStatus.IN_PROGRESS
        else:
            statuses[node] = SkillStatus.AVAILABLE
    return statuses
