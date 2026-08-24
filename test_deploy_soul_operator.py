"""Regression tests for the hosted DEVON browser Operator boundary.

The live Sandbox service is replaced with a fake that mirrors the public API
shipped by ``vercel-sandbox==0.4.0``. This intentionally does not provide the
old ``Sandbox.create``/``run_command`` methods, and it reports the Git workspace
through ``sandbox.cwd`` instead of assuming a host path.
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
import asyncio
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
    def __init__(self, stdout="hello from sandbox\n__DEVON_CWD__=/home/vercel-sandbox\n"):
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""

class FakeSandbox:
    def __init__(self, name, kwargs=None, cwd="/home/vercel-sandbox"):
        self.name = name
        self.kwargs = kwargs or {}
        self.cwd = cwd
        self.commands = []
        self.stopped = False
        boxes.append(self)
    async def run_process(self, executable, args=None, **kwargs):
        self.commands.append([executable, list(args or []), dict(kwargs)])
        if executable == "pwd":
            return FakeResult("/home/vercel-sandbox\n")
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
    # This is the stale path already cached by the production browser UI.
    json={"command":"pwd", "cwd":"/vercel/sandbox"},
)
second = client.post(
    "/api/v1/operator-terminal/command",
    json={
        "command":"git status",
        "cwd":"/home/vercel-sandbox",
        "workspace_id":"devon-workspace-001",
    },
)
escape = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/etc", "workspace_id":"devon-workspace-001"},
)

fallback_box = FakeSandbox("fallback", cwd=None)
fallback_root = asyncio.run(hosted._sandbox_root(fallback_box))

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
    "fallback_root": fallback_root,
    "fallback_commands": fallback_box.commands,
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


def test_browser_operator_reports_dynamic_workspace_contract():
    probe = _probe()
    status_body = probe["status_body"]
    assert status_body["mode"] == "isolated-vercel-sandbox"
    assert status_body["workspace"] == "auto-discovered from Sandbox cwd"
    assert status_body["workspace_discovery"] == "sandbox.cwd with pwd fallback"
    assert status_body["production_secrets_injected"] is False
    assert status_body["github_write_connected"] is False
    assert status_body["devon_core_executes"] is False
    assert status_body["sandbox_sdk_contract"] == "vercel-sandbox-0.4-module-api"


def test_legacy_browser_path_maps_to_runtime_reported_workspace():
    probe = _probe()
    assert probe["first_status"] == 200
    assert probe["first_body"]["stdout"] == "hello from sandbox\n"
    assert probe["first_body"]["cwd"] == "/home/vercel-sandbox"
    assert probe["first_body"]["workspace_root"] == "/home/vercel-sandbox"
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
    assert probe["resumed"][0] == {"name": "devon-workspace-001"}

    first_command = probe["commands"][0][0]
    assert first_command[0] == "bash"
    assert first_command[1][0] == "-lc"
    assert first_command[2]["cwd"] == "/home/vercel-sandbox"
    assert first_command[2]["capture_output"] is True


def test_pwd_fallback_discovers_workspace_when_sdk_cwd_is_missing():
    probe = _probe()
    assert probe["fallback_root"] == "/home/vercel-sandbox"
    assert probe["fallback_commands"] == [["pwd", [], {"capture_output": True}]]


def test_workspace_cannot_escape_runtime_reported_root():
    probe = _probe()
    assert probe["escape_status"] == 422
    assert probe["headers_registered"] is True


def test_persistent_sandboxes_stop_after_normal_commands():
    probe = _probe()
    # Fresh and resumed command boxes stop. The escape-path box also stops in
    # finally after the request is rejected. The fallback probe is standalone.
    assert all(probe["stopped"][:3])


def test_sandbox_creation_never_receives_production_secrets():
    probe = _probe()
    for create in probe["created"]:
        assert "env" not in create
        assert "password" not in create
        assert "token" not in create


def test_deployed_code_cannot_regress_to_removed_or_guessed_runtime_contracts():
    source = (DEPLOY / "app.py").read_text()
    source_lines = source.splitlines()
    assert "Sandbox.create" not in source
    assert ".run_command(" not in source
    assert "vercel_sandbox.create_sandbox(" in source
    assert "vercel_sandbox.resume_sandbox(" in source
    assert ".run_process(" in source
    assert 'WORKSPACE_ROOT = "/vercel/sandbox"' not in source_lines
    assert 'LEGACY_WORKSPACE_ROOT = "/vercel/sandbox"' in source_lines
    assert 'reported = getattr(sandbox, "cwd", None)' in source_lines
    assert "            cwd=cwd," in source_lines


def test_hosted_wrapper_itself_never_imports_subprocess():
    source = (DEPLOY / "app.py").read_text()
    assert "import subprocess" not in source
    assert "subprocess." not in source


def test_deployment_pins_the_sdk_surface_it_implements():
    requirements = (DEPLOY / "requirements.txt").read_text().splitlines()
    assert "vercel==0.10.0" in requirements
    assert "vercel-sandbox==0.4.0" in requirements
