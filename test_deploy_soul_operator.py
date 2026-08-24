"""Regression tests for the hosted DEVON browser Operator boundary.

The live Sandbox service is replaced with a fake that mirrors the public API
shipped by ``vercel-sandbox==0.4.0``. This intentionally does not provide the
old ``Sandbox.create``/``run_command`` methods, so SDK drift cannot be hidden by
a stale test double again.
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
resumed = []
headers_seen = []
boxes = []

class FakeGitSource(dict):
    def __init__(self, *, url, revision=None):
        super().__init__(url=url, revision=revision)

class FakeResult:
    def __init__(self):
        self.returncode = 0
        self.stdout = "hello from sandbox\n__DEVON_CWD__=/vercel/sandbox\n"
        self.stderr = ""

class FakeSandbox:
    def __init__(self, name, kwargs=None):
        self.name = name
        self.kwargs = kwargs or {}
        self.commands = []
        self.stopped = False
        boxes.append(self)
    async def run_process(self, executable, args, **kwargs):
        self.commands.append([executable, list(args), dict(kwargs)])
        return FakeResult()
    async def stop(self):
        self.stopped = True

async def create_sandbox(**kwargs):
    created.append(kwargs)
    return FakeSandbox("devon-workspace-001", kwargs)

async def resume_sandbox(*, name, **kwargs):
    resumed.append({"name": name, **kwargs})
    return FakeSandbox(name, kwargs)

vercel = types.ModuleType("vercel")
vercel.__path__ = []
sandbox_mod = types.ModuleType("vercel.sandbox")
sandbox_mod.GitSource = FakeGitSource
sandbox_mod.create_sandbox = create_sandbox
sandbox_mod.resume_sandbox = resume_sandbox
vercel.sandbox = sandbox_mod
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
        "workspace_id":"devon-workspace-001",
    },
)
escape = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/etc", "workspace_id":"devon-workspace-001"},
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
    "created": created,
    "resumed": resumed,
    "commands": [s.commands for s in boxes],
    "stopped": [s.stopped for s in boxes],
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
    assert status_body["sandbox_sdk_contract"] == "vercel-sandbox-0.4-module-api"


def test_commands_create_from_meta_then_resume_named_workspace():
    probe = _probe()
    assert probe["first_status"] == 200
    assert probe["first_body"]["stdout"] == "hello from sandbox\n"
    assert probe["first_body"]["cwd"] == "/vercel/sandbox"
    assert probe["first_body"]["workspace_id"] == "devon-workspace-001"
    assert probe["first_body"]["snapshot_id"] == "devon-workspace-001"
    assert probe["second_status"] == 200

    assert len(probe["created"]) == 1
    first_create = probe["created"][0]
    assert first_create["source"] == {
        "url": "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-.git",
        "revision": "main",
    }
    assert first_create["persistent"] is True
    assert probe["resumed"] == [{"name": "devon-workspace-001"}]

    for create in probe["created"]:
        assert "env" not in create
        assert "password" not in create
        assert "token" not in create


def test_command_uses_current_run_process_api_and_stops_for_persistence():
    probe = _probe()
    assert probe["commands"][0][0][0] == "bash"
    assert probe["commands"][0][0][1][0] == "-lc"
    assert probe["commands"][0][0][2]["capture_output"] is True
    assert all(probe["stopped"])
    assert probe["escape_status"] == 422
    assert probe["headers_registered"] is True


def test_deployed_code_cannot_regress_to_removed_sdk_methods():
    source = (DEPLOY / "app.py").read_text()
    assert "Sandbox.create" not in source
    assert ".run_command(" not in source
    assert "vercel_sandbox.create_sandbox(" in source
    assert "vercel_sandbox.resume_sandbox(" in source
    assert ".run_process(" in source


def test_hosted_wrapper_itself_never_imports_subprocess():
    source = (DEPLOY / "app.py").read_text()
    assert "import subprocess" not in source
    assert "subprocess." not in source


def test_deployment_pins_the_sdk_surface_it_implements():
    requirements = (DEPLOY / "requirements.txt").read_text().splitlines()
    assert "vercel==0.10.0" in requirements
    assert "vercel-sandbox==0.4.0" in requirements
