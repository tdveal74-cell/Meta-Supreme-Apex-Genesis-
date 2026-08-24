"""Crash-injection style regression for durable effect intents.

Simulates the window where an external effect intent was written but the
process died before a receipt was recorded. The next run must refuse
automatic retry with ambiguous_external_effect.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_orphan_intent_refuses_automatic_retry(
    client,
    auth_headers,
    db_session,
):
    from app.models.agent_runtime import (
        AgentEffectIntentRecord,
        AgentTaskRecord,
    )
    from app.services.agent_effect_receipts import EffectReceiptRepository

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Crash window regression",
            "steps": [
                {
                    "title": "Read only step",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    # Resolve owner_id from the durable task row.
    task_row = (
        await db_session.execute(
            select(AgentTaskRecord).where(AgentTaskRecord.id == task_id)
        )
    ).scalar_one()
    owner_id = task_row.owner_id

    # Simulate crash: intent written, no receipt.
    now = datetime.now(timezone.utc)
    db_session.add(
        AgentEffectIntentRecord(
            id="EIR-CRASH-TEST",
            intent_id="INT-CRASH-TEST",
            task_id=task_id,
            owner_id=owner_id,
            step_id="STEP-01",
            tool_name="operator.command",
            arguments_hash="deadbeef",
            idempotency_key="crash-key",
            execution_generation=1,
            lease_token=None,
            created_at=now,
        )
    )
    await db_session.commit()

    orphans = await EffectReceiptRepository().find_orphan_intents(
        db_session, owner_id=owner_id, task_id=task_id
    )
    assert len(orphans) == 1
    assert orphans[0].intent.intent_id == "INT-CRASH-TEST"
    assert orphans[0].reason == "ambiguous_external_effect"

    # Running the task must refuse rather than silently re-executing.
    run = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers={**auth_headers, "Idempotency-Key": "after-crash"},
        json={"max_steps": 3},
    )
    assert run.status_code in {409, 500, 400, 422}, run.text
    body = run.text.lower()
    assert "ambiguous" in body or "orphan" in body or "external_effect" in body


@pytest.mark.asyncio
async def test_intent_with_matching_receipt_is_not_orphan(
    client,
    auth_headers,
    db_session,
):
    from app.models.agent_runtime import (
        AgentEffectIntentRecord,
        AgentEffectReceiptRecord,
        AgentTaskRecord,
    )
    from app.services.agent_effect_receipts import EffectReceiptRepository

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Completed effect is not orphan",
            "steps": [
                {
                    "title": "Read only step",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    task_row = (
        await db_session.execute(
            select(AgentTaskRecord).where(AgentTaskRecord.id == task_id)
        )
    ).scalar_one()
    owner_id = task_row.owner_id
    now = datetime.now(timezone.utc)

    db_session.add(
        AgentEffectIntentRecord(
            id="EIR-OK-TEST",
            intent_id="INT-OK-TEST",
            task_id=task_id,
            owner_id=owner_id,
            step_id="STEP-01",
            tool_name="github.write_file",
            arguments_hash="cafe",
            idempotency_key="ok-key",
            execution_generation=1,
            lease_token=None,
            created_at=now,
        )
    )
    db_session.add(
        AgentEffectReceiptRecord(
            id="ERR-OK-TEST",
            intent_id="INT-OK-TEST",
            task_id=task_id,
            owner_id=owner_id,
            status="succeeded",
            provider_receipt_id="sha-abc",
            raw_response={"ok": True},
            execution_generation=1,
            lease_token=None,
            recorded_at=now,
        )
    )
    await db_session.commit()

    orphans = await EffectReceiptRepository().find_orphan_intents(
        db_session, owner_id=owner_id, task_id=task_id
    )
    assert orphans == []
