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
from services.agent_runtime.tools import ToolRegistry
from services.browser.agent_adapter import BrowserCapabilityAdapter
from services.devon.approval import ApprovalQueue


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
async def test_spawn_subagent_tool_emits_receipt_id() -> None:
    adapter = ExpansionToolAdapter()
    # WRITE tools need approval in the full runtime; unit-call the handler body
    # after stripping the approval gate by invoking the private method with
    # arguments only (approval is enforced by AgentRuntime before execute).
    result = adapter._spawn_subagent(
        {"parent_task_id": "TASK-1", "goal": "Child research", "max_steps": 4}
    )
    assert result.ok
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"].startswith("SUB-")


def test_schedule_future_not_due_yet() -> None:
    store = InMemoryScheduleStore()
    item = store.schedule(
        owner_id="tee",
        goal="Tomorrow",
        run_at=utcnow() + timedelta(hours=2),
    )
    assert item.schedule_id.startswith("SCH-")
    assert store.due(owner_id="tee") == []
