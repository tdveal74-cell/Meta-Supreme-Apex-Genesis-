"""Regression tests for the hosted DEVON browser Operator boundary.

The fake mirrors the shipped ``vercel-sandbox==0.4.0`` module API and reproduces
the production incidents where the Sandbox cwd is not itself a Git repository
and a source-provided Git worktree can arrive at detached HEAD. DEVON must
verify/bootstrap the Meta worktree and safely attach a clean detached checkout
to local ``main`` without discarding dirty workspace edits.
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
repo_ready = set()
repo_paths = {}
branches = {}
local_branches = {}
dirty_workspaces = set()
clone_targets = []

class FakeGitSource(dict):
    def __init__(self, *, url, revision=None):
        super().__init__(url=url, revision=revision)

class FakeResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

class FakeSandbox:
    def __init__(self, name, kwargs=None, cwd="/vercel"):
        self.name = name
        self.kwargs = kwargs or {}
        self.cwd = cwd
        self.commands = []
        self.stopped = False
        boxes.append(self)

    async def run_process(self, executable, args=None, **kwargs):
        argv = list(args or [])
        self.commands.append([executable, argv, dict(kwargs)])

        if executable == "pwd":
            return FakeResult(f"{self.cwd or '/vercel'}\n")

        if executable == "git" and len(argv) >= 3 and argv[0] == "-C":
            candidate = argv[1]
            command = argv[2:]
            repo_path = repo_paths.get(self.name)

            if command == ["rev-parse", "--show-toplevel"]:
                if self.name in repo_ready and candidate == repo_path:
                    return FakeResult(f"{repo_path}\n")
                return FakeResult(stderr="fatal: not a git repository\n", returncode=128)

            if candidate != repo_path or self.name not in repo_ready:
                return FakeResult(stderr="fatal: not a git repository\n", returncode=128)

            if command == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
                branch = branches.get(self.name)
                if branch:
                    return FakeResult(f"{branch}\n")
                return FakeResult(returncode=1)

            if command == ["status", "--porcelain"]:
                if self.name in dirty_workspaces:
                    return FakeResult(" M user-work.txt\n")
                return FakeResult("")

            if command == ["rev-parse", "--verify", "refs/remotes/origin/main"]:
                return FakeResult("deadbeef\n")

            if command == ["show-ref", "--verify", "--quiet", "refs/heads/main"]:
                exists = "main" in local_branches.get(self.name, set())
                return FakeResult(returncode=0 if exists else 1)

            if command == ["switch", "main"]:
                if "main" not in local_branches.get(self.name, set()):
                    return FakeResult(stderr="unknown branch main\n", returncode=1)
                branches[self.name] = "main"
                return FakeResult("Your branch is up to date with 'origin/main'.\n")

            if command == ["switch", "-c", "main", "--track", "origin/main"]:
                local_branches.setdefault(self.name, set()).add("main")
                branches[self.name] = "main"
                return FakeResult("branch 'main' set up to track 'origin/main'.\n")

            if command[:3] == ["fetch", "--depth", "1"]:
                return FakeResult("")

            return FakeResult()

        if executable == "find":
            if self.name in repo_ready:
                return FakeResult(f"{repo_paths[self.name]}/.git\n")
            return FakeResult("")

        if executable == "git" and argv and argv[0] == "clone":
            target = argv[-1]
            clone_targets.append(target)
            repo_ready.add(self.name)
            repo_paths[self.name] = target
            branches[self.name] = "main"
            local_branches.setdefault(self.name, set()).add("main")
            return FakeResult(stderr="Cloning into 'devon-meta'...\n")

        if executable == "bash":
            cwd = kwargs.get("cwd", "/vercel")
            return FakeResult(f"hello from sandbox\n__DEVON_CWD__={cwd}\n")

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

# Reproduce the first production incident: /vercel exists but is not a Git repo.
first = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/vercel"},
)
second = client.post(
    "/api/v1/operator-terminal/command",
    json={
        "command":"git status",
        "cwd":"/vercel/devon-meta",
        "workspace_id":"devon-workspace-001",
    },
)
escape = client.post(
    "/api/v1/operator-terminal/command",
    json={"command":"pwd", "cwd":"/etc", "workspace_id":"devon-workspace-001"},
)

# Reproduce the latest production screenshot: verified Git worktree, detached HEAD,
# clean tree. DEVON should create/track local main without resetting the worktree.
detached_box = FakeSandbox("detached-clean")
repo_ready.add("detached-clean")
repo_paths["detached-clean"] = "/vercel/Meta-Supreme-Apex-Genesis-"
branches["detached-clean"] = None
local_branches["detached-clean"] = set()
detached_attach = asyncio.run(
    hosted._ensure_main_branch(detached_box, "/vercel/Meta-Supreme-Apex-Genesis-")
)

# A dirty detached workspace is user state. Preserve it rather than switching.
dirty_box = FakeSandbox("detached-dirty")
repo_ready.add("detached-dirty")
repo_paths["detached-dirty"] = "/vercel/Meta-Supreme-Apex-Genesis-"
branches["detached-dirty"] = None
local_branches["detached-dirty"] = set()
dirty_workspaces.add("detached-dirty")
dirty_attach = asyncio.run(
    hosted._ensure_main_branch(dirty_box, "/vercel/Meta-Supreme-Apex-Genesis-")
)

fallback_box = FakeSandbox("fallback", cwd=None)
fallback_root = asyncio.run(hosted._sandbox_root(fallback_box))
legacy_alias = hosted._normalize_cwd(
    "/vercel/sandbox", "/vercel/devon-meta", "/vercel"
)
home_alias = hosted._normalize_cwd(
    "/home/vercel-sandbox", "/vercel/devon-meta", "/vercel"
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
    "clone_targets": clone_targets,
    "stopped": [s.stopped for s in boxes],
    "fallback_root": fallback_root,
    "fallback_commands": fallback_box.commands,
    "legacy_alias": legacy_alias,
    "home_alias": home_alias,
    "detached_attach": detached_attach,
    "detached_branch": branches["detached-clean"],
    "detached_commands": detached_box.commands,
    "dirty_attach": dirty_attach,
    "dirty_branch": branches["detached-dirty"],
    "dirty_commands": dirty_box.commands,
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


def test_browser_operator_reports_verified_git_worktree_contract():
    probe = _probe()
    status_body = probe["status_body"]
    assert status_body["mode"] == "isolated-vercel-sandbox"
    assert status_body["workspace"] == "verified Meta Git worktree"
    assert "git rev-parse" in status_body["workspace_discovery"]
    assert status_body["production_secrets_injected"] is False
    assert status_body["github_write_connected"] is False
    assert status_body["devon_core_executes"] is False
    assert status_body["sandbox_sdk_contract"] == "vercel-sandbox-0.4-module-api"


def test_non_git_sandbox_cwd_bootstraps_and_enters_meta_worktree():
    probe = _probe()
    assert probe["first_status"] == 200
    assert probe["first_body"]["stdout"] == "hello from sandbox\n"
    assert probe["first_body"]["sandbox_root"] == "/vercel"
    assert probe["first_body"]["workspace_root"] == "/vercel/devon-meta"
    assert probe["first_body"]["cwd"] == "/vercel/devon-meta"
    assert probe["first_body"]["repo_bootstrapped"] is True
    assert probe["first_body"]["branch"] == "main"
    assert probe["first_body"]["branch_attached"] is False
    assert probe["first_body"]["workspace_id"] == "devon-workspace-001"
    assert probe["clone_targets"] == ["/vercel/devon-meta"]

    first_box_commands = probe["commands"][0]
    clone = next(cmd for cmd in first_box_commands if cmd[0] == "git" and cmd[1][0] == "clone")
    assert clone[1][-1] == "/vercel/devon-meta"
    user_command = next(cmd for cmd in first_box_commands if cmd[0] == "bash")
    assert user_command[2]["cwd"] == "/vercel/devon-meta"


def test_resumed_workspace_reuses_verified_repo_for_git_status():
    probe = _probe()
    assert probe["second_status"] == 200
    assert probe["second_body"]["cwd"] == "/vercel/devon-meta"
    assert probe["second_body"]["workspace_root"] == "/vercel/devon-meta"
    assert probe["second_body"]["repo_bootstrapped"] is False
    assert probe["second_body"]["branch"] == "main"
    assert probe["resumed"][0] == {"name": "devon-workspace-001"}


def test_clean_detached_git_source_worktree_attaches_to_local_main():
    probe = _probe()
    assert probe["detached_attach"] == ["main", True]
    assert probe["detached_branch"] == "main"
    commands = probe["detached_commands"]
    assert any(
        cmd[0] == "git"
        and cmd[1][-5:] == ["switch", "-c", "main", "--track", "origin/main"]
        for cmd in commands
    )


def test_dirty_detached_worktree_is_preserved_without_switch_or_reset():
    probe = _probe()
    assert probe["dirty_attach"] == ["detached", False]
    assert probe["dirty_branch"] is None
    commands = probe["dirty_commands"]
    assert any(cmd[0] == "git" and cmd[1][-2:] == ["status", "--porcelain"] for cmd in commands)
    assert not any(cmd[0] == "git" and "switch" in cmd[1] for cmd in commands)


def test_old_browser_paths_are_aliases_for_verified_repo_root():
    probe = _probe()
    assert probe["legacy_alias"] == "/vercel/devon-meta"
    assert probe["home_alias"] == "/vercel/devon-meta"


def test_pwd_fallback_discovers_sandbox_base_when_sdk_cwd_is_missing():
    probe = _probe()
    assert probe["fallback_root"] == "/vercel"
    assert probe["fallback_commands"] == [["pwd", [], {"capture_output": True}]]


def test_working_directory_cannot_escape_verified_meta_worktree():
    probe = _probe()
    assert probe["escape_status"] == 422
    assert probe["headers_registered"] is True


def test_persistent_sandboxes_stop_after_normal_and_refused_commands():
    probe = _probe()
    assert all(probe["stopped"][:3])


def test_sandbox_creation_never_receives_production_secrets():
    probe = _probe()
    assert len(probe["created"]) == 1
    create = probe["created"][0]
    assert create["source"] == {
        "url": "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-.git",
        "revision": "main",
    }
    assert create["persistent"] is True
    assert "env" not in create
    assert "password" not in create
    assert "token" not in create


def test_deployed_code_cannot_equate_sandbox_cwd_with_git_repo_or_leave_clean_detached_head():
    source = (DEPLOY / "app.py").read_text()
    source_lines = [line.strip() for line in source.splitlines()]
    assert "Sandbox.create" not in source
    assert ".run_command(" not in source
    assert "vercel_sandbox.create_sandbox(" in source
    assert "vercel_sandbox.resume_sandbox(" in source
    assert "async def _repo_root(" in source
    assert "async def _ensure_main_branch(" in source
    assert '"rev-parse", "--show-toplevel"' in source
    assert '"symbolic-ref", "--quiet", "--short", "HEAD"' in source
    assert 'META_REPO_DIRNAME = "devon-meta"' in source_lines
    assert "repo_root, repo_bootstrapped = await _repo_root(" in source
    assert "branch, branch_attached = await _ensure_main_branch(" in source
    assert "cwd=cwd," in source_lines


def test_hosted_wrapper_itself_never_imports_subprocess():
    source = (DEPLOY / "app.py").read_text()
    assert "import subprocess" not in source
    assert "subprocess." not in source


def test_deployment_pins_the_sdk_surface_it_implements():
    requirements = (DEPLOY / "requirements.txt").read_text().splitlines()
    assert "vercel==0.10.0" in requirements
    assert "vercel-sandbox==0.4.0" in requirements
