"""Small allowlisted GitHub REST client for DEVON capability adapters.

The token is configuration, never a tool argument or output. Repository access
fails closed unless the exact owner/name is present in DEVON_GITHUB_ALLOWED_REPOS.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, Iterable, Optional
from urllib.parse import quote

import httpx

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_FILE_BYTES = 1_000_000
MAX_ERROR_CHARS = 2_000


class GitHubRESTError(ValueError):
    """A GitHub request cannot proceed safely or the remote API refused it."""


class GitHubRESTClient:
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        allowed_repos: Optional[Iterable[str]] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.token = (
            token
            if token is not None
            else os.getenv("DEVON_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
        ).strip()
        raw_allowed = (
            list(allowed_repos)
            if allowed_repos is not None
            else [
                item.strip()
                for item in os.getenv("DEVON_GITHUB_ALLOWED_REPOS", "").split(",")
                if item.strip()
            ]
        )
        self.allowed_repos = {self._validate_repository_name(item) for item in raw_allowed}
        self.base_url = (
            base_url or os.getenv("DEVON_GITHUB_API_URL") or "https://api.github.com"
        ).rstrip("/")
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.token and self.allowed_repos)

    @property
    def allowed_repositories(self) -> list[str]:
        return sorted(self.allowed_repos)

    def require_repository(self, repository: str) -> str:
        normalized = self._validate_repository_name(repository)
        if normalized not in self.allowed_repos:
            raise GitHubRESTError(f"repository is not allowlisted for DEVON: {normalized}")
        return normalized

    async def repo_status(self, repository: str) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        return await self._request("GET", f"/repos/{repo}")

    async def read_file(
        self,
        repository: str,
        path: str,
        *,
        ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        clean_path = self._clean_repo_path(path)
        params = {"ref": ref} if ref else None
        data = await self._request(
            "GET",
            f"/repos/{repo}/contents/{quote(clean_path, safe='/')}",
            params=params,
        )
        if not isinstance(data, dict) or data.get("type") != "file":
            raise GitHubRESTError("requested GitHub contents path is not a file")
        size = int(data.get("size") or 0)
        if size > MAX_FILE_BYTES:
            raise GitHubRESTError(
                f"GitHub file exceeds DEVON read limit of {MAX_FILE_BYTES} bytes"
            )
        encoded = str(data.get("content") or "").replace("\n", "")
        try:
            raw = base64.b64decode(encoded, validate=False)
        except Exception as exc:
            raise GitHubRESTError("GitHub file content is not valid base64") from exc
        if len(raw) > MAX_FILE_BYTES:
            raise GitHubRESTError(
                f"decoded GitHub file exceeds DEVON read limit of {MAX_FILE_BYTES} bytes"
            )
        return {
            "repository": repo,
            "path": clean_path,
            "ref": ref,
            "sha": data.get("sha"),
            "size": len(raw),
            "content": raw.decode("utf-8", errors="replace"),
            "html_url": data.get("html_url"),
        }

    async def pull_request(self, repository: str, number: int) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        return await self._request("GET", f"/repos/{repo}/pulls/{int(number)}")

    async def create_branch(
        self,
        repository: str,
        branch: str,
        *,
        base_ref: str = "main",
    ) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        clean_branch = self._clean_ref(branch, field="branch")
        clean_base = self._clean_ref(base_ref, field="base_ref")
        source = await self._request(
            "GET",
            f"/repos/{repo}/git/ref/heads/{quote(clean_base, safe='')}",
        )
        try:
            sha = str(source["object"]["sha"])
        except (KeyError, TypeError) as exc:
            raise GitHubRESTError("GitHub base ref response has no commit SHA") from exc
        return await self._request(
            "POST",
            f"/repos/{repo}/git/refs",
            json_body={"ref": f"refs/heads/{clean_branch}", "sha": sha},
        )

    async def write_file(
        self,
        repository: str,
        path: str,
        *,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        clean_path = self._clean_repo_path(path)
        clean_branch = self._clean_ref(branch, field="branch")
        clean_message = (message or "").strip()
        if not clean_message:
            raise GitHubRESTError("GitHub commit message is empty")
        raw = (content or "").encode("utf-8")
        if len(raw) > MAX_FILE_BYTES:
            raise GitHubRESTError(
                f"GitHub file exceeds DEVON write limit of {MAX_FILE_BYTES} bytes"
            )
        body: Dict[str, Any] = {
            "message": clean_message,
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": clean_branch,
        }
        if sha:
            body["sha"] = str(sha).strip()
        return await self._request(
            "PUT",
            f"/repos/{repo}/contents/{quote(clean_path, safe='/')}",
            json_body=body,
        )

    async def create_pull_request(
        self,
        repository: str,
        *,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
    ) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        clean_title = (title or "").strip()
        if not clean_title:
            raise GitHubRESTError("pull request title is empty")
        return await self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json_body={
                "title": clean_title,
                "head": self._clean_ref(head, field="head"),
                "base": self._clean_ref(base, field="base"),
                "body": body or "",
                "draft": bool(draft),
            },
        )

    async def merge_pull_request(
        self,
        repository: str,
        number: int,
        *,
        merge_method: str = "merge",
        expected_head_sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        repo = self.require_repository(repository)
        method = (merge_method or "merge").strip().lower()
        if method not in {"merge", "squash", "rebase"}:
            raise GitHubRESTError("merge_method must be merge, squash, or rebase")
        body: Dict[str, Any] = {"merge_method": method}
        if expected_head_sha:
            body["sha"] = str(expected_head_sha).strip()
        return await self._request(
            "PUT",
            f"/repos/{repo}/pulls/{int(number)}/merge",
            json_body=body,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.configured:
            raise GitHubRESTError(
                "GitHub adapter is not configured. Set DEVON_GITHUB_TOKEN and "
                "DEVON_GITHUB_ALLOWED_REPOS."
            )
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DEVON-Agent-Runtime",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method.upper(),
                    path,
                    params=params,
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            raise GitHubRESTError(f"GitHub transport error: {exc}") from exc

        if not 200 <= response.status_code < 300:
            message = self._error_message(response)
            raise GitHubRESTError(
                f"GitHub API {response.status_code} for {method.upper()} {path}: {message}"
            )
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubRESTError("GitHub API returned non-JSON data") from exc
        if not isinstance(data, dict):
            raise GitHubRESTError("GitHub API returned an unexpected response shape")
        return data

    @staticmethod
    def _validate_repository_name(repository: str) -> str:
        value = (repository or "").strip()
        if not _REPOSITORY_RE.fullmatch(value):
            raise GitHubRESTError("repository must be exact owner/name")
        return value

    @staticmethod
    def _clean_repo_path(path: str) -> str:
        value = (path or "").strip().lstrip("/")
        if not value or value in {".", ".."}:
            raise GitHubRESTError("repository path is empty")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise GitHubRESTError("repository path contains an invalid segment")
        return "/".join(parts)

    @staticmethod
    def _clean_ref(value: str, *, field: str) -> str:
        clean = (value or "").strip().removeprefix("refs/heads/")
        if not clean or clean.startswith("/") or clean.endswith("/"):
            raise GitHubRESTError(f"{field} is invalid")
        if ".." in clean or "~" in clean or "^" in clean or ":" in clean or "\\" in clean:
            raise GitHubRESTError(f"{field} contains a forbidden ref sequence")
        return clean

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            data = response.json()
            if isinstance(data, dict):
                message = str(data.get("message") or json.dumps(data, ensure_ascii=False))
            else:
                message = str(data)
        except ValueError:
            message = response.text
        return message[:MAX_ERROR_CHARS]
