"""The capability matrix may not say a scheduled goal runs unless one runs.

WHY THIS FILE EXISTS

`tool_catalog` in app/services/agent_tasks.py reported `"scheduler": True` as a
literal, never as a probe. The command centre dock read that key straight into a
green light and, directly under it, listed every agent_schedules row with a
run_at and no task_id as the next scheduled goal. Those rows are the ones that
will never fire.

The reason is a call graph, not an opinion, so this file reads the call graph:

* `AgentTaskService.materialize_due_schedules` is the only thing that turns a
  due schedule into a task. It has one caller, the manual HTTP route in
  app/api/v1/agent_expansion.py.
* The cron the API image ships (infrastructure/docker/Dockerfile.api, then
  dispatch.py at the repository root) calls `dispatch_due` in
  app/services/dispatcher.py, which selects Workflow rows. It never touches
  agent_schedules, so it is not this scheduler's runner however much the two
  read alike.

So the guard is a coupling, not a constant. Flip the matrix to claim a runner
and it goes red for having none. Add a runner and leave the matrix claiming
none, and it goes red for that. Neither direction can be corrected in isolation.

No database: `tool_catalog` is a pure read of process configuration, and the
call graph comes from `ast`.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from app.services.agent_tasks import agent_tasks_service

ROOT = Path(__file__).resolve().parent
MATERIALIZE = "materialize_due_schedules"

#: Directories that hold no runner: vendored deploy copies of the estate's own
#: modules, throwaway agent worktrees, and build output.
_SKIP_DIRS = {".git", ".claude", "node_modules", "__pycache__", ".next", "venv"}


def _sources() -> List[Path]:
    """Every first party module that could hold a caller.

    Test modules are excluded on purpose. A test calling the materializer
    directly is not a runner in production, and counting one would make this
    guard unfalsifiable the moment somebody wrote a unit test for it.
    """
    found: List[Path] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if rel.name.startswith("test_") or rel.parts[0] == "tests":
            continue
        found.append(path)
    return sorted(found)


def _parents(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    links: Dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            links[child] = node
    return links


def _enclosing_function(
    node: ast.AST, links: Dict[ast.AST, ast.AST]
) -> Optional[ast.AST]:
    current = links.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = links.get(current)
    return None


def _route_decorator(func: ast.AST) -> Optional[Tuple[str, str]]:
    """(http method, path) if this function is a FastAPI route handler.

    Matches `@router.<method>("<path>", ...)`, which is how every route in
    app/api/v1 is declared. A caller reached only through an HTTP request is a
    human or an operator asking for the work, not a runner.
    """
    for decorator in getattr(func, "decorator_list", []):
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if not isinstance(target, ast.Attribute):
            continue
        if not isinstance(target.value, ast.Name) or target.value.id != "router":
            continue
        if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            continue
        path = decorator.args[0].value
        if isinstance(path, str):
            return target.attr.upper(), path
    return None


def _call_sites() -> Tuple[List[Tuple[str, int, str]], List[Tuple[str, int]]]:
    """Split every call of the materializer into HTTP routes and everything else."""
    routes: List[Tuple[str, int, str]] = []
    automatic: List[Tuple[str, int]] = []
    for path in _sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a parse failure is its own bug
            continue
        links = _parents(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if not isinstance(target, ast.Attribute) or target.attr != MATERIALIZE:
                continue
            rel = str(path.relative_to(ROOT))
            func = _enclosing_function(node, links)
            route = _route_decorator(func) if func is not None else None
            if route is None:
                automatic.append((rel, node.lineno))
            else:
                routes.append((rel, node.lineno, f"{route[0]} {route[1]}"))
    return routes, automatic


@pytest.fixture(scope="module")
def sites() -> Tuple[List[Tuple[str, int, str]], List[Tuple[str, int]]]:
    return _call_sites()


@pytest.fixture(scope="module")
def status() -> Dict[str, object]:
    expansion = agent_tasks_service.tool_catalog()["expansion"]
    assert isinstance(expansion, dict)
    detail = expansion.get("scheduler_status")
    assert isinstance(detail, dict), (
        "expansion.scheduler_status is gone from the capability matrix. The dock "
        "reads it for both the Scheduler light and the reason under the queued "
        "goals, and without it the dock has nothing to tell the truth from"
    )
    return {"expansion": expansion, "scheduler_status": detail}


def test_the_materializer_still_exists_and_is_still_called(sites) -> None:
    """Anti-vacuity. Everything below is about calls to one method.

    Rename or delete it and every coupling in this file would pass while
    describing something that is no longer there.
    """
    routes, automatic = sites
    assert hasattr(agent_tasks_service, MATERIALIZE), (
        f"AgentTaskService.{MATERIALIZE} is gone; this file guards a method that "
        "no longer exists and proves nothing"
    )
    assert routes or automatic, (
        f"nothing in the estate calls {MATERIALIZE} any more, not even the manual "
        "route. Either the route was dropped, in which case the schedule store "
        "has no path out at all and the matrix must say so, or this scan stopped "
        "finding call sites and is no longer a guard"
    )


def test_the_only_caller_is_the_manual_route(sites) -> None:
    routes, _ = sites
    assert len(routes) == 1, (
        "expected exactly one HTTP caller of the materializer, found "
        f"{routes}. More than one is not wrong on its own, but the matrix's "
        "materialize_route names a single path and would now be incomplete"
    )
    where, _line, signature = routes[0]
    assert where == "app/api/v1/agent_expansion.py", (
        f"the manual materialize route moved to {where}; the comment in "
        "app/services/agent_tasks.py cites the old path"
    )
    assert signature == "POST /schedules/materialize", (
        f"the route is now {signature}, so the matrix's advertised "
        "materialize_route no longer matches the code"
    )


def test_the_matrix_claims_a_runner_only_when_one_exists(sites, status) -> None:
    """The coupling. Both flags follow the call graph, in both directions."""
    _routes, automatic = sites
    detail = status["scheduler_status"]
    assert isinstance(detail, dict)
    runs = detail.get("runs_goals")

    assert runs is bool(automatic), (
        "expansion.scheduler_status.runs_goals says "
        f"{runs!r} while the automatic call sites of {MATERIALIZE} are "
        f"{automatic or 'none'}. A cron, a background loop or a startup task "
        "calling it is a runner and the matrix has to admit it; nothing calling "
        "it means recorded goals are inert and the matrix must not imply "
        "otherwise. Fix whichever half is lying"
    )

    # The plain flag exists so a consumer that never learned about
    # scheduler_status fails safe. It has to track the real answer, or the two
    # readings of the same catalog disagree.
    expansion = status["expansion"]
    assert isinstance(expansion, dict)
    assert expansion.get("scheduler") is runs, (
        "expansion.scheduler and expansion.scheduler_status.runs_goals "
        "disagree. The plain flag is the fail safe reading for a stale "
        "consumer; a stale consumer reading True while the detail says False is "
        "the original green light back again"
    )


def test_a_recorded_goal_that_cannot_run_still_says_so_out_loud(status) -> None:
    """The dock renders `detail` verbatim, so an empty one is a silent panel."""
    detail = status["scheduler_status"]
    assert isinstance(detail, dict)
    assert detail.get("records_goals") is True, (
        "the matrix no longer claims schedules are recorded, but "
        "POST /agent-expansion/schedules still writes them. Tee needs to know "
        "the rows are there; do not answer a dishonest green with a dishonest "
        "silence"
    )
    if detail.get("runs_goals") is False:
        assert detail.get("runner") is None, (
            "runs_goals is False and a runner is named. One of the two is wrong"
        )
        reason = detail.get("detail")
        assert isinstance(reason, str) and len(reason.strip()) >= 40, (
            "runs_goals is False and the matrix gives no reason. The dock shows "
            "this string under the queued goals, so an empty one leaves the "
            "panel listing goals with no word about whether anything runs them"
        )
