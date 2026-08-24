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
                    "DEVON approval. A full expected_head_sha is required so the ruling is "
                    "pinned to the exact code revision."
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
        try:
            repository = self._repo(arguments)
        except GitHubRESTError as exc:
            return ToolResult(False, error=str(exc))
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
        try:
            repository = self._repo(arguments)
            number = int(arguments.get("number"))
        except (GitHubRESTError, TypeError, ValueError) as exc:
            return ToolResult(False, error=str(exc))
        return await self._read_call(lambda: self.client.pull_request(repository, number))

    async def _create_branch(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments, tool_name="github.create_branch")
        if isinstance(args, ToolResult):
            return args
        try:
            repository = self._repo(args)
        except GitHubRESTError as exc:
            return ToolResult(False, error=str(exc))
        branch = str(args.get("branch") or "").strip()
        base_ref = str(args.get("base_ref") or "main").strip()
        return await self._write_call(
            lambda: self.client.create_branch(repository, branch, base_ref=base_ref)
        )

    async def _write_file(self, arguments: Dict[str, Any]) -> ToolResult:
        args = self._approved_arguments(arguments, tool_name="github.write_file")
        if isinstance(args, ToolResult):
            return args
        try:
            repository = self._repo(args)
        except GitHubRESTError as exc:
            return ToolResult(False, error=str(exc))
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
        args = self._approved_arguments(arguments, tool_name="github.create_pull_request")
        if isinstance(args, ToolResult):
            return args
        try:
            repository = self._repo(args)
        except GitHubRESTError as exc:
            return ToolResult(False, error=str(exc))
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
        args = self._approved_arguments(arguments, tool_name="github.merge_pull_request")
        if isinstance(args, ToolResult):
            return args
        try:
            repository = self._repo(args)
            number = int(args.get("number"))
        except (GitHubRESTError, TypeError, ValueError) as exc:
            return ToolResult(False, error=str(exc))
        expected = str(args.get("expected_head_sha") or "").strip()
        if not expected:
            return ToolResult(
                False,
                error="expected_head_sha is required for every GitHub pull request merge",
            )
        return await self._write_call(
            lambda: self.client.merge_pull_request(
                repository,
                number,
                expected_head_sha=expected,
                merge_method=str(args.get("merge_method") or "merge"),
            )
        )

    def _approved_arguments(
        self,
        arguments: Dict[str, Any],
        *,
        tool_name: str,
    ) -> Dict[str, Any] | ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        try:
            require_approved_runtime_binding(
                self.approvals,
                metadata,
                tool_name=tool_name,
                arguments=args,
            )
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

        metadata: Dict[str, Any] = {"truncated": truncated}
        for key in (
            "repository",
            "path",
            "ref",
            "sha",
            "size",
            "html_url",
            "number",
            "url",
            "merged",
            "message",
        ):
            if key in data:
                metadata[key] = data[key]
        for key in ("object", "commit", "content"):
            nested = data.get(key)
            if isinstance(nested, dict) and nested.get("sha"):
                metadata[f"{key}_sha"] = nested.get("sha")
        metadata["response_keys"] = sorted(str(key) for key in data.keys())[:100]
        return ToolResult(
            True,
            output=rendered,
            metadata=metadata,
        )
