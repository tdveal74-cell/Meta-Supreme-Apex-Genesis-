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
import re

EXPORTS = pathlib.Path(__file__).parent / "n8n" / "tqo-v5" / "exports"
README = pathlib.Path(__file__).parent / "n8n" / "tqo-v5" / "README.md"
WORKFLOW_ID = "qEkGOUsNyVaRAmm6"

# Mismatched IF nodes known to exist in the published export. Shrink this the
# moment a fix is published and the export regenerated; never add to it to
# make a test green. Script: Already Written? was the one entry until the fix
# was published as version 3123aef0 on 2026-10-06 and the exports regenerated.
KNOWN_IF_MISMATCH: set[str] = set()


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


ROW = re.compile(r"^\| (active|draft) \| `([0-9a-f]{8})` \| (\d+) nodes \|", re.MULTILINE)


def _readme_rows() -> dict[str, tuple[str, int]]:
    """The README's version table, one row per role, so a count and a version
    id are checked against the export of the same role rather than anywhere in
    the prose."""
    rows = {role: (version, int(count)) for role, version, count in ROW.findall(README.read_text())}
    assert set(rows) == {"active", "draft"}, f"README.md version table rows found: {sorted(rows)}"
    return rows


def test_readme_table_rows_match_the_export_of_the_same_role() -> None:
    rows = _readme_rows()
    for role in ("active", "draft"):
        export = _load(role)
        version, count = rows[role]
        assert version == export["versionId"][:8], (
            f"README.md names {role} as {version}; the export is {export['versionId'][:8]}"
        )
        assert count == len(export["nodes"]), (
            f"README.md says {role} has {count} nodes; the export has {len(export['nodes'])}"
        )


def test_webhook_paths_and_ids_are_redacted() -> None:
    """The Gumroad door carries no authentication, so its path suffix is the
    secret. The exporter strips every webhook path and id; this proves it."""
    for role in ("active", "draft"):
        raw = (EXPORTS / f"{WORKFLOW_ID}_{role}.json").read_text()
        assert "gumroad-sale-" not in raw, f"{role} export carries the Gumroad path"
        for node in _load(role)["nodes"]:
            if node.get("type") == "n8n-nodes-base.webhook":
                assert node["parameters"].get("path") == "redacted", node["name"]
            assert node.get("webhookId", "redacted") == "redacted", node["name"]


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


def test_exports_of_the_same_version_carry_the_same_graph() -> None:
    """The exporter writes both roles from one API read, so equal version ids
    must mean equal nodes and connections; anything else is a hand edit."""
    active, draft = _load("active"), _load("draft")
    if active["versionId"] != draft["versionId"]:
        return
    def by_name(node: dict) -> str:
        return node["name"]

    assert sorted(active["nodes"], key=by_name) == sorted(draft["nodes"], key=by_name), "same version, different nodes"
    assert active["connections"] == draft["connections"], "same version, different connections"


#: The Gemini chat agent lane, disabled on Tee's ruling of 2026-10-06 and
#: published as 36013f35. CREATOR and UPDATER can POST or PUT any workflow on
#: the instance. The nodes stay in the graph until the stage split removes
#: them; until then an export that carries any of them enabled is a regression.
CHAT_AGENT_LANE = (
    "When chat message received",
    "AI Agent",
    "Google Gemini Chat Model",
    "Simple Memory",
    "READER",
    "CREATOR",
    "UPDATER",
)


def test_the_chat_agent_lane_stays_disabled() -> None:
    for role in ("active", "draft"):
        nodes = {node["name"]: node for node in _load(role)["nodes"]}
        for name in CHAT_AGENT_LANE:
            if name in nodes:
                assert nodes[name].get("disabled") is True, f"{role} export: {name} is enabled"


#: The three nodes that hold the writer to the row's approved sources, ruled by
#: Tee 2026-10-07 after row 46 and published as 61d4aeeb, and the NCO Presenter
#: Rule that joined them in d7f4d56f the same day. Each sits on an edge
#: that existed before it, so the test pins both the body and the wiring: a
#: node that drifts from its mirror, or an edge that skips it, is a regression.
SOURCES_NODES = {
    "Sources Rule": ("sources_rule.js", "Build Script Prompt", "NCO Presenter Rule"),
    "NCO Presenter Rule": ("nco_presenter_rule.js", "Sources Rule", "Series Addendum"),
    "Doctor Sources": ("doctor_sources.js", "Build Doctor Prompt", "Token Budget: Doctor"),
    "Sources Gate": ("sources_gate.js", "Script Gate: Quality", "Save Script to Data Table"),
}


def _targets(connections: dict, source: str) -> list[str]:
    outs = connections.get(source, {}).get("main", [])
    return [edge["node"] for branch in outs for edge in (branch or [])]


def test_the_sources_nodes_match_their_mirrors_and_sit_on_their_edges() -> None:
    mirrors = EXPORTS.parent
    for role in ("active", "draft"):
        export = _load(role)
        nodes = {node["name"]: node for node in export["nodes"]}
        for name, (mirror, before, after) in SOURCES_NODES.items():
            assert name in nodes, f"{role} export has no {name}"
            assert nodes[name]["parameters"]["jsCode"] == (mirrors / mirror).read_text(), f"{role}: {name} drifted from {mirror}"
            assert not nodes[name].get("disabled"), f"{role}: {name} is disabled"
            assert _targets(export["connections"], before) == [name], f"{role}: {before} does not feed {name} alone"
            assert _targets(export["connections"], name) == [after], f"{role}: {name} does not feed {after}"


#: The length check after the doctor, ruled by Tee 2026-10-07 after test 2357
#: and published as 83ec66d9. It sits between Parse Doctor Verdict and Fetch
#: Prior Episodes, and Originality Scan and DT Shim: Prior REST read its last
#: node by name, so a script lengthened here is the script every later node
#: measures and saves. Fetch Prior Episodes always outputs, because the first
#: episode of a show has no prior script and the run stopped there in test 2361.
LENGTH_NODES = {
    "Script: Short After Doctor?": "length_after_doctor.js",
    "Parse Expanded After Doctor": "parse_expanded_after_doctor.js",
    "Script: Final Text": "script_final_text.js",
}


def test_the_length_check_after_the_doctor_is_wired_and_mirrored() -> None:
    mirrors = EXPORTS.parent
    for role in ("active", "draft"):
        export = _load(role)
        nodes = {node["name"]: node for node in export["nodes"]}
        conn = export["connections"]
        for name, mirror in LENGTH_NODES.items():
            assert nodes[name]["parameters"]["jsCode"] == (mirrors / mirror).read_text(), f"{role}: {name} drifted from {mirror}"
            assert not nodes[name].get("disabled"), f"{role}: {name} is disabled"
        assert _targets(conn, "Parse Doctor Verdict") == ["Script: Short After Doctor?"], role
        assert _targets(conn, "Script: Short After Doctor?") == ["Expand After Doctor?"], role
        assert conn["Expand After Doctor?"]["main"][0][0]["node"] == "Expand After Doctor (Cerebras)", role
        assert conn["Expand After Doctor?"]["main"][1][0]["node"] == "Script: Final Text", role
        assert _targets(conn, "Expand After Doctor (Cerebras)") == ["Parse Expanded After Doctor"], role
        assert _targets(conn, "Parse Expanded After Doctor") == ["Script: Final Text"], role
        assert _targets(conn, "Script: Final Text") == ["Fetch Prior Episodes"], role
        cond = nodes["Expand After Doctor?"]["parameters"]["conditions"]
        assert cond["options"]["typeValidation"] == "strict", role
        (only,) = cond["conditions"]
        assert only["leftValue"] == "={{ $json.needsExpansion3 }}", role
        assert only["operator"] == {"operation": "true", "singleValue": True, "type": "boolean"}, role
        assert nodes["Fetch Prior Episodes"].get("alwaysOutputData") is True, role
        for reader in ("Originality Scan", "DT Shim: Prior REST"):
            code = nodes[reader]["parameters"]["jsCode"]
            assert "$('Script: Final Text')" in code and "$('Parse Doctor Verdict')" not in code, f"{role}: {reader}"
        assert nodes["Build Script Prompt"]["parameters"]["jsCode"] == (mirrors / "build_script_prompt.js").read_text(), role
