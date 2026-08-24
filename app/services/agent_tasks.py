"""Durable application coordinator for DEVON Agent Runtime."""

from __future__ import annotations

import asyncio
import os
import secrets
import socket
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.devon import _queue as approvals
from app.api.v1.operator import _bridge as operator_bridge
from app.db.session import AsyncSessionLocal
from app.services.agent_effect_receipts import EffectReceiptRepository
from app.services.agent_runtime_persistence import (
    AgentLearningRepository,
    AgentTaskRepository,
    TaskExecutionLeaseLost,
)
from app.services.intelligence import get_provider
from app.services.leased_effect_recorder import LeasedEffectRecorder
from services.agent_runtime.contracts import AgentTask, PlanStep, TaskState, ToolCall
from services.agent_runtime.effect_recorder import EffectRecorder
from services.agent_runtime.planner import LLMPlanner, StaticPlanner
from services.agent_runtime.runtime import AgentRuntime
from services.agent_runtime.store import InMemoryAgentTaskStore
from services.agent_runtime.tools import ToolRegistry
from services.github.agent_adapter import GitHubCapabilityAdapter
from services.github.client import GitHubRESTClient
from services.operator.agent_adapter import OperatorCapabilityAdapter

github_client = GitHubRESTClient()


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    OperatorCapabilityAdapter(operator_bridge, approvals).register(registry)
    GitHubCapabilityAdapter(github_client, approvals).register(registry)
    return registry


def _lease_seconds() -> int:
    raw = os.getenv("DEVON_AGENT_TASK_LEASE_SECONDS", "120").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("DEVON_AGENT_TASK_LEASE_SECONDS must be an integer") from exc
    return max(15, min(value, 3600))


@dataclass(frozen=True)
class TaskRunOutcome:
    result: Dict[str, Any]
    idempotency_key: str
    replayed: bool


class DurableAgentTaskService:
    """Persist task transitions and fence execution across API workers."""

    def __init__(self) -> None:
        self.tasks = AgentTaskRepository()
        self.learning = AgentLearningRepository()
        self.effects = EffectReceiptRepository()
        self.worker_id = (
            f"{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(4)}"
        )

    async def create_task(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        planned_steps: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> AgentTask:
        clean_goal = (goal or "").strip()
        if not clean_goal:
            raise ValueError("agent goal is empty")

        tools = build_tool_registry()
        merged_context = dict(context or {})
        if project_id:
            merged_context["project_id"] = project_id
        merged_context["devon_learning"] = await self.learning.context_for(
            db,
            owner_id=owner_id,
            goal=clean_goal,
            project_id=project_id,
        )

        if planned_steps is not None:
            steps = self._steps_from_payload(planned_steps)
            planner = StaticPlanner(steps)
        else:
            planner = LLMPlanner(get_provider())

        plan = await planner.plan(clean_goal, merged_context, tools)
        task = AgentTask(
            task_id=f"TASK-{secrets.token_hex(6).upper()}",
            goal=clean_goal,
            context=merged_context,
            plan=plan,
        )
        await self.tasks.save(
            db,
            owner_id=owner_id,
            task=task,
            project_id=project_id,
        )
        return task

    async def get_task(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> Optional[AgentTask]:
        return await self.tasks.get_owned(db, owner_id=owner_id, task_id=task_id)

    async def list_tasks(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTask]:
        return await self.tasks.list_owned(
            db,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

    async def run_until_blocked(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        max_steps: int = 20,
        idempotency_key: Optional[str] = None,
    ) -> TaskRunOutcome:
        key = self._normalize_idempotency_key(idempotency_key)

        # Refuse automatic retry when a prior crash left an intent without a receipt.
        orphans = await self.effects.find_orphan_intents(
            db, owner_id=owner_id, task_id=task_id
        )
        if orphans:
            task = await self.tasks.get_owned(db, owner_id=owner_id, task_id=task_id)
            if task is not None and not task.done:
                task.state = TaskState.FAILED
                task.failure_reason = orphans[0].reason
                task.touch()
                await self.tasks.save(
                    db,
                    owner_id=owner_id,
                    task=task,
                    project_id=self._project_id(task),
                )
                await db.commit()
            raise RuntimeError(
                f"ambiguous_external_effect: {orphans[0].detail} "
                f"(intent_id={orphans[0].intent.intent_id})"
            )

        lease_seconds = _lease_seconds()
        claim = await self.tasks.acquire_execution(
            db,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key=key,
            max_steps=max_steps,
            lease_owner=self.worker_id,
            lease_seconds=lease_seconds,
        )
        if claim.replay_result is not None:
            return TaskRunOutcome(
                result=dict(claim.replay_result),
                idempotency_key=key,
                replayed=True,
            )
        if claim.task is None or claim.lease_token is None:
            raise TaskExecutionLeaseLost("execution claim is missing its fenced task state")

        # The lease must be durable before any capability adapter can execute.
        await db.commit()

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat_execution_lease(
                stop=stop_heartbeat,
                lost=lease_lost,
                owner_id=owner_id,
                task_id=task_id,
                run_id=claim.run_id,
                lease_token=claim.lease_token,
                lease_seconds=lease_seconds,
            )
        )
        try:
            recorder = LeasedEffectRecorder(
                db=db,
                owner_id=owner_id,
                lease_token=claim.lease_token,
                execution_generation=claim.execution_generation,
                repository=self.effects,
            )
            runtime = self._runtime_for(
                claim.task,
                effect_recorder=recorder,
                effect_idempotency_key=key,
            )
            result = await runtime.run_until_blocked(
                claim.task.task_id,
                max_steps=max_steps,
            )
            await self._stop_heartbeat(stop_heartbeat, heartbeat)
            if lease_lost.is_set():
                raise TaskExecutionLeaseLost(
                    "agent task lease renewal failed; stale result was not committed"
                )
            payload = result.to_dict()
            await self.tasks.complete_execution(
                db,
                owner_id=owner_id,
                run_id=claim.run_id,
                lease_token=claim.lease_token,
                task=result.task,
                result_payload=payload,
                project_id=self._project_id(result.task),
            )
            await db.commit()
            return TaskRunOutcome(
                result=payload,
                idempotency_key=key,
                replayed=False,
            )
        except Exception as exc:
            await self._stop_heartbeat(stop_heartbeat, heartbeat)
            await db.rollback()
            try:
                await self.tasks.fail_execution(
                    db,
                    owner_id=owner_id,
                    task_id=task_id,
                    run_id=claim.run_id,
                    lease_token=claim.lease_token,
                    error=str(exc),
                )
                await db.commit()
            except Exception:
                await db.rollback()
            raise

    async def cancel(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        reason: str,
    ) -> AgentTask:
        task = await self._required_for_mutation(
            db,
            owner_id=owner_id,
            task_id=task_id,
        )
        runtime = self._runtime_for(task)
        cancelled = runtime.cancel(task.task_id, reason=reason)
        await self.tasks.save(
            db,
            owner_id=owner_id,
            task=cancelled,
            project_id=self._project_id(cancelled),
        )
        return cancelled

    async def rollback(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        checkpoint_id: str,
    ) -> AgentTask:
        task = await self._required_for_mutation(
            db,
            owner_id=owner_id,
            task_id=task_id,
        )
        runtime = self._runtime_for(task)
        rewound = runtime.rollback_agent_state(task.task_id, checkpoint_id)
        await self.tasks.save(
            db,
            owner_id=owner_id,
            task=rewound,
            project_id=self._project_id(rewound),
        )
        return rewound

    async def delete_task(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> bool:
        return await self.tasks.delete_owned(db, owner_id=owner_id, task_id=task_id)

    def tool_catalog(self) -> Dict[str, object]:
        return {
            "tools": build_tool_registry().describe(),
            "operator": {
                "enabled": operator_bridge.enabled,
                "configured": operator_bridge.configured,
                "root": str(operator_bridge.root),
                "cwd_confinement_is_os_sandbox": False,
            },
            "github": {
                "configured": github_client.configured,
                "allowed_repositories": github_client.allowed_repositories,
                "api_url": github_client.base_url,
                "token_exposed": False,
            },
            "execution": {
                "shared_task_leases": True,
                "fencing_tokens": True,
                "idempotency_ledger": True,
                "lease_seconds": _lease_seconds(),
                "crash_atomic_external_effects": False,
                "effect_receipts": True,
            },
        }

    async def _required(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> AgentTask:
        task = await self.get_task(db, owner_id=owner_id, task_id=task_id)
        if task is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return task

    async def _required_for_mutation(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> AgentTask:
        task = await self.tasks.get_owned_for_mutation(
            db,
            owner_id=owner_id,
            task_id=task_id,
        )
        if task is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return task

    async def _heartbeat_execution_lease(
        self,
        *,
        stop: asyncio.Event,
        lost: asyncio.Event,
        owner_id: str,
        task_id: str,
        run_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> None:
        interval = max(5.0, lease_seconds / 3)
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            try:
                async with AsyncSessionLocal() as session:
                    renewed = await self.tasks.renew_execution(
                        session,
                        owner_id=owner_id,
                        task_id=task_id,
                        run_id=run_id,
                        lease_token=lease_token,
                        lease_seconds=lease_seconds,
                    )
                    if renewed:
                        await session.commit()
                    else:
                        await session.rollback()
                        lost.set()
                        return
            except Exception:
                lost.set()
                return

    @staticmethod
    async def _stop_heartbeat(stop: asyncio.Event, heartbeat: asyncio.Task) -> None:
        if heartbeat.done():
            await heartbeat
            return
        stop.set()
        await heartbeat

    @staticmethod
    def _normalize_idempotency_key(value: Optional[str]) -> str:
        if value is None:
            return f"auto-{secrets.token_hex(16)}"
        key = value.strip()
        if not key:
            raise ValueError("Idempotency-Key cannot be empty")
        if len(key) > 200:
            raise ValueError("Idempotency-Key exceeds 200 characters")
        return key

    @staticmethod
    def _runtime_for(
        task: AgentTask,
        *,
        effect_recorder: Optional[EffectRecorder] = None,
        effect_idempotency_key: str = "",
    ) -> AgentRuntime:
        store = InMemoryAgentTaskStore()
        store.put(task)
        planner = StaticPlanner(
            task.plan.steps,
            criteria=task.plan.completion_criteria,
        )
        return AgentRuntime(
            planner=planner,
            tools=build_tool_registry(),
            approvals=approvals,
            store=store,
            effect_recorder=effect_recorder,
            effect_idempotency_key=effect_idempotency_key,
        )

    @staticmethod
    def _project_id(task: AgentTask) -> Optional[str]:
        value = task.context.get("project_id")
        return str(value) if value else None

    @staticmethod
    def _steps_from_payload(raw_steps: Sequence[Dict[str, Any]]) -> List[PlanStep]:
        if not raw_steps:
            raise ValueError("explicit plan has no steps")
        if len(raw_steps) > 12:
            raise ValueError("explicit plan exceeds 12 steps")
        steps = []
        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"explicit plan step {index} is not an object")
            tool = str(raw.get("tool") or "").strip()
            title = str(raw.get("title") or "").strip()
            arguments = raw.get("arguments") or {}
            if not tool:
                raise ValueError(f"explicit plan step {index} has no tool")
            if not title:
                raise ValueError(f"explicit plan step {index} has no title")
            if not isinstance(arguments, dict):
                raise ValueError(f"explicit plan step {index} arguments are not an object")
            steps.append(
                PlanStep(
                    step_id=f"STEP-{index:02d}",
                    title=title,
                    tool_call=ToolCall(
                        name=tool,
                        arguments=dict(arguments),
                        reason=str(raw.get("reason") or ""),
                        expected_outcome=str(raw.get("expected_outcome") or ""),
                    ),
                )
            )
        return steps


agent_tasks_service = DurableAgentTaskService()
