"""The Data Table name-to-id conversion, proven on the shapes it actually met.

Tee ruled on 2026-09-16 to convert TQO FINAL V5's thirty one name mode Data
Table locators to id mode, because a name is capturable by any other table name
that contains it and an id is not. ``scripts/n8n_table_id_conversion.py`` does
the conversion; this proves it on every shape that is really in that workflow,
and proves its audit bites on the one miss that got past a first reading.

The conversion is additive on purpose: ``tableId`` and ``__table`` keep their
values, a new ``tableRef`` and ``__tableRef`` carry the id, and only the
locators move. A node the transform misses keeps working on the old path, and a
locator pointed at a ref nobody set fails loudly instead of returning zero rows.
Silence is what made the original incident cost four and a half hours.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

_SPEC = importlib.util.spec_from_file_location(
    "n8n_table_id_conversion",
    pathlib.Path(__file__).parent / "scripts" / "n8n_table_id_conversion.py",
)
conversion = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(conversion)

TQO = "2GtmrFcTNqVMbddh"
NCO = "DSH1tn4TZjzAEKxp"
EXEMPLARS = "k3A66wV0vUoeaElo"


def _code_node(name: str, js: str) -> dict:
    return {
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "parameters": {"jsCode": js, "mode": "runOnceForAllItems"},
    }


def _locator(name: str, value: str) -> dict:
    return {
        "name": name,
        "type": "n8n-nodes-base.dataTable",
        "typeVersion": 1.1,
        "parameters": {
            "operation": "get",
            "resource": "row",
            "dataTableId": {"__rl": True, "mode": "name", "value": value},
        },
    }


def _workflow(nodes: list[dict]) -> dict:
    return {"name": "fixture", "nodes": nodes, "connections": {}}


def test_a_literal_name_becomes_that_table_s_id():
    wf = _workflow(
        [
            _locator("Analytics: Fetch TQO Published", "tqo_content"),
            _locator("Analytics: Fetch NCO Published", "nco_content"),
            _locator("Fetch Script Exemplars", "script_exemplars"),
        ]
    )
    conversion.convert(wf)
    got = {n["name"]: n["parameters"]["dataTableId"] for n in wf["nodes"]}
    assert got["Analytics: Fetch TQO Published"] == {"__rl": True, "mode": "id", "value": TQO}
    assert got["Analytics: Fetch NCO Published"] == {"__rl": True, "mode": "id", "value": NCO}
    assert got["Fetch Script Exemplars"] == {"__rl": True, "mode": "id", "value": EXEMPLARS}


def test_a_show_context_mints_a_ref_without_disturbing_the_name():
    """The old field keeps its old value. That is what makes a miss survivable."""
    wf = _workflow(
        [
            _code_node(
                "Show Context: Script",
                "return [{ json: nco ? {\n"
                "  show: 'NCO', channel: 'NCO Forge', tableId: 'nco_content',\n"
                "} : {\n"
                "  show: 'TQO', channel: 'The Quiet Operator', tableId: 'tqo_content',\n"
                "} }];",
            ),
            _locator("Get Idea Rows", "={{ $('Show Context: Script').first().json.tableId }}"),
        ]
    )
    conversion.convert(wf)
    js = wf["nodes"][0]["parameters"]["jsCode"]
    assert f"tableId: 'nco_content', tableRef: '{NCO}'," in js
    assert f"tableId: 'tqo_content', tableRef: '{TQO}'," in js

    locator = wf["nodes"][1]["parameters"]["dataTableId"]
    assert locator["mode"] == "id"
    assert locator["value"] == "={{ $('Show Context: Script').first().json.tableRef }}"


def test_the_unpacker_hands_the_ref_on_beside_the_name():
    wf = _workflow(
        [
            _code_node(
                "DT Unpack: Ideas",
                "const out=[];for(const it of $input.all()){const j=it.json||{};"
                "for(const r of recs){out.push({json:{__table:j.tableId,__id:r.id}});}}return out;",
            ),
            _locator("Ideas: Upsert", "={{ $json.__table }}"),
        ]
    )
    conversion.convert(wf)
    assert "__table:j.tableId,__tableRef:j.tableRef," in wf["nodes"][0]["parameters"]["jsCode"]
    assert wf["nodes"][1]["parameters"]["dataTableId"] == {
        "__rl": True,
        "mode": "id",
        "value": "={{ $json.__tableRef }}",
    }


def test_the_other_brand_lock_keeps_its_inversion():
    """Render Lock deliberately reads the OTHER show's table. Order must hold."""
    wf = _workflow(
        [
            _locator(
                "Render Lock: Other Brand",
                "={{ $('Show Context: Render').first().json.show === 'NCO'"
                " ? 'tqo_content' : 'nco_content' }}",
            )
        ]
    )
    conversion.convert(wf)
    value = wf["nodes"][0]["parameters"]["dataTableId"]["value"]
    assert value == (
        "={{ $('Show Context: Render').first().json.show === 'NCO'"
        f" ? '{TQO}' : '{NCO}' }}}}"
    ), value


def test_a_locator_the_transform_does_not_understand_is_left_and_named():
    """An unrecognised expression must stay on name mode and be reported."""
    wf = _workflow([_locator("Mystery", "={{ $json.somethingElse }}")])
    report = conversion.convert(wf)
    assert wf["nodes"][0]["parameters"]["dataTableId"]["mode"] == "name"
    assert any("UNCONVERTED" in line for line in report)


def test_the_audit_catches_a_ref_dropped_by_a_rebuild():
    """The real miss: a ref minted at the top and lost in a closing map.

    Winner: Build Re-expansion pushed rows carrying tableRef and then rebuilt
    its output with `rows.map(r => ({ json: { tableId: r.tableId, body: ...`,
    forwarding the name alone. The locator downstream would have resolved
    undefined. A first reading of the conversion report did not show this,
    because the report says what was CHANGED, not what survives to the edge.
    """
    dropped = _workflow(
        [
            _code_node(
                "Winner: Build Re-expansion",
                "const TQO = 'tqo_content', NCO = 'nco_content';\n"
                "const TQO_REF = 'x', NCO_REF = 'y';\n"
                "rows.push({ tableId: isNCO ? NCO : TQO, tableRef: isNCO ? NCO_REF : TQO_REF });\n"
                "return rows.map(r => ({ json: { tableId: r.tableId, body: {} } }));",
            )
        ]
    )
    problems = conversion.audit(dropped)
    assert len(problems) == 1
    assert "Winner: Build Re-expansion" in problems[0]
    assert "line 4" in problems[0], problems[0]

    kept = json.loads(json.dumps(dropped))
    kept["nodes"][0]["parameters"]["jsCode"] = kept["nodes"][0]["parameters"]["jsCode"].replace(
        "tableId: r.tableId, body:", "tableId: r.tableId, tableRef: r.tableRef, body:"
    )
    assert conversion.audit(kept) == []


def test_the_script_refuses_a_partial_conversion(tmp_path):
    """Exit 1 on a survivor. A half converted lane looks finished and is not."""
    workflow = tmp_path / "wf.json"
    workflow.write_text(json.dumps(_workflow([_locator("Mystery", "={{ $json.nope }}")])))
    done = subprocess.run(
        [sys.executable, "scripts/n8n_table_id_conversion.py", str(workflow)],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).parent,
    )
    assert done.returncode == 1, done.stdout
    assert "STILL ON NAME MODE" in done.stderr


def test_a_clean_conversion_exits_zero(tmp_path):
    workflow = tmp_path / "wf.json"
    workflow.write_text(json.dumps(_workflow([_locator("Literal", "tqo_content")])))
    done = subprocess.run(
        [sys.executable, "scripts/n8n_table_id_conversion.py", str(workflow)],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).parent,
    )
    assert done.returncode == 0, done.stderr
    assert "0 name mode locators left" in done.stdout
