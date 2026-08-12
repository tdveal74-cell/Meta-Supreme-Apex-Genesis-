"""
Workflow engine — deterministic execution with human approval gates.

The engine is pure and stateless: it takes a validated definition, the
results already recorded for this run, and the approvals granted so far, then
runs as far as it honestly can. It stops in three situations:

- an effect step has no approval decision yet  → `awaiting_approval`
- an effect step was rejected                  → `halted`
- a handler raised                             → `failed`

Resuming is the same call with more results and more approvals, so a run can
sit paused for days without the engine holding any state. The app layer owns
persistence and supplies the handlers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
)

from services.workflows.definition import (
    StepType,
    WorkflowDefinition,
    WorkflowStep,
    render_template,
)


class StepStatus:
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RunStatus:
    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaiting_approval"
    HALTED = "halted"
    FAILED = "failed"


APPROVED = "approved"
REJECTED = "rejected"


@dataclass(frozen=True)
class StepOutput:
    """What a handler returns. `summary` is what later steps interpolate."""

    summary: str
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class StepContext:
    """Everything a handler needs — config already rendered."""

    step: WorkflowStep
    config: Dict[str, Any]
    trigger_input: str
    results: Dict[str, Dict[str, Any]]


StepHandler = Callable[[StepContext], Awaitable[StepOutput]]


@dataclass(frozen=True)
class StepResult:
    step_id: str
    step_type: str
    status: str
    summary: str = ""
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "status": self.status,
            "summary": self.summary,
            "text": self.text,
            "data": dict(self.data),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StepResult":
        return cls(
            step_id=str(raw.get("step_id", "")),
            step_type=str(raw.get("step_type", "")),
            status=str(raw.get("status", StepStatus.COMPLETED)),
            summary=str(raw.get("summary", "") or ""),
            text=str(raw.get("text", "") or ""),
            data=dict(raw.get("data") or {}),
            input_tokens=int(raw.get("input_tokens") or 0),
            output_tokens=int(raw.get("output_tokens") or 0),
            latency_ms=int(raw.get("latency_ms") or 0),
            error=raw.get("error"),
        )


@dataclass(frozen=True)
class RunOutcome:
    status: str
    results: List[StepResult]
    pending_step_id: Optional[str] = None
    error: Optional[str] = None

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.results)

    @property
    def output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.results)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def latency_ms(self) -> int:
        return sum(r.latency_ms for r in self.results)

    @property
    def is_terminal(self) -> bool:
        return self.status != RunStatus.AWAITING_APPROVAL

    def token_usage(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }

    def results_as_dicts(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.results]


class WorkflowEngine:
    """
    Executes workflow steps in order against injected handlers.

    `require_approval_for_effects=False` exists for tests and for a future
    trusted-automation mode; the product default is True and the API does not
    expose a way to turn it off.
    """

    def __init__(
        self,
        handlers: Mapping[StepType, StepHandler],
        *,
        require_approval_for_effects: bool = True,
    ) -> None:
        self._handlers = dict(handlers)
        self._require_approval = require_approval_for_effects

    async def run(
        self,
        definition: WorkflowDefinition,
        *,
        trigger_input: str = "",
        prior_results: Iterable[Any] = (),
        approvals: Optional[Mapping[str, str]] = None,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> RunOutcome:
        results: List[StepResult] = [
            r if isinstance(r, StepResult) else StepResult.from_dict(r)
            for r in prior_results
        ]
        approvals = dict(approvals or {})
        completed_ids = {r.step_id for r in results}

        def emit(event_type: str, **payload: Any) -> None:
            if on_event is not None:
                on_event({"type": event_type, **payload})

        if not definition.steps:
            emit("run_failed", error="This workflow has no steps yet")
            return RunOutcome(
                status=RunStatus.FAILED,
                results=results,
                error="This workflow has no steps yet",
            )

        emit(
            "run_started",
            steps=len(definition.steps),
            resumed=bool(results),
            awaiting_approvals=[s.id for s in definition.effect_steps],
        )

        for step in definition.steps:
            if step.id in completed_ids:
                continue

            if step.is_effect and self._require_approval:
                decision = approvals.get(step.id)
                if decision is None:
                    emit(
                        "awaiting_approval",
                        step_id=step.id,
                        step_type=step.type.value,
                        preview=self._preview(step, trigger_input, results),
                    )
                    return RunOutcome(
                        status=RunStatus.AWAITING_APPROVAL,
                        results=results,
                        pending_step_id=step.id,
                    )
                if decision == REJECTED:
                    results.append(
                        StepResult(
                            step_id=step.id,
                            step_type=step.type.value,
                            status=StepStatus.REJECTED,
                            summary="Rejected by the workflow owner — run halted "
                            "before this step.",
                        )
                    )
                    emit("step_rejected", step_id=step.id, step_type=step.type.value)
                    emit("run_halted", step_id=step.id)
                    return RunOutcome(status=RunStatus.HALTED, results=results)

            handler = self._handlers.get(step.type)
            if handler is None:
                message = f"No handler registered for step type {step.type.value!r}"
                results.append(
                    StepResult(
                        step_id=step.id,
                        step_type=step.type.value,
                        status=StepStatus.FAILED,
                        error=message,
                    )
                )
                emit("step_failed", step_id=step.id, error=message)
                emit("run_failed", error=message)
                return RunOutcome(
                    status=RunStatus.FAILED, results=results, error=message
                )

            emit("step_started", step_id=step.id, step_type=step.type.value)
            context = StepContext(
                step=step,
                config=render_template(
                    step.config,
                    trigger_input=trigger_input,
                    results=self._result_map(results),
                ),
                trigger_input=trigger_input,
                results=self._result_map(results),
            )

            started = time.perf_counter()
            try:
                output = await handler(context)
            except Exception as exc:  # handler failures are recorded, never hidden
                latency_ms = int((time.perf_counter() - started) * 1000)
                message = f"{type(exc).__name__}: {exc}"
                results.append(
                    StepResult(
                        step_id=step.id,
                        step_type=step.type.value,
                        status=StepStatus.FAILED,
                        latency_ms=latency_ms,
                        error=message,
                    )
                )
                emit("step_failed", step_id=step.id, error=message)
                emit("run_failed", error=message)
                return RunOutcome(
                    status=RunStatus.FAILED, results=results, error=message
                )

            latency_ms = int((time.perf_counter() - started) * 1000)
            results.append(
                StepResult(
                    step_id=step.id,
                    step_type=step.type.value,
                    status=StepStatus.COMPLETED,
                    summary=output.summary,
                    text=output.text,
                    data=dict(output.data),
                    input_tokens=output.input_tokens,
                    output_tokens=output.output_tokens,
                    latency_ms=latency_ms,
                )
            )
            emit(
                "step_completed",
                step_id=step.id,
                step_type=step.type.value,
                latency_ms=latency_ms,
                total_tokens=output.input_tokens + output.output_tokens,
            )

        emit("run_completed", steps=len(results))
        return RunOutcome(status=RunStatus.COMPLETED, results=results)

    def _preview(
        self,
        step: WorkflowStep,
        trigger_input: str,
        results: Sequence[StepResult],
    ) -> Dict[str, Any]:
        """
        The rendered config a human is being asked to approve — so the gate
        shows exactly what would be written, not the template that produced it.
        """
        return render_template(
            step.config,
            trigger_input=trigger_input,
            results=self._result_map(results),
        )

    @staticmethod
    def _result_map(results: Sequence[StepResult]) -> Dict[str, Dict[str, Any]]:
        return {
            r.step_id: {"summary": r.summary, "text": r.text or r.summary}
            for r in results
            if r.status == StepStatus.COMPLETED
        }
