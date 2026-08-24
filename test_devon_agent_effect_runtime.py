"""Offline tests for optional EffectRecorder integration in AgentRuntime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from services.agent_runtime.contracts import (
    EffectIntent,
    EffectReceipt,
    EffectStatus,
    PlanStep,
    ToolCall,
    ToolRisk,
)
from services.agent_runtime.planner import StaticPlanner
from services.agent_runtime.runtime import AgentRuntime
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue


class _Recorder:
    def __init__(self) -> None:
        self.intents: List[EffectIntent] = []
        self.receipts: List[EffectReceipt] = []

    async def begin_effect(
        self,
        *,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
    ) -> EffectIntent:
        intent = EffectIntent(
            intent_id="INT-TEST",
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments_hash="hash",
            idempotency_key=idempotency_key,
        )
        self.intents.append(intent)
        return intent

    async def complete_effect(
        self,
        *,
        intent: EffectIntent,
        status: EffectStatus,
        provider_receipt_id: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> EffectReceipt:
        receipt = EffectReceipt(
            intent_id=intent.intent_id,
            status=status,
            provider_receipt_id=provider_receipt_id,
            raw_response=dict(raw_response or {}),
        )
        self.receipts.append(receipt)
        return receipt


@pytest.mark.asyncio
async def test_runtime_records_intent_and_receipt_for_effectful_tool() -> None:
    registry = ToolRegistry()

    def _handler(arguments: Dict[str, Any]) -> ToolResult:
        return ToolResult(True, output="done", metadata={"id": "prov-9"})

    registry.register(
        ToolSpec(
            name="demo.write",
            description="effectful demo",
            risk=ToolRisk.WRITE,
            handler=_handler,
            reversible=False,
            blast_radius="test only",
        )
    )

    approvals = ApprovalQueue()
    recorder = _Recorder()
    steps = [
        PlanStep(
            step_id="STEP-01",
            title="Write something",
            tool_call=ToolCall(name="demo.write", arguments={"x": 1}),
        )
    ]
    runtime = AgentRuntime(
        planner=StaticPlanner(steps),
        tools=registry,
        approvals=approvals,
        effect_recorder=recorder,
        effect_idempotency_key="key-1",
    )
    task = await runtime.create_task("demo goal")

    # First call stops at approval.
    first = await runtime.run_next(task.task_id)
    assert first.approval_token
    assert not recorder.intents

    request_id = first.task.plan.steps[0].approval_request_id
    assert request_id
    decided = approvals.decide(request_id, first.approval_token, "approve")
    assert decided.ok

    second = await runtime.run_next(task.task_id)
    assert second.task.done or second.task.current_step >= 1
    assert len(recorder.intents) == 1
    assert len(recorder.receipts) == 1
    assert recorder.receipts[0].status is EffectStatus.SUCCEEDED
    assert recorder.receipts[0].provider_receipt_id == "prov-9"
