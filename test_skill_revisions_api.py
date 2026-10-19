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
