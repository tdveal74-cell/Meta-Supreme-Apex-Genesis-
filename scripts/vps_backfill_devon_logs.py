"""Backfill DEVON's own memory tables from Cloud onto the VPS, insert only.

Found on 2026-09-16, hours after the cutover, by checking why the Heartbeat had
not beaten rather than assuming wall clock. The VPS copies of the tables DEVON
reads about himself are a snapshot taken 2026-09-03T09:01Z by the earlier
migration, and Cloud kept writing to its own copies until 2026-09-15T22:00:24Z,
when the switch unpublished it. Measured at the time:

* ``devon_heartbeat_log``: VPS 23 rows, newest beat 2026-09-03T04:00:24Z.
  Cloud 88 rows, newest beat 2026-09-15T22:00:24Z.
* ``devon_build12_feed_log``: VPS 2 rows, newest fed 2026-08-25.
  Cloud's final pulse counted 11 fed.

The cutover's step three moved the state ledger and nothing else, correctly:
every Cloud ledger row was terminal, so none of them were owed. These logs were
never in that step at all, which is why the gap survived a clean switch.

What it costs, left alone: the first VPS beat reads its own log, sees its last
pulse thirteen days back and emails a missed_beat finding of about 310 hours.
That one clears itself after a beat. The lasting cost is the memory, because
the pulse is where DEVON's continuity lives and twelve days of it would simply
be absent from the host he now runs on.

Ruled by Tee 2026-09-16: copy it.

This script only ever INSERTS. It never updates a row and never deletes one, it
touches no table outside ``TABLES`` below, and ``approval_queue`` is not in that
list and must never be added to it: its rows carry plaintext decision tokens and
the standing rule is that the queue does not move and that column is not read.

A row is copied only when its natural key is absent from the destination, so
running this twice is a no-op rather than a duplicate. Keys are per table and
deliberately compound, because ``beat_at`` alone would collide a pulse with a
reflection written in the same second.

Usage::

    python3 scripts/vps_backfill_devon_logs.py            # dry run, changes nothing
    python3 scripts/vps_backfill_devon_logs.py --apply

Needs ``N8N_CLOUD_KEY`` and ``N8N_VPS_KEY``. Row bodies are never printed; the
output is counts and keys, because a reflection is Tee's and does not belong in
a terminal scrollback.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

TIMEOUT = 60

#: The rows API takes ``limit`` and nothing else. Measured on 2026-09-16:
#: ``skip`` and ``offset`` are both rejected with "Unknown query parameter",
#: ``limit`` is capped at 250, and the response body carries no total. So there
#: is no way to page, and a table larger than the cap would come back silently
#: truncated. ``read_all`` refuses in that case rather than copying a prefix and
#: calling it the table. The three tables here were 88, 11 and 1 rows when this
#: was written, so the cap is headroom rather than a limit anyone is near.
PAGE = 250
CLOUD_URL_DEFAULT = "https://thequietoperator.app.n8n.cloud"

#: n8n adds these to every row. They are the destination's to assign, so they
#: are stripped before the insert rather than carried across.
SYSTEM_COLUMNS = ("id", "createdAt", "updatedAt")

#: label -> (cloud data table id, vps data table id, natural key columns)
TABLES: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("devon_heartbeat_log", "Adg1Gd9HML7Q4L3U", "RuPMZKXkqcbuHRKa", ("beat_at", "kind")),
    ("devon_build12_feed_log", "QeoV4V4dYXXN8dBR", "U0PqQWiq4nadKFlm", ("intent_id", "fed_at")),
    ("devon_soul_commit_log", "U9fnVy19Vc8kvQAw", "x8U4QqvXTVgINg3h", ("intent_id", "request_id")),
)


def api(base: str, key: str, path: str, payload: Optional[Any] = None) -> Dict[str, Any]:
    url = f"{base.rstrip('/')}/api/v1{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("X-N8N-API-KEY", key)
    request.add_header("Accept", "application/json")
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{request.get_method()} {url} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(body) if body else {}


def read_all(base: str, key: str, table_id: str) -> List[Dict[str, Any]]:
    """Every row, or an error. A full page means the read may be short."""
    page = api(base, key, f"/data-tables/{table_id}/rows?limit={PAGE}")
    rows = page.get("data") or []
    if len(rows) >= PAGE:
        raise RuntimeError(
            f"{table_id} returned {len(rows)} rows at the {PAGE} cap and this API cannot page. "
            "Refusing: a truncated read would copy a prefix and look complete.")
    return rows


def key_of(row: Dict[str, Any], columns: Sequence[str]) -> Tuple[str, ...]:
    return tuple(str(row.get(c, "")) for c in columns)


def payload_of(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in SYSTEM_COLUMNS}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually insert; default is a dry run")
    parser.add_argument("--table", action="append", help="limit to one label, repeatable")
    args = parser.parse_args(argv)

    cloud = (os.environ.get("N8N_CLOUD_URL", CLOUD_URL_DEFAULT), os.environ.get("N8N_CLOUD_KEY", ""))
    vps_url = os.environ.get("N8N_VPS_URL")
    if not vps_url:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from services.devon import vault  # noqa: WPS433

        vps_url = vault.N8N_HOST
    vps = (vps_url, os.environ.get("N8N_VPS_KEY", ""))
    missing = [n for n, v in (("N8N_CLOUD_KEY", cloud[1]), ("N8N_VPS_KEY", vps[1])) if not v]
    if missing:
        print(json.dumps({"error": "unset: " + ", ".join(missing)}))
        return 2

    report: List[Dict[str, Any]] = []
    failed = 0
    for label, cloud_id, vps_id, columns in TABLES:
        if args.table and label not in args.table:
            continue
        src = read_all(*cloud, cloud_id)
        dst = read_all(*vps, vps_id)
        have = {key_of(r, columns) for r in dst}
        owed = [r for r in src if key_of(r, columns) not in have]

        print(f"{label}: cloud {len(src)}, vps {len(dst)}, owed {len(owed)}")
        if owed:
            keys = sorted("|".join(key_of(r, columns)) for r in owed)
            print(f"  first owed key: {keys[0]}")
            print(f"  last  owed key: {keys[-1]}")

        inserted = 0
        if owed and args.apply:
            # One row per call. Slower, and worth it: a rejected batch would
            # leave a partial copy nobody could tell from a complete one.
            for row in owed:
                try:
                    api(*vps, f"/data-tables/{vps_id}/rows", payload={"data": [payload_of(row)]})
                    inserted += 1
                except RuntimeError as exc:
                    failed += 1
                    print(f"  FAILED {'|'.join(key_of(row, columns))}: {str(exc)[:160]}")
            after = read_all(*vps, vps_id)
            still = [r for r in src if key_of(r, columns) not in {key_of(x, columns) for x in after}]
            print(f"  inserted {inserted}, vps now {len(after)}, still owed {len(still)}")
            if still:
                failed += len(still)
        report.append({"table": label, "cloud": len(src), "vps_before": len(dst),
                       "owed": len(owed), "inserted": inserted})

    print()
    print(json.dumps({"mode": "apply" if args.apply else "dry-run",
                      "tables": report, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
