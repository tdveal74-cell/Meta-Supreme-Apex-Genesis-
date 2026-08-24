"""DEVON Operator Bridge.

This module is intentionally outside ``services.devon``. DEVON remains a
network- and subprocess-free planner/gatekeeper. The bridge is the separate
capability boundary that may execute an approved local process.

Security defaults:
- disabled unless DEVON_OPERATOR_ENABLED=1
- every command endpoint requires DEVON_OPERATOR_KEY
- no shell expansion for direct commands (argv execution only)
- working directory is confined to DEVON_OPERATOR_ROOT
- obvious host-destruction commands are refused
- unknown or mutating commands require DEVON approval
- subprocesses run with a timeout and bounded captured output
"""

from __future__ import annotations

import hmac
import os
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from services.agent_runtime.governance import require_approved_runtime_binding
from services.devon.approval import ApprovalQueue, ApprovalState

MAX_COMMAND_CHARS = 4000
MAX_OUTPUT_CHARS = 1_000_000
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 300


class OperatorError(ValueError):
    """A command cannot be planned or executed safely."""


class Risk(str, Enum):
    READ = "read"
    WRITE = "write"
    BLOCKED = "blocked"


READ_ONLY_BINARIES = {
    "pwd", "ls", "cat", "head", "tail", "wc", "stat", "uname", "whoami",
    "id", "date", "df", "du", "ps", "which", "whereis",
}
READ_ONLY_GIT = {
    "status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree",
    "describe", "shortlog",
}
READ_ONLY_DOCKER = {"ps", "images", "logs", "inspect", "stats", "version", "info"}
READ_ONLY_DOCKER_COMPOSE = {"ps", "logs", "config", "images", "top", "ls"}
BLOCKED_BINARIES = {
    "sudo", "su", "doas", "shutdown", "reboot", "poweroff", "halt", "mkfs",
    "fdisk", "parted",
}
BLOCKED_RM_TARGETS = {
    "/", "/*", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib64",
    "/proc", "/root", "/run", "/sbin", "/sys", "/usr", "/var",
}


@dataclass(frozen=True)
class CommandPlan:
    command: str
    argv: tuple[str, ...]
    cwd: str
    risk: Risk
    approval_required: bool
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "command": self.command,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "risk": self.risk.value,
            "approval_required": self.approval_required,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class PendingExecution:
    request_id: str
    plan: CommandPlan


class OperatorBridge:
    """Plan and execute commands while preserving DEVON's capability boundary."""

    def __init__(
        self,
        *,
        root: Optional[Path] = None,
        enabled: Optional[bool] = None,
        operator_key: Optional[str] = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        configured_root = root or Path(os.getenv("DEVON_OPERATOR_ROOT", str(repo_root)))
        self.root = configured_root.expanduser().resolve()
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("DEVON_OPERATOR_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self._operator_key = (
            operator_key if operator_key is not None else os.getenv("DEVON_OPERATOR_KEY", "")
        )
        self._pending: Dict[str, PendingExecution] = {}

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self._operator_key)

    def authenticate(self, supplied_key: Optional[str]) -> None:
        if not self.enabled:
            raise OperatorError("operator bridge is disabled")
        if not self._operator_key:
            raise OperatorError("DEVON_OPERATOR_KEY is not configured")
        candidate = supplied_key or ""
        if not hmac.compare_digest(self._operator_key, candidate):
            raise OperatorError("operator key does not match")

    def resolve_cwd(self, cwd: Optional[str]) -> Path:
        if not cwd:
            target = self.root
        else:
            candidate = Path(cwd).expanduser()
            target = candidate if candidate.is_absolute() else self.root / candidate
            target = target.resolve()

        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise OperatorError(f"working directory escapes operator root: {target}") from exc

        if not target.exists():
            raise OperatorError(f"working directory does not exist: {target}")
        if not target.is_dir():
            raise OperatorError(f"working directory is not a directory: {target}")
        return target

    def plan(self, command: str, cwd: Optional[str] = None) -> CommandPlan:
        raw = (command or "").strip()
        if not raw:
            raise OperatorError("command is empty")
        if len(raw) > MAX_COMMAND_CHARS:
            raise OperatorError(f"command exceeds {MAX_COMMAND_CHARS} characters")

        try:
            argv = tuple(shlex.split(raw, posix=True))
        except ValueError as exc:
            raise OperatorError(f"command could not be parsed: {exc}") from exc

        if not argv:
            raise OperatorError("command is empty after parsing")

        resolved_cwd = self.resolve_cwd(cwd)
        risk, reason = self._classify(argv)
        return CommandPlan(
            command=raw,
            argv=argv,
            cwd=str(resolved_cwd),
            risk=risk,
            approval_required=risk is Risk.WRITE,
            reason=reason,
        )

    def request(self, plan: CommandPlan, approvals: ApprovalQueue) -> tuple[str, str]:
        if plan.risk is Risk.BLOCKED:
            raise OperatorError(plan.reason)
        if not plan.approval_required:
            raise OperatorError("read-only command does not require an approval request")

        record, token = approvals.request(
            title="DEVON Operator Terminal command",
            what_happens=f"Run `{plan.command}` in `{plan.cwd}` on the operator host.",
            requested_by="DEVON Operator Bridge",
            area="Systems",
            reversible=False,
            blast_radius="local operator host and files reachable by the current process user",
        )
        self._pending[record.request_id] = PendingExecution(record.request_id, plan)
        return record.request_id, token

    def execute_read(
        self, plan: CommandPlan, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    ) -> ExecutionResult:
        if plan.risk is not Risk.READ:
            raise OperatorError("command is not read-only")
        return self._run(plan, timeout_seconds)

    def execute_approved(
        self,
        request_id: str,
        approvals: ApprovalQueue,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult:
        pending = self._pending.get(request_id)
        if pending is None:
            raise OperatorError("no pending operator command with that request id")

        record = approvals.get(request_id)
        if record is None:
            raise OperatorError("approval request no longer exists")
        if record.state is not ApprovalState.APPROVED:
            raise OperatorError(f"approval state is {record.state.value}, not approved")

        self._pending.pop(request_id, None)
        return self._run(pending.plan, timeout_seconds)

    def execute_runtime_approved(
        self,
        *,
        arguments: Dict[str, object],
        approval_metadata: object,
        approvals: ApprovalQueue,
    ) -> ExecutionResult:
        """Execute only the exact Operator arguments approved by DEVON.

        The bridge does not trust a supplied binding string. It asks the shared
        governance helper to recompute the binding from the actual arguments it
        is about to interpret, then builds the command plan from those same
        arguments before crossing the process boundary.
        """
        args = dict(arguments)
        try:
            require_approved_runtime_binding(
                approvals,
                approval_metadata,
                tool_name="operator.command",
                arguments=args,
            )
        except ValueError as exc:
            raise OperatorError(str(exc)) from exc

        command = str(args.get("command") or "").strip()
        cwd = args.get("cwd")
        timeout = int(args.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        plan = self.plan(command, str(cwd) if cwd else None)
        if plan.risk is Risk.BLOCKED:
            raise OperatorError(plan.reason)
        if plan.risk is Risk.READ:
            raise OperatorError(
                "operator.command is for effectful work; use operator.read for reads"
            )
        return self._run(plan, timeout)

    def _run(self, plan: CommandPlan, timeout_seconds: int) -> ExecutionResult:
        timeout = max(1, min(int(timeout_seconds), MAX_TIMEOUT_SECONDS))
        try:
            completed = subprocess.run(
                list(plan.argv),
                cwd=plan.cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
            stdout, out_truncated = self._limit(completed.stdout or "")
            stderr, err_truncated = self._limit(completed.stderr or "")
            return ExecutionResult(
                command=plan.command,
                cwd=plan.cwd,
                returncode=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                truncated=out_truncated or err_truncated,
            )
        except FileNotFoundError as exc:
            raise OperatorError(f"executable not found: {plan.argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_timeout_output(exc.stdout)
            stderr = self._coerce_timeout_output(exc.stderr)
            stdout, out_truncated = self._limit(stdout)
            stderr, err_truncated = self._limit(stderr)
            return ExecutionResult(
                command=plan.command,
                cwd=plan.cwd,
                returncode=124,
                stdout=stdout,
                stderr=stderr or f"command exceeded {timeout} seconds",
                timed_out=True,
                truncated=out_truncated or err_truncated,
            )

    @staticmethod
    def _coerce_timeout_output(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def _limit(value: str) -> tuple[str, bool]:
        if len(value) <= MAX_OUTPUT_CHARS:
            return value, False
        return value[:MAX_OUTPUT_CHARS] + "\n[DEVON output truncated]\n", True

    def _classify(self, argv: tuple[str, ...]) -> tuple[Risk, str]:
        executable = Path(argv[0]).name.lower()

        if executable in BLOCKED_BINARIES:
            return Risk.BLOCKED, f"`{executable}` is blocked at the operator boundary"

        if executable == "rm" and self._rm_targets_host_root(argv[1:]):
            return Risk.BLOCKED, "refusing an rm command aimed at a protected host root path"

        if executable in READ_ONLY_BINARIES:
            return Risk.READ, f"`{executable}` is in the read-only command set"

        if executable == "git":
            subcommand = self._first_non_option(argv[1:])
            if subcommand in READ_ONLY_GIT:
                return Risk.READ, f"`git {subcommand}` is read-only"
            return Risk.WRITE, "git command may change repository or remote state"

        if executable == "docker":
            if len(argv) >= 2 and argv[1] == "compose":
                subcommand = self._first_non_option(argv[2:])
                if subcommand in READ_ONLY_DOCKER_COMPOSE:
                    return Risk.READ, f"`docker compose {subcommand}` is read-only"
                return Risk.WRITE, "docker compose command may change container state"

            subcommand = self._first_non_option(argv[1:])
            if subcommand in READ_ONLY_DOCKER:
                return Risk.READ, f"`docker {subcommand}` is read-only"
            return Risk.WRITE, "docker command may change host or container state"

        return Risk.WRITE, "unknown or potentially mutating command fails closed to human approval"

    @staticmethod
    def _first_non_option(args: tuple[str, ...]) -> str:
        for arg in args:
            if not arg.startswith("-"):
                return arg.lower()
        return ""

    @staticmethod
    def _rm_targets_host_root(args: tuple[str, ...]) -> bool:
        for arg in args:
            if arg.startswith("-"):
                continue
            normalized = os.path.normpath(arg)
            if normalized in BLOCKED_RM_TARGETS:
                return True
        return False
