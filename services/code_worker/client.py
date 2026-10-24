"""Client for the DEVON code worker on the VPS (`deploy/code-worker`).

The worker takes one approved coding job, runs the Claude Agent SDK in a fresh
clone on a new branch, runs the tests itself and opens a draft pull request.
This client submits the job and reads its record back. The key
(`DEVON_CODE_WORKER_KEY`) is approval equivalent for a coding job and is
configuration, never a tool argument or output. Written 2026-10-24 against a
mock transport; no job has been posted to a live worker yet.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, Optional

import httpx

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_JOB_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,63}$")
MAX_ERROR_CHARS = 2_000


class CodeWorkerError(ValueError):
    """The job cannot be sent, or the worker refused it."""


class CodeWorkerClient:
    def __init__(
        self,
        *,
        key: Optional[str] = None,
        url: Optional[str] = None,
        allowed_repos: Optional[Iterable[str]] = None,
        timeout_seconds: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.key = (key if key is not None else os.getenv("DEVON_CODE_WORKER_KEY", "")).strip()
        self.url = (url if url is not None else os.getenv("DEVON_CODE_WORKER_URL", "")).strip().rstrip("/")
        raw = (
            list(allowed_repos)
            if allowed_repos is not None
            else [r.strip() for r in os.getenv("DEVON_CODE_WORKER_REPOS", "").split(",") if r.strip()]
        )
        self.allowed_repos = sorted({r for r in raw if _REPO_RE.fullmatch(r)})
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.key and self.url.startswith("https://") and self.allowed_repos)

    def require_repository(self, repository: str) -> str:
        clean = (repository or "").strip()
        if clean not in self.allowed_repos:
            raise CodeWorkerError(
                f"repository is not allowlisted for the code worker: {clean!r}. "
                f"Allowlisted: {', '.join(self.allowed_repos) or 'none'}"
            )
        return clean

    async def submit(self, job: Dict[str, Any]) -> Dict[str, Any]:
        self.require_repository(str(job.get("repository") or ""))
        return await self._request("POST", "/jobs", job)

    async def status(self, job_id: str) -> Dict[str, Any]:
        if not _JOB_RE.fullmatch(job_id or ""):
            raise CodeWorkerError("job_id is not a code worker job id")
        return await self._request("GET", f"/jobs/{job_id}", None)

    async def _request(self, method: str, path: str, body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.configured:
            raise CodeWorkerError(
                "code worker is not configured. Set DEVON_CODE_WORKER_URL (https), "
                "DEVON_CODE_WORKER_KEY and DEVON_CODE_WORKER_REPOS."
            )
        try:
            async with httpx.AsyncClient(
                base_url=self.url,
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    headers={"x-devon-code-key": self.key, "User-Agent": "DEVON-Agent-Runtime"},
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise CodeWorkerError(
                f"code worker transport error: {exc}. Read the job with code.status before resubmitting."
            ) from exc
        if not 200 <= response.status_code < 300:
            raise CodeWorkerError(
                f"code worker answered HTTP {response.status_code}: {response.text[:MAX_ERROR_CHARS]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise CodeWorkerError("code worker answered without JSON") from exc
        if not isinstance(data, dict):
            raise CodeWorkerError("code worker answered with an unexpected shape")
        return data
