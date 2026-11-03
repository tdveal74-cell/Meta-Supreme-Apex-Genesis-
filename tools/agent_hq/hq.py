#!/usr/bin/env python3
"""Agent HQ: a live 3D office for the Claude Code sessions on this machine.

One file, Python 3 standard library only, no network calls. The server binds
to 127.0.0.1 and reads only local files: ~/.agent-hq, ~/.claude, the
.claude/agents folders of the projects sessions run in, and the transcripts
the hooks name. Nothing it reads leaves the machine. Like any loopback
server it answers every process on this machine, so /state is as private as
the account that runs it.

    python3 hq.py up          roster (asks for your OK the first time), hooks, serve
    python3 hq.py install     merge the hooks into ~/.claude/settings.json, copy files
    python3 hq.py roster      scan agents and session folders; show, ask, merge roster.json
    python3 hq.py serve       serve the office on http://127.0.0.1:7777
    python3 hq.py state       print the current state once, as JSON
    python3 hq.py uninstall   remove the Agent HQ hooks, keep the data

Data lives in ~/.agent-hq (override with AGENT_HQ_DIR):
    roster.json    every bot with its job, model and team
    events.jsonl   one JSON line per hook event, written by hook.py
    hq.py hook.py index.html app.js vendor/    the installed copies

Status rules, per session, from events.jsonl and the session's transcript.
Event order is the order the hook wrote the rows, so a Stop and a prompt in
the same second still sort correctly.
    waiting   a Notification since the last prompt that nothing has answered
              yet: no Stop after it and no transcript turn line after it. An
              idle_prompt notification reads as resting unless IDLE_IS_WAITING.
    resting   stopped, ended, no prompt yet, or quiet for STALE_AFTER_S
    working   mid turn, and the transcript grew inside STUCK_AFTER_S; a
              subagent transcript growing under the session counts too
    stuck     mid turn, nothing new for STUCK_AFTER_S (10 minutes)
A bot shows the highest of its sessions: waiting, then stuck, working, resting.
An agent bot (a .claude/agents definition) shows working while a session has
an open Agent tool call of its type, and resting once SubagentStop lands.

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
CHUNK_BYTES = 4 * 1024 * 1024
MAX_LINE_BYTES = 8 * 1024 * 1024
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Notification", "Stop", "SubagentStop", "SessionEnd")
HOOK_SUFFIX = '>/dev/null 2>&1 || true  # agent-hq'
HOOK_MARK = re.compile(r"(?:agent-hq[}\"']?/hook\.py|# agent-hq\s*$)")
HOOK_TIMEOUT_S = 5
INSTALL_FILES = ("hq.py", "hook.py", "index.html", "app.js")
VENDOR_FILES = ("three.module.js", "three.core.js", "LICENSE")
TEAM_ORDER = ("Research", "Content", "Visuals", "Ops")
UNASSIGNED = "Unassigned"
# A trailing * makes a keyword a stem matched at a word start; without it the
# keyword must be a whole word, so "frame" does not fire on "framework" and
# "post" does not fire on "postgres". First team to match wins.
TEAM_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Visuals", ("render*", "video*", "image*", "thumbnail*", "design*", "carousel*", "visual*", "frame",
                 "frames", "shot", "shots", "avatar*", "scene*", "motion", "art", "photo*", "film*",
                 "graphic*", "animat*")),
    ("Content", ("script*", "writ*", "draft*", "copy", "episode*", "podcast*", "content", "story", "stories",
                 "caption*", "voice*", "canon", "brand*", "viral", "tqo", "nco", "tsws", "short", "shorts",
                 "newsletter*", "post", "posts", "blog*", "narrat*")),
    ("Research", ("research*", "scan*", "read-only", "search*", "audit*", "verif*", "analy*", "investigat*",
                  "review*", "critic*", "explor*", "reader", "scout*", "inspect*")),
    ("Ops", ("deploy*", "ci", "test", "tests", "testing", "fix", "fixes", "edit", "edits", "editor", "pipeline*",
             "workflow*", "infra*", "ops", "build*", "registry", "steward*", "hook*", "release*", "devops",
             "migrat*", "monitor*", "watchdog*", "backup*")),
)
STATUS_RANK = {"waiting": 3, "stuck": 2, "working": 1, "resting": 0}
TOKEN_KEYS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_create", "cache_creation_input_tokens"),
)
# What the page shows as the current step. A Bash command, a URL, a prompt or
# a search query can carry a secret, so only these fields are ever read.
TOOL_DETAIL_KEYS = ("description", "file_path", "path", "pattern", "skill")


# --------------------------------------------------------------------------- paths and time


def _abs_dir(value: Optional[str], fallback: Path) -> Path:
    """Absolute, so a relative AGENT_HQ_DIR never bakes a relative path into a hook line."""
    return Path(os.path.abspath(os.path.expanduser(value))) if value else fallback


def default_hq_dir() -> Path:
    return _abs_dir(os.environ.get("AGENT_HQ_DIR"), Path.home() / ".agent-hq")


def default_claude_dir() -> Path:
    return _abs_dir(os.environ.get("CLAUDE_CONFIG_DIR"), Path.home() / ".claude")


def now_iso(epoch: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(epoch) if epoch is not None else datetime.now()
    return dt.astimezone().isoformat(timespec="milliseconds")


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
    """First team whose keyword appears in the texts; Ops when none does."""
    blob = " ".join(t for t in texts if t).lower()
    for team, words in TEAM_RULES:
        for word in words:
            if word.endswith("*"):
                pattern = r"\b" + re.escape(word[:-1])
            else:
                pattern = r"\b" + re.escape(word) + r"\b"
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
                    line = handle.readline(MAX_LINE_BYTES)
                    if not line:
                        break
                    try:
                        row = json.loads(line)
                    except (ValueError, RecursionError):
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
            except (ValueError, RecursionError):
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
        "id": f"agent:{path.stem}@{cwd or 'user'}",
        "name": name,
        "agent_type": name,
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
    cwds = sorted(set(cwd_to_dir) | {os.path.abspath(c) for c in extra_cwds if c})
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
    """Make display names unique: two files with one name, or one name in two folders.

    Ids never change here. An agent's id is its file, and `agent_type` keeps
    the frontmatter name the hooks match on, whatever the display name becomes.
    """
    scoped: Dict[Tuple[str, Optional[str]], int] = {}
    for bot in bots:
        if bot.get("kind") == "agent":
            key = (bot["name"], bot.get("cwd"))
            scoped[key] = scoped.get(key, 0) + 1
    for bot in bots:
        if bot.get("kind") == "agent" and scoped[(bot["name"], bot.get("cwd"))] > 1:
            bot["name"] = f"{bot['name']} ({Path(str(bot.get('source') or '')).stem})"
    names: Dict[str, int] = {}
    for bot in bots:
        names[bot["name"]] = names.get(bot["name"], 0) + 1
    for bot in bots:
        if names[bot["name"]] > 1 and bot.get("cwd"):
            parent = os.path.basename(os.path.dirname(bot["cwd"].rstrip("/")))
            bot["name"] = f"{bot['name']} ({parent})" if parent else bot["name"]


def _source_gone(bot: Dict[str, Any]) -> bool:
    """True when the file or folder a bot came from is no longer on disk."""
    if bot.get("kind") == "agent":
        source = str(bot.get("source") or "")
        return bool(source) and not os.path.isfile(source)
    cwd = str(bot.get("cwd") or "")
    return bool(cwd) and not os.path.isdir(cwd)


def merge_roster(existing: Optional[Dict[str, Any]], scanned: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep the user's edits (name, team, job), refresh what the files say.

    A bot the scan did not see stays as it was while its file or folder is
    still on disk (a folder with no transcript yet is not seen by a scan run
    from elsewhere); it is marked retired only once that source is gone.
    """
    old = {b.get("id"): b for b in (existing or {}).get("bots", []) if isinstance(b, dict) and b.get("id")}
    by_source = {(b.get("kind"), b.get("source")): bot_id for bot_id, b in old.items() if b.get("source")}
    bots: List[Dict[str, Any]] = []
    seen = set()
    for bot in scanned:
        seen.add(bot["id"])
        prev = old.get(bot["id"])
        if prev is None:
            # The same file under an older id scheme: carry its edits, drop the old row.
            old_id = by_source.get((bot.get("kind"), bot.get("source")))
            if old_id and old_id not in seen:
                prev = old[old_id]
                seen.add(old_id)
        if prev:
            merged = dict(prev)
            merged["id"] = bot["id"]
            for key in ("kind", "scope", "model", "source", "cwd", "tools", "agent_type"):
                if key in bot:
                    merged[key] = bot[key]
            merged.pop("retired", None)
            bots.append(merged)
        else:
            bots.append(dict(bot))
    for bot_id, prev in old.items():
        if bot_id in seen:
            continue
        kept = dict(prev)
        if _source_gone(kept):
            kept["retired"] = True
        else:
            kept.pop("retired", None)
        bots.append(kept)
    return {"version": 1, "generated": now_iso(), "bots": bots}


def load_roster(hq_dir: Path, strict: bool = False) -> Dict[str, Any]:
    """The roster on disk. The server reads leniently; a writer reads strictly,
    so a hand edit with a stray comma is never flattened into an empty roster."""
    path = hq_dir / "roster.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {"version": 1, "bots": []}
    except (ValueError, RecursionError) as exc:
        if strict:
            raise ValueError(f"{path} is not valid JSON ({exc}); fix it or move it aside") from exc
        return {"version": 1, "bots": []}
    if not isinstance(data, dict) or not isinstance(data.get("bots"), list):
        if strict:
            raise ValueError(f"{path} does not hold an object with a bots list; fix it or move it aside")
        return {"version": 1, "bots": []}
    data["bots"] = [b for b in data["bots"] if isinstance(b, dict) and b.get("name")]
    for bot in data["bots"]:
        bot.setdefault("id", f"{bot.get('kind', 'bot')}:{bot['name']}")
        bot.setdefault("team", UNASSIGNED)
        bot.setdefault("kind", "session")
    return data


def write_roster(hq_dir: Path, roster: Dict[str, Any]) -> Path:
    """Write roster.json, keeping the previous version beside it as roster.json.previous."""
    hq_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = hq_dir / "roster.json"
    if path.exists():
        shutil.copy2(path, path.with_name("roster.json.previous"))
    _atomic_write(path, json.dumps(roster, indent=2, ensure_ascii=False) + "\n", mode=0o600)
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
        lines.append("retired (file or folder gone, kept for history): " + ", ".join(map(str, retired)))
    return "\n".join(lines)


# --------------------------------------------------------------------------- incremental files


class _Tail:
    """Reads a growing file from where it left off, one complete line at a time.

    Memory is bounded by CHUNK_BYTES plus one line: a line longer than
    MAX_LINE_BYTES is dropped and counted in `oversized`. A file that shrank
    is read again from the start.
    """

    def _init_tail(self, path: str) -> None:
        self.path = path
        self.offset = 0
        self.buf = b""
        self.skipping = False
        self.mtime: float = 0.0
        self.size = 0
        self.missing = True
        self.lines = 0
        self.bad = 0
        self.oversized = 0

    def _reset(self) -> None:
        raise NotImplementedError

    def _consume(self, raw: bytes) -> None:
        raise NotImplementedError

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
                while True:
                    data = handle.read(CHUNK_BYTES)
                    if not data:
                        break
                    self.offset += len(data)
                    self._feed(data)
        except OSError:
            return

    def _feed(self, data: bytes) -> None:
        parts = (self.buf + data).split(b"\n")
        self.buf = parts.pop()
        for raw in parts:
            if self.skipping:
                self.skipping = False
                self.oversized += 1
                continue
            if len(raw) > MAX_LINE_BYTES:
                self.oversized += 1
                continue
            if raw.strip():
                self.lines += 1
                self._consume(raw)
        if len(self.buf) > MAX_LINE_BYTES:
            self.buf = b""
            self.skipping = True


def _load_row(raw: bytes) -> Optional[Dict[str, Any]]:
    try:
        row = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return row if isinstance(row, dict) else None


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


class Transcript(_Tail):
    """Incremental reader of one Claude Code transcript (.jsonl).

    Usage is counted once per message id because the transcript writes one
    line per content block, each carrying the whole message's usage. Open
    Agent tool calls are tracked by tool_use_id so an agent bot can show
    working while its subagent runs.
    """

    def __init__(self, path: str) -> None:
        self._init_tail(path)
        self.model: Optional[str] = None
        self.last_ts: Optional[float] = None
        self.step: Optional[str] = None
        self.last_tool: Optional[str] = None
        self.tokens: Dict[str, Dict[str, int]] = {}
        self.recent_ids: Deque[str] = deque(maxlen=256)
        self.texts: Deque[Tuple[float, str]] = deque(maxlen=200)
        self.open_agents: Dict[str, Tuple[str, float]] = {}

    def _reset(self) -> None:
        self.__init__(self.path)  # type: ignore[misc]

    def _consume(self, raw: bytes) -> None:
        row = _load_row(raw)
        if row is None:
            self.bad += 1
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
        if kind == "user" and self.open_agents and _is_plain_prompt(content):
            self.open_agents.clear()
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if kind == "assistant" and btype == "tool_use":
                self.last_tool = describe_tool(block)
                self.step = self.last_tool
                if block.get("name") == "Agent" and isinstance(block.get("id"), str):
                    params = block.get("input") if isinstance(block.get("input"), dict) else {}
                    agent_type = str(params.get("subagent_type") or "general-purpose")
                    if len(self.open_agents) >= 64:
                        self.open_agents.pop(next(iter(self.open_agents)))
                    self.open_agents[block["id"]] = (agent_type, ts or self.mtime)
            elif kind == "assistant" and btype == "text":
                text = squash(block.get("text"), 200)
                if text:
                    self.texts.append((ts or self.mtime, text))
                    self.step = "says: " + squash(text, 90)
            elif kind == "assistant" and btype == "thinking":
                self.step = "thinking"
            elif kind == "user" and btype == "tool_result":
                self.open_agents.pop(str(block.get("tool_use_id")), None)

    def _add_usage(self, usage: Dict[str, Any], ts: Optional[float]) -> None:
        day = local_day(ts if ts else (self.mtime or time.time()))
        bucket = self.tokens.setdefault(day, _empty_tokens())
        total = 0
        for key, source in TOKEN_KEYS:
            value = _int(usage.get(source))
            bucket[key] += value
            total += value
        bucket["total"] += total
        bucket["calls"] += 1

    def tokens_for(self, day: str) -> Dict[str, int]:
        return dict(self.tokens.get(day) or _empty_tokens())

    def summary_before(self, epoch: float) -> Optional[str]:
        best: Optional[str] = None
        for ts, text in self.texts:
            if ts <= epoch + ANSWER_GRACE_S:
                best = text
        return best

    def activity(self) -> float:
        return max(self.mtime, self.last_ts or 0.0)

    def open_agent_types(self) -> List[str]:
        return [agent_type for agent_type, _ in self.open_agents.values()]


def _is_plain_prompt(content: Any) -> bool:
    """A user line that is a typed prompt, not a tool result: it starts a new turn."""
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list):
        return False
    types = {b.get("type") for b in content if isinstance(b, dict)}
    return "text" in types and "tool_result" not in types


def _empty_tokens() -> Dict[str, int]:
    return {k: 0 for k, _ in TOKEN_KEYS} | {"total": 0, "calls": 0}


def _add_tokens(into: Dict[str, int], more: Dict[str, int]) -> None:
    for key, value in more.items():
        into[key] = into.get(key, 0) + value


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
                 "last_prompt", "last_stop", "last_event", "notification", "events",
                 "prompt_seq", "stop_seq", "end_seq")

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
        self.prompt_seq = 0
        self.stop_seq = 0
        self.end_seq = 0


class Events(_Tail):
    """Incremental reader of events.jsonl, folded into per-session state.

    Every row gets a sequence number in file order; ordering decisions use
    the sequence, durations use the timestamps.
    """

    def __init__(self, path: Path) -> None:
        self._init_tail(str(path))
        self.seq = 0
        self.sessions: Dict[str, Session] = {}
        self.stops: Deque[Dict[str, Any]] = deque(maxlen=5000)
        self.subagents: Dict[str, Dict[str, Any]] = {}

    def _reset(self) -> None:
        self.__init__(Path(self.path))  # type: ignore[misc]

    def _consume(self, raw: bytes) -> None:
        row = _load_row(raw)
        if row is None:
            self.bad += 1
            return
        self.seq += 1
        seq = self.seq
        t = parse_ts(row.get("time", row.get("t"))) or time.time()
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
            session.prompt_seq = seq
            session.notification = None
            session.ended = None
        elif event == "Notification":
            session.notification = {
                "t": t,
                "seq": seq,
                "message": squash(row.get("message"), 300),
                "type": str(row.get("notification_type") or ""),
            }
        elif event == "Stop":
            session.last_stop = t
            session.stop_seq = seq
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
            session.end_seq = seq
            session.ended_reason = str(row.get("reason") or "")


def session_status(session: Session, transcript: Optional[Transcript], now: float,
                   extra_activity: float = 0.0) -> Tuple[str, bool]:
    """(status, stale) for one session under the rules in the module docstring.

    `extra_activity` is the newest write under the session's subagent
    transcripts, so a parent waiting on a long subagent is working, not stuck.
    """
    turn_ts = transcript.last_ts if transcript and transcript.last_ts else 0.0
    any_ts = max(transcript.mtime if transcript else 0.0, session.last_event, extra_activity)
    if session.ended is not None:
        return "resting", False
    if now - max(any_ts, turn_ts) > STALE_AFTER_S:
        return "resting", True
    note = session.notification
    if note and note["seq"] > session.prompt_seq and note["seq"] > session.stop_seq:
        idle = note["type"] == "idle_prompt"
        answered = turn_ts > note["t"] + ANSWER_GRACE_S
        if (not idle or IDLE_IS_WAITING) and not answered:
            return "waiting", False
    if session.prompt_seq == 0 or session.stop_seq > session.prompt_seq:
        return "resting", False
    quiet = now - max(any_ts, turn_ts)
    return ("stuck" if quiet > STUCK_AFTER_S else "working"), False


# --------------------------------------------------------------------------- state


def _agent_for(agents: Dict[str, List[Dict[str, Any]]], agent_type: str,
               cwd: Optional[str]) -> Optional[Dict[str, Any]]:
    """The roster agent an agent_type names: the one defined in the session's own
    project when there is one, else the user level one, else the first."""
    candidates = agents.get(agent_type) or []
    if not candidates:
        return None
    for bot in candidates:
        lane = str(bot.get("cwd") or "").rstrip("/")
        if lane and cwd and (cwd == lane or cwd.startswith(lane + "/")):
            return bot
    for bot in candidates:
        if not bot.get("cwd"):
            return bot
    return candidates[0]


class State:
    """Everything /state returns, rebuilt at most once per STATE_TTL_S."""

    def __init__(self, hq_dir: Path) -> None:
        self.hq_dir = hq_dir
        self.events = Events(hq_dir / "events.jsonl")
        self.transcripts: Dict[str, Transcript] = {}
        self.lock = threading.Lock()
        self.cache: Optional[Dict[str, Any]] = None
        self.cache_at = 0.0
        self._used: set = set()

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
        self._used.add(path)
        tr = self.transcripts.get(path)
        if tr is None:
            tr = self.transcripts[path] = Transcript(path)
        tr.refresh()
        return tr

    def _lane_for(self, cwd: Optional[str], lanes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not cwd:
            return None
        best: Optional[Dict[str, Any]] = None
        best_len = -1
        for lane in lanes:
            lane_cwd = str(lane.get("cwd") or "").rstrip("/")
            if not lane_cwd:
                continue
            if (cwd == lane_cwd or cwd.startswith(lane_cwd + "/")) and len(lane_cwd) > best_len:
                best, best_len = lane, len(lane_cwd)
        return best

    def _build(self, now: float) -> Dict[str, Any]:
        roster = load_roster(self.hq_dir)
        self.events.refresh()
        self._used = set()
        today = local_day(now)
        views: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for bot in roster["bots"]:
            if bot.get("retired"):
                continue
            views[bot["id"]] = self._view(bot)
            order.append(bot["id"])
        lanes = [b for b in roster["bots"] if b.get("kind") == "session" and b.get("cwd") and not b.get("retired")]
        agents: Dict[str, List[Dict[str, Any]]] = {}
        for b in roster["bots"]:
            if b.get("kind") == "agent" and not b.get("retired"):
                agents.setdefault(str(b.get("agent_type") or b["name"]), []).append(b)
        session_bot: Dict[str, str] = {}
        seen_sub: set = set()

        for session in self.events.sessions.values():
            lane = self._lane_for(session.cwd, lanes)
            if lane is None:
                lane = self._unassigned(session, views, order)
            session_bot[session.sid] = lane["id"]
            view = views[lane["id"]]
            if now - session.last_event > STALE_AFTER_S:
                # Nothing from this session in a day: no file is opened for it.
                self._fold(view, "resting", True, session, None, now)
                continue
            tr = self.transcript(session.transcript_path)
            sub_paths = subagent_paths(session.transcript_path)
            sub_activity = 0.0
            for sub_path in sub_paths:
                st = self.transcript(sub_path)
                if st is not None and not st.missing:
                    info = self.events.subagents.get(sub_path)
                    if not (info and info.get("stopped")):
                        sub_activity = max(sub_activity, st.activity())
            status, stale = session_status(session, tr, now, sub_activity)
            if tr is not None:
                _add_tokens(view["tokens_today"], tr.tokens_for(today))
                if tr.model:
                    view["model_seen"] = tr.model
            self._fold(view, status, stale, session, tr, now)
            for sub_path in sub_paths:
                seen_sub.add(sub_path)
                self._fold_subagent(sub_path, view, views, agents, today, now, session.cwd)
            if tr is not None and status != "resting":
                # Only a turn in flight can hold an Agent call open; a Stop or a
                # new prompt closes whatever result line never arrived.
                activity = max(tr.activity(), sub_activity, session.last_event)
                for agent_type in tr.open_agent_types():
                    agent = _agent_for(agents, agent_type, session.cwd)
                    if agent is None or agent["id"] not in views:
                        continue
                    live = "stuck" if now - activity > STUCK_AFTER_S else "working"
                    self._mark(views[agent["id"]], live, activity, f"running for {view['name']}", active=True)
        for sub_path, info in self.events.subagents.items():
            if sub_path in seen_sub:
                continue
            parent = self.events.sessions.get(info["parent"])
            if parent is None or now - parent.last_event > STALE_AFTER_S:
                continue
            parent_id = session_bot.get(info["parent"])
            parent_view = views.get(parent_id) if parent_id else None
            self._fold_subagent(sub_path, parent_view, views, agents, today, now, parent.cwd)

        for path in list(self.transcripts):
            if path not in self._used:
                del self.transcripts[path]

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
            "events": {"lines": self.events.lines, "bad": self.events.bad, "oversized": self.events.oversized,
                       "path": str(self.events.path)},
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
            "runs_active": 0,
            "runs_seen": 0,
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

    @staticmethod
    def _mark(view: Dict[str, Any], status: str, activity: float, step: Optional[str], active: bool) -> None:
        """Fold one status observation into a bot view: the highest status wins, newest breaks ties."""
        view["last_line_epoch"] = max(view["last_line_epoch"], activity)
        view["runs_seen"] += 1
        if active:
            view["runs_active"] += 1
        rank = STATUS_RANK[status]
        if rank > view["_rank"] or (rank == view["_rank"] and activity > view["_step_at"]):
            view["_rank"] = rank
            view["status"] = status
            view["_step_at"] = activity
            view["step"] = step

    def _fold(self, view: Dict[str, Any], status: str, stale: bool, session: Session,
              tr: Optional[Transcript], now: float) -> None:
        activity = max(session.last_event, tr.activity() if tr else 0.0)
        step = (tr.step if tr else None) or ("idle" if status == "resting" else None)
        before = view["_rank"]
        self._mark(view, status, activity, step, active=session.ended is None and not stale)
        if view["_rank"] != before or view["_step_at"] == activity:
            view["stale"] = stale
            if status == "waiting" and session.notification:
                view["waiting"] = {"message": session.notification["message"], "since": now_iso(session.notification["t"]),
                                   "type": session.notification["type"], "session_id": session.sid}
            elif status != "waiting":
                view["waiting"] = None
        if view.get("model_seen") is None and tr and tr.model:
            view["model_seen"] = tr.model

    def _fold_subagent(self, sub_path: str, parent_view: Optional[Dict[str, Any]],
                       views: Dict[str, Dict[str, Any]], agents: Dict[str, List[Dict[str, Any]]], today: str, now: float,
                       cwd: Optional[str]) -> None:
        info = self.events.subagents.get(sub_path)
        agent = _agent_for(agents, info["agent_type"], cwd) if info else None
        target = views.get(agent["id"]) if agent else parent_view
        if target is None:
            return
        tr = self.transcript(sub_path)
        if tr is None or tr.missing:
            return
        _add_tokens(target["tokens_today"], tr.tokens_for(today))
        activity = tr.activity()
        target["last_line_epoch"] = max(target["last_line_epoch"], activity)
        if target is parent_view:
            return
        stopped = bool(info and info.get("stopped"))
        if stopped or now - activity > STALE_AFTER_S:
            self._mark(target, "resting", activity, tr.step or "idle", active=False)
        else:
            live = "stuck" if now - activity > STUCK_AFTER_S else "working"
            self._mark(target, live, activity, tr.step, active=True)
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
    bound = server.server_address[1]
    print(f"Agent HQ  http://{HOST}:{bound}")
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


def _atomic_write(path: Path, text: str, mode: Optional[int] = None) -> None:
    """Replace the file in one step, through a symlink, keeping its mode.

    A new file gets `mode` (0o644 when not given). An existing file keeps the
    mode it had, and a symlink is written through, so a dotfile manager's
    real file is the one that changes.
    """
    target = path.resolve() if path.is_symlink() else path
    try:
        keep = target.stat().st_mode & 0o777
    except OSError:
        keep = mode if mode is not None else 0o644
    tmp = target.with_name(target.name + ".agent-hq.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, keep)
    os.replace(tmp, target)


def hook_command(hq_dir: Path) -> str:
    """The shell line the hooks run. $HOME form for the default dir, a baked path otherwise."""
    if hq_dir == (Path.home() / ".agent-hq"):
        where = '"$HOME/.agent-hq/hook.py"'
    else:
        where = '"' + str(hq_dir / "hook.py").replace('"', '\\"') + '"'
    return f"python3 {where} {HOOK_SUFFIX}"


def _is_ours(hook: Any) -> bool:
    return isinstance(hook, dict) and bool(HOOK_MARK.search(str(hook.get("command") or "")))


def _group_has_ours(group: Any) -> bool:
    return isinstance(group, dict) and any(_is_ours(h) for h in group.get("hooks") or [])


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
    shutil.copy2(path, backup, follow_symlinks=True)
    return backup


def merge_hooks(settings_path: Path, hq_dir: Path) -> Dict[str, Any]:
    """Add one Agent HQ hook per event, leaving every other hook untouched."""
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    if hooks is None:
        hooks = data["hooks"] = {}
    if not isinstance(hooks, dict):
        raise ValueError("settings.json 'hooks' is not an object")
    command = hook_command(hq_dir)
    added: List[str] = []
    for event in HOOK_EVENTS:
        groups = hooks.get(event)
        if groups is None:
            groups = hooks[event] = []
        if not isinstance(groups, list):
            raise ValueError(f"settings.json hooks.{event} is not a list")
        if any(_group_has_ours(g) for g in groups):
            continue
        groups.append({"hooks": [{"type": "command", "command": command, "timeout": HOOK_TIMEOUT_S}]})
        added.append(event)
    backup = None
    if added:
        backup = _backup(settings_path)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(settings_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return {"added": added, "backup": str(backup) if backup else None, "path": str(settings_path), "command": command}


def remove_hooks(settings_path: Path) -> Dict[str, Any]:
    """Remove the Agent HQ hook entries only; a group that still has other hooks stays."""
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    removed: List[str] = []
    if isinstance(hooks, dict):
        for event in list(hooks):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            kept_groups = []
            changed = False
            for group in groups:
                if not isinstance(group, dict):
                    kept_groups.append(group)
                    continue
                entries = group.get("hooks") or []
                kept = [h for h in entries if not _is_ours(h)]
                if len(kept) != len(entries):
                    changed = True
                    if kept:
                        group = dict(group)
                        group["hooks"] = kept
                        kept_groups.append(group)
                else:
                    kept_groups.append(group)
            if changed:
                removed.append(event)
                if kept_groups:
                    hooks[event] = kept_groups
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
    hq_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(hq_dir, 0o700)
    for private in ("events.jsonl", "roster.json", "roster.json.previous"):
        if (hq_dir / private).is_file():
            os.chmod(hq_dir / private, 0o600)
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
    missing = [n for n in INSTALL_FILES if not (hq_dir / n).is_file()]
    if missing:
        raise OSError(f"{', '.join(missing)} not found beside {app_dir / 'hq.py'}; the checkout is incomplete")
    return copied


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(app_dir: Path, hq_dir: Path, claude_dir: Path) -> Dict[str, Any]:
    copied = copy_files(app_dir, hq_dir)
    result = merge_hooks(claude_dir / "settings.json", hq_dir)
    result["copied"] = copied
    result["hq_dir"] = str(hq_dir)
    return result


def refresh_roster(hq_dir: Path, claude_dir: Path, extra_cwds: Iterable[str], write: bool) -> Tuple[Dict[str, Any], List[str]]:
    existing = load_roster(hq_dir, strict=True) if (hq_dir / "roster.json").exists() else None
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


def _confirm(question: str, assume_yes: bool) -> bool:
    """Ask on a terminal; without one (a service, a pipe) the answer is yes and says so."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{question} (no terminal to ask on, going ahead)")
        return True
    try:
        answer = input(f"{question} [Y/n] ").strip().lower()
    except EOFError:
        return True
    return answer in ("", "y", "yes")


def _show_roster(hq_dir: Path, claude_dir: Path, extra_cwds: List[str], assume_yes: bool, write: bool) -> Tuple[Dict[str, Any], bool]:
    roster, notes = refresh_roster(hq_dir, claude_dir, extra_cwds, write=False)
    print(roster_table(roster))
    for note in notes:
        print(note)
    if not write:
        return roster, False
    if not _confirm(f"Save this roster to {hq_dir / 'roster.json'}?", assume_yes):
        print("Not saved. Edit the agent files or pass --cwd, then run again.")
        return roster, False
    write_roster(hq_dir, roster)
    print(f"written to {hq_dir / 'roster.json'} ({len(roster['bots'])} bots)")
    return roster, True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hq.py", description="Agent HQ: a local 3D office for Claude Code sessions.")
    sub = parser.add_subparsers(dest="cmd")
    up = sub.add_parser("up", help="roster (asks for your OK the first time), hooks, then serve")
    up.add_argument("--port", type=int, default=PORT)
    up.add_argument("--yes", action="store_true", help="save the first roster without asking")
    up.add_argument("--cwd", action="append", default=[], help="extra folder to treat as a session lane")
    sv = sub.add_parser("serve", help="serve only")
    sv.add_argument("--port", type=int, default=PORT)
    sub.add_parser("install", help="merge the hooks into settings.json and copy the files into ~/.agent-hq")
    sub.add_parser("uninstall", help="remove the Agent HQ hooks from settings.json; data stays")
    r = sub.add_parser("roster", help="scan agents and session folders, show the roster, ask, merge it into roster.json")
    r.add_argument("--no-write", action="store_true", help="print only")
    r.add_argument("--yes", action="store_true", help="save without asking")
    r.add_argument("--json", action="store_true", help="print JSON instead of a table (implies --no-write)")
    r.add_argument("--cwd", action="append", default=[], help="extra folder to treat as a session lane")
    sub.add_parser("state", help="print /state once as JSON")
    args = parser.parse_args(argv)

    hq_dir = default_hq_dir()
    claude_dir = default_claude_dir()
    cmd = args.cmd or "up"
    if cmd == "up":
        port = getattr(args, "port", PORT)
        extra = [os.path.abspath(c) for c in getattr(args, "cwd", [])] + _cwd_hint()
        if not (hq_dir / "roster.json").exists():
            _, saved = _show_roster(hq_dir, claude_dir, extra, getattr(args, "yes", False), write=True)
            if not saved:
                return 1
        else:
            try:
                load_roster(hq_dir, strict=True)
            except ValueError as exc:
                sys.stderr.write(f"Agent HQ: {exc}. Serving with an empty roster until it is fixed.\n")
        try:
            result = install(APP_DIR, hq_dir, claude_dir)
            print(f"hooks   {result['path']}: " + (f"added {', '.join(result['added'])}" if result["added"] else "already present"))
            if result["backup"]:
                print(f"backup  {result['backup']}")
            if result["copied"]:
                print(f"copied  {', '.join(result['copied'])} into {hq_dir}")
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: hooks not installed, {exc}. Fix {claude_dir / 'settings.json'} and run install again.\n")
        return serve(hq_dir, APP_DIR, port)
    if cmd == "serve":
        return serve(hq_dir, APP_DIR, args.port)
    if cmd == "install":
        try:
            result = install(APP_DIR, hq_dir, claude_dir)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: hooks not installed, {exc}.\n")
            return 2
        print(json.dumps(result, indent=2))
        return 0
    if cmd == "uninstall":
        try:
            result = remove_hooks(claude_dir / "settings.json")
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"Agent HQ: nothing removed, {exc}.\n")
            return 2
        print(json.dumps(result, indent=2))
        return 0
    if cmd == "roster":
        extra = [os.path.abspath(c) for c in args.cwd] + _cwd_hint()
        try:
            if args.json:
                roster, _ = refresh_roster(hq_dir, claude_dir, extra, write=False)
                print(json.dumps(roster, indent=2, ensure_ascii=False))
                return 0
            _show_roster(hq_dir, claude_dir, extra, args.yes, write=not args.no_write)
        except ValueError as exc:
            sys.stderr.write(f"Agent HQ: {exc}. Nothing was written.\n")
            return 2
        return 0
    if cmd == "state":
        print(json.dumps(State(hq_dir).snapshot(force=True), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
