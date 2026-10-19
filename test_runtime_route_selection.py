"""Database regression: sample distinct runtime tasks before applying limits."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.agent_runtime import AgentTaskRecord, AgentVerificationRecord
from app.services import agent_tasks
from services.agent_benchmarks import RouteTrace, fingerprint
from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry, ToolSpec
from services.agent_runtime.verification import canonical, digest


@pytest.mark.asyncio
async def test_calibration_and_repeat_generations_do_not_crowd_route_sample(
    client, auth_headers, db_session, monkeypatch,
):
    registry = ToolRegistry()
    registry.register(ToolSpec(name='fixture.read', description='fixture', risk=ToolRisk.READ,
                              handler=lambda args: 'fixture'))
    monkeypatch.setattr(agent_tasks, 'build_tool_registry', lambda: registry)
    task_ids = []
    for label in ('older-distinct', 'many-generations'):
        response = await client.post('/api/v1/agent-tasks', headers=auth_headers, json={
            'goal': label, 'steps': [{'title': 'read', 'tool': 'fixture.read'}],
        })
        assert response.status_code == 201, response.text
        task_ids.append(response.json()['task_id'])
    owner = await db_session.scalar(select(AgentTaskRecord.owner_id).where(AgentTaskRecord.id == task_ids[0]))
    start = datetime.now(timezone.utc) - timedelta(hours=1)

    def add(receipt_id, task_id, minute, latency=None):
        body = {'calibration': {'fixture': True}}
        if latency is not None:
            trace = RouteTrace(
                trace_id=receipt_id, task_id=task_id, task_family='fixture',
                task_hash=fingerprint({'task': task_id}), route_version='fixture-v1',
                model_version='none', prompt_version='v1', skill_version='v1', suite_version='v1',
                config_fingerprint=fingerprint({}), treatment='baseline', stop_reason='completed',
                receipt_refs=('result:' + task_id,), required=1, unresolved=0, evidenced=1,
                investigated=True, unsupported_answer=False, stopped_with_available_next_step=False,
                latency_ms=latency,
            )
            body = {'trace': asdict(trace)}
        encoded = canonical(body)
        db_session.add(AgentVerificationRecord(
            id=receipt_id, owner_id=owner, task_id=task_id, generation=minute,
            body=encoded, content_hash=digest(encoded), created_at=start + timedelta(minutes=minute),
        ))

    add('ROUTE-older', task_ids[0], 0, 1)
    for generation in range(1, 6):
        add('ROUTE-repeat-' + str(generation), task_ids[1], generation, generation)
    # Same timestamp must resolve deterministically by receipt ID descending.
    add('ROUTE-repeat-z', task_ids[1], 5, 99)
    for i in range(6, 12):
        add('CALIB-newer-' + str(i), task_ids[1], i)
    await db_session.commit()

    response = await client.get('/api/v1/agent-tasks/evaluation/routes?limit=2', headers=auth_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['tasks'] == 2
    assert result['duplicate_task_content_excluded'] == 0
    assert result['profiles'][0]['latency_ms'] == {'recorded': 2, 'missing': 0, 'mean': 50}
    # Limit is applied globally after per-task selection, not once per task.
    newest = await client.get('/api/v1/agent-tasks/evaluation/routes?limit=1', headers=auth_headers)
    assert newest.status_code == 200, newest.text
    assert newest.json()['tasks'] == 1
    assert newest.json()['profiles'][0]['latency_ms']['mean'] == 99
