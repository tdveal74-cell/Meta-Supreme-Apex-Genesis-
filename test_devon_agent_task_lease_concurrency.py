"""Real PostgreSQL concurrency coverage for DEVON Agent Task leases."""

import asyncio

import pytest
from sqlalchemy import func, select


@pytest.fixture
def configured_operator(monkeypatch, tmp_path):
    from app.api.v1.operator import _bridge

    monkeypatch.setattr(_bridge, "enabled", True)
    monkeypatch.setattr(_bridge, "_operator_key", "test-operator-key")
    monkeypatch.setattr(_bridge, "root", tmp_path.resolve())
    return _bridge


@pytest.mark.asyncio
async def test_two_database_workers_race_for_one_task_and_exactly_one_wins(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import AgentTaskRecord, AgentTaskRunRecord
    from app.models.user import User
    from app.services.agent_runtime_persistence import (
        AgentTaskRepository,
        TaskExecutionBusy,
    )

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Prove one winner under simultaneous worker claims",
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    owner_result = await db_session.execute(
        select(User.id).where(User.email == "council-tester@example.com")
    )
    owner_id = str(owner_result.scalar_one())
    repo = AgentTaskRepository()

    async def claim(key: str):
        async with AsyncSessionLocal() as session:
            try:
                acquired = await repo.acquire_execution(
                    session,
                    owner_id=owner_id,
                    task_id=task_id,
                    idempotency_key=key,
                    max_steps=5,
                    lease_owner=key,
                    lease_seconds=120,
                )
            except TaskExecutionBusy:
                await session.rollback()
                return ("busy", key, None)
            await session.commit()
            return ("won", key, acquired)

    results = await asyncio.gather(claim("worker-a"), claim("worker-b"))
    winners = [item for item in results if item[0] == "won"]
    refused = [item for item in results if item[0] == "busy"]
    assert len(winners) == 1
    assert len(refused) == 1
    assert winners[0][2].execution_generation == 1

    async with AsyncSessionLocal() as verify:
        task = await verify.get(AgentTaskRecord, task_id)
        assert task is not None
        assert task.lease_token == winners[0][2].lease_token
        assert task.execution_generation == 1

        running_count = await verify.scalar(
            select(func.count())
            .select_from(AgentTaskRunRecord)
            .where(
                AgentTaskRunRecord.task_id == task_id,
                AgentTaskRunRecord.state == "running",
            )
        )
        assert running_count == 1
