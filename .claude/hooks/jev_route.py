#!/usr/bin/env python3
"""
Ask Jev two questions about a tool call before it runs.

Ruled by Tee 2026-10-16, over a recommendation to hold it. Jev is TypeSafe's
typed decision model, called at POST https://api.typesafe.ai/v1/systemone with
a Bearer key. The request and answer shapes below were checked against
TypeSafe's live OpenAPI spec (api.typesafe.ai/openapi.json, version 0.2.0) and
the official typesafe-sdk 0.7.5 on 2026-10-16. No authenticated call had been
made when this was written.

Each call asks two independent noul questions in one request, as the TypeSafe
skill advises for judgments that can both hold:

    better_tool  a dedicated tool (Read, Grep, Glob, Edit, Write) would do
                 this step better than the tool being called
    needs_human  the step changes something outside the repository or cannot
                 be undone

A noul is the probability of yes. At or above CONFIDENCE, needs_human asks Tee
and, failing that, better_tool denies the call with a reason. Every other
answer prints nothing and the normal permission flow runs. The hook never
prints allow, because allow would skip the permission system: it can narrow
what runs and never widen it. With ENFORCE false it prints nothing at all and
only records what it would have decided.

What it cannot do. It cannot pick the tool, choose a path or retry. Jev answers
typed questions and writes no text, and no hook can swap one tool for another.

It fails open. With no TYPESAFE_API_KEY, a refused host, a redirect, the
deadline passing, an HTTP error or a malformed answer, it prints nothing and
the call runs exactly as it would without this file. So a quiet hook proves
nothing. Every outcome is written to .claude/ledger/jev-route.jsonl, the only
evidence that Jev decided anything. A deny is printed only after its ledger
row is written, because that row is what lets the identical call through the
second time.

What leaves the container: the tool name and at most MAX_INPUT characters of
its input. Every string in the input is scrubbed on its own, as raw text,
before anything is joined or encoded, first by gate_ledger.scrub and then by
the outbound rules below. If the scrubber cannot load, nothing is sent. The
ledger keeps a hash of the input, never the input.

CONFIDENCE is a starting guess, to be set from the ledger once real answers
exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
CONFIDENCE = 0.8
DEADLINE_S = 2.5
MAX_INPUT = 2000
SCRUB_SLICE = MAX_INPUT + 512
ENFORCE = False

STATE_NOTE = (
    "`tool_name` is the tool a coding agent is about to call and `tool_input` "
    "is its input, one `key: value` per line. The agent also has dedicated "
    "tools: Read reads a file, Grep searches file contents, Glob finds files "
    "by name, Edit changes part of a file and Write creates one."
)

QUESTIONS = {
    "better_tool": {
        "type": "noul",
        "instructions": STATE_NOTE + " Would one of those dedicated tools do this step better than `tool_name`?",
        "criteria": {
            "true": (
                "A dedicated tool does the same thing more directly, for example "
                "cat, head, grep, find or sed run through Bash only to read, "
                "search, list or edit files."
            ),
            "false": (
                "The step needs this tool: it runs a program, a test, a build, git, "
                "a network call, or a pipeline that no dedicated tool performs, or "
                "the tool already is the dedicated one."
            ),
        },
    },
    "needs_human": {
        "type": "noul",
        "instructions": STATE_NOTE + " Does this step change something outside the repository, or something that cannot be undone?",
        "criteria": {
            "true": (
                "It deploys, publishes, sends a message to a person, moves money, "
                "deletes or overwrites data outside the repository, force pushes, "
                "or changes a live service or its credentials."
            ),
            "false": (
                "It reads, or it changes only files in the working tree that git "
                "can restore, or it runs a local check."
            ),
        },
    },
}

# Applied after gate_ledger.scrub, to every string on its way out. They cover
# shapes the gate's scrubber was not built for, because the gate's text stays
# in the container and this text does not.
OUTBOUND_SHAPES = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S),
    re.compile(r"\b(?:github_pat|gh[pousr])_[A-Za-z0-9_]{20,}"),
    re.compile(r"\b[A-Za-z0-9_]*(?:api|key|token|secret)[A-Za-z0-9_]*_[0-9a-fA-F]{24,}\b"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    re.compile(r"(?<![A-Za-z0-9/+=])(?=[A-Za-z0-9/+=]*\d)(?=[A-Za-z0-9/+=]*[A-Za-z])[A-Za-z0-9/+=]{36,}(?![A-Za-z0-9/+=])"),
]


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def ledger_path():
    return os.path.join(project_dir(), ".claude", "ledger", "jev-route.jsonl")


def load_scrub():
    """The gate ledger's scrubber, or None. Without it nothing is sent."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        from gate_ledger import scrub
        return scrub
    except Exception:
        return None


def outbound(text, scrub):
    """One string, scrubbed raw. The slice before scrubbing bounds its cost."""
    text = scrub(str(text)[:SCRUB_SLICE])
    for shape in OUTBOUND_SHAPES:
        text = shape.sub("[REDACTED]", text)
    return text


def leaves(value, path=""):
    """Every scalar in a nested input, with its dotted path, never JSON encoded."""
    if isinstance(value, dict):
        for k in value:
            yield from leaves(value[k], "%s.%s" % (path, k) if path else str(k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from leaves(v, "%s[%d]" % (path, i))
    else:
        yield path, "" if value is None else str(value)


def call_text(tool_input, scrub):
    """Short values first, so a path survives the cut when a body is long."""
    pairs = [(p, outbound(v, scrub)) for p, v in leaves(tool_input if tool_input is not None else "")]
    pairs.sort(key=lambda pv: len(pv[1]))
    return "\n".join("%s: %s" % (p, v) if p else v for p, v in pairs)[:MAX_INPUT]


def endpoint_ok(url):
    """HTTPS only, except plain HTTP to loopback for the test stub."""
    parsed = urllib.parse.urlparse(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


def ask_jev(body, key, endpoint, timeout):
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read(1 << 20).decode("utf-8"))


def ask_within(body, key, endpoint, deadline):
    """The whole call, DNS and every read included, inside one deadline."""
    box = {}

    def work():
        try:
            box["response"] = ask_jev(body, key, endpoint, deadline)
        except BaseException as exc:
            box["error"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        raise TimeoutError("no answer inside %.1fs" % deadline)
    if "error" in box:
        raise box["error"]
    return box["response"]


def read_answers(response):
    """(better_tool, needs_human, model), or ValueError on any shape it does not know."""
    model = response.get("model")
    if not isinstance(model, str) or not model.startswith("jev-"):
        raise ValueError("model is not a jev model: %r" % (model,))
    answers = response.get("answers") or {}
    values = []
    for name in ("better_tool", "needs_human"):
        answer = answers.get(name) or {}
        p = answer.get("noul")
        if answer.get("type") != "noul" or isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
            raise ValueError("bad %s answer: %r" % (name, answer))
        values.append(float(p))
    return values[0], values[1], model


def decision_for(better_tool, needs_human):
    if needs_human >= CONFIDENCE:
        return "ask"
    if better_tool >= CONFIDENCE:
        return "deny"
    return None


def denied_before(session, digest):
    try:
        with open(ledger_path(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if (row.get("session") == session and row.get("input_sha") == digest
                        and row.get("decision") == "deny" and row.get("enforced")):
                    return True
    except OSError:
        return False
    return False


def write_row(row):
    """True only when the row is on disk."""
    try:
        path = ledger_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return True
    except Exception as exc:
        sys.stderr.write("jev_route: ledger write failed: %s: %s\n" % (type(exc).__name__, exc))
        return False


def output(decision, tool_name, p):
    if decision == "deny":
        reason = (
            "Jev (p=%.2f) reads this %s call as one a dedicated tool does better. "
            "Use Read, Grep, Glob, Edit or Write for this step. If none of them "
            "can do it, run the same call again: Jev denies an identical call "
            "only once per session." % (p, tool_name)
        )
    else:
        reason = (
            "Jev (p=%.2f) reads this %s call as changing something outside the "
            "repository or something that cannot be undone." % (p, tool_name)
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def run(payload, key=None, endpoint=None, now=None, scrub=None, timeout=None):
    """Returns the JSON object to print on stdout, or None to print nothing."""
    now = now or datetime.now(timezone.utc)
    endpoint = endpoint or ENDPOINT
    deadline = DEADLINE_S if timeout is None else timeout
    name = payload.get("tool_name", "")
    session = payload.get("session_id", "")
    row = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session,
        "tool": name,
        "enforced": ENFORCE,
        "decision": "none",
    }

    if not key:
        row["outcome"] = "no_key"
        write_row(row)
        return None
    if not endpoint_ok(endpoint):
        row.update(outcome="error", error="endpoint refused")
        write_row(row)
        return None
    if scrub is None:
        row.update(outcome="error", error="scrubber did not load, nothing sent")
        write_row(row)
        return None

    text = call_text(payload.get("tool_input"), scrub)
    digest = hashlib.sha256((name + "\0" + text).encode("utf-8")).hexdigest()[:16]
    row["input_sha"] = digest

    if denied_before(session, digest):
        row["outcome"] = "repeat_pass"
        write_row(row)
        return None

    body = {
        "model": MODEL,
        "state": {"tool_name": name, "tool_input": text},
        "questions": QUESTIONS,
    }
    started = time.monotonic()
    try:
        better_tool, needs_human, model = read_answers(ask_within(body, key, endpoint, deadline))
    except urllib.error.HTTPError as exc:
        row.update(outcome="error", error="HTTP %d" % exc.code)
    except Exception as exc:
        row.update(outcome="error", error="%s: %s" % (type(exc).__name__, str(exc)[:200]))
    else:
        row.update(outcome="answered", better_tool=better_tool, needs_human=needs_human, model=model)
        decision = decision_for(better_tool, needs_human)
        if decision:
            row["decision"] = decision
    row["latency_ms"] = int((time.monotonic() - started) * 1000)

    persisted = write_row(row)
    if row["decision"] == "none" or not ENFORCE:
        return None
    if row["decision"] == "deny" and not persisted:
        return None
    p = row["needs_human"] if row["decision"] == "ask" else row["better_tool"]
    return output(row["decision"], name, p)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        out = run(payload, key=os.environ.get("TYPESAFE_API_KEY", ""), scrub=load_scrub())
    except Exception as exc:
        sys.stderr.write("jev_route: %s: %s\n" % (type(exc).__name__, exc))
        out = None
    if out is not None:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
