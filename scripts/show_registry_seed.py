"""Seed and read back the `show_registry` and `show_series` data tables.

The tables on the n8n instance are the registry a stage workflow reads
instead of a `Show Context` Code node, and `services/devon/show_registry.py`
is their source. This script moves rows in one direction only, module to
table, and proves the table by reading it back and diffing it against the
module, so a seed that silently wrote nothing cannot read as done.

    python3 scripts/show_registry_seed.py --check          # read back, diff, exit 1 on drift
    python3 scripts/show_registry_seed.py --seed           # insert the rows the table lacks, then check
    python3 scripts/show_registry_seed.py --seed --dry-run # say what would be inserted

It needs `N8N_VPS_URL` and `N8N_VPS_KEY` in the environment, the same pair
the two GitHub Actions watchdogs use, and it never deletes or updates a row:
a row whose values drifted from the module is reported, not rewritten,
because which side is right is a ruling rather than a script's call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.devon.show_registry import REGISTRY_TABLES, registry_rows, series_rows  # noqa: E402

SYSTEM_COLUMNS = {"id", "createdAt", "updatedAt"}
#: Which columns identify a row in each table.
ROW_KEYS = {"show_registry": ("key",), "show_series": ("show", "key")}


def _api(path: str, method: str = "GET", body: object = None) -> object:
    base = os.environ.get("N8N_VPS_URL", "").rstrip("/")
    key = os.environ.get("N8N_VPS_KEY", "")
    if not base or not key:
        raise SystemExit("N8N_VPS_URL and N8N_VPS_KEY are required")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/api/v1{path}",
        data=data,
        method=method,
        headers={"X-N8N-API-KEY": key, "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> HTTP {error.code}: {detail[:500]}") from None


def read_rows(table_id: str) -> List[Dict[str, object]]:
    """Every row, following the endpoint's `nextCursor` until it runs out."""
    rows: List[Dict[str, object]] = []
    query: Dict[str, object] = {"limit": 100}
    while True:
        page = _api(f"/data-tables/{table_id}/rows?{urllib.parse.urlencode(query)}")
        if not isinstance(page, dict):
            raise SystemExit(f"unexpected rows payload for {table_id}: {str(page)[:200]}")
        rows.extend(page.get("data", []))
        cursor = page.get("nextCursor")
        if not cursor or not page.get("data"):
            return rows
        query["cursor"] = cursor


def insert_rows(table_id: str, rows: List[Dict[str, object]]) -> object:
    """POST on the rows route is the insert; the instance's OpenAPI spec names it."""
    return _api(f"/data-tables/{table_id}/rows", "POST", {"data": rows, "returnType": "count"})


def _identity(table: str, row: Dict[str, object]) -> Tuple[object, ...]:
    return tuple(row.get(column) for column in ROW_KEYS[table])


def expected(table: str) -> List[Dict[str, object]]:
    return list(registry_rows() if table == "show_registry" else series_rows())


def diff(table: str, live: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], List[str]]:
    """Rows the table lacks, and one line per row or value that disagrees."""
    wanted = {_identity(table, row): row for row in expected(table)}
    found: Dict[Tuple[object, ...], Dict[str, object]] = {}
    problems: List[str] = []
    for row in live:
        identity = _identity(table, row)
        if identity in found:
            problems.append(f"{table}: duplicate row {identity}")
        found[identity] = row
    for identity, row in found.items():
        if identity not in wanted:
            problems.append(f"{table}: row {identity} is in the table and not in the module")
            continue
        for column, value in wanted[identity].items():
            live_value = row.get(column)
            if live_value != value:
                problems.append(f"{table}: {identity} {column}: table {live_value!r}, module {value!r}")
        extra = set(row) - set(wanted[identity]) - SYSTEM_COLUMNS
        if extra:
            problems.append(f"{table}: {identity} carries columns the module does not: {sorted(extra)}")
    missing = [row for identity, row in wanted.items() if identity not in found]
    return missing, problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", action="store_true", help="insert the rows the tables lack")
    parser.add_argument("--check", action="store_true", help="read the tables back and diff them against the module")
    parser.add_argument("--dry-run", action="store_true", help="with --seed, print the rows instead of inserting them")
    args = parser.parse_args(argv)
    if not (args.seed or args.check):
        parser.error("pass --seed, --check or both")
    clean = True
    for table, table_id in REGISTRY_TABLES.items():
        live = read_rows(table_id)
        missing, problems = diff(table, live)
        if args.seed and missing:
            if args.dry_run:
                print(f"{table} ({table_id}): would insert {len(missing)} rows")
                for row in missing:
                    print("  ", json.dumps(row, ensure_ascii=False)[:160])
            else:
                result = insert_rows(table_id, missing)
                print(f"{table} ({table_id}): inserted {len(missing)} rows -> {json.dumps(result)[:200]}")
                live = read_rows(table_id)
                missing, problems = diff(table, live)
        for line in problems:
            print(line)
        if missing:
            print(f"{table} ({table_id}): {len(missing)} rows missing: {[_identity(table, row) for row in missing]}")
        clean = clean and not missing and not problems
        print(f"{table} ({table_id}): {len(live)} rows read back, {len(expected(table))} expected, {'CLEAN' if not missing and not problems else 'DRIFT'}")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
