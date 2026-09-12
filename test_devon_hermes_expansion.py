"""Offline tests for Hermes expansion: subagents, schedule, browser, skills."""

from __future__ import annotations

from datetime import timedelta

import pytest

from services.agent_runtime.contracts import ToolRisk, utcnow
from services.agent_runtime.expansion import (
    InMemoryScheduleStore,
    SkillProposalState,
    SkillProposalStore,
    new_subagent_spec,
    schedule_in,
)
from services.agent_runtime.expansion_tools import ExpansionToolAdapter
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.tools import ToolRegistry
from services.browser.agent_adapter import BrowserCapabilityAdapter
from services.devon.approval import ApprovalQueue, ApprovalState


def _approved_call(queue, *, tool, arguments, task_id="TASK-1", step_id="STEP-1"):
    """Arguments carrying a spent-once approval, as the runtime hands them over."""
    binding = approval_binding(
        task_id=task_id, step_id=step_id, tool_name=tool, arguments=arguments
    )
    record, token = queue.request(
        title="governed expansion",
        what_happens=f"Run {tool}. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert queue.decide(record.request_id, token, "approve").approved is True
    return {
        **arguments,
        APPROVAL_METADATA_KEY: {
            "request_id": record.request_id,
            "binding": binding,
            "task_id": task_id,
            "step_id": step_id,
            "tool_name": tool,
        },
    }


def test_subagent_spec_is_bounded() -> None:
    spec = new_subagent_spec(parent_task_id="TASK-1", goal="Research allowlist", max_steps=99)
    assert spec.max_steps == 12
    assert spec.subagent_id.startswith("SUB-")
    assert spec.parent_task_id == "TASK-1"


def test_schedule_marks_due_after_delay() -> None:
    store = InMemoryScheduleStore()
    item = schedule_in(store, owner_id="tee", goal="Later work", delay_seconds=0)
    assert item.state.value in {"pending", "due"}
    due = store.due(owner_id="tee")
    assert any(x.schedule_id == item.schedule_id for x in due)


def test_skill_proposal_requires_human_before_active() -> None:
    store = SkillProposalStore()
    proposal = store.propose_from_task(
        task_id="TASK-9",
        goal="File a receipt",
        observations=["Asked for area", "Built filename"],
    )
    assert proposal.state is SkillProposalState.PROPOSED
    decided = store.decide(proposal.proposal_id, approve=True)
    assert decided.state is SkillProposalState.APPROVED


def test_skill_reject_path() -> None:
    store = SkillProposalStore()
    proposal = store.propose_from_task(
        task_id="TASK-10",
        goal="Bad pattern",
        observations=[],
    )
    rejected = store.decide(proposal.proposal_id, approve=False)
    assert rejected.state is SkillProposalState.REJECTED


def test_browser_fetch_rejects_unknown_host() -> None:
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._fetch({"url": "https://evil.example/x"})
    assert not result.ok
    assert "allowlist" in (result.error or "").lower()


def test_browser_fetch_accepts_allowlisted_host() -> None:
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._fetch({"url": "https://github.com/tdveal74-cell"})
    assert result.ok
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"].startswith("br-fetch-")


def test_browser_navigate_requires_approval_metadata() -> None:
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._navigate({"url": "https://github.com/tdveal74-cell"})
    assert not result.ok


def test_expansion_tools_register_and_describe() -> None:
    registry = ToolRegistry()
    ExpansionToolAdapter().register(registry)
    names = {item["name"] for item in registry.describe()}
    assert "runtime.spawn_subagent" in names
    assert "runtime.schedule_goal" in names
    assert "runtime.propose_skill" in names
    for item in registry.describe():
        if item["name"].startswith("runtime."):
            assert item["approval_required"] is True
            assert item["risk"] == ToolRisk.WRITE.value


@pytest.mark.asyncio
async def test_spawn_subagent_tool_spends_its_approval_and_emits_receipt_id() -> None:
    queue = ApprovalQueue()
    adapter = ExpansionToolAdapter(approvals=queue, process_local_ok=True)
    call = _approved_call(
        queue,
        tool="runtime.spawn_subagent",
        arguments={"parent_task_id": "TASK-1", "goal": "Child research", "max_steps": 4},
    )
    result = await adapter._spawn_subagent(call)
    assert result.ok, result.error
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"].startswith("SUB-")
    assert result.metadata["durable"] is False
    request_id = call[APPROVAL_METADATA_KEY]["request_id"]
    assert queue.get(request_id).state is ApprovalState.CONSUMED

    # The same metadata cannot run the tool twice: the approval was spent.
    replay = await adapter._spawn_subagent(call)
    assert not replay.ok
    assert "consumed" in (replay.error or "").lower()


@pytest.mark.asyncio
async def test_expansion_tools_refuse_without_approval_metadata() -> None:
    adapter = ExpansionToolAdapter(approvals=ApprovalQueue(), process_local_ok=True)
    for handler, arguments in (
        (adapter._spawn_subagent, {"parent_task_id": "TASK-1", "goal": "x"}),
        (adapter._schedule_goal, {"goal": "x", "delay_seconds": 0}),
        (adapter._propose_skill, {"task_id": "TASK-1", "goal": "x", "observations": []}),
    ):
        result = await handler(arguments)
        assert not result.ok
        assert "metadata" in (result.error or "").lower()

    bare = ExpansionToolAdapter()
    result = await bare._schedule_goal({"goal": "x", "delay_seconds": 0})
    assert not result.ok
    assert "approval authority" in (result.error or "").lower()

    # Writers missing and no test opt-in: the in-memory store is refused, and
    # the refusal comes before the binding so no approval could be spent.
    queue = ApprovalQueue()
    strict = ExpansionToolAdapter(approvals=queue)
    call = _approved_call(queue, tool="runtime.schedule_goal", arguments={"goal": "x"})
    result = await strict._schedule_goal(call)
    assert not result.ok
    assert "durable writer" in (result.error or "")
    assert queue.get(call[APPROVAL_METADATA_KEY]["request_id"]).state is ApprovalState.APPROVED
    assert strict.durable is False


@pytest.mark.asyncio
async def test_out_of_bounds_arguments_are_refused_before_the_approval_is_spent() -> None:
    queue = ApprovalQueue()
    adapter = ExpansionToolAdapter(approvals=queue, process_local_ok=True)
    call = _approved_call(
        queue,
        tool="runtime.schedule_goal",
        arguments={"goal": "far future", "delay_seconds": 10**15},
    )
    result = await adapter._schedule_goal(call)
    assert not result.ok
    assert "delay_seconds" in (result.error or "")
    assert queue.get(call[APPROVAL_METADATA_KEY]["request_id"]).state is ApprovalState.APPROVED

    call = _approved_call(
        queue,
        tool="runtime.propose_skill",
        arguments={"goal": "x" * 20_001, "observations": []},
    )
    result = await adapter._propose_skill(call)
    assert not result.ok
    assert "goal" in (result.error or "")
    assert queue.get(call[APPROVAL_METADATA_KEY]["request_id"]).state is ApprovalState.APPROVED


@pytest.mark.asyncio
async def test_spawn_and_propose_are_pinned_to_the_running_task() -> None:
    queue = ApprovalQueue()
    adapter = ExpansionToolAdapter(approvals=queue, process_local_ok=True)
    call = _approved_call(
        queue,
        tool="runtime.spawn_subagent",
        arguments={"parent_task_id": "TASK-OTHER", "goal": "Child"},
        task_id="TASK-1",
    )
    result = await adapter._spawn_subagent(call)
    assert not result.ok
    assert "running task" in (result.error or "")

    call = _approved_call(
        queue,
        tool="runtime.propose_skill",
        arguments={"task_id": "TASK-OTHER", "goal": "Skill", "observations": []},
        task_id="TASK-1",
    )
    result = await adapter._propose_skill(call)
    assert not result.ok
    assert "running task" in (result.error or "")


@pytest.mark.asyncio
async def test_schedule_goal_owner_comes_from_the_card_not_the_arguments() -> None:
    queue = ApprovalQueue()
    adapter = ExpansionToolAdapter(approvals=queue, process_local_ok=True)
    binding = approval_binding(
        task_id="TASK-1",
        step_id="STEP-1",
        tool_name="runtime.schedule_goal",
        arguments={"goal": "Later", "delay_seconds": 0, "owner_id": "someone-else"},
    )
    record, token = queue.request(
        title="schedule",
        what_happens=f"Schedule. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
        owner_id="the-real-owner",
    )
    assert queue.decide(record.request_id, token, "approve").approved is True
    result = await adapter._schedule_goal(
        {
            "goal": "Later",
            "delay_seconds": 0,
            "owner_id": "someone-else",
            APPROVAL_METADATA_KEY: {
                "request_id": record.request_id,
                "binding": binding,
                "task_id": "TASK-1",
                "step_id": "STEP-1",
                "tool_name": "runtime.schedule_goal",
            },
        }
    )
    assert not result.ok
    assert "does not match the owner" in (result.error or "")


def test_schedule_future_not_due_yet() -> None:
    store = InMemoryScheduleStore()
    item = store.schedule(
        owner_id="tee",
        goal="Tomorrow",
        run_at=utcnow() + timedelta(hours=2),
    )
    assert item.schedule_id.startswith("SCH-")
    assert store.due(owner_id="tee") == []
