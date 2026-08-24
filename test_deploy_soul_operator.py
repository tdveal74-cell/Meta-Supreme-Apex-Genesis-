"""Regression tests for the hosted DEVON browser Operator boundary.

The live Sandbox service is replaced with a tiny fake.  CI verifies routing,
authentication, snapshot continuity and secret non-forwarding without spending
cloud compute or requiring Vercel credentials.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"


def _probe() -> dict:
    script = r'''
import json
import os
import sys
import types

os.environ["CONSOLE_TOKEN"] = "test-console-token"
os.environ.pop("PINECONE_API_KEY", None)
sys.path.insert(0, r"__DEPLOY__")

created = []
headers_seen = []

class FakeResult:
    exit_code = 0
    def stdout(self):
        return "hello from sandbox\n__DEVON_CWD__=/vercel/sandbox\n"
    def stderr(self):
        return ""

class FakeSnapshot:
    snapshot_id = "snap_test_123"

class FakeSandbox:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.commands = []
        self.stopped = False
    @classmethod
    def create(cls, **kwargs):
        sbx = cls(kwargs)
        created.append(sbx)
        return sbx
    def run_command(self, executable, args):
        self.commands.append([executable, list(args)])
        return FakeResult()
    def snapshot(self):
        return FakeSnapshot()
    def stop(self):
        self.stopped = True

vercel = types.ModuleType("vercel")
vercel.__path__ = []
sandbox_mod = types.ModuleType("vercel.sandbox")
sandbox_mod.Sandbox = FakeSandbox
headers_mod = types.ModuleType("vercel.headers")
def set_headers(headers):
    headers_seen.append(dict(headers))
headers_mod.set_headers = set_headers
sys.modules["vercel"] = vercel
sys.modules["vercel.sandbox"] = sandbox_mod
sys.modules["vercel.headers"] = headers_mod

from fastapi.testclient import TestClient
import app as hosted

client = TestClient(hosted.app)

anon_terminal = client.get("/terminal")
anon_status = client.get("/api/v1/operator-terminal/status")
anon_command = client.post("/api/v1/operator-terminal/command", json={"command":"pwd"})

client.cookies.set("devon_console", "test-console-token")
authed_terminal = client.get("/terminal")
authed_status = client.get("/api/v1/operator-terminal/status")
first = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/vercel/sandbox"},
)
second = client.post(
    "/api/v1/operator-terminal/command",
    json={
        "command":"git status",
        "cwd":"/vercel/sandbox",
        "snapshot_id":"snap_test_123",
    },
)
escape = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/etc", "snapshot_id":"snap_test_123"},
)

mutations = sorted(
    (method, route.path)
    for route in hosted.app.routes
    for method in (route.methods or set())
    if method not in {"GET", "HEAD", "OPTIONS"}
)

print(json.dumps({
    "anon_terminal": anon_terminal.status_code,
    "anon_terminal_has_state": "STATE =" in anon_terminal.text,
    "anon_status": anon_status.status_code,
    "anon_command": anon_command.status_code,
    "authed_terminal": authed_terminal.status_code,
    "authed_terminal_is_real": "Operator Terminal" in authed_terminal.text,
    "authed_status": authed_status.status_code,
    "status_body": authed_status.json(),
    "first_status": first.status_code,
    "first_body": first.json(),
    "second_status": second.status_code,
    "second_body": second.json(),
    "escape_status": escape.status_code,
    "created": [s.kwargs for s in created],
    "commands": [s.commands for s in created],
    "headers_registered": bool(headers_seen),
    "mutations": mutations,
}))
'''.replace("__DEPLOY__", str(DEPLOY).replace("\\", "\\\\"))
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_browser_operator_is_gated_and_separate_from_soul():
    probe = _probe()
    assert probe["anon_terminal"] == 401
    assert probe["anon_terminal_has_state"] is False
    assert probe["anon_status"] == 401
    assert probe["anon_command"] == 401
    assert probe["authed_terminal"] == 200
    assert probe["authed_terminal_is_real"] is True
    assert probe["authed_status"] == 200
    assert probe["mutations"] == [["POST", "/api/v1/operator-terminal/command"]]


def test_browser_operator_reports_the_truth_about_its_boundary():
    probe = _probe()
    status_body = probe["status_body"]
    assert status_body["mode"] == "isolated-vercel-sandbox"
    assert status_body["production_secrets_injected"] is False
    assert status_body["github_write_connected"] is False
    assert status_body["devon_core_executes"] is False


def test_commands_start_from_meta_and_resume_only_from_snapshot():
    probe = _probe()
    assert probe["first_status"] == 200
    assert probe["first_body"]["stdout"] == "hello from sandbox\n"
    assert probe["first_body"]["cwd"] == "/vercel/sandbox"
    assert probe["first_body"]["snapshot_id"] == "snap_test_123"
    assert probe["second_status"] == 200

    first_create, second_create = probe["created"][:2]
    assert first_create["source"] == {
        "type": "git",
        "url": "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-.git",
        "revision": "main",
        "depth": 1,
    }
    assert second_create["source"] == {
        "type": "snapshot",
        "snapshot_id": "snap_test_123",
    }

    for create in probe["created"]:
        assert "env" not in create
        assert "password" not in create
        assert "token" not in create


def test_command_runs_in_microvm_shell_and_cwd_cannot_escape_workspace():
    probe = _probe()
    assert probe["commands"][0][0][0] == "bash"
    assert probe["commands"][0][0][1][0] == "-lc"
    assert probe["escape_status"] == 422
    assert probe["headers_registered"] is True


def test_hosted_wrapper_itself_never_imports_subprocess():
    source = (DEPLOY / "app.py").read_text()
    assert "import subprocess" not in source
    assert "subprocess." not in source
