"""Follow-on tests for durable Hermes expansion slice."""

from pathlib import Path

import pytest

from services.agent_runtime.expansion import SkillProposalStore
from services.agent_runtime.learning import InMemoryLearningStore
from services.agent_runtime.skill_promotion import promote_approved_skill
from services.browser.http_fetcher import maybe_live_fetcher


def test_promote_approved_skill_writes_to_learning_store() -> None:
    proposals = SkillProposalStore()
    learning = InMemoryLearningStore()
    proposal = proposals.propose_from_task(
        task_id="TASK-77",
        goal="Capture episode idea",
        observations=["Tagged Podcast", "Filed to Idea stage"],
    )
    approved = proposals.decide(proposal.proposal_id, approve=True)
    skill = promote_approved_skill(learning, approved)
    assert skill.name
    assert skill.version == 1
    assert "proposal:" in skill.provenance
    listed = learning.list_skills()
    assert any(item.name == skill.name for item in listed)


def test_promote_refuses_unapproved_proposal() -> None:
    proposals = SkillProposalStore()
    learning = InMemoryLearningStore()
    proposal = proposals.propose_from_task(
        task_id="TASK-78",
        goal="Should not promote",
        observations=[],
    )
    with pytest.raises(ValueError, match="not approved"):
        promote_approved_skill(learning, proposal)


def test_live_fetcher_disabled_by_default() -> None:
    assert maybe_live_fetcher(False) is None
    assert maybe_live_fetcher(True) is not None


def test_schema_009_exists() -> None:
    path = Path("database/schemas/009_agent_hermes_expansion.sql")
    assert path.is_file()
    text = path.read_text()
    assert "agent_schedules" in text
    assert "agent_skill_proposals" in text
