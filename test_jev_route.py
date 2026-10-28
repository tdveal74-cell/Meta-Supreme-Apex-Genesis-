"""
The Jev router, rebuilt as an allowlist, tested against the ways it could leak
what it should not send or overrun its time.

Ruled by Tee 2026-10-16 (.claude/hooks/jev_route.py), held as PR #368, and on
2026-10-17 rebuilt as an allowlist on a card: "Hold it, rebuild as allowlist".
The held version scrubbed the raw call. This one builds the outbound text from
a short list of pieces (tool name, program names, flag names, file paths, field
names) and the tests below pin that nothing else is sent, whatever is put in the
call. They drive the hook against a stub server on 127.0.0.1 that answers in
the shape of TypeSafe's published OpenAPI spec, and pin the promises the module
docstring makes: it never prints allow, it fails open with a ledger row on every
call, a deny stands only once its ledger row is written, and the whole hook
stays inside its time budget on any input up to 1 MB.

They prove the hook's own logic and nothing about Jev's judgment, which only a
live call can measure.

Standalone: no database, no network beyond loopback, no repository state
beyond the files.
"""

from __future__ import annotations

import ast
import http.server
import importlib.util
import io
import json
import os
import pathlib
import random
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

try:
    import re._parser as sre_parse
except ImportError:  # pragma: no cover - Python before 3.11
    import sre_parse

ROOT = pathlib.Path(__file__).parent
HOOK = ROOT / ".claude" / "hooks" / "jev_route.py"
WRAPPER = (
    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/jev_route.py"; rc=$?; '
    '[ $rc -eq 0 ] || { echo "jev_route hook failed rc=$rc" >&2; exit 1; }'
)


def fresh_module():
    spec = importlib.util.spec_from_file_location("jev_route_fresh", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jev = fresh_module()
SHIPPED_ENFORCE = jev.ENFORCE
NOW = datetime(2026, 10, 17, 18, 0, 0, tzinfo=timezone.utc)
DEAD = "http://127.0.0.1:9/v1/systemone"
MEGABYTE = 1024 * 1024


class Stub:
    """A loopback server that records each request and answers as told."""

    def __init__(self):
        self.requests = []
        self.reply = None
        self.delay = 0.0
        self.redirect_to = None
        self.answer(0.1, 0.1)
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _send(self):
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw_in = self.rfile.read(length) if length else b""
                stub.requests.append({"path": self.path, "method": self.command, "headers": dict(self.headers),
                                      "body": json.loads(raw_in) if raw_in else None})
                time.sleep(stub.delay)
                if stub.redirect_to and self.path.endswith("/v1/systemone"):
                    self.send_response(302)
                    self.send_header("Location", stub.redirect_to)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status, body = stub.reply
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_POST = _send
            do_GET = _send

            def log_message(self, *args):
                pass

        class Quiet(http.server.ThreadingHTTPServer):
            """A client that gave up on a slow answer is the point of some tests."""

            def handle_error(self, request, client_address):
                pass

        self.server = Quiet(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d/v1/systemone" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    def answer(self, better_tool, needs_human, model="jev-1.14.0"):
        self.reply = (200, {
            "model": model,
            "answers": {
                "better_tool": {"type": "noul", "noul": better_tool},
                "needs_human": {"type": "noul", "noul": needs_human},
            },
            "usage": {"input_tokens": 120, "output_tokens": 2},
        })


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.server.shutdown()


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return proj


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(jev, "ENFORCE", True)


def ledger(project):
    path = project / ".claude" / "ledger" / "jev-route.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def payload(command="cat README.md", session="s1", tool="Bash", tool_input=None, cwd="/repo"):
    return {"session_id": session, "tool_name": tool, "cwd": cwd,
            "tool_input": tool_input if tool_input is not None else {"command": command}}


def go(stub, p=None, **kw):
    kw.setdefault("key", "k")
    kw.setdefault("endpoint", stub.url)
    return jev.run(p or payload(), now=NOW, **kw)


def sent_text(stub):
    return stub.requests[-1]["body"]["state"]["tool_input"]


def sent_everything(stub):
    """The whole request body, questions and all, as one string."""
    return json.dumps(stub.requests[-1]["body"])


def sent_chars(stub):
    state = stub.requests[-1]["body"]["state"]
    return len(state["tool_name"]) + len(state["tool_input"])


def outline(command, cwd="/nonexistent-cwd", home="/home/nobody"):
    return jev.build_text("Bash", {"command": command}, cwd, home)


def decision(out):
    return out["hookSpecificOutput"]["permissionDecision"]


def run_main(monkeypatch, stdin_text, endpoint, key="k"):
    monkeypatch.setattr(jev, "ENDPOINT", endpoint)
    monkeypatch.setenv("TYPESAFE_API_KEY", key)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    rc = jev.main()
    return rc, out.getvalue()


# ------------------------------------------------- the acceptance tests


def test_curl_u_sends_the_program_and_the_flag_and_not_the_credential(stub):
    go(stub, payload(command="curl -u admin:hunter2 https://x.example"))
    assert sent_text(stub) == "curl -u"
    everything = sent_everything(stub)
    for fragment in ("hunter2", "admin", "x.example"):
        assert fragment not in everything


def test_curl_basic_auth_and_cookie_headers_send_no_header_value(stub):
    for command in ('curl -H "Authorization: Basic YWRtaW46aHVudGVy" https://x.example',
                    'curl -H "Cookie: session=abc123def456" https://x.example'):
        go(stub, payload(command=command))
        assert sent_text(stub) == "curl -H"
        everything = sent_everything(stub)
        for fragment in ("YWRtaW46aHVudGVy", "Basic", "abc123def456", "session", "Cookie", "Authorization"):
            assert fragment not in everything, (command, fragment)


def test_an_mcp_call_with_a_credential_field_sends_the_field_names_only(stub):
    go(stub, payload(tool="mcp__railway__set_variables", tool_input={"credential": "s3cr3tvalue", "token_name": "x"}))
    assert sent_text(stub) == "fields credential token_name"
    assert "s3cr3tvalue" not in sent_everything(stub)
    assert stub.requests[-1]["body"]["state"]["tool_name"] == "mcp__railway__set_variables"


LEAF = "a" * 250 + "key" + " " * 1247


def leaf_payloads():
    """Where the one-leaf input from the held version's finding can sit: a Bash
    command, a file body and an MCP field. Forty of them is the second case."""
    return {
        "mcp leaf": payload(tool="mcp__x__y", tool_input={"leaf": LEAF}),
        "mcp 40 leaves": payload(tool="mcp__x__y", tool_input={"k%d" % i: LEAF for i in range(40)}),
        "mcp list of 40": payload(tool="mcp__x__y", tool_input={"rows": [LEAF] * 40}),
        "bash leaf": payload(command="echo '%s'" % LEAF),
        "bash 40 leaves": payload(command=" ".join("--k%d='%s'" % (i, LEAF) for i in range(40))),
        "write leaf": payload(tool="Write", tool_input={"file_path": "/repo/a.txt", "content": LEAF}),
        "edit 40 leaves": payload(tool="Edit", tool_input={"file_path": "/repo/a.txt", "old_string": LEAF * 20,
                                                          "new_string": LEAF * 20}),
    }


@pytest.mark.parametrize("which", ["mcp leaf", "bash leaf", "write leaf"])
def test_one_pathological_leaf_finishes_under_a_second_and_writes_a_row(stub, project, monkeypatch, which):
    """The real input goes through main(), JSON and all. The row's hash is the
    hash of the full call, which is how this test knows the hook saw it."""
    p = leaf_payloads()[which]
    started = time.monotonic()
    rc, out = run_main(monkeypatch, json.dumps(p), stub.url)
    elapsed = time.monotonic() - started
    assert rc == 0 and out == ""
    assert elapsed < 1.0, elapsed
    row = ledger(project)[-1]
    assert row["outcome"] == "answered"
    assert row["input_sha"] == jev.input_digest(p["tool_name"], p["tool_input"])
    assert "aaaa" not in sent_everything(stub)


@pytest.mark.parametrize("which", ["mcp 40 leaves", "mcp list of 40", "bash 40 leaves", "edit 40 leaves"])
def test_forty_pathological_leaves_finish_under_a_second_and_write_a_row(stub, project, monkeypatch, which):
    p = leaf_payloads()[which]
    assert len(json.dumps(p)) > 40 * 1500
    started = time.monotonic()
    rc, out = run_main(monkeypatch, json.dumps(p), stub.url)
    elapsed = time.monotonic() - started
    assert rc == 0 and out == ""
    assert elapsed < 1.0, elapsed
    row = ledger(project)[-1]
    assert row["outcome"] == "answered"
    assert row["input_sha"] == jev.input_digest(p["tool_name"], p["tool_input"])
    assert "aaaa" not in sent_everything(stub)


MB = MEGABYTE
ONE_MEGABYTE_COMMANDS = {
    "one word": lambda: "a" * MB,
    "many words": lambda: "x " * (MB // 2),
    "flags": lambda: "ls -la " * (MB // 7),
    "lines of commands": lambda: "ls -la\n" * (MB // 7),
    "programs": lambda: "ls;" * (MB // 3),
    "one quoted string": lambda: "echo '" + "q" * MB + "'",
    "unterminated single quote": lambda: "echo '" + "q " * (MB // 2),
    "unterminated double quote": lambda: 'echo "' + "q " * (MB // 2),
    "heredoc body": lambda: "cat <<EOF\n" + "secret line\n" * (MB // 12) + "EOF\nls",
    "unterminated heredoc": lambda: "cat <<EOF\n" + "x\n" * (MB // 2),
    "substitutions": lambda: "$( " * (MB // 3),
    "backslashes": lambda: "\\ " * (MB // 2),
    "dollars": lambda: "$ " * (MB // 2),
    "backticks": lambda: "` " * (MB // 2),
    "double quote specials": lambda: '" ' + "\\$ " * (MB // 3) + '"',
    "assignments": lambda: "A=b " * (MB // 4),
    "redirects": lambda: ">x " * (MB // 3),
    "paths": lambda: "cat " + "./a " * (MB // 4),
    "newlines": lambda: "\n" * MB,
    "mixed": lambda: "a='b' \"c\" $d `e` ;f|g&h <i >j (k) " * (MB // 36),
    # The regions the reader skips without looking in, closed and not closed.
    "test expression": lambda: "[[ " + "a " * (MB // 2) + "]] && ls",
    "unterminated test expression": lambda: "[[ " + "a " * (MB // 2),
    "many test expressions": lambda: "[[ a ]] && " * (MB // 11),
    "array literal": lambda: "A=(" + "a 'b c' " * (MB // 8) + ") ls",
    "unterminated array literal": lambda: "A=(" + "a " * (MB // 2),
    "many array literals": lambda: "A=(a) " * (MB // 6),
    "arithmetic": lambda: "echo $((" + "1 + " * (MB // 4) + "1)) && ls",
    "unterminated arithmetic": lambda: "echo $((" + "(" * (MB // 2),
    "many arithmetic": lambda: "x=$((1<<2)) " * (MB // 12),
    "parameter expansion": lambda: "echo ${X:-" + "a " * (MB // 2) + "} && ls",
    "unterminated parameter expansion": lambda: "echo ${X:-" + "a " * (MB // 2),
    "many parameter expansions": lambda: "echo ${X} " * (MB // 10),
    # What the second round of fixes reads or stops at.
    "ampersand redirects": lambda: "ls &>x " * (MB // 7),
    "ampersand redirects with targets": lambda: "ls &>> x y " * (MB // 11),
    "ampersand then continuation": lambda: "ls &\\\n" * (MB // 6),
    "continuations": lambda: "\\\n" * (MB // 2),
    "continuations after an ampersand": lambda: "ls &" + "\\\n" * (MB // 2),
    "quoted assignments": lambda: '"A=1" ' * (MB // 6),
    "assignment then keyword": lambda: "A=1 if " * (MB // 7),
    "redirect then keyword": lambda: ">x if " * (MB // 6),
    "carriage returns": lambda: "a\r" * (MB // 2),
    "legacy arithmetic": lambda: "echo $[" + "1 + " * (MB // 4) + "]",
    "many legacy arithmetic": lambda: "echo $[1] " * (MB // 10),
    "continuation inside an operator": lambda: "cat <\\\n<EOF\n" + "x\n" * (MB // 2),
    "ansi string": lambda: "echo $'" + "a\\'" * (MB // 3) + "' && ls",
    "unterminated ansi string": lambda: "echo $'" + "a\\'" * (MB // 3),
    "deep substitutions": lambda: "echo " + "$(echo " * (MB // 7),
    "substitutions in double quotes": lambda: 'echo "' + "$(echo a) " * (MB // 10) + '"',
    "backticks in double quotes": lambda: 'echo "' + "`echo a` " * (MB // 9) + '"',
    # What the third round reads: a continuation in the body of a here-document is
    # joined to the line after it, and a joined line can be as long as the body.
    "heredoc lines that continue": lambda: "cat <<EOF\n" + "a\\\n" * (MB // 3) + "EOF\nls",
    "heredoc lines of one backslash": lambda: "cat <<EOF\n" + "\\\n" * (MB // 2) + "EOF\nls",
    "heredoc lines of long backslash runs": lambda: "cat <<EOF\n" + ("\\" * 999 + "\n") * (MB // 1000),
    "heredoc lines that continue, tabbed": lambda: "cat <<-EOF\n" + "\ta\\\n" * (MB // 4) + "\tEOF\nls",
    "many heredocs that continue": lambda: "cat <<EOF\na\\\nEOF\nEOF\n" * (MB // 22),
    "continuations between words": lambda: "ls \\\n" * (MB // 5),
    "continuations inside a word": lambda: "e\\\n" * (MB // 3),
    "continuations before a keyword": lambda: "true && \\\n[[ a ]] " * (MB // 18),
    "continuations before a redirect operand": lambda: "ls > \\\n" * (MB // 7),
    "continuations inside parentheses": lambda: "(\\\n(a)) " * (MB // 8),
    "delimiters with an expansion": lambda: "cat <<$'EOF'\n" * (MB // 13),
    "bare case words": lambda: "echo case " * (MB // 10),
    "bare test words": lambda: "echo [[ " * (MB // 8),
}


@pytest.mark.parametrize("shape", sorted(ONE_MEGABYTE_COMMANDS))
def test_a_one_megabyte_bash_command_finishes_under_2_5_seconds_and_sends_at_most_2000_characters(
        stub, project, monkeypatch, shape):
    command = ONE_MEGABYTE_COMMANDS[shape]()[:MEGABYTE]
    p = payload(command=command)
    started = time.monotonic()
    rc, out = run_main(monkeypatch, json.dumps(p), stub.url)
    elapsed = time.monotonic() - started
    assert rc == 0 and out == ""
    assert elapsed < 2.5, elapsed
    assert sent_chars(stub) <= 2000
    assert len(json.dumps(stub.requests[-1]["body"])) < 8000, "nothing of the command passes through whole"
    row = ledger(project)[-1]
    assert row["outcome"] == "answered"
    assert row["input_sha"] == jev.input_digest("Bash", p["tool_input"]), "the hook saw the whole command"


def test_the_cap_is_2000_characters_cut_at_a_piece_boundary(stub):
    go(stub, payload(command="ls -la\n" * 150000))
    text = sent_text(stub)
    assert jev.MAX_OUT - 12 <= sent_chars(stub) <= jev.MAX_OUT
    assert {line for line in text.split("\n")} == {"ls -la"}, "the last line is whole"
    go(stub, payload(command="ls -la " * 150000))
    assert set(sent_text(stub).split()) <= {"ls", "-la"} and sent_chars(stub) <= jev.MAX_OUT


def run_in_a_process(project, stub_url, stdin_text, key="k"):
    """The harness's path: a new interpreter, the payload on stdin, the exit
    code and stdout read back. Only the endpoint is swapped, in a driver, because
    the hook reads nothing but the key and the project directory from its
    environment."""
    driver = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('jev_route_child', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "m.ENDPOINT = sys.argv[2]\n"
        "sys.exit(m.main())\n"
    )
    env = {"CLAUDE_PROJECT_DIR": str(project), "TYPESAFE_API_KEY": key, "HOME": os.environ["HOME"],
           "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", driver, str(HOOK), stub_url], input=stdin_text,
                          capture_output=True, text=True, env=env, timeout=30)
    return proc, time.monotonic() - started


def test_a_one_megabyte_command_through_a_real_process_stays_inside_the_budget(stub, project):
    p = payload(command=("ls -la " + "x" * 500 + "\n") * (MEGABYTE // 510))
    stdin_text = json.dumps(p)
    assert len(stdin_text) > MEGABYTE * 0.99
    proc, elapsed = run_in_a_process(project, stub.url, stdin_text)
    assert proc.returncode == 0 and proc.stdout == "", proc.stderr
    assert elapsed < 2.5, elapsed
    assert ledger(project)[-1]["outcome"] == "answered"


def test_the_whole_process_stays_inside_the_budget_when_jev_never_answers(stub, project):
    """The request gets what is left of HOOK_BUDGET_S, so a vendor that hangs
    costs the budget and not the 5 second timeout."""
    stub.delay = 8.0
    stdin_text = json.dumps(payload(command="ls -la " * (MEGABYTE // 7)))
    proc, elapsed = run_in_a_process(project, stub.url, stdin_text)
    assert proc.returncode == 0 and proc.stdout == "", proc.stderr
    assert elapsed < jev.HOOK_BUDGET_S, elapsed
    row = ledger(project)[-1]
    assert row["outcome"] == "error" and row["error"] == "TimeoutError"


def test_the_request_gets_what_is_left_of_the_budget(stub, project):
    stub.delay = 8.0
    started = time.monotonic()
    out = jev.run(payload(), key="k", endpoint=stub.url, now=NOW, started=time.monotonic() - 1.5)
    assert out is None
    assert time.monotonic() - started < 1.0, "1.5 s of the budget was already spent"
    assert ledger(project)[-1]["error"] == "TimeoutError"


def test_a_deny_on_one_call_does_not_pass_a_different_call(stub, project, enforce):
    """Two calls that read the same to Jev are still two calls. Dropping the
    input hash match in denied_before makes the second one pass unasked."""
    stub.answer(0.95, 0.0)
    first = payload(command="rm -rf build")
    other = payload(command="rm -rf dist")
    assert outline("rm -rf build") == outline("rm -rf dist"), "the test needs two calls with one outline"
    assert decision(go(stub, first)) == "deny"
    assert decision(go(stub, other)) == "deny"
    assert len(stub.requests) == 2
    assert [r["outcome"] for r in ledger(project)] == ["answered", "answered"]
    assert go(stub, first) is None, "the identical call is the one that passes"
    assert ledger(project)[-1]["outcome"] == "repeat_pass"
    assert len(stub.requests) == 2


def test_a_deny_does_not_pass_the_same_call_in_another_session(stub, enforce):
    stub.answer(0.95, 0.0)
    assert decision(go(stub, payload(session="s1"))) == "deny"
    assert decision(go(stub, payload(session="s2"))) == "deny"
    assert len(stub.requests) == 2


def test_an_ask_is_asked_again_on_the_identical_call(stub, project, enforce):
    """Only a deny is let through the second time. Treating an ask as a deny
    would let a step that changes something outside the repository through
    after one question."""
    stub.answer(0.0, 0.95)
    for _ in range(3):
        assert decision(go(stub)) == "ask"
    assert len(stub.requests) == 3
    assert [r["outcome"] for r in ledger(project)] == ["answered"] * 3


def idle_rows():
    stamp = jev.stamp(NOW)
    return [
        {"ts": stamp, "outcome": "no_key"},
        {"ts": stamp, "outcome": "repeat_pass"},
        {"ts": stamp, "outcome": "breaker_open"},
        {"ts": stamp, "outcome": "bad_input"},
        {"ts": stamp, "outcome": "crash", "error": "RuntimeError"},
        {"ts": stamp, "outcome": "error", "error": "endpoint refused"},
    ]


def test_a_row_that_made_no_request_neither_closes_nor_breaks_the_failure_streak():
    failure = {"ts": jev.stamp(NOW), "outcome": "error", "latency_ms": 5, "error": "TimeoutError"}
    answered = {"ts": jev.stamp(NOW), "outcome": "answered", "latency_ms": 5}
    for idle in idle_rows():
        assert jev.breaker_open([failure, failure, idle, failure], NOW), ("breaks the streak", idle)
        assert jev.breaker_open([failure, idle, failure, idle, failure], NOW), ("breaks the streak", idle)
        assert not jev.breaker_open([failure, failure, idle], NOW), ("counts as a failure", idle)
        assert not jev.breaker_open([failure, idle, failure], NOW), ("counts as a failure", idle)
    assert not jev.breaker_open([failure, failure, answered, failure], NOW), "an answer closes the streak"
    assert jev.breaker_open([failure, failure, failure], NOW)


def test_a_no_key_row_between_failures_does_not_reset_the_streak(project):
    for _ in range(2):
        jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    jev.run(payload(), key="", endpoint=DEAD, now=NOW)
    assert ledger(project)[-1]["outcome"] == "no_key"
    jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    assert [r["outcome"] for r in ledger(project)] == ["error", "error", "no_key", "error", "breaker_open"]


# ------------------------------------------------------ what it decides


def test_the_shipped_mode_is_shadow():
    """Flipping this takes a ruling and a commit."""
    assert SHIPPED_ENFORCE is False


def test_the_shipped_numbers_are_the_ones_claude_md_states():
    assert (jev.CONFIDENCE, jev.HOOK_BUDGET_S, jev.MAX_OUT, jev.MAX_PATH, jev.MAX_SCAN) == (0.8, 2.5, 2000, 200, 65536)
    assert (jev.BREAKER_ERRORS, jev.BREAKER_S) == (3, 600)
    assert jev.MAX_NEST == 8 and len(WRAPPERS) == 14
    section = (ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0]
    flat = " ".join(section.split())
    for stated in ("probability of 0.8", "2.5 seconds", "2,000 characters", "200 characters", "64 KiB",
                   "three failed requests", "ten minutes", "`ENFORCE = False`", "`TYPESAFE_API_KEY`",
                   "any nesting up to 8", "nesting past 8", "fourteen wrapping commands"):
        assert stated in flat, stated


def test_needs_human_at_threshold_asks(stub, enforce):
    stub.answer(0.0, jev.CONFIDENCE)
    assert decision(go(stub)) == "ask"


def test_a_shadow_deny_does_not_grant_a_repeat_pass(stub, project, monkeypatch):
    """A row written in shadow mode must not let the call through once ENFORCE flips."""
    stub.answer(0.95, 0.0)
    assert go(stub) is None and ledger(project)[-1]["decision"] == "deny"
    monkeypatch.setattr(jev, "ENFORCE", True)
    assert decision(go(stub)) == "deny"
    assert len(stub.requests) == 2


def test_better_tool_at_threshold_denies(stub, project, enforce):
    stub.answer(jev.CONFIDENCE, 0.0)
    assert decision(go(stub)) == "deny"
    assert ledger(project)[-1]["decision"] == "deny"


def test_just_below_threshold_prints_nothing(stub, enforce):
    stub.answer(jev.CONFIDENCE - 0.001, jev.CONFIDENCE - 0.001)
    assert go(stub) is None


def test_needs_human_asks_and_wins_over_better_tool(stub, enforce):
    stub.answer(0.99, 0.95)
    assert decision(go(stub)) == "ask"


@pytest.mark.parametrize("better_tool", [0.0, 0.5, 0.8, 1.0])
@pytest.mark.parametrize("needs_human", [0.0, 0.5, 0.8, 1.0])
def test_it_never_prints_allow(stub, enforce, better_tool, needs_human):
    stub.answer(better_tool, needs_human)
    out = go(stub, payload(command="echo %s %s" % (better_tool, needs_human)))
    assert out is None or decision(out) in ("deny", "ask")


def test_shadow_mode_records_and_prints_nothing(stub, project):
    stub.answer(0.95, 0.0)
    assert go(stub) is None
    row = ledger(project)[-1]
    assert row["decision"] == "deny" and row["enforced"] is False


def test_an_identical_call_is_denied_once_and_then_not_sent(stub, project, enforce):
    stub.answer(0.95, 0.0)
    assert go(stub) is not None
    sent = len(stub.requests)
    assert go(stub) is None
    assert len(stub.requests) == sent, "the repeat pass must not call Jev again"
    assert ledger(project)[-1]["outcome"] == "repeat_pass"
    assert go(stub, payload(session="s2")) is not None


def test_a_deny_is_not_printed_when_its_row_cannot_be_written(stub, monkeypatch, enforce):
    stub.answer(0.95, 0.0)
    monkeypatch.setattr(jev, "write_row", lambda row: False)
    for _ in range(3):
        assert go(stub) is None


def test_write_row_is_true_only_when_the_row_is_on_disk(project, monkeypatch):
    assert jev.write_row({"probe": 1}) is True
    assert ledger(project)[-1] == {"probe": 1}
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/dev/null")
    assert jev.write_row({"probe": 2}) is False


def test_an_unwritable_ledger_prints_no_deny_through_the_real_writer(stub, monkeypatch, enforce):
    stub.answer(0.95, 0.0)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/dev/null")
    for _ in range(3):
        assert go(stub) is None


def test_the_repeat_pass_reads_only_the_ledger_tail(stub, project, enforce):
    stub.answer(0.95, 0.0)
    go(stub)
    path = project / ".claude" / "ledger" / "jev-route.jsonl"
    deny = path.read_text()
    path.write_text('{"pad": "%s"}\n' % ("x" * 200) * 40000 + deny)
    started = time.monotonic()
    assert go(stub) is None
    assert ledger(project)[-1]["outcome"] == "repeat_pass"
    assert time.monotonic() - started < 0.5


# ------------------------------------------------------------ fails open


def test_no_key_sends_nothing(stub, project):
    assert go(stub, key="") is None
    assert stub.requests == []
    assert ledger(project)[-1]["outcome"] == "no_key"


@pytest.mark.parametrize("reply", [
    (500, {"error": "boom"}),
    (422, {"detail": []}),
    (403, {"detail": {"error_type": "authentication_error"}}),
    (200, b"not json"),
    (200, {"model": "gpt-x", "answers": {"better_tool": {"type": "noul", "noul": 0.99}, "needs_human": {"type": "noul", "noul": 0.1}}}),
    (200, {"model": "jev-1.14.0", "answers": {"better_tool": {"type": "noul", "noul": 7}, "needs_human": {"type": "noul", "noul": 0.1}}}),
    (200, {"model": "jev-1.14.0", "answers": {"better_tool": {"type": "noul", "noul": True}, "needs_human": {"type": "noul", "noul": 0.1}}}),
    (200, {"model": "jev-1.14.0", "answers": {"better_tool": {"type": "choice", "choice": "x", "confidence": 0.99}, "needs_human": {"type": "noul", "noul": 0.1}}}),
    (200, {"model": "jev-1.14.0", "answers": {"better_tool": {"type": "noul", "noul": 0.99}}}),
])
def test_a_bad_answer_prints_nothing_and_is_recorded(stub, project, enforce, reply):
    stub.reply = reply
    assert go(stub) is None
    assert ledger(project)[-1]["outcome"] == "error"


def test_an_http_error_is_recorded_by_code(stub, project, enforce):
    stub.reply = (503, {"error": "down"})
    assert go(stub) is None
    assert ledger(project)[-1]["error"] == "HTTP 503"


def test_a_slow_answer_is_cut_at_the_deadline(stub, project, enforce):
    stub.answer(0.99, 0.0)
    stub.delay = 2.0
    started = time.monotonic()
    assert go(stub, timeout=0.3) is None
    assert time.monotonic() - started < 1.0
    assert ledger(project)[-1]["outcome"] == "error"


def test_a_trickling_server_is_cut_at_the_deadline(project, enforce):
    """One byte at a time resets a socket timeout forever; the deadline does not."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def trickle():
        conn, _ = listener.accept()
        conn.recv(65536)
        try:
            for ch in b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n" + b"x" * 100:
                conn.send(bytes([ch]))
                time.sleep(0.05)
        except OSError:
            pass
        conn.close()

    threading.Thread(target=trickle, daemon=True).start()
    started = time.monotonic()
    out = jev.run(payload(), key="k", endpoint="http://127.0.0.1:%d/v1/systemone" % port, now=NOW, timeout=0.5)
    assert out is None
    assert time.monotonic() - started < 1.5
    assert ledger(project)[-1]["outcome"] == "error"
    listener.close()


def test_a_dead_host_fails_open(project):
    assert jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5) is None
    assert ledger(project)[-1]["outcome"] == "error"


def test_a_redirect_is_refused_and_the_key_does_not_follow(stub, project, enforce):
    target = Stub()
    try:
        target.answer(0.99, 0.0)
        stub.redirect_to = target.url.replace("/v1/systemone", "/elsewhere")
        assert go(stub) is None
        assert target.requests == [], "the Bearer key followed a redirect"
        assert ledger(project)[-1]["error"] == "HTTP 302"
    finally:
        target.server.shutdown()


@pytest.mark.parametrize("url", [
    "http://api.typesafe.ai/v1/systemone",
    "https://user:pw@api.typesafe.ai/v1/systemone",
    "https://api.typesafe.ai/v1/systemone?x=1",
    "ftp://api.typesafe.ai/",
])
def test_an_unsafe_endpoint_is_refused_before_any_send(url):
    assert jev.run(payload(), key="k", endpoint=url, now=NOW) is None


def test_a_refused_endpoint_is_recorded(project):
    jev.run(payload(), key="k", endpoint="http://api.typesafe.ai/v1/systemone", now=NOW)
    assert ledger(project)[-1]["error"] == "endpoint refused"


def test_three_failed_requests_open_the_breaker_for_ten_minutes(project):
    for _ in range(jev.BREAKER_ERRORS):
        jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    assert [r["outcome"] for r in ledger(project)] == ["error"] * jev.BREAKER_ERRORS
    started = time.monotonic()
    jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "breaker_open"
    assert "latency_ms" not in ledger(project)[-1]
    assert time.monotonic() - started < 0.4
    nine = NOW + timedelta(seconds=jev.BREAKER_S - 1)
    jev.run(payload(), key="k", endpoint=DEAD, now=nine, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "breaker_open"
    later = NOW + timedelta(seconds=jev.BREAKER_S)
    jev.run(payload(), key="k", endpoint=DEAD, now=later, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "error", "the breaker must let one request through after BREAKER_S"


def test_two_failures_do_not_open_the_breaker(project):
    for _ in range(jev.BREAKER_ERRORS - 1):
        jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "error"
    assert len(ledger(project)) == 3


def test_an_answer_closes_the_breaker(stub, project):
    for _ in range(jev.BREAKER_ERRORS - 1):
        jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    go(stub)
    jev.run(payload(), key="k", endpoint=DEAD, now=NOW, timeout=0.5)
    go(stub)
    assert ledger(project)[-1]["outcome"] == "answered"


def test_each_call_leaves_exactly_one_row(stub, project, monkeypatch):
    calls = [
        lambda: go(stub),
        lambda: go(stub, key=""),
        lambda: go(stub, payload(tool="Not A Tool;")),
        lambda: go(stub, endpoint="http://api.typesafe.ai/v1/x"),
        lambda: go(stub, "not a payload"),
        lambda: go(stub, payload(tool="mcp__x__y", tool_input={"a": 1})),
        lambda: go(stub, payload(tool="Write", tool_input=None)),
        lambda: go(stub, key="a\nb"),
    ]
    for n, call in enumerate(calls, 1):
        call()
        assert len(ledger(project)) == n, n


def test_the_shipped_endpoint_and_model():
    assert jev.ENDPOINT == "https://api.typesafe.ai/v1/systemone" and jev.endpoint_ok(jev.ENDPOINT)
    assert jev.MODEL.startswith("jev-")


# --------------------------------------------------- the key stays in the header


def test_the_key_goes_in_one_header_and_nowhere_else(stub, project):
    go(stub, key="tsk_live_abcDEF123456xyz")
    assert stub.requests[-1]["headers"]["Authorization"] == "Bearer tsk_live_abcDEF123456xyz"
    assert "tsk_live" not in sent_everything(stub)
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_a_key_with_a_trailing_newline_is_stripped_and_never_written(stub, project):
    go(stub, key="tsk_live_abcDEF123456xyz\n")
    assert stub.requests[-1]["headers"]["Authorization"] == "Bearer tsk_live_abcDEF123456xyz"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_a_key_a_header_cannot_carry_is_refused_before_any_send(stub, project):
    go(stub, key="tsk_live_abc\nDEF123456xyz")
    assert stub.requests == []
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_an_error_carrying_the_key_is_never_written(project, monkeypatch, capsys):
    def leaky(body, key, endpoint, deadline):
        raise ValueError("Invalid header value b'Bearer %s'" % key)
    monkeypatch.setattr(jev, "ask_within", leaky)
    jev.run(payload(), key="tsk_live_abcDEF123456xyz", endpoint=DEAD, now=NOW)
    row = ledger(project)[-1]
    assert row["outcome"] == "error" and row["error"] == "ValueError"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()
    assert "tsk_live" not in capsys.readouterr().err


def test_a_crash_carrying_the_key_leaves_a_row_with_the_class_name_only(stub, project, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("Bearer tsk_live_abcDEF123456xyz")
    monkeypatch.setattr(jev, "run", boom)
    run_main(monkeypatch, json.dumps(payload()), stub.url, key="tsk_live_abcDEF123456xyz")
    row = ledger(project)[-1]
    assert row["outcome"] == "crash" and row["error"] == "RuntimeError"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()
    assert "tsk_live" not in capsys.readouterr().err


def test_main_reads_only_the_key_and_the_project_dir_from_the_environment():
    source = HOOK.read_text()
    reads = set(re.findall(r"""(?:environ\.get|getenv)\(\s*["']([A-Za-z_]+)["']""", source))
    assert reads == {"CLAUDE_PROJECT_DIR", "TYPESAFE_API_KEY"}
    assert "os.environ[" not in source and "environ.copy" not in source and "dict(os.environ" not in source


# ------------------------------------------- what leaves: the allowed pieces

# Two canaries. Both fit the character class. The first has two digits, which a
# program name may carry, so it is only kept out by reading the command right.
# The second has five, which the digit rule alone would drop, so it also covers
# the rules that do not depend on it.
CANARIES = ("Zq81nTwUvaBcDe", "Zq81nT0wUv44aB")

# Each way a value can sit in a command. A canary fits the character class, so
# if any of these were read as a program, a flag or a path it would leave.
VALUE_PLACES = [
    "curl -u admin:{s} https://x.example",
    "curl --user admin:{s}",
    "curl --user={s}",
    "curl -u {s}",
    "curl -H 'Authorization: Bearer {s}'",
    "curl -H \"Cookie: session={s}\"",
    "curl -H {s}",
    "curl --header {s}",
    "mysql -p{s}",
    "mysql -u root -p{s}",
    "mysql --password={s}",
    "mysql --password {s}",
    "TOKEN={s} ./run.sh",
    "TOKEN={s} PASSWORD=x ./run.sh",
    "export TOKEN={s}",
    "env TOKEN={s} printenv",
    "env -i TOKEN={s} printenv",
    "echo {s}",
    "echo '{s}'",
    "echo \"{s}\"",
    "echo hi {s} there",
    "echo {s} > out.txt",
    "echo {s} >> out.txt",
    "echo {s} 2>&1",
    "cat <<< {s}",
    "cat <<<{s}",
    "cat <<EOF\n{s}\nEOF",
    "cat <<'EOF'\n{s}\nEOF",
    "cat <<\"EOF\"\n{s}\nEOF",
    "cat <<-EOF\n\t{s}\n\tEOF",
    "cat <<EOF | sh\n{s}\nEOF",
    "cat > .env <<'EOF'\nTOKEN={s}\n{s}\nEOF\nls",
    "cat <<EOF\n{s}",
    "echo hi # {s}",
    "echo hi\n# {s}\nls",
    "echo $(echo {s})",
    "echo `echo {s}`",
    "git commit -m {s}",
    "git commit -m '{s}'",
    "git remote add origin https://x:{s}@github.com/a/b",
    "aws configure set aws_secret_access_key {s}",
    "gh auth login --with-token <<< {s}",
    "python3 -c 'print(\"{s}\")'",
    "bash -c \"echo {s}\"",
    "docker login -u user -p {s}",
    "sudo -u {s} ls",
    "sudo -p {s} ls",
    "timeout {s} ls",
    "ssh -i key {s}@host",
    "x={s}; echo $x",
    "printf '%s' {s} | sha256sum",
    "read -s {s}",
    "{s}=1 true",
    "for {s} in a b; do echo; done",
    "case {s} in a) true;; esac",
    "[ -n {s} ]",
    "echo a\\ {s}",
    "echo a\\\n{s}",
    "ls -- {s}",
    "xargs -I {s} ls",
    "find . -name {s}",
    "grep -e {s} file",
    "sed -i s/{s}/x/ file",
    "echo $'{s}'",
    "echo ${{X:-{s}}}",
    "echo \"$(echo {s})\"",
    "(echo {s})",
    "{{ echo {s}; }}",
    "echo {s} &",
    "echo {s} | cat",
    "echo {s} && echo {s} || echo {s}",
    # Syntax the reader once guessed at. Each row below sent the value as a
    # program name, a flag name or a path before the reader stopped guessing.
    # An array literal.
    "KEYS=({s} other)",
    "KEYS=(other {s})",
    "KEYS=(\"a b\" {s})",
    "KEYS=($(echo a) {s})",
    "A+=({s})",
    "A=({s}) echo hi",
    "declare -a KEYS=({s} other)",
    "declare -A M=([a]={s} [b]=c)",
    "PASSWORDS=({s} x) deploy.sh",
    # A subscripted assignment is a variable, not a program with a path in it.
    "A[0]=x/{s}",
    "A[$i]=x/{s}",
    "arr=(a b); arr[1]=http://h/{s}",
    # case, [[ ]] and arithmetic: a pattern, an operand or a name, never a command.
    "case $1 in start|{s}) echo hi;; esac",
    "case x in ({s}) true;; esac",
    "[[ $x =~ ^({s}|b)$ ]] && echo yes",
    "[[ x > {s} ]]",
    "[[ x < {s} ]]",
    "[[ x == @({s}|b) ]]",
    "[[ ( -n x ) && {s} == y ]]",
    "[[ a =~ x\\ ]]|{s} ]] && ls",
    "[[ a =~ \"x ]]\"|{s} ]] && ls",
    "time [[ x > {s} ]]",
    "! [[ x < {s} ]]",
    "time (( {s} > 1 ))",
    # A list that never closes is not known to be a list, so nothing in it is sent.
    "echo \"$(echo a; {s}",
    "echo $(echo a; {s}",
    "echo `echo a; {s}",
    "echo $(echo a; {s} 'unclosed)",
    "echo \"`echo a$(`; {s}",
    "[[ \"a b\" == '{s}' ]]; echo done",
    "echo $(({s} + 1))",
    "echo $(( ({s}) ))",
    "echo $(({s}<<2))",
    "(( {s} = 1 << 3 ))\nls",
    "((i++)); echo {s}",
    "for (({s}=0; {s}<3; {s}++)); do echo; done",
    "x=$(({s}<<2))\ngit push",
    # A separator inside a parameter expansion or an ANSI-C string.
    "echo ${{X:-a b;{s} c}}",
    "echo ${{X:+a|{s}}}",
    "echo ${{X:-({s})}}",
    "echo $'pre\\'; {s} --secret-flag \\'post'",
    "echo $'a\\'b' {s}",
    # Quotes nested inside a substitution inside a double quoted string.
    "git commit -m \"$(cat <<'EOF'\nFix the 5\" pipe handling\n\nRotated the credential for staging\n{s} is the new value\nEOF\n)\"",
    "git commit -m \"$(cat <<'EOF'\nFix a \"bug\nsecond line {s} here\nEOF\n)\"",
    "gh pr create --body \"$(cat <<EOF\nit's \"odd\n{s}\nEOF\n)\"",
    "echo \"$(echo \"\n{s} x x \")\"",
    "echo \"$(echo 'x\"; {s} ')\"",
    "echo \"x $(echo \"a;\n{s}\n\") y\"",
    "curl -d \"$(printf '%s' \"user\n{s}\n\")\" https://x",
    "echo \"`echo \"a;{s}\"`\"",
    "echo \"$(echo \"$(echo \"a; {s}\")\")\"",
    # A quoted string after a wrapper is one word, and its tail is not a program.
    "watch \"curl https://h/api/{s}\"",
    "time \"echo x/{s}\"",
    "sudo \"A B=x/{s}\"",
    "env \"A B={s}/x\" true",
    "xargs \"echo a/{s}\"",
    "command \"x y/{s}\"",
    "exec \"a:b/{s}\"",
    # A word after a substitution or a subshell is an argument, not a new command.
    "echo $(whoami) {s}",
    "echo `whoami` {s}",
    "echo $(whoami){s} x",
    "echo a$(whoami){s}",
    "echo \"$(date)\" {s}",
    "sudo $(which foo) {s}",
    "cat <(echo a) {s}",
    "cat <(echo a){s}",
    "(echo a) {s}",
    "(echo a){s}",
    "{s}$(date) foo",
    # A quoted string that starts with a dash is a value, not a flag.
    "git commit -m '--{s}'",
    "echo \"--{s}\"",
    "ls '--{s}'=auto",
    # A word after the target of &> or &>> is an argument. The & was read as a
    # separator before the > was seen, so the word became a program.
    "echo a &>/dev/null {s}",
    "echo a &>>log.txt {s}",
    "echo a &> out.log {s} correcthorsebatterystaple",
    "ls &>out.log {s}",
    "{{ echo a; }} && echo b &>/dev/null {s}",
    # An assignment or a reserved word is one only when it is typed bare. Quoted or
    # escaped it is a command name, and the next word is its argument.
    "\"FOO=bar\" {s}",
    "\\FOO=bar {s}",
    "FOO\"=\"bar {s}",
    "F\\OO=bar {s}",
    "\"if\" {s}",
    "\"then\" {s}",
    "\"{{\" {s}",
    "\"!\" {s}",
    "\"fi\" {s}",
    "\\done {s}",
    "false || \\ex=cho {s}",
    "(ex=cho a\\= {s})",
    "time \"A=1\" {s}",
    # Nothing read ahead of a command makes the reserved word after it one: after
    # an assignment or a redirect, if and then are command names.
    "FOO=bar if {s}",
    "x= if {s} echo",
    "A=1 then {s}",
    "A=1 do {s}",
    "A=1 while {s}",
    "A=1 ! {s}",
    "A=1 {{ {s}",
    "> out.txt if {s}",
    "2>/dev/null then {s}",
    "<in.txt do {s}",
    "2>&1 if {s}",
    "> out.txt {{ {s}",
    "A=1 ({s})",
    "> out.txt ({s})",
    # Bash keeps a carriage return inside the word, so this is one assignment.
    "FOO=bar\r{s}",
    "A=1\rB=2\r{s}",
    "\r{s}",
    "ls && \r{s}",
    "sudo \r{s}",
    # Bash joins a line continuation before it reads an operator, so the two
    # halves of one operator are not two operators.
    "cat <\\\n<EOF\n{s}\nEOF",
    "cat <\\\n<EOF\n{s}\nEOF\nls",
    "cat <<\\\n<{s}",
    "echo a >\\\n&{s} x",
    "echo a &\\\n>/dev/null {s}",
    "echo $\\\n{{X:-a;{s} }}",
    # The legacy $[ ] arithmetic is not a command list and holds a ; or a newline.
    "echo $[ 1 ; {s} ]",
    "echo $[ 1\n{s} ]",
    "echo \"$[ 1 \"; {s} ]\"",
    "x=$[ 1 ; {s} ]",
    # A quoted string that never closes is not known to be a word, whether the
    # command is malformed or a 64 KiB cut opened the quote.
    "'{s}",
    "\"{s}",
    "sudo '{s}",
    "echo hi; '{s}",
    "time \"{s}",
    "echo hi; ls | \\{s}\\",
    "echo hi; \"{s}\\\n",
    # A bare delimiter means an expanded body, and bash removes a backslash-newline
    # from it before it compares a line with the delimiter: foo\ then EOF is the one
    # line fooEOF and the body goes on, so the lines after it are text. A line that
    # ends in an odd number of backslashes joins, an even number does not.
    "cat <<EOF\nline one\\\nEOF\n{s} --token abc\nEOF\nls",
    "cat <<EOF\nline one\\\nEOF\n{s}\nEOF",
    "cat <<EOF\nfoo\\\\\\\nEOF\n{s} two\nEOF",
    "cat <<EOF\nfoo\\\n\\\nEOF\n{s} two\nEOF",
    "cat <<-EOF\n\tfoo\\\n\tEOF\n{s} two\n\tEOF",
    # A delimiter is literal text. Bash expands nothing in it and runs nothing in
    # it, so a $ in it is not a resolved word, and $(cmd) in it is not a command.
    "cat <<$'EOF'\n$\n{s} --token abc\nEOF",
    "cat <<$\"EOF\"\n$\n{s} --token abc\nEOF",
    "cat <<${{X}}\n$\n{s} --token abc\n${{X}}",
    "cat <<$X\n$\n{s} --token abc\n$X",
    "cat <<$(echo)\n$\n{s} --token abc\n$(echo)\nend",
    "cat <<$({s})\n$\nx\n$({s})\nend",
    "cat <<`{s}`\n$\nx\n`{s}`\nend",
    # Whether [[ and case are read does not depend on where the reader thinks a
    # command starts. A line continuation, time -p, a function body and a coprocess
    # each hid the keyword, and then < > && || and a case pattern were commands.
    "true && \\\n[[ x < {s} ]]",
    "true && \\\n[[ x > {s} ]]",
    "true && \\\n[[ -n x && {s} == y ]]",
    "true && \\\n[[ -z x || {s} == y ]]",
    "true && \\\ncase x in a|{s}) true;; esac",
    "prog1 && [\\\n[ x < {s} ]]",
    "function f {{ [[ x < {s} ]]; }}",
    "function f {{ [[ -n x && {s} == y ]]; }}",
    "function f {{ case x in a|{s}) true;; esac; }}",
    "time -p [[ x < {s} ]]",
    "time -p case x in a|{s}) true;; esac",
    "coproc c {{ [[ x < {s} ]]; }}",
    "coproc {{ case x in a|{s}) true;; esac; }}",
    "coproc [[ x < {s} ]]",
    # Bash joins the two halves of (( and $(( across a line continuation.
    "(\\\n(x < {s}))",
    "echo $(\\\n(3 < {s}))",
    # A line continuation is not a word, so the here-string operand after one is
    # still the operand.
    "<<< \\\n  {s}",
    "cat <<< \\\n  {s}",
]


@pytest.mark.parametrize("canary", CANARIES)
@pytest.mark.parametrize("command", VALUE_PLACES)
def test_no_value_leaves_wherever_it_sits_in_a_command(stub, command, canary):
    command = command.format(s=canary)
    assert canary in command
    text = outline(command)
    assert canary not in text, text
    go(stub, payload(command=command))
    assert canary not in sent_everything(stub)
    assert canary[:6] not in sent_text(stub)


Q, S, BT, BS, NL = '"', "'", "`", "\\", "\n"

# Each wraps a command, as written inside another command's quotes or
# substitution, so every row above is also read at a nesting the rows do not
# spell out. Nothing here runs the command: the reader reads text.
WRAPPERS = {
    "dq_sub": lambda c: "echo " + Q + "$(" + c + ")" + Q,
    "assign_dq_sub": lambda c: "X=" + Q + "$(" + c + ")" + Q,
    "dq_backtick": lambda c: "echo " + Q + BT + c + BT + Q,
    "sh_c_sq": lambda c: "sh -c " + S + c.replace(S, "") + S,
    "eval_dq": lambda c: "eval " + Q + c.replace(Q, BS + Q) + Q,
    "plain_sub": lambda c: "echo $(" + c + ")",
    "if_then": lambda c: "if true; then " + c + "; fi",
    "ssh_dq": lambda c: "ssh host " + Q + c.replace(Q, BS + Q) + Q,
    "time_dq": lambda c: "time " + Q + c.replace(Q, BS + Q) + Q,
    "xargs_dq": lambda c: "xargs " + Q + c.replace(Q, BS + Q) + Q,
    "watch_dq": lambda c: "watch " + Q + c.replace(Q, BS + Q) + Q,
    "group": lambda c: "{ " + c + "; }",
    "subshell": lambda c: "( " + c + " )",
    "for_do": lambda c: "for i in 1 2; do " + c + "; done",
}


def fits_wrapper(wrapper, template):
    """Escaping the quotes of a command that holds a substitution, or putting a
    command that holds backticks inside backticks, makes it a different command
    in which the canary can be a program. Those pairs are not value places."""
    if wrapper in ("eval_dq", "ssh_dq", "time_dq", "xargs_dq", "watch_dq"):
        return "$(" not in template and BT not in template
    if wrapper == "dq_backtick":
        return BT not in template
    return True


@pytest.mark.parametrize("wrapper", sorted(WRAPPERS))
def test_no_value_leaves_when_a_command_sits_inside_another_command(wrapper):
    leaks = []
    for template in VALUE_PLACES:
        if not fits_wrapper(wrapper, template):
            continue
        for canary in CANARIES:
            command = WRAPPERS[wrapper](template.format(s=canary))
            text = outline(command)
            if canary in text or canary[:6] in text:
                leaks.append((command, text))
    assert leaks == [], leaks[:3]


def quoted_canary_command(rng, canary):
    """A command with the canary only inside quoted text, which nests up to three
    deep through $( ) and backticks, and with the separators, odd quote counts
    and newlines that desynchronise a reader that tracks quotes badly. The canary
    is quoted text in bash whatever the nesting: none of it is a command."""
    seps = [" ", "; ", NL, " | ", " && ", " ", " ", " -", " --", " > "]

    def text(with_canary):
        parts = []
        for _ in range(rng.randint(1, 4)):
            parts.append(rng.choice(["foo", "bar baz", "x", "a-b", "k=v", "tok"]))
            parts.append(rng.choice(seps))
        s = "".join(parts)
        if with_canary:
            i = rng.randint(0, len(s))
            s = s[:i] + rng.choice(seps) + canary + rng.choice(seps) + s[i:]
        return s

    def single(with_canary):
        return S + text(with_canary).replace(S, "") + S

    def double(depth, with_canary):
        body, n = [], rng.randint(1, 3)
        at = rng.randrange(n) if with_canary else -1
        for k in range(n):
            kind = rng.choice(["t", "t", "sub", "bt"]) if depth < 3 else "t"
            if kind == "t":
                body.append(text(k == at).replace(Q, "").replace("$", "").replace(BT, "").replace(BS, ""))
            elif kind == "sub":
                body.append("$(" + command(depth + 1, k == at) + ")")
            else:
                body.append(BT + command(depth + 1, k == at) + BT)
        return Q + "".join(body) + Q

    def command(depth, with_canary):
        words, n = ["echo"], rng.randint(1, 3)
        at = rng.randrange(n) if with_canary else -1
        for k in range(n):
            kind = rng.choice(["sq", "dq", "dq", "bare"])
            if kind == "sq":
                words.append(single(k == at))
            elif kind == "dq":
                words.append(double(depth, k == at))
            else:
                words.append(single(True) if k == at else "w%d" % k)
        return " ".join(words)

    return command(0, True)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_value_inside_quoted_text_never_leaves_at_any_nesting(seed):
    """The differential fuzz the reader failed at 22165922: 876 leaks in 20,000
    commands at seed 1, found by putting the canary only in quoted text."""
    rng = random.Random(seed)
    leaks, made = [], 0
    for _ in range(4000):
        command = quoted_canary_command(rng, CANARIES[0])
        if CANARIES[0] not in command:
            continue
        made += 1
        text = outline(command)
        if CANARIES[0] in text:
            leaks.append((len(command), command, text))
    assert made > 3500
    leaks.sort()
    assert leaks == [], leaks[:3]


@pytest.mark.parametrize("command,expected", [
    ("curl -u admin:hunter2 https://x.example", "curl -u"),
    ("curl --user admin:hunter2 --cookie a=b https://x", "curl --user --cookie"),
    ("curl --user=admin:hunter2 https://x", "curl --user"),
    ("git push --force-with-lease origin main", "git --force-with-lease"),
    ("git push -f", "git -f"),
    ("rm -rf build", "rm -rf"),
    ("ls -la | grep -rn foo", "ls -la\ngrep -rn"),
    ("sudo rm -rf x", "sudo rm -rf"),
    ("sudo -u admin rm -rf x", "sudo -u -rf"),
    ("env FOO=bar python3 -m pytest -q", "env python3 -m -q"),
    ("FOO=bar ./run.sh --verbose", "run.sh --verbose"),
    ("/usr/bin/env python3.11 script.py", "env python3.11"),
    ("cat <<'EOF' > notes.md\nhello hunter2\nEOF\nls", "cat notes.md\nls"),
    ("cat > .env <<EOF\nTOKEN=x\nEOF", "cat .env"),
    ("echo hi > out.txt 2>&1", "echo out.txt"),
    ("sort < in.txt > out.txt", "sort in.txt out.txt"),
    ("mysql -u root -phunter2", "mysql -u"),
    ("tar -xzf x.tgz", "tar -xzf"),
    ("tar -czvf x.tgz y", "tar"),
    ("find . -name '*.py' -delete", "find -name -delete"),
    ("echo $(whoami)", "echo\nwhoami"),
    ("echo `whoami`", "echo\nwhoami"),
    ("if true; then echo hi; fi", "true\necho"),
    ("for f in a b; do rm -f $f; done", "rm -f"),
    ("while read l; do echo $l; done", "read\necho"),
    ("a && b || c; d | e & f", "a\nb\nc\nd\ne\nf"),
    ("echo hi # a comment", "echo"),
    ("python3 -c 'import os'", "python3 -c"),
    ("ls --color=auto -la", "ls --color -la"),
    ("ls -- -la", "ls"),
    ("g++ -O2 x.cc", ""),
    ("x86_64-linux-gnu-gcc --version", "x86_64-linux-gnu-gcc --version"),
    ("", ""),
    ("   \n\n  ", ""),
    # What the reader reads past without looking in, and the commands around it.
    ("[[ -f x ]] && rm -rf build", "rm -rf"),
    ("if [[ -z \"$X\" ]]; then rm -rf build; fi", "rm -rf"),
    ("x=$((1<<4))\ngit push --force origin main\nrm -rf build", "git --force\nrm -rf"),
    ("dd if=/dev/zero of=x bs=$((1<<20)) count=1\nrm x", "dd\nrm"),
    ("echo $((1<<4))\nls -la", "echo\nls -la"),
    ("(( n = 1 << 3 ))\nls", "ls"),
    ("for ((i=0;i<3;i++)); do echo $i; done", "echo"),
    ("ls $(( $(date +%s) - 5 )) && git push --force", "ls\ngit --force"),
    ("PASSWORDS=(hunter2 s3cr3tvalue) deploy.sh", "deploy.sh"),
    ("declare -a KEYS=(a b)", "declare -a"),
    ("echo $'it\\'s ok; hunter2' && ls", "echo\nls"),
    ("echo ${X:-a b;c} && ls", "echo\nls"),
    # A substitution inside double quotes is a command list with its own quotes.
    ("git commit -m \"$(cat <<'EOF'\nFix the 5\" pipe\nbody\nEOF\n)\" && git push", "git -m\ncat\ngit"),
    ("echo \"$(echo \"a;\nb\")\" && ls", "echo\necho\nls"),
    # A word after a substitution belongs to the command around it.
    ("echo $(whoami) -n", "echo\nwhoami\n-n"),
    ("cat <(sort a) b", "cat\nsort"),
    # A flag is typed bare. Quoting its value does not hide its name.
    ("git commit --message=\"fix\" --author='a b'", "git --message --author"),
    ("git commit -m '--wip-token'", "git -m"),
    ("ls --co\"lor\"=auto", "ls"),
    # &> and &>> are one redirect: the target is a path and the next word an argument.
    ("echo hi &>/dev/null; ls", "echo /dev/null\nls"),
    ("ls &>> log.txt && rm -rf build", "ls log.txt\nrm -rf"),
    ("make 2>&1 &>build.log | tee x", "make build.log\ntee"),
    ("cmd &>f &", "cmd f"),
    ("sleep 1 & ls", "sleep\nls"),
    ("sleep 1 &\nls", "sleep\nls"),
    # An assignment is one when its name and = are typed bare, whatever its value.
    ("FOO=\"bar baz\" ls -la", "ls -la"),
    ("FOO='a b' BAR=2 ls", "ls"),
    ("FOO=$(echo a) ls", "echo\nls"),
    ("FOO=bar BAZ=qux ./run.sh --verbose", "run.sh --verbose"),
    ("A+=x ls", "ls"),
    ("A[0]=x ls", "ls"),
    ("\"A=1\" ls", ""),
    ("\\A=1 ls", ""),
    ("A\"=\"1 ls", ""),
    ("time \"A=1\" ls", "time"),
    # A reserved word is one only when typed bare and first on its command. After
    # an assignment or a redirect, or quoted or escaped, it is a program.
    ("FOO=bar if x", "if"),
    ("> out.txt if x", "out.txt if"),
    ("2>&1 if x", "if"),
    ("\"if\" x", "if"),
    ("\\if x", "if"),
    ("FOO=bar ! ls", ""),
    ("! FOO=bar ls", "ls"),
    ("> out.txt ls -la", "out.txt ls -la"),
    ("if FOO=bar x; then ls; fi", "x\nls"),
    # A carriage return is part of the word, as bash has it.
    ("FOO=bar\rls", ""),
    ("ls\r\npwd", "pwd"),
    # Bash removes a line continuation before it reads a token. It is not a word,
    # it quotes nothing, and what is on both sides of it is joined.
    ("cd build && \\\n  git push --force origin main", "cd\ngit --force"),
    ("FOO=1 \\\n  BAR=2 \\\n  git push --force origin main", "git --force"),
    ("cat a.log |\\\n  grep -rn foo", "cat\ngrep -rn"),
    ("prog1 ;\\\n prog2 --force", "prog1\nprog2 --force"),
    ("git push \\\n  --force", "git --force"),
    ("ec\\\nho hi", "echo"),
    ("FOO=\\\nbar ls -la", "ls -la"),
    ("i\\\nf true; then ls; fi", "true\nls"),
    ("[\\\n[ -f x ]] && rm -rf build", "rm -rf"),
    ("true && \\\n[[ -f x ]] && rm -rf build", "true\nrm -rf"),
    # A here-document body ends at the line that is the delimiter once bash has
    # joined a line that ends in an odd number of backslashes to the one after it.
    # A quoted delimiter joins nothing, and neither does an even number.
    ("cat <<EOF\nfoo\\\nEOF\nhunter2pw --token abc\nEOF\nls", "cat\nls"),
    ("cat <<EOF\nE\\\nOF\nls", "cat\nls"),
    ("cat <<EOF\n\\\nEOF\nls", "cat\nls"),
    ("cat <<EOF\nfoo\\\\\nEOF\nls", "cat\nls"),
    ("cat <<EOF\nfoo\\\\\\\nEOF\nls\nEOF\npwd", "cat\npwd"),
    ("cat <<-EOF\n\tfoo\\\n\tEOF\nls\n\tEOF\npwd", "cat\npwd"),
    ("cat <<-EOF\n\\\n\tEOF\nls", "cat\nls"),
    ("cat <<'EOF'\nfoo\\\nEOF\nls -la\nEOF", "cat\nls -la\nEOF"),
    ("cat <<E\"O\"F\nfoo\\\nEOF\nls", "cat\nls"),
    ("cat <<E\\\nOF\nx\nEOF\nls", "cat\nls"),
    # A delimiter is literal text, quoted or not, and a quoted $ in it is only a $.
    ("cat <<\"$X\"\n$X\nls", "cat\nls"),
    ("cat <<'$'\n$\nls", "cat\nls"),
])
def test_the_outline_of_a_command_is_programs_flags_and_paths(command, expected):
    assert outline(command) == expected


CONTINUATION_CORPUS = [
    "cd build && git push --force origin main",
    "FOO=1 BAR=2 git push --force origin main",
    "cat a.log | grep -rn foo",
    "prog1 ; prog2 --force",
    "curl -u admin:hunter2 https://x.example",
    "sudo -u admin rm -rf x",
    "env FOO=bar python3 -m pytest -q",
    "if true; then echo hi; fi",
    "for f in a b; do rm -f $f; done",
    "echo $(whoami) -n",
    "ls -la || rm -rf build",
    "time -p ls",
    "! FOO=bar ls",
    "x=$(date) ls -la",
    "git commit -m 'ab' --author=x",
    "sort < in.txt > out.txt",
    "echo a &>/dev/null; ls",
    "(echo a; ls -la)",
    "{ echo a; ls -la; }",
]


@pytest.mark.parametrize("command", CONTINUATION_CORPUS)
def test_a_line_continuation_next_to_a_space_changes_nothing_in_the_outline(command):
    """Bash removes the continuation before it reads a token, so a command that
    has one next to any of its spaces is the same command. The one place that is
    stopped at on purpose is right after < > or &, which may be half an operator."""
    expected = outline(command)
    assert expected
    seen = 0
    for at, ch in enumerate(command):
        if ch != " ":
            continue
        for glue in ("\\\n", "\\\n  "):
            variants = [command[:at + 1] + glue + command[at + 1:]]
            if command[at - 1] not in "<>&":
                variants.append(command[:at] + glue + command[at:])
            for variant in variants:
                seen += 1
                assert outline(variant) == expected, variant
    assert seen >= 4


@pytest.mark.parametrize("command,expected", [
    ("ls -la; case $x in a) rm -rf b;; esac; git push --force", "ls -la"),
    ("ls; foo() { rm -rf b; }; git push --force", "ls\nfoo"),
    ("ls; echo a(b); git push --force", "ls\necho"),
    ("ls; echo @(a|b); git push --force", "ls\necho"),
    ("ls; echo ${X:-'a'}; git push --force", "ls\necho"),
    ("ls; echo ${X:-$(date)}; git push --force", "ls\necho"),
    ("ls; echo $(( 'a' )); git push --force", "ls\necho"),
    ("ls; echo $((1+2); git push --force", "ls\necho"),
    ("ls; echo $'abc; git push --force", "ls\necho"),
    ("ls; echo ${X:-a; git push --force", "ls\necho"),
    ("ls; A=(a (b)); git push --force", "ls"),
    ("ls; echo a); git push --force", "ls\necho"),
    ("ls; [[ a == b; git push --force", "ls"),
    # A list inside $( ) or backticks that does not close sends nothing from inside.
    ("ls; echo $(echo a; git push --force", "ls\necho"),
    ("ls; echo \"$(echo a; git push --force", "ls\necho"),
    ("ls; echo `echo a; git push --force", "ls\necho"),
    ("ls; echo $(echo a 'b; git push --force)", "ls\necho"),
    ("ls; echo $(echo $(echo a; git push --force)", "ls\necho"),
    # The legacy $[ ] arithmetic, in a word and inside double quotes.
    ("ls; echo $[ 1 ; x ]; git push --force", "ls\necho"),
    ("ls; echo \"$[ 1 \"; x ]\"; git push --force", "ls\necho"),
    # A line continuation inside an operator joins its two halves in bash, so what
    # follows may be a different operator than the characters show.
    ("ls; cat <\\\n<EOF\nx\nEOF\ngit push --force", "ls\ncat"),
    ("ls; echo $\\\n{X:-a;b}; git push --force", "ls\necho"),
    ("ls; echo a &\\\n>f; git push --force", "ls\necho"),
    ("ls; echo a >\\\n&2; git push --force", "ls\necho"),
    # A here-document delimiter that holds an expansion cannot be read as the text
    # bash takes it for, and the substitution in it is not run.
    ("ls; cat <<$'EOF'\n$\nx\nEOF\ngit push --force", "ls\ncat"),
    ("ls; cat <<$\"EOF\"\n$\nx\nEOF\ngit push --force", "ls\ncat"),
    ("ls; cat <<${X}\n$\nx\n${X}\ngit push --force", "ls\ncat"),
    ("ls; cat <<$X\n$X\ngit push --force", "ls\ncat"),
    ("ls; cat <<$(echo)\n$\nx\n$(echo)\ngit push --force", "ls\ncat"),
    ("ls; cat <<`echo`\n$\nx\n`echo`\ngit push --force", "ls\ncat"),
    # A function definition and a coprocess hold a command list the reader does not
    # open. function and coproc are reserved at the start of a command only.
    ("ls; function f { rm -rf b; }; git push --force", "ls"),
    ("ls; coproc c { rm -rf b; }; git push --force", "ls"),
    ("ls; echo function coproc; git push --force", "ls\necho\ngit --force"),
    # [[ and case end the read or skip to ]] wherever they are typed bare. When bash
    # reads one as an ordinary argument the cost is the commands after it.
    ("ls; echo case; git push --force", "ls\necho"),
    ("ls; grep [[ file; git push --force", "ls\ngrep"),
    ("ls; echo \"case\" '[[' \\case; git push --force", "ls\necho\ngit --force"),
    # A subshell cannot follow an assignment or a redirect.
    ("ls; FOO=bar (git push --force)", "ls"),
    ("ls; > f (git push --force)", "ls\nf"),
    # A quote or an escape the text ends inside is a word that was cut, not a word.
    ("ls; 'abc", "ls"),
    ("ls; \"abc", "ls"),
    ("ls; \\abc\\", "ls"),
    ("ls; \"abc\\\n", "ls"),
    ("ls; echo abc\\", "ls\necho"),
    ("ls; echo 'abc; git push --force", "ls\necho"),
    ("ls; echo \"abc; git push --force", "ls\necho"),
])
def test_syntax_the_reader_does_not_model_ends_the_read_and_nothing_after_it_is_guessed_at(command, expected):
    assert outline(command) == expected


def test_a_word_cut_inside_a_quote_or_an_escape_is_never_judged():
    """A command over 64 KiB is cut at the last separator in its first 64 KiB, and
    that can fall inside a quoted string or after an escaped space. What is left
    is a piece of a word, and a piece of a word is not a program."""
    canary = CANARIES[0]
    filler = "b" * (jev.MAX_SCAN + 10)
    cuts = {
        "single quote": "'" + canary + " " + filler + "'",
        "double quote": '"' + canary + " " + filler + '"',
        "escaped space": canary + "\\ " + filler,
        "escaped first character": "\\" + canary + "\\ " + filler,
        "double quote in a substitution": '"$(echo ' + canary + " " + filler + ')"',
    }
    for name, word in cuts.items():
        for head in ("", "ls && ", "echo hi; ", "sudo ", "env FOO=1 ", "time ", "ls | "):
            command = head + word
            assert len(command) > jev.MAX_SCAN
            text = outline(command)
            assert canary not in text, (name, head, text)
    assert outline("ls && " + cuts["single quote"]) == "ls"
    assert outline("sudo " + cuts["double quote"]) == "sudo"


def test_an_assignment_needs_its_name_and_its_equals_sign_typed_bare():
    for word, quoted_at in (("A=1", None), ("A=b c", 2), ("A+=1", None), ("A[0]=x", None), ("A=", 2)):
        assert jev.assignment(word, quoted_at), (word, quoted_at)
    for word, quoted_at in (("A=1", 0), ("A=1", 1), ("A+=1", 2), ("a b", None), ("A", None), ("=1", None)):
        assert not jev.assignment(word, quoted_at), (word, quoted_at)


def test_a_backslash_inside_backticks_ends_the_read():
    assert "git" not in outline("echo `echo \\`x\\``; git push --force")
    assert "git" not in outline("echo `echo \"a\\\"b\"`; git push --force")


def test_substitutions_nested_past_the_cap_end_the_read_and_never_crash():
    deep = "echo " + "$(echo " * 40 + ")" * 40 + "; git push --force"
    lines = outline(deep).split("\n")
    assert len(lines) <= jev.MAX_NEST + 2 and "git" not in lines
    assert outline("echo " + "$(echo " * (jev.MAX_NEST - 1) + ")" * (jev.MAX_NEST - 1) + "; ls").endswith("ls")


def test_a_program_name_comes_from_a_whole_word_that_is_a_plain_piece():
    assert jev.program_name("git") == "git"
    assert jev.program_name("/usr/bin/env") == "env"
    assert jev.program_name("./run.sh") == "run.sh"
    for word in ("curl https://h/api/Zq81nTwUvaBcDe", "A B=x/Zq81nTwUvaBcDe", "A[0]=x/Zq81nTwUvaBcDe",
                 "x:y/Zq81nTwUvaBcDe", "a=b/c", "a/b c", "$/x", "", "/", "a/" + "b" * 41):
        assert jev.program_name(word) is None, word


def test_an_assignment_may_carry_a_subscript_and_is_still_an_assignment():
    for word in ("A=1", "A+=1", "A=", "A[0]=x", "A[i]+=x", "arr[1]=http://h/x", "A[$i]=x/y", "_a1=b"):
        assert jev.is_assignment(word), word
    for word in ("A", "A[0]", "A[0", "[0]=x", "A[0]x=1", "a-b=c", "=x", "1a=b", "A.b=c"):
        assert not jev.is_assignment(word), word


def test_a_long_run_of_digits_is_not_a_program_or_a_flag_name():
    assert outline("0123456789abcdef0123456789abcdef --0123456789abcdef -x") == "-x"
    assert outline("ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5 --flag") == "--flag"
    assert outline("cmd --sha256 --x509") == "cmd --sha256 --x509"


def test_a_flag_value_attached_to_a_short_flag_is_dropped_beyond_two_letters():
    assert outline("mysql -phunter2") == "mysql"
    assert outline("mysql -pS3cret") == "mysql"
    assert outline("mysql -uadmin") == "mysql"
    assert outline("curl -fsSL x") == "curl"
    assert outline("curl -sS x") == "curl -sS"


def test_a_bare_word_is_a_path_only_when_it_exists(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.py").write_text("x")
    cwd = str(tmp_path)
    assert outline("cat notes.txt missing.txt", cwd=cwd) == "cat notes.txt"
    assert outline("cat sub/a.py ./sub/a.py sub/b.py", cwd=cwd) == "cat sub/a.py ./sub/a.py"
    assert outline("cat %s" % (tmp_path / "notes.txt"), cwd="/nonexistent") == "cat %s" % (tmp_path / "notes.txt")
    assert outline("cat 'notes.txt'", cwd=cwd) == "cat notes.txt"
    assert outline("cat 'no tes.txt'", cwd=cwd) == "cat"


def test_a_secret_that_fits_the_path_class_is_not_sent_as_a_path():
    for secret in ("wJalrXUtnFEMI/K7MDENG/bPxRfiCYzz9Q7Z8XQK", "ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5",
                   "/Zq81nT0wUv44aB/xyz", "~/Zq81nT0wUv44aB", "./Zq81nT0wUv44aB", "0123456789abcdef0123456789abcdef"):
        assert outline("echo %s" % secret) == "echo", secret
        assert outline("aws configure set k %s" % secret) == "aws", secret


def test_only_a_few_bare_words_are_looked_up_on_disk(tmp_path, monkeypatch):
    looked = []
    real = os.path.lexists
    monkeypatch.setattr(os.path, "lexists", lambda p: looked.append(p) or real(p))
    outline("cat " + "w%d " % 0 * 5000, cwd=str(tmp_path))
    assert len(looked) == jev.MAX_STATS


def test_a_path_under_home_is_written_with_a_tilde(home):
    (home / "notes.txt").write_text("x")
    h = str(home)
    assert outline("cat %s/notes.txt" % h, home=h, cwd="/nonexistent") == "cat ~/notes.txt"
    assert outline("cat ~/notes.txt", home=h, cwd="/nonexistent") == "cat ~/notes.txt"
    assert outline("cat ~/missing.txt", home=h, cwd="/nonexistent") == "cat"
    assert outline("echo > %s/new.txt" % h, home=h) == "echo ~/new.txt"
    assert outline("cat %sother/x" % h, home=h) == "cat"
    assert outline("cat ~/x", home="") == "cat"


def test_the_home_directory_never_leaves_in_a_path(stub, home):
    h = str(home)
    go(stub, payload(tool="Write", tool_input={"file_path": h + "/notes/plan.md", "content": "x"}))
    assert sent_text(stub) == "path ~/notes/plan.md\nfields file_path content"
    assert h not in sent_everything(stub)
    go(stub, payload(command="echo hi > %s/out.txt" % h))
    assert sent_text(stub) == "echo ~/out.txt"
    assert h not in sent_everything(stub)
    go(stub, payload(tool="NotebookEdit", tool_input={"notebook_path": h, "new_source": "x"}))
    assert sent_text(stub).startswith("path ~\n")


def test_a_home_of_slash_replaces_nothing(stub, monkeypatch):
    monkeypatch.setenv("HOME", "/")
    go(stub, payload(tool="Write", tool_input={"file_path": "/etc/x.conf", "content": "x"}))
    assert sent_text(stub).startswith("path /etc/x.conf\n")


def test_a_redirect_target_over_200_characters_is_dropped():
    long = "/" + "a" * 199
    assert outline("echo > %s" % long) == "echo %s" % long
    assert outline("echo > %s" % (long + "a")) == "echo"


@pytest.mark.parametrize("tool,field", [("Write", "file_path"), ("Edit", "file_path"), ("NotebookEdit", "notebook_path")])
def test_a_file_path_over_200_characters_is_dropped(stub, tool, field):
    ok = "/" + "a" * 199
    go(stub, payload(tool=tool, tool_input={field: ok, "content": "x"}))
    assert sent_text(stub).startswith("path " + ok + "\n")
    go(stub, payload(tool=tool, tool_input={field: ok + "a", "content": "x"}))
    assert sent_text(stub) == "fields %s content" % field
    assert "aaaa" not in sent_everything(stub)


@pytest.mark.parametrize("bad", ["/repo/my file.txt", "/repo/a;b", "/repo/é.txt", "/repo/a b/../c", "$HOME/x",
                                 "/repo/a\nb", "/repo/$(x)", "", None, 7, ["/repo/x"], "/repo/a=b"])
def test_a_file_path_outside_the_character_class_is_dropped_not_escaped(stub, bad):
    go(stub, payload(tool="Write", tool_input={"file_path": bad, "content": "x"}))
    text = sent_text(stub)
    assert not text.startswith("path"), text
    assert text == "fields file_path content"
    assert "/repo/" not in sent_everything(stub)


FILE_BODY_SECRETS = {
    "ghp": "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5",
    "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzz9Q7Z8XQK",
    "pw": "correcthorsebattery42",
    "short": "Hunter2!",
    "n8n": "n8n_api_" + "f3a9c1e7b2d84a6c9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b",
}
DOTENV = "".join("%s=%s\n" % (k.upper(), v) for k, v in FILE_BODY_SECRETS.items())
PEM = ("-----BEGIN RSA PRIVATE KEY-----\n" + "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0\n" * 4 +
       "-----END RSA PRIVATE KEY-----\n")


@pytest.mark.parametrize("tool,tool_input,expected", [
    ("Write", {"file_path": "/repo/.env", "content": DOTENV}, "path /repo/.env\nfields file_path content"),
    ("Write", {"file_path": "/repo/id_rsa", "content": PEM}, "path /repo/id_rsa\nfields file_path content"),
    ("Edit", {"file_path": "/repo/cfg.py", "old_string": "x", "new_string": DOTENV, "replace_all": True},
     "path /repo/cfg.py\nfields file_path old_string new_string replace_all"),
    ("NotebookEdit", {"notebook_path": "/repo/n.ipynb", "new_source": DOTENV, "cell_id": "c1"},
     "path /repo/n.ipynb\nfields notebook_path new_source cell_id"),
])
def test_a_file_tool_sends_the_path_and_the_field_names_and_no_content(stub, tool, tool_input, expected):
    go(stub, payload(tool=tool, tool_input=tool_input))
    assert sent_text(stub) == expected
    everything = sent_everything(stub)
    assert [n for n, v in FILE_BODY_SECRETS.items() if v in everything] == []
    assert "PRIVATE KEY" not in everything and "MIIEow" not in everything


def test_a_bash_command_that_writes_a_secret_file_sends_the_target_and_not_the_body(stub):
    command = "cat > .env <<'EOF'\n" + DOTENV + "EOF\ngh auth login --with-token <<< %s" % FILE_BODY_SECRETS["ghp"]
    go(stub, payload(command=command))
    assert sent_text(stub) == "cat .env\ngh --with-token"
    everything = sent_everything(stub)
    assert [n for n, v in FILE_BODY_SECRETS.items() if v in everything] == []


PLAIN = "correcthorsebattery42"


@pytest.mark.parametrize("tool_input,names", [
    ({"password": PLAIN}, "password"),
    ({"username": "tee", "password": PLAIN}, "username password"),
    ({"variables": {"DB_PASSWORD": PLAIN}}, "variables DB_PASSWORD"),
    ({"env": {"DB_PASSWORD": PLAIN, "N8N_VPS_KEY": "Zq81nT0wUv44"}}, "env DB_PASSWORD N8N_VPS_KEY"),
    ({"key": "DB_PASSWORD", "value": PLAIN}, "key value"),
    ({"name": "SMTP_PASS", "value": PLAIN}, "name value"),
    ({"env": [{"name": "SMTP_PASS", "value": PLAIN}]}, "env name value"),
    ({"headers": {"x-devon-key": PLAIN}}, "headers x-devon-key"),
    ({"headers": {"Authorization": "Bearer " + PLAIN}}, "headers Authorization"),
    ({"credentials": {"user": "tee", "secret": {"value": PLAIN}}}, "credentials user secret value"),
    ({"auth": [PLAIN]}, "auth"),
    ({"token": "abc"}, "token"),
    ({"operations": [{"node": {"parameters": {"apiKey": PLAIN, "body": DOTENV}}}]}, "operations node parameters apiKey body"),
    ({"a": None, "b": True, "c": 1.5, "d": [], "e": {}}, "a b c d e"),
])
def test_an_mcp_call_sends_the_field_names_and_never_a_value(stub, tool_input, names):
    go(stub, payload(tool="mcp__railway__set_variables", tool_input=tool_input))
    assert sent_text(stub) == "fields " + names
    everything = sent_everything(stub)
    assert PLAIN not in everything and "Zq81nT0wUv44" not in everything and "tee" not in sent_text(stub).split()
    assert [n for n, v in FILE_BODY_SECRETS.items() if v in everything] == []


@pytest.mark.parametrize("tool_input", [None, "a string", ["a", "b"], 7, True, {}, [], {"": 1}])
def test_an_mcp_input_with_no_field_names_sends_the_tool_name_alone(stub, project, tool_input):
    go(stub, {"session_id": "s1", "tool_name": "mcp__x__y", "cwd": "/repo", "tool_input": tool_input})
    assert sent_text(stub) == ""
    assert stub.requests[-1]["body"]["state"]["tool_name"] == "mcp__x__y"
    assert ledger(project)[-1]["outcome"] == "answered"


def test_a_secret_used_as_a_field_name_is_dropped(stub):
    keys = {
        FILE_BODY_SECRETS["ghp"]: "label",
        "Authorization: Bearer abcdefgh12345678": "x",
        "0123456789abcdef0123456789abcdef": 1,
        "a" * 31: 1,
        "key with space": 1,
        "k1234567": 1,
        "9starts_with_digit": 1,
        "café": 1,
        "ok_name": 1,
        "x" * 30: 1,
    }
    go(stub, payload(tool="mcp__x__y", tool_input=keys))
    assert sent_text(stub) == "fields ok_name " + "x" * 30
    everything = sent_everything(stub)
    assert FILE_BODY_SECRETS["ghp"] not in everything and "abcdefgh12345678" not in everything


def test_ordinary_mcp_field_names_still_leave(stub):
    go(stub, payload(tool="mcp__github__create_pull_request",
                     tool_input={"owner": "tdveal74-cell", "repo": "app", "title": "Fix the sweep", "draft": True}))
    assert sent_text(stub) == "fields owner repo title draft"
    assert "tdveal74" not in sent_everything(stub) and "sweep" not in sent_everything(stub)


def test_field_names_are_shallowest_first_deduplicated_and_depth_bounded():
    deep = {"l0": {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": 1}}}}}}}}}}
    assert jev.field_names(deep) == ["l0", "l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8"]
    assert jev.field_names({"a": [{"b": 1}, {"b": 2, "c": 3}], "d": 4}) == ["a", "d", "b", "c"]


def test_a_huge_input_is_cut_at_the_field_and_node_caps():
    started = time.monotonic()
    assert len(jev.field_names({"ids": list(range(500000))})) == 1
    assert len(jev.field_names({"f%d" % i: i for i in range(100000)})) == jev.MAX_FIELDS
    assert len(jev.field_names({"a": [{"k%d" % i: 1} for i in range(1000)]})) <= jev.MAX_FIELDS
    assert time.monotonic() - started < 0.5


def test_a_wide_mcp_input_is_cut_at_a_field_boundary(stub):
    wide = {"n" + chr(97 + i // 26) + chr(97 + i % 26) + "q" * 26: i for i in range(300)}
    go(stub, payload(tool="mcp__x__" + "y" * 100, tool_input=wide))
    names = sent_text(stub).split()[1:]
    assert sent_chars(stub) <= jev.MAX_OUT
    assert len(names) == jev.MAX_FIELDS and all(len(name) == 29 for name in names)


def test_a_tool_name_outside_the_character_class_sends_nothing(stub, project):
    for name in ("Bad Tool", "x;rm", "tést", "a" * 121, "mcp__x/y"):
        assert go(stub, payload(tool=name)) is None
        assert ledger(project)[-1]["outcome"] == "bad_input"
    assert stub.requests == []


def test_the_request_shape(stub):
    go(stub)
    sent = stub.requests[-1]
    assert sent["headers"]["Authorization"] == "Bearer k"
    body = sent["body"]
    assert set(body) == {"model", "state", "questions"}
    assert set(body["state"]) == {"tool_name", "tool_input"}
    assert set(body["questions"]) == {"better_tool", "needs_human"}
    for q in body["questions"].values():
        assert q["type"] == "noul" and set(q["criteria"]) == {"true", "false"}


def test_the_questions_describe_an_outline_and_not_a_command():
    note = jev.STATE_NOTE
    assert "never holds a value" in note
    assert "key: value" not in note


def test_the_ledger_never_holds_the_input(stub, project):
    go(stub, payload(command="cat a-very-distinctive-filename.txt"))
    text = (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()
    assert "distinctive" not in text
    row = ledger(project)[-1]
    assert row["input_sha"] == jev.input_digest("Bash", {"command": "cat a-very-distinctive-filename.txt"})
    assert row["sent_chars"] == sent_chars(stub)


def test_the_hash_is_of_the_raw_call_so_identical_means_identical():
    a = jev.input_digest("Bash", {"command": "rm -rf build"})
    assert a == jev.input_digest("Bash", {"command": "rm -rf build"})
    assert a != jev.input_digest("Bash", {"command": "rm -rf dist"})
    assert a != jev.input_digest("bash", {"command": "rm -rf build"})
    assert a != jev.input_digest("Bash", {"command": "rm -rf build", "timeout": 5})
    assert jev.input_digest("Bash", {"b": 1, "a": 2}) == jev.input_digest("Bash", {"a": 2, "b": 1})
    assert jev.input_digest("Bash", {1: "x", "a": 2})
    assert jev.input_digest("Bash", {"x": "\ud800"})


# ---------------------------------------------- no scrubbing, no backtracking


def test_nothing_is_cut_out_of_the_raw_call():
    """The held version scrubbed the call. This one has no scrubber to miss with."""
    source = HOOK.read_text()
    assert "gate_ledger" not in source
    assert not hasattr(jev, "load_scrub") and not hasattr(jev, "outbound") and not hasattr(jev, "OUTBOUND_SHAPES")


REPEATS = ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT")


def quantifier_faults(pattern):
    """Nested or adjacent unbounded quantifiers in a regex, by parsing it."""
    faults = []

    def name_of(op):
        return getattr(op, "name", repr(op))

    def children(op, av):
        name = name_of(op)
        if name in REPEATS:
            yield av[2]
        elif name == "SUBPATTERN":
            yield av[3]
        elif name == "BRANCH":
            yield from av[1]
        elif name in ("ASSERT", "ASSERT_NOT"):
            yield av[1]
        elif name == "ATOMIC_GROUP":
            yield av
        elif name == "GROUPREF_EXISTS":
            yield from (part for part in av[1:] if part is not None)

    def walk(seq, inside_unbounded):
        previous = False
        for op, av in seq:
            repeat = name_of(op) in REPEATS
            unbounded = repeat and av[1] == sre_parse.MAXREPEAT
            if repeat and inside_unbounded:
                faults.append("nested")
            if unbounded and previous:
                faults.append("adjacent")
            previous = unbounded
            for child in children(op, av):
                walk(child, inside_unbounded or unbounded)

    walk(sre_parse.parse(pattern), False)
    return faults


def test_the_fault_finder_finds_faults():
    assert "nested" in quantifier_faults(r"(a+)+")
    assert "nested" in quantifier_faults(r"(?:ab*)*c")
    assert "nested" in quantifier_faults(r"(a|b+)*")
    assert "adjacent" in quantifier_faults(r"\s*\S*")
    assert "adjacent" in quantifier_faults(r"[a-z]+\d*x")
    assert quantifier_faults(r"[A-Za-z0-9._/~-]{1,200}") == []
    assert quantifier_faults(r"[^ \t]+") == []


def test_no_regex_in_the_hook_has_a_nested_or_adjacent_unbounded_quantifier():
    tree = ast.parse(HOOK.read_text())
    calls, literals = [], []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"):
            calls.append(node)
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                literals.append(node.args[0].value)
    assert calls and len(calls) == len(literals), "every pattern is a literal that can be read here"
    for pattern in literals:
        assert quantifier_faults(pattern) == [], pattern


def test_the_hook_imports_only_what_it_uses():
    imports = {n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(HOOK.read_text())) if isinstance(n, ast.Import)}
    assert imports <= {"hashlib", "itertools", "json", "os", "re", "sys", "threading", "time", "urllib"}, imports


# ------------------------------------------------------------------ main()


def test_main_sends_through_the_outline_only(stub, monkeypatch):
    p = payload(tool="Write", tool_input={"file_path": "/repo/.env", "content": DOTENV})
    rc, _ = run_main(monkeypatch, json.dumps(p), stub.url)
    assert rc == 0
    assert [n for n, v in FILE_BODY_SECRETS.items() if v in sent_everything(stub)] == []


def test_main_fails_open_on_a_crash(stub, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("crash")
    monkeypatch.setattr(jev, "run", boom)
    rc, out = run_main(monkeypatch, json.dumps(payload()), stub.url)
    assert rc == 0 and out == ""


@pytest.mark.parametrize("stdin_text", ["not json", "[]", "{}", '{"tool_name": 7}', '{"tool_input": {"command": "ls"}}', "",
                                        "[" * 100000, '{"tool_name": "Bash", "tool_input": ' + "[" * 100000])
def test_main_on_bad_input_sends_nothing_and_says_so(stub, project, monkeypatch, stdin_text):
    rc, out = run_main(monkeypatch, stdin_text, stub.url)
    assert rc == 0 and out == ""
    assert stub.requests == []
    assert ledger(project)[-1]["outcome"] == "bad_input"


def test_main_on_input_over_the_stdin_cap_sends_nothing_and_says_so(stub, project, monkeypatch):
    big = '{"tool_name": "Bash", "tool_input": {"command": "%s"}}' % ("x" * jev.MAX_STDIN)
    rc, out = run_main(monkeypatch, big, stub.url)
    assert rc == 0 and out == "" and stub.requests == []
    assert ledger(project)[-1]["outcome"] == "bad_input"


def test_a_crash_inside_run_still_leaves_a_row(stub, project, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Bearer tsk_live_abcDEF123456xyz")
    monkeypatch.setattr(jev, "run", boom)
    run_main(monkeypatch, json.dumps(payload()), stub.url)
    row = ledger(project)[-1]
    assert row["outcome"] == "crash" and row["error"] == "RuntimeError"


def test_a_lone_surrogate_is_sent_and_recorded(stub, project, monkeypatch):
    rc, out = run_main(monkeypatch, '{"tool_name": "Bash", "session_id": "s", "tool_input": {"command": "echo \\ud800"}}', stub.url)
    assert rc == 0 and len(stub.requests) == 1
    assert ledger(project)[-1]["outcome"] == "answered"


def test_the_script_runs_as_a_process_and_prints_nothing_without_a_key(project):
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload()), capture_output=True, text=True,
                          env=env, timeout=30)
    assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""
    assert ledger(project)[-1]["outcome"] == "no_key"


# --------------------------------------------------------------- the wiring


def jev_group():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    groups = [g for g in settings["hooks"]["PreToolUse"] if any("jev_route.py" in h["command"] for h in g["hooks"])]
    assert len(groups) == 1
    return groups[0]


def test_the_matcher_names_exactly_the_tools_claude_md_names():
    assert jev_group()["matcher"] == "^(Bash|bash|Edit|Write|NotebookEdit|mcp__.*)$"


def test_the_matcher_is_exact_under_substring_search():
    """Claude Code tests the matcher as a regex search, so it must be anchored."""
    matcher = jev_group()["matcher"]
    for tool in ("Bash", "Edit", "Write", "NotebookEdit", "mcp__n8n_vps__publish_workflow"):
        assert re.search(matcher, tool), tool
    for tool in ("Read", "Grep", "Glob", "Agent", "TodoWrite", "MultiEdit", "BashOutput", "KillBash"):
        assert not re.search(matcher, tool), tool


def test_the_wrapper_maps_any_failure_to_a_visible_non_blocking_exit():
    hooks = jev_group()["hooks"]
    assert [h["command"] for h in hooks] == [WRAPPER]
    assert [h["timeout"] for h in hooks] == [5]


def test_the_budget_fits_inside_the_hook_timeout_with_room():
    timeout = jev_group()["hooks"][0]["timeout"]
    assert jev.HOOK_BUDGET_S <= timeout / 2
    assert jev.RESERVE_S < jev.HOOK_BUDGET_S


def test_the_ledger_directory_is_not_repository_content():
    assert ".claude/ledger/" in (ROOT / ".gitignore").read_text()


def test_the_test_file_is_in_the_standalone_job_and_in_the_documented_list():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert re.search(r"^\s+test_jev_route\.py \\$", ci, re.M)
    assert "test_jev_route.py" in (ROOT / "CLAUDE.md").read_text().split("## Reproducing CI")[1].split("## Invariants")[0]


def test_no_em_or_en_dashes_in_the_hook_or_this_file():
    for path in (HOOK, pathlib.Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, path
