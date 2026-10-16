"""
The Jev router, tested against the ways it could quietly widen what runs or
leak what it sends.

Ruled by Tee 2026-10-16 (.claude/hooks/jev_route.py). The hook may only deny
or ask. These tests drive it against a stub server on 127.0.0.1 that answers in
the shape of TypeSafe's published OpenAPI spec, and pin the promises the module
docstring makes: it never prints allow, it fails open with a ledger row on
every failure, a deny stands only once its ledger row is written, and nothing
leaves unscrubbed.

They prove the hook's own logic and nothing about Jev's judgment, which only a
live call can measure.

Standalone: no database, no network beyond loopback, no repository state
beyond the files.
"""

from __future__ import annotations

import http.server
import importlib.util
import io
import json
import pathlib
import re
import socket
import threading
import time
from datetime import datetime, timezone

import pytest

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
REAL_SCRUB = jev.load_scrub()
NOW = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)


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

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d/v1/systemone" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

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
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(jev, "ENFORCE", True)


def ledger(project):
    path = project / ".claude" / "ledger" / "jev-route.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def payload(command="cat README.md", session="s1", tool="Bash", tool_input=None):
    return {"session_id": session, "tool_name": tool, "cwd": "/repo",
            "tool_input": tool_input if tool_input is not None else {"command": command}}


def go(stub, p=None, **kw):
    kw.setdefault("key", "k")
    kw.setdefault("endpoint", stub.url)
    kw.setdefault("scrub", REAL_SCRUB)
    return jev.run(p or payload(), now=NOW, **kw)


# ------------------------------------------------------------ what it decides


def test_the_shipped_mode_is_shadow():
    """Flipping this takes a ruling and a commit."""
    assert SHIPPED_ENFORCE is False


def test_the_shipped_numbers_are_the_ones_claude_md_states():
    assert (jev.CONFIDENCE, jev.DEADLINE_S, jev.MAX_INPUT) == (0.8, 2.5, 2000)
    assert (jev.SCRUB_BUDGET_S, jev.BREAKER_ERRORS, jev.BREAKER_S) == (1.0, 3, 600)
    section = (ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0]
    for stated in ("probability\nof 0.8", "2.5 second", "2,000\ncharacters", "1 second", "three failed", "ten minutes"):
        assert stated.replace("\n", " ") in section.replace("\n", " "), stated


def test_needs_human_at_threshold_asks(stub, enforce):
    stub.answer(0.0, jev.CONFIDENCE)
    assert go(stub)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_a_shadow_deny_does_not_grant_a_repeat_pass(stub, project, monkeypatch):
    """A row written in shadow mode must not let the call through once ENFORCE flips."""
    stub.answer(0.95, 0.0)
    assert go(stub) is None and ledger(project)[-1]["decision"] == "deny"
    monkeypatch.setattr(jev, "ENFORCE", True)
    assert go(stub)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert len(stub.requests) == 2


def test_better_tool_at_threshold_denies(stub, project, enforce):
    stub.answer(jev.CONFIDENCE, 0.0)
    out = go(stub)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert ledger(project)[-1]["decision"] == "deny"


def test_just_below_threshold_prints_nothing(stub, enforce):
    stub.answer(jev.CONFIDENCE - 0.001, jev.CONFIDENCE - 0.001)
    assert go(stub) is None


def test_needs_human_asks_and_wins_over_better_tool(stub, enforce):
    stub.answer(0.99, 0.95)
    assert go(stub)["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize("better_tool", [0.0, 0.5, 0.8, 1.0])
@pytest.mark.parametrize("needs_human", [0.0, 0.5, 0.8, 1.0])
def test_it_never_prints_allow(stub, enforce, better_tool, needs_human):
    stub.answer(better_tool, needs_human)
    out = go(stub, payload(command="echo %s %s" % (better_tool, needs_human)))
    assert out is None or out["hookSpecificOutput"]["permissionDecision"] in ("deny", "ask")


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


def test_a_deny_is_not_printed_when_its_row_cannot_be_written(stub, project, monkeypatch, enforce):
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


# --------------------------------------------------------------- fails open


def test_no_key_sends_nothing(stub, project):
    assert go(stub, key="") is None
    assert stub.requests == []
    assert ledger(project)[-1]["outcome"] == "no_key"


def test_no_scrubber_sends_nothing(stub, project):
    assert go(stub, scrub=None) is None
    assert stub.requests == []
    assert "scrubber" in ledger(project)[-1]["error"]


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
    out = jev.run(payload(), key="k", endpoint="http://127.0.0.1:%d/v1/systemone" % port,
                  now=NOW, scrub=REAL_SCRUB, timeout=0.5)
    assert out is None
    assert time.monotonic() - started < 1.5
    assert ledger(project)[-1]["outcome"] == "error"
    listener.close()


def test_a_dead_host_fails_open(project):
    assert jev.run(payload(), key="k", endpoint="http://127.0.0.1:9/v1/systemone",
                   now=NOW, scrub=REAL_SCRUB, timeout=0.5) is None
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
def test_an_unsafe_endpoint_is_refused_before_any_send(project, url):
    assert jev.run(payload(), key="k", endpoint=url, now=NOW, scrub=REAL_SCRUB) is None
    assert ledger(project)[-1]["error"] == "endpoint refused"


def test_three_failed_requests_open_the_breaker_for_ten_minutes(project):
    dead = "http://127.0.0.1:9/v1/systemone"
    for _ in range(jev.BREAKER_ERRORS):
        jev.run(payload(), key="k", endpoint=dead, now=NOW, scrub=REAL_SCRUB, timeout=0.5)
    assert [r["outcome"] for r in ledger(project)] == ["error"] * jev.BREAKER_ERRORS
    started = time.monotonic()
    jev.run(payload(), key="k", endpoint=dead, now=NOW, scrub=REAL_SCRUB, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "breaker_open"
    assert "latency_ms" not in ledger(project)[-1]
    assert time.monotonic() - started < 0.4
    later = NOW.replace(minute=NOW.minute + 10)
    jev.run(payload(), key="k", endpoint=dead, now=later, scrub=REAL_SCRUB, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "error", "the breaker must let one request through after BREAKER_S"


def test_an_answer_closes_the_breaker(stub, project):
    for _ in range(jev.BREAKER_ERRORS - 1):
        jev.run(payload(), key="k", endpoint="http://127.0.0.1:9/v1/systemone", now=NOW, scrub=REAL_SCRUB, timeout=0.5)
    go(stub)
    jev.run(payload(), key="k", endpoint="http://127.0.0.1:9/v1/systemone", now=NOW, scrub=REAL_SCRUB, timeout=0.5)
    go(stub)
    assert ledger(project)[-1]["outcome"] == "answered"


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


def test_a_key_with_a_trailing_newline_is_stripped_and_never_written(stub, project):
    go(stub, key="tsk_live_abcDEF123456xyz\n")
    assert stub.requests[-1]["headers"]["Authorization"] == "Bearer tsk_live_abcDEF123456xyz"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_a_key_a_header_cannot_carry_is_refused_before_any_send(stub, project):
    go(stub, key="tsk_live_abc\nDEF123456xyz")
    assert stub.requests == []
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_an_error_message_carrying_the_key_is_scrubbed(project, monkeypatch):
    def leaky(body, key, endpoint, deadline):
        raise ValueError("Invalid header value b'Bearer %s'" % key)
    monkeypatch.setattr(jev, "ask_within", leaky)
    jev.run(payload(), key="tsk_live_abcDEF123456xyz", endpoint="http://127.0.0.1:9/v1/systemone", now=NOW, scrub=REAL_SCRUB)
    row = ledger(project)[-1]
    assert row["outcome"] == "error" and "tsk_live" not in row["error"]


def test_the_shipped_endpoint_and_model():
    assert jev.ENDPOINT == "https://api.typesafe.ai/v1/systemone" and jev.endpoint_ok(jev.ENDPOINT)
    assert jev.MODEL.startswith("jev-")


# --------------------------------------------------------- what leaves here

SECRETS = {
    "ghp": "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5",
    "github_pat": "github_pat_11ABCDEFG0" + "aB3dE5fG7hJ9kL1mN3pQ5r_S7tU9vW1xY3zA5bC7dE9fG1hJ3kL5mN7pQ9rS1tU3vW5xY7z",
    "aws_akid": "AKIA" + "Z7Q2LMNOPQRSTUVW",
    "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzz9Q7Z8XQK",
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "n8n": "n8n_api_" + "f3a9c1e7b2d84a6c9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b",
    "hex40": "3f786850e387550fdab836ed7e6dc881de23001b",
    "quoted_pw": "correcthorsebattery42",
    "short_pw": "Hunter2!",
    "smtp_pass": "pl41nP4ssw0rdValue",
    "pg_pw": "Sup3rS3cretDbPw",
    "devon_key": "devonkey9f8e7d6c5b4a",
    "anthropic": "sk-ant-api03-" + "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
}
PEM_BODY = "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0" * 4
PEM = "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(PEM_BODY[i:i + 64] for i in range(0, len(PEM_BODY), 64)) + "\n-----END RSA PRIVATE KEY-----\n"
DOTENV = (
    "GITHUB_TOKEN=%(ghp)s\nAWS_ACCESS_KEY_ID=%(aws_akid)s\nAWS_SECRET_ACCESS_KEY=%(aws_secret)s\n"
    'DB_PASSWORD="%(quoted_pw)s"\n' "ADMIN_PASSWORD='%(short_pw)s'\nSMTP_PASS=%(smtp_pass)s\n"
    "DATABASE_URL=postgresql://app:%(pg_pw)s@db.internal:5432/app\n" 'N8N_VPS_KEY="%(n8n)s"\n'
) % SECRETS
CREDS_JSON = json.dumps({"api_key": SECRETS["anthropic"], "password": SECRETS["quoted_pw"],
                         "x-devon-key": SECRETS["devon_key"]}, indent=2)


def sent_text(stub):
    return stub.requests[-1]["body"]["state"]["tool_input"]


@pytest.mark.parametrize("tool,tool_input", [
    ("Write", {"file_path": "/repo/.env", "content": DOTENV}),
    ("Write", {"file_path": "/repo/creds.json", "content": CREDS_JSON}),
    ("Edit", {"file_path": "/repo/cfg.py", "old_string": "x", "new_string": DOTENV}),
    ("Bash", {"command": "cat > .env <<'EOF'\n" + DOTENV + "EOF"}),
    ("Bash", {"command": "gh auth login --with-token <<< %s; echo %s %s" % (SECRETS["github_pat"], SECRETS["jwt"], SECRETS["hex40"])}),
    ("mcp__n8n_vps__update_workflow", {"workflowId": "x", "operations": [{"node": {"parameters": {"apiKey": SECRETS["n8n"], "body": DOTENV}}}]}),
])
def test_no_secret_shape_leaves_in_any_tool(stub, tool, tool_input):
    go(stub, payload(tool=tool, tool_input=tool_input))
    text = sent_text(stub)
    leaked = [name for name, value in SECRETS.items() if value in text]
    assert leaked == []


def test_a_private_key_leaves_no_body(stub):
    go(stub, payload(tool="Write", tool_input={"file_path": "/repo/id_rsa", "content": PEM}))
    text = sent_text(stub)
    assert "BEGIN RSA PRIVATE KEY" not in text
    assert not re.search(r"[A-Za-z0-9+/]{16,}", text.replace("/repo/id_rsa", ""))


def test_an_unterminated_private_key_is_still_cut(stub):
    go(stub, payload(tool="Write", tool_input={"file_path": "/repo/k", "content": "x" * 2400 + PEM}))
    assert "MIIEowIBAAKCAQEA" not in sent_text(stub)


PLAIN = "correcthorsebattery42"


@pytest.mark.parametrize("tool_input", [
    {"password": PLAIN},
    {"username": "tee", "password": PLAIN},
    {"variables": {"DB_PASSWORD": PLAIN}},
    {"env": {"DB_PASSWORD": PLAIN, "N8N_VPS_KEY": "Zq81nT0wUv44"}},
    {"key": "DB_PASSWORD", "value": PLAIN},
    {"name": "SMTP_PASS", "value": PLAIN},
    {"env": [{"name": "SMTP_PASS", "value": PLAIN}]},
    {"headers": {"x-devon-key": PLAIN}},
    {"headers": {"Authorization": "Bearer " + PLAIN}},
    {"credentials": {"user": "tee", "secret": {"value": PLAIN}}},
    {"auth": [PLAIN]},
    {"token": "abc"},
])
def test_a_value_under_a_secret_name_never_leaves(stub, tool_input):
    """An MCP input is structured: the name sits in the key or a sibling field,
    so the value must be judged by its name and not by its shape."""
    go(stub, payload(tool="mcp__railway__set_variables", tool_input=tool_input))
    text = sent_text(stub)
    assert PLAIN not in text and "Zq81nT0wUv44" not in text and "abc" not in text.split("token: ")[-1]


def test_the_name_beside_a_secret_still_leaves(stub):
    go(stub, payload(tool="mcp__railway__set_variables", tool_input={"name": "SMTP_PASS", "value": PLAIN, "service": "web"}))
    text = sent_text(stub)
    assert "name: SMTP_PASS" in text and "value: [REDACTED]" in text


def test_a_token_used_as_a_dict_key_never_leaves(stub):
    go(stub, payload(tool="mcp__x__y", tool_input={SECRETS["ghp"]: "label", "Authorization: Bearer abcdefgh12345678": "x"}))
    text = sent_text(stub)
    assert SECRETS["ghp"] not in text and "abcdefgh12345678" not in text


def test_ordinary_mcp_fields_still_leave(stub):
    go(stub, payload(tool="mcp__github__create_pull_request",
                     tool_input={"owner": "tdveal74-cell", "repo": "app", "title": "Fix the sweep", "draft": True}))
    text = sent_text(stub)
    for line in ("owner: tdveal74-cell", "repo: app", "title: Fix the sweep", "draft: True"):
        assert line in text


def test_the_path_survives_a_long_body(stub):
    go(stub, payload(tool="Write", tool_input={"file_path": "/repo/notes/plan.md", "content": "word " * 2000}))
    text = sent_text(stub)
    assert text.startswith("file_path: /repo/notes/plan.md")
    assert len(text) <= jev.MAX_INPUT


def test_the_path_survives_whatever_order_the_keys_arrive_in(stub):
    go(stub, payload(tool="Write", tool_input={"content": "word " * 2000, "file_path": "/repo/notes/plan.md"}))
    assert sent_text(stub).startswith("file_path: /repo/notes/plan.md")


@pytest.mark.parametrize("pad", [" ", "\n", "w "])
def test_scrubbing_happens_before_the_cut(stub, pad):
    """A secret that straddles the MAX_INPUT edge must not leave as a prefix.
    The padding is separate words, so the secret is a word of its own and the
    order of scrub and cut decides whether its prefix leaves."""
    secret = SECRETS["ghp"]
    content = (pad * jev.MAX_INPUT)[:jev.MAX_INPUT - len("content: ") - 10] + secret
    go(stub, payload(tool="Write", tool_input={"content": content}))
    assert secret[:6] not in sent_text(stub)


def test_no_fragment_survives_the_slice_edge():
    """A token cut in half by SCRUB_SLICE is too short for any rule to know."""
    tokens = ["%040x" % (0x9F3B << 140 | i * 7919 + 13) for i in range(70)]
    for lead in range(0, 41, 3):
        text = jev.call_text({"command": " " * lead + " ".join(tokens)}, REAL_SCRUB)
        words = [w for w in text.replace("command:", "").split() if w != "[REDACTED]"]
        assert words == [], (lead, words)


def test_scrubbing_a_huge_input_stays_fast(stub):
    started = time.monotonic()
    go(stub, payload(tool="Write", tool_input={"file_path": "/x", "content": "a=" * 80000}))
    assert time.monotonic() - started < 2.0


def test_many_pathological_leaves_stay_inside_the_scrub_budget():
    """The gate's NAME=value rule is quadratic on long runs. One leaf is bounded
    by the slice; the number of leaves is bounded by the budget."""
    tool_input = {"k%d" % i: "a." * 1300 for i in range(40)}
    started = time.monotonic()
    jev.call_text(tool_input, REAL_SCRUB)
    assert time.monotonic() - started < jev.SCRUB_BUDGET_S + 0.6


def test_a_huge_list_is_cut_at_max_leaves():
    started = time.monotonic()
    text = jev.call_text({"ids": list(range(500000))}, REAL_SCRUB)
    assert time.monotonic() - started < 0.5
    assert text.count("\n") < jev.MAX_LEAVES


# One sample per outbound rule that only that rule catches, after the gate's own
# scrubber has run. The secret part must survive every other rule.
ONLY_THIS_RULE = [
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Bl bnNz\n-----END OPENSSH PRIVATE KEY-----", "b3Bl bnNz"),
    ("echo ghu_abcdefghij0123456789", "ghu_abcdefghij"),
    ("echo n8n_api_0123456789abcdef01234567", "0123456789abcdef01234567"),
    ("echo 0123456789abcdef0123456789abcdef", "0123456789abcdef0123456789abcdef"),
    ("echo QWxhZGRpbjpvcGVuIHNl/c2FtZQx9+abc12zz34", "QWxhZGRpbjpvcGVuIHNl"),
    ('curl -H "X-Auth: glpat-' 'aB3dE5gH7jK9mN1pQ3sT"', "aB3dE5gH7jK9mN1pQ3sT"),
    ('curl -H "X-Auth: shpat_' '0123456789abcdef0123456789abcdef"', "0123456789abcdef0123456789abcdef"),
    ('curl -H "X-Auth: SG.abcdefghijklmnopqrstuv.wxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefg"', "abcdefghijklmnopqrstuv"),
    ('curl -H "X-Auth: hf_' 'aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgH"', "hf_aBcDeFgH"),
    ("mysql --password=abc12", "abc12"),
]


def test_every_outbound_rule_is_needed():
    assert len(ONLY_THIS_RULE) == len(jev.OUTBOUND_SHAPES)
    for i, (sample, secret) in enumerate(ONLY_THIS_RULE):
        assert secret in REAL_SCRUB(sample), (i, "the gate already catches this sample")
        without = REAL_SCRUB(sample)
        for j, shape in enumerate(jev.OUTBOUND_SHAPES):
            if j != i:
                without = shape.sub(jev._redact, without)
        assert secret in without, (i, "another rule already catches this sample")
        assert secret not in jev.outbound(sample, REAL_SCRUB), i


@pytest.mark.parametrize("text,secret", [
    ("Server=db;Uid=sa;Pwd=abc12;", "abc12"),
    ("export DB_PWD=abc12", "abc12"),
    ('{"token": "abc"}', '"abc"'),
    ("password: hunter2", "hunter2"),
])
def test_a_short_value_after_a_secret_name_never_leaves(text, secret):
    assert secret not in jev.outbound(text, REAL_SCRUB)


@pytest.mark.parametrize("command", [
    "ls /var/lib/postgresql/16/main",
    "pip install -r requirements.txt",
    "git commit -m 'Fix the sweep' && git push -u origin claude/jev-route-hook",
    "PYTHONPATH=$PWD:$PWD/apps/api python3 -m pytest -q test_jev_route.py",
])
def test_ordinary_commands_leave_unchanged(command):
    assert jev.outbound(command, REAL_SCRUB) == command


def test_the_request_shape_and_key(stub):
    go(stub)
    sent = stub.requests[-1]
    assert sent["headers"]["Authorization"] == "Bearer k"
    body = sent["body"]
    assert set(body) == {"model", "state", "questions"}
    assert set(body["questions"]) == {"better_tool", "needs_human"}
    for q in body["questions"].values():
        assert q["type"] == "noul" and set(q["criteria"]) == {"true", "false"}


def test_the_ledger_never_holds_the_input(stub, project):
    go(stub, payload(command="cat a-very-distinctive-filename.txt"))
    assert "distinctive" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_the_real_scrubber_loads():
    assert REAL_SCRUB is not None


# ------------------------------------------------------------------ main()


def run_main(monkeypatch, stdin_text, endpoint, key="k"):
    monkeypatch.setattr(jev, "ENDPOINT", endpoint)
    monkeypatch.setenv("TYPESAFE_API_KEY", key)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    rc = jev.main()
    return rc, out.getvalue()


def test_main_sends_through_the_real_scrubber(stub, monkeypatch):
    rc, _ = run_main(monkeypatch, json.dumps(payload(tool="Write", tool_input={"file_path": "/repo/.env", "content": DOTENV})), stub.url)
    assert rc == 0
    assert [n for n, v in SECRETS.items() if v in sent_text(stub)] == []


def test_main_fails_open_on_a_crash(stub, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("crash")
    monkeypatch.setattr(jev, "run", boom)
    rc, out = run_main(monkeypatch, json.dumps(payload()), stub.url)
    assert rc == 0 and out == ""


@pytest.mark.parametrize("stdin_text", ["not json", "[]", "{}", '{"tool_name": 7}', '{"tool_input": {"command": "ls"}}'])
def test_main_on_bad_input_sends_nothing_and_says_so(stub, project, monkeypatch, stdin_text):
    rc, out = run_main(monkeypatch, stdin_text, stub.url)
    assert rc == 0 and out == ""
    assert stub.requests == []
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


def test_main_reads_only_the_key_and_the_project_dir_from_the_environment():
    source = HOOK.read_text()
    reads = set(re.findall(r"""(?:environ\.get|getenv)\(\s*["']([A-Za-z_]+)["']""", source))
    assert reads == {"CLAUDE_PROJECT_DIR", "TYPESAFE_API_KEY"}
    assert "os.environ[" not in source and "environ.copy" not in source and "dict(os.environ" not in source


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


def test_the_worst_case_fits_inside_the_hook_timeout():
    """Start up, one scrub budget plus one leaf past it, the deadline: under 5 s."""
    assert jev.SCRUB_BUDGET_S + 0.5 + jev.DEADLINE_S + 0.5 < jev_group()["hooks"][0]["timeout"]


def test_no_em_or_en_dashes_in_the_hook_or_this_file():
    for path in (HOOK, pathlib.Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, path
