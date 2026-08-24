"""Regression for Vercel shallow detached checkout without a tracked origin/main."""

from __future__ import annotations

import asyncio
import importlib
import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"


class Result:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class Sandbox:
    """Fake that reproduces GitSource's missing remote-tracking metadata."""

    def __init__(self, *, dirty: bool = False):
        self.dirty = dirty
        self.branch: str | None = None
        self.remote_ref = False
        self.fetch_tracking = False
        self.local_main = False
        self.commands: list[list[object]] = []

    async def run_process(self, executable, args=None, **kwargs):
        argv = list(args or [])
        self.commands.append([executable, argv, dict(kwargs)])
        if executable != "git" or len(argv) < 3 or argv[0] != "-C":
            return Result()

        command = argv[2:]
        if command == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
            return Result(f"{self.branch}\n") if self.branch else Result(returncode=1)
        if command == ["status", "--porcelain"]:
            return Result(" M user-work.txt\n" if self.dirty else "")
        if command == ["rev-parse", "HEAD"]:
            return Result("ad5651ef9ca4e58ba19879ab3a00b034b5479b5a\n")
        if command == [
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/devon/recovery-ad5651ef9ca4",
        ]:
            return Result(returncode=1)
        if command == [
            "branch",
            "devon/recovery-ad5651ef9ca4",
            "ad5651ef9ca4e58ba19879ab3a00b034b5479b5a",
        ]:
            return Result()
        if command == [
            "config",
            "remote.origin.fetch",
            "+refs/heads/main:refs/remotes/origin/main",
        ]:
            self.fetch_tracking = True
            return Result()
        if command == [
            "fetch",
            "--depth",
            "1",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ]:
            self.remote_ref = True
            return Result()
        if command == ["rev-parse", "--verify", "refs/remotes/origin/main"]:
            return Result("feedface\n") if self.remote_ref else Result(returncode=1)
        if command == ["show-ref", "--verify", "--quiet", "refs/heads/main"]:
            return Result(returncode=0 if self.local_main else 1)
        if command == ["switch", "-c", "main", "refs/remotes/origin/main"]:
            if not (self.fetch_tracking and self.remote_ref):
                return Result(stderr="origin/main is not a branch\n", returncode=128)
            self.local_main = True
            self.branch = "main"
            return Result()
        if command in (
            ["config", "branch.main.remote", "origin"],
            ["config", "branch.main.merge", "refs/heads/main"],
        ):
            return Result()
        return Result()


def _hosted():
    os.environ["CONSOLE_TOKEN"] = "test-console-token"
    if str(DEPLOY) not in sys.path:
        sys.path.insert(0, str(DEPLOY))

    vercel = types.ModuleType("vercel")
    vercel.__path__ = []
    sandbox_mod = types.ModuleType("vercel.sandbox")

    async def _noop(**kwargs):
        return None

    sandbox_mod.create_sandbox = _noop
    sandbox_mod.resume_sandbox = _noop
    sandbox_mod.GitSource = type(
        "GitSource",
        (),
        {"__init__": lambda self, **kwargs: None},
    )
    headers_mod = types.ModuleType("vercel.headers")
    headers_mod.set_headers = lambda headers: None
    vercel.sandbox = sandbox_mod
    sys.modules["vercel"] = vercel
    sys.modules["vercel.sandbox"] = sandbox_mod
    sys.modules["vercel.headers"] = headers_mod
    sys.modules.pop("app", None)
    sys.modules.pop("app_legacy", None)
    return importlib.import_module("app")


def test_shallow_detached_checkout_builds_real_tracking_ref_before_main():
    hosted = _hosted()
    box = Sandbox()
    result = asyncio.run(
        hosted._ensure_main_branch(box, "/vercel/Meta-Supreme-Apex-Genesis-")
    )
    assert result == ("main", True)
    assert box.branch == "main"

    commands = [entry[1][2:] for entry in box.commands if entry[0] == "git"]
    assert [
        "config",
        "remote.origin.fetch",
        "+refs/heads/main:refs/remotes/origin/main",
    ] in commands
    assert [
        "fetch",
        "--depth",
        "1",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    ] in commands
    assert ["switch", "-c", "main", "refs/remotes/origin/main"] in commands
    assert ["switch", "-c", "main", "--track", "origin/main"] not in commands
    assert [
        "branch",
        "devon/recovery-ad5651ef9ca4",
        "ad5651ef9ca4e58ba19879ab3a00b034b5479b5a",
    ] in commands


def test_dirty_detached_checkout_is_preserved_before_fetch_or_switch():
    hosted = _hosted()
    box = Sandbox(dirty=True)
    result = asyncio.run(
        hosted._ensure_main_branch(box, "/vercel/Meta-Supreme-Apex-Genesis-")
    )
    assert result == ("detached", False)
    commands = [entry[1][2:] for entry in box.commands if entry[0] == "git"]
    assert not any(command and command[0] == "fetch" for command in commands)
    assert not any(command and command[0] == "switch" for command in commands)
