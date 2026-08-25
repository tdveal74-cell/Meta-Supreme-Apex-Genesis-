"""Hermes learning loop helpers.

Auto skill-propose creates a draft only. Promotion still requires Tee.
"""

from __future__ import annotations

from typing import List, Optional

from services.agent_runtime.contracts import AgentTask, TaskState
from services.agent_runtime.expansion import SkillProposal, SkillProposalStore


def draft_skill_proposal_from_task(
    task: AgentTask,
    *,
    store: Optional[SkillProposalStore] = None,
) -> Optional[SkillProposal]:
    """If the task completed successfully, draft a skill proposal from observations."""
    if task.state is not TaskState.COMPLETED:
        return None
    observations: List[str] = []
    for item in task.observations:
        if item.ok and (item.output or "").strip():
            observations.append(item.output.strip()[:500])
        elif item.error:
            observations.append(f"error: {item.error.strip()[:300]}")
    proposal_store = store or SkillProposalStore()
    return proposal_store.propose_from_task(
        task_id=task.task_id,
        goal=task.goal,
        observations=observations,
    )
