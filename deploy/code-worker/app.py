"""HTTP surface of the DEVON code worker.

POST /jobs        accept one job, start it in the background, answer 202
GET  /jobs/{id}   the job record: state, branch, tests, agent, pull request
GET  /health      configuration, never a secret

Every route but /health needs the `x-devon-code-key` header, compared in
constant time. The key is approval equivalent for a coding job, the same way
the Action Router's key is for a write, so it lives on the API deployment and
on this box and nowhere else.

Configuration, all from the environment:

  DEVON_CODE_WORKER_KEY            the shared key
  DEVON_CODE_WORKER_GITHUB_TOKEN   push and pull request rights on the allowlist
  DEVON_CODE_WORKER_REPOS          comma separated owner/name allowlist
  DEVON_CODE_WORKER_JOBS_DIR       where job records live (default ./jobs)
  DEVON_CODE_WORKER_CONCURRENCY    jobs running at once (default 2)
  DEVON_CODE_WORKER_MODEL          optional model for the agent
  ANTHROPIC_API_KEY                read by the Agent SDK itself
"""

from __future__ import annotations

import asyncio
import hmac
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException

try:  # loaded as a package in tests, as a script directory on the box
    from .worker import CodeWorker, JobRefused, sdk_query
except ImportError:  # pragma: no cover
    from worker import CodeWorker, JobRefused, sdk_query  # type: ignore


async def github_http(method: str, path: str, headers: Dict[str, str], body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url="https://api.github.com", timeout=30.0, follow_redirects=False) as client:
        response = await client.request(
            method,
            path,
            headers={
                **headers,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "DEVON-code-worker",
            },
            json=body,
        )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"GitHub {response.status_code} for {method} {path}: {response.text[:500]}")
    return response.json()


def build_app(worker: Optional[CodeWorker] = None, *, key: Optional[str] = None, concurrency: Optional[int] = None) -> FastAPI:
    shared_key = (key if key is not None else os.getenv("DEVON_CODE_WORKER_KEY", "")).strip()
    if worker is None:
        query = None
        try:
            query = sdk_query()
        except ImportError:
            query = None
        worker = CodeWorker(
            github_token=os.getenv("DEVON_CODE_WORKER_GITHUB_TOKEN", "").strip(),
            allowed_repos=[r.strip() for r in os.getenv("DEVON_CODE_WORKER_REPOS", "").split(",") if r.strip()],
            jobs_dir=Path(os.getenv("DEVON_CODE_WORKER_JOBS_DIR", "jobs")),
            query=query,
            http=github_http,
            model=os.getenv("DEVON_CODE_WORKER_MODEL") or None,
        )
    slots = asyncio.Semaphore(max(1, int(concurrency or os.getenv("DEVON_CODE_WORKER_CONCURRENCY", "2"))))
    running: Dict[str, asyncio.Task] = {}
    app = FastAPI(title="DEVON code worker")

    def authorise(supplied: Optional[str]) -> None:
        if not shared_key:
            raise HTTPException(status_code=503, detail="DEVON_CODE_WORKER_KEY is not set; every job is refused")
        if not supplied or not hmac.compare_digest(supplied.encode(), shared_key.encode()):
            raise HTTPException(status_code=401, detail="x-devon-code-key is missing or wrong")

    async def run(job_id: str) -> None:
        async with slots:
            await worker.execute(job_id)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "key_set": bool(shared_key),
            "github_token_set": bool(worker.github_token),
            "agent_installed": worker._query is not None,
            "repositories": worker.allowed_repos,
        }

    @app.post("/jobs", status_code=202)
    async def create_job(body: Dict[str, Any], x_devon_code_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        authorise(x_devon_code_key)
        if worker._query is None:
            raise HTTPException(status_code=503, detail="claude-agent-sdk is not installed on this box")
        if not worker.github_token:
            raise HTTPException(status_code=503, detail="DEVON_CODE_WORKER_GITHUB_TOKEN is not set")
        try:
            record = worker.accept(body)
        except JobRefused as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        job_id = record.job["job_id"]
        if record.state == "queued" and job_id not in running:
            running[job_id] = asyncio.create_task(run(job_id))
        return record.to_dict()

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str, x_devon_code_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        authorise(x_devon_code_key)
        record = worker.load(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such job")
        return record.to_dict()

    return app
