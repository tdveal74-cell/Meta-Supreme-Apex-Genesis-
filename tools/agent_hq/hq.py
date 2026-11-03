#!/usr/bin/env python3
"""Agent HQ: a live 3D office for the Claude Code sessions on this machine.

One file, Python 3 standard library only, no network calls. The server binds
to 127.0.0.1 and reads only files under ~/.claude and ~/.agent-hq. Nothing it
reads leaves the machine.

    python3 hq.py up          install the hooks, build the roster if missing, serve
    python3 hq.py install     merge the hooks into ~/.claude/settings.json, copy files
    python3 hq.py roster      scan agents and session folders; print and merge roster.json
    python3 hq.py serve       serve the office on http://127.0.0.1:7777
    python3 hq.py state       print the current state once, as JSON
    python3 hq.py uninstall   remove the Agent HQ hooks, keep the data

Data lives in ~/.agent-hq (override with AGENT_HQ_DIR):
    roster.json    every bot with its job, model and team
    events.jsonl   one JSON line per hook event, written by hook.py
    hq.py hook.py index.html app.js vendor/    the installed copies

Status rules, per session, from events.jsonl and the session's transcript:
    waiting   a Notification since the last prompt that nothing has answered
              yet: no Stop after it and no transcript turn line after it. An
              idle_prompt notification reads as resting unless IDLE_IS_WAITING.
    resting   stopped, ended, no prompt yet, or quiet for STALE_AFTER_S
    working   mid turn, and the transcript grew inside STUCK_AFTER_S
    stuck     mid turn, nothing new for STUCK_AFTER_S (10 minutes)
A bot shows the highest of its sessions: waiting, then stuck, working, resting.

Tokens are summed from the usage field of every assistant line in the
transcripts the hooks name, once per message id (the transcript repeats a
message once per content block), bucketed by local day. Subagent transcripts
under <session>/subagents/ count toward the agent named by SubagentStop when
the roster has that agent, otherwise toward the parent session's bot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 7777
STUCK_AFTER_S = 600
STALE_AFTER_S = 24 * 3600
IDLE_IS_WAITING = False
ANSWER_GRACE_S = 5.0
STATE_TTL_S = 2.0
TAIL_BYTES = 256 * 1024
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Notification", "Stop", "SubagentStop", "SessionEnd")
HOOK_MARK = re.compile(r"agent-hq[}\"']?/hook\.py")
HOOK_COMMAND = 'python3 "${AGENT_HQ_DIR:-$HOME/.agent-hq}/hook.py" >/dev/null 2>&1 || true'
HOOK_TIMEOUT_S = 5
INSTALL_FILES = ("hq.py", "hook.py", "index.html", "app.js")
VENDOR_FILES = ("three.module.js", "three.core.js", "LICENSE")
TEAM_ORDER = ("Research", "Content", "Visuals", "Ops")
UNASSIGNED = "Unassigned"
TEAM_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Visuals", ("render", "video", "image", "thumbnail", "design", "carousel", "visual", "frame",
                 "shot", "avatar", "scene", "motion", "art", "photo", "film", "graphic", "animat")),
    ("Content", ("script", "writ", "draft", "copy", "episode", "podcast", "content", "story", "caption",
                 "voice", "canon", "brand", "viral", "tqo", "nco", "tsws", "short", "newsletter",
                 "post", "blog", "narrat")),
    ("Research", ("research", "scan", "read-only", "search", "audit", "verif", "analy", "investigat",
                  "review", "critic", "explor", "reader", "scout", "inspect")),
    ("Ops", ("deploy", "ci", "test", "fix", "edit", "editor", "pipeline", "workflow", "infra", "ops",
             "build", "registry", "steward", "hook", "release", "devops", "migrat", "monitor",
             "watchdog", "backup")),
)
STATUS_RANK = {"waiting": 3, "stuck": 2, "working": 1, "resting": 0}
TOKEN_KEYS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_create", "cache_creation_input_tokens"),
)
TOOL_DETAIL_KEYS = ("description", "file_path", "pattern", "query", "command", "url", "prompt",
                    "path", "skill", "name")


# --------------------------------------------------------------------------- paths and time


def default_hq_dir() -> Path:
    return Path(os.environ.get("AGENT_HQ_DIR") or (Path.home() / ".agent-hq")).expanduser()


def default_claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")).expanduser()


def now_iso(epoch: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(epoch) if epoch is not None else datetime.now()
    return dt.astimezone().isoformat(timespec="seconds")


def parse_ts(value: Any) -> Optional[float]:
    """ISO 8601 (with Z or an offset) or epoch seconds/milliseconds to epoch seconds."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value) / 1000.0 if value > 1e11 else float(value)
    text = str(value).strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.timestamp()


def local_day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d")


def squash(text: Any, limit: int = 200) -> str:
    out = " ".join(str(text or "").split())
    return out if len(out) <= limit else out[: limit - 1] + "…"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------- roster


def parse_frontmatter(text: str) -> Dict[str, str]:
    """The YAML front matter of an agent file, read without a YAML library.

    Handles `key: value`, quoted values and indented continuation lines, which
    is all an agent definition carries. Anything stranger is left as text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: Dict[str, str] = {}
    key: Optional[str] = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match and not line[:1].isspace():
            key, value = match.group(1), match.group(2).strip()
            if value in ("|", ">", "|-", ">-"):
                value = ""
            out[key] = _unquote(value)
        elif key and line[:1].isspace():
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def infer_team(*texts: Optional[str]) -> str:
    """First team whose keyword appears in the texts; Ops when none does.

    A keyword of four letters or fewer must be a whole word, so "ci" does not
    fire on "specific" and "post" does not fire on "postgres". A longer one is
    a stem matched at a word start, so "verif" covers verify and verifies.
    """
    blob = " ".join(t for t in texts if t).lower()
    for team, words in TEAM_RULES:
        for word in words:
            pattern = r"\b" + re.escape(word) + (r"\b" if len(word) <= 4 else "")
            if re.search(pattern, blob):
                return team
    return "Ops"


def project_dirs(claude_dir: Path) -> List[Tuple[Path, Optional[str]]]:
    """Each folder under ~/.claude/projects with the cwd its transcripts record."""
    root = claude_dir / "projects"
    if not root.is_dir():
        return []
    out: List[Tuple[Path, Optional[str]]] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        out.append((folder, _cwd_of_project(folder)))
    return out


def _newest_transcripts(folder: Path, limit: int) -> List[Path]:
    files = [p for p in folder.glob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _cwd_of_project(folder: Path) -> Optional[str]:
    for path in _newest_transcripts(folder, 5):
        try:
            with path.open("rb") as handle:
                for _ in range(400):
                    line = handle.readline()
                    if not line:
                        break
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    cwd = row.get("cwd") if isinstance(row, dict) else None
                    if isinstance(cwd, str) and cwd:
                        return cwd
        except OSError:
            continue
    return None


def observed_model(folder: Optional[Path]) -> Optional[str]:
    """The model named by the newest assistant line in the folder's newest transcript."""
    if folder is None:
        return None
    for path in _newest_transcripts(folder, 3):
        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                handle.seek(max(0, size - TAIL_BYTES))
                chunk = handle.read()
        except OSError:
            continue
        for line in reversed(chunk.splitlines()):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("type") != "assistant":
                continue
            msg = row.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("model"), str):
                return msg["model"]
    return None


def agent_bot(path: Path, cwd: Optional[str], scope: str) -> Dict[str, Any]:
    front = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    name = front.get("name") or path.stem
    job = front.get("description") or "No description in the agent file"
    return {
        "id": f"agent:{name}@{cwd or 'user'}",
        "name": name,
        "kind": "agent",
        "scope": scope,
        "job": job,
        "model": front.get("model") or "inherit",
        "team": infer_team(name, job),
        "source": str(path),
        "cwd": cwd,
        "tools": front.get("tools"),
    }


def lane_bot(cwd: str, model: Optional[str]) -> Dict[str, Any]:
    name = os.path.basename(cwd.rstrip("/")) or cwd
    return {
        "id": f"session:{cwd}",
        "name": name,
        "kind": "session",
        "scope": "folder",
        "job": f"Sessions run in {cwd}",
        "model": model or "unknown",
        "team": infer_team(name),
        "source": cwd,
        "cwd": cwd,
    }


def scan_roster(claude_dir: Path, extra_cwds: Iterable[str] = ()) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Every bot the machine shows: user agents, project agents, session folders."""
    notes: List[str] = []
    cwd_to_dir: Dict[str, Path] = {}
    for folder, cwd in project_dirs(claude_dir):
        if cwd:
            cwd_to_dir.setdefault(cwd, folder)
        else:
            notes.append(f"skipped {folder.name}: no transcript line carries a cwd")
    cwds = sorted(set(cwd_to_dir) | {c for c in extra_cwds if c})
    bots: List[Dict[str, Any]] = []
    user_agents = claude_dir / "agents"
    if user_agents.is_dir():
        for md in sorted(user_agents.glob("*.md")):
            bots.append(agent_bot(md, None, "user"))
    for cwd in cwds:
        agents_dir = Path(cwd) / ".claude" / "agents"
        if agents_dir.is_dir():
            for md in sorted(agents_dir.glob("*.md")):
                bots.append(agent_bot(md, cwd, "project"))
    for cwd in cwds:
        bots.append(lane_bot(cwd, observed_model(cwd_to_dir.get(cwd))))
    _disambiguate(bots)
    return bots, notes


def _disambiguate(bots: List[Dict[str, Any]]) -> None:
    seen: Dict[str, int] = {}
    for bot in bots:
        seen[bot["name"]] = seen.get(bot["name"], 0) + 1
    for bot in bots:
        if seen[bot["name"]] > 1 and bot.get("cwd"):
            parent = os.path.basename(os.path.dirname(bot["cwd"].rstrip("/")))
            bot["name"] = f"{bot['name']} ({parent})" if parent else bot["name"]


def merge_roster(existing: Optional[Dict[str, Any]], scanned: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep the user's edits (name, team, job), refresh what the files say, retire the gone."""
    old = {b.get("id"): b for b in (existing or {}).get("bots", []) if isinstance(b, dict) and b.get("id")}
    bots: List[Dict[str, Any]] = []
    seen = set()
    for bot in scanned:
        seen.add(bot["id"])
        prev = old.get(bot["id"])
        if prev:
            merged = dict(prev)
            for key in ("kind", "scope", "model", "source", "cwd", "tools"):
                if key in bot:
                    merged[key] = bot[key]
            merged.pop("retired", None)
            bots.append(merged)
        else:
            bots.append(dict(bot))
    for bot_id, prev in old.items():
        if bot_id not in seen:
            retired = dict(prev)
            retired["retired"] = True
            bots.append(retired)
    return {"version": 1, "generated": now_iso(), "bots": bots}


def load_roster(hq_dir: Path) -> Dict[str, Any]:
    path = hq_dir / "roster.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "bots": []}
    if not isinstance(data, dict) or not isinstance(data.get("bots"), list):
        return {"version": 1, "bots": []}
    data["bots"] = [b for b in data["bots"] if isinstance(b, dict) and b.get("name")]
    for bot in data["bots"]:
        bot.setdefault("id", f"{bot.get('kind', 'bot')}:{bot['name']}")
        bot.setdefault("team", UNASSIGNED)
        bot.setdefault("kind", "session")
    return data


def write_roster(hq_dir: Path, roster: Dict[str, Any]) -> Path:
    hq_dir.mkdir(parents=True, exist_ok=True)
    path = hq_dir / "roster.json"
    _atomic_write(path, json.dumps(roster, indent=2, ensure_ascii=False) + "\n")
    return path


def team_order(teams: Iterable[str]) -> List[str]:
    present = set(teams)
    ordered = [t for t in TEAM_ORDER if t in present]
    ordered += sorted(t for t in present if t not in TEAM_ORDER and t != UNASSIGNED)
    if UNASSIGNED in present:
        ordered.append(UNASSIGNED)
    return ordered


def roster_table(roster: Dict[str, Any]) -> str:
    bots = [b for b in roster.get("bots", []) if not b.get("retired")]
    order = {t: i for i, t in enumerate(team_order(b.get("team", UNASSIGNED) for b in bots))}
    bots.sort(key=lambda b: (order.get(b.get("team", UNASSIGNED), 99), b.get("kind", ""), b.get("name", "")))
    rows = [("TEAM", "BOT", "KIND", "MODEL", "JOB")]
    for bot in bots:
        rows.append((str(bot.get("team", "")), str(bot.get("name", "")), str(bot.get("kind", "")),
                     str(bot.get("model", "")), squash(bot.get("job", ""), 72)))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = []
    for row in rows:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(4)) + "  " + row[4])
    retired = [b.get("name") for b in roster.get("bots", []) if b.get("retired")]
    if retired:
        lines.append("retired (file gone, kept for history): " + ", ".join(map(str, retired)))
    return "\n".join(lines)


# --------------------------------------------------------------------------- transcripts


def describe_tool(block: Dict[str, Any]) -> str:
    name = str(block.get("name") or "tool")
    params = block.get("input")
    if isinstance(params, dict):
        for key in TOOL_DETAIL_KEYS:
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                return f"{name}: {squash(value, 70)}"
    return name


class Transcript:
    """Incremental reader of one Claude Code transcript (.jsonl).

    Reads only the bytes appended since the last refresh, so a 50 MB file costs
    one pass and then pennies. Usage is counted once per message id because
    the transcript writes one line per content block, each carrying the whole
    message's usage.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.offset = 0
        self.buf = b""
        self.mtime: float = 0.0
        self.size = 0
        self.missing = True
        self.lines = 0
        self.bad = 0
        self.model: Optional[str] = None
        self.last_ts: Optional[float] = None
        self.step: Optional[str] = None
        self.last_tool: Optional[str] = None
        self.tokens: Dict[str, Dict[str, int]] = {}
        self.recent_ids: Deque[str] = deque(maxlen=256)
        self.texts: Deque[Tuple[float, str]] = deque(maxlen=200)

    def _reset(self) -> None:
        self.__init__(self.path)  # type: ignore[misc]

    def refresh(self) -> None:
        try:
            stat = os.stat(self.path)
        except OSError:
            self.missing = True
            return
        self.missing = False
        self.mtime = stat.st_mtime
        if stat.st_size < self.offset:
            self._reset()
            self.missing = False
            self.mtime = stat.st_mtime
        self.size = stat.st_size
        if stat.st_size == self.offset:
            return
        try:
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                data = handle.read()
        except OSError:
            return
        self.offset += len(data)
        parts = (self.buf + data).split(b"\n")
        self.buf = parts.pop()
        for raw in parts:
            if raw.strip():
                self._consume(raw)

    def _consume(self, raw: bytes) -> None:
        self.lines += 1
        try:
            row = json.loads(raw)
        except ValueError:
            self.bad += 1
            return
        if not isinstance(row, dict):
            return
        kind = row.get("type")
        ts = parse_ts(row.get("timestamp"))
        if ts and kind in ("user", "assistant"):
            self.last_ts = max(self.last_ts or 0.0, ts)
        msg = row.get("message")
        if not isinstance(msg, dict):
            return
        if kind == "assistant":
            if isinstance(msg.get("model"), str):
                self.model = msg["model"]
            usage = msg.get("usage")
            if isinstance(usage, dict):
                mid = msg.get("id") or row.get("requestId")
                if not isinstance(mid, str):
                    self._add_usage(usage, ts)
                elif mid not in self.recent_ids:
                    self.recent_ids.append(mid)
                    self._add_usage(usage, ts)
        content = msg.get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if kind == "assistant" and btype == "tool_use":
                self.last_tool = describe_tool(block)
                self.step = self.last_tool
            elif kind == "assistant" and btype == "text":
                text = squash(block.get("text"), 200)
                if text:
                    self.texts.append((ts or self.mtime, text))
                    self.step = "says: " + squash(text, 90)
            elif kind == "assistant" and btype == "thinking":
                self.step = "thinking"

    def _add_usage(self, usage: Dict[str, Any], ts: Optional[float]) -> None:
        day = local_day(ts if ts else (self.mtime or time.time()))
        bucket = self.tokens.setdefault(day, {k: 0 for k, _ in TOKEN_KEYS} | {"total": 0, "calls": 0})
        total = 0
        for key, source in TOKEN_KEYS:
            value = _int(usage.get(source))
            bucket[key] += value
            total += value
        bucket["total"] += total
        bucket["calls"] += 1

    def tokens_for(self, day: str) -> Dict[str, int]:
        return dict(self.tokens.get(day) or ({k: 0 for k, _ in TOKEN_KEYS} | {"total": 0, "calls": 0}))

    def summary_before(self, epoch: float) -> Optional[str]:
        best: Optional[str] = None
        for ts, text in self.texts:
            if ts <= epoch + ANSWER_GRACE_S:
                best = text
        return best


def subagent_paths(transcript_path: Optional[str]) -> List[str]:
    """Subagent transcripts live under <session>/subagents/, sometimes deeper."""
    if not transcript_path or not transcript_path.endswith(".jsonl"):
        return []
    root = Path(transcript_path[: -len(".jsonl")]) / "subagents"
    if not root.is_dir():
        return []
    try:
        return sorted(str(p) for p in root.rglob("*.jsonl") if p.is_file())
    except OSError:
        return []


# --------------------------------------------------------------------------- events


class Session:
    __slots__ = ("sid", "cwd", "transcript_path", "bot_hint", "started", "ended", "ended_reason",
                 "last_prompt", "last_stop", "last_event", "notification", "events")

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.cwd: Optional[str] = None
        self.transcript_path: Optional[str] = None
        self.bot_hint: Optional[str] = None
        self.started: Optional[float] = None
        self.ended: Optional[float] = None
        self.ended_reason: Optional[str] = None
        self.last_prompt: Optional[float] = None
        self.last_stop: Optional[float] = None
        self.last_event: float = 0.0
        self.notification: Optional[Dict[str, Any]] = None
        self.events = 0


class Events:
    """Incremental reader of events.jsonl, folded into per-session state."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.buf = b""
        self.lines = 0
        self.bad = 0
        self.sessions: Dict[str, Session] = {}
        self.stops: Deque[Dict[str, Any]] = deque(maxlen=5000)
        self.subagents: Dict[str, Dict[str, Any]] = {}

    def refresh(self) -> None:
        try:
            stat = os.stat(self.path)
        except OSError:
            return
        if stat.st_size < self.offset:
            self.__init__(self.path)  # type: ignore[misc]
        if stat.st_size == self.offset:
            return
        try:
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                data = handle.read()
        except OSError:
            return
        self.offset += len(data)
        parts = (self.buf + data).split(b"\n")
        self.buf = parts.pop()
        for raw in parts:
            if raw.strip():
                self._consume(raw)

    def _consume(self, raw: bytes) -> None:
        self.lines += 1
        try:
            row = json.loads(raw)
        except ValueError:
            self.bad += 1
            return
        if not isinstance(row, dict):
            self.bad += 1
            return
        t = parse_ts(row.get("t")) or time.time()
        event = str(row.get("event") or "")
        sid = str(row.get("session_id") or "unknown")
        session = self.sessions.get(sid)
        if session is None:
            session = self.sessions[sid] = Session(sid)
        session.events += 1
        session.last_event = max(session.last_event, t)
        if isinstance(row.get("cwd"), str) and row["cwd"]:
            session.cwd = row["cwd"]
        if isinstance(row.get("transcript_path"), str) and row["transcript_path"]:
            session.transcript_path = row["transcript_path"]
        if isinstance(row.get("bot"), str) and row["bot"]:
            session.bot_hint = row["bot"]
        if event == "SessionStart":
            session.started = session.started or t
            session.ended = None
        elif event == "UserPromptSubmit":
            session.last_prompt = t
            session.notification = None
            session.ended = None
        elif event == "Notification":
            session.notification = {
                "t": t,
                "message": squash(row.get("message"), 300),
                "type": str(row.get("notification_type") or ""),
            }
        elif event == "Stop":
            session.last_stop = t
            self.stops.append({"t": t, "session_id": sid, "summary": squash(row.get("summary"), 200)})
        elif event == "SubagentStop":
            path = row.get("agent_transcript_path")
            if isinstance(path, str) and path:
                self.subagents[path] = {
                    "agent_type": str(row.get("agent_type") or ""),
                    "parent": sid,
                    "stopped": t,
                    "summary": squash(row.get("summary"), 200),
                }
        elif event == "SessionEnd":
            session.ended = t
            session.ended_reason = str(row.get("reason") or "")


def session_status(session: Session, transcript: Optional[Transcript], now: float) -> Tuple[str, bool]:
    """(status, stale) for one session under the rules in the module docstring."""
    turn_ts = transcript.last_ts if transcript and transcript.last_ts else 0.0
    any_ts = max(transcript.mtime if transcript else 0.0, session.last_event)
    if session.ended is not None:
        return "resting", False
    if now - max(any_ts, turn_ts) > STALE_AFTER_S:
        return "resting", True
    prompt = session.last_prompt or 0.0
    stop = session.last_stop or 0.0
    note = session.notification
    if note and note["t"] > prompt and note["t"] > stop:
        idle = note["type"] == "idle_prompt"
        answered = turn_ts > note["t"] + ANSWER_GRACE_S
        if (not idle or IDLE_IS_WAITING) and not answered:
            return "waiting", False
    if not session.last_prompt or stop >= prompt:
        return "resting", False
    quiet = now - max(any_ts, turn_ts)
    return ("stuck" if quiet > STUCK_AFTER_S else "working"), False


# --------------------------------------------------------------------------- state


def _empty_tokens() -> Dict[str, int]:
    return {k: 0 for k, _ in TOKEN_KEYS} | {"total": 0, "calls": 0}


def _add_tokens(into: Dict[str, int], more: Dict[str, int]) -> None:
    for key, value in more.items():
        into[key] = into.get(key, 0) + value


class State:
    """Everything /state returns, rebuilt at most once per STATE_TTL_S."""

    def __init__(self, hq_dir: Path) -> None:
        self.hq_dir = hq_dir
        self.events = Events(hq_dir / "events.jsonl")
        self.transcripts: Dict[str, Transcript] = {}
        self.lock = threading.Lock()
        self.cache: Optional[Dict[str, Any]] = None
        self.cache_at = 0.0

    def snapshot(self, now: Optional[float] = None, force: bool = False) -> Dict[str, Any]:
        with self.lock:
            now = now if now is not None else time.time()
            if self.cache is not None and not force and now - self.cache_at < STATE_TTL_S:
                return self.cache
            self.cache = self._build(now)
            self.cache_at = now
            return self.cache

    def transcript(self, path: Optional[str]) -> Optional[Transcript]:
        if not path:
            return None
        tr = self.transcripts.get(path)
        if tr is None:
            tr = self.transcripts[path] = Transcript(path)
        tr.refresh()
        return tr

    def _lane_for(self, cwd: Optional[str], lanes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not cwd:
            return None
        best: Optional[Dict[str, Any]] = None
        for lane in lanes:
            lane_cwd = str(lane.get("cwd") or "").rstrip("/")
            if not lane_cwd:
                continue
            if cwd == lane_cwd or cwd.startswith(lane_cwd + "/"):
                if best is None or len(lane_cwd) > len(str(best.get("cwd") or "")):
                    best = lane
        return best

    def _build(self, now: float) -> Dict[str, Any]:
        roster = load_roster(self.hq_dir)
        self.events.refresh()
        today = local_day(now)
        views: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for bot in roster["bots"]:
            if bot.get("retired"):
                continue
            views[bot["id"]] = self._view(bot)
            order.append(bot["id"])
        lanes = [b for b in roster["bots"] if b.get("kind") == "session" and b.get("cwd") and not b.get("retired")]
        agents = {b["name"]: b for b in roster["bots"] if b.get("kind") == "agent" and not b.get("retired")}
        session_bot: Dict[str, str] = {}
        seen_sub: set = set()

        for session in self.events.sessions.values():
            lane = self._lane_for(session.cwd, lanes)
            if lane is None:
                lane = self._unassigned(session, views, order)
            session_bot[session.sid] = lane["id"]
            view = views[lane["id"]]
            tr = self.transcript(session.transcript_path)
            status, stale = session_status(session, tr, now)
            if tr is not None:
                _add_tokens(view["tokens_today"], tr.tokens_for(today))
                if tr.model:
                    view["model_seen"] = tr.model
            self._fold(view, status, stale, session, tr, now)
            for sub_path in subagent_paths(session.transcript_path):
                seen_sub.add(sub_path)
                self._fold_subagent(sub_path, session, view, views, agents, today, now)
        for sub_path, info in self.events.subagents.items():
            if sub_path in seen_sub:
                continue
            parent_id = session_bot.get(info["parent"])
            parent_view = views.get(parent_id) if parent_id else None
            if parent_view is None:
                parent_session = self.events.sessions.get(info["parent"])
                lane = self._lane_for(parent_session.cwd if parent_session else None, lanes)
                parent_view = views[lane["id"]] if lane else None
            self._fold_subagent(sub_path, self.events.sessions.get(info["parent"]), parent_view, views, agents, today, now)

        bots = [views[i] for i in order]
        for view in bots:
            view.pop("_rank", None)
            view.pop("_step_at", None)
            if view["last_line_epoch"]:
                view["last_line"] = now_iso(view["last_line_epoch"])
        counts = {k: 0 for k in STATUS_RANK}
        for view in bots:
            counts[view["status"]] += 1
        waiting = [
            {"bot": v["name"], "bot_id": v["id"], "team": v["team"], "message": v["waiting"]["message"],
             "since": v["waiting"]["since"], "type": v["waiting"]["type"]}
            for v in bots if v["status"] == "waiting" and v.get("waiting")
        ]
        waiting.sort(key=lambda w: w["since"])
        finished = []
        for stop in self.events.stops:
            if local_day(stop["t"]) != today:
                continue
            session = self.events.sessions.get(stop["session_id"])
            bot_id = session_bot.get(stop["session_id"])
            view = views.get(bot_id) if bot_id else None
            summary = stop.get("summary") or ""
            if not summary and session and session.transcript_path:
                tr = self.transcripts.get(session.transcript_path)
                summary = (tr.summary_before(stop["t"]) if tr else None) or ""
            finished.append({
                "t": now_iso(stop["t"]),
                "epoch": stop["t"],
                "bot": view["name"] if view else (session.bot_hint if session else "unknown"),
                "team": view["team"] if view else UNASSIGNED,
                "session_id": stop["session_id"],
                "summary": summary,
            })
        finished.sort(key=lambda f: f["epoch"], reverse=True)
        total = sum(v["tokens_today"]["total"] for v in bots)
        return {
            "now": now_iso(now),
            "now_epoch": now,
            "day": today,
            "teams": team_order(v["team"] for v in bots),
            "bots": bots,
            "counts": counts,
            "waiting": waiting,
            "finished_today": finished[:100],
            "tokens_total_today": total,
            "max_tokens_today": max([v["tokens_today"]["total"] for v in bots] or [0]),
            "rules": {"stuck_after_s": STUCK_AFTER_S, "stale_after_s": STALE_AFTER_S, "idle_is_waiting": IDLE_IS_WAITING},
            "roster_generated": roster.get("generated"),
            "events": {"lines": self.events.lines, "bad": self.events.bad, "path": str(self.events.path)},
        }

    @staticmethod
    def _view(bot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": bot["id"],
            "name": bot.get("name"),
            "team": bot.get("team") or UNASSIGNED,
            "kind": bot.get("kind") or "session",
            "model": bot.get("model") or "unknown",
            "model_seen": None,
            "job": bot.get("job") or "",
            "source": bot.get("source"),
            "status": "resting",
            "stale": False,
            "step": None,
            "tokens_today": _empty_tokens(),
            "last_line": None,
            "last_line_epoch": 0.0,
            "sessions_active": 0,
            "sessions_seen": 0,
            "waiting": None,
            "_rank": -1,
            "_step_at": 0.0,
        }

    def _unassigned(self, session: Session, views: Dict[str, Dict[str, Any]], order: List[str]) -> Dict[str, Any]:
        cwd = session.cwd or ""
        bot_id = f"session:{cwd}" if cwd else f"session-id:{session.sid}"
        if bot_id not in views:
            name = os.path.basename(cwd.rstrip("/")) if cwd else session.sid[:8]
            bot = {"id": bot_id, "name": name or bot_id, "kind": "session", "team": UNASSIGNED,
                   "model": "unknown", "job": f"Sessions run in {cwd}" if cwd else "Session with no cwd recorded",
                   "source": cwd or None, "cwd": cwd or None}
            views[bot_id] = self._view(bot)
            order.append(bot_id)
        return {"id": bot_id, "cwd": cwd}

    def _fold(self, view: Dict[str, Any], status: str, stale: bool, session: Session,
              tr: Optional[Transcript], now: float) -> None:
        view["sessions_seen"] += 1
        if session.ended is None and not stale:
            view["sessions_active"] += 1
        activity = max(session.last_event, tr.mtime if tr else 0.0, tr.last_ts if tr and tr.last_ts else 0.0)
        view["last_line_epoch"] = max(view["last_line_epoch"], activity)
        rank = STATUS_RANK[status]
        if rank > view["_rank"] or (rank == view["_rank"] and activity > view["_step_at"]):
            view["_rank"] = rank
            view["status"] = status
            view["stale"] = stale
            view["_step_at"] = activity
            view["step"] = (tr.step if tr else None) or ("idle" if status == "resting" else None)
            if status == "waiting" and session.notification:
                view["waiting"] = {"message": session.notification["message"], "since": now_iso(session.notification["t"]),
                                   "type": session.notification["type"], "session_id": session.sid}
            elif status != "waiting":
                view["waiting"] = None
        if view.get("model_seen") is None and tr and tr.model:
            view["model_seen"] = tr.model

    def _fold_subagent(self, sub_path: str, session: Optional[Session], parent_view: Optional[Dict[str, Any]],
                       views: Dict[str, Dict[str, Any]], agents: Dict[str, Dict[str, Any]], today: str, now: float) -> None:
        info = self.events.subagents.get(sub_path)
        agent = agents.get(info["agent_type"]) if info else None
        target = views.get(agent["id"]) if agent else parent_view
        if target is None:
            return
        tr = self.transcript(sub_path)
        if tr is None or tr.missing:
            return
        _add_tokens(target["tokens_today"], tr.tokens_for(today))
        activity = max(tr.mtime, tr.last_ts or 0.0)
        target["last_line_epoch"] = max(target["last_line_epoch"], activity)
        if target is parent_view:
            return
        target["sessions_seen"] += 1
        if info and info.get("stopped"):
            status = "resting"
        elif now - activity > STALE_AFTER_S:
            status = "resting"
        else:
            target["sessions_active"] += 1
            status = "stuck" if now - activity > STUCK_AFTER_S else "working"
        rank = STATUS_RANK[status]
        if rank > target["_rank"] or (rank == target["_rank"] and activity > target["_step_at"]):
            target["_rank"] = rank
            target["status"] = status
            target["_step_at"] = activity
            target["step"] = tr.step or ("idle" if status == "resting" else None)
        if tr.model:
            target["model_seen"] = tr.model


# --------------------------------------------------------------------------- server


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    "": "text/plain; charset=utf-8",
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'")


def host_allowed(host_header: Optional[str]) -> bool:
    """Only loopback names: a page on another origin cannot read the office through DNS rebinding."""
    host = (host_header or "").strip().lower()
    if host.startswith("["):
        host = host.split("]", 1)[0] + "]"
    else:
        host = host.split(":", 1)[0]
    return host in {"127.0.0.1", "localhost", "[::1]"}


def make_handler(state: State, app_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AgentHQ/1"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            if os.environ.get("AGENT_HQ_LOG"):
                sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

        def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _file(self, path: Path, cache: str) -> None:
            try:
                body = path.read_bytes()
            except OSError:
                self._send(404, b"not found", CONTENT_TYPES[".txt"])
                return
            self._send(200, body, CONTENT_TYPES.get(path.suffix, CONTENT_TYPES[""]), cache)

        def do_HEAD(self) -> None:  # noqa: N802 (http.server naming)
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            if not host_allowed(self.headers.get("Host")):
                self._send(403, b"forbidden host", CONTENT_TYPES[".txt"])
                return
            route = urlparse(self.path).path
            if route in ("/", "/index.html"):
                self._file(app_dir / "index.html", "no-store")
            elif route == "/app.js":
                self._file(app_dir / "app.js", "no-store")
            elif route == "/state":
                body = json.dumps(state.snapshot(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, CONTENT_TYPES[".json"])
            elif route == "/health":
                self._send(200, b'{"ok":true}', CONTENT_TYPES[".json"])
            elif route.startswith("/vendor/"):
                name = route[len("/vendor/"):]
                if name in VENDOR_FILES:
                    self._file(app_dir / "vendor" / name, "public, max-age=31536000, immutable")
                else:
                    self._send(404, b"not found", CONTENT_TYPES[".txt"])
            else:
                self._send(404, b"not found", CONTENT_TYPES[".txt"])

    return Handler


def make_server(hq_dir: Path, app_dir: Path, host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    state = State(hq_dir)
    server = ThreadingHTTPServer((host, port), make_handler(state, app_dir))
    server.daemon_threads = True
    return server


def serve(hq_dir: Path, app_dir: Path, port: int = PORT) -> int:
    try:
        server = make_server(hq_dir, app_dir, HOST, port)
    except OSError as exc:
        sys.stderr.write(f"Agent HQ: cannot listen on {HOST}:{port} ({exc.strerror or exc}). "
                         "Another copy may be running; stop it or pass --port.\n")
        return 2
    print(f"Agent HQ  http://{HOST}:{port}")
    print(f"  data    {hq_dir}")
    print(f"  events  {hq_dir / 'events.jsonl'}")
    print("  loopback only, no outbound calls; Ctrl-C stops it")
    sys.stdout.flush()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


# --------------------------------------------------------------------------- install


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".agent-hq.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _is_ours(group: Any) -> bool:
    if not isinstance(group, dict):
        return False
    for hook in group.get("hooks") or []:
        if isinstance(hook, dict) and HOOK_MARK.search(str(hook.get("command") or "")):
            return True
    return False


def _load_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("settings.json is not a JSON object")
    return data


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.agent-hq-backup-{stamp}")
    shutil.copy2(path, backup)
    return backup


def merge_hooks(settings_path: Path) -> Dict[str, Any]:
    """Add one Agent HQ hook group per event, leaving every other hook untouched."""
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    if hooks is None:
        hooks = data["hooks"] = {}
    if not isinstance(hooks, dict):
        raise ValueError("settings.json 'hooks' is not an object")
    added: List[str] = []
    for event in HOOK_EVENTS:
        groups = hooks.get(event)
        if groups is None:
            groups = hooks[event] = []
        if not isinstance(groups, list):
            raise ValueError(f"settings.json hooks.{event} is not a list")
        if any(_is_ours(g) for g in groups):
            continue
        groups.append({"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": HOOK_TIMEOUT_S}]})
        added.append(event)
    backup = None
    if added:
        backup = _backup(settings_path)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(settings_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return {"added": added, "backup": str(backup) if backup else None, "path": str(settings_path)}


def remove_hooks(settings_path: Path) -> Dict[str, Any]:
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    removed: List[str] = []
    if isinstance(hooks, dict):
        for event in list(hooks):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            kept = [g for g in groups if not _is_ours(g)]
            if len(kept) != len(groups):
                removed.append(event)
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if not hooks:
            del data["hooks"]
    backup = None
    if removed:
        backup = _backup(settings_path)
        _atomic_write(settings_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return {"removed": removed, "backup": str(backup) if backup else None, "path": str(settings_path)}


def copy_files(app_dir: Path, hq_dir: Path) -> List[str]:
    copied: List[str] = []
    hq_dir.mkdir(parents=True, exist_ok=True)
    (hq_dir / "vendor").mkdir(exist_ok=True)
    pairs = [(app_dir / n, hq_dir / n) for n in INSTALL_FILES]
    pairs += [(app_dir / "vendor" / n, hq_dir / "vendor" / n) for n in VENDOR_FILES]
    for src, dst in pairs:
        if not src.is_file():
            continue
        if dst.exists() and os.path.samefile(src, dst):
            continue
        if dst.exists() and _sha256(src) == _sha256(dst):
            continue
        shutil.copy2(src, dst)
        copied.append(dst.name)
    return copied


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(app_dir: Path, hq_dir: Path, claude_dir: Path) -> Dict[str, Any]:
    copied = copy_files(app_dir, hq_dir)
    result = merge_hooks(claude_dir / "settings.json")
    result["copied"] = copied
    result["hq_dir"] = str(hq_dir)
    return result


def refresh_roster(hq_dir: Path, claude_dir: Path, extra_cwds: Iterable[str], write: bool) -> Tuple[Dict[str, Any], List[str]]:
    existing = load_roster(hq_dir) if (hq_dir / "roster.json").exists() else None
    scanned, notes = scan_roster(claude_dir, extra_cwds)
    roster = merge_roster(existing, scanned)
    if write:
        write_roster(hq_dir, roster)
    return roster, notes


# --------------------------------------------------------------------------- cli


def _cwd_hint() -> List[str]:
    try:
        cwd = os.getcwd()
    except OSError:
        return []
    return [] if Path(cwd) == Path.home() else [cwd]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hq.py", description="Agent HQ: a local 3D office for Claude Code sessions.")
    sub = parser.add_subparsers(dest="cmd")
    for name in ("up", "serve"):
        p = sub.add_parser(name, help=f"{name}: " + ("install, roster if missing, then serve" if name == "up" else "serve only"))
        p.add_argument("--port", type=int, default=PORT)
    sub.add_parser("install", help="merge the hooks into settings.json and copy the files into ~/.agent-hq")
    sub.add_parser("uninstall", help="remove the Agent HQ hooks from settings.json; data stays")
    r = sub.add_parser("roster", help="scan agents and session folders, print the roster, merge it into roster.json")
    r.add_argument("--no-write", action="store_true", help="print only")
    r.add_argument("--json", action="store_true", help="print JSON instead of a table")
    r.add_argument("--cwd", action="append", default=[], help="extra folder to treat as a session lane")
    sub.add_parser("state", help="print /state once as JSON")
    args = parser.parse_args(argv)

    hq_dir = default_hq_dir()
    claude_dir = default_claude_dir()
    if args.cmd in (None, "up"):
        port = getattr(args, "port", PORT)
        try:
            result = install(APP_DIR, hq_dir, claude_dir)
            print(f"hooks   {result['path']}: " + (f"added {', '.join(result['added'])}" if result["added"] else "already present"))
            if result["backup"]:
                print(f"backup  {result['backup']}")
            if result["copied"]:
                print(f"copied  {', '.join(result['copied'])} into {hq_dir}")
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: hooks not installed, {exc}. Fix {claude_dir / 'settings.json'} and run install again.\n")
        if not (hq_dir / "roster.json").exists():
            roster, notes = refresh_roster(hq_dir, claude_dir, _cwd_hint(), write=True)
            print(f"roster  {hq_dir / 'roster.json'} written with {len(roster['bots'])} bots")
            for note in notes:
                print(f"        {note}")
            print(roster_table(roster))
        return serve(hq_dir, APP_DIR, port)
    if args.cmd == "serve":
        return serve(hq_dir, APP_DIR, args.port)
    if args.cmd == "install":
        try:
            result = install(APP_DIR, hq_dir, claude_dir)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: hooks not installed, {exc}.\n")
            return 2
        print(json.dumps(result, indent=2))
        return 0
    if args.cmd == "uninstall":
        try:
            result = remove_hooks(claude_dir / "settings.json")
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: nothing removed, {exc}.\n")
            return 2
        print(json.dumps(result, indent=2))
        return 0
    if args.cmd == "roster":
        roster, notes = refresh_roster(hq_dir, claude_dir, list(args.cwd) + _cwd_hint(), write=not args.no_write)
        if args.json:
            print(json.dumps(roster, indent=2, ensure_ascii=False))
        else:
            print(roster_table(roster))
            for note in notes:
                print(note)
            if not args.no_write:
                print(f"written to {hq_dir / 'roster.json'}")
        return 0
    if args.cmd == "state":
        print(json.dumps(State(hq_dir).snapshot(force=True), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
