"""The two exported versions of TQO FINAL V5 are read, not described.

``n8n/tqo-v5/exports/`` holds the published version and the draft of the
workflow as ``scripts/tqo_v5_export.py`` wrote them. The README beside them
cites node counts; this module computes the counts from the files and fails
when the prose drifts, which is the only reason those numbers can be trusted.

It also records one defect by name. An IF node at typeVersion 1 whose
``conditions`` carry the version 2 shape (``combinator`` plus a list) is read
by the engine as a node with no conditions at all, and IF v1 routes every
item to its TRUE output when there is nothing to test. ``Script: Already
Written?`` carried exactly that on 2026-10-06, so every locked content row
would reach ``Script: Hydrate from Row``, which throws on an empty script.
The allowlist below names it. One test fails if a new mismatch appears; the
other fails once the named node is fixed and re-exported but still listed,
so the list can only shrink.
"""

from __future__ import annotations

import json
import pathlib

EXPORTS = pathlib.Path(__file__).parent / "n8n" / "tqo-v5" / "exports"
README = pathlib.Path(__file__).parent / "n8n" / "tqo-v5" / "README.md"
WORKFLOW_ID = "qEkGOUsNyVaRAmm6"

# Mismatched IF nodes known to exist in the published export. Shrink this the
# moment a fix is published and the export regenerated; never add to it to
# make a test green.
KNOWN_IF_MISMATCH = {"Script: Already Written?"}


def _load(role: str) -> dict:
    return json.loads((EXPORTS / f"{WORKFLOW_ID}_{role}.json").read_text())


def _if_mismatches(nodes: list[dict]) -> set[str]:
    found = set()
    for node in nodes:
        if node.get("type") != "n8n-nodes-base.if":
            continue
        conditions = node.get("parameters", {}).get("conditions")
        v2_shape = isinstance(conditions, dict) and "combinator" in conditions
        if node.get("typeVersion") == 1 and v2_shape:
            found.add(node["name"])
    return found


def test_both_exports_name_the_workflow_and_their_role() -> None:
    for role in ("active", "draft"):
        export = _load(role)
        assert export["workflowId"] == WORKFLOW_ID
        assert export["role"] == role
        assert export["versionId"], f"{role} export carries no versionId"
        assert export["nodes"] and isinstance(export["connections"], dict)


def test_readme_counts_are_the_exports_counts() -> None:
    text = README.read_text()
    for role in ("active", "draft"):
        export = _load(role)
        cited = f"{len(export['nodes'])} nodes"
        assert cited in text, (
            f"README.md does not cite '{cited}' for the {role} export; "
            "regenerate the exports and copy the count the script prints"
        )
        assert export["versionId"][:8] in text, (
            f"README.md does not name the {role} version {export['versionId'][:8]}"
        )


def test_no_if_node_carries_a_shape_its_version_cannot_read() -> None:
    for role in ("active", "draft"):
        unexpected = _if_mismatches(_load(role)["nodes"]) - KNOWN_IF_MISMATCH
        assert not unexpected, (
            f"{role} export: IF nodes at typeVersion 1 carrying version 2 conditions: "
            f"{sorted(unexpected)}. The engine reads them as having no conditions and "
            "routes every item to TRUE. Retype the node, do not add it to the allowlist"
        )


def test_the_known_mismatch_list_only_shrinks() -> None:
    still_broken = _if_mismatches(_load("active")["nodes"])
    stale = KNOWN_IF_MISMATCH - still_broken
    assert not stale, (
        f"{sorted(stale)} no longer mismatch in the published export; "
        "remove them from KNOWN_IF_MISMATCH"
    )
