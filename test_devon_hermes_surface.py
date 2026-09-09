"""The Hermes agent surface, pinned so DEVON cannot miss an update to it.

DEVON's record of the Hermes agent lives in
``docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md``, whose "On
main" table is maintained by hand. Nothing bound that table to the code, so a
new runtime tool, a new route, a new table or a new state could land and leave
the record silently stale. That already happened once: the same document said
Alembic head 010 while production ran 015, caught by the audit of 2026-09-02
rather than by any check.

This file closes that gap. It derives the Hermes agent surface from the code on
every run and compares it to ``docs/devon/hermes-surface.json``, the manifest
DEVON owns. A surface change with no matching amendment fails here, and the
failure names what moved and which records to amend.

Regenerate the manifest after a deliberate change:

    PYTHONPATH=$PWD python3 -m test_devon_hermes_surface

Cheap on purpose: no database, no network, no TestClient.
"""

from __future__ import annotations

import enum
import inspect
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.models import agent_runtime as agent_models
from services.agent_runtime import expansion
from services.agent_runtime.expansion_tools import ExpansionToolAdapter
from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "docs" / "devon" / "hermes-surface.json"

#: The records a surface change has to move with it. Named in the failure
#: message so the next session does not have to go looking for them.
RECORDS = (
    "docs/devon/hermes-surface.json (this manifest)",
    "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md (the On main table)",
    "a dated docs/devon/SYS_OPS_*.md closing the arc",
    "scripts/estate_reconcile.py DOC_CLAIMS, if a pinned sentence changed",
)


def _tools() -> List[Dict[str, Any]]:
    """Every runtime tool the expansion adapter registers, with its governance."""
    registry = ToolRegistry()
    ExpansionToolAdapter().register(registry)
    return [
        {
            "name": spec["name"],
            "risk": spec["risk"],
            "reversible": spec["reversible"],
            "blast_radius": spec["blast_radius"],
        }
        for spec in registry.describe()
    ]


def _routes() -> List[str]:
    """Every HTTP method and path under the agent-expansion prefix."""
    app = FastAPI()
    app.include_router(api_router)
    paths = app.openapi()["paths"]
    return sorted(
        f"{method.upper()} {path}"
        for path, operations in paths.items()
        if "agent-expansion" in path
        for method in operations
    )


def _tables() -> List[str]:
    """Every table the agent runtime models map to."""
    return sorted(
        obj.__tablename__
        for obj in vars(agent_models).values()
        if inspect.isclass(obj) and hasattr(obj, "__tablename__")
    )


def _states() -> Dict[str, List[str]]:
    """Every expansion state machine and the values it admits."""
    found: Dict[str, List[str]] = {}
    for name, obj in vars(expansion).items():
        if (
            inspect.isclass(obj)
            and issubclass(obj, enum.Enum)
            and obj.__module__ == expansion.__name__
        ):
            found[name] = sorted(member.value for member in obj)
    return found


def live_surface() -> Dict[str, Any]:
    """The Hermes agent surface as the code has it right now."""
    return {
        "tools": _tools(),
        "routes": _routes(),
        "tables": _tables(),
        "states": _states(),
    }


def manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _drift(slice_name: str, live: Any, recorded: Any) -> str:
    """A failure a reader can act on without opening this file."""
    lines = [
        "",
        f"The Hermes agent {slice_name} changed and DEVON's record did not.",
        "",
        f"  in the code, not in DEVON: {_only(live, recorded) or 'none'}",
        f"  in DEVON, not in the code: {_only(recorded, live) or 'none'}",
        "",
        "Amend, in the same pull request:",
    ]
    lines.extend(f"  {index}. {record}" for index, record in enumerate(RECORDS, start=1))
    lines += [
        "",
        "Regenerate the manifest with:",
        "  PYTHONPATH=$PWD python3 -m test_devon_hermes_surface",
        "",
    ]
    return "\n".join(lines)


def _only(left: Any, right: Any) -> str:
    """What is in left and not in right, rendered for a human."""
    if isinstance(left, dict) and isinstance(right, dict):
        return ", ".join(
            f"{key}={left[key]!r}" for key in sorted(left) if right.get(key) != left[key]
        )
    left_items = [json.dumps(item, sort_keys=True) for item in left]
    right_items = {json.dumps(item, sort_keys=True) for item in right}
    return ", ".join(item for item in left_items if item not in right_items)


def test_manifest_exists_and_names_the_records_to_amend() -> None:
    assert MANIFEST_PATH.is_file(), f"DEVON's Hermes manifest is missing at {MANIFEST_PATH}"
    readme = manifest()["_readme"]
    assert "hermes-stack-status_v2" in " ".join(readme), (
        "the manifest must name the DEVON record a surface change has to move with it"
    )


def test_runtime_tools_match_devon() -> None:
    live, recorded = _tools(), manifest()["tools"]
    assert live == recorded, _drift("runtime tools", live, recorded)


def test_http_routes_match_devon() -> None:
    live, recorded = _routes(), manifest()["routes"]
    assert live == recorded, _drift("HTTP routes", live, recorded)


def test_tables_match_devon() -> None:
    live, recorded = _tables(), manifest()["tables"]
    assert live == recorded, _drift("tables", live, recorded)


def test_states_match_devon() -> None:
    live, recorded = _states(), manifest()["states"]
    assert live == recorded, _drift("state machines", live, recorded)


def test_every_runtime_tool_stays_a_governed_write() -> None:
    """A tool downgraded from WRITE would skip the approval the record claims."""
    for spec in _tools():
        assert spec["risk"] == "write", (
            f"{spec['name']} is no longer a WRITE tool, so it no longer raises the "
            "human approval the Hermes record says every expansion tool raises"
        )


def test_a_missing_durable_writer_refuses_rather_than_writing_process_local() -> None:
    """The invariant that stops a Hermes update from vanishing into memory.

    An adapter with no writer injected must refuse. If it ever succeeds into
    the process-local store outside tests, the operator sees a succeeded
    result for a row that exists nowhere, and DEVON has missed the update.
    """
    adapter = ExpansionToolAdapter(approvals=ApprovalQueue())
    assert adapter.process_local_ok is False, (
        "the process-local store must stay opt-in, or a missing writer silently "
        "drops every Hermes update"
    )
    assert adapter.durable is False, "a bare adapter has no durable writer and must say so"
    for tool in ("runtime.spawn_subagent", "runtime.schedule_goal", "runtime.propose_skill"):
        refusal = adapter._ready(None, tool_name=tool)
        assert refusal is not None and refusal.ok is False, (
            f"{tool} accepted a write with no durable writer injected"
        )
        assert "process-local store is refused" in (refusal.error or "")


def test_no_approval_authority_refuses_before_anything_is_written() -> None:
    """The other way a Hermes update could land unrecorded and ungoverned."""
    adapter = ExpansionToolAdapter()
    refusal = adapter._ready(None, tool_name="runtime.spawn_subagent")
    assert refusal is not None and refusal.ok is False
    assert "no approval authority" in (refusal.error or "")


def _regenerate() -> None:
    """Rewrite the manifest from the code, keeping the readme DEVON wrote."""
    current = manifest() if MANIFEST_PATH.is_file() else {"_readme": []}
    payload = {"_readme": current["_readme"], **live_surface()}
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    _regenerate()
