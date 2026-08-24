"""End-to-end coverage for durable DEVON Agent Tasks."""

from pathlib import Path

import pytest


@pytest.fixture
def configured_operator(monkeypatch, tmp_path):
    from app.api.v1.operator import _bridge

    monkeypatch.setattr(_bridge, "enabled", True)
    monkeypatch.setattr(_bridge, "_operator_key", "test-operator-key")
    monkeypatch.setattr(_bridge, "root", tmp_path.resolve())
    return _bridge


@pytest.mark.asyncio
async def test_read_task_persists_and_completes(client, auth_headers, configured_operator):
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Report the operator working directory",
            "steps": [
                {
                    "title": "Read working directory",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    run = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={"max_steps": 5},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["task"]["state"] == "completed"
    assert body["task"]["observations"][0]["ok"] is True
    assert body["task"]["observations"][0]["output"].strip() == str(
        configured_operator.root
    )

    fetched = await client.get(
        f"/api/v1/agent-tasks/{task_id}", headers=auth_headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "completed"
    assert len(fetched.json()["checkpoints"]) == 1


@pytest.mark.asyncio
async def test_effectful_task_requires_bound_approval_and_replays_once(
    client,
    auth_headers,
    configured_operator,
):
    command = "python -c \"open('count.txt','a').write('x')\""
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Create one execution marker",
            "steps": [
                {
                    "title": "Write execution marker",
                    "tool": "operator.command",
                    "arguments": {"command": command},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert waiting.status_code == 200, waiting.text
    waiting_body = waiting.json()
    assert waiting_body["task"]["state"] == "waiting_approval"
    token = waiting_body["approval_token"]
    request_id = waiting_body["task"]["plan"]["steps"][0]["approval_request_id"]
    assert token
    assert request_id
    assert not (configured_operator.root / "count.txt").exists()

    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": request_id,
            "token": token,
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["approved"] is True

    resumed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["task"]["state"] == "completed"
    marker = configured_operator.root / "count.txt"
    assert marker.read_text() == "x"

    replay = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert replay.status_code == 200
    assert replay.json()["task"]["state"] == "completed"
    assert marker.read_text() == "x"


@pytest.mark.asyncio
async def test_learning_records_are_durable_transparent_and_versioned(
    client,
    auth_headers,
):
    memory = await client.post(
        "/api/v1/agent-tasks/learning/memories",
        headers=auth_headers,
        json={
            "text": "Operator prefers evidence-backed verification before merge.",
            "tags": ["verification", "merge"],
            "source": "operator",
        },
    )
    assert memory.status_code == 201, memory.text
    memory_id = memory.json()["memory_id"]

    first_skill = await client.put(
        "/api/v1/agent-tasks/learning/skills/verify-before-merge",
        headers=auth_headers,
        json={
            "description": "Verify repository gates before merge.",
            "instructions": "Run the full CI gates and read the final state back.",
        },
    )
    assert first_skill.status_code == 200, first_skill.text
    assert first_skill.json()["version"] == 1

    second_skill = await client.put(
        "/api/v1/agent-tasks/learning/skills/verify-before-merge",
        headers=auth_headers,
        json={
            "description": "Verify the exact head before merge.",
            "instructions": "Run all gates on the exact head, then verify PR state.",
        },
    )
    assert second_skill.status_code == 200
    assert second_skill.json()["version"] == 2

    task = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Verify this merge with evidence",
            "steps": [
                {
                    "title": "Inspect directory",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert task.status_code == 201, task.text
    learning = task.json()["context"]["devon_learning"]
    assert any(item["memory_id"] == memory_id for item in learning["memories"])
    assert any(item["name"] == "verify-before-merge" for item in learning["skills"])

    memories = await client.get(
        "/api/v1/agent-tasks/learning/memories", headers=auth_headers
    )
    assert memories.status_code == 200
    assert any(item["memory_id"] == memory_id for item in memories.json())

    deleted = await client.delete(
        f"/api/v1/agent-tasks/learning/memories/{memory_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    after = await client.get(
        "/api/v1/agent-tasks/learning/memories", headers=auth_headers
    )
    assert all(item["memory_id"] != memory_id for item in after.json())


@pytest.mark.asyncio
async def test_task_owner_isolation(client, auth_headers):
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Owner-only task",
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-agent-user@example.com",
            "password": "another-strong-password-123",
            "full_name": "Other User",
        },
    )
    assert register.status_code == 201, register.text
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "other-agent-user@example.com",
            "password": "another-strong-password-123",
        },
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    hidden = await client.get(
        f"/api/v1/agent-tasks/{task_id}", headers=other_headers
    )
    assert hidden.status_code == 404
    listing = await client.get("/api/v1/agent-tasks", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []


def test_runtime_approval_binding_cannot_authorize_a_different_command(
    configured_operator,
):
    from services.agent_runtime.governance import (
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.devon.approval import ApprovalQueue
    from services.operator.bridge import OperatorError

    approvals = ApprovalQueue()
    original = {"command": "touch approved.txt"}
    binding = approval_binding(
        task_id="TASK-BOUND",
        step_id="STEP-01",
        tool_name="operator.command",
        arguments=original,
    )
    record, token = approvals.request(
        title="Bound command",
        what_happens=f"Run the approved command. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    ruled = approvals.decide(record.request_id, token, "approve")
    assert ruled.approved is True

    metadata = {
        "request_id": record.request_id,
        "binding": binding,
        "task_id": "TASK-BOUND",
        "step_id": "STEP-01",
        "tool_name": "operator.command",
    }
    with pytest.raises(OperatorError, match="does not match these arguments"):
        configured_operator.execute_runtime_approved(
            arguments={"command": "touch substituted.txt"},
            approval_metadata=metadata,
            approvals=approvals,
        )
    assert not Path(configured_operator.root, "approved.txt").exists()
    assert not Path(configured_operator.root, "substituted.txt").exists()
