"""Planning layer for DEVON Agent Runtime.

The planner may use an LLM, but model output is never trusted as executable
structure. Tool names, step count, and field types are validated before a plan
enters the runtime.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Protocol, Sequence

from services.agent_runtime.contracts import AgentPlan, PlanStep, ToolCall
from services.agent_runtime.tools import ToolRegistry
from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    extract_json,
)

MAX_PLAN_STEPS = 12


class Planner(Protocol):
    async def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        tools: ToolRegistry,
    ) -> AgentPlan: ...


class StaticPlanner:
    """Deterministic planner for tests and controlled workflows."""

    def __init__(self, steps: Sequence[PlanStep], *, criteria: Sequence[str] = ()) -> None:
        self._steps = list(steps)
        self._criteria = tuple(criteria)

    async def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        tools: ToolRegistry,
    ) -> AgentPlan:
        del context
        for step in self._steps:
            tools.require(step.tool_call.name)
        return AgentPlan(
            goal=goal,
            steps=[
                PlanStep(
                    step_id=step.step_id,
                    title=step.title,
                    tool_call=ToolCall(
                        name=step.tool_call.name,
                        arguments=dict(step.tool_call.arguments),
                        reason=step.tool_call.reason,
                        expected_outcome=step.tool_call.expected_outcome,
                    ),
                )
                for step in self._steps
            ],
            completion_criteria=self._criteria,
        )


class LLMPlanner:
    """Provider-backed planner with strict JSON validation."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        model: str | None = None,
        max_steps: int = MAX_PLAN_STEPS,
    ) -> None:
        self.provider = provider
        self.model = model
        self.max_steps = max(1, min(int(max_steps), MAX_PLAN_STEPS))

    async def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        tools: ToolRegistry,
    ) -> AgentPlan:
        clean_goal = (goal or "").strip()
        if not clean_goal:
            raise ValueError("agent goal is empty")

        catalog = tools.describe()
        if not catalog:
            raise ValueError("agent runtime has no registered tools")

        system = (
            "You are the planning component of DEVON Agent Runtime. "
            "DEVON governance is binding. Plan only with the supplied tools. "
            "Never invent a tool. Prefer the smallest verifiable sequence. "
            "Read actions may run automatically. Write and high-impact actions "
            "will stop for human approval. Blocked tools must never be selected. "
            "Return one JSON object only with keys steps and completion_criteria. "
            "Each step must contain title, tool, arguments, reason, and expected_outcome."
        )
        payload = {
            "goal": clean_goal,
            "context": context,
            "tools": catalog,
            "limits": {"max_steps": self.max_steps},
        }
        response = await self.provider.complete(
            CompletionRequest(
                system=system,
                messages=[
                    ChatMessage(
                        role="user",
                        content=json.dumps(payload, ensure_ascii=False, default=str),
                    )
                ],
                model=self.model,
                max_tokens=1800,
                temperature=0.1,
                json_mode=True,
                metadata={"component": "devon-agent-planner"},
            )
        )
        parsed = extract_json(response.text)
        return self._validate(clean_goal, parsed, tools)

    def _validate(
        self,
        goal: str,
        parsed: Dict[str, Any],
        tools: ToolRegistry,
    ) -> AgentPlan:
        raw_steps = parsed.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("planner returned no steps")
        if len(raw_steps) > self.max_steps:
            raise ValueError(
                f"planner returned {len(raw_steps)} steps; limit is {self.max_steps}"
            )

        steps: List[PlanStep] = []
        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"planner step {index} is not an object")
            title = str(raw.get("title") or "").strip()
            tool_name = str(raw.get("tool") or "").strip()
            arguments = raw.get("arguments", {})
            reason = str(raw.get("reason") or "").strip()
            expected = str(raw.get("expected_outcome") or "").strip()
            if not title:
                raise ValueError(f"planner step {index} has no title")
            if not tool_name:
                raise ValueError(f"planner step {index} has no tool")
            spec = tools.require(tool_name)
            if spec.risk.value == "blocked":
                raise ValueError(f"planner selected blocked tool: {tool_name}")
            if not isinstance(arguments, dict):
                raise ValueError(f"planner step {index} arguments are not an object")
            steps.append(
                PlanStep(
                    step_id=f"STEP-{index:02d}",
                    title=title,
                    tool_call=ToolCall(
                        name=tool_name,
                        arguments=dict(arguments),
                        reason=reason,
                        expected_outcome=expected,
                    ),
                )
            )

        raw_criteria = parsed.get("completion_criteria", [])
        if raw_criteria is None:
            raw_criteria = []
        if not isinstance(raw_criteria, list):
            raise ValueError("completion_criteria must be a list")
        criteria = tuple(str(item).strip() for item in raw_criteria if str(item).strip())
        return AgentPlan(goal=goal, steps=steps, completion_criteria=criteria)
