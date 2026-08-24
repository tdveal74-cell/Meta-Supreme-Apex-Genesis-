"""Framework-free contracts for the DEVON Agent Runtime.

The runtime is deliberately outside ``services.devon``. DEVON remains the
planner, doctrine compiler, and approval authority. This package owns resumable
agent work state and can call capability adapters only after policy allows it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskState(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolRisk(str, Enum):
    READ = "read"
    WRITE = "write"
    HIGH_IMPACT = "high_impact"
    BLOCKED = "blocked"


class EffectStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    expected_outcome: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": dict(self.arguments),
            "reason": self.reason,
            "expected_outcome": self.expected_outcome,
        }


@dataclass
class PlanStep:
    step_id: str
    title: str
    tool_call: ToolCall
    state: StepState = StepState.PLANNED
    approval_request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "tool_call": self.tool_call.to_dict(),
            "state": self.state.value,
            "approval_request_id": self.approval_request_id,
        }


@dataclass
class AgentPlan:
    goal: str
    steps: List[PlanStep]
    completion_criteria: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "completion_criteria": list(self.completion_criteria),
        }


@dataclass(frozen=True)
class Observation:
    step_id: str
    ok: bool
    output: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "metadata": dict(self.metadata),
            "observed_at": self.observed_at.isoformat(),
        }


@dataclass(frozen=True)
class TaskCheckpoint:
    checkpoint_id: str
    task_id: str
    current_step: int
    step_states: Tuple[Tuple[str, str], ...]
    observation_count: int
    reason: str
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "current_step": self.current_step,
            "step_states": [list(item) for item in self.step_states],
            "observation_count": self.observation_count,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AgentTask:
    task_id: str
    goal: str
    context: Dict[str, Any]
    plan: AgentPlan
    state: TaskState = TaskState.PLANNED
    current_step: int = 0
    observations: List[Observation] = field(default_factory=list)
    checkpoints: List[TaskCheckpoint] = field(default_factory=list)
    final_summary: str = ""
    failure_reason: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def done(self) -> bool:
        return self.state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }

    @property
    def active_step(self) -> Optional[PlanStep]:
        if self.current_step < 0 or self.current_step >= len(self.plan.steps):
            return None
        return self.plan.steps[self.current_step]

    def touch(self) -> None:
        self.updated_at = utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "context": dict(self.context),
            "plan": self.plan.to_dict(),
            "state": self.state.value,
            "current_step": self.current_step,
            "observations": [item.to_dict() for item in self.observations],
            "checkpoints": [item.to_dict() for item in self.checkpoints],
            "final_summary": self.final_summary,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class RuntimeResult:
    task: AgentTask
    approval_token: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "approval_token": self.approval_token,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Phase 1: Adapter-level durable effect receipts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectIntent:
    """Pure record written before an external effect is attempted.

    Bound to the task, step, tool, arguments hash, and the caller's
    Idempotency-Key so a later receipt can be matched exactly and a stale
    worker cannot claim a different intent.
    """

    intent_id: str
    task_id: str
    step_id: str
    tool_name: str
    arguments_hash: str
    idempotency_key: str
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "arguments_hash": self.arguments_hash,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class EffectReceipt:
    """Record written after the external system has acknowledged the effect
    (or after the adapter has recorded that no provider-level idempotency
    was available).

    Status AMBIGUOUS is reserved for the runtime when an intent exists but
    no matching receipt can be found after a crash; adapters themselves
    should return SUCCEEDED or FAILED.
    """

    intent_id: str
    status: EffectStatus
    provider_receipt_id: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "status": self.status.value,
            "provider_receipt_id": self.provider_receipt_id,
            "raw_response": dict(self.raw_response),
            "recorded_at": self.recorded_at.isoformat(),
        }


@dataclass(frozen=True)
class AmbiguousOutcome:
    """Surfaced when an EffectIntent exists and no matching EffectReceipt
    can be found. The runtime must refuse automatic retry.
    """

    intent: EffectIntent
    reason: str = "ambiguous_external_effect"
    detail: str = (
        "An external effect was intended but no durable receipt was recorded. "
        "Automatic retry is refused; human inspection is required."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "reason": self.reason,
            "detail": self.detail,
        }
