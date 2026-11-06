"""Database-backed immutable skill history and rollback integration."""
import pytest

BASE = "/api/v1/agent-tasks/learning/skills"


@pytest.mark.asyncio
async def test_exact_history_and_monotonic_rollback(client, auth_headers):
    first = {"description": "  original  ", "instructions": "line one\n\nline two\n"}
    for body in (first, {"description": "new", "instructions": "replacement"}):
        response = await client.put(f"{BASE}/proof", headers=auth_headers, json=body)
        assert response.status_code == 200, response.text
    response = await client.get(f"{BASE}/proof/revisions", headers=auth_headers)
    rows = response.json()["items"]
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["instructions"] == first["instructions"]
    assert rows[0]["description"] == first["description"]
    restored = await client.post(f"{BASE}/proof/rollback", headers=auth_headers,
                                json={"target_version": 1, "expected_version": 2})
    assert restored.status_code == 200, restored.text
    assert restored.json()["version"] == 3
    assert restored.json()["content_hash"] == rows[0]["content_hash"]
    stale = await client.post(f"{BASE}/proof/rollback", headers=auth_headers,
                             json={"target_version": 2, "expected_version": 2})
    assert stale.status_code == 409
    rows = (await client.get(f"{BASE}/proof/revisions", headers=auth_headers)).json()["items"]
    assert len(rows) == 3
    assert rows[0]["instructions"] == first["instructions"]


@pytest.mark.asyncio
async def test_cannot_self_assert_evaluation(client, auth_headers):
    result = await client.post(f"{BASE}/proof/evaluations", headers=auth_headers, json={
        "description": "test", "instructions": "test", "source_task_id": "fake",
        "suite_id": "receipt-decision-policy", "suite_version": "1", "passed": True})
    assert result.status_code == 422


@pytest.mark.asyncio
async def test_evolved_proposal_cannot_promote_without_receipt(client, auth_headers):
    proposal = await client.post("/api/v1/agent-expansion/skill-proposals", headers=auth_headers,
        json={"task_id": "TASK-DEMO", "goal": "test promoted evidence", "observations": ["evidence"]})
    assert proposal.status_code == 201, proposal.text
    result = await client.post(f"/api/v1/agent-expansion/skill-proposals/{proposal.json()['proposal_id']}/decide",
        headers=auth_headers, json={"approve": True, "promote": True, "expected_version": 0})
    assert result.status_code == 409
    proposals = (await client.get("/api/v1/agent-expansion/skill-proposals", headers=auth_headers)).json()
    assert next(p for p in proposals if p["proposal_id"] == proposal.json()["proposal_id"])["state"] == "proposed"


async def _candidate(client, headers, db):
    """Seed an owned lineage and exact declarative proposal, not an LLM score."""
    import json
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.models.agent_runtime import AgentSkillProposalRecord, AgentTaskRecord

    owner = (await client.get('/api/v1/auth/me', headers=headers)).json()['id']
    task_id, proposal_id = str(uuid4()), str(uuid4())
    instructions = json.dumps({'format': 'receipt-policy-v1', 'rules': {
        'verified': 'VERIFIED', 'failed': 'FAILED', 'missing': 'UNVERIFIED'},
        'default': 'UNVERIFIED'})
    now = datetime.now(timezone.utc)
    db.add(AgentTaskRecord(id=task_id, owner_id=owner, goal='owned fixture',
        state='completed', payload={}, created_at=now, updated_at=now))
    db.add(AgentSkillProposalRecord(id=proposal_id, proposal_id=proposal_id,
        owner_id=owner, name='proof', description='receipt policy', instructions=instructions,
        source_task_id=task_id, state='proposed', created_at=now))
    await db.commit()
    return owner, proposal_id, {'description': 'receipt policy', 'instructions': instructions,
        'source_task_id': task_id, 'suite_id': 'receipt-decision-policy', 'suite_version': '1'}


async def _decision(client, headers, proposal, evaluation):
    return await client.post(f'/api/v1/agent-expansion/skill-proposals/{proposal}/decide',
        headers=headers, json={'approve': True, 'promote': True,
                              'expected_version': 0, 'evaluation_id': evaluation})


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['bad_rule', 'unsupported_candidate', 'unsupported_runner'])
async def test_failed_attempt_retained_and_cannot_promote(client, auth_headers, db_session, failure):
    _, proposal, body = await _candidate(client, auth_headers, db_session)
    if failure == 'bad_rule':
        body['instructions'] = body['instructions'].replace('"failed": "FAILED"', '"failed": "VERIFIED"')
    elif failure == 'unsupported_candidate':
        body['instructions'] = 'natural language is not supported by this suite'
    else:
        body['suite_id'] = 'unregistered-suite'
    result = await client.post(f'{BASE}/proof/evaluations', headers=auth_headers, json=body)
    assert result.status_code == 200, result.text
    assert result.json()['evaluation_status'] == 'FAILED'
    evaluation_id = result.json()['evaluation_id']
    stored = await client.get(f'{BASE}/proof/evaluations/{evaluation_id}', headers=auth_headers)
    assert stored.status_code == 200
    evidence = stored.json()['evidence']
    assert evidence['candidate']['instructions'] == body['instructions']
    assert evidence['evaluation_status'] == 'FAILED' and evidence['error']
    # Use the failed candidate's exact hash/lineage to reach the status guard,
    # rather than relying only on a mismatch to prevent promotion.
    from sqlalchemy import select

    from app.models.agent_runtime import AgentSkillProposalRecord
    row = (await db_session.execute(select(AgentSkillProposalRecord).where(
        AgentSkillProposalRecord.proposal_id == proposal))).scalar_one()
    row.instructions = body['instructions']
    await db_session.commit()
    refused = await _decision(client, auth_headers, proposal, evaluation_id)
    assert refused.status_code == 409, refused.text
    assert (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items'] == []


@pytest.mark.asyncio
async def test_successful_evaluation_promotes_exact_candidate(client, auth_headers, db_session):
    _, proposal, body = await _candidate(client, auth_headers, db_session)
    result = await client.post(f'{BASE}/proof/evaluations', headers=auth_headers, json=body)
    assert result.status_code == 200 and result.json()['evaluation_status'] == 'PASSED', result.text
    promoted = await _decision(client, auth_headers, proposal, result.json()['evaluation_id'])
    assert promoted.status_code == 200, promoted.text
    rows = (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items']
    assert len(rows) == 1 and rows[0]['instructions'] == body['instructions']
    assert rows[0]['evidence']['evaluation_id'] == result.json()['evaluation_id']


@pytest.mark.asyncio
@pytest.mark.parametrize('mismatch', ['candidate', 'stale', 'cross_owner'])
async def test_promotion_refuses_mismatched_evaluation(client, auth_headers, db_session, mismatch):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from sqlalchemy import select

    from app.models.agent_runtime import AgentSkillEvaluationRecord, AgentSkillProposalRecord

    owner, proposal, body = await _candidate(client, auth_headers, db_session)
    response = await client.post(f'{BASE}/proof/evaluations', headers=auth_headers, json=body)
    assert response.status_code == 200, response.text
    evaluation_id = response.json()['evaluation_id']
    if mismatch == 'candidate':
        candidate = (await db_session.execute(select(AgentSkillProposalRecord).where(
            AgentSkillProposalRecord.proposal_id == proposal))).scalar_one()
        candidate.instructions += '\n'
    else:
        original = (await db_session.execute(select(AgentSkillEvaluationRecord).where(
            AgentSkillEvaluationRecord.id == evaluation_id))).scalar_one()
        if mismatch == 'cross_owner':
            registered = await client.post('/api/v1/auth/register', json={
                'email': 'other-skill-owner@example.com', 'password': 'another-strong-password-123',
                'full_name': 'Other Owner'})
            assert registered.status_code == 201, registered.text
            owner = registered.json()['id']
        evaluation_id = str(uuid4())
        db_session.add(AgentSkillEvaluationRecord(id=evaluation_id, owner_id=owner,
            skill_name=original.skill_name, content_hash=original.content_hash,
            source_task_id=original.source_task_id, suite_id=original.suite_id,
            suite_version=original.suite_version, evidence=original.evidence,
            created_at=datetime.now(timezone.utc) - timedelta(hours=25 if mismatch == 'stale' else 0)))
    await db_session.commit()
    refused = await _decision(client, auth_headers, proposal, evaluation_id)
    assert refused.status_code == 409, refused.text
    assert (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items'] == []


@pytest.mark.asyncio
async def test_curator_lock_gates_edit_rollback_and_requires_current_owner_version(client, auth_headers):
    original = {'description': '  curated  ', 'instructions': 'exact\n\nwording\n'}
    created = await client.put(f'{BASE}/proof', headers=auth_headers, json=original)
    assert created.status_code == 200
    locked = await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': True, 'expected_version': 1})
    assert locked.status_code == 200, locked.text
    assert locked.json()['version'] == 2 and locked.json()['locked'] is True
    assert (await client.get(f'{BASE}/proof/lock', headers=auth_headers)).json() == locked.json()
    skills = (await client.get(BASE, headers=auth_headers)).json()
    assert skills[0]['curator_locked'] is True
    assert skills[0]['instructions'] == original['instructions']
    edited = await client.put(f'{BASE}/proof', headers=auth_headers,
        json={'description': 'new', 'instructions': 'new', 'provenance': 'operator:unlock'})
    assert edited.status_code == 409, edited.text
    restored = await client.post(f'{BASE}/proof/rollback', headers=auth_headers,
        json={'target_version': 1, 'expected_version': 2})
    assert restored.status_code == 409, restored.text
    stale = await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': False, 'expected_version': 1})
    assert stale.status_code == 409
    assert (await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': 'false', 'expected_version': 2})).status_code == 422
    assert (await client.put(f'{BASE}/proof/lock',
        json={'locked': False, 'expected_version': 2})).status_code == 401
    rows = (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items']
    assert len(rows) == 2 and rows[0]['content_hash'] == rows[1]['content_hash']
    assert rows[1]['evidence'] == {'operation': 'human_curator_lock', 'curator_locked': True}
    unlocked = await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': False, 'expected_version': 2})
    assert unlocked.status_code == 200 and unlocked.json()['version'] == 3
    edited = await client.put(f'{BASE}/proof', headers=auth_headers, json=original)
    assert edited.status_code == 200 and edited.json()['version'] == 4
    assert edited.json()['curator_locked'] is False


@pytest.mark.asyncio
async def test_curator_lock_cannot_be_changed_or_read_by_another_owner(client, auth_headers):
    await client.put(f'{BASE}/proof', headers=auth_headers,
                     json={'description': 'canon', 'instructions': 'protected'})
    await client.put(f'{BASE}/proof/lock', headers=auth_headers,
                     json={'locked': True, 'expected_version': 1})
    registered = await client.post('/api/v1/auth/register', json={
        'email': 'curator-other@example.com', 'password': 'another-strong-password-123',
        'full_name': 'Other Owner'})
    assert registered.status_code == 201, registered.text
    login = await client.post('/api/v1/auth/login', json={
        'email': 'curator-other@example.com', 'password': 'another-strong-password-123'})
    assert login.status_code == 200, login.text
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    assert (await client.get(f'{BASE}/proof/lock', headers=headers)).status_code == 404
    assert (await client.put(f'{BASE}/proof/lock', headers=headers,
        json={'locked': False, 'expected_version': 2})).status_code == 404
    own = await client.put(f'{BASE}/proof', headers=headers,
                           json={'description': 'own', 'instructions': 'own'})
    assert own.status_code == 200 and own.json()['version'] == 1
    assert (await client.get(f'{BASE}/proof/lock', headers=auth_headers)).json()['locked'] is True


@pytest.mark.asyncio
async def test_curator_lock_refuses_even_evaluated_promotion(client, auth_headers, db_session):
    _, proposal, body = await _candidate(client, auth_headers, db_session)
    await client.put(f'{BASE}/proof', headers=auth_headers,
                     json={'description': 'canon', 'instructions': 'protected'})
    locked = await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': True, 'expected_version': 1})
    assert locked.status_code == 200
    evaluation = await client.post(f'{BASE}/proof/evaluations', headers=auth_headers, json=body)
    assert evaluation.json()['evaluation_status'] == 'PASSED'
    result = await client.post(f'/api/v1/agent-expansion/skill-proposals/{proposal}/decide',
        headers=auth_headers, json={'approve': True, 'promote': True, 'expected_version': 2,
                                   'evaluation_id': evaluation.json()['evaluation_id']})
    assert result.status_code == 409 and 'locked' in result.text
    proposals = (await client.get('/api/v1/agent-expansion/skill-proposals', headers=auth_headers)).json()
    assert next(p for p in proposals if p['proposal_id'] == proposal)['state'] == 'proposed'
    rows = (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items']
    assert len(rows) == 2 and rows[-1]['instructions'] == 'protected'


@pytest.mark.asyncio
async def test_curator_lock_refreshes_previously_loaded_skill_before_write(client, auth_headers, db_session):
    from sqlalchemy import select

    from app.models.agent_runtime import AgentRuntimeSkill
    from app.services.agent_tasks import agent_tasks_service
    from app.services.skill_revisions import SkillLocked

    await client.put(f'{BASE}/proof', headers=auth_headers,
                     json={'description': 'canon', 'instructions': 'protected'})
    owner = (await client.get('/api/v1/auth/me', headers=auth_headers)).json()['id']
    stale = (await db_session.execute(select(AgentRuntimeSkill).where(
        AgentRuntimeSkill.owner_id == owner, AgentRuntimeSkill.name == 'proof'))).scalar_one()
    assert stale.version == 1
    locked = await client.put(f'{BASE}/proof/lock', headers=auth_headers,
        json={'locked': True, 'expected_version': 1})
    assert locked.status_code == 200 and locked.json()['version'] == 2
    with pytest.raises(SkillLocked):
        await agent_tasks_service.learning.upsert_skill(db_session, owner_id=owner,
            name='proof', description='overwrite', instructions='forbidden')
    await db_session.rollback()
    skills = (await client.get(BASE, headers=auth_headers)).json()
    assert skills[0]['version'] == 2 and skills[0]['instructions'] == 'protected'


@pytest.mark.asyncio
async def test_curator_lock_commit_serializes_waiting_writer_and_rollback_is_atomic(client, auth_headers):
    import asyncio

    from app.db.session import AsyncSessionLocal
    from app.services.agent_tasks import agent_tasks_service
    from app.services.skill_revisions import SkillLocked, set_curator_lock

    await client.put(f'{BASE}/proof', headers=auth_headers,
                     json={'description': 'canon', 'instructions': 'protected'})
    owner = (await client.get('/api/v1/auth/me', headers=auth_headers)).json()['id']
    # An abandoned transition leaves neither a lock nor a partial version.
    async with AsyncSessionLocal() as transition:
        await set_curator_lock(transition, owner_id=owner, name='proof',
                               locked=True, expected_version=1)
        await transition.rollback()
    status = (await client.get(f'{BASE}/proof/lock', headers=auth_headers)).json()
    assert status['version'] == 1 and status['locked'] is False
    started = asyncio.Event()

    async def overwrite():
        async with AsyncSessionLocal() as writer:
            started.set()
            try:
                await agent_tasks_service.learning.upsert_skill(writer, owner_id=owner,
                    name='proof', description='bad', instructions='bad')
                await writer.commit()
            finally:
                await writer.rollback()

    async with AsyncSessionLocal() as transition:
        await set_curator_lock(transition, owner_id=owner, name='proof',
                               locked=True, expected_version=1)
        pending = asyncio.create_task(overwrite())
        try:
            await started.wait()
            # Writer must wait for the committed verdict, not read an old
            # unlocked revision while the transition remains in flight.
            await asyncio.sleep(0.05)
            assert not pending.done()
            await transition.commit()
            with pytest.raises(SkillLocked):
                await asyncio.wait_for(pending, timeout=5)
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
    status = (await client.get(f'{BASE}/proof/lock', headers=auth_headers)).json()
    assert status['version'] == 2 and status['locked'] is True
    rows = (await client.get(f'{BASE}/proof/revisions', headers=auth_headers)).json()['items']
    assert len(rows) == 2 and rows[-1]['instructions'] == 'protected'
