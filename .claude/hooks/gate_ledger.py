#!/usr/bin/env python3
"""Gate and ledger for outward, hard to undo tool calls.

Ruled by Tee 2026-10-14, after a read of all 67 cloud sessions found 1,810
outward high tier calls and, among them, 45 merges, 49 workflow edits, 36
publishes, 29 workflow executions and 29 force pushes that ran with no answered
card and no message from Tee in the 30 minutes before.

Two jobs, one file.

  pre   PreToolUse. A GATED call is refused unless a human signal exists inside
        WINDOW_MIN minutes before it: a message Tee typed, or an answered
        AskUserQuestion card. Every other call passes. Every decision is logged.
  post  PostToolUse. Appends the executed call to the ledger.
  fail  PostToolUseFailure. Appends the failed call to the ledger.

Design choices that are rulings, not defaults:

  * The gate FAILS CLOSED. If the transcript cannot be read, a gated call is
    refused with that reason. A gate that fails open reports safety while
    watching nothing, which is the failure this repository's watchdogs were
    built around. Only gated calls are affected, so a broken reader cannot lock
    the session out of reading or editing files.
  * There is no environment switch and no flag that disables it. Compliance
    items have no exception path. Changing what is gated means editing GATED
    below, in a commit.
  * Merges are ledger only. Tee's standing merge approval of 2026-10-11 covers
    them, and the CI green condition lives in CLAUDE.md, where a hook cannot
    check it.
  * A signal counts only if it is Tee's. Webhook turns, scheduled check-ins,
    task notifications, peer agent reports and summaries all arrive as user
    turns in the transcript and none of them is a person. The discriminator is
    origin.kind == "human" on the entry. A transcript with no origin field at
    all (an older format) falls back to a prefix test.

The ledger is JSON lines at .claude/ledger/gate-ledger.jsonl under the project
directory. It lives in the container, which is reclaimed after inactivity, so it
is a record of the session, not a durable archive. Long strings in it are
scrubbed of anything shaped like a token before they are written.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

WINDOW_MIN = 30

# Tool name suffixes, matched after the last "__" so a connector that arrives
# under a UUID instead of a name is still caught. The list is the executed
# high tier outward set from the 2026-10-14 audit, less merges.
GATED_SUFFIXES = {
    "publish_workflow",
    "unpublish_workflow",
    "archive_workflow",
    "execute_workflow",
    "update_workflow",
    "restore_workflow_version",
    "rename_data_table",
    "rename_data_table_column",
    "set-variables",
    "actions_run_trigger",
    "update_bot",
    "create_bot",
    "give_bot_n8n",
    "update_records_for_table",
    "create_records_for_table",
    "delete_records_for_table",
    "update_field",
    "create_field",
    "trash_file",
    "deploy_to_vercel",
    "create_deployment",
    "create-deployment",
    "create_git_project",
    "redeploy",
    "restart-service",
    "railway-agent",
    "apply_migration",
    "execute_sql",
    "submit_media_job",
    "DNS_updateDNSRecordsV1",
}
# Hostinger VPS tools are gated when the verb mutates.
VPS_MUTATING = re.compile(
    r"^VPS_(create|delete|update|restart|recreate|stop|start|purchase|set|attach|detach|restore)",
    re.I,
)
# send_message is gated only on the Rakazo bot platform. The Claude Code Remote
# send_message is a message to a sibling session, which is not outward.
RAKAZO_PREFIX = "mcp__Rakazo__"

# Ledger only: recorded, never refused.
LEDGER_ONLY_SUFFIXES = {"merge_pull_request", "test_workflow"}

SHELL_SPLIT = re.compile(r"&&|\|\||;|\||\n")
LOCAL_HOST = re.compile(r"^(https?://)?(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|\[::1\])([:/]|$)", re.I)

TOKEN_SHAPES = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),
    re.compile(r"\b(?:sk|pk|csk|key|ghp|gho|ghs|xox[bp]|AKIA)[-_][A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(authorization|bearer|api[_-]?key|key|token|secret|password)(['\":= ]+)([^\s'\",}]{8,})"),
    re.compile(r"\b[A-Za-z0-9+=_-]{40,}\b"),
]


def scrub(text):
    text = str(text)
    for shape in TOKEN_SHAPES:
        if shape.groups >= 3:
            text = shape.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)
        else:
            text = shape.sub("[REDACTED]", text)
    return text


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def ledger_path():
    return os.path.join(project_dir(), ".claude", "ledger", "gate-ledger.jsonl")


# --------------------------------------------------------------- classification


def _segments(command):
    return [s.strip() for s in SHELL_SPLIT.split(command) if s.strip()]


def _current_branch(cwd):
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd or None, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _push_force_kind(segment, cwd):
    """Returns (kind, target) for a git push segment, or None.

    kind is "plain" for --force or -f, "lease" for --force-with-lease, "plus"
    for a +refspec, "none" for a push with no force. target is the branch the
    push writes, "" when it cannot be told.
    """
    tokens = segment.split()
    if "git" not in tokens or "push" not in tokens:
        return None
    gi = tokens.index("git")
    rest = tokens[gi + 1:]
    if "push" not in rest:
        return None
    args = rest[rest.index("push") + 1:]
    kind = "none"
    positional = []
    for a in args:
        if a == "--force" or a == "-f" or (re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a) and not a.startswith("--")):
            kind = "plain"
        elif a.startswith("--force-with-lease") or a == "--force-if-includes":
            if kind != "plain":
                kind = "lease"
        elif a.startswith("-"):
            continue
        else:
            positional.append(a)
    # positional is [remote, refspec...]
    refspecs = positional[1:] if len(positional) > 1 else []
    target = ""
    for spec in refspecs:
        if spec.startswith("+"):
            if kind == "none":
                kind = "plus"
            spec = spec[1:]
        dst = spec.split(":")[-1]
        dst = re.sub(r"^refs/heads/", "", dst)
        if dst == "HEAD" or not dst:
            dst = _current_branch(cwd)
        target = dst
    if not refspecs:
        target = _current_branch(cwd)
    return kind, target


def _curl_mutating(segment):
    tokens = segment.split()
    if "curl" not in tokens:
        return False
    body = segment
    mutating = bool(
        re.search(r"(?:^|\s)-X\s*(POST|PUT|PATCH|DELETE)\b", body, re.I)
        or re.search(r"--request\s+(POST|PUT|PATCH|DELETE)\b", body, re.I)
        or re.search(r"(?:^|\s)(-d|--data|--data-raw|--data-binary|--data-urlencode|-F|--form|-T|--upload-file)\b", body)
    )
    if not mutating:
        return False
    urls = re.findall(r"https?://[^\s'\"]+", body)
    if not urls:
        return True
    return not all(LOCAL_HOST.match(u) for u in urls)


def classify(tool_name, tool_input, cwd=""):
    """Returns (cls, gated). cls is None for a call that is not tracked."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    suffix = tool_name.rsplit("__", 1)[-1] if tool_name.startswith("mcp__") else tool_name

    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        classes = []
        gated = False
        for seg in _segments(command):
            push = _push_force_kind(seg, cwd)
            if push:
                kind, target = push
                if kind == "none":
                    classes.append("git_push")
                else:
                    classes.append("git_force_push:" + kind)
                    protected = target in ("main", "master", "")
                    own = target.startswith("claude/")
                    if kind == "plain" or protected or not own:
                        gated = True
            elif _curl_mutating(seg):
                classes.append("curl_mutating")
                gated = True
            elif re.search(r"\bgit\s+reset\s+--hard\b", seg):
                classes.append("git_reset_hard")
            elif re.search(r"\bgit\s+branch\s+-[dD]\b", seg):
                classes.append("git_branch_delete")
            elif re.search(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)\b", seg):
                classes.append("rm_recursive")
        if not classes:
            return None, False
        return ",".join(classes), gated

    if not tool_name.startswith("mcp__"):
        return None, False
    if suffix in LEDGER_ONLY_SUFFIXES:
        return suffix, False
    if suffix in GATED_SUFFIXES:
        return suffix, True
    if suffix == "send_message" and tool_name.startswith(RAKAZO_PREFIX):
        return suffix, True
    if VPS_MUTATING.match(suffix):
        return suffix, True
    return None, False


# ------------------------------------------------------------------ the signal


NOT_HUMAN_PREFIXES = (
    "<system-reminder", "[SYSTEM NOTIFICATION", "<task-notification", "<wake",
    "Another Claude session sent a message", "<agent-message", "[Request interrupted",
    "This session is being continued", "<command-name>", "<local-command",
)


def _parse_ts(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _is_human(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    return not content.lstrip().startswith(NOT_HUMAN_PREFIXES)


def main_transcript(path):
    """A subagent's hook can point at a file under <session>/subagents/. The
    person spoke in the parent file, so read that one."""
    if "/subagents/" in path:
        parent = os.path.dirname(os.path.dirname(path)) + ".jsonl"
        return parent
    return path


def latest_signal(path, now):
    """Returns (signal_kind, age_minutes) of the newest human signal, or None
    when the transcript holds none. Raises when it cannot be read."""
    card_ids = set()
    newest = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line, strict=False)
            except Exception:
                continue
            ts = _parse_ts(entry.get("timestamp"))
            if ts is None:
                continue
            kind = None
            if _is_human(entry):
                kind = "message"
            elif entry.get("type") == "assistant":
                blocks = (entry.get("message") or {}).get("content")
                if isinstance(blocks, list):
                    for b in blocks:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                            card_ids.add(b.get("id"))
            elif entry.get("type") == "user":
                blocks = (entry.get("message") or {}).get("content")
                if isinstance(blocks, list):
                    for b in blocks:
                        if (
                            isinstance(b, dict)
                            and b.get("type") == "tool_result"
                            and b.get("tool_use_id") in card_ids
                            and not b.get("is_error")
                        ):
                            kind = "card"
            if kind and (newest is None or ts > newest[1]):
                newest = (kind, ts)
    if newest is None:
        return None
    return newest[0], (now - newest[1]).total_seconds() / 60.0


def decide(cls, gated, payload, now):
    """Returns (allow, reason, signal). Pure apart from reading the transcript."""
    if not gated:
        return True, "not gated", None
    path = payload.get("transcript_path") or ""
    if not path:
        return False, "the hook input carried no transcript_path, so no human signal could be checked", None
    try:
        sig = latest_signal(main_transcript(path), now)
    except Exception as exc:
        return False, "the transcript could not be read (%s: %s)" % (type(exc).__name__, exc), None
    if sig is None:
        return False, "the session holds no message from Tee and no answered card", None
    kind, age = sig
    if age <= WINDOW_MIN:
        return True, "%s %.1f min ago" % (kind, age), sig
    return False, "the newest human signal is a %s %.0f min old, outside the %d min window" % (kind, age, WINDOW_MIN), sig


# ----------------------------------------------------------------------- ledger


def summarize(tool_name, tool_input):
    if tool_name == "Bash":
        return scrub(str((tool_input or {}).get("command", "")))[:400]
    try:
        return scrub(json.dumps(tool_input, default=str, sort_keys=True))[:400]
    except Exception:
        return ""


def write_ledger(row):
    path = ledger_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _row(event, payload, cls, gated, now, **extra):
    row = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "session": payload.get("session_id", ""),
        "agent": payload.get("agent_id", ""),
        "tool": payload.get("tool_name", ""),
        "class": cls,
        "gated": gated,
        "input": summarize(payload.get("tool_name", ""), payload.get("tool_input")),
    }
    row.update(extra)
    return row


def run(mode, payload, now=None):
    """Returns the JSON object to print on stdout, or None to print nothing."""
    now = now or datetime.now(timezone.utc)
    name = payload.get("tool_name", "")
    cls, gated = classify(name, payload.get("tool_input"), payload.get("cwd", ""))
    if cls is None:
        return None

    if mode == "pre":
        allow, reason, _sig = decide(cls, gated, payload, now)
        write_ledger(_row("gate-allow" if allow else "gate-deny", payload, cls, gated, now, reason=reason))
        if allow:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Gate refused %s (%s): %s. Put the decision to Tee on an "
                    "AskUserQuestion card with the recommended option first, wait "
                    "for the answer, then retry. Do not rephrase the call to get "
                    "around the gate." % (name, cls, reason)
                ),
            }
        }

    event = "executed" if mode == "post" else "failed"
    extra = {}
    if mode == "fail":
        extra["error"] = scrub(str(payload.get("error", "")))[:300]
    write_ledger(_row(event, payload, cls, gated, now, **extra))
    return None


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode not in ("pre", "post", "fail"):
        sys.stderr.write("usage: gate_ledger.py pre|post|fail\n")
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        out = run(mode, payload)
    except Exception as exc:
        if mode == "pre":
            name = payload.get("tool_name", "")
            try:
                tracked = classify(name, payload.get("tool_input"), payload.get("cwd", ""))
            except Exception:
                tracked = ("unknown", True)
            if tracked[1]:
                out = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "Gate failed closed on a gated call: %s: %s" % (type(exc).__name__, exc)
                        ),
                    }
                }
            else:
                out = None
        else:
            sys.stderr.write("ledger write failed: %s: %s\n" % (type(exc).__name__, exc))
            out = None
    if out is not None:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
