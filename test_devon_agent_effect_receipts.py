"""Phase 1 foundation tests for durable effect intents and receipts.

These tests prove the contracts and persistence models are loadable and
behave as designed. Runtime wiring that writes intents before adapter calls
and records receipts afterward is the next implementation slice and is not
claimed by this PR.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.agent_runtime.contracts import (
    AmbiguousOutcome,
    EffectIntent,
    EffectReceipt,
    EffectStatus,
)


def test_effect_intent_to_dict_is_stable() -> None:
    created = datetime(2026, 8, 24, 18, 0, tzinfo=timezone.utc)
    intent = EffectIntent(
        intent_id="INT-1",
        task_id="TASK-1",
        step_id="step-1",
        tool_name="operator.command",
        arguments_hash="abc123",
        idempotency_key="key-1",
        created_at=created,
    )
    payload = intent.to_dict()
    assert payload["intent_id"] == "INT-1"
    assert payload["task_id"] == "TASK-1"
    assert payload["tool_name"] == "operator.command"
    assert payload["arguments_hash"] == "abc123"
    assert payload["idempotency_key"] == "key-1"
    assert payload["created_at"] == created.isoformat()


def test_effect_receipt_statuses() -> None:
    for status in (EffectStatus.SUCCEEDED, EffectStatus.FAILED, EffectStatus.AMBIGUOUS):
        receipt = EffectReceipt(
            intent_id="INT-1",
            status=status,
            provider_receipt_id="prov-1",
            raw_response={"ok": True},
        )
        assert receipt.to_dict()["status"] == status.value


def test_ambiguous_outcome_refuses_automatic_retry_framing() -> None:
    intent = EffectIntent(
        intent_id="INT-2",
        task_id="TASK-2",
        step_id="step-2",
        tool_name="github.create_issue",
        arguments_hash="def456",
        idempotency_key="key-2",
    )
    outcome = AmbiguousOutcome(intent=intent)
    payload = outcome.to_dict()
    assert payload["reason"] == "ambiguous_external_effect"
    assert "Automatic retry is refused" in payload["detail"]
    assert payload["intent"]["intent_id"] == "INT-2"


def test_effect_models_are_registered() -> None:
    from app.models import AgentEffectIntentRecord, AgentEffectReceiptRecord

    assert AgentEffectIntentRecord.__tablename__ == "agent_effect_intents"
    assert AgentEffectReceiptRecord.__tablename__ == "agent_effect_receipts"
