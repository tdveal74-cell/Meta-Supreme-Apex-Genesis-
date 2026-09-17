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


def verdict(
    failures: Sequence[Dict[str, Any]],
    now: datetime,
    window_h: float = WINDOW_H,
    truncated: bool = False,
) -> Tuple[int, str]:
    """Exit code and the line a human reads, from failures already fetched.

    Each failure is ``{id, workflow_id, node, started_at, kind}``. Pure, so the
    decision is testable without a network or a key.
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
    )


def fetch_failures(base: str, key: str, limit: int = MAX_OPEN) -> Tuple[List[Dict[str, Any]], bool]:
    """Errored executions, opened far enough to read why they failed.

    Returns the failures and whether the list came back at the cap.
    """
    def call(path: str) -> Dict[str, Any]:
        request = urllib.request.Request(base.rstrip("/") + path)
        request.add_header("X-N8N-API-KEY", key)
        request.add_header("Accept", "application/json")
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)

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
    except urllib.error.HTTPError as exc:
        print(f"CANNOT CHECK: the executions API answered HTTP {exc.code}.", file=sys.stderr)
        return CANNOT_CHECK
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"CANNOT CHECK: the executions API could not be read ({exc}).", file=sys.stderr)
        return CANNOT_CHECK

    code, line = verdict(failures, datetime.now(timezone.utc), truncated=truncated)
    print(line, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
