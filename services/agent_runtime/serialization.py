"""Round-trip helpers for durable DEVON Agent Runtime task snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from services.agent_runtime.contracts import (
    AgentPlan,
    AgentTask,
    Observation,
    PlanStep,
    StepState,
    TaskCheckpoint,
    TaskState,
    ToolCall,
)


def _dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError("durable task snapshot has an invalid datetime")
    return datetime.fromisoformat(value)


def task_from_dict(payload: Dict[str, Any]) -> AgentTask:
    """Restore one task from its canonical ``AgentTask.to_dict`` shape."""
    if not isinstance(payload, dict):
        raise ValueError("durable task snapshot is not an object")

    raw_plan = payload.get("plan")
    if not isinstance(raw_plan, dict):
        raise ValueError("durable task snapshot has no plan")

    steps = []
    for raw_step in raw_plan.get("steps") or []:
        raw_call = raw_step.get("tool_call") or {}
        steps.append(
            PlanStep(
                step_id=str(raw_step["step_id"]),
                title=str(raw_step["title"]),
                tool_call=ToolCall(
                    name=str(raw_call["name"]),
                    arguments=dict(raw_call.get("arguments") or {}),
                    reason=str(raw_call.get("reason") or ""),
                    expected_outcome=str(raw_call.get("expected_outcome") or ""),
                ),
                state=StepState(str(raw_step.get("state") or StepState.PLANNED.value)),
                approval_request_id=raw_step.get("approval_request_id"),
            )
        )

    observations = [
        Observation(
            step_id=str(item["step_id"]),
            ok=bool(item.get("ok")),
            output=str(item.get("output") or ""),
            error=str(item.get("error") or ""),
            metadata=dict(item.get("metadata") or {}),
            observed_at=_dt(item["observed_at"]),
        )
        for item in payload.get("observations") or []
    ]

    checkpoints = [
        TaskCheckpoint(
            checkpoint_id=str(item["checkpoint_id"]),
            task_id=str(item["task_id"]),
            current_step=int(item.get("current_step", 0)),
            step_states=tuple(
                (str(pair[0]), str(pair[1])) for pair in item.get("step_states") or []
            ),
            observation_count=int(item.get("observation_count", 0)),
            reason=str(item.get("reason") or ""),
            created_at=_dt(item["created_at"]),
        )
        for item in payload.get("checkpoints") or []
    ]

    plan = AgentPlan(
        goal=str(raw_plan.get("goal") or payload.get("goal") or ""),
        steps=steps,
        completion_criteria=tuple(str(item) for item in raw_plan.get("completion_criteria") or []),
    )
    return AgentTask(
        task_id=str(payload["task_id"]),
        goal=str(payload["goal"]),
        context=dict(payload.get("context") or {}),
        plan=plan,
        state=TaskState(str(payload.get("state") or TaskState.PLANNED.value)),
        current_step=int(payload.get("current_step", 0)),
        observations=observations,
        checkpoints=checkpoints,
        final_summary=str(payload.get("final_summary") or ""),
        failure_reason=str(payload.get("failure_reason") or ""),
        created_at=_dt(payload["created_at"]),
        updated_at=_dt(payload["updated_at"]),
    )
