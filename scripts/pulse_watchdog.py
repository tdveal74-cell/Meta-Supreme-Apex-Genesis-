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

A FRESH BEAT DOES NOT MEAN A FINISHED RUN
=========================================

This script shipped reading one thing, the newest beat's timestamp, and that was
not enough. Measured on 2026-09-22, thirty six hours into an outage it reported
OK through:

    DEVON - Heartbeat (Build 13) failed seven consecutive runs, 2026-09-20T16:00
    through 2026-09-22T04:00. Execution 729 started at 04:00:15.037Z, wrote beat
    row 116 at 04:00:15.184Z, and died at 04:00:27.596Z at the node ``Send
    Pulse`` on ``Invalid login: 535-5.7.8 Username and Password not accepted``.

``Record Beat`` sits on a branch parallel to the email branch, both fed by
``Compose Pulse``, so the row lands about 150ms into a run that then takes
twelve seconds to die. Reading that row, this script found a beat 5.6h old,
inside the threshold, and printed OK four times a day while Tee's mail went
nowhere. The failure was found by a session that had come to look at something
else, which is the same way the 2026-09-17 provider outage was found.

So the beat is now a necessary condition and not a sufficient one. The script
also asks n8n for ERRORED executions of the Heartbeat itself, and alarms when
one landed inside the same threshold window. That catches every way the Pulse
can die after writing its receipt, not just this one.

GRADED HONESTLY, because over-calling a finding is its own error: a single
transient failure now turns this job red for up to 7.5h, which is two or three
red runs and two or three emails about something already recovered. That is the
right trade only because this exact shape has now cost the estate twice, nine
days of dead Gmail OAuth from 2026-09-01 and thirty six hours of dead SMTP from
2026-09-20, and in both cases the channel that should have reported it was the
channel that had failed. The Heartbeat runs four times a day; one failure is
worth one red job.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
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

#: The Heartbeat workflow itself, so this script can ask whether the run that
#: wrote the newest beat actually finished. Same id as the module docstring
#: above, which took it from ``docs/devon/vps-cutover-maps_2026-09-15.json``.
HEARTBEAT_WORKFLOW_ID = "EEDrp2jLlw2Ssd5b"

#: How many errored executions to pull ESTATE WIDE, newest first. Not a list of
#: lanes: a hand written list is what went wrong here. CLAUDE.md records SIXTEEN
#: workflows sending across TWENTY emailSend nodes on one credential, measured
#: on 2026-09-22 after this file's first version watched three of them and
#: called that an estate count. Asking the instance for its own failures needs
#: no list and picks up a workflow added tomorrow.
ESTATE_RUN_LIMIT = 15

#: The node type every alerting send uses. Errored executions are classified by
#: this rather than alarmed on wholesale, because the estate carries unrelated
#: failures at all times (the Cerebras lanes have been returning 402 since about
#: 2026-09-17) and a watchdog that is permanently red teaches nothing.
MAIL_NODE_TYPE = "n8n-nodes-base.emailSend"

#: The lane this check still cannot see, whatever it reads. OS Error Handler
#: (all pipelines) sets ``onError: continueRegularOutput`` on its send, so a
#: failed alert finishes the run GREEN and never appears under ``status=error``.
#: Going estate wide does not fix that: there is no errored execution to find.
#: Declared on every run rather than quietly omitted. Tee declined flipping the
#: flag on 2026-09-22, because a mail outage would then kill pipelines.
UNWATCHABLE_LANE = (
    "GbeNilHQzjmoWDz3",
    "OS Error Handler (all pipelines)",
    "sets onError continueRegularOutput on its send, so a failed alert reports SUCCESS",
)

#: How many rows to ask for when the narrowed, newest-first read is available.
#: Comfortably more than the ~5 rows a day the log grows by, so a verdict never
#: rests on a handful, and far under the cap below.
NARROW_LIMIT = 50

#: How many errored runs of the Heartbeat to list. Only the newest decides the
#: verdict; the rest are counted so the message can say how deep the outage
#: goes. The 2026-09-20 outage was seven consecutive failures, so a handful is
#: enough to tell one bad run from a stuck lane.
MAX_FAILED_RUNS = 10

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


def is_newest_first(rows: Sequence[Dict[str, Any]], want: int) -> bool:
    """Did a narrowed read really come back newest first, or was it ignored?

    The rows API was measured in September as ``limit`` and nothing else, so a
    server that ignores an ordering parameter would hand back the OLDEST rows
    instead. Acting on that would drop the newest beat and manufacture a false
    alarm, which is worse than the row cap this narrowing exists to dodge. So
    the response has to prove itself: at least two rows, no more than asked
    for, integer ids, strictly descending. A server that ignored the parameter
    cannot satisfy that by accident, and if it fails the caller falls back to
    the wide read and the old refusal. Pure, so the guard is testable without a
    network or a key.
    """
    if want < 2 or len(rows) < 2 or len(rows) > want:
        return False
    ids = [row.get("id") for row in rows]
    if not all(isinstance(value, int) for value in ids):
        return False
    return all(earlier > later for earlier, later in zip(ids, ids[1:], strict=False))


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


def newest_failure(executions: Sequence[Dict[str, Any]]) -> Tuple[Optional[datetime], Optional[str], int]:
    """(newest errored start, that execution's id, how many errored runs were seen).

    The caller asks n8n for errored executions of one workflow, so everything in
    the list is a failure by construction and nothing here re-checks a status
    field. The maximum is taken over the whole list rather than trusting the
    response order, for the same reason ``newest_beat`` does: this API promises
    none.
    """
    newest: Optional[datetime] = None
    newest_id: Optional[str] = None
    seen = 0
    for run in executions:
        seen += 1
        stamp = parse_iso(run.get("startedAt"))
        if stamp is None:
            continue
        if newest is None or stamp > newest:
            newest = stamp
            newest_id = str(run.get("id") or "") or None
    return newest, newest_id, seen


def run_verdict(
    executions: Sequence[Dict[str, Any]],
    now: datetime,
    threshold_h: float = MISSED_BEAT_H,
    detail: str = "",
) -> Tuple[int, str]:
    """Exit code and message for "did DEVON's alerting runs actually finish".

    Separate from ``verdict`` because it answers a different question about a
    different source. ``verdict`` reads the receipt the Pulse leaves behind;
    this reads whether the run that left it lived long enough to do its job.
    Pure, so the decision is testable without a network or a key.
    """
    newest, execution_id, seen = newest_failure(executions)

    if seen == 0 or newest is None:
        return OK, (
            "OK: no alerting run of any DEVON workflow came back errored, so every "
            "send that ran finished rather than dying on its way to Tee."
        )

    age_h = (now - newest).total_seconds() / 3600.0
    if age_h > threshold_h:
        return OK, (
            f"OK: the newest errored alerting run started {age_h:.1f}h ago, outside the "
            f"{threshold_h}h window, so it is old news rather than a live outage. "
            f"{seen} errored run(s) were listed."
        )

    stamp = newest.isoformat().replace("+00:00", "Z")
    where = f" ({detail})" if detail else ""
    which = f" Execution {execution_id}." if execution_id else ""
    plural = "" if seen == 1 else "s"
    return ALARM, (
        f"ALARM: a DEVON alerting send RAN but did not DELIVER. Its newest errored run started "
        f"{stamp}, {age_h:.1f}h ago, inside the {threshold_h}h window{where}.{which} "
        f"{seen} errored run{plural} were listed. A beat row is written early, on a branch "
        "parallel to the email, so a fresh beat proves the Pulse started and proves nothing "
        "about whether it delivered. Open the execution on the VPS and read the failing node."
    )


def combine(beat_code: int, run_code: int) -> int:
    """The exit code for two verdicts, where a definite finding beats an absence.

    ALARM wins over CANNOT_CHECK on purpose. A stopped Pulse is news; "I could
    not read the run list" is the lack of news, and letting the second mask the
    first would bury the only thing worth saying. OK loses to both.
    """
    if ALARM in (beat_code, run_code):
        return ALARM
    if CANNOT_CHECK in (beat_code, run_code):
        return CANNOT_CHECK
    return OK


def get_json(base: str, key: str, path: str) -> Dict[str, Any]:
    """One GET against the n8n public API, or a RuntimeError naming what broke.

    Every read in this script goes through here so that a 401, an unreachable
    host and a non-JSON body all reach the caller as the same kind of refusal
    rather than as three different silences.
    """
    url = f"{base.rstrip('/')}{path}"
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
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {url} -> response was not an object: {body[:300]!r}")
    return payload


def _rows_at(base: str, key: str, path: str) -> List[Dict[str, Any]]:
    payload = get_json(base, key, path)
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"GET {base.rstrip('/')}{path} -> no 'data' array in the response")
    return rows


def fetch_rows(base: str, key: str, table_id: str) -> List[Dict[str, Any]]:
    """Rows from the n8n public API, or a RuntimeError naming what went wrong.

    Tries a narrowed newest-first read before the wide one. The beat log grows
    about five rows a day and stood at 120 on 2026-09-22, so the 250 row cap
    that makes ``verdict`` refuse arrives in about a month. A watchdog that
    starts crying CANNOT CHECK on schedule is one Tee stops reading, which is
    worse than the cap itself.

    Whether this API honours ordering is NOT known here: it was measured in
    September as limit-only, and no key is reachable from the container this
    was written in, so it could not be tried. That is why the narrowed read has
    to prove itself through ``is_newest_first`` rather than be trusted. A server
    that ignores the parameters hands back rows this rejects, and the wide read
    below runs exactly as it did before. The first scheduled run on main is what
    settles which path this instance takes.
    """
    narrow = (
        f"/api/v1/data-tables/{table_id}/rows"
        f"?limit={NARROW_LIMIT}&sortBy=id%3Adesc"
    )
    try:
        rows = _rows_at(base, key, narrow)
    except RuntimeError:
        rows = []
    if is_newest_first(rows, NARROW_LIMIT):
        return rows

    return _rows_at(base, key, f"/api/v1/data-tables/{table_id}/rows?limit={PAGE}")


def fetch_failed_runs(
    base: str,
    key: str,
    workflow_id: Optional[str] = None,
    limit: int = MAX_FAILED_RUNS,
) -> List[Dict[str, Any]]:
    """Errored executions of one workflow, newest first as n8n returns them.

    The ``status=error`` filter does the work, so nothing downstream has to
    interpret a status field whose name has changed across n8n versions. The
    same filter is already proven against this instance by
    ``scripts/provider_watchdog.py``.
    """
    path = f"/api/v1/executions?status=error&limit={int(limit)}"
    if workflow_id:
        path += f"&workflowId={urllib.parse.quote(workflow_id)}"
    payload = get_json(base, key, path)
    runs = payload.get("data")
    if not isinstance(runs, list):
        raise RuntimeError(f"GET {base.rstrip('/')}{path} -> no 'data' array in the response")
    return runs


def failure_node(base: str, key: str, execution_id: str) -> Tuple[str, str, str]:
    """(node name, node type, message) for one errored execution, or three "".

    The node TYPE is what makes an estate wide read usable. This instance always
    carries unrelated failures, so alarming on every errored execution would
    leave the watchdog permanently red and therefore unread. Every error is
    swallowed rather than allowed to downgrade a verdict, for the same reason
    ``failure_detail`` swallows its own. n8n redacts credential values in
    execution payloads and only the name, the type and the message are taken.
    """
    try:
        payload = get_json(base, key, f"/api/v1/executions/{execution_id}?includeData=true")
    except RuntimeError:
        return "", "", ""
    error = (((payload.get("data") or {}).get("resultData") or {}).get("error") or {})
    if not isinstance(error, dict):
        return "", "", ""
    node = error.get("node") if isinstance(error.get("node"), dict) else {}
    name = str((node or {}).get("name") or "").strip()
    node_type = str((node or {}).get("type") or "").strip()
    message = " ".join(str(error.get("message") or "").split())[:200]
    return name, node_type, message


def mail_failures(
    runs: Sequence[Dict[str, Any]],
    resolved: Dict[str, Tuple[str, str, str]],
    now: datetime,
    threshold_h: float = MISSED_BEAT_H,
) -> List[Dict[str, Any]]:
    """The errored runs inside the window whose failing node is a mail send.

    Pure: the caller does the reading and hands the answers in, so the decision
    is testable without a network or a key. A run whose node could not be
    resolved is KEPT rather than dropped, because an unreadable failure inside
    the window is exactly when guessing is least affordable, and ``run_verdict``
    is the thing that decides what to do about it.
    """
    keep: List[Dict[str, Any]] = []
    for run in runs:
        stamp = parse_iso(run.get("startedAt"))
        if stamp is None or (now - stamp).total_seconds() / 3600.0 > threshold_h:
            continue
        _, node_type, _ = resolved.get(str(run.get("id") or ""), ("", "", ""))
        if node_type and node_type != MAIL_NODE_TYPE:
            continue
        keep.append(run)
    return keep


def failure_detail(base: str, key: str, execution_id: str) -> str:
    """"node X: message" for one errored execution, or "" if it cannot be read.

    This is a nicety and never a finding. An alarm that knows the failing node
    saves Tee a click; an alarm that cannot read it is still a correct alarm, so
    every error here is swallowed rather than allowed to downgrade the verdict
    to CANNOT CHECK. n8n redacts credential values in execution payloads, and
    only the node name and the error message are taken, so nothing secret is
    printed.
    """
    try:
        payload = get_json(base, key, f"/api/v1/executions/{execution_id}?includeData=true")
    except RuntimeError:
        return ""
    error = (((payload.get("data") or {}).get("resultData") or {}).get("error") or {})
    if not isinstance(error, dict):
        return ""
    node = ((error.get("node") or {}) if isinstance(error.get("node"), dict) else {}).get("name")
    message = error.get("message")
    node_text = str(node).strip() if node else ""
    message_text = " ".join(str(message).split())[:200] if message else ""
    if node_text and message_text:
        return f"node {node_text}: {message_text}"
    return node_text or message_text


def main(argv: Optional[List[str]] = None) -> int:
    base = os.environ.get("N8N_VPS_URL", "").strip() or DEFAULT_BASE_URL
    key = os.environ.get("N8N_VPS_KEY", "").strip()
    table_id = os.environ.get("DEVON_HEARTBEAT_TABLE_ID", "").strip() or HEARTBEAT_TABLE_ID
    # DEVON_HEARTBEAT_WORKFLOW_ID is deliberately no longer read. The run check
    # names no workflow at all now, so an override that points it at one would
    # narrow the estate read back into the hand list this replaced.

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

    now = datetime.now(timezone.utc)

    try:
        rows = fetch_rows(base, key, table_id)
    except RuntimeError as exc:
        print(f"CANNOT CHECK: {exc}", file=sys.stderr)
        return CANNOT_CHECK

    beat_code, beat_message = verdict(rows, now)
    print(beat_message, file=sys.stderr if beat_code else sys.stdout)

    # The beat is necessary and not sufficient. A run that writes its row and
    # then dies at the send leaves a beat that looks perfect, which is what this
    # script reported for thirty six hours in September 2026. So ask the
    # instance whether its alerting runs finished. Estate wide and unfiltered by
    # workflow, because the first version of this check watched three lanes out
    # of sixteen and described that as counted from the estate.
    print(f"Reading errored runs across the estate (newest {ESTATE_RUN_LIMIT}).")
    try:
        runs = fetch_failed_runs(base, key, limit=ESTATE_RUN_LIMIT)
    except RuntimeError as exc:
        print(
            f"CANNOT CHECK: the beat log was read but the run list was not ({exc}). "
            "A fresh beat alone does not prove a send delivered, so this is not "
            "reported as healthy.",
            file=sys.stderr,
        )
        return combine(beat_code, CANNOT_CHECK)

    # Only failures inside the window are worth a detail read, and only their
    # failing node decides whether this is an alerting outage or one of the
    # unrelated failures this estate always carries.
    resolved: Dict[str, Tuple[str, str, str]] = {}
    for run in runs:
        stamp = parse_iso(run.get("startedAt"))
        execution_id = str(run.get("id") or "")
        if not execution_id or stamp is None:
            continue
        if (now - stamp).total_seconds() / 3600.0 > MISSED_BEAT_H:
            continue
        resolved[execution_id] = failure_node(base, key, execution_id)

    mail = mail_failures(runs, resolved, now)
    detail = ""
    newest, execution_id, _ = newest_failure(mail)
    if execution_id:
        name, _, message = resolved.get(execution_id, ("", "", ""))
        if name and message:
            detail = f"node {name}: {message}"
        elif name or message:
            detail = name or message

    run_code, run_message = run_verdict(mail, now, detail=detail)
    print(run_message, file=sys.stderr if run_code else sys.stdout)

    skipped = len(runs) - len(mail)
    if skipped > 0:
        print(
            f"{skipped} errored run(s) were read and set aside as not alerting failures "
            "or outside the window. This estate carries unrelated errors at all times, "
            "and a watchdog that alarms on all of them is one nobody reads."
        )

    # Said on every run, green or red, so this never reads as everything watched.
    blind_id, blind_label, blind_why = UNWATCHABLE_LANE
    print(
        f"NOT WATCHED: {blind_label} ({blind_id}) {blind_why}, so it cannot appear "
        "in the check above however broken it is. Going estate wide does not reach "
        "it either, because there is no errored execution to find."
    )

    return combine(beat_code, run_code)

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
