"""Airtable to n8n data table mirror: the deterministic transform.

Ruled by Tee 2026-09-15: every Airtable table becomes its own n8n data table
on the VPS under an ``at_`` prefix, a faithful archive that no lane reads, with
the Credentials table excluded because a data table is not a secret store.

This module is the part of that move that can live in a public repository:
the naming, typing and cell rules, with tests. The records themselves never
enter the repository. The move itself ran through the Airtable and n8n
connectors in the 2026-09-15 session; this file makes the rules repeatable and
lets a later run produce the same table names and column names, which is what
makes a second pull an update instead of a second copy.

Usage, offline::

    python3 scripts/airtable_mirror.py plan --base-key tqo \
        --schema tables.json --records records.json > mirror.json

``tables.json`` is the connector's list_tables_for_base shape
(``{"tables": [{"id", "name", "fields": [{"id", "name", "type"}]}]}``) and
``records.json`` is a map of table id to a list of records in the connector's
list_records_for_table shape (``{"id", "createdTime", "cellValuesByFieldId"}``).
The output is a list of ``{"table", "columns", "rows"}`` objects ready for the
n8n data table create and insert calls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Tables that never move. A data table is readable by every workflow on the
#: instance, so a secret store cannot live there. Matched on the table name,
#: case insensitive, after trimming.
EXCLUDED_TABLE_NAMES = ("credentials",)

#: Base keys the prefix carries so two bases with a table called Content do not
#: collide on the instance.
BASE_KEYS = {
    "app28z7XnKzjfTXwc": "tqo",
    "appVZxfdyG8jZi5GM": "fin",
    "appa7WL221K1DhYnX": "tsws",
}

#: The two columns every mirror row carries in front of the Airtable fields.
SYSTEM_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("airtable_record_id", "string"),
    ("airtable_created_time", "date"),
)

_NUMBER_TYPES = {"number", "rating", "count", "autoNumber", "percent", "currency", "duration"}
_BOOLEAN_TYPES = {"checkbox"}
_DATE_TYPES = {"date", "dateTime", "createdTime", "lastModifiedTime"}

#: n8n data table column rule: a letter, then letters, digits and underscores,
#: at most 63 characters.
_COLUMN_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_MAX_COLUMN = 63
_MAX_TABLE = 128


def slug(text: str) -> str:
    """Lower snake case from any Airtable name; never empty."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    return s or "field"


def table_name(base_key: str, airtable_name: str) -> str:
    name = f"at_{slug(base_key)}_{slug(airtable_name)}"
    return name[:_MAX_TABLE]


def is_excluded(airtable_name: str) -> bool:
    return str(airtable_name or "").strip().lower() in EXCLUDED_TABLE_NAMES


def column_type(field_type: str) -> str:
    if field_type in _NUMBER_TYPES:
        return "number"
    if field_type in _BOOLEAN_TYPES:
        return "boolean"
    if field_type in _DATE_TYPES:
        return "date"
    return "string"


def column_names(fields: Iterable[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    """(field id, column name, column type) for every field, unique and legal.

    A column that would collide with a system column or with an earlier field
    gets a numeric suffix. A name that starts with a digit gets an ``f_``
    prefix. Everything is cut to the 63 character limit before the suffix so
    the suffix survives the cut.
    """
    taken = {name for name, _ in SYSTEM_COLUMNS}
    out: List[Tuple[str, str, str]] = []
    for f in fields:
        base = slug(f.get("name", ""))
        if not base[0].isalpha():
            base = "f_" + base
        base = base[: _MAX_COLUMN - 4]
        name = base
        n = 2
        while name in taken:
            name = f"{base}_{n}"
            n += 1
        taken.add(name)
        if not _COLUMN_RE.match(name):  # pragma: no cover - the rules above make this unreachable
            raise ValueError(f"column name {name!r} is not legal for an n8n data table")
        out.append((str(f.get("id")), name, column_type(str(f.get("type", "")))))
    return out


def _scalar(v: Any) -> Any:
    if isinstance(v, dict):
        # A select choice, a collaborator, an attachment: the human readable
        # part wins, the id is not the value Tee reads.
        for key in ("name", "url", "email", "id"):
            if key in v and v[key] not in (None, ""):
                return str(v[key])
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    if isinstance(v, list):
        return ", ".join(str(_scalar(x)) for x in v)
    return v


def cell_value(col_type: str, value: Any) -> Any:
    """One Airtable cell into one data table cell of the column's type.

    ``None`` stays ``None``. A number column that receives a non number keeps
    the text in a way the caller can see (returns ``None``) rather than a
    fabricated 0. A date column passes an ISO string through untouched.
    """
    if value is None:
        return None
    if col_type == "number":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).strip())
        except ValueError:
            return None
    if col_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "y", "checked", "ticked")
    if col_type == "date":
        return str(value) if value != "" else None
    s = _scalar(value)
    return None if s is None else str(s)


def plan_table(base_key: str, table: Dict[str, Any], records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The create and insert plan for one table, or None when it is excluded."""
    if is_excluded(table.get("name", "")):
        return None
    cols = column_names(table.get("fields", []))
    columns = [{"name": n, "type": t} for n, t in SYSTEM_COLUMNS] + [
        {"name": name, "type": ctype} for _, name, ctype in cols
    ]
    rows = []
    for rec in records:
        cells = rec.get("cellValuesByFieldId") or rec.get("fields") or {}
        row: Dict[str, Any] = {
            "airtable_record_id": str(rec.get("id", "")),
            "airtable_created_time": rec.get("createdTime"),
        }
        for fid, name, ctype in cols:
            fdef = next((f for f in table.get("fields", []) if str(f.get("id")) == fid), {})
            raw = cells.get(fid, cells.get(fdef.get("name", ""), None))
            row[name] = cell_value(ctype, raw)
        rows.append(row)
    return {
        "table": table_name(base_key, table.get("name", "")),
        "airtable_table_id": table.get("id"),
        "airtable_table_name": table.get("name"),
        "columns": columns,
        "rows": rows,
    }


def plan_base(base_key: str, schema: Dict[str, Any], records_by_table: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for t in schema.get("tables", []):
        p = plan_table(base_key, t, records_by_table.get(str(t.get("id")), []))
        if p is not None:
            out.append(p)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="emit the create and insert plan as JSON")
    p.add_argument("--base-key", required=True, help="tqo, fin or tsws")
    p.add_argument("--schema", required=True, help="list_tables_for_base JSON")
    p.add_argument("--records", required=True, help="JSON map of table id to records")
    a = ap.parse_args(argv)
    with open(a.schema, encoding="utf-8") as fh:
        schema = json.load(fh)
    with open(a.records, encoding="utf-8") as fh:
        recs = json.load(fh)
    json.dump(plan_base(a.base_key, schema, recs), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
