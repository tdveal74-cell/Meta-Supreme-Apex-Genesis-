"""GitHub capability adapter for DEVON Agent Runtime."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue
from services.github.client import GitHubRESTClient, GitHubRESTError

MAX_OUTPUT_CHARS = 200_000


class GitHubCapabilityAdapter:
    """Expose an explicit allowlisted subset of GitHub REST to the agent loop."""

    name = "github"

    def __init__(self, client: GitHubRESTClient, approvals: ApprovalQueue) -> None:
        self.client = client
        self.approvals = approvals

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="github.repo_status",
                description="Read metadata for one allowlisted GitHub repository.",
                risk=ToolRisk.READ,
                handler=self._repo_status,
                reversible=True,
                blast_radius="read-only GitHub API request in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.read_file",
                description="Read one UTF-8 file up to 1 MB from an allowlisted repository.",
                risk=ToolRisk.READ,
                handler=self._read_file,
                reversible=True,
                blast_radius="read-only GitHub contents request in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.pull_request",
                description="Read one pull request from an allowlisted repository.",
                risk=ToolRisk.READ,
                handler=self._pull_request,
                reversible=True,
                blast_radius="read-only GitHub pull request request in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.create_branch",
                description="Create one branch in an allowlisted repository after DEVON approval.",
                risk=ToolRisk.WRITE,
                handler=self._create_branch,
                reversible=False,
                blast_radius="one new Git branch in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.write_file",
                description=(
                    "Create or replace one repository file up to 1 MB after DEVON approval. "
                    "Existing files require their current blob SHA."
                ),
                risk=ToolRisk.HIGH_IMPACT,
                handler=self._write_file,
                reversible=False,
                blast_radius="one commit affecting one file in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.create_pull_request",
                description="Open one pull request in an allowlisted repository after DEVON approval.",
                risk=ToolRisk.WRITE,
                handler=self._create_pull_request,
                reversible=False,
                blast_radius="one pull request in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.merge_pull_request",
                description=(
                    "Merge one pull request in an allowlisted repository after high-impact "
                    "DEVON approval. expected_head_sha should be supplied to prevent stale merges."
                ),
                risk=ToolRisk.HIGH_IMPACT,
                handler=self._merge_pull_request,
                reversible=False,
                blast_radius="target branch history and repository state for one pull request",
            )
        )

    async def _repo_status(self, arguments: Dict[str, Any]) -> ToolResult:
        return await self._read_call(
            lambda: self.client.repo_status(self._repo(arguments)),
        )

    async def _read_file(self, arguments: Dict[str, Any]) -> ToolResult:
        repository = self._repo(arguments)
        path = str(arguments.get("path") or "").strip()
        ref = arguments.get("ref")
        return await self._read_call(
            lambda: self.client.read_file(
                repository,
                path,
                ref=str(ref).strip() if ref else None,
            )
        )

    async def _pull_request(self, arguments: Dict[str, Any]) -> ToolResult:
        repository = self._repo(arguments)
        try:
            number = int(arguments.get("number"))
        except (TypeError, ValueError) as exc:
            return ToolResult(False, error="pull request number must be an integer")
        return await self._read_call(lambda: self.client.pull_request(repository, number))

    async def _create_branch(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments)
        if isinstance(args, ToolResult):
            return args
        repository = self._repo(args)
        branch = str(args.get("branch") or "").strip()
        base_ref = str(args.get("base_ref") or "main").strip()
        return await self._write_call(
            lambda: self.client.create_branch(repository, branch, base_ref=base_ref)
        )

    async def _write_file(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments)
        if isinstance(args, ToolResult):
            return args
        repository = self._repo(args)
        sha = args.get("sha")
        return await self._write_call(
            lambda: self.client.write_file(
                repository,
                str(args.get("path") or ""),
                content=str(args.get("content") or ""),
                message=str(args.get("message") or ""),
                branch=str(args.get("branch") or ""),
                sha=str(sha).strip() if sha else None,
            )
        )

    async def _create_pull_request(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments)
        if isinstance(args, ToolResult):
            return args
        repository = self._repo(args)
        return await self._write_call(
            lambda: self.client.create_pull_request(
                repository,
                title=str(args.get("title") or ""),
                head=str(args.get("head") or ""),
                base=str(args.get("base") or "main"),
                body=str(args.get("body") or ""),
                draft=bool(args.get("draft", False)),
            )
        )

    async def _merge_pull_request(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments)
        if isinstance(args, ToolResult):
            return args
        repository = self._repo(args)
        try:
            number = int(args.get("number"))
        except (TypeError, ValueError):
            return ToolResult(False, error="pull request number must be an integer")
        expected = args.get("expected_head_sha")
        return await self._write_call(
            lambda: self.client.merge_pull_request(
                repository,
                number,
                merge_method=str(args.get("merge_method") or "merge"),
                expected_head_sha=str(expected).strip() if expected else None,
            )
        )

    def _approved_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any] | ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        try:
            require_approved_runtime_binding(self.approvals, metadata)
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        return args

    def _repo(self, arguments: Dict[str, Any]) -> str:
        repository = str(arguments.get("repository") or "").strip()
        return self.client.require_repository(repository)

    async def _read_call(
        self,
        call: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> ToolResult:
        if not self.client.configured:
            return self._not_configured()
        try:
            data = await call()
        except (GitHubRESTError, ValueError, TypeError) as exc:
            return ToolResult(False, error=str(exc))
        return self._result(data)

    async def _write_call(
        self,
        call: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> ToolResult:
        if not self.client.configured:
            return self._not_configured()
        try:
            data = await call()
        except (GitHubRESTError, ValueError, TypeError) as exc:
            return ToolResult(False, error=str(exc))
        return self._result(data)

    @staticmethod
    def _not_configured() -> ToolResult:
        return ToolResult(
            False,
            error=(
                "GitHub adapter is not configured. Set DEVON_GITHUB_TOKEN and "
                "DEVON_GITHUB_ALLOWED_REPOS."
            ),
        )

    @staticmethod
    def _result(data: Dict[str, Any]) -> ToolResult:
        rendered = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        truncated = len(rendered) > MAX_OUTPUT_CHARS
        if truncated:
            rendered = rendered[:MAX_OUTPUT_CHARS] + "\n[DEVON GitHub output truncated]\n"
        return ToolResult(
            True,
            output=rendered,
            metadata={"response": data, "truncated": truncated},
        )
