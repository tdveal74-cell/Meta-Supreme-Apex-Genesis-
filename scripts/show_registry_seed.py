"""Seed and read back the `show_registry` and `show_series` data tables.

The tables on the n8n instance are the registry a stage workflow reads
instead of a `Show Context` Code node, and `services/devon/show_registry.py`
is their source. This script moves rows in one direction only, module to
table, and proves the table by reading it back and diffing it against the
module, so a seed that silently wrote nothing cannot read as done.

    python3 scripts/show_registry_seed.py --check          # read back, diff, exit 1 on drift
    python3 scripts/show_registry_seed.py --seed           # insert the rows the table lacks, then check
    python3 scripts/show_registry_seed.py --seed --dry-run # say what would be inserted
    python3 scripts/show_registry_seed.py --spec           # print the create payload derived from the module

It needs `N8N_VPS_KEY` in the environment, the secret the two GitHub Actions
watchdogs use, and reads `N8N_VPS_URL` with the same default they fall back
to, and it never deletes or updates a row:
a row whose values drifted from the module is reported, not rewritten,
because which side is right is a ruling rather than a script's call. For the
same reason `--seed` inserts nothing into a table whose diff reports any
problem, a drifted value, a duplicate, a stranger or an extra column: it
prints the problems, refuses, and exits 1.

Before any insert it reads the table's own definition and refuses when the
table's name is not the `REGISTRY_TABLES` key or its column set is not the
module's row keys, because the id in that dict is the only thing that aims
the POST, and a stale or edited id would otherwise read some other table,
find every module row missing, and write into it.
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
#: The instance the watchdogs default to, scripts/pulse_watchdog.py line 108.
DEFAULT_BASE_URL = "https://n8n.editforge.online"
#: The n8n project the two tables live in.
PROJECT_ID = "qbrcjkbIoorbwot6"
#: Which columns identify a row in each table.
ROW_KEYS = {"show_registry": ("key",), "show_series": ("show", "key")}


def _api(path: str, method: str = "GET", body: object = None) -> object:
    base = (os.environ.get("N8N_VPS_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/")
    key = os.environ.get("N8N_VPS_KEY", "")
    if not key:
        raise SystemExit("N8N_VPS_KEY is required")
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


def describe_table(table_id: str) -> object:
    """The table's own definition: `name`, `projectId` and `columns` as a list of {name, type, ...}.

    Shape read from the live instance on 2026-10-06 for both registry tables.
    """
    return _api(f"/data-tables/{table_id}")


def check_table(table: str, table_id: str, payload: object) -> List[str]:
    """Reasons the table behind `table_id` is not the one `table` names, empty when it is.

    The name must equal the `REGISTRY_TABLES` key and the column names must equal
    the module's row keys exactly, in both directions, so a stale id pointing at
    another real table is refused before a single row is posted into it.
    """
    if not isinstance(payload, dict):
        return [f"{table} ({table_id}): unexpected table payload: {str(payload)[:200]}"]
    reasons: List[str] = []
    name = payload.get("name")
    if name != table:
        reasons.append(f"{table} ({table_id}): the table is named {name!r}, not {table!r}")
    columns = payload.get("columns")
    if not isinstance(columns, list):
        return reasons + [f"{table} ({table_id}): the table payload carries no column list"]
    live = {column["name"] for column in columns if isinstance(column, dict) and isinstance(column.get("name"), str)}
    wanted = set(expected(table)[0])
    if live != wanted:
        reasons.append(
            f"{table} ({table_id}): columns differ from the module: "
            f"table only {sorted(live - wanted)}, module only {sorted(wanted - live)}"
        )
    return reasons


def _reported_count(result: object) -> str:
    """The insert response as the instance gave it, never as a claim of what landed."""
    if isinstance(result, dict) and isinstance(result.get("count"), int):
        return f"count {result['count']}"
    return json.dumps(result)[:200]


def _identity(table: str, row: Dict[str, object]) -> Tuple[object, ...]:
    return tuple(row.get(column) for column in ROW_KEYS[table])


def column_spec(table: str) -> Dict[str, object]:
    """The create payload for one table, derived from the module's row shape.

    n8n data table columns are string, number, boolean or date; a bool is
    checked before an int because a Python bool is an int.
    """
    columns = []
    for name, value in expected(table)[0].items():
        kind = "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"
        columns.append({"name": name, "type": kind})
    return {"name": table, "projectId": PROJECT_ID, "columns": columns}


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
    parser.add_argument("--spec", action="store_true", help="print the create payload for both tables and exit; touches nothing")
    args = parser.parse_args(argv)
    if args.spec:
        print(json.dumps([column_spec(table) for table in REGISTRY_TABLES], indent=2))
        return 0
    if not (args.seed or args.check):
        parser.error("pass --seed, --check, --spec or a combination")
    clean = True
    for table, table_id in REGISTRY_TABLES.items():
        live = read_rows(table_id)
        missing, problems = diff(table, live)
        # A table that reads DRIFT gets nothing inserted. A row whose key drifted
        # on the instance (' nco' for 'nco') is a stranger to the diff and the
        # module's row is missing, so seeding here would leave two near identical
        # rows for a stage workflow to choose between. Settling that is a ruling.
        refused = bool(args.seed and missing and problems)
        if args.seed and missing and not problems:
            refusals = check_table(table, table_id, describe_table(table_id))
            if refusals:
                for line in refusals:
                    print(line)
                print(f"{table} ({table_id}): REFUSED to insert {len(missing)} rows, the id does not point at this table")
                clean = False
            elif args.dry_run:
                print(f"{table} ({table_id}): would insert {len(missing)} rows")
                for row in missing:
                    print("  ", json.dumps(row, ensure_ascii=False)[:160])
            else:
                posted = [_identity(table, row) for row in missing]
                result = insert_rows(table_id, missing)
                print(f"{table} ({table_id}): posted {len(posted)} rows, instance reports {_reported_count(result)}")
                live = read_rows(table_id)
                missing, problems = diff(table, live)
                still_missing = {_identity(table, row) for row in missing}
                landed = [identity for identity in posted if identity not in still_missing]
                print(f"{table} ({table_id}): {len(landed)} of {len(posted)} posted rows inserted, proven by read back")
        for line in problems:
            print(line)
        if refused:
            print(f"{table} ({table_id}): REFUSED to insert {len(missing)} rows: the table reads DRIFT, settle the lines above first")
        if missing:
            print(f"{table} ({table_id}): {len(missing)} rows missing: {[_identity(table, row) for row in missing]}")
        clean = clean and not missing and not problems
        print(f"{table} ({table_id}): {len(live)} rows read back, {len(expected(table))} expected, {'CLEAN' if not missing and not problems else 'DRIFT'}")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
