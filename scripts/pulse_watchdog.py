"""Watch the Build 13 Pulse from outside n8n, and fail loudly when it stops.

WHY THIS EXISTS, AND WHY IT CANNOT LIVE IN n8n
==============================================

The Pulse (``DEVON - Heartbeat (Build 13)``, VPS ``EEDrp2jLlw2Ssd5b``) beats
every six hours and writes one row to ``devon_heartbeat_log``. Among its
findings is ``missed_beat``, which compares the current beat against the
previous one.

That finding is computed BY the Pulse. So it can report a LATE beat and can
never report a STOPPED one: a Pulse that does not run writes nothing, and
nothing is indistinguishable from a healthy quiet estate. Every organ that
could watch it lives on the same n8n instance and dies with it.

DEVON said so himself in the reflection of 2026-09-16:

    missed_beat is computed BY the pulse, so a pulse that does not run cannot
    report its own absence; it can flag a late beat, never a stopped one.

    ... decide whether something outside n8n should watch the Pulse, because
    nothing inside it can.

This script is the answer to that. It runs in GitHub Actions, on infrastructure
that shares nothing with the VPS, and it reads the beat log over the public API.
When the newest beat is older than the Pulse's own missed-beat threshold, the
script exits non-zero, the scheduled workflow goes red, and GitHub mails the
repository owner. The alarm channel is the job failing; there is deliberately no
SMTP here, because an alerting path with its own credentials is one more thing
that can fail silently.

WHAT COUNTS AS A BEAT
=====================

``devon_heartbeat_log`` holds TWO kinds of row: ``pulse`` rows written by the
Pulse, and ``reflection`` rows written by DEVON's daily reflection. Only a
``pulse`` row is a beat. This matters more than it looks: the reflection writes
to the same table, so a watchdog that took the newest row of ANY kind would be
reassured by a reflection while the Pulse lay dead, which is the exact failure
it exists to catch. ``newest_beat`` filters on kind, and
``test_pulse_watchdog.py`` pins that with a case where the newest row overall is
a reflection and the newest beat is stale.

THREE OUTCOMES, NEVER TWO
=========================

A watchdog that cannot tell "the Pulse is dead" from "I could not look" is worth
very little, so they are separate exit codes and separate messages:

    0  OK           a pulse row inside the threshold
    1  ALARM        no pulse row inside the threshold: the Pulse has stopped
    2  CANNOT CHECK config missing, HTTP error, truncated read, no readable
                    timestamp. NEVER reported as healthy.

Both 1 and 2 fail the job on purpose. Silence about an unchecked Pulse would be
the same lie the Pulse itself cannot avoid telling.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: The VPS n8n instance. Every DEVON organ runs here, live and published, per
#: Tee's cutover ruling of 2026-09-15 recorded in
#: ``docs/devon/vps-cutover-maps_2026-09-15.json``, which is also where this
#: host is already written down. Overridable so the same script can be pointed
#: at another instance without editing it.
DEFAULT_BASE_URL = "https://n8n.editforge.online"

#: ``devon_heartbeat_log`` on the VPS. Same id as the ``TABLES`` map in
#: ``scripts/vps_backfill_devon_logs.py``, which is what backfilled it.
HEARTBEAT_TABLE_ID = "RuPMZKXkqcbuHRKa"

#: Hours after which a missing beat is an alarm. This is NOT a fresh guess: it
#: is ``MISSED_BEAT_H`` from ``n8n/devon/heartbeat/compose_pulse.js``, so the
#: watchdog and the Pulse agree on what "missed" means rather than drifting
#: apart. ``test_pulse_watchdog.py`` reads the number back out of that file and
#: fails if the two stop matching.
MISSED_BEAT_H = 7.5

#: The rows API takes ``limit`` and nothing else, is capped at 250, returns no
#: total, and cannot page. Measured on 2026-09-16 and recorded in
#: ``scripts/vps_backfill_devon_logs.py``. A read that comes back at the cap may
#: be short, and since the API does not promise an order, a short read could
#: omit the newest beat and manufacture a false alarm. So a full page refuses
#: rather than guesses, exactly as ``read_all`` does there.
PAGE = 250

TIMEOUT = 30

OK = 0
ALARM = 1
CANNOT_CHECK = 2


def parse_iso(value: Any) -> Optional[datetime]:
    """A timezone-aware datetime, or None if this is not a readable timestamp.

    ``datetime.fromisoformat`` only learned to accept a trailing ``Z`` in 3.11,
    and every beat_at in this table carries one, so it is normalised first.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def newest_beat(rows: Sequence[Dict[str, Any]]) -> Tuple[Optional[datetime], int, int]:
    """(newest pulse beat, pulse rows seen, pulse rows with no readable beat_at).

    Only ``kind == "pulse"`` rows count. A reflection row is not a beat, and
    treating one as a beat would hide the outage this script exists to find.
    The maximum is taken over every row rather than trusting the response order,
    because the rows API documents none.
    """
    newest: Optional[datetime] = None
    seen = 0
    unreadable = 0
    for row in rows:
        if str(row.get("kind") or "").strip().lower() != "pulse":
            continue
        seen += 1
        stamp = parse_iso(row.get("beat_at"))
        if stamp is None:
            unreadable += 1
            continue
        if newest is None or stamp > newest:
            newest = stamp
    return newest, seen, unreadable


def verdict(
    rows: Sequence[Dict[str, Any]],
    now: datetime,
    threshold_h: float = MISSED_BEAT_H,
) -> Tuple[int, str]:
    """Exit code and the line a human reads, from rows already fetched.

    Pure, so the whole decision is testable without a network or a key.
    """
    if len(rows) >= PAGE:
        return CANNOT_CHECK, (
            f"CANNOT CHECK: the beat log returned {len(rows)} rows at the {PAGE} row cap. "
            "This API cannot page and promises no order, so the newest beat may not be in "
            "what came back. Refusing to judge a truncated read. Prune the log or teach "
            "this script a narrower read."
        )

    newest, seen, unreadable = newest_beat(rows)

    if seen == 0:
        return ALARM, (
            f"ALARM: the beat log holds {len(rows)} row(s) and not one of them is a pulse. "
            "The Pulse has never beaten, or its rows are being written under another kind."
        )

    if newest is None:
        return CANNOT_CHECK, (
            f"CANNOT CHECK: all {seen} pulse row(s) carry no readable beat_at. "
            "The log is reachable but its timestamps are not, so the Pulse may be fine or "
            "may be dead and this script cannot tell which."
        )

    age_h = (now - newest).total_seconds() / 3600.0
    stamp = newest.isoformat().replace("+00:00", "Z")
    tail = ""
    if unreadable:
        tail = (
            f" ({unreadable} pulse row(s) had no readable beat_at and were skipped; "
            "the verdict rests on the rest.)"
        )

    if age_h > threshold_h:
        return ALARM, (
            f"ALARM: the Pulse last beat at {stamp}, {age_h:.1f}h ago. It beats every 6h and "
            f"anything past {threshold_h}h is a missed beat. Nothing inside n8n can report "
            "this, which is why this job exists. Check whether the Heartbeat workflow is "
            "still published and active on the VPS." + tail
        )

    return OK, (
        f"OK: the Pulse last beat at {stamp}, {age_h:.1f}h ago, inside the {threshold_h}h "
        f"threshold. {seen} pulse row(s) read." + tail
    )


def fetch_rows(base: str, key: str, table_id: str) -> List[Dict[str, Any]]:
    """Rows from the n8n public API, or a RuntimeError naming what went wrong."""
    url = f"{base.rstrip('/')}/api/v1/data-tables/{table_id}/rows?limit={PAGE}"
    request = urllib.request.Request(url, method="GET")
    request.add_header("X-N8N-API-KEY", key)
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GET {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} -> could not reach the instance: {exc.reason}") from exc
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {url} -> response was not JSON: {body[:300]!r}") from exc
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"GET {url} -> no 'data' array in the response: {body[:300]!r}")
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    base = os.environ.get("N8N_VPS_URL", "").strip() or DEFAULT_BASE_URL
    key = os.environ.get("N8N_VPS_KEY", "").strip()
    table_id = os.environ.get("DEVON_HEARTBEAT_TABLE_ID", "").strip() or HEARTBEAT_TABLE_ID

    if not key:
        print(
            "CANNOT CHECK: N8N_VPS_KEY is not set, so the beat log cannot be read. "
            "Set it as a repository secret; without it this job can only ever be "
            "uninformative, and an uninformative watchdog reporting green is worse "
            "than no watchdog.",
            file=sys.stderr,
        )
        return CANNOT_CHECK

    print(f"Reading the beat log from {base} (table {table_id}).")

    try:
        rows = fetch_rows(base, key, table_id)
    except RuntimeError as exc:
        print(f"CANNOT CHECK: {exc}", file=sys.stderr)
        return CANNOT_CHECK

    code, message = verdict(rows, datetime.now(timezone.utc))
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
