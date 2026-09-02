"""Runtime tools for Hermes expansion capabilities.

These tools propose structure; they do not bypass approval or effect receipts.
Subagent spawn records a child goal. Schedule records a delayed goal. Skill
propose drafts a skill from a completed task for human promotion.

Every handler first verifies and spends the runtime approval binding, the way
each other governed adapter does, and then writes through the durable writers
the application injects: the same repositories the HTTP routes read, so an
approved effect with a succeeded receipt exists where the operator looks for
it. With no writers injected the adapter keeps process-local stores, marks
every result ``durable: False``, and is fit for offline tests only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from services.agent_runtime.contracts import ToolRisk, utcnow
from services.agent_runtime.expansion import (
    InMemoryScheduleStore,
    ScheduledGoal,
    SkillProposal,
    SkillProposalStore,
    new_subagent_spec,
    schedule_in,
)
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue

SPAWN_TOOL = "runtime.spawn_subagent"
SCHEDULE_TOOL = "runtime.schedule_goal"
PROPOSE_TOOL = "runtime.propose_skill"

#: Durable writers, injected by the application layer. Each runs in its own
#: committed transaction and returns what the HTTP routes would return.
ScheduleWriter = Callable[..., Awaitable[ScheduledGoal]]
ProposalWriter = Callable[..., Awaitable[SkillProposal]]
SubagentWriter = Callable[..., Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class _Approved:
    """What the boundary learned once the binding checked out and was spent."""

    args: Dict[str, Any]
    owner_id: str
    task_id: str


class ExpansionToolAdapter:
    """Registers subagent, schedule, and skill-proposal tools."""

    name = "expansion"

    def __init__(
        self,
        *,
        approvals: Optional[ApprovalQueue] = None,
        schedules: Optional[InMemoryScheduleStore] = None,
        skill_proposals: Optional[SkillProposalStore] = None,
        default_owner_id: str = "runtime",
        schedule_writer: Optional[ScheduleWriter] = None,
        proposal_writer: Optional[ProposalWriter] = None,
        subagent_writer: Optional[SubagentWriter] = None,
    ) -> None:
        self.approvals = approvals
        self.schedules = schedules or InMemoryScheduleStore()
        self.skill_proposals = skill_proposals or SkillProposalStore()
        self.default_owner_id = default_owner_id
        self.schedule_writer = schedule_writer
        self.proposal_writer = proposal_writer
        self.subagent_writer = subagent_writer
        self._spawned: List[Dict[str, Any]] = []

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name=SPAWN_TOOL,
                parameters=("parent_task_id", "goal", "max_steps", "inherit_context_keys"),
                description=(
                    "Create a bounded child task under the current parent task, "
                    "linked durably. parent_task_id defaults to the running task. "
                    "The child does not run until its own governed run; every "
                    "effect it attempts raises its own approval."
                ),
                risk=ToolRisk.WRITE,
                handler=self._spawn_subagent,
                reversible=True,
                blast_radius="one child AgentTask row and one parent-child link",
            )
        )
        registry.register(
            ToolSpec(
                name=SCHEDULE_TOOL,
                parameters=("goal", "owner_id", "delay_seconds", "context"),
                description=(
                    "Schedule a goal to become runnable after a delay, on the same "
                    "schedule table the operator reads and materializes. owner_id, "
                    "when given, must match the task's owner. The scheduled goal "
                    "does not execute effects until a later governed run."
                ),
                risk=ToolRisk.WRITE,
                handler=self._schedule_goal,
                reversible=True,
                blast_radius="one delayed goal row in the schedule table",
            )
        )
        registry.register(
            ToolSpec(
                name=PROPOSE_TOOL,
                parameters=("task_id", "goal", "observations"),
                description=(
                    "Draft a skill proposal from a completed task's observations, "
                    "on the same proposal table the operator decides from. Does "
                    "not activate the skill; Tee must approve promotion."
                ),
                risk=ToolRisk.WRITE,
                handler=self._propose_skill,
                reversible=True,
                blast_radius="one SkillProposal row awaiting human decision",
            )
        )

    # ------------------------------------------------------------------
    # The boundary every handler crosses first
    # ------------------------------------------------------------------

    def _approved(
        self, arguments: Dict[str, Any], *, tool_name: str
    ) -> Union[_Approved, ToolResult]:
        """Verify and spend the binding; learn the owner from the card.

        The owner comes from the approval record the runtime stamped at card
        time from the task context, never from the arguments the planner
        wrote, so a durable row can only land under the account that owns
        the task.
        """
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        if self.approvals is None:
            return ToolResult(
                False,
                error=(
                    "no approval authority is configured for the runtime "
                    "expansion tools, so the governed write is refused"
                ),
            )
        try:
            request_id, _binding = require_approved_runtime_binding(
                self.approvals,
                metadata,
                tool_name=tool_name,
                arguments=args,
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        record = self.approvals.get(request_id)
        owner_id = (record.owner_id if record is not None else "") or ""
        task_id = str(metadata.get("task_id") or "").strip()
        return _Approved(args=args, owner_id=owner_id.strip(), task_id=task_id)

    def _owner_for(
        self, approved: _Approved, *, stated: str, durable: bool
    ) -> Union[str, ToolResult]:
        if approved.owner_id:
            if stated and stated != approved.owner_id:
                return ToolResult(
                    False,
                    error=(
                        "owner_id in the arguments does not match the owner of "
                        "the task that raised this approval"
                    ),
                )
            return approved.owner_id
        if durable:
            return ToolResult(
                False,
                error=(
                    "the approval carries no owner, so the durable write is "
                    "refused; recreate the task under a signed-in account"
                ),
            )
        return stated or self.default_owner_id

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _spawn_subagent(self, arguments: Dict[str, Any]) -> ToolResult:
        approved = self._approved(arguments, tool_name=SPAWN_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        parent = str(args.get("parent_task_id") or "").strip() or approved.task_id
        goal = str(args.get("goal") or "").strip()
        if not parent:
            return ToolResult(False, error="parent_task_id is required")
        try:
            max_steps = int(args.get("max_steps") or 8)
        except (TypeError, ValueError):
            return ToolResult(False, error="max_steps must be an integer")
        keys = [str(k) for k in (args.get("inherit_context_keys") or ()) if k]
        durable = self.subagent_writer is not None
        owner = self._owner_for(approved, stated="", durable=durable)
        if isinstance(owner, ToolResult):
            return owner

        if durable:
            try:
                child = await self.subagent_writer(  # type: ignore[misc]
                    owner_id=owner,
                    parent_task_id=parent,
                    goal=goal,
                    max_steps=max_steps,
                    inherit_context_keys=keys,
                )
            except (KeyError, ValueError) as exc:
                return ToolResult(False, error=str(exc))
            context = dict(child.get("context") or {})
            payload = {
                "task_id": child.get("task_id"),
                "subagent_id": context.get("subagent_id"),
                "parent_task_id": parent,
                "goal": child.get("goal"),
                "max_steps": context.get("max_steps", max_steps),
                "state": child.get("state"),
                "durable": True,
            }
            return ToolResult(
                True,
                output=(
                    f"Subagent task {payload['task_id']} created under {parent} "
                    f"for {payload['goal']}. It runs only through its own governed run."
                ),
                metadata={**payload, "provider_receipt_id": str(payload["task_id"])},
            )

        try:
            spec = new_subagent_spec(
                parent_task_id=parent,
                goal=goal,
                max_steps=max_steps,
                inherit_context_keys=keys,
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        payload = {**spec.to_dict(), "durable": False}
        self._spawned.append(payload)
        return ToolResult(
            True,
            output=(
                f"Subagent proposed: {spec.subagent_id} for {spec.goal} "
                "(process-local, not durable)"
            ),
            metadata={**payload, "provider_receipt_id": spec.subagent_id},
        )

    async def _schedule_goal(self, arguments: Dict[str, Any]) -> ToolResult:
        approved = self._approved(arguments, tool_name=SCHEDULE_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        goal = str(args.get("goal") or "").strip()
        stated_owner = str(args.get("owner_id") or "").strip()
        try:
            delay = max(0, int(args.get("delay_seconds") or 0))
        except (TypeError, ValueError):
            return ToolResult(False, error="delay_seconds must be an integer")
        context = dict(args.get("context") or {})
        durable = self.schedule_writer is not None
        owner = self._owner_for(approved, stated=stated_owner, durable=durable)
        if isinstance(owner, ToolResult):
            return owner

        try:
            if durable:
                item = await self.schedule_writer(  # type: ignore[misc]
                    owner_id=owner,
                    goal=goal,
                    run_at=utcnow() + timedelta(seconds=delay),
                    context=context,
                )
            else:
                item = schedule_in(
                    self.schedules,
                    owner_id=owner,
                    goal=goal,
                    delay_seconds=delay,
                    context=context,
                )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        payload = {**item.to_dict(), "durable": durable}
        return ToolResult(
            True,
            output=(
                f"Scheduled {item.schedule_id} for {item.run_at.isoformat()}"
                + ("" if durable else " (process-local, not durable)")
            ),
            metadata={**payload, "provider_receipt_id": item.schedule_id},
        )

    async def _propose_skill(self, arguments: Dict[str, Any]) -> ToolResult:
        approved = self._approved(arguments, tool_name=PROPOSE_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        task_id = str(args.get("task_id") or "").strip() or approved.task_id
        goal = str(args.get("goal") or "").strip()
        observations = args.get("observations") or []
        if not task_id:
            return ToolResult(False, error="task_id is required")
        if not goal:
            return ToolResult(False, error="goal is required")
        if not isinstance(observations, list):
            return ToolResult(False, error="observations must be a list")
        durable = self.proposal_writer is not None
        owner = self._owner_for(approved, stated="", durable=durable)
        if isinstance(owner, ToolResult):
            return owner

        clean = [str(x) for x in observations]
        if durable:
            # The draft is the same one the HTTP propose route builds; only
            # the store differs.
            draft = SkillProposalStore().propose_from_task(
                task_id=task_id, goal=goal, observations=clean
            )
            try:
                proposal = await self.proposal_writer(  # type: ignore[misc]
                    owner_id=owner, proposal=draft
                )
            except ValueError as exc:
                return ToolResult(False, error=str(exc))
        else:
            proposal = self.skill_proposals.propose_from_task(
                task_id=task_id, goal=goal, observations=clean
            )
        payload = {**proposal.to_dict(), "durable": durable}
        return ToolResult(
            True,
            output=(
                f"Skill proposal {proposal.proposal_id} drafted as '{proposal.name}'. "
                "Not active until approved."
                + ("" if durable else " (process-local, not durable)")
            ),
            metadata={**payload, "provider_receipt_id": proposal.proposal_id},
        )
