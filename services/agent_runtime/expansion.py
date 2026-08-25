"""Hermes-style expansion contracts for DEVON Agent Runtime.

Four governed capabilities:
1. Subagents — child tasks under a parent, same approval/receipt rules
2. Scheduler — delayed/resumable goals, never silent effects
3. Skill proposals — autonomous drafts only; promotion needs Tee
4. Browser tools live in services.browser (separate adapter)

DEVON core remains effect-free. Nothing here executes outside the runtime
approval + effect-receipt path.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.agent_runtime.contracts import utcnow


class ScheduleState(str, Enum):
    PENDING = "pending"
    DUE = "due"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SkillProposalState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class SubAgentSpec:
    """A bounded child goal spawned from a parent task."""

    subagent_id: str
    parent_task_id: str
    goal: str
    max_steps: int = 8
    inherit_context_keys: Tuple[str, ...] = ()
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "parent_task_id": self.parent_task_id,
            "goal": self.goal,
            "max_steps": self.max_steps,
            "inherit_context_keys": list(self.inherit_context_keys),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ScheduledGoal:
    """A goal that becomes runnable at or after run_at."""

    schedule_id: str
    owner_id: str
    goal: str
    run_at: datetime
    state: ScheduleState = ScheduleState.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    failure_reason: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def mark_due(self) -> None:
        if self.state is ScheduleState.PENDING and utcnow() >= self.run_at:
            self.state = ScheduleState.DUE
            self.updated_at = utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "owner_id": self.owner_id,
            "goal": self.goal,
            "run_at": self.run_at.isoformat(),
            "state": self.state.value,
            "context": dict(self.context),
            "task_id": self.task_id,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class SkillProposal:
    """Draft skill extracted from a completed task. Not active until approved."""

    proposal_id: str
    name: str
    description: str
    instructions: str
    source_task_id: str
    state: SkillProposalState = SkillProposalState.PROPOSED
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "source_task_id": self.source_task_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
        }


class InMemoryScheduleStore:
    """Process-local schedule ledger for tests and single-process development."""

    def __init__(self) -> None:
        self._items: Dict[str, ScheduledGoal] = {}

    def schedule(
        self,
        *,
        owner_id: str,
        goal: str,
        run_at: datetime,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScheduledGoal:
        clean_goal = (goal or "").strip()
        if not clean_goal:
            raise ValueError("scheduled goal is empty")
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        item = ScheduledGoal(
            schedule_id=f"SCH-{secrets.token_hex(6).upper()}",
            owner_id=owner_id,
            goal=clean_goal,
            run_at=run_at,
            context=dict(context or {}),
        )
        item.mark_due()
        self._items[item.schedule_id] = item
        return item

    def get(self, schedule_id: str) -> Optional[ScheduledGoal]:
        return self._items.get(schedule_id)

    def list_for(self, owner_id: str) -> List[ScheduledGoal]:
        return sorted(
            [item for item in self._items.values() if item.owner_id == owner_id],
            key=lambda item: item.run_at,
        )

    def due(self, owner_id: Optional[str] = None) -> List[ScheduledGoal]:
        now = utcnow()
        out: List[ScheduledGoal] = []
        for item in self._items.values():
            if owner_id and item.owner_id != owner_id:
                continue
            item.mark_due()
            if item.state is ScheduleState.DUE and item.run_at <= now:
                out.append(item)
        return sorted(out, key=lambda item: item.run_at)

    def cancel(self, schedule_id: str, *, reason: str = "cancelled") -> Optional[ScheduledGoal]:
        item = self._items.get(schedule_id)
        if item is None:
            return None
        if item.state in {ScheduleState.COMPLETED, ScheduleState.CANCELLED}:
            return item
        item.state = ScheduleState.CANCELLED
        item.failure_reason = reason
        item.updated_at = utcnow()
        return item

    def attach_task(self, schedule_id: str, task_id: str) -> ScheduledGoal:
        item = self._items[schedule_id]
        item.task_id = task_id
        item.state = ScheduleState.RUNNING
        item.updated_at = utcnow()
        return item

    def complete(self, schedule_id: str) -> ScheduledGoal:
        item = self._items[schedule_id]
        item.state = ScheduleState.COMPLETED
        item.updated_at = utcnow()
        return item


class SkillProposalStore:
    """Transparent skill proposal ledger. Promotion is a separate step."""

    def __init__(self) -> None:
        self._items: Dict[str, SkillProposal] = {}

    def propose_from_task(
        self,
        *,
        task_id: str,
        goal: str,
        observations: Sequence[str],
    ) -> SkillProposal:
        name = _slug_from_goal(goal)
        description = f"Proposed skill from completed task {task_id}"
        instructions = _instructions_from_observations(goal, observations)
        proposal = SkillProposal(
            proposal_id=f"SP-{secrets.token_hex(6).upper()}",
            name=name,
            description=description,
            instructions=instructions,
            source_task_id=task_id,
        )
        self._items[proposal.proposal_id] = proposal
        return proposal

    def get(self, proposal_id: str) -> Optional[SkillProposal]:
        return self._items.get(proposal_id)

    def list_proposed(self) -> List[SkillProposal]:
        return [
            item
            for item in sorted(self._items.values(), key=lambda p: p.created_at)
            if item.state is SkillProposalState.PROPOSED
        ]

    def decide(
        self,
        proposal_id: str,
        *,
        approve: bool,
    ) -> SkillProposal:
        item = self._items.get(proposal_id)
        if item is None:
            raise KeyError(f"unknown skill proposal: {proposal_id}")
        if item.state is not SkillProposalState.PROPOSED:
            raise ValueError(f"proposal already decided: {item.state.value}")
        new_state = SkillProposalState.APPROVED if approve else SkillProposalState.REJECTED
        updated = SkillProposal(
            proposal_id=item.proposal_id,
            name=item.name,
            description=item.description,
            instructions=item.instructions,
            source_task_id=item.source_task_id,
            state=new_state,
            created_at=item.created_at,
        )
        self._items[proposal_id] = updated
        return updated


def new_subagent_spec(
    *,
    parent_task_id: str,
    goal: str,
    max_steps: int = 8,
    inherit_context_keys: Sequence[str] = (),
) -> SubAgentSpec:
    clean = (goal or "").strip()
    if not clean:
        raise ValueError("subagent goal is empty")
    steps = max(1, min(int(max_steps), 12))
    return SubAgentSpec(
        subagent_id=f"SUB-{secrets.token_hex(5).upper()}",
        parent_task_id=parent_task_id,
        goal=clean,
        max_steps=steps,
        inherit_context_keys=tuple(k for k in inherit_context_keys if k),
    )


def schedule_in(
    store: InMemoryScheduleStore,
    *,
    owner_id: str,
    goal: str,
    delay_seconds: int,
    context: Optional[Dict[str, Any]] = None,
) -> ScheduledGoal:
    delay = max(0, int(delay_seconds))
    return store.schedule(
        owner_id=owner_id,
        goal=goal,
        run_at=utcnow() + timedelta(seconds=delay),
        context=context,
    )


def _slug_from_goal(goal: str) -> str:
    words = [w for w in (goal or "").lower().split() if w.isalnum()][:6]
    return "-".join(words) or "proposed-skill"


def _instructions_from_observations(goal: str, observations: Sequence[str]) -> str:
    lines = [f"Goal pattern: {goal.strip()}", "Observed steps:"]
    for index, item in enumerate(observations[:12], start=1):
        clean = (item or "").strip()
        if clean:
            lines.append(f"{index}. {clean[:500]}")
    if len(lines) == 2:
        lines.append("1. (no observations recorded)")
    lines.append("Promotion requires human approval before this becomes an active skill.")
    return "\n".join(lines)
