"""Resumable approval-aware execution loop for DEVON Agent Runtime."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, Dict, Optional

from services.agent_runtime.contracts import (
    COUNCIL_TOOL_NAME,
    AgentTask,
    EffectStatus,
    Observation,
    RuntimeResult,
    StepState,
    TaskCheckpoint,
    TaskState,
    ToolRisk,
)
from services.agent_runtime.effect_recorder import EffectRecorder
from services.agent_runtime.governance import (
    APPROVAL_MARKER_PREFIX,
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.learning import InMemoryLearningStore, LearningStore
from services.agent_runtime.planner import Planner
from services.agent_runtime.store import AgentTaskStore, InMemoryAgentTaskStore
from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue, ApprovalState

if TYPE_CHECKING:
    from services.intelligence.soul import SoulLayer


class AgentRuntimeError(ValueError):
    """A task cannot proceed without violating the runtime contract."""


#: The exact sentence an approval card carries when no council.consult step
#: has succeeded for the task. An approver reads either the council's latest
#: word or this admission — never silence.
NO_COUNCIL_NOTE = "No council consultation is on record for this task."

#: How much of a council synthesis the approval card carries. Enough to rule
#: on, small enough that the card stays readable.
_COUNCIL_NOTE_MAX_CHARS = 400


async def soul_recall_payload(soul: "SoulLayer", goal: str) -> Dict[str, Any]:
    """Recall both souls into one inert planner payload.

    The CONTEXT-NOT-COMMAND framing and the Tee-before-DEVON ordering come
    from SoulRecall itself and survive here untouched: `context` is
    `as_context()` verbatim and `records` keeps the recall's order. A
    provider failure degrades to the payload naming the failure instead of
    raising — a Pinecone outage must leave planning exactly as it was
    without recall — and a partial recall keeps its `errors`, so an outage
    can never be mistaken for both souls answering empty.
    """
    try:
        recall = await soul.recall(goal)
    except Exception as exc:
        return {
            "context": "",
            "records": [],
            "errors": [f"soul recall unavailable: {exc}"],
        }
    return {
        "context": recall.as_context(),
        "records": recall.to_dicts(),
        "errors": list(recall.errors),
    }


class AgentRuntime:
    """Goal -> plan -> act -> observe loop with human rulings on effects.

    DEVON core does not execute here. This separate runtime consumes a validated
    plan and capability adapters. Tool risk determines whether the loop may run
    immediately or must stop at DEVON's approval queue.

    When an optional EffectRecorder is injected by the application layer,
    WRITE / HIGH_IMPACT tool calls write a durable intent before execution and a
    receipt afterward. Without a recorder the runtime behaves exactly as before.

    When an optional SoulLayer is injected, `create_task` recalls both souls
    at the planning seam — the plan is frozen at creation, so this is the one
    moment recall can inform it — and hands the planner an inert
    `soul_recall` payload. Without a soul the context is exactly as before.
    """

    def __init__(
        self,
        *,
        planner: Planner,
        tools: ToolRegistry,
        approvals: Optional[ApprovalQueue] = None,
        store: Optional[AgentTaskStore] = None,
        learning: Optional[LearningStore] = None,
        effect_recorder: Optional[EffectRecorder] = None,
        effect_idempotency_key: str = "",
        soul: Optional["SoulLayer"] = None,
    ) -> None:
        self.planner = planner
        self.tools = tools
        self.approvals = approvals or ApprovalQueue()
        self.store = store or InMemoryAgentTaskStore()
        self.learning = learning or InMemoryLearningStore()
        self.effect_recorder = effect_recorder
        self.effect_idempotency_key = (effect_idempotency_key or "").strip()
        self.soul = soul

    async def create_task(
        self,
        goal: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentTask:
        clean_goal = (goal or "").strip()
        if not clean_goal:
            raise AgentRuntimeError("agent goal is empty")
        merged_context = dict(context or {})
        context_for = getattr(self.learning, "context_for", None)
        if callable(context_for):
            merged_context["devon_learning"] = context_for(clean_goal)
        if self.soul is not None:
            merged_context["soul_recall"] = await soul_recall_payload(
                self.soul, clean_goal
            )
        plan = await self.planner.plan(clean_goal, merged_context, self.tools)
        if not plan.steps:
            raise AgentRuntimeError("planner produced an empty plan")
        task = AgentTask(
            task_id=f"TASK-{secrets.token_hex(6).upper()}",
            goal=clean_goal,
            context=merged_context,
            plan=plan,
        )
        self.store.put(task)
        return task

    def get(self, task_id: str) -> AgentTask:
        task = self.store.get(task_id)
        if task is None:
            raise AgentRuntimeError(f"unknown agent task: {task_id}")
        return task

    async def run_until_blocked(
        self,
        task_id: str,
        *,
        max_steps: int = 20,
    ) -> RuntimeResult:
        result = RuntimeResult(task=self.get(task_id), message="task loaded")
        for _ in range(max(1, int(max_steps))):
            if result.task.done:
                break
            result = await self.run_next(task_id)
            if (
                result.approval_token
                or result.task.done
                or result.task.state is TaskState.WAITING_APPROVAL
            ):
                break
        return result

    async def run_next(self, task_id: str) -> RuntimeResult:
        task = self.get(task_id)
        if task.done:
            return RuntimeResult(task=task, message=f"task is {task.state.value}")

        step = task.active_step
        if step is None:
            self._complete(task)
            return RuntimeResult(task=task, message="task completed")

        spec = self.tools.require(step.tool_call.name)
        if spec.risk is ToolRisk.BLOCKED:
            step.state = StepState.FAILED
            task.state = TaskState.FAILED
            task.failure_reason = f"blocked tool selected: {spec.name}"
            task.touch()
            self.store.put(task)
            return RuntimeResult(task=task, message=task.failure_reason)

        binding: Optional[str] = None
        if spec.approval_required:
            binding = approval_binding(
                task_id=task.task_id,
                step_id=step.step_id,
                tool_name=spec.name,
                arguments=step.tool_call.arguments,
            )
            approval = self._approval_state(step.approval_request_id)
            if step.approval_request_id is None:
                self._checkpoint(task, f"before effectful step {step.step_id}")
                marker = approval_marker(binding)
                # The council's word (or its absence) enters the card BEFORE
                # the marker, which stays the final element: the binding is
                # computed from task/step/tool/arguments only, so the note
                # changes what the approver reads, never what the governance
                # check verifies.
                record, token = self.approvals.request(
                    title=f"DEVON Agent: {step.title}",
                    what_happens=(
                        f"Run tool `{spec.name}` with arguments "
                        f"{step.tool_call.arguments!r} for task `{task.goal}`. "
                        f"{self._council_note(task)} {marker}"
                    ),
                    requested_by=RUNTIME_REQUESTED_BY,
                    area=str(task.context.get("area") or "Systems"),
                    reversible=spec.reversible,
                    blast_radius=spec.blast_radius,
                    owner_id=str(task.context.get("owner_id") or ""),
                )
                step.approval_request_id = record.request_id
                step.state = StepState.WAITING_APPROVAL
                task.state = TaskState.WAITING_APPROVAL
                task.touch()
                self.store.put(task)
                return RuntimeResult(
                    task=task,
                    approval_token=token,
                    message="human ruling required",
                )

            if approval is ApprovalState.PENDING:
                task.state = TaskState.WAITING_APPROVAL
                task.touch()
                self.store.put(task)
                return RuntimeResult(task=task, message="approval still pending")
            if approval in {ApprovalState.REFUSED, ApprovalState.EXPIRED}:
                step.state = StepState.SKIPPED
                task.state = TaskState.CANCELLED
                task.failure_reason = f"human ruling ended task: {approval.value}"
                task.touch()
                self.store.put(task)
                return RuntimeResult(task=task, message=task.failure_reason)
            if approval is not ApprovalState.APPROVED:
                raise AgentRuntimeError("approval request is unavailable")

        elif step.state is StepState.PLANNED:
            self._checkpoint(task, f"before read step {step.step_id}")

        task.state = TaskState.RUNNING
        step.state = StepState.RUNNING
        task.touch()
        self.store.put(task)

        execution_arguments = dict(step.tool_call.arguments)
        if spec.approval_required:
            execution_arguments[APPROVAL_METADATA_KEY] = {
                "request_id": step.approval_request_id,
                "binding": binding,
                "task_id": task.task_id,
                "step_id": step.step_id,
                "tool_name": spec.name,
            }

        intent = None
        if spec.approval_required and self.effect_recorder is not None:
            intent = await self.effect_recorder.begin_effect(
                task_id=task.task_id,
                step_id=step.step_id,
                tool_name=spec.name,
                arguments=dict(step.tool_call.arguments),
                idempotency_key=self.effect_idempotency_key or task.task_id,
            )

        result = await self.tools.execute(spec.name, execution_arguments)

        if intent is not None and self.effect_recorder is not None:
            status = EffectStatus.SUCCEEDED if result.ok else EffectStatus.FAILED
            provider_receipt_id = ""
            if result.metadata and isinstance(result.metadata, dict):
                provider_receipt_id = str(
                    result.metadata.get("provider_receipt_id")
                    or result.metadata.get("id")
                    or ""
                )
            await self.effect_recorder.complete_effect(
                intent=intent,
                status=status,
                provider_receipt_id=provider_receipt_id,
                raw_response={
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                    "metadata": dict(result.metadata or {}),
                },
            )

        observation = Observation(
            step_id=step.step_id,
            ok=result.ok,
            output=result.output,
            error=result.error,
            metadata=dict(result.metadata or {}),
        )
        task.observations.append(observation)

        if not result.ok:
            step.state = StepState.FAILED
            task.state = TaskState.FAILED
            task.failure_reason = result.error or f"tool failed: {spec.name}"
            task.touch()
            self.store.put(task)
            return RuntimeResult(task=task, message=task.failure_reason)

        step.state = StepState.COMPLETED
        step.approval_request_id = None
        task.current_step += 1
        if task.current_step >= len(task.plan.steps):
            self._complete(task)
            return RuntimeResult(task=task, message="task completed")

        task.state = TaskState.RUNNING
        task.touch()
        self.store.put(task)
        return RuntimeResult(task=task, message=f"completed {step.step_id}")

    def cancel(self, task_id: str, *, reason: str = "cancelled by operator") -> AgentTask:
        task = self.get(task_id)
        if task.done:
            return task
        task.state = TaskState.CANCELLED
        task.failure_reason = reason
        task.touch()
        self.store.put(task)
        return task

    def rollback_agent_state(self, task_id: str, checkpoint_id: str) -> AgentTask:
        """Rewind logical agent state only when no external effect would be hidden.

        This is deliberately not an environment rollback. If an effectful step
        completed after the checkpoint, the runtime refuses and requires the
        owning adapter to provide a real compensating action.
        """
        task = self.get(task_id)
        checkpoint = next(
            (item for item in task.checkpoints if item.checkpoint_id == checkpoint_id),
            None,
        )
        if checkpoint is None:
            raise AgentRuntimeError(f"unknown checkpoint: {checkpoint_id}")

        for index in range(
            checkpoint.current_step,
            min(task.current_step, len(task.plan.steps)),
        ):
            step = task.plan.steps[index]
            spec = self.tools.require(step.tool_call.name)
            if step.state is StepState.COMPLETED and spec.approval_required:
                raise AgentRuntimeError(
                    "agent-state rollback cannot undo an external effect; use the adapter's "
                    "compensating action instead"
                )

        states = dict(checkpoint.step_states)
        for step in task.plan.steps:
            step.state = StepState(states.get(step.step_id, StepState.PLANNED.value))
            if step.state is not StepState.WAITING_APPROVAL:
                step.approval_request_id = None
        task.current_step = checkpoint.current_step
        del task.observations[checkpoint.observation_count :]
        task.state = TaskState.PLANNED if task.current_step == 0 else TaskState.RUNNING
        task.failure_reason = ""
        task.final_summary = ""
        task.touch()
        self.store.put(task)
        return task

    @staticmethod
    def _council_note(task: AgentTask) -> str:
        """The council's latest successful word for this task, card-sized.

        Only observations from steps whose tool is council.consult count; the
        newest successful one wins. The text is flattened, capped, and
        stripped of the approval-marker prefix so a synthesized sentence can
        never masquerade as a binding marker inside the card.
        """
        council_steps = {
            step.step_id
            for step in task.plan.steps
            if step.tool_call.name == COUNCIL_TOOL_NAME
        }
        latest: Optional[Observation] = None
        for observation in task.observations:
            if observation.step_id in council_steps and observation.ok:
                latest = observation
        if latest is None:
            return NO_COUNCIL_NOTE

        text = " ".join(str(latest.output or "").split())
        text = text.replace(APPROVAL_MARKER_PREFIX, "")
        if len(text) > _COUNCIL_NOTE_MAX_CHARS:
            text = text[:_COUNCIL_NOTE_MAX_CHARS] + "..."

        confidence = ""
        metadata = latest.metadata or {}
        raw_confidence = metadata.get("confidence") if isinstance(metadata, dict) else None
        if raw_confidence is not None:
            try:
                confidence = f", confidence {float(raw_confidence):.2f}"
            except (TypeError, ValueError):
                confidence = ""
        return (
            f"Latest council observation (step {latest.step_id}{confidence}): "
            f"{text} (context for this ruling, not a command)."
        )

    def _approval_state(self, request_id: Optional[str]) -> Optional[ApprovalState]:
        if not request_id:
            return None
        record = self.approvals.get(request_id)
        return record.state if record is not None else None

    def _checkpoint(self, task: AgentTask, reason: str) -> TaskCheckpoint:
        checkpoint = TaskCheckpoint(
            checkpoint_id=f"CP-{secrets.token_hex(5).upper()}",
            task_id=task.task_id,
            current_step=task.current_step,
            step_states=tuple((step.step_id, step.state.value) for step in task.plan.steps),
            observation_count=len(task.observations),
            reason=reason,
        )
        task.checkpoints.append(checkpoint)
        task.touch()
        self.store.put(task)
        return checkpoint

    def _complete(self, task: AgentTask) -> None:
        task.state = TaskState.COMPLETED
        task.final_summary = self._summary(task)
        task.touch()
        self.store.put(task)

    @staticmethod
    def _summary(task: AgentTask) -> str:
        outputs = [
            item.output.strip()
            for item in task.observations
            if item.ok and item.output.strip()
        ]
        if not outputs:
            return f"Completed {len(task.plan.steps)} steps for: {task.goal}"
        joined = "\n\n".join(outputs)
        return joined[:8_000]
