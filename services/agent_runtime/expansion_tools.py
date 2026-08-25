"""Runtime tools for Hermes expansion capabilities.

These tools propose structure; they do not bypass approval or effect receipts.
Subagent spawn records a child goal. Schedule records a delayed goal. Skill
propose drafts a skill from a completed task for human promotion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.expansion import (
    InMemoryScheduleStore,
    SkillProposalStore,
    new_subagent_spec,
    schedule_in,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec


class ExpansionToolAdapter:
    """Registers subagent, schedule, and skill-proposal tools."""

    name = "expansion"

    def __init__(
        self,
        *,
        schedules: Optional[InMemoryScheduleStore] = None,
        skill_proposals: Optional[SkillProposalStore] = None,
        default_owner_id: str = "runtime",
    ) -> None:
        self.schedules = schedules or InMemoryScheduleStore()
        self.skill_proposals = skill_proposals or SkillProposalStore()
        self.default_owner_id = default_owner_id
        self._spawned: List[Dict[str, Any]] = []

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="runtime.spawn_subagent",
                description=(
                    "Propose a bounded child agent goal under the current parent task. "
                    "Does not execute the child; the application layer must create the "
                    "child task under the same approval and receipt rules."
                ),
                risk=ToolRisk.WRITE,
                handler=self._spawn_subagent,
                reversible=True,
                blast_radius="one child AgentTask plan under the parent task",
            )
        )
        registry.register(
            ToolSpec(
                name="runtime.schedule_goal",
                description=(
                    "Schedule a goal to become runnable after a delay. The scheduled "
                    "goal does not execute effects until a later governed run."
                ),
                risk=ToolRisk.WRITE,
                handler=self._schedule_goal,
                reversible=True,
                blast_radius="one delayed goal entry in the schedule ledger",
            )
        )
        registry.register(
            ToolSpec(
                name="runtime.propose_skill",
                description=(
                    "Draft a skill proposal from a completed task's observations. "
                    "Does not activate the skill; Tee must approve promotion."
                ),
                risk=ToolRisk.WRITE,
                handler=self._propose_skill,
                reversible=True,
                blast_radius="one SkillProposal row awaiting human decision",
            )
        )

    def _spawn_subagent(self, arguments: Dict[str, Any]) -> ToolResult:
        from services.agent_runtime.governance import APPROVAL_METADATA_KEY

        args = dict(arguments)
        args.pop(APPROVAL_METADATA_KEY, None)
        parent = str(args.get("parent_task_id") or "").strip()
        goal = str(args.get("goal") or "").strip()
        if not parent:
            return ToolResult(False, error="parent_task_id is required")
        try:
            spec = new_subagent_spec(
                parent_task_id=parent,
                goal=goal,
                max_steps=int(args.get("max_steps") or 8),
                inherit_context_keys=list(args.get("inherit_context_keys") or ()),
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        payload = spec.to_dict()
        self._spawned.append(payload)
        return ToolResult(
            True,
            output=f"Subagent proposed: {spec.subagent_id} for {spec.goal}",
            metadata={**payload, "provider_receipt_id": spec.subagent_id},
        )

    def _schedule_goal(self, arguments: Dict[str, Any]) -> ToolResult:
        from services.agent_runtime.governance import APPROVAL_METADATA_KEY

        args = dict(arguments)
        args.pop(APPROVAL_METADATA_KEY, None)
        goal = str(args.get("goal") or "").strip()
        owner_id = str(args.get("owner_id") or self.default_owner_id).strip()
        delay = int(args.get("delay_seconds") or 0)
        try:
            item = schedule_in(
                self.schedules,
                owner_id=owner_id,
                goal=goal,
                delay_seconds=delay,
                context=dict(args.get("context") or {}),
            )
        except ValueError as exp:
            return ToolResult(False, error=str(exp))
        payload = item.to_dict()
        return ToolResult(
            True,
            output=f"Scheduled {item.schedule_id} for {item.run_at.isoformat()}",
            metadata={**payload, "provider_receipt_id": item.schedule_id},
        )

    def _propose_skill(self, arguments: Dict[str, Any]) -> ToolResult:
        from services.agent_runtime.governance import APPROVAL_METADATA_KEY

        args = dict(arguments)
        args.pop(APPROVAL_METADATA_KEY, None)
        task_id = str(args.get("task_id") or "").strip()
        goal = str(args.get("goal") or "").strip()
        observations = args.get("observations") or []
        if not task_id:
            return ToolResult(False, error="task_id is required")
        if not goal:
            return ToolResult(False, error="goal is required")
        if not isinstance(observations, list):
            return ToolResult(False, error="observations must be a list")
        proposal = self.skill_proposals.propose_from_task(
            task_id=task_id,
            goal=goal,
            observations=[str(x) for x in observations],
        )
        payload = proposal.to_dict()
        return ToolResult(
            True,
            output=(
                f"Skill proposal {proposal.proposal_id} drafted as '{proposal.name}'. "
                "Not active until approved."
            ),
            metadata={**payload, "provider_receipt_id": proposal.proposal_id},
        )
