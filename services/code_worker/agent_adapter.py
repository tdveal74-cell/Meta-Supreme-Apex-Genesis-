"""Code worker capability adapter for DEVON Agent Runtime.

Ruled by Tee 2026-10-24: DEVON writes code through the Claude Agent SDK on the
VPS. `code.task` submits one approved job and returns its id at once, because a
job runs for minutes; `code.status` reads the job back, and its draft pull
request link is the receipt. `code.task` is HIGH_IMPACT: the agent runs shell
commands on the worker box and pushes a branch, even though nothing it does can
reach the base branch without a human.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.code_worker.client import CodeWorkerClient, CodeWorkerError
from services.devon.approval import ApprovalQueue

TASK_TOOL = "code.task"
STATUS_TOOL = "code.status"
MIN_TASK_CHARS = 20
MAX_TASK_CHARS = 20_000


class CodeWorkerCapabilityAdapter:
    name = "code"

    def __init__(self, client: CodeWorkerClient, approvals: ApprovalQueue) -> None:
        self.client = client
        self.approvals = approvals

    def _scope(self) -> str:
        repos = self.client.allowed_repos
        if not repos:
            return " No repository is allowlisted, so every job is refused until DEVON_CODE_WORKER_REPOS is set."
        return " Allowlisted repositories: " + ", ".join(repos) + "."

    def register(self, registry: ToolRegistry) -> None:
        scope = self._scope()
        registry.register(
            ToolSpec(
                name=TASK_TOOL,
                parameters=("repository", "task", "base_ref", "test_command", "max_turns", "max_budget_usd"),
                description=(
                    "Hand one coding job to DEVON's code worker after high-impact DEVON "
                    "approval. A Claude Agent SDK session clones the repository onto a "
                    "new branch, makes the change with a test writer and a reviewer as "
                    "subagents, the worker runs test_command itself, and opens a DRAFT "
                    "pull request. Returns the job id at once; read it with code.status. "
                    "max_budget_usd caps the spend (default 5, at most 50)." + scope
                ),
                risk=ToolRisk.HIGH_IMPACT,
                handler=self._task,
                reversible=False,
                blast_radius=(
                    "one new branch and one draft pull request in one allowlisted repository, "
                    "and shell commands on the code worker box"
                ),
            )
        )
        registry.register(
            ToolSpec(
                name=STATUS_TOOL,
                parameters=("job_id",),
                description="Read one code worker job: state, tests, agent result and the draft pull request link.",
                risk=ToolRisk.READ,
                handler=self._status,
                reversible=True,
                blast_radius="read-only code worker job record",
            )
        )

    async def _task(self, arguments: Dict[str, Any]) -> ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        # Refusals that cost nothing come before the approval is spent.
        if not self.client.configured:
            return ToolResult(
                False,
                error=(
                    "code worker is not configured. Set DEVON_CODE_WORKER_URL, DEVON_CODE_WORKER_KEY "
                    "and DEVON_CODE_WORKER_REPOS. Nothing ran and the approval was not spent."
                ),
            )
        try:
            self.client.require_repository(str(args.get("repository") or ""))
        except CodeWorkerError as exc:
            return ToolResult(False, error=f"{exc}. Nothing ran and the approval was not spent.")
        task = str(args.get("task") or "").strip()
        if not MIN_TASK_CHARS <= len(task) <= MAX_TASK_CHARS:
            return ToolResult(
                False,
                error=f"task must be {MIN_TASK_CHARS} to {MAX_TASK_CHARS} characters. Nothing ran.",
            )
        try:
            request_id, binding = require_approved_runtime_binding(
                self.approvals, metadata, tool_name=TASK_TOOL, arguments=args
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        job = {
            # The binding names this exact approved step, so a retry of the same
            # step reaches the worker as the same job and runs once.
            "job_id": f"DEVON-{binding[:24].upper()}",
            "repository": args.get("repository"),
            "task": task,
            "base_ref": args.get("base_ref") or "main",
            "test_command": args.get("test_command") or "",
            "max_turns": args.get("max_turns") or 60,
            "max_budget_usd": args.get("max_budget_usd") or 5,
            "requested_by": "DEVON Agent Runtime",
            "approval_id": request_id,
        }
        try:
            record = await self.client.submit(job)
        except CodeWorkerError as exc:
            return ToolResult(False, error=str(exc))
        job_id = str((record.get("job") or {}).get("job_id") or job["job_id"])
        return ToolResult(
            True,
            output=json.dumps(
                {
                    "job_id": job_id,
                    "state": record.get("state"),
                    "branch": record.get("branch"),
                    "next": f"Read it with code.status job_id={job_id}. The draft pull request link is the receipt.",
                },
                sort_keys=True,
            ),
            metadata={"job_id": job_id, "state": record.get("state"), "provider_receipt_id": job_id},
        )

    async def _status(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            record = await self.client.status(str(arguments.get("job_id") or ""))
        except CodeWorkerError as exc:
            return ToolResult(False, error=str(exc))
        state = str(record.get("state") or "")
        pr = record.get("pull_request") or {}
        summary = {
            "job_id": (record.get("job") or {}).get("job_id"),
            "state": state,
            "branch": record.get("branch"),
            "commits": record.get("commits"),
            "tests": {k: v for k, v in (record.get("tests") or {}).items() if k != "tail"},
            "tests_tail": str((record.get("tests") or {}).get("tail") or "")[-2_000:],
            "agent": record.get("agent"),
            "pull_request": pr,
            "error": record.get("error"),
        }
        ok = state not in ("failed",)
        return ToolResult(
            ok,
            output=json.dumps(summary, sort_keys=True, default=str),
            error="" if ok else f"code job failed: {record.get('error')}",
            metadata={
                "state": state,
                "url": pr.get("url"),
                "provider_receipt_id": str(pr.get("url") or summary["job_id"] or ""),
            },
        )
