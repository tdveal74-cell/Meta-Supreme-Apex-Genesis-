#!/usr/bin/env python3
"""Agent HQ hook: one JSON line per Claude Code hook event, then exit 0.

Claude Code pipes the hook payload to stdin. This script appends a row to
~/.agent-hq/events.jsonl (or AGENT_HQ_DIR), makes no network call, prints
nothing, and swallows every error, so a session is never blocked by it. The
prompt text is never written; only the fact that a prompt was submitted.

Row: time, event, session_id, cwd, bot (the roster name matched by agent type
or by folder, else the folder name) and transcript_path (the token counter
reads it). Added where the event carries them: message on a Notification;
notification_type, title, source, reason, agent_type, agent_id,
agent_transcript_path and stop_hook_active (a boolean); and summary, the
first 200 characters of the last assistant message on Stop and SubagentStop,
which feeds "Finished today". Every added text value is cut at 300
characters. The directory is kept 0700 and the file 0600 on every write,
because the rows hold conversation excerpts.
"""
import json
import os
import sys
from datetime import datetime

READ_LIMIT = 1_000_000
SUMMARY_CHARS = 200
VALUE_CHARS = 300
PASSTHROUGH = ("source", "reason", "notification_type", "title", "agent_type", "agent_id",
               "agent_transcript_path", "stop_hook_active")


def _text(value, limit):
    return " ".join(str(value).split())[:limit]


def pick_bot(roster, cwd, agent_type):
    """The roster bot for this event: the agent by name, else the longest folder match."""
    bots = roster.get("bots", []) if isinstance(roster, dict) else []
    bots = [b for b in bots if isinstance(b, dict) and not b.get("retired")]
    if agent_type:
        for bot in bots:
            if bot.get("kind") == "agent" and (bot.get("agent_type") or bot.get("name")) == agent_type:
                return bot.get("name")
    best = None
    best_len = -1
    if cwd:
        for bot in bots:
            lane = bot.get("cwd")
            if bot.get("kind") != "session" or not isinstance(lane, str):
                continue
            lane = lane.rstrip("/")
            if not lane:
                continue
            if (cwd == lane or cwd.startswith(lane + "/")) and len(lane) > best_len:
                best, best_len = bot, len(lane)
    if best is not None:
        return best.get("name")
    return os.path.basename(cwd.rstrip("/")) if cwd else None


def build_row(payload, roster, cwd_fallback):
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else cwd_fallback
    event = payload.get("hook_event_name") or "unknown"
    transcript = payload.get("transcript_path")
    row = {
        "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "event": _text(event, 60),
        "session_id": _text(payload.get("session_id"), 120) if payload.get("session_id") else None,
        "cwd": cwd,
        "transcript_path": transcript if isinstance(transcript, str) else None,
        "bot": pick_bot(roster, cwd, payload.get("agent_type")),
    }
    for key in PASSTHROUGH:
        value = payload.get(key)
        if value in (None, ""):
            continue
        row[key] = value if isinstance(value, bool) else _text(value, VALUE_CHARS)
    if event == "Notification":
        row["message"] = _text(payload.get("message") or "", VALUE_CHARS)
    last = payload.get("last_assistant_message")
    if isinstance(last, str) and last.strip():
        row["summary"] = _text(last, SUMMARY_CHARS)
    return row


def main():
    try:
        raw = "" if sys.stdin.isatty() else sys.stdin.read(READ_LIMIT)
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        hq_dir = os.environ.get("AGENT_HQ_DIR") or os.path.join(os.path.expanduser("~"), ".agent-hq")
        hq_dir = os.path.abspath(os.path.expanduser(hq_dir))
        os.makedirs(hq_dir, mode=0o700, exist_ok=True)
        if os.stat(hq_dir).st_mode & 0o777 != 0o700:
            os.chmod(hq_dir, 0o700)
        try:
            with open(os.path.join(hq_dir, "roster.json"), encoding="utf-8") as handle:
                roster = json.load(handle)
        except Exception:
            roster = {}
        try:
            cwd_fallback = os.getcwd()
        except OSError:
            cwd_fallback = None
        row = build_row(payload, roster, cwd_fallback)
        fd = os.open(os.path.join(hq_dir, "events.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        if os.fstat(fd).st_mode & 0o777 != 0o600:
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
