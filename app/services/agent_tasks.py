"""Durable application coordinator for DEVON Agent Runtime."""

from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.devon import _queue as approvals
from app.api.v1.operator import _bridge as operator_bridge
from app.services.agent_runtime_persistence import (
    AgentLearningRepository,
    AgentTaskRepository,
)
from app.services.intelligence import get_provider
from services.agent_runtime.contracts import (
    AgentTask,
    PlanStep,
    RuntimeResult,
    ToolCall,
)
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


class DurableAgentTaskService:
    """Persist every externally visible task transition in PostgreSQL."""

    def __init__(self) -> None:
        self.tasks = AgentTaskRepository()
        self.learning = AgentLearningRepository()

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
    ) -> RuntimeResult:
        task = await self._required(db, owner_id=owner_id, task_id=task_id)
        runtime = self._runtime_for(task)
        result = await runtime.run_until_blocked(task.task_id, max_steps=max_steps)
        await self.tasks.save(
            db,
            owner_id=owner_id,
            task=result.task,
            project_id=self._project_id(result.task),
        )
        return result

    async def cancel(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        reason: str,
    ) -> AgentTask:
        task = await self._required(db, owner_id=owner_id, task_id=task_id)
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
        task = await self._required(db, owner_id=owner_id, task_id=task_id)
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

    @staticmethod
    def _runtime_for(task: AgentTask) -> AgentRuntime:
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
