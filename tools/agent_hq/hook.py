#!/usr/bin/env python3
"""Agent HQ hook: one JSON line per Claude Code hook event, then exit 0.

Claude Code pipes the hook payload to stdin. This script appends a row to
~/.agent-hq/events.jsonl (or AGENT_HQ_DIR), makes no network call, prints
nothing, and swallows every error, so a session is never blocked by it. The
prompt text is never written; only the fact that a prompt was submitted.

Row: t, event, session_id, cwd, transcript_path, bot (the roster name matched
by agent type or by folder), plus message and notification_type on a
Notification, source and reason where the event carries them, the subagent
fields on SubagentStop, and summary (the last assistant message, 200 chars).
"""
import json
import os
import sys
from datetime import datetime

READ_LIMIT = 1_000_000
SUMMARY_CHARS = 200
MESSAGE_CHARS = 300
PASSTHROUGH = ("source", "reason", "notification_type", "title", "agent_type", "agent_id",
               "agent_transcript_path", "stop_hook_active", "permission_mode")


def pick_bot(roster, cwd, agent_type):
    """The roster bot for this event: the agent by name, else the longest folder match."""
    bots = roster.get("bots", []) if isinstance(roster, dict) else []
    bots = [b for b in bots if isinstance(b, dict) and not b.get("retired")]
    if agent_type:
        for bot in bots:
            if bot.get("kind") == "agent" and bot.get("name") == agent_type:
                return bot.get("name")
    best = None
    if cwd:
        for bot in bots:
            lane = bot.get("cwd")
            if bot.get("kind") != "session" or not isinstance(lane, str) or not lane:
                continue
            lane = lane.rstrip("/")
            if cwd == lane or cwd.startswith(lane + "/"):
                if best is None or len(lane) > len(str(best.get("cwd") or "").rstrip("/")):
                    best = bot
    if best is not None:
        return best.get("name")
    return os.path.basename(cwd.rstrip("/")) if cwd else None


def build_row(payload, roster, cwd_fallback):
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else cwd_fallback
    event = payload.get("hook_event_name") or "unknown"
    row = {
        "t": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": str(event),
        "session_id": payload.get("session_id"),
        "cwd": cwd,
        "transcript_path": payload.get("transcript_path"),
        "bot": pick_bot(roster, cwd, payload.get("agent_type")),
    }
    for key in PASSTHROUGH:
        value = payload.get(key)
        if value not in (None, ""):
            row[key] = value
    if event == "Notification":
        row["message"] = " ".join(str(payload.get("message") or "").split())[:MESSAGE_CHARS]
    last = payload.get("last_assistant_message")
    if isinstance(last, str) and last.strip():
        row["summary"] = " ".join(last.split())[:SUMMARY_CHARS]
    return row


def main():
    try:
        raw = "" if sys.stdin.isatty() else sys.stdin.read(READ_LIMIT)
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        hq_dir = os.environ.get("AGENT_HQ_DIR") or os.path.join(os.path.expanduser("~"), ".agent-hq")
        os.makedirs(hq_dir, exist_ok=True)
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
        with open(os.path.join(hq_dir, "events.jsonl"), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
