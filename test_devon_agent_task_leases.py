"""Adversarial coverage for DEVON Agent Task execution leases."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update


@pytest.fixture
def configured_operator(monkeypatch, tmp_path):
    from app.api.v1.operator import _bridge

    monkeypatch.setattr(_bridge, "enabled", True)
    monkeypatch.setattr(_bridge, "_operator_key", "test-operator-key")
    monkeypatch.setattr(_bridge, "root", tmp_path.resolve())
    return _bridge


async def _owner_id(db_session) -> str:
    from app.models.user import User

    result = await db_session.execute(
        select(User.id).where(User.email == "council-tester@example.com")
    )
    owner_id = result.scalar_one()
    return str(owner_id)


@pytest.mark.asyncio
async def test_completed_effect_run_replays_by_idempotency_key_without_second_effect(
    client,
    auth_headers,
    configured_operator,
):
    command = "python -c \"open('lease-count.txt','a').write('x')\""
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Create exactly one leased execution marker",
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
        headers={**auth_headers, "Idempotency-Key": "approval-phase"},
        json={"max_steps": 5},
    )
    assert waiting.status_code == 200, waiting.text
    assert waiting.headers["idempotent-replay"] == "false"
    token = waiting.json()["approval_token"]
    request_id = waiting.json()["task"]["plan"]["steps"][0]["approval_request_id"]

    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": request_id,
            "token": token,
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200, decision.text

    effect_headers = {**auth_headers, "Idempotency-Key": "effect-once"}
    completed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=effect_headers,
        json={"max_steps": 5},
    )
    assert completed.status_code == 200, completed.text
    assert completed.headers["idempotent-replay"] == "false"
    assert completed.json()["task"]["state"] == "completed"
    marker = configured_operator.root / "lease-count.txt"
    assert marker.read_text() == "x"

    replay = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=effect_headers,
        json={"max_steps": 5},
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["idempotent-replay"] == "true"
    assert replay.json() == completed.json()
    assert marker.read_text() == "x"


@pytest.mark.asyncio
async def test_same_idempotency_key_cannot_change_run_parameters(
    client,
    auth_headers,
    configured_operator,
):
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Read once",
            "steps": [
                {
                    "title": "Read working directory",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    task_id = created.json()["task_id"]
    headers = {**auth_headers, "Idempotency-Key": "same-request"}
    first = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=headers,
        json={"max_steps": 1},
    )
    assert first.status_code == 200, first.text
    assert first.json()["task"]["state"] == "completed"

    changed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=headers,
        json={"max_steps": 2},
    )
    assert changed.status_code == 409, changed.text
    assert "different run parameters" in changed.json()["detail"]


@pytest.mark.asyncio
async def test_live_lease_blocks_second_worker_cancel_and_delete(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    from app.db.session import AsyncSessionLocal
    from app.services.agent_runtime_persistence import (
        AgentTaskRepository,
        TaskExecutionBusy,
    )

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Hold a task lease",
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    task_id = created.json()["task_id"]
    owner_id = await _owner_id(db_session)
    repo = AgentTaskRepository()

    async with AsyncSessionLocal() as first_session:
        first = await repo.acquire_execution(
            first_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="worker-one",
            max_steps=5,
            lease_owner="worker-one",
            lease_seconds=120,
        )
        await first_session.commit()
    assert first.lease_token

    async with AsyncSessionLocal() as second_session:
        with pytest.raises(TaskExecutionBusy, match="already running"):
            await repo.acquire_execution(
                second_session,
                owner_id=owner_id,
                task_id=task_id,
                idempotency_key="worker-two",
                max_steps=5,
                lease_owner="worker-two",
                lease_seconds=120,
            )
        await second_session.rollback()

    cancelled = await client.post(
        f"/api/v1/agent-tasks/{task_id}/cancel",
        headers=auth_headers,
        json={"reason": "should be blocked while leased"},
    )
    assert cancelled.status_code == 409, cancelled.text

    deleted = await client.delete(
        f"/api/v1/agent-tasks/{task_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 409, deleted.text


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over_and_stale_worker_is_fenced(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import AgentTaskRecord, AgentTaskRunRecord
    from app.services.agent_runtime_persistence import (
        AgentTaskRepository,
        TaskExecutionLeaseLost,
    )

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Prove stale worker fencing",
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    task_id = created.json()["task_id"]
    owner_id = await _owner_id(db_session)
    repo = AgentTaskRepository()

    async with AsyncSessionLocal() as first_session:
        first = await repo.acquire_execution(
            first_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="stale-worker",
            max_steps=5,
            lease_owner="worker-stale",
            lease_seconds=15,
        )
        await first_session.commit()
    assert first.task is not None
    assert first.lease_token is not None

    async with AsyncSessionLocal() as expire_session:
        await expire_session.execute(
            update(AgentTaskRecord)
            .where(AgentTaskRecord.id == task_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await expire_session.commit()

    async with AsyncSessionLocal() as takeover_session:
        second = await repo.acquire_execution(
            takeover_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="replacement-worker",
            max_steps=5,
            lease_owner="worker-new",
            lease_seconds=120,
        )
        await takeover_session.commit()
    assert second.lease_token and second.lease_token != first.lease_token
    assert second.execution_generation > first.execution_generation

    async with AsyncSessionLocal() as ledger_session:
        abandoned = await ledger_session.get(AgentTaskRunRecord, first.run_id)
        assert abandoned is not None
        assert abandoned.state == "failed"
        assert abandoned.error == "superseded after execution lease expired"
        assert abandoned.completed_at is not None
        assert abandoned.lease_token is None

    async with AsyncSessionLocal() as stale_session:
        with pytest.raises(TaskExecutionLeaseLost, match="stale result"):
            await repo.complete_execution(
                stale_session,
                owner_id=owner_id,
                run_id=first.run_id,
                lease_token=first.lease_token,
                task=first.task,
                result_payload={
                    "task": first.task.to_dict(),
                    "approval_token": None,
                    "message": "stale",
                },
                project_id=None,
            )
        await stale_session.rollback()

    async with AsyncSessionLocal() as stale_renewal:
        renewed = await repo.renew_execution(
            stale_renewal,
            owner_id=owner_id,
            task_id=task_id,
            run_id=first.run_id,
            lease_token=first.lease_token,
            lease_seconds=120,
        )
        assert renewed is False
        await stale_renewal.rollback()
