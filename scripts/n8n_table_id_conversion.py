#!/usr/bin/env python3
"""Convert TQO FINAL V5's Data Table locators from NAME mode to ID mode.

WHY THIS EXISTS

A Data Table resolved in NAME mode is only as stable as every OTHER table name
in the project, because a new name that merely CONTAINS an existing one captures
it. On 2026-09-15 at 23:38Z that happened and the TQO lane found no work for
four and a half hours without failing. Tee ruled the instance fix on 2026-09-16
(rename the longer table) and ruled the durable fix on the same day: resolve by
id, which cannot be captured because ids are unique and immutable.

WHY IT IS NOT A FIND AND REPLACE

Only four of V5's thirty one name mode locators carry a literal table name. The
other twenty seven compute one at run time from a field called ``tableId`` that
holds a NAME, set by the five ``Show Context: *`` nodes and carried onward by
five ``DT Unpack: *`` nodes as ``__table``. Converting the locators alone would
point id mode at a name and every one of them would refuse.

So the conversion is ADDITIVE, and deliberately so. ``tableId`` and ``__table``
keep their current values and their current meaning; a new ``tableRef`` and
``__tableRef`` carry the id alongside them, and only the locators move. Nothing
that reads the old fields changes. A node this transform MISSES therefore keeps
working on the old path instead of breaking, and a locator pointed at a
``tableRef`` that nobody set fails loudly rather than returning zero rows, which
is the exact failure mode that made the original incident invisible.

WHAT IS PROVEN BEFORE THIS RUNS

Two things, both measured on 2026-09-16 rather than assumed:

  * id mode evaluates an expression. Execution 268 of the throwaway probe
    2RQX9mrwJTvqGATQ read tqo_content three ways, id via expression, id literal
    and name via expression, and all three returned the same 40 rows.
  * id mode does not fall back to name resolution. Saving a locator with
    mode id and value ``tqo_content`` is REFUSED by n8n at save time: "data
    table with id 'tqo_content' not found". That refusal is what makes this a
    real fix rather than a cosmetic one.

USAGE

    python3 scripts/n8n_table_id_conversion.py <workflow.json> [--out FILE]

Reads an exported workflow, writes the converted workflow, and prints one line
per change. Exit 1 if any name mode locator survives the pass, because a
partial conversion is the one outcome worse than none: it looks done.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

# Read from search_data_tables on project qbrcjkbIoorbwot6, 2026-09-16.
TABLE_IDS = {
    "tqo_content": "2GtmrFcTNqVMbddh",
    "nco_content": "DSH1tn4TZjzAEKxp",
    "script_exemplars": "k3A66wV0vUoeaElo",
}

TQO, NCO = TABLE_IDS["tqo_content"], TABLE_IDS["nco_content"]

#: Code nodes that MINT the table reference. Each gains ``tableRef`` beside the
#: existing ``tableId`` rather than changing it.
SHOW_CONTEXT = (
    "Show Context: Script",
    "Show Context: Promote",
    "Show Context: Render",
    "Show Context: Publish",
    "Show Context: Brief",
)

#: Code nodes that CARRY a reference minted upstream, as ``ctx.tableId``.
CARRIERS = (
    "Family: Assign IDs",
    "Reaper: Build Release",
    "Short Engine: Build Rows",
    "Script: Fill Run Fields",
    "Render: Release Claim",
)

#: Code nodes that pick a table from a local pair of name constants.
LOCAL_PAIR = ("Winner: Build Re-expansion", "Signals: Recurrence Check")

#: Code nodes that flatten rows and hand the reference on as ``__table``.
UNPACKERS = (
    "DT Unpack: Reaper",
    "DT Unpack: Render",
    "DT Unpack: Script",
    "DT Unpack: Ideas",
    "DT Unpack: Short Engine",
)


def _code(node: dict[str, Any]) -> str:
    return (node.get("parameters") or {}).get("jsCode") or ""


def _set_code(node: dict[str, Any], code: str) -> None:
    node["parameters"]["jsCode"] = code


def convert(workflow: dict[str, Any]) -> list[str]:
    """Convert in place. Returns one report line per change made."""
    report: list[str] = []
    by_name = {n["name"]: n for n in workflow.get("nodes", [])}

    def note(node_name: str, what: str) -> None:
        report.append(f"{node_name}: {what}")

    # 1. The minters. `tableId: 'tqo_content',` gains `tableRef: '<id>',`.
    for name in SHOW_CONTEXT:
        node = by_name.get(name)
        if node is None:
            note(name, "MISSING from this workflow, skipped")
            continue
        code = _code(node)
        before = code
        for table, ident in (("tqo_content", TQO), ("nco_content", NCO)):
            code = re.sub(
                r"tableId: '" + table + r"',",
                f"tableId: '{table}', tableRef: '{ident}',",
                code,
            )
        if code != before:
            _set_code(node, code)
            note(name, f"minted tableRef ({before.count('tableId:')} sites)")

    # 2. The carriers. `tableId: ctx.tableId,` gains `tableRef: ctx.tableRef,`.
    for name in CARRIERS:
        node = by_name.get(name)
        if node is None:
            note(name, "MISSING from this workflow, skipped")
            continue
        code = _code(node)
        if "tableRef: ctx.tableRef" in code:
            continue
        # Match the indentation of the line being followed. These are live
        # production bodies and a two space line inside a four space object
        # is the kind of thing a reader trips over for no reason.
        new = re.sub(
            r"([ \t]*)tableId: ctx\.tableId,",
            lambda m: f"{m.group(1)}tableId: ctx.tableId,\n{m.group(1)}tableRef: ctx.tableRef,",
            code,
        )
        if new != code:
            _set_code(node, new)
            note(name, "carried tableRef from ctx")

    # 3. The local pairs. A second pair of constants, chosen by the same test.
    for name in LOCAL_PAIR:
        node = by_name.get(name)
        if node is None:
            note(name, "MISSING from this workflow, skipped")
            continue
        code = _code(node)
        new = code.replace(
            "const TQO = 'tqo_content', NCO = 'nco_content';",
            "const TQO = 'tqo_content', NCO = 'nco_content';\n"
            f"const TQO_REF = '{TQO}', NCO_REF = '{NCO}';",
        ).replace(
            "tableId: isNCO ? NCO : TQO,",
            "tableId: isNCO ? NCO : TQO, tableRef: isNCO ? NCO_REF : TQO_REF,",
        ).replace(
            # Winner rebuilds its items in a final map that forwarded tableId
            # alone, so the ref minted above was dropped before the unpacker
            # ever saw it. Caught by reading the converted body; _audit below
            # is what stops the next one of these reaching a live workflow.
            "return rows.map(r => ({ json: { tableId: r.tableId, body: {",
            "return rows.map(r => ({ json: { tableId: r.tableId, tableRef: r.tableRef, body: {",
        )
        if new != code:
            _set_code(node, new)
            note(name, "added a parallel pair of id constants")

    # 4. The unpackers. `__table` gains `__tableRef` beside it.
    for name in UNPACKERS:
        node = by_name.get(name)
        if node is None:
            note(name, "MISSING from this workflow, skipped")
            continue
        code = _code(node)
        new = code.replace("__table:j.tableId,", "__table:j.tableId,__tableRef:j.tableRef,")
        if new != code:
            _set_code(node, new)
            note(name, "carried __tableRef beside __table")

    # 5. The locators themselves, and only now.
    for node in workflow.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.dataTable":
            continue
        rl = (node.get("parameters") or {}).get("dataTableId")
        if not isinstance(rl, dict) or rl.get("mode") != "name":
            continue
        value = rl.get("value") or ""
        new_value = None

        if value in TABLE_IDS:                       # a bare literal name
            new_value = TABLE_IDS[value]
        elif ".json.tableId }}" in value:            # minted or carried upstream
            new_value = value.replace(".json.tableId }}", ".json.tableRef }}")
        elif "$json.__table }}" in value:            # handed on by an unpacker
            new_value = value.replace("$json.__table }}", "$json.__tableRef }}")
        elif "'tqo_content' : 'nco_content'" in value:  # the other-brand lock
            new_value = value.replace(
                "'tqo_content' : 'nco_content'", f"'{TQO}' : '{NCO}'"
            )

        if new_value is None:
            report.append(f"{node['name']}: UNCONVERTED, value {value!r}")
            continue

        rl["mode"] = "id"
        rl["value"] = new_value
        rl.pop("cachedResultName", None)
        report.append(f"{node['name']}: locator -> id mode, {new_value!r}")

    return report


def audit(workflow: dict[str, Any]) -> list[str]:
    """Every place that emits a table reference must emit BOTH, or neither.

    The conversion is additive, so a node that still emits ``tableId`` without
    a ``tableRef`` beside it is a node whose downstream locator will resolve
    ``undefined``. That is loud rather than silent, which is the point, but it
    is still a broken lane and it must never reach a live workflow.

    This fires on exactly the miss it was written for: ``Winner: Build
    Re-expansion`` minted a ref at the top and then rebuilt its items in a
    final ``rows.map`` that forwarded ``tableId`` alone.
    """
    problems: list[str] = []
    emitters = set(SHOW_CONTEXT) | set(CARRIERS) | set(LOCAL_PAIR)
    for node in workflow.get("nodes", []):
        if node["name"] not in emitters:
            continue
        code = _code(node)
        for match in re.finditer(r"tableId:", code):
            window = code[match.start() : match.start() + 70]
            if "tableRef" not in window:
                line = code[: match.start()].count("\n") + 1
                problems.append(
                    f"{node['name']} line {line}: emits tableId with no tableRef beside it"
                )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workflow", help="exported workflow JSON")
    ap.add_argument("--out", help="where to write the converted workflow")
    args = ap.parse_args()

    with open(args.workflow) as handle:
        workflow = json.load(handle)

    report = convert(workflow)
    for line in report:
        print(line)

    problems = audit(workflow)
    for problem in problems:
        print(f"AUDIT: {problem}", file=sys.stderr)

    survivors = [
        n["name"]
        for n in workflow.get("nodes", [])
        if n.get("type") == "n8n-nodes-base.dataTable"
        and isinstance((n.get("parameters") or {}).get("dataTableId"), dict)
        and n["parameters"]["dataTableId"].get("mode") == "name"
    ]
    print(f"\n{len(report)} changes; {len(survivors)} name mode locators left")

    if args.out:
        with open(args.out, "w") as handle:
            json.dump(workflow, handle, indent=2)
        print(f"wrote {args.out}")

    if survivors:
        print("STILL ON NAME MODE: " + ", ".join(survivors), file=sys.stderr)
        return 1
    if problems:
        print(f"{len(problems)} emitter(s) carry tableId with no tableRef", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
