"""Hardening tests for durable effect receipts.

Covers:
- approval_token never lands in receipt raw_response
- provider_receipt_id extraction from adapter metadata
- crash GitHub result surfaces a stable receipt id
- orphan AmbiguousOutcome refuses automatic retry framing
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from services.agent_runtime.contracts import (
    AmbiguousOutcome,
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
from services.github.agent_adapter import GitHubCapabilityAdapter


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
            intent_id="INT-HARDEN",
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


def test_github_result_sets_provider_receipt_id_from_sha() -> None:
    data = {
        "sha": "abc123def",
        "html_url": "https://github.com/example/repo/commit/abc123def",
        "path": "file.txt",
    }
    result = GitHubCapabilityAdapter._result(data)
    assert result.ok
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"] == "abc123def"


def test_github_result_falls_back_to_html_url() -> None:
    data = {"html_url": "https://github.com/example/repo/pull/12", "number": 12}
    result = GitHubCapabilityAdapter._result(data)
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"] == "https://github.com/example/repo/pull/12"


def test_ambiguous_outcome_refuses_automatic_retry() -> None:
    intent = EffectIntent(
        intent_id="INT-ORPHAN",
        task_id="TASK-1",
        step_id="STEP-01",
        tool_name="github.write_file",
        arguments_hash="x",
        idempotency_key="key",
    )
    outcome = AmbiguousOutcome(intent=intent)
    assert outcome.reason == "ambiguous_external_effect"
    assert "Automatic retry is refused" in outcome.detail


@pytest.mark.asyncio
async def test_runtime_passes_provider_receipt_id_from_metadata() -> None:
    registry = ToolRegistry()

    def _handler(arguments: Dict[str, Any]) -> ToolResult:
        return ToolResult(
            True,
            output="wrote",
            metadata={"provider_receipt_id": "sha-from-adapter", "sha": "ignored-when-explicit"},
        )

    registry.register(
        ToolSpec(
            name="demo.write",
            description="effectful demo",
            risk=ToolRisk.WRITE,
            handler=_handler,
            reversible=False,
            blast_radius="test",
        )
    )

    approvals = ApprovalQueue()
    recorder = _Recorder()
    steps = [
        PlanStep(
            step_id="STEP-01",
            title="Write",
            tool_call=ToolCall(name="demo.write", arguments={"x": 1}),
        )
    ]
    runtime = AgentRuntime(
        planner=StaticPlanner(steps),
        tools=registry,
        approvals=approvals,
        effect_recorder=recorder,
        effect_idempotency_key="key-harden",
    )
    task = await runtime.create_task("harden goal")
    first = await runtime.run_next(task.task_id)
    assert first.approval_token
    request_id = first.task.plan.steps[0].approval_request_id
    assert request_id
    decided = approvals.decide(request_id, first.approval_token, "approve")
    assert decided.ok

    second = await runtime.run_next(task.task_id)
    assert len(recorder.receipts) == 1
    assert recorder.receipts[0].provider_receipt_id == "sha-from-adapter"
    assert second.task.done or second.task.current_step >= 1


@pytest.mark.asyncio
async def test_runtime_does_not_put_approval_token_in_receipt_payload() -> None:
    """Recorder raw_response is built from tool result, not from the one-time token."""
    registry = ToolRegistry()

    def _handler(arguments: Dict[str, Any]) -> ToolResult:
        # Even if an adapter mistakenly echoed secrets into metadata, the
        # durable receipt path must not be trusted as a secret store.
        return ToolResult(True, output="ok", metadata={"note": "clean"})

    registry.register(
        ToolSpec(
            name="demo.write",
            description="effectful",
            risk=ToolRisk.WRITE,
            handler=_handler,
            reversible=False,
            blast_radius="test",
        )
    )
    approvals = ApprovalQueue()
    recorder = _Recorder()
    steps = [
        PlanStep(
            step_id="STEP-01",
            title="Write",
            tool_call=ToolCall(name="demo.write", arguments={}),
        )
    ]
    runtime = AgentRuntime(
        planner=StaticPlanner(steps),
        tools=registry,
        approvals=approvals,
        effect_recorder=recorder,
        effect_idempotency_key="key-2",
    )
    task = await runtime.create_task("token safety")
    first = await runtime.run_next(task.task_id)
    request_id = first.task.plan.steps[0].approval_request_id
    approvals.decide(request_id, first.approval_token, "approve")
    await runtime.run_next(task.task_id)

    assert len(recorder.receipts) == 1
    raw = recorder.receipts[0].raw_response
    assert "approval_token" not in raw
    assert "approval_token" not in str(raw.get("metadata") or {})
