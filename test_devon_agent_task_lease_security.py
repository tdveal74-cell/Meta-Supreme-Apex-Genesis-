"""Security regressions for the DEVON Agent Task idempotency ledger."""

import pytest
from sqlalchemy import select


@pytest.fixture
def configured_operator(monkeypatch, tmp_path):
    from app.api.v1.operator import _bridge

    monkeypatch.setattr(_bridge, "enabled", True)
    monkeypatch.setattr(_bridge, "_operator_key", "test-operator-key")
    monkeypatch.setattr(_bridge, "root", tmp_path.resolve())
    return _bridge


@pytest.mark.asyncio
async def test_approval_token_is_delivered_once_but_never_persisted_or_reissued(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    from app.models.agent_runtime import AgentTaskRunRecord

    command = "python -c \"open('secure-lease.txt','w').write('approved')\""
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Request one approved write without persisting its credential",
            "steps": [
                {
                    "title": "Write only after approval",
                    "tool": "operator.command",
                    "arguments": {"command": command},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    headers = {**auth_headers, "Idempotency-Key": "secure-approval-gate"}

    first = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=headers,
        json={"max_steps": 5},
    )
    assert first.status_code == 200, first.text
    approval_token = first.json()["approval_token"]
    assert approval_token
    assert first.headers["idempotent-replay"] == "false"

    result = await db_session.execute(
        select(AgentTaskRunRecord).where(
            AgentTaskRunRecord.task_id == task_id,
            AgentTaskRunRecord.idempotency_key == "secure-approval-gate",
        )
    )
    run_row = result.scalar_one()
    assert run_row.state == "completed"
    assert run_row.result is not None
    assert run_row.result["approval_token"] is None
    assert approval_token not in str(run_row.result)

    replay = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=headers,
        json={"max_steps": 5},
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["idempotent-replay"] == "true"
    assert replay.json()["approval_token"] is None
    assert replay.json()["task"] == first.json()["task"]

    request_id = first.json()["task"]["plan"]["steps"][0]["approval_request_id"]
    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": request_id,
            "token": approval_token,
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200, decision.text
