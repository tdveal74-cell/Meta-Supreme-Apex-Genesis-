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

#: The same bounds the HTTP routes enforce with pydantic, checked before the
#: approval is spent so an oversized argument never burns a human ruling.
MAX_GOAL_CHARS = 20_000
MAX_DELAY_SECONDS = 31_536_000
MAX_OBSERVATIONS = 50
MAX_INHERIT_KEYS = 20
MAX_TASK_ID_CHARS = 64
MAX_STEPS = 12

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
    step_id: str
    request_id: str

    def provenance(self) -> Dict[str, str]:
        """Which governed step raised the row, for the operator reading it later."""
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "approval_request_id": self.request_id,
        }


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
        process_local_ok: bool = False,
    ) -> None:
        self.approvals = approvals
        self.schedules = schedules or InMemoryScheduleStore()
        self.skill_proposals = skill_proposals or SkillProposalStore()
        self.default_owner_id = default_owner_id
        self.schedule_writer = schedule_writer
        self.proposal_writer = proposal_writer
        self.subagent_writer = subagent_writer
        # A tool whose writer is missing refuses rather than succeeding into a
        # process-local store, unless a test says the in-memory path is what
        # it wants. A succeeded receipt for a row that exists nowhere is the
        # failure this adapter was rewritten to end.
        self.process_local_ok = process_local_ok
        self._spawned: List[Dict[str, Any]] = []

    @property
    def durable(self) -> bool:
        """True only when every tool has a durable writer behind it."""
        return all(
            writer is not None
            for writer in (self.schedule_writer, self.proposal_writer, self.subagent_writer)
        )

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

    def _ready(self, writer: object, *, tool_name: str) -> Optional[ToolResult]:
        """Refusals that must come before the approval is spent."""
        if self.approvals is None:
            return ToolResult(
                False,
                error=(
                    "no approval authority is configured for the runtime "
                    "expansion tools, so the governed write is refused"
                ),
            )
        if writer is None and not self.process_local_ok:
            return ToolResult(
                False,
                error=(
                    f"no durable writer is injected for {tool_name}; the "
                    "process-local store is refused outside tests, so the "
                    "approval was not spent"
                ),
            )
        return None

    @staticmethod
    def _bounded_goal(args: Dict[str, Any]) -> Union[str, ToolResult]:
        goal = str(args.get("goal") or "").strip()
        if not goal:
            return ToolResult(False, error="goal is required")
        if len(goal) > MAX_GOAL_CHARS:
            return ToolResult(False, error=f"goal is longer than {MAX_GOAL_CHARS} characters")
        return goal

    @staticmethod
    def _bounded_int(
        args: Dict[str, Any], key: str, *, default: int, low: int, high: int
    ) -> Union[int, ToolResult]:
        raw = args.get(key)
        if raw is None or raw == "":
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return ToolResult(False, error=f"{key} must be an integer")
        if value < low or value > high:
            return ToolResult(False, error=f"{key} must be between {low} and {high}")
        return value

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
        return _Approved(
            args=args,
            owner_id=owner_id.strip(),
            task_id=str(metadata.get("task_id") or "").strip(),
            step_id=str(metadata.get("step_id") or "").strip(),
            request_id=request_id,
        )

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
        raw = {k: v for k, v in arguments.items() if k != APPROVAL_METADATA_KEY}
        goal = self._bounded_goal(raw)
        if isinstance(goal, ToolResult):
            return goal
        max_steps = self._bounded_int(raw, "max_steps", default=8, low=1, high=MAX_STEPS)
        if isinstance(max_steps, ToolResult):
            return max_steps
        raw_keys = raw.get("inherit_context_keys") or ()
        if not isinstance(raw_keys, (list, tuple)):
            return ToolResult(False, error="inherit_context_keys must be a list")
        if len(raw_keys) > MAX_INHERIT_KEYS:
            return ToolResult(
                False, error=f"inherit_context_keys holds more than {MAX_INHERIT_KEYS} keys"
            )
        keys = [str(k)[:MAX_TASK_ID_CHARS] for k in raw_keys if k]
        not_ready = self._ready(self.subagent_writer, tool_name=SPAWN_TOOL)
        if not_ready is not None:
            return not_ready

        approved = self._approved(arguments, tool_name=SPAWN_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        parent = str(args.get("parent_task_id") or "").strip() or approved.task_id
        if not parent:
            return ToolResult(False, error="parent_task_id is required")
        if parent != approved.task_id:
            # The child lands under the task the approval was raised for, so
            # the row's provenance and the effect receipt name the same task.
            return ToolResult(
                False,
                error=(
                    "parent_task_id must be the running task; a child of another "
                    "task is spawned from that task's own governed run"
                ),
            )
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
        raw = {k: v for k, v in arguments.items() if k != APPROVAL_METADATA_KEY}
        goal = self._bounded_goal(raw)
        if isinstance(goal, ToolResult):
            return goal
        delay = self._bounded_int(
            raw, "delay_seconds", default=0, low=0, high=MAX_DELAY_SECONDS
        )
        if isinstance(delay, ToolResult):
            return delay
        if raw.get("context") is not None and not isinstance(raw.get("context"), dict):
            return ToolResult(False, error="context must be an object")
        not_ready = self._ready(self.schedule_writer, tool_name=SCHEDULE_TOOL)
        if not_ready is not None:
            return not_ready

        approved = self._approved(arguments, tool_name=SCHEDULE_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        stated_owner = str(args.get("owner_id") or "").strip()
        context = dict(args.get("context") or {})
        # The operator reading the schedule table can trace the row back to
        # the governed step and the human ruling that produced it.
        context["raised_by"] = approved.provenance()
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
        except (ValueError, OverflowError) as exc:
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
        raw = {k: v for k, v in arguments.items() if k != APPROVAL_METADATA_KEY}
        goal = self._bounded_goal(raw)
        if isinstance(goal, ToolResult):
            return goal
        observations = raw.get("observations") or []
        if not isinstance(observations, list):
            return ToolResult(False, error="observations must be a list")
        if len(observations) > MAX_OBSERVATIONS:
            return ToolResult(
                False, error=f"observations holds more than {MAX_OBSERVATIONS} entries"
            )
        if len(str(raw.get("task_id") or "")) > MAX_TASK_ID_CHARS:
            return ToolResult(False, error=f"task_id is longer than {MAX_TASK_ID_CHARS}")
        not_ready = self._ready(self.proposal_writer, tool_name=PROPOSE_TOOL)
        if not_ready is not None:
            return not_ready

        approved = self._approved(arguments, tool_name=PROPOSE_TOOL)
        if isinstance(approved, ToolResult):
            return approved
        args = approved.args
        task_id = str(args.get("task_id") or "").strip() or approved.task_id
        if not task_id:
            return ToolResult(False, error="task_id is required")
        if task_id != approved.task_id:
            # The proposal's provenance names the task whose run drafted it,
            # the same task the effect receipt names.
            return ToolResult(
                False,
                error="task_id must be the running task; a skill is drafted from its own run",
            )
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
