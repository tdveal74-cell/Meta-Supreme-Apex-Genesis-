"""The runtime side of the code worker: code.task and code.status."""

from __future__ import annotations

import json

import httpx
import pytest

REPO = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"


def _configure(monkeypatch, handler):
    from app.services.agent_tasks import code_worker_client

    monkeypatch.setattr(code_worker_client, "key", "test-code-key")
    monkeypatch.setattr(code_worker_client, "url", "https://code.test")
    monkeypatch.setattr(code_worker_client, "allowed_repos", [REPO])
    monkeypatch.setattr(code_worker_client, "transport", httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_code_task_waits_for_a_high_impact_card_then_submits_once(client, auth_headers, monkeypatch):
    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-devon-code-key"] == "test-code-key"
        if request.method == "POST":
            body = json.loads(request.content)
            posts.append(body)
            assert body["repository"] == REPO and body["approval_id"].startswith("REQ-")
            return httpx.Response(202, json={"job": body, "state": "queued", "branch": "devon/code-x"})
        return httpx.Response(
            200,
            json={
                "job": {"job_id": posts[0]["job_id"]},
                "state": "done",
                "branch": "devon/code-x",
                "commits": 2,
                "tests": {"ran": True, "passed": True, "exit_code": 0, "tail": "2 passed"},
                "agent": {"subtype": "success", "total_cost_usd": 0.8},
                "pull_request": {"number": 9, "url": "https://github.com/x/pull/9", "draft": True},
                "error": "",
            },
        )

    _configure(monkeypatch, handler)
    catalog = await client.get("/api/v1/agent-tasks/tools", headers=auth_headers)
    specs = {item["name"]: item for item in catalog.json()["tools"]}
    assert specs["code.task"]["risk"] == "high_impact"
    assert specs["code.status"]["approval_required"] is False

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Fix the failing test",
            "steps": [
                {
                    "title": "Code it",
                    "tool": "code.task",
                    "arguments": {
                        "repository": REPO,
                        "task": "Make test_calc pass by fixing add in calc.py.",
                        "test_command": "pytest -q",
                    },
                }
            ],
        },
    )
    task_id = created.json()["task_id"]
    waiting = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert waiting.json()["task"]["state"] == "waiting_approval"
    assert posts == []
    step = waiting.json()["task"]["plan"]["steps"][0]
    await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": step["approval_request_id"], "token": waiting.json()["approval_token"], "decision": "approve"},
    )
    resumed = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert resumed.json()["task"]["state"] == "completed", resumed.text
    assert len(posts) == 1
    job_id = posts[0]["job_id"]
    assert job_id.startswith("DEVON-")
    assert "test-code-key" not in resumed.text

    from app.services.agent_tasks import build_tool_registry

    status = await build_tool_registry().execute("code.status", {"job_id": job_id})
    assert status.ok is True
    assert status.metadata["url"] == "https://github.com/x/pull/9"


@pytest.mark.asyncio
async def test_a_repository_off_the_allowlist_is_refused_before_the_approval_is_spent():
    from services.agent_runtime.governance import (
        APPROVAL_METADATA_KEY,
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.agent_runtime.tools import ToolRegistry
    from services.code_worker.agent_adapter import CodeWorkerCapabilityAdapter
    from services.code_worker.client import CodeWorkerClient
    from services.devon.approval import ApprovalQueue, ApprovalState

    calls = []
    approvals = ApprovalQueue()
    args = {"repository": "someone/else", "task": "Rewrite everything in this repository."}
    binding = approval_binding(task_id="T", step_id="S", tool_name="code.task", arguments=args)
    record, token = approvals.request(title="x", what_happens=f"y {approval_marker(binding)}", requested_by=RUNTIME_REQUESTED_BY)
    approvals.decide(record.request_id, token, "approve")
    registry = ToolRegistry()
    CodeWorkerCapabilityAdapter(
        CodeWorkerClient(key="k", url="https://code.test", allowed_repos=[REPO], transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))),
        approvals,
    ).register(registry)
    result = await registry.execute(
        "code.task",
        {**args, APPROVAL_METADATA_KEY: {"request_id": record.request_id, "binding": binding, "task_id": "T", "step_id": "S", "tool_name": "code.task"}},
    )
    assert result.ok is False and "not allowlisted" in result.error and "approval was not spent" in result.error
    assert calls == []
    assert approvals.get(record.request_id).state is ApprovalState.APPROVED


@pytest.mark.asyncio
async def test_a_failed_job_reads_back_as_a_failure():
    from services.agent_runtime.tools import ToolRegistry
    from services.code_worker.agent_adapter import CodeWorkerCapabilityAdapter
    from services.code_worker.client import CodeWorkerClient
    from services.devon.approval import ApprovalQueue

    registry = ToolRegistry()
    CodeWorkerCapabilityAdapter(
        CodeWorkerClient(
            key="k", url="https://code.test", allowed_repos=[REPO],
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"job": {"job_id": "DEVON-ABCDEF"}, "state": "failed", "error": "git clone failed"})),
        ),
        ApprovalQueue(),
    ).register(registry)
    result = await registry.execute("code.status", {"job_id": "DEVON-ABCDEF"})
    assert result.ok is False and "git clone failed" in result.error


def test_the_client_needs_https_a_key_and_an_allowlist(monkeypatch):
    from services.code_worker.client import CodeWorkerClient

    for name in ("DEVON_CODE_WORKER_KEY", "DEVON_CODE_WORKER_URL", "DEVON_CODE_WORKER_REPOS"):
        monkeypatch.delenv(name, raising=False)
    assert CodeWorkerClient().configured is False
    assert CodeWorkerClient(key="k", url="http://code.test", allowed_repos=[REPO]).configured is False
    assert CodeWorkerClient(key="k", url="https://code.test", allowed_repos=[]).configured is False
    assert CodeWorkerClient(key="k", url="https://code.test", allowed_repos=[REPO]).configured is True
