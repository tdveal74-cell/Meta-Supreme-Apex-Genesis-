"""Promote an approved skill proposal into the transparent learning store.

Approval is external (Tee decides). This module only applies an already-approved
proposal. It never activates a proposed skill on its own.
"""

from __future__ import annotations

from services.agent_runtime.expansion import SkillProposal, SkillProposalState
from services.agent_runtime.learning import LearningStore, SkillRecord


def promote_approved_skill(
    learning: LearningStore,
    proposal: SkillProposal,
) -> SkillRecord:
    if proposal.state is not SkillProposalState.APPROVED:
        raise ValueError(
            f"skill proposal is not approved (state={proposal.state.value}); "
            "promotion refused"
        )
    return learning.upsert_skill(
        name=proposal.name,
        description=proposal.description,
        instructions=proposal.instructions,
        provenance=f"proposal:{proposal.proposal_id}:{proposal.source_task_id}",
    )
