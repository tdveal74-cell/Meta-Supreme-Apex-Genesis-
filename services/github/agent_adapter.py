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

READ_WINDOW_CHARS = 4_000
"""How much file content one github.read_file call returns.

Deliberately larger than the model's observation budget and far smaller than the
1 MB file limit. Bigger than the budget so a window is never the thing that
truncates; smaller than the file so `next_offset` is a real answer to "read the
rest" rather than a promise the tool cannot keep."""


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
                parameters=("repository",),
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
                parameters=("repository", "path", "ref", "offset"),
                description=(
                    "Read one UTF-8 file up to 1 MB from an allowlisted repository. "
                    "A long file is returned in windows: pass the next_offset from the "
                    "previous call as offset to continue reading where it stopped."
                ),
                risk=ToolRisk.READ,
                handler=self._read_file,
                reversible=True,
                blast_radius="read-only GitHub contents request in one allowlisted repository",
            )
        )
        registry.register(
            ToolSpec(
                name="github.pull_request",
                parameters=("repository", "number"),
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
                parameters=("repository", "branch", "base_ref"),
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
                parameters=("repository", "path", "content", "message", "branch", "sha"),
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
                parameters=("repository", "title", "head", "base", "body", "draft"),
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
                parameters=("repository", "number", "expected_head_sha", "merge_method"),
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
        try:
            offset = self._offset(arguments.get("offset"))
        except ValueError as exc:
            return ToolResult(False, error=str(exc))

        async def call() -> Dict[str, Any]:
            data = await self.client.read_file(
                repository,
                path,
                ref=str(ref).strip() if ref else None,
            )
            return self._window(data, offset)

        return await self._read_call(call)

    @staticmethod
    def _offset(raw: Any) -> int:
        """Where in the file to start reading. Rejects nonsense rather than clamping.

        Silently treating a bad offset as 0 would hand back the opening window
        again, which is the exact loop this argument exists to end.
        """
        if raw is None or raw == "":
            return 0
        try:
            offset = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"offset must be a whole number of characters, got {raw!r}") from None
        if offset < 0:
            raise ValueError(f"offset must not be negative, got {offset}")
        return offset

    @staticmethod
    def _window(data: Dict[str, Any], offset: int) -> Dict[str, Any]:
        """Return one readable slice of a file, and say where the next one starts.

        The window is smaller than the file limit on purpose. The model reads a
        bounded prefix of any observation, so returning 200 KB of JSON spends the
        whole budget on content it will never see and leaves it unable to tell a
        long file from a finished one. A window plus `next_offset` is the same
        information in a form it can act on.
        """
        content = data.get("content")
        if not isinstance(content, str):
            return data
        total = len(content)
        windowed = dict(data)
        windowed["content"] = content[offset : offset + READ_WINDOW_CHARS]
        windowed["offset"] = offset
        windowed["total_characters"] = total
        end = min(offset + READ_WINDOW_CHARS, total)
        if end < total:
            windowed["next_offset"] = end
            windowed["remaining_characters"] = total - end
        else:
            windowed["next_offset"] = None
            windowed["remaining_characters"] = 0
        return windowed

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

        # Prefer a stable provider receipt id so durable effect receipts can
        # bind to the exact GitHub object that was created or mutated.
        receipt_id = ""
        for candidate in (
            data.get("sha"),
            (data.get("commit") or {}).get("sha") if isinstance(data.get("commit"), dict) else None,
            (data.get("object") or {}).get("sha") if isinstance(data.get("object"), dict) else None,
            data.get("html_url"),
            data.get("url"),
            data.get("number"),
        ):
            if candidate is not None and str(candidate).strip():
                receipt_id = str(candidate).strip()
                break
        if receipt_id:
            metadata["provider_receipt_id"] = receipt_id

        return ToolResult(
            True,
            output=rendered,
            metadata=metadata,
        )
