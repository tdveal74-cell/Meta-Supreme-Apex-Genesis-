"""Database-backed schedule policy, cancellation and materialization races."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.agent_tasks import agent_tasks_service
from app.services.hermes_expansion_persistence import HermesExpansionRepository
from services.agent_runtime.contracts import TaskState
from services.agent_runtime.schedule_policy import POLICY_KEY
from test_devon_agent_scheduler_runner import _owner

REPO = HermesExpansionRepository()


@pytest.mark.asyncio
async def test_http_cancel_before_materialize_and_validate_policy(client, auth_headers):
    bad = await client.post('/api/v1/agent-expansion/schedules', headers=auth_headers,
        json={'goal': 'fixture', 'missed_run_policy': 'unknown'})
    assert bad.status_code == 422
    created = await client.post('/api/v1/agent-expansion/schedules', headers=auth_headers,
        json={'goal': 'fixture', 'missed_run_policy': 'skip', 'max_lateness_seconds': 600})
    assert created.status_code == 201, created.text
    assert created.json()['context'][POLICY_KEY]['missed_run_policy'] == 'skip'
    sid = created.json()['schedule_id']
    cancelled = await client.post(f'/api/v1/agent-expansion/schedules/{sid}/cancel',
        headers=auth_headers, json={'reason': 'stop fixture'})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()['schedule']['state'] == 'cancelled'
    assert cancelled.json()['in_flight_tool_may_finish'] is False
    materialized = await client.post('/api/v1/agent-expansion/schedules/materialize', headers=auth_headers)
    assert materialized.status_code == 200, materialized.text
    assert materialized.json() == []


@pytest.mark.asyncio
async def test_skip_survives_restart_backoff_and_other_owner_cannot_cancel(db_session):
    owner, other = await _owner(db_session), await _owner(db_session)
    slot = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = await REPO.create_schedule(db_session, owner_id=owner, goal='expired', run_at=slot,
        context={POLICY_KEY: {'missed_run_policy': 'skip', 'max_lateness_seconds': 60}})
    await REPO.defer_due_schedules(db_session, owner_id=owner, until=datetime.now(timezone.utc), reason='fixture')
    await db_session.commit()
    async with AsyncSessionLocal() as fresh:
        with pytest.raises(KeyError):
            await REPO.cancel_schedule(fresh, owner_id=other, schedule_id=expired.schedule_id, reason='intruder')
        await fresh.rollback()
        assert await REPO.due_schedules(fresh, owner_id=owner) == []
        await fresh.commit()
    async with AsyncSessionLocal() as again:
        saved = (await REPO.list_schedules(again, owner_id=owner))[0]
        assert saved.state.value == 'cancelled'
        assert saved.failure_reason.startswith('missed_run_skipped')
        assert saved.task_id is None


@pytest.mark.asyncio
async def test_cancelled_materialized_task_stops_before_tool_and_replays(db_session):
    owner = await _owner(db_session)
    schedule = await REPO.create_schedule(db_session, owner_id=owner, goal='Read fixture',
        run_at=datetime.now(timezone.utc))
    created = await agent_tasks_service.materialize_due_schedules(db_session, owner_id=owner)
    task_id = created[0]['task']['task_id']
    await db_session.commit()
    async with AsyncSessionLocal() as other_worker:
        await REPO.cancel_schedule(other_worker, owner_id=owner, schedule_id=schedule.schedule_id, reason='stop now')
        await other_worker.commit()
    outcome = await agent_tasks_service.run_until_blocked(db_session, owner_id=owner,
        task_id=task_id, idempotency_key='cancel-fixture')
    assert outcome.result['task']['state'] == TaskState.CANCELLED.value
    assert outcome.result['task']['observations'] == []
    repeat = await agent_tasks_service.run_until_blocked(db_session, owner_id=owner,
        task_id=task_id, idempotency_key='cancel-fixture')
    assert repeat.replayed and repeat.result == outcome.result
    schedule = (await REPO.list_schedules(db_session, owner_id=owner))[0]
    assert schedule.state.value == 'cancelled'
    assert schedule.failure_reason == 'stop now'


@pytest.mark.asyncio
async def test_two_manual_materializers_create_only_one_task(db_session):
    owner = await _owner(db_session)
    await REPO.create_schedule(db_session, owner_id=owner, goal='Only one fixture task',
        run_at=datetime.now(timezone.utc))
    await db_session.commit()

    async def worker():
        async with AsyncSessionLocal() as db:
            result = await agent_tasks_service.materialize_due_schedules(db, owner_id=owner)
            await db.commit()
            return result

    results = await asyncio.gather(worker(), worker())
    assert sum(map(len, results)) == 1
    count = await db_session.scalar(text('SELECT count(*) FROM agent_tasks WHERE owner_id = CAST(:owner AS uuid)'), {'owner': owner})
    assert count == 1
