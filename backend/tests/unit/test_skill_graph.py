from lifeexe.domain.skills import (
    SkillProgressInput,
    SkillStatus,
    depth_levels,
    find_cycle,
    is_demonstrated,
    skill_statuses,
    topological_order,
    would_create_cycle,
)

# (skill, prerequisite): Pandas needs Python; EDA needs Pandas and Stats.
EDGES = [("pandas", "python"), ("eda", "pandas"), ("eda", "stats")]
NODES = ["python", "pandas", "stats", "eda"]


def test_acyclic_graph_has_no_cycle() -> None:
    assert find_cycle(NODES, EDGES) is None


def test_cycle_is_reported_as_path() -> None:
    cycle = find_cycle(NODES, [*EDGES, ("python", "eda")])
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"python", "pandas", "eda"}


def test_self_loop() -> None:
    assert find_cycle(["a"], [("a", "a")]) == ["a", "a"]


def test_would_create_cycle() -> None:
    assert would_create_cycle(EDGES, ("python", "eda"))
    assert would_create_cycle(EDGES, ("python", "python"))
    assert not would_create_cycle(EDGES, ("eda", "python"))  # redundant but acyclic


def test_topological_order_prerequisites_first_and_deterministic() -> None:
    order = topological_order(NODES, EDGES, {n: n for n in NODES})
    assert order.index("python") < order.index("pandas") < order.index("eda")
    assert order.index("stats") < order.index("eda")
    assert order == topological_order(list(reversed(NODES)), list(reversed(EDGES)), {n: n for n in NODES})


def test_depth_levels() -> None:
    assert depth_levels(NODES, EDGES) == {"python": 0, "stats": 0, "pandas": 1, "eda": 2}


def test_deep_chain_has_no_recursion_limit() -> None:
    n = 5000
    nodes = list(range(n))
    edges = [(i + 1, i) for i in range(n - 1)]
    assert find_cycle(nodes, edges) is None
    assert would_create_cycle(edges, (0, n - 1))


def _p(xp: int, ev: int, xp_req: int = 100, ev_req: int = 1) -> SkillProgressInput:
    return SkillProgressInput(xp, xp_req, ev, ev_req)


def test_xp_alone_never_demonstrates() -> None:
    assert not is_demonstrated(_p(xp=10_000, ev=0))
    assert not is_demonstrated(_p(xp=0, ev=5))
    assert is_demonstrated(_p(xp=100, ev=1))


def test_statuses_cascade_locks() -> None:
    progress = {
        "python": _p(150, 1),  # demonstrated
        "stats": _p(50, 0),  # in progress
        "pandas": _p(0, 0),  # available (python done)
        "eda": _p(500, 3),  # locked: stats not demonstrated
    }
    st = skill_statuses(NODES, EDGES, progress)
    assert st == {
        "python": SkillStatus.DEMONSTRATED,
        "stats": SkillStatus.IN_PROGRESS,
        "pandas": SkillStatus.AVAILABLE,
        "eda": SkillStatus.LOCKED,
    }
