"""Apply an ``airtable_mirror`` plan to the n8n VPS: create the tables, insert the rows.

``airtable_mirror.py`` produces the plan; this applies it. It talks to the n8n
public REST API directly rather than through a connector, because the rows run to
about two megabytes and retyping them through a tool call is both slow and a chance
to corrupt a script body.

Resume safe by design. A table that already carries N rows is topped up from plan
row N onward, so an interrupted run is finished rather than duplicated. That only
holds because rows are inserted in plan order and nothing else writes these tables.

Reads ``N8N_VPS_URL`` and ``N8N_VPS_KEY`` from the environment. The key is never
logged, never written to the receipt, and never enters the repository.

Usage::

    python3 scripts/airtable_mirror_load.py --plan tqo.json --plan tsws.json \
        --receipt receipt.json [--dry-run]

The receipt it writes is the input to ``airtable_mirror_verify.py``, which is the
step that actually proves the load. This script reporting its own row counts is a
claim; the verifier reading every cell back is the result.
"""

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ["N8N_VPS_URL"].rstrip("/")
KEY = os.environ["N8N_VPS_KEY"]
PROJECT = "qbrcjkbIoorbwot6"
MAX_BYTES = 500_000
MAX_ROWS = 200


def call(method, path, body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(BASE + path, data=data, method=method)
        req.add_header("X-N8N-API-KEY", KEY)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=180) as fh:
                raw = fh.read()
            return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:400]
            if exc.code < 500:
                raise SystemExit(f"{method} {path} -> {exc.code} {detail}") from exc
            last = f"{exc.code} {detail}"
        except Exception as exc:  # noqa: BLE001 - transport errors are retried
            last = repr(exc)
        time.sleep(2 ** attempt)
    raise SystemExit(f"{method} {path} failed after {tries}: {last}")


def existing_tables():
    out = {}
    cursor = None
    while True:
        path = "/api/v1/data-tables?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = call("GET", path)
        for table in page["data"]:
            out[table["name"]] = table
        cursor = page.get("nextCursor")
        if not cursor:
            return out


def row_count(table_id):
    page = call("GET", f"/api/v1/data-tables/{table_id}/rows?limit=1")
    if isinstance(page, dict) and "count" in page:
        return page["count"]
    total = 0
    cursor = None
    while True:
        path = f"/api/v1/data-tables/{table_id}/rows?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = call("GET", path)
        total += len(page["data"])
        cursor = page.get("nextCursor")
        if not cursor:
            return total


def batches(rows):
    batch, size = [], 0
    for row in rows:
        blob = len(json.dumps(row, ensure_ascii=False))
        if batch and (size + blob > MAX_BYTES or len(batch) >= MAX_ROWS):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += blob
    if batch:
        yield batch


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", action="append", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = []
    for path in args.plan:
        plan.extend(json.load(open(path, encoding="utf-8")))

    live = existing_tables()
    receipt = []
    for spec in plan:
        name = spec["table"]
        columns = [
            {"name": c["name"], "type": ("string" if c["type"] == "date" else c["type"])}
            for c in spec["columns"]
        ]
        retyped = [c["name"] for c in spec["columns"] if c["type"] == "date"]
        rows = spec["rows"]
        entry = {
            "table": name,
            "airtable_table_id": spec["airtable_table_id"],
            "airtable_table_name": spec["airtable_table_name"],
            "columns": len(columns),
            "date_columns_stored_as_string": retyped,
            "rows_planned": len(rows),
        }

        if args.dry_run:
            entry["would"] = "create" if name not in live else "reuse"
            entry["batches"] = len(list(batches(rows)))
            receipt.append(entry)
            print(f"  {name:36s} {entry['would']:6s} cols={len(columns):3d} rows={len(rows):4d} batches={entry['batches']}")
            continue

        if name in live:
            table_id = live[name]["id"]
            entry["created"] = False
        else:
            made = call("POST", "/api/v1/data-tables",
                        {"name": name, "projectId": PROJECT, "columns": columns})
            table_id = made["id"]
            entry["created"] = True
        entry["data_table_id"] = table_id

        already = row_count(table_id)
        entry["rows_before"] = already
        todo = rows[already:]
        sent = 0
        for batch in batches(todo):
            call("POST", f"/api/v1/data-tables/{table_id}/rows", {"data": batch})
            sent += len(batch)
        entry["rows_inserted"] = sent
        entry["rows_after"] = row_count(table_id)
        entry["ok"] = entry["rows_after"] == len(rows)
        receipt.append(entry)
        flag = "ok " if entry["ok"] else "BAD"
        print(f"  {flag} {name:36s} id={table_id} cols={len(columns):3d} "
              f"before={already:4d} inserted={sent:4d} after={entry['rows_after']:4d} want={len(rows):4d}")

    pathlib.Path(args.receipt).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [e for e in receipt if not args.dry_run and not e.get("ok")]
    print(f"\ntables={len(receipt)} rows={sum(e['rows_planned'] for e in receipt)} "
          f"mismatched={len(bad)} receipt={args.receipt}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
