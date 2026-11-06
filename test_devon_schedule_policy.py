"""Offline policy and cooperative cancellation adversaries."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from services.agent_runtime import (
    AgentRuntime,
    PlanStep,
    StaticPlanner,
    TaskState,
    ToolCall,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
)
from services.agent_runtime.expansion import InMemoryScheduleStore, ScheduleState
from services.agent_runtime.schedule_policy import (
    POLICY_KEY,
    missed_run_expired,
    schedule_context,
)
from services.devon.approval import ApprovalQueue
from test_devon_agent_effect_runtime import _Recorder


@pytest.mark.parametrize("age,expired", [(299, False), (300, False), (301, True)])
def test_skip_policy_exact_boundary_and_backoff_does_not_reset_it(age, expired):
    slot = datetime(2026, 11, 6, tzinfo=timezone.utc)
    context = schedule_context({POLICY_KEY: {"missed_run_policy": "skip"}}, slot)
    # Retry moved run_at an hour later. Expiry still belongs to the first slot.
    assert missed_run_expired(context, slot + timedelta(hours=1), slot + timedelta(seconds=age)) is expired


def test_legacy_defaults_to_catch_up_and_policy_is_bound_at_creation():
    slot = datetime(2026, 11, 6, tzinfo=timezone.utc)
    assert not missed_run_expired({}, slot, slot + timedelta(days=30))
    context = schedule_context({POLICY_KEY: {"missed_run_policy": "skip", "original_run_at": "2099-01-01"}}, slot)
    assert context[POLICY_KEY]["original_run_at"] == slot.isoformat()


@pytest.mark.parametrize("policy", [[], {"missed_run_policy": "all"}, {"max_lateness_seconds": True}, {"max_lateness_seconds": -1}, {"max_lateness_seconds": 1.5}])
def test_malformed_policy_refuses(policy):
    with pytest.raises(ValueError):
        schedule_context({POLICY_KEY: policy}, datetime.now(timezone.utc))


def test_memory_schedule_skip_is_owner_scoped_and_terminal():
    store = InMemoryScheduleStore()
    slot = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = store.schedule(owner_id="tee", goal="expired", run_at=slot,
        context={POLICY_KEY: {"missed_run_policy": "skip"}})
    other = store.schedule(owner_id="other", goal="other", run_at=slot)
    catch_up = store.schedule(owner_id="tee", goal="catch up", run_at=slot)
    assert [item.schedule_id for item in store.due("tee")] == [catch_up.schedule_id]
    assert expired.state is ScheduleState.CANCELLED
    assert expired.failure_reason.startswith("missed_run_skipped")
    assert other.state is ScheduleState.DUE


@pytest.mark.asyncio
async def test_running_effect_finishes_receipt_then_cancel_stops_next_tool():
    started, release = asyncio.Event(), asyncio.Event()
    stopped = False
    calls = []

    async def check():
        return "operator stop" if stopped else None

    async def write(args):
        started.set()
        await release.wait()
        calls.append("write")
        return "written"

    tools, approvals, recorder = ToolRegistry(), ApprovalQueue(), _Recorder()
    tools.register(ToolSpec(name="test.write", description="fixture", risk=ToolRisk.WRITE, handler=write))
    tools.register(ToolSpec(name="test.next", description="fixture", risk=ToolRisk.READ,
        handler=lambda args: calls.append("next") or "read"))
    steps = [PlanStep(step_id=str(i), title=tool, tool_call=ToolCall(name=tool))
        for i, tool in enumerate(["test.write", "test.next"])]
    runtime = AgentRuntime(planner=StaticPlanner(steps), tools=tools, approvals=approvals,
        effect_recorder=recorder, cancellation_check=check)
    task = await runtime.create_task("fixture")
    pending = await runtime.run_until_blocked(task.task_id)
    approvals.decide(task.active_step.approval_request_id, pending.approval_token, "approve")
    running = asyncio.create_task(runtime.run_until_blocked(task.task_id))
    await asyncio.wait_for(started.wait(), 1)
    stopped = True
    release.set()
    result = await asyncio.wait_for(running, 1)
    assert result.task.state is TaskState.CANCELLED
    assert calls == ["write"]
    assert len(recorder.intents) == len(recorder.receipts) == 1
    assert len(result.task.observations) == 1
    again = await runtime.run_until_blocked(task.task_id)
    assert again.task.state is TaskState.CANCELLED
    assert calls == ["write"]


@pytest.mark.asyncio
async def test_unreadable_cancellation_state_refuses_before_any_tool():
    async def check():
        raise RuntimeError("schedule store unavailable")

    calls = []
    tools = ToolRegistry()
    tools.register(ToolSpec(name="test.read", description="fixture", risk=ToolRisk.READ,
        handler=lambda args: calls.append("read") or "read"))
    runtime = AgentRuntime(planner=StaticPlanner([
        PlanStep(step_id="one", title="read", tool_call=ToolCall(name="test.read"))
    ]), tools=tools, cancellation_check=check)
    task = await runtime.create_task("fixture")
    with pytest.raises(RuntimeError, match="schedule store unavailable"):
        await runtime.run_until_blocked(task.task_id)
    assert calls == []
