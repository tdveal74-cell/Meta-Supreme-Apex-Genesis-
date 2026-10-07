"""TQO Research, read from its record rather than described.

``n8n/tqo-research/workflow.json`` is the active version of TQO Research
(``0zLNB34UOOTq6mck``) as it was read back after the publish on 2026-10-07,
and the ``.js`` files beside it are its Code node bodies, named after the
nodes in snake case. This module fails when a body drifts from its record, and
it pins the two promises the stage makes about the row: it writes only the
``sources`` and ``research_note`` columns, never ``status``, and it reads only
locked Idea rows. The behaviour of the bodies is tested by
``n8n/tqo-research/research.test.mjs`` in the standalone job.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent / "n8n" / "tqo-research"
RECORD = json.loads((HERE / "workflow.json").read_text())
NODES = {node["name"]: node for node in RECORD["nodes"]}

MIRRORS = {
    "Credit Floor": "credit_floor.js",
    "Rows Needing Sources": "rows_needing_sources.js",
    "Build Extract Prompt": "build_extract_prompt.js",
    "Quote Check": "quote_check.js",
    "Build Doctor Prompt": "build_doctor_prompt.js",
    "Compose Approved Sources": "compose_approved_sources.js",
}


def test_the_record_names_the_workflow_and_a_published_version() -> None:
    assert RECORD["workflowId"] == "0zLNB34UOOTq6mck"
    assert RECORD["active"] is True
    assert RECORD["versionId"]


def test_every_code_node_matches_its_mirror_and_every_mirror_has_a_node() -> None:
    code_nodes = {name for name, node in NODES.items() if node["type"] == "n8n-nodes-base.code"}
    assert code_nodes == set(MIRRORS)
    for name, mirror in MIRRORS.items():
        assert NODES[name]["parameters"]["jsCode"] == (HERE / mirror).read_text(), f"{name} drifted from {mirror}"
    on_disk = {path.name for path in HERE.glob("*.js")}
    assert on_disk == set(MIRRORS.values())


def test_the_stage_writes_sources_and_a_note_and_never_the_status() -> None:
    writes = [node for node in NODES.values() if node["type"] == "n8n-nodes-base.dataTable" and node["parameters"].get("operation") == "update"]
    assert len(writes) == 1
    columns = writes[0]["parameters"]["columns"]["value"]
    assert set(columns) == {"sources", "research_note"}


def test_it_runs_daily_at_0940_utc_and_alarms_through_the_shared_handler() -> None:
    schedules = [node for node in NODES.values() if node["type"] == "n8n-nodes-base.scheduleTrigger"]
    assert len(schedules) == 1
    assert schedules[0]["parameters"]["rule"]["interval"] == [{"field": "cronExpression", "expression": "40 9 * * *"}]
    assert RECORD["settings"]["timezone"] == "Etc/UTC"
    assert RECORD["settings"]["errorWorkflow"] == "GbeNilHQzjmoWDz3"


def test_the_balance_is_read_before_any_row_is() -> None:
    edges = {src: [e["node"] for branch in v.get("main", []) for e in (branch or [])] for src, v in RECORD["connections"].items()}
    assert edges["Firecrawl Balance"] == ["Credit Floor"]
    assert edges["Credit Floor"] == ["Get Idea Rows"]
    for trigger in ("Run Research by Hand", "Daily 09:40Z Research"):
        assert edges[trigger] == ["Firecrawl Balance"]
