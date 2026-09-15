"""Read every mirrored row back off the VPS and diff it against the Airtable plan.

The companion to ``airtable_mirror_load``. That script reports what it sent; this
one reports what the instance actually holds, cell by cell, and exits non-zero on
any difference.

It exists because an insert that returns HTTP 200 has told you the request was
accepted, not that the value survived. n8n coerces on ingest: a date-only string in
a ``date`` column came back with the instance timezone stamped on it, which is the
measurement that made every date field a ``string``. A count check would have shown
that load as clean. Green is not correct.

Reads ``N8N_VPS_URL`` and ``N8N_VPS_KEY`` from the environment.

Usage::

    python3 scripts/airtable_mirror_verify.py --plan tqo.json --plan tsws.json \
        --receipt receipt.json --out verify.json
"""

import argparse
import json
import os
import sys
import urllib.request

BASE = os.environ["N8N_VPS_URL"].rstrip("/")
KEY = os.environ["N8N_VPS_KEY"]
SYSTEM = {"id", "createdAt", "updatedAt"}


def get(path):
    req = urllib.request.Request(BASE + path)
    req.add_header("X-N8N-API-KEY", KEY)
    with urllib.request.urlopen(req, timeout=180) as fh:
        return json.loads(fh.read())


def all_rows(table_id):
    rows, cursor = [], None
    while True:
        page = get(f"/api/v1/data-tables/{table_id}/rows?limit=100" + (f"&cursor={cursor}" if cursor else ""))
        rows.extend(page["data"])
        cursor = page.get("nextCursor")
        if not cursor:
            return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", action="append", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    plan = {}
    for path in args.plan:
        for spec in json.load(open(path, encoding="utf-8")):
            plan[spec["table"]] = spec
    receipt = {e["table"]: e for e in json.load(open(args.receipt, encoding="utf-8"))}

    live = {t["name"]: t for t in get("/api/v1/data-tables?limit=100")["data"]}
    problems, checked_cells, checked_rows = [], 0, 0
    report = []

    for name, spec in plan.items():
        entry = receipt.get(name)
        if entry is None:
            problems.append(f"{name}: absent from the load receipt")
            continue
        if name not in live:
            problems.append(f"{name}: data table not present on the VPS")
            continue
        table_id = live[name]["id"]
        if table_id != entry.get("data_table_id"):
            problems.append(f"{name}: receipt id {entry.get('data_table_id')} but live id {table_id}")

        want_cols = {c["name"]: ("string" if c["type"] == "date" else c["type"]) for c in spec["columns"]}
        got_cols = {c["name"]: c["type"] for c in live[name]["columns"]}
        for col, ty in want_cols.items():
            if col not in got_cols:
                problems.append(f"{name}.{col}: column missing on the VPS")
            elif got_cols[col] != ty:
                problems.append(f"{name}.{col}: type {got_cols[col]} on the VPS, planned {ty}")
        for col in got_cols:
            if col not in want_cols:
                problems.append(f"{name}.{col}: extra column on the VPS")

        rows = all_rows(table_id)
        if len(rows) != len(spec["rows"]):
            problems.append(f"{name}: {len(rows)} rows on the VPS, {len(spec['rows'])} in the plan")
        for i, (want, got) in enumerate(zip(spec["rows"], rows, strict=False)):
            checked_rows += 1
            for col in want_cols:
                checked_cells += 1
                a, b = want.get(col), got.get(col)
                if a != b:
                    problems.append(
                        f"{name}[{i}].{col}: airtable {json.dumps(a, ensure_ascii=False)[:90]} "
                        f"!= vps {json.dumps(b, ensure_ascii=False)[:90]}")
        report.append({"table": name, "data_table_id": table_id,
                       "rows": len(rows), "columns": len(got_cols)})

    out = {
        "ok": not problems,
        "tables_checked": len(report),
        "rows_checked": checked_rows,
        "cells_checked": checked_cells,
        "problems": problems,
        "tables": report,
    }
    open(args.out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"tables={len(report)} rows={checked_rows} cells={checked_cells} problems={len(problems)}")
    for p in problems[:25]:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
