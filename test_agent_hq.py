"""Agent HQ, the local 3D office under tools/agent_hq, tested offline.

No network, no database, no model call. Covers the hook (one JSON line, exit
0, never the prompt text), the settings merge (keeps other hooks, idempotent,
reversible, refuses a broken file), token counting (once per message id, by
local day, incremental), the status rules, the roster scan and merge, the
server's routes and headers, the vendored Three.js pin and the dash ban.
"""
from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
APP = ROOT / "tools" / "agent_hq"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"agent_hq_{name}", APP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hq = _load("hq")
hook = _load("hook")


def _iso(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="seconds")


def _line(**row) -> str:
    return json.dumps(row) + "\n"


def _assistant(mid: str, ts: datetime, blocks, usage=None, model="claude-sonnet-4-5"):
    usage = usage or {"input_tokens": 100, "output_tokens": 10, "cache_read_input_tokens": 1000,
                      "cache_creation_input_tokens": 50}
    return "".join(
        _line(type="assistant", timestamp=ts.astimezone().isoformat(), cwd="/w",
              message={"id": mid, "model": model, "usage": usage, "content": [block]})
        for block in blocks
    )


# --------------------------------------------------------------------------- hook


def _run_hook(payload, env_dir: Path, raw: str | None = None):
    env = dict(os.environ, AGENT_HQ_DIR=str(env_dir))
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run([sys.executable, str(APP / "hook.py")], input=data, text=True,
                          capture_output=True, env=env, timeout=30)


def test_the_hook_writes_one_line_and_prints_nothing(tmp_path):
    roster = {"bots": [{"id": "session:/w/repo", "name": "repo", "kind": "session", "cwd": "/w/repo"}]}
    (tmp_path / "roster.json").write_text(json.dumps(roster))
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": "/w/repo/sub",
               "transcript_path": "/w/t.jsonl", "prompt": "SECRET PROMPT TEXT", "source": "user"}
    result = _run_hook(payload, tmp_path)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["event"] == "UserPromptSubmit" and row["session_id"] == "s1"
    assert row["bot"] == "repo", "the longest folder match names the bot"
    assert row["source"] == "user" and row["transcript_path"] == "/w/t.jsonl"
    assert "SECRET PROMPT TEXT" not in lines[0] and "prompt" not in row
    assert hq.parse_ts(row["t"]) is not None


def test_the_hook_keeps_the_notification_message_and_the_stop_summary(tmp_path):
    _run_hook({"hook_event_name": "Notification", "session_id": "s1", "cwd": "/w",
               "message": "Claude needs your permission to use Bash", "notification_type": "permission_prompt"}, tmp_path)
    _run_hook({"hook_event_name": "Stop", "session_id": "s1", "cwd": "/w",
               "last_assistant_message": "  Done.\n\nAll   tests pass. " + "x" * 500}, tmp_path)
    _run_hook({"hook_event_name": "SubagentStop", "session_id": "s1", "cwd": "/w", "agent_type": "verifier",
               "agent_id": "a1", "agent_transcript_path": "/w/s1/subagents/agent-a1.jsonl"}, tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert rows[0]["message"] == "Claude needs your permission to use Bash"
    assert rows[0]["notification_type"] == "permission_prompt"
    assert rows[1]["summary"].startswith("Done. All tests pass. ") and len(rows[1]["summary"]) == 200
    assert rows[2]["agent_type"] == "verifier" and rows[2]["agent_transcript_path"].endswith("agent-a1.jsonl")
    assert rows[2]["bot"] == "w", "no roster: the folder name stands in"


def test_the_hook_exits_zero_on_garbage_and_on_an_unwritable_dir(tmp_path):
    result = _run_hook(None, tmp_path, raw="this is not json")
    assert result.returncode == 0 and result.stdout == ""
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    result = _run_hook({"hook_event_name": "Stop"}, blocker)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""


def test_pick_bot_prefers_the_agent_then_the_longest_folder():
    roster = {"bots": [
        {"name": "verifier", "kind": "agent"},
        {"name": "outer", "kind": "session", "cwd": "/w"},
        {"name": "inner", "kind": "session", "cwd": "/w/inner/"},
        {"name": "gone", "kind": "session", "cwd": "/w/inner/deep", "retired": True},
    ]}
    assert hook.pick_bot(roster, "/w/inner/deep/x", "verifier") == "verifier"
    assert hook.pick_bot(roster, "/w/inner/deep/x", None) == "inner"
    assert hook.pick_bot(roster, "/w/other", None) == "outer"
    assert hook.pick_bot(roster, "/elsewhere/proj", None) == "proj"
    assert hook.pick_bot({}, None, None) is None


# --------------------------------------------------------------------------- settings merge


def test_the_hook_command_is_quiet_and_never_blocks():
    assert hq.HOOK_COMMAND.endswith("|| true")
    assert ">/dev/null 2>&1" in hq.HOOK_COMMAND, "SessionStart and UserPromptSubmit stdout is injected into context"
    assert "${AGENT_HQ_DIR:-$HOME/.agent-hq}/hook.py" in hq.HOOK_COMMAND
    assert hq.HOOK_EVENTS == ("SessionStart", "UserPromptSubmit", "Notification", "Stop", "SubagentStop", "SessionEnd")


def test_merge_keeps_other_hooks_is_idempotent_and_reverses(tmp_path):
    settings = tmp_path / "settings.json"
    before = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "echo keep-me"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo pre"}]}],
        },
    }
    settings.write_text(json.dumps(before))
    first = hq.merge_hooks(settings)
    assert first["added"] == list(hq.HOOK_EVENTS)
    assert first["backup"] and Path(first["backup"]).exists()
    assert json.loads(Path(first["backup"]).read_text()) == before
    after = json.loads(settings.read_text())
    assert after["permissions"] == before["permissions"]
    assert after["hooks"]["PreToolUse"] == before["hooks"]["PreToolUse"]
    assert after["hooks"]["Stop"][0] == before["hooks"]["Stop"][0]
    assert len(after["hooks"]["Stop"]) == 2
    for event in hq.HOOK_EVENTS:
        ours = [g for g in after["hooks"][event] if hq._is_ours(g)]
        assert len(ours) == 1 and ours[0]["hooks"][0]["command"] == hq.HOOK_COMMAND
        assert ours[0]["hooks"][0]["timeout"] == hq.HOOK_TIMEOUT_S

    second = hq.merge_hooks(settings)
    assert second["added"] == [] and second["backup"] is None
    assert json.loads(settings.read_text()) == after
    assert len(list(tmp_path.glob("settings.json.agent-hq-backup-*"))) == 1

    removed = hq.remove_hooks(settings)
    assert set(removed["removed"]) == set(hq.HOOK_EVENTS)
    assert json.loads(settings.read_text()) == before


def test_merge_recognises_the_old_command_spelling():
    group = {"hooks": [{"type": "command", "command": 'python3 "$HOME/.agent-hq/hook.py" >/dev/null 2>&1 || true'}]}
    assert hq._is_ours(group)
    assert not hq._is_ours({"hooks": [{"type": "command", "command": "python3 other/hook.py"}]})


def test_merge_creates_a_missing_settings_file_and_refuses_a_broken_one(tmp_path):
    settings = tmp_path / "nested" / "settings.json"
    result = hq.merge_hooks(settings)
    assert result["added"] == list(hq.HOOK_EVENTS) and result["backup"] is None
    data = json.loads(settings.read_text())
    assert set(data) == {"hooks"} and set(data["hooks"]) == set(hq.HOOK_EVENTS)

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(ValueError):
        hq.merge_hooks(broken)
    assert broken.read_text() == "{not json"
    listy = tmp_path / "list.json"
    listy.write_text("[]")
    with pytest.raises(ValueError):
        hq.merge_hooks(listy)


def test_install_copies_the_files_once(tmp_path):
    hq_dir = tmp_path / "hq"
    claude_dir = tmp_path / "claude"
    result = hq.install(APP, hq_dir, claude_dir)
    assert set(result["copied"]) == set(hq.INSTALL_FILES) | set(hq.VENDOR_FILES)
    assert (hq_dir / "hook.py").read_bytes() == (APP / "hook.py").read_bytes()
    assert (hq_dir / "vendor" / "three.core.js").exists()
    again = hq.install(APP, hq_dir, claude_dir)
    assert again["copied"] == [] and again["added"] == []


# --------------------------------------------------------------------------- tokens


def test_tokens_count_once_per_message_id_and_by_local_day(tmp_path):
    now = datetime.now().astimezone()
    yesterday = now - timedelta(days=1)
    path = tmp_path / "t.jsonl"
    text = _assistant("m0", yesterday, [{"type": "text", "text": "old"}])
    text += _line(type="user", timestamp=now.isoformat(), cwd="/w", message={"role": "user", "content": "hi"})
    text += _assistant("m1", now, [
        {"type": "thinking", "thinking": "..."},
        {"type": "text", "text": "Running the   tests now."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q", "description": "Run the suite"}},
    ])
    text += _line(type="progress", timestamp=now.isoformat())
    text += "not json at all\n"
    path.write_text(text)

    tr = hq.Transcript(str(path))
    tr.refresh()
    today = hq.local_day(now.timestamp())
    assert tr.tokens_for(today) == {"input": 100, "output": 10, "cache_read": 1000, "cache_create": 50, "total": 1160, "calls": 1}
    assert tr.tokens_for(hq.local_day(yesterday.timestamp()))["total"] == 1160
    assert tr.bad == 1 and tr.model == "claude-sonnet-4-5"
    assert tr.step == "Bash: Run the suite"
    assert tr.summary_before(now.timestamp()) == "Running the tests now."

    with path.open("a") as handle:
        handle.write(_assistant("m2", now, [{"type": "text", "text": "Done"}], usage={"input_tokens": 1, "output_tokens": 2}))
    tr.refresh()
    assert tr.tokens_for(today)["total"] == 1163 and tr.tokens_for(today)["calls"] == 2
    assert tr.step == "says: Done"

    path.write_text(_assistant("m9", now, [{"type": "text", "text": "fresh"}], usage={"input_tokens": 5, "output_tokens": 5}))
    tr.refresh()
    assert tr.tokens_for(today)["total"] == 10, "a truncated file is read again from the start"


def test_a_partial_trailing_line_is_held_until_it_completes(tmp_path):
    now = datetime.now().astimezone()
    path = tmp_path / "t.jsonl"
    full = _assistant("m1", now, [{"type": "text", "text": "a"}], usage={"input_tokens": 7, "output_tokens": 0})
    path.write_text(full[:-10])
    tr = hq.Transcript(str(path))
    tr.refresh()
    assert tr.tokens_for(hq.local_day(now.timestamp()))["total"] == 0
    with path.open("a") as handle:
        handle.write(full[-10:])
    tr.refresh()
    assert tr.tokens_for(hq.local_day(now.timestamp()))["total"] == 7


def test_usage_without_a_message_id_is_counted_per_line(tmp_path):
    now = datetime.now().astimezone()
    path = tmp_path / "t.jsonl"
    row = {"type": "assistant", "timestamp": now.isoformat(), "message": {"usage": {"input_tokens": 1, "output_tokens": 1}, "content": []}}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    tr = hq.Transcript(str(path))
    tr.refresh()
    assert tr.tokens_for(hq.local_day(now.timestamp()))["calls"] == 2


def test_parse_ts_accepts_z_offsets_and_epochs():
    assert hq.parse_ts("2026-11-03T05:16:00Z") == hq.parse_ts("2026-11-03T05:16:00+00:00")
    assert hq.parse_ts("2026-11-03T01:16:00-04:00") == hq.parse_ts("2026-11-03T05:16:00Z")
    assert hq.parse_ts(1_700_000_000) == 1_700_000_000.0
    assert hq.parse_ts(1_700_000_000_000) == 1_700_000_000.0
    assert hq.parse_ts("nope") is None and hq.parse_ts(None) is None


# --------------------------------------------------------------------------- status rules


class _Tr:
    def __init__(self, mtime, last_ts=None, step=None, model=None):
        self.mtime = mtime
        self.last_ts = last_ts
        self.step = step
        self.model = model
        self.missing = False


def _session(**kw):
    s = hq.Session(kw.pop("sid", "s"))
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_status_rules():
    now = 1_000_000.0
    tr = _Tr(mtime=now - 30, last_ts=now - 30)
    assert hq.session_status(_session(started=now - 100), tr, now) == ("resting", False), "no prompt yet"
    working = _session(started=now - 100, last_prompt=now - 90, last_event=now - 90)
    assert hq.session_status(working, tr, now) == ("working", False)
    assert hq.session_status(working, _Tr(mtime=now - 601, last_ts=now - 601), now) == ("working", False), "the prompt itself is 90s old"
    long_turn = _session(started=now - 800, last_prompt=now - 700, last_event=now - 700)
    assert hq.session_status(long_turn, _Tr(mtime=now - 601, last_ts=now - 601), now) == ("stuck", False)
    assert hq.session_status(long_turn, _Tr(mtime=now - 599, last_ts=now - 599), now) == ("working", False)
    assert hq.session_status(long_turn, None, now) == ("stuck", False), "no transcript at all after 700s"
    stopped = _session(started=now - 100, last_prompt=now - 90, last_stop=now - 10, last_event=now - 10)
    assert hq.session_status(stopped, tr, now) == ("resting", False)
    ended = _session(started=now - 100, last_prompt=now - 90, ended=now - 5, last_event=now - 5)
    assert hq.session_status(ended, tr, now) == ("resting", False)
    stale = _session(started=now - 90000, last_prompt=now - 89000, last_event=now - 89000)
    assert hq.session_status(stale, _Tr(mtime=now - 89000, last_ts=now - 89000), now) == ("resting", True)


def test_waiting_is_a_notification_nothing_has_answered():
    now = 1_000_000.0
    note = {"t": now - 20, "message": "permission?", "type": "permission_prompt"}
    s = _session(started=now - 100, last_prompt=now - 90, last_event=now - 20, notification=note)
    assert hq.session_status(s, _Tr(mtime=now - 25, last_ts=now - 25), now) == ("waiting", False)
    assert hq.session_status(s, None, now) == ("waiting", False)
    answered = _Tr(mtime=now - 5, last_ts=now - 5)
    assert hq.session_status(s, answered, now) == ("working", False), "a turn line after the notification means it was answered"
    s.last_stop = now - 10
    assert hq.session_status(s, _Tr(mtime=now - 25, last_ts=now - 25), now) == ("resting", False), "a Stop after it closes it"
    idle = _session(started=now - 100, last_prompt=now - 90, last_stop=now - 60, last_event=now - 5,
                    notification={"t": now - 5, "message": "waiting for input", "type": "idle_prompt"})
    assert hq.session_status(idle, _Tr(mtime=now - 60, last_ts=now - 60), now) == ("resting", False)
    assert hq.IDLE_IS_WAITING is False
    prompt_after = _session(started=now - 100, last_prompt=now - 1, last_event=now - 1,
                            notification={"t": now - 20, "message": "old", "type": "permission_prompt"})
    assert hq.session_status(prompt_after, _Tr(mtime=now - 1, last_ts=now - 1), now) == ("working", False)


# --------------------------------------------------------------------------- roster


def test_frontmatter_and_team_inference():
    text = '---\nname: "scanner"\ndescription: Read-only scan stage.\n  Never edits.\ntools: Read, Grep\nmodel: sonnet\n---\nbody: not frontmatter\n'
    front = hq.parse_frontmatter(text)
    assert front == {"name": "scanner", "description": "Read-only scan stage. Never edits.", "tools": "Read, Grep", "model": "sonnet"}
    assert hq.parse_frontmatter("no front matter") == {}
    assert hq.infer_team("scanner", "Read-only scan stage") == "Research"
    assert hq.infer_team("editor", "Applies exactly one fix") == "Ops"
    assert hq.infer_team("thumbnailer", "draws the thumbnail image") == "Visuals"
    assert hq.infer_team("tqo-writer", "writes the episode script") == "Content"
    assert hq.infer_team("specific", "nothing here") == "Ops", "short keywords match whole words only"
    assert hq.infer_team("checker", "Verifies each finding again.") == "Research", "stems cover inflections"
    assert hq.infer_team("db", "the postgres migration helper") == "Ops", "post needs a whole word"
    assert hq.infer_team("editor", "") == "Ops"


def _fake_claude(tmp_path: Path, project: Path, model="claude-opus-4-1"):
    claude = tmp_path / "claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "agents" / "scribe.md").write_text("---\nname: scribe\ndescription: Writes the weekly newsletter draft.\nmodel: opus\n---\n")
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / "checker.md").write_text("---\ndescription: Verifies each finding again.\n---\n")
    folder = claude / "projects" / "-enc-project"
    folder.mkdir(parents=True)
    now = datetime.now().astimezone()
    (folder / "sess.jsonl").write_text(
        _line(type="ai-title", sessionId="sess")
        + _line(type="user", timestamp=now.isoformat(), cwd=str(project), message={"content": "x"})
        + _assistant("m1", now, [{"type": "text", "text": "hi"}], model=model)
    )
    (claude / "projects" / "-no-cwd").mkdir()
    (claude / "projects" / "-no-cwd" / "a.jsonl").write_text(_line(type="ai-title", sessionId="a"))
    return claude


def test_scan_roster_finds_user_agents_project_agents_and_lanes(tmp_path):
    project = tmp_path / "work" / "proj"
    claude = _fake_claude(tmp_path, project)
    bots, notes = hq.scan_roster(claude)
    by_name = {b["name"]: b for b in bots}
    assert set(by_name) == {"scribe", "checker", "proj"}
    assert by_name["scribe"]["kind"] == "agent" and by_name["scribe"]["scope"] == "user" and by_name["scribe"]["cwd"] is None
    assert by_name["scribe"]["team"] == "Content" and by_name["scribe"]["model"] == "opus"
    assert by_name["checker"]["scope"] == "project" and by_name["checker"]["cwd"] == str(project)
    assert by_name["checker"]["model"] == "inherit" and by_name["checker"]["team"] == "Research"
    assert by_name["proj"]["kind"] == "session" and by_name["proj"]["model"] == "claude-opus-4-1"
    assert by_name["proj"]["id"] == f"session:{project}"
    assert notes == ["skipped -no-cwd: no transcript line carries a cwd"]


def test_merge_roster_keeps_edits_refreshes_files_and_retires_the_gone():
    scanned = [{"id": "agent:a@user", "name": "a", "kind": "agent", "job": "new job", "model": "haiku", "team": "Ops", "source": "/a.md"},
               {"id": "session:/w", "name": "w", "kind": "session", "job": "Sessions run in /w", "model": "m", "team": "Ops", "cwd": "/w"}]
    existing = {"bots": [{"id": "agent:a@user", "name": "Alpha", "kind": "agent", "job": "my words", "model": "opus", "team": "Content"},
                         {"id": "agent:old@user", "name": "old", "kind": "agent", "job": "", "model": "x", "team": "Ops"}]}
    merged = hq.merge_roster(existing, scanned)
    by_id = {b["id"]: b for b in merged["bots"]}
    assert by_id["agent:a@user"]["name"] == "Alpha" and by_id["agent:a@user"]["team"] == "Content"
    assert by_id["agent:a@user"]["job"] == "my words" and by_id["agent:a@user"]["model"] == "haiku"
    assert by_id["agent:old@user"]["retired"] is True
    assert "retired" not in by_id["session:/w"]
    assert merged["version"] == 1 and hq.parse_ts(merged["generated"])
    table = hq.roster_table(merged)
    assert "Alpha" in table and "retired (file gone" in table and "old" in table


def test_team_order_and_disambiguation():
    assert hq.team_order(["Ops", "Unassigned", "Zeta", "Research"]) == ["Research", "Ops", "Zeta", "Unassigned"]
    bots = [{"name": "repo", "cwd": "/a/repo"}, {"name": "repo", "cwd": "/b/repo"}, {"name": "solo", "cwd": "/c/solo"}]
    hq._disambiguate(bots)
    assert [b["name"] for b in bots] == ["repo (a)", "repo (b)", "solo"]


# --------------------------------------------------------------------------- state and server


def _state_fixture(tmp_path: Path):
    hq_dir = tmp_path / "hq"
    hq_dir.mkdir()
    now = datetime.now().astimezone()
    project = tmp_path / "proj"
    project.mkdir()
    transcript = tmp_path / "sess.jsonl"
    transcript.write_text(_assistant("m1", now - timedelta(seconds=40), [
        {"type": "tool_use", "name": "Bash", "input": {"description": "Run the suite"}}]))
    roster = {"version": 1, "bots": [
        {"id": f"session:{project}", "name": "proj", "kind": "session", "team": "Ops", "model": "inherit", "cwd": str(project), "job": "j"},
        {"id": "agent:verifier@x", "name": "verifier", "kind": "agent", "team": "Research", "model": "sonnet", "job": "v"},
    ]}
    (hq_dir / "roster.json").write_text(json.dumps(roster))
    events = hq_dir / "events.jsonl"

    def emit(event, t, **extra):
        row = {"t": _iso(t), "event": event, "session_id": "s1", "cwd": str(project / "sub"), "transcript_path": str(transcript), "bot": "proj"}
        row.update(extra)
        with events.open("a") as handle:
            handle.write(json.dumps(row) + "\n")

    return hq_dir, now, emit, transcript, project


def test_state_follows_the_session_through_its_day(tmp_path):
    hq_dir, now, emit, transcript, project = _state_fixture(tmp_path)
    state = hq.State(hq_dir)
    emit("SessionStart", now - timedelta(seconds=60), source="startup")
    emit("UserPromptSubmit", now - timedelta(seconds=50), source="user")
    snap = state.snapshot(now=now.timestamp(), force=True)
    proj = next(b for b in snap["bots"] if b["name"] == "proj")
    assert proj["status"] == "working" and proj["step"] == "Bash: Run the suite"
    assert proj["tokens_today"]["total"] == 1160 and snap["tokens_total_today"] == 1160
    assert proj["model_seen"] == "claude-sonnet-4-5" and proj["sessions_active"] == 1
    assert snap["counts"] == {"waiting": 0, "stuck": 0, "working": 1, "resting": 1}
    assert snap["teams"] == ["Research", "Ops"]

    emit("Notification", now - timedelta(seconds=30), message="Claude needs your permission to use Bash", notification_type="permission_prompt")
    snap = state.snapshot(now=now.timestamp(), force=True)
    proj = next(b for b in snap["bots"] if b["name"] == "proj")
    assert proj["status"] == "waiting"
    assert snap["waiting"] == [{"bot": "proj", "bot_id": f"session:{project}", "team": "Ops",
                                "message": "Claude needs your permission to use Bash",
                                "since": _iso(now - timedelta(seconds=30)), "type": "permission_prompt"}]

    emit("Stop", now - timedelta(seconds=10), summary="Suite is green, 12 passed.")
    snap = state.snapshot(now=now.timestamp(), force=True)
    proj = next(b for b in snap["bots"] if b["name"] == "proj")
    assert proj["status"] == "resting" and snap["waiting"] == []
    assert [f["summary"] for f in snap["finished_today"]] == ["Suite is green, 12 passed."]
    assert snap["finished_today"][0]["bot"] == "proj"

    emit("UserPromptSubmit", now - timedelta(seconds=8), source="user")
    os.utime(transcript, (now.timestamp() - 700, now.timestamp() - 700))
    snap = state.snapshot(now=now.timestamp(), force=True)
    proj = next(b for b in snap["bots"] if b["name"] == "proj")
    assert proj["status"] == "working", "the prompt event itself is 8 seconds old, so the lane is alive"
    snap = state.snapshot(now=now.timestamp() + 700, force=True)
    proj = next(b for b in snap["bots"] if b["name"] == "proj")
    assert proj["status"] == "stuck"


def test_an_unknown_folder_gets_an_unassigned_desk_and_a_subagent_feeds_its_agent(tmp_path):
    hq_dir, now, emit, transcript, project = _state_fixture(tmp_path)
    events = hq_dir / "events.jsonl"
    with events.open("a") as handle:
        handle.write(json.dumps({"t": _iso(now), "event": "SessionStart", "session_id": "s9", "cwd": "/elsewhere/mystery",
                                 "transcript_path": str(tmp_path / "none.jsonl")}) + "\n")
    sub_dir = tmp_path / "sess" / "subagents"
    sub_dir.mkdir(parents=True)
    (sub_dir / "agent-1.jsonl").write_text(_assistant("v1", now, [{"type": "text", "text": "checked"}], usage={"input_tokens": 3, "output_tokens": 4}))
    emit("SessionStart", now - timedelta(seconds=60), source="startup")
    emit("UserPromptSubmit", now - timedelta(seconds=50), source="user")
    state = hq.State(hq_dir)
    snap = state.snapshot(now=now.timestamp(), force=True)
    names = {b["name"]: b for b in snap["bots"]}
    assert names["mystery"]["team"] == "Unassigned" and snap["teams"][-1] == "Unassigned"
    assert names["proj"]["tokens_today"]["total"] == 1160 + 7, "an unattributed subagent counts for its parent"
    assert names["verifier"]["tokens_today"]["total"] == 0
    emit("SubagentStop", now, agent_type="verifier", agent_transcript_path=str(sub_dir / "agent-1.jsonl"))
    snap = state.snapshot(now=now.timestamp(), force=True)
    names = {b["name"]: b for b in snap["bots"]}
    assert names["verifier"]["tokens_today"]["total"] == 7 and names["verifier"]["status"] == "resting"
    assert names["proj"]["tokens_today"]["total"] == 1160


def test_events_file_rotation_and_bad_lines(tmp_path):
    hq_dir, now, emit, transcript, project = _state_fixture(tmp_path)
    (hq_dir / "events.jsonl").write_text("garbage\n[1,2]\n")
    emit("SessionStart", now)
    ev = hq.Events(hq_dir / "events.jsonl")
    ev.refresh()
    assert ev.bad == 2 and ev.lines == 3 and "s1" in ev.sessions
    (hq_dir / "events.jsonl").write_text("")
    ev.refresh()
    assert ev.sessions == {} and ev.bad == 0


@pytest.fixture()
def server(tmp_path):
    hq_dir, now, emit, transcript, project = _state_fixture(tmp_path)
    emit("SessionStart", now - timedelta(seconds=60), source="startup")
    srv = hq.make_server(hq_dir, APP, "127.0.0.1", 0)
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _get(port: int, path: str, host: str | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host} if host else {}
    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, dict(resp.getheaders()), body


def test_server_routes_and_headers(server):
    status, headers, body = _get(server, "/")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert b"<title>Agent HQ</title>" in body
    assert headers["Content-Security-Policy"].startswith("default-src 'none'; script-src 'self'")
    assert headers["X-Content-Type-Options"] == "nosniff" and headers["Cache-Control"] == "no-store"
    assert headers["X-Frame-Options"] == "DENY"
    status, headers, body = _get(server, "/app.js")
    assert status == 200 and headers["Content-Type"].startswith("text/javascript")
    assert b"./vendor/three.module.js" in body
    status, headers, body = _get(server, "/state")
    assert status == 200
    snap = json.loads(body)
    assert {"now", "bots", "counts", "waiting", "finished_today", "teams", "tokens_total_today"} <= set(snap)
    assert [b["name"] for b in snap["bots"]] == ["proj", "verifier"]
    status, headers, body = _get(server, "/health")
    assert status == 200 and json.loads(body) == {"ok": True}


def test_server_serves_only_the_pinned_vendor_files(server):
    manifest = {}
    for line in (APP / "vendor" / "MANIFEST.sha256").read_text().splitlines():
        digest, name = line.split()
        manifest[name] = digest
    for name in hq.VENDOR_FILES:
        status, headers, body = _get(server, f"/vendor/{name}")
        assert status == 200, name
        assert hashlib.sha256(body).hexdigest() == manifest[name], name
        assert headers["Cache-Control"].startswith("public, max-age=")
    assert _get(server, "/vendor/../hq.py")[0] == 404
    assert _get(server, "/vendor/hq.py")[0] == 404
    assert _get(server, "/hq.py")[0] == 404
    assert _get(server, "/roster.json")[0] == 404
    assert _get(server, "/nope")[0] == 404


def test_server_refuses_a_foreign_host_header(server):
    assert _get(server, "/state", host="evil.example.com")[0] == 403
    assert _get(server, "/state", host="127.0.0.1.evil.example.com")[0] == 403
    assert _get(server, "/state", host=f"localhost:{server}")[0] == 200
    assert _get(server, "/state", host="[::1]:7777")[0] == 200
    assert hq.host_allowed("LOCALHOST") and not hq.host_allowed("") and not hq.host_allowed("127.0.0.2")


def test_the_state_snapshot_is_cached_for_a_moment(tmp_path):
    hq_dir, now, emit, transcript, project = _state_fixture(tmp_path)
    state = hq.State(hq_dir)
    first = state.snapshot(now=now.timestamp())
    emit("SessionStart", now)
    assert state.snapshot(now=now.timestamp() + 0.5) is first
    assert state.snapshot(now=now.timestamp() + hq.STATE_TTL_S + 0.1) is not first


def test_cli_state_and_roster_run_offline(tmp_path):
    project = tmp_path / "work" / "proj"
    claude = _fake_claude(tmp_path, project)
    env = dict(os.environ, AGENT_HQ_DIR=str(tmp_path / "hq"), CLAUDE_CONFIG_DIR=str(claude))
    result = subprocess.run([sys.executable, str(APP / "hq.py"), "roster", "--json"], env=env, capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr
    roster = json.loads(result.stdout)
    assert {b["name"] for b in roster["bots"]} >= {"scribe", "checker", "proj"}
    assert (tmp_path / "hq" / "roster.json").exists()
    result = subprocess.run([sys.executable, str(APP / "hq.py"), "state"], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    snap = json.loads(result.stdout)
    assert snap["counts"]["resting"] == len(snap["bots"]) >= 3


# --------------------------------------------------------------------------- pins and prose


def test_vendored_three_matches_the_manifest():
    manifest = dict(reversed(line.split()) for line in (APP / "vendor" / "MANIFEST.sha256").read_text().splitlines())
    assert set(manifest) == set(hq.VENDOR_FILES) == {"three.module.js", "three.core.js", "LICENSE"}
    for name, digest in manifest.items():
        assert hashlib.sha256((APP / "vendor" / name).read_bytes()).hexdigest() == digest, name
    assert b"REVISION = '187'" in (APP / "vendor" / "three.core.js").read_bytes()
    assert "0.187.0" in (APP / "vendor" / "UPSTREAM.txt").read_text()


def test_no_dashes_in_the_delivered_files():
    files = [p for p in APP.rglob("*") if p.is_file() and "vendor" not in p.parts and "__pycache__" not in p.parts]
    files.append(Path(__file__))
    assert len(files) >= 6
    for path in files:
        text = path.read_text(encoding="utf-8")
        for bad in (chr(0x2014), chr(0x2013)):
            assert bad not in text, f"{path.name} carries a dash"


def test_the_hook_is_small_and_imports_only_the_standard_library():
    text = (APP / "hook.py").read_text()
    assert len(text.splitlines()) < 120
    imports = {line.split()[1] for line in text.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"json", "os", "sys", "datetime"}
    assert "urllib" not in text and "socket" not in text and "http" not in text
    hq_text = (APP / "hq.py").read_text()
    assert "urllib.request" not in hq_text and "import socket" not in hq_text
    assert 'HOST = "127.0.0.1"' in hq_text


def test_time_helpers_round_trip():
    epoch = 1_762_000_000.0
    assert abs(hq.parse_ts(hq.now_iso(epoch)) - epoch) < 1
    assert hq.local_day(epoch) == datetime.fromtimestamp(epoch).strftime("%Y-%m-%d")
    assert hq.squash("  a \n b  ", 3) == "a b"
    assert hq.squash("  a \n b  ", 2) == "a" + chr(0x2026)
    assert hq.describe_tool({"name": "Read", "input": {"file_path": "/x/y.py"}}) == "Read: /x/y.py"
    assert hq.describe_tool({"name": "Agent", "input": {"other": 1}}) == "Agent"


def test_server_start_is_quick(tmp_path):
    hq_dir = tmp_path / "hq"
    hq_dir.mkdir()
    started = time.time()
    srv = hq.make_server(hq_dir, APP, "127.0.0.1", 0)
    srv.server_close()
    assert time.time() - started < 2
