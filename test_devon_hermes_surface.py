"""The Hermes agent surface, pinned so DEVON cannot miss an update to it.

DEVON's record of the Hermes agent is the capability table in
``docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md``, maintained
by hand. Nothing bound it to the code, so a new tool, route, table, column,
state or migration could land and leave the record silently stale.

This file binds them. It derives the surface from the code on every run and
compares it to ``docs/devon/hermes-surface.json``, the manifest DEVON owns.

What is pinned, and what is not:

* Tools come from ``build_tool_registry()``, the registry the running service
  builds, not from one adapter. Counting from a single lane is how this estate
  has been wrong before, and a HIGH_IMPACT tool added to any other adapter is
  still a Hermes agent update.
* Routes cover the whole agent runtime HTTP surface, not just the expansion
  prefix.
* Tables carry their columns, so a column added to an existing table is caught.
* Migrations carry their parent, so a new revision cannot land unrecorded.
  This reads the source tree, which says what the next deploy will apply. What
  the deployed estate actually runs is ``scripts/estate_reconcile.py``, and it
  is UNVERIFIED without a Railway read. This file does not close that.

Every slice is a sorted set of strings, so hand-reordering the manifest cannot
produce a failure that names nothing.

Regenerate the manifest after a deliberate change:

    PYTHONPATH=$PWD python3 -m test_devon_hermes_surface

Regenerating is not the whole amendment, and on its own it cannot clear a red:
the counts stated in the Hermes status document are checked against the code
too, so the record has to move with the manifest.

Cheap on purpose: no database, no network, no TestClient.
"""

from __future__ import annotations

import enum
import inspect
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pytest
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.models import agent_runtime as agent_models
from app.services.agent_tasks import build_tool_registry
from services.agent_runtime import expansion
from services.agent_runtime.expansion_tools import ExpansionToolAdapter
from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "docs" / "devon" / "hermes-surface.json"
RECORD_PATH = ROOT / "docs" / "devon" / "SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md"

#: The HTTP prefixes the agent runtime serves. A new one belongs here and in
#: the record, which is the point of the test that counts them.
RUNTIME_PREFIXES = ("/agent-expansion", "/agent-tasks")

#: The records a surface change has to move with it.
RECORDS = (
    "docs/devon/hermes-surface.json (this manifest)",
    "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md (the counts and the table)",
    "a dated docs/devon/SYS_OPS_*.md closing the arc",
    "scripts/estate_reconcile.py DOC_CLAIMS, if a pinned sentence changed",
)


def _tools() -> List[str]:
    """Every tool the running service registers, with its governance."""
    registry = build_tool_registry()
    return sorted(
        "{name} | risk={risk} | reversible={reversible} | blast={blast_radius}".format(**spec)
        for spec in registry.describe()
    )


def _routes() -> List[str]:
    """Every HTTP method and path the agent runtime serves."""
    app = FastAPI()
    app.include_router(api_router)
    return sorted(
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(RUNTIME_PREFIXES)
        for method in operations
    )


def _columns() -> List[str]:
    """Every agent runtime table and the columns it carries."""
    found: List[str] = []
    for obj in vars(agent_models).values():
        if not (inspect.isclass(obj) and hasattr(obj, "__tablename__")):
            continue
        if obj.__module__ != agent_models.__name__:
            continue
        found.extend(f"{obj.__tablename__}.{column.name}" for column in obj.__table__.columns)
    return sorted(found)


def _states() -> List[str]:
    """Every expansion state machine and the values it admits."""
    found: List[str] = []
    for name, obj in vars(expansion).items():
        if (
            inspect.isclass(obj)
            and issubclass(obj, enum.Enum)
            and obj.__module__ == expansion.__name__
        ):
            found.extend(f"{name}.{member.value}" for member in obj)
    return sorted(found)


def _migrations() -> List[str]:
    """Every migration in the source tree, with the revision it follows."""
    versions = ROOT / "database" / "migrations" / "versions"
    found: List[str] = []
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision = re.search(r'^revision = "([^"]+)"', text, re.MULTILINE)
        parent = re.search(r"^down_revision = (?:\"([^\"]+)\"|None)", text, re.MULTILINE)
        if revision:
            found.append(f"{revision.group(1)} <- {parent.group(1) if parent and parent.group(1) else 'root'}")
    return sorted(found)


SLICES = {
    "tools": _tools,
    "routes": _routes,
    "columns": _columns,
    "states": _states,
    "migrations": _migrations,
}


def live_surface() -> Dict[str, List[str]]:
    """The Hermes agent surface as the code has it right now."""
    return {name: derive() for name, derive in SLICES.items()}


def manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _drift(slice_name: str, live: Iterable[str], recorded: Iterable[str]) -> str:
    """A failure a reader can act on without opening this file."""
    live_set, recorded_set = set(live), set(recorded)
    added = sorted(live_set - recorded_set)
    removed = sorted(recorded_set - live_set)
    lines = [
        "",
        f"The Hermes agent {slice_name} changed and DEVON's record did not.",
        "",
        "  in the code, not in DEVON:",
        *(f"      + {item}" for item in added or ["(nothing)"]),
        "  in DEVON, not in the code:",
        *(f"      - {item}" for item in removed or ["(nothing)"]),
        "",
        "Amend, in the same pull request:",
        *(f"  {index}. {record}" for index, record in enumerate(RECORDS, start=1)),
        "",
        "Regenerating the manifest alone will not clear this:",
        "  PYTHONPATH=$PWD python3 -m test_devon_hermes_surface",
        "  then correct the counts in the Hermes status document to match.",
        "",
    ]
    return "\n".join(lines)


@pytest.mark.parametrize("slice_name", sorted(SLICES))
def test_surface_slice_matches_devon(slice_name: str) -> None:
    live = SLICES[slice_name]()
    recorded = manifest()[slice_name]
    assert set(live) == set(recorded), _drift(slice_name, live, recorded)
    assert list(recorded) == sorted(recorded), (
        f"the {slice_name} manifest is out of canonical order, so its diffs will not "
        "read cleanly. Regenerate it with "
        "PYTHONPATH=$PWD python3 -m test_devon_hermes_surface"
    )


def _stated_counts() -> Dict[str, int]:
    """The counts the Hermes record states in prose, parsed back out of it."""
    text = RECORD_PATH.read_text(encoding="utf-8")
    counts: Dict[str, int] = {}
    for slice_name in SLICES:
        found = re.search(rf"(\d+)\s+governed\s+{slice_name}\b", text)
        assert found, (
            f"the Hermes record no longer states a count for {slice_name}. It must "
            f"carry the phrase 'N governed {slice_name}' so this test can check it."
        )
        counts[slice_name] = int(found.group(1))
    return counts


def test_the_record_states_counts_that_match_the_code() -> None:
    """Regenerating the manifest cannot clear a red on its own.

    The manifest is machine written, so a careless author could reconcile it
    with one command and never touch the record a human reads. The record
    states its own counts in prose, and they are checked here against the code,
    so a surface change has to move the document too.
    """
    stated = _stated_counts()
    for slice_name, derive in SLICES.items():
        live = len(derive())
        assert stated[slice_name] == live, (
            f"the Hermes record says {stated[slice_name]} governed {slice_name}, the code has "
            f"{live}. Correct {RECORD_PATH.relative_to(ROOT)}, do not only regenerate the manifest."
        )


def test_manifest_names_the_records_to_amend() -> None:
    assert MANIFEST_PATH.is_file(), f"DEVON's Hermes manifest is missing at {MANIFEST_PATH}"
    readme = " ".join(manifest()["_readme"])
    assert "hermes-stack-status_v2" in readme, (
        "the manifest must name the DEVON record a surface change has to move with it"
    )


def test_every_high_impact_tool_stays_irreversible_and_declares_its_blast_radius() -> None:
    """A HIGH_IMPACT tool quietly relabelled reversible would change what a
    human is agreeing to when they rule on its approval."""
    registry = build_tool_registry()
    for spec in registry.describe():
        assert spec["blast_radius"], f"{spec['name']} declares no blast radius"
        if spec["risk"] == "high_impact":
            assert spec["reversible"] is False, (
                f"{spec['name']} is HIGH_IMPACT but now claims to be reversible, which "
                "changes what the human ruling on its approval is agreeing to"
            )


def test_every_expansion_tool_stays_a_governed_write() -> None:
    registry = ToolRegistry()
    ExpansionToolAdapter().register(registry)
    for spec in registry.describe():
        assert spec["risk"] == "write", (
            f"{spec['name']} is no longer a WRITE tool, so it no longer raises the "
            "human approval the Hermes record says every expansion tool raises"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("runtime.spawn_subagent", {"goal": "probe"}),
        ("runtime.schedule_goal", {"goal": "probe", "delay_seconds": 60}),
        ("runtime.propose_skill", {"task_id": "t1", "goal": "probe", "observations": []}),
    ],
)
async def test_a_missing_durable_writer_refuses_through_the_real_call_path(
    tool: str, arguments: Dict[str, Any]
) -> None:
    """The invariant that stops a Hermes update from vanishing into memory.

    Driven through ``registry.execute`` rather than the adapter's private
    guard, so deleting the guard from a handler fails here. If a handler ever
    succeeds into the process-local store outside tests, the operator sees a
    succeeded result for a row that exists nowhere, and DEVON has missed the
    update.
    """
    registry = ToolRegistry()
    adapter = ExpansionToolAdapter(approvals=ApprovalQueue())
    assert adapter.process_local_ok is False, (
        "the process-local store must stay opt-in, or a missing writer silently "
        "drops every Hermes update"
    )
    assert adapter.durable is False, "a bare adapter has no durable writer and must say so"
    adapter.register(registry)

    result = await registry.execute(tool, arguments)

    assert result.ok is False, f"{tool} accepted a write with no durable writer injected"
    assert "process-local store is refused" in (result.error or ""), (
        f"{tool} refused for the wrong reason: {result.error!r}"
    )


@pytest.mark.asyncio
async def test_no_approval_authority_refuses_through_the_real_call_path() -> None:
    """The other way a Hermes update could land unrecorded and ungoverned."""
    registry = ToolRegistry()
    ExpansionToolAdapter().register(registry)
    result = await registry.execute("runtime.spawn_subagent", {"goal": "probe"})
    assert result.ok is False
    assert "no approval authority" in (result.error or "")


def _regenerate() -> None:
    """Rewrite the manifest from the code, keeping the readme DEVON wrote."""
    current = manifest() if MANIFEST_PATH.is_file() else {"_readme": []}
    payload = {"_readme": current["_readme"], **live_surface()}
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    counts = {name: len(values) for name, values in live_surface().items()}
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print("the record must now state:")
    for name in sorted(counts):
        print(f"  {counts[name]} governed {name}")


if __name__ == "__main__":
    _regenerate()
