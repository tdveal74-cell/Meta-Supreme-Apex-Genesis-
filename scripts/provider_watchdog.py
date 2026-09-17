"""Watch for a model provider refusing the estate's calls, and fail loudly.

WHY THIS EXISTS
===============

On 2026-09-17 at 19:00Z a session looking at something else noticed that the
content pipeline had been dead since 01:00Z that morning. Cerebras was answering
HTTP 402, "Payment required to access this resource", and seventeen nodes in
``TQO FINAL V5`` route through it: every script, packaging, brief, manifest, QC
and doctor call for both shows. Eight of the retained executions had failed the
same way across eighteen hours and nothing anywhere said so.

That is the same failure the 2026-08-14 teardown found on Anthropic, where the
script writers died on "Your credit balance is too low" and the render lane
politely reported an empty queue because no work had reached it. Twice now the
whole content operation has stopped because one provider stopped taking calls,
and both times the estate's own machinery reported nothing.

WHAT THIS IS NOT, STATED FIRST BECAUSE IT WAS ASKED FOR
=======================================================

Tee ruled for a "provider balance alarm": something that reads the balances and
goes red before the pipeline starves. That option was written before checking,
and it is only half buildable. Anthropic publishes no balance endpoint, and
neither does Cerebras. A script that claimed to watch all three balances would
be lying about two of them, which is the exact shape of failure this repository
keeps writing rules against.

So this watches the thing that IS observable for every provider: the estate's
own executions, for a terminal error that means a provider refused the call.
It is a LAGGING indicator by necessity. It fires after the first refusal rather
than before it, and one cycle after is the whole improvement over eighteen
hours of silence.

TWO WAYS A LANE FAILS, AND ONLY ONE OF THEM ERRORS
==================================================

Added 2026-09-17, hours after the rest of this file shipped, when reading the
live nodes for a different question found that the first version watched less
than it implied. ``TQO FINAL V5`` throws on a refusal, so it lands in the error
list this script reads. ``DEVON Face`` and ``DEVON Drive Draft Writer`` do not:
both set ``neverError`` and ``onError: continueRegularOutput`` on their provider
call, deliberately, because a chat face that throws a stack trace at Tee is
worse than one that says it could not reach its lane. A 402 there produces a
SUCCESSFUL execution carrying the refusal as data, and Face answers "I could not
reach my language lane (HTTP 402). The ledger still stands; ask again in a
minute", which reads like a blip on the first day and on the eighth.

So this script now reads both: the error list, and the newest successful runs of
every lane that calls a provider host and swallows the answer. Those lanes are
derived from the workflows rather than listed here, so a third one written the
same way is covered the day it lands.

One lane cannot be covered at all and is named in the output instead. ``DEVON
Drive Draft Writer`` sets ``saveDataSuccessExecution: none``, so a successful
run of it leaves nothing for any execution reader to open. Its refusal is not
lost, it rides back on the job envelope as ``refused`` with the reason and the
state ledger holds it, but this script cannot see it and says so on every run
rather than reporting coverage it does not have.

Grading this honestly, because over calling a finding is its own error: the
first version DID catch the 2026-09-17 outage, and the test that replays it
still passes unchanged. The gap is narrower than "the watchdog was broken". It
is an outage confined to the soft failing lanes, which is exactly what a
provider split or a paused content trigger would produce.

OpenRouter does expose credit at ``GET /api/v1/credits``, so for that one
provider a leading check is possible and would be a genuine improvement. It is
deliberately not built here: it needs a second repository secret, and a
half-built leading indicator beside a working lagging one invites the reader to
trust the wrong number. Build it when the key is available, and say in its
message that it covers OpenRouter alone.

WHAT COUNTS AS A REFUSAL
========================

Three kinds, and they are not treated alike:

``payment``  HTTP 402, or a message naming a credit balance, payment, or
             insufficient funds. This never clears itself. ALARM.
``auth``     HTTP 401 or 403, or a message naming an invalid or missing key.
             Also never clears itself, and it starves the pipeline identically.
             ALARM.
``rate``     HTTP 429, or a message about too many requests. Usually transient
             and usually self clearing, so it is COUNTED and REPORTED but does
             not alarm on its own. A rate limit that is really an outage will
             show up as sustained failure, which a human reading the count can
             see without this script guessing on their behalf.

THREE OUTCOMES, NEVER TWO
=========================

    0  OK           no payment or auth refusal in the window
    1  ALARM        a provider is refusing calls; the pipeline is starving
    2  CANNOT CHECK config missing, HTTP error, unreadable data. NEVER reported
                    as healthy.

Both 1 and 2 fail the job on purpose, for the same reason ``pulse_watchdog.py``
does it: an unchecked provider reported as fine is the lie the whole thing
exists to prevent.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: The VPS n8n instance, same default and same reason as ``pulse_watchdog.py``.
DEFAULT_BASE_URL = "https://n8n.editforge.online"

#: How far back a refusal still counts. The job is scheduled every three hours,
#: so a six hour window means no failure falls between two runs, and a refusal
#: that has genuinely been fixed stops alarming within two runs rather than
#: lingering for half a day.
WINDOW_H = 6.0

#: How many errored executions to open. The list call is cheap and carries no
#: error message, so each candidate costs one more request. A payment refusal
#: recurs on every scheduled run rather than happening once, so reading the
#: newest handful cannot miss a live one; it could miss an old isolated refusal
#: that has already stopped, which is not what this alarm is for.
MAX_OPEN = 25

#: How many successful runs to open PER soft failing lane. A refusal recurs on
#: every call, so the newest handful cannot miss a live one. Narrow rather than
#: deep on purpose: the cost here is one request per execution opened.
MAX_SUCCESS_PER_LANE = 6

#: Pages of the workflow list to walk. 100 per page against 65 workflows today,
#: so one page covers it and the loop exists so a doubling of the estate does
#: not silently truncate the derivation.
MAX_WORKFLOW_PAGES = 5

TIMEOUT = 30

OK = 0
ALARM = 1
CANNOT_CHECK = 2

PAYMENT = "payment"
AUTH = "auth"
RATE = "rate"

#: Matched against the lowercased error message. Kept as plain substrings
#: rather than regexes: every one of these is a literal phrase seen in a real
#: vendor response, and a regex here would be harder to check than to write.
PAYMENT_PHRASES = (
    "payment required",
    "credit balance is too low",
    "insufficient funds",
    "insufficient credit",
    "billing",
    "quota exceeded",
)
AUTH_PHRASES = (
    "invalid api key",
    "invalid_api_key",
    "incorrect api key",
    "unauthorized",
    "authentication_error",
    "no auth credential",
)
RATE_PHRASES = (
    "too many requests",
    "rate limit",
    "rate_limit",
)


def parse_iso(value: Any) -> Optional[datetime]:
    """A timezone-aware datetime, or None. Same normalisation as the Pulse."""
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


def classify(message: Any, http_code: Any = None) -> Optional[str]:
    """Which kind of provider refusal this is, or None if it is not one.

    Pure, and the whole judgement of the script rests on it, so it is driven
    directly by ``test_provider_watchdog.py`` over the real strings these
    vendors return rather than over invented ones.
    """
    code: Optional[int]
    try:
        code = int(http_code) if http_code is not None else None
    except (TypeError, ValueError):
        code = None

    if code == 402:
        return PAYMENT
    if code in (401, 403):
        return AUTH
    if code == 429:
        return RATE

    text = str(message or "").lower()
    if not text:
        return None
    if any(p in text for p in PAYMENT_PHRASES):
        return PAYMENT
    if any(p in text for p in AUTH_PHRASES):
        return AUTH
    if any(p in text for p in RATE_PHRASES):
        return RATE
    return None


#: Hosts that are model providers. A node posting to one of these is a model
#: call wherever it lives, so the soft failure scan below does not need a list
#: of workflows that would drift the moment a lane is added. These are facts
#: about the vendors rather than about this estate, which is why a literal
#: tuple is checkable by eye.
PROVIDER_HOSTS = (
    "api.cerebras.ai",
    "api.anthropic.com",
    "openrouter.ai",
    "api.openai.com",
    "api.groq.com",
    "api.x.ai",
    "generativelanguage.googleapis.com",
)


def swallowing_provider_nodes(workflow: Dict[str, Any]) -> List[str]:
    """Nodes that call a model provider AND turn its refusal into ordinary data.

    Found on 2026-09-17, after this script shipped, by reading the live nodes
    rather than the mirrors. ``DEVON Face`` and ``DEVON Drive Draft Writer``
    both set ``neverError`` and ``onError: continueRegularOutput`` on their
    provider call, on purpose: a chat face that throws a stack trace at Tee is
    worse than one that says it could not reach its lane. The cost of that
    choice is that a 402 there produces a SUCCESSFUL execution, and the error
    list this script reads never mentions it.

    Pure, and driven by fixtures in ``test_provider_watchdog.py`` built from the
    two real nodes, so a third lane written the same way is covered the day it
    lands without anything here being edited.
    """
    found: List[str] = []
    for node in workflow.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        params = node.get("parameters")
        params = params if isinstance(params, dict) else {}
        url = str(params.get("url") or "")
        if not any(host in url for host in PROVIDER_HOSTS):
            continue
        # Two independent ways to swallow, and either one is enough. neverError
        # keeps a non-200 out of the error path; continueRegularOutput keeps a
        # thrown request out of it. A node with both is the common case here.
        options = params.get("options")
        options = options if isinstance(options, dict) else {}
        response = options.get("response")
        response = response if isinstance(response, dict) else {}
        inner = response.get("response")
        inner = inner if isinstance(inner, dict) else {}
        swallows = bool(inner.get("neverError")) or node.get("onError") == "continueRegularOutput"
        if swallows:
            found.append(str(node.get("name") or "unnamed"))
    return sorted(found)


def saves_no_success_data(workflow: Dict[str, Any]) -> bool:
    """True when a successful run of this workflow leaves nothing to read.

    ``DEVON Drive Draft Writer`` sets ``saveDataSuccessExecution: none``. A
    refusal there is therefore invisible to ANY execution reader, this one
    included, and no amount of scanning fixes it. That is named in the output
    rather than skipped quietly, because a blind spot reported as coverage is
    the failure this whole script exists to prevent. The refusal is not lost:
    it rides back on the job envelope as ``refused`` with its reason, so the
    state ledger holds it even though the execution list does not.
    """
    settings = workflow.get("settings")
    settings = settings if isinstance(settings, dict) else {}
    return settings.get("saveDataSuccessExecution") == "none"


def refusals_in_run_data(
    run_data: Any,
    node_names: Sequence[str],
    max_items: int = 8,
) -> List[Tuple[str, str]]:
    """Provider refusals sitting inside a successful execution's node output.

    A node with ``fullResponse`` emits ``{statusCode, headers, body}``, so the
    refusal is a plain integer on the item rather than an error on the run. The
    status code is read first because it is unambiguous; the body's message is
    read only when the code says nothing, which is the shape a provider takes
    when it answers 200 with an error object.

    ``max_items`` bounds the walk. Node output is model output and therefore
    attacker shaped in the same sense a long draft is: unbounded iteration over
    it is how a watchdog becomes the outage.
    """
    if not isinstance(run_data, dict):
        return []
    wanted = set(node_names)
    out: List[Tuple[str, str]] = []
    for name, runs in run_data.items():
        if name not in wanted or not isinstance(runs, list):
            continue
        seen = 0
        for run in runs:
            if not isinstance(run, dict):
                continue
            main = ((run.get("data") or {}) if isinstance(run.get("data"), dict) else {}).get("main")
            if not isinstance(main, list):
                continue
            for branch in main:
                if not isinstance(branch, list):
                    continue
                for item in branch:
                    if seen >= max_items:
                        break
                    seen += 1
                    if not isinstance(item, dict):
                        continue
                    payload = item.get("json")
                    if not isinstance(payload, dict):
                        continue
                    code = payload.get("statusCode")
                    kind = classify(None, code) if code is not None else None
                    if kind is None:
                        body = payload.get("body")
                        message = ""
                        if isinstance(body, dict):
                            err = body.get("error")
                            if isinstance(err, dict):
                                message = str(err.get("message") or "")
                            elif isinstance(err, str):
                                message = err
                            if not message:
                                message = str(body.get("message") or "")
                        kind = classify(message) if message else None
                    if kind is not None:
                        out.append((str(name), kind))
    return out

def _blind_note(blind: Sequence[str]) -> str:
    """The sentence that says what this script could not look at.

    Empty when there is nothing to disclose, so a clean estate reads clean.
    """
    names = sorted({str(b) for b in blind if str(b).strip()})
    if not names:
        return ""
    return (
        f" NOT WATCHED: {', '.join(names)} save no data on a successful run, and each "
        "turns a provider refusal into ordinary data rather than an error, so a "
        "refusal there leaves no execution for this or any other execution reader to "
        "find. It does reach the state ledger as a refused envelope with its reason."
    )


def verdict(
    failures: Sequence[Dict[str, Any]],
    now: datetime,
    window_h: float = WINDOW_H,
    truncated: bool = False,
    blind: Sequence[str] = (),
) -> Tuple[int, str]:
    """Exit code and the line a human reads, from failures already fetched.

    Each failure is ``{id, workflow_id, node, started_at, kind}``, from either
    the error list or the soft failure scan; both shapes are identical on
    purpose so the judgement below does not care which one found it.

    ``blind`` names workflows whose refusals this script CANNOT see, because
    they save no data on a successful run. It is carried into both the OK and
    the ALARM line rather than only the OK one: a live alarm does not make the
    unwatched lane watched, and a reader who assumes it does is exactly the
    reader this script is written for. Pure, so the decision is testable
    without a network or a key.
    """
    cutoff = now - timedelta(hours=window_h)
    in_window = []
    for f in failures:
        stamp = parse_iso(f.get("started_at"))
        if stamp is not None and stamp >= cutoff:
            item = dict(f)
            item["_stamp"] = stamp
            in_window.append(item)

    blocking = [f for f in in_window if f.get("kind") in (PAYMENT, AUTH)]
    rated = [f for f in in_window if f.get("kind") == RATE]

    if not blocking:
        tail = ""
        if rated:
            tail = (
                f" {len(rated)} rate limited run(s) in the window, which is reported "
                "rather than alarmed on because a rate limit usually clears itself."
            )
        if truncated:
            tail += (
                f" NOTE: the error list came back at the {MAX_OPEN} row cap, so only the "
                "newest were opened. A live refusal recurs and would be among them."
            )
        tail += _blind_note(blind)
        return OK, (
            f"OK: no payment or auth refusal in the last {window_h:.0f}h." + tail
        )

    oldest = min(f["_stamp"] for f in blocking)
    age_h = (now - oldest).total_seconds() / 3600.0
    nodes = sorted({str(f.get("node") or "unknown") for f in blocking})
    kinds = sorted({str(f.get("kind")) for f in blocking})
    workflows = sorted({str(f.get("workflow_id") or "unknown") for f in blocking})

    return ALARM, (
        f"ALARM: a model provider is refusing calls. {len(blocking)} run(s) in the last "
        f"{window_h:.0f}h failed with {'/'.join(kinds)}, the oldest {age_h:.1f}h ago at "
        f"{oldest.isoformat().replace('+00:00', 'Z')}. "
        f"Failing node(s): {', '.join(nodes)}. Workflow(s): {', '.join(workflows)}. "
        "A payment or auth refusal does not clear itself, so the content pipeline is "
        "starving now and will keep starving until the account is fixed. This is the "
        "second recorded time this class of failure has stopped the whole operation."
        + _blind_note(blind)
    )


def _caller(base: str, key: str):
    """One authenticated GET, shared by both fetch paths."""
    def call(path: str) -> Dict[str, Any]:
        request = urllib.request.Request(base.rstrip("/") + path)
        request.add_header("X-N8N-API-KEY", key)
        request.add_header("Accept", "application/json")
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    return call


def fetch_soft_failures(
    base: str,
    key: str,
    per_lane: int = MAX_SUCCESS_PER_LANE,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Refusals hiding in SUCCESSFUL runs, plus the lanes that cannot be read.

    The lanes are derived from the workflows themselves rather than listed
    here, so a new one written the same way is covered the day it lands. The
    per lane execution list is narrowed by ``workflowId`` on purpose: the
    estate's newest successful executions are overwhelmingly housekeeping, and
    an unfiltered list of the newest twenty would be heartbeats and janitor
    passes with no chat turn among them.
    """
    call = _caller(base, key)

    workflows: List[Dict[str, Any]] = []
    cursor = ""
    for _ in range(MAX_WORKFLOW_PAGES):
        path = "/api/v1/workflows?active=true&limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        page = call(path)
        workflows.extend(w for w in (page.get("data") or []) if isinstance(w, dict))
        cursor = str(page.get("nextCursor") or "")
        if not cursor:
            break

    failures: List[Dict[str, Any]] = []
    blind: List[str] = []
    for workflow in workflows:
        nodes = swallowing_provider_nodes(workflow)
        if not nodes:
            continue
        name = str(workflow.get("name") or workflow.get("id") or "unnamed")
        if saves_no_success_data(workflow):
            blind.append(name)
            continue
        workflow_id = str(workflow.get("id") or "")
        if not workflow_id:
            continue
        listing = call(
            f"/api/v1/executions?status=success&workflowId={urllib.parse.quote(workflow_id)}"
            f"&limit={int(per_lane)}"
        )
        for row in listing.get("data") or []:
            execution_id = row.get("id")
            if execution_id is None:
                continue
            detail = call(f"/api/v1/executions/{execution_id}?includeData=true")
            result = ((detail.get("data") or {}).get("resultData") or {})
            for node, kind in refusals_in_run_data(result.get("runData"), nodes):
                failures.append(
                    {
                        "id": execution_id,
                        "workflow_id": row.get("workflowId"),
                        "node": node,
                        "started_at": row.get("startedAt"),
                        "kind": kind,
                    }
                )
    return failures, sorted(set(blind))


def fetch_failures(base: str, key: str, limit: int = MAX_OPEN) -> Tuple[List[Dict[str, Any]], bool]:
    """Errored executions, opened far enough to read why they failed.

    Returns the failures and whether the list came back at the cap.
    """
    call = _caller(base, key)

    listing = call(f"/api/v1/executions?status=error&limit={int(limit)}")
    rows = listing.get("data") or []
    truncated = len(rows) >= limit

    failures: List[Dict[str, Any]] = []
    for row in rows:
        execution_id = row.get("id")
        if execution_id is None:
            continue
        detail = call(f"/api/v1/executions/{execution_id}?includeData=true")
        result = ((detail.get("data") or {}).get("resultData") or {})
        error = result.get("error") or {}
        kind = classify(error.get("message"), error.get("httpCode"))
        if kind is None:
            continue
        failures.append(
            {
                "id": execution_id,
                "workflow_id": row.get("workflowId"),
                "node": result.get("lastNodeExecuted"),
                "started_at": row.get("startedAt"),
                "kind": kind,
            }
        )
    return failures, truncated


def main(argv: Optional[List[str]] = None) -> int:
    del argv
    base = os.environ.get("N8N_VPS_URL", "").strip() or DEFAULT_BASE_URL
    key = os.environ.get("N8N_VPS_KEY", "").strip()
    if not key:
        print(
            "CANNOT CHECK: N8N_VPS_KEY is not set, so no execution can be read. "
            "A watchdog that skipped quietly when unconfigured would report green "
            "while watching nothing.",
            file=sys.stderr,
        )
        return CANNOT_CHECK

    try:
        failures, truncated = fetch_failures(base, key)
        soft, blind = fetch_soft_failures(base, key)
    except urllib.error.HTTPError as exc:
        print(f"CANNOT CHECK: the executions API answered HTTP {exc.code}.", file=sys.stderr)
        return CANNOT_CHECK
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"CANNOT CHECK: the executions API could not be read ({exc}).", file=sys.stderr)
        return CANNOT_CHECK

    code, line = verdict(
        list(failures) + list(soft),
        datetime.now(timezone.utc),
        truncated=truncated,
        blind=blind,
    )
    print(line, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
