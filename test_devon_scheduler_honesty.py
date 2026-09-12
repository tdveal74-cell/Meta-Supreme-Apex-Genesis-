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

WHAT THIS FILE COUPLED TO THE WRONG FACT, AND THE CORRECTION

Until 2026-09-10 it asserted `runs_goals is bool(automatic)`: a first party
automatic call site in this repository meant the matrix had to claim goals run.
A runner landed that day, `app/services/agent_scheduler.py` called from
`dispatch.py`, and this file duly demanded True. An adversary then measured the
deployment instead of the repository, and the live Railway project held exactly
three services (api, presence, Postgres), no cron or job service, a long running
uvicorn container, and zero log lines mentioning dispatch over two hours against
a documented per minute schedule. The image carried a runner that nothing ran,
and the dock would have lit a green Scheduler tile over goals that still could
not fire.

A call site is therefore evidence that a RUNNER EXISTS, and nothing more. So the
couplings split:

* `runner` is named exactly when an automatic call site exists. That is a fact
  about this repository and `ast` reads it here, in both directions.
* `runs_goals`, the plain `scheduler` flag and
  `tick_scheduled_in_this_deployment` follow `SCHEDULER_TICK_INSTALLED`, an
  operator statement about ONE deployment, defaulting to False. This file proves
  that coupling by flipping the setting and re-reading the catalog, so it is a
  measurement rather than a restatement.
* `runs_goals` may never be True while `runner` is None: a tick cannot schedule a
  runner that does not exist.

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


def test_the_matrix_names_a_runner_only_when_one_exists(sites, status) -> None:
    """The repository half of the coupling, in both directions."""
    _routes, automatic = sites
    detail = status["scheduler_status"]
    assert isinstance(detail, dict)
    runner = detail.get("runner")

    assert (runner is not None) is bool(automatic), (
        "expansion.scheduler_status.runner says "
        f"{runner!r} while the automatic call sites of {MATERIALIZE} are "
        f"{automatic or 'none'}. A cron, a background loop or a startup task "
        "calling it is a runner and the matrix has to name it; nothing calling "
        "it means no runner exists and the matrix must not name one. Fix "
        "whichever half is lying"
    )
    if runner is not None:
        assert isinstance(runner, str) and runner.strip(), (
            "runner is present and empty, which names nothing"
        )
        # The named module has to be the one the call graph found, or the string
        # is decoration. Every automatic call site's module must appear in it,
        # matched with the .py stripped because the matrix names the callable in
        # dotted form (module.function) rather than the file.
        for where, _line in automatic:
            stem = where[:-3] if where.endswith(".py") else where
            assert stem in runner, (
                f"the call graph found an automatic caller at {where} and the "
                f"matrix names {runner!r}. A reader following the name would not "
                "arrive at the code that runs"
            )
        assert detail.get("runner_in_image") is True, (
            "a runner is named and runner_in_image is not True"
        )
    else:
        assert detail.get("runner_in_image") is not True, (
            "runner_in_image is True while no runner exists in the call graph"
        )


def test_the_matrix_claims_goals_run_only_where_the_tick_is_scheduled(sites, status) -> None:
    """The deployment half. A runner in the image is not a runner that runs."""
    from app.core.config import settings

    _routes, automatic = sites
    detail = status["scheduler_status"]
    assert isinstance(detail, dict)
    runs = detail.get("runs_goals")
    installed = bool(getattr(settings, "SCHEDULER_TICK_INSTALLED", False))

    assert runs is installed, (
        f"expansion.scheduler_status.runs_goals says {runs!r} while "
        f"SCHEDULER_TICK_INSTALLED is {installed!r}. Whether a due goal fires is "
        "a property of the deployment, not of this repository: an image can carry "
        "a runner that nothing schedules, which is exactly what was about to be "
        "reported as True on 2026-09-10"
    )
    assert detail.get("tick_scheduled_in_this_deployment") is runs, (
        "tick_scheduled_in_this_deployment and runs_goals disagree, so the two "
        "readings of the same fact do not match"
    )

    if runs:
        assert bool(automatic), (
            "runs_goals is True and NOTHING in this repository calls "
            f"{MATERIALIZE} automatically. A scheduled tick of an entrypoint that "
            "materializes nothing fires nothing"
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


def test_the_deployment_flag_is_read_rather_than_restated(monkeypatch) -> None:
    """Prove the coupling above by moving the flag and re-reading the catalog.

    Without this the previous test could pass over two constants that happen to
    agree. Both directions are exercised, and each one also asserts the sentence
    the dock renders changes with it, because a matrix whose flag moves and whose
    prose does not is the same defect in the half a person actually reads.
    """
    from app.core.config import settings

    def read() -> Dict[str, object]:
        status = agent_tasks_service.tool_catalog()["expansion"]
        assert isinstance(status, dict)
        inner = status["scheduler_status"]
        assert isinstance(inner, dict)
        return {"expansion": status, "detail": inner}

    monkeypatch.setattr(settings, "SCHEDULER_TICK_INSTALLED", False, raising=False)
    off = read()
    assert off["detail"]["runs_goals"] is False  # type: ignore[index]
    assert off["expansion"]["scheduler"] is False  # type: ignore[index]
    reason_off = off["detail"]["detail"]  # type: ignore[index]
    assert isinstance(reason_off, str)
    assert "NOTHING IN THIS DEPLOYMENT SCHEDULES" in reason_off, (
        "with the tick unscheduled the dock's own sentence does not say nothing "
        f"schedules it: {reason_off!r}"
    )

    monkeypatch.setattr(settings, "SCHEDULER_TICK_INSTALLED", True, raising=False)
    on = read()
    assert on["detail"]["runs_goals"] is True, (  # type: ignore[index]
        "SCHEDULER_TICK_INSTALLED was set and runs_goals did not move, so the "
        "flag is not read at all and the value above is a constant"
    )
    assert on["expansion"]["scheduler"] is True  # type: ignore[index]
    reason_on = on["detail"]["detail"]  # type: ignore[index]
    assert isinstance(reason_on, str)
    assert reason_on != reason_off, (
        "the flag moved and the sentence the dock renders did not"
    )
    assert "NOTHING IN THIS DEPLOYMENT SCHEDULES" not in reason_on
    # Even the scheduled sentence has to keep the human gate in it, because the
    # dock prints it verbatim beside a green light.
    assert "human gated" in reason_on, (
        "the scheduled sentence drops the human gate, and the dock prints it "
        f"verbatim next to a green tile: {reason_on!r}"
    )
    # and the runner is named in both, because the image carries it either way
    assert off["detail"]["runner"] == on["detail"]["runner"]  # type: ignore[index]


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
    reason = detail.get("detail")
    assert isinstance(reason, str) and len(reason.strip()) >= 40, (
        "the matrix gives no reason. The dock shows this string under the queued "
        "goals in BOTH branches, so an empty one leaves the panel listing goals "
        "with no word about whether anything runs them"
    )
    if detail.get("runs_goals") is False:
        # A runner MAY be named here: since 2026-09-10 the image carries one
        # whether or not this deployment schedules it, and hiding that would be
        # its own dishonesty. What the sentence may not do is imply goals fire.
        assert "NOTHING IN THIS DEPLOYMENT SCHEDULES" in reason, (
            "runs_goals is False and the sentence does not say that nothing "
            f"schedules the runner: {reason!r}"
        )
        assert detail.get("materialize_route"), (
            "nothing fires a due goal automatically and the matrix does not name "
            "the manual route that can, so a recorded goal has no stated path out"
        )
