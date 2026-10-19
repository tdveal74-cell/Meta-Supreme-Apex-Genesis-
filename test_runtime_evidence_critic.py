"""Adversarial recorder checks without database or external capabilities."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services.agent_effect_receipts import EffectFenceRefused
from app.services.runtime_evidence import RuntimeEvidenceRepository
from services.agent_runtime.contracts import (
    AgentPlan,
    AgentTask,
    Observation,
    PlanStep,
    TaskState,
    ToolCall,
)
from services.agent_runtime.verification import canonical, digest


class Session:
    def __init__(self, row=None):
        self.row, self.added, self.queries = row, [], []

    async def scalar(self, query):
        self.queries.append(query)
        return self.row

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        pass


def task(ref=None):
    value = AgentTask(task_id='TASK-example', goal='read the input', context={'input': 'one'},
                     plan=AgentPlan(goal='read the input', steps=[PlanStep(
                         step_id='s', title='read', tool_call=ToolCall(name='fixture.read', arguments={}))]),
                     state=TaskState.COMPLETED,
                     verification_requirements=[{'id': 'check', 'step_id': 's', 'kind': 'tool_succeeded', 'expected': {}}])
    if ref is not None:
        value.observations.append(Observation(step_id='s', ok=True, output='claimed success',
                                             metadata={'durable_result': ref}))
    return value


class Evidence(RuntimeEvidenceRepository):
    def __init__(self, result):
        self.result, self.lookups = result, []

    async def _fence(self, db, **kwargs):
        pass

    async def get_result(self, db, **kwargs):
        self.lookups.append(kwargs)
        return self.result


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize('result', [None,
    {'id': 'r', 'sha256': 'b' * 64, 'step_id': 's', 'captured': {'tool': 'fixture.read', 'ok': True, 'output': ''}},
    {'id': 'r', 'sha256': 'a' * 64, 'step_id': 'OTHER', 'captured': {'tool': 'fixture.read', 'ok': True, 'output': ''}}])
def test_forged_result_reference_cannot_establish_success(result):
    repo, db = Evidence(result), Session()
    value = task({'id': 'r', 'sha256': 'a' * 64})
    run(repo.verify(db, owner_id='owner', lease_token='lease', generation=2, task=value, latency_ms=1))
    assert value.verification['verdict'] == 'UNVERIFIED'
    assert repo.lookups == [{'owner_id': 'owner', 'task_id': 'TASK-example', 'result_id': 'r'}]
    assert len(db.added) == 1


def test_stale_fence_prevents_receipt_before_any_result_lookup():
    db = Session()
    with pytest.raises(EffectFenceRefused):
        run(RuntimeEvidenceRepository().verify(db, owner_id='owner', lease_token='stale',
                                              generation=2, task=task(), latency_ms=1))
    assert db.added == []
    assert len(db.queries) == 1


def test_result_lookup_authenticates_owner_task_and_body_hash():
    body = canonical({'tool': 'fixture.read', 'ok': True, 'output': 'original'})
    row = SimpleNamespace(id='r', body=body, content_hash=digest(body), step_id='s', generation=1)
    db = Session(row)
    result = run(RuntimeEvidenceRepository().get_result(db, owner_id='owner', task_id='task', result_id='r'))
    assert result['captured']['output'] == 'original'
    assert set(db.queries[0].compile().params.values()) == {'owner', 'task', 'r'}
    row.body = body.replace('original', 'forged')
    with pytest.raises(ValueError, match='integrity'):
        run(RuntimeEvidenceRepository().get_result(db, owner_id='owner', task_id='task', result_id='r'))


def test_legacy_task_context_affects_frozen_trace_hash():
    repo, db = Evidence(None), Session()
    value = task()
    run(repo.verify(db, owner_id='owner', lease_token='lease', generation=2, task=value, latency_ms=1))
    first = json.loads(db.added[-1].body)['trace']['task_hash']
    value.context['input'] = 'different'
    run(repo.verify(db, owner_id='owner', lease_token='lease', generation=2, task=value, latency_ms=1))
    assert first != json.loads(db.added[-1].body)['trace']['task_hash']


def test_rollback_drops_later_refs_and_resets_current_verdict():
    from services.agent_runtime.contracts import StepState, TaskCheckpoint, ToolRisk
    from services.agent_runtime.runtime import AgentRuntime
    from services.agent_runtime.tools import ToolRegistry, ToolSpec
    tools = ToolRegistry()
    tools.register(ToolSpec(name='fixture.read', description='fixture', risk=ToolRisk.READ, handler=lambda args: ''))
    runtime = AgentRuntime(planner=None, tools=tools)
    value = task({'id': 'old-result', 'sha256': 'a' * 64})
    value.current_step = 1
    value.plan.steps[0].state = StepState.COMPLETED
    value.verification = {'verdict': 'VERIFIED', 'receipt_id': 'old-receipt'}
    value.checkpoints.append(TaskCheckpoint(checkpoint_id='before', task_id=value.task_id,
        current_step=0, step_states=(('s', 'planned'),), observation_count=0, reason='before read'))
    runtime.store.put(value)
    rewound = runtime.rollback_agent_state(value.task_id, 'before')
    assert rewound.observations == []
    assert rewound.verification['verdict'] == 'UNVERIFIED'
    assert 'receipt_id' not in rewound.verification
    repo, db = Evidence(None), Session()
    run(repo.verify(db, owner_id='owner', lease_token='lease', generation=2, task=rewound, latency_ms=1))
    assert rewound.verification['verdict'] == 'UNVERIFIED'
    assert repo.lookups == []


def test_execution_budget_is_part_of_configuration_fingerprint():
    repo, db, value = Evidence(None), Session(), task()
    hashes = []
    for budget in (1, 20):
        run(repo.verify(db, owner_id='owner', lease_token='lease', generation=2,
                        task=value, latency_ms=1, max_steps=budget))
        hashes.append(json.loads(db.added[-1].body)['trace']['config_fingerprint'])
    assert hashes[0] != hashes[1]
