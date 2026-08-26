"""Planning layer for DEVON Agent Runtime.

The planner may use an LLM, but model output is never trusted as executable
structure. Tool names, step count, and field types are validated before a plan
enters the runtime.

A model that answers in the wrong shape is a format slip, not a governance
event. One such slip — `completion_criteria` arriving as something other than a
list — earns exactly one correction request to the same provider, after which
the identical validation runs again. Nothing about the rules relaxes for the
second answer: the repair path changes what DEVON does with a violation, never
what counts as one. Every other rejection (an unknown tool, a blocked tool, a
missing title, too many steps) still fails on the first answer, because those
are refusals rather than typos and a retry would only invite the model to try
the same door again.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Protocol, Sequence

from services.agent_runtime.contracts import AgentPlan, PlanStep, ToolCall
from services.agent_runtime.tools import ToolRegistry
from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)

logger = logging.getLogger(__name__)

MAX_PLAN_STEPS = 12

#: The plan contract, stated to the model in both the first request and the
#: correction. `completion_criteria` is a list of strings — the single field
#: whose type violation is repairable.
PLAN_CONTRACT = (
    '{"steps": [{"title": "...", "tool": "...", "arguments": {}, '
    '"reason": "...", "expected_outcome": "..."}], '
    '"completion_criteria": ["criterion one"]}'
)

CRITERIA_FIELD = "completion_criteria"


class PlannerContractError(ValueError):
    """The provider could not produce a valid plan contract, twice.

    Subclasses ValueError so the existing API mapping (422, not a 500) holds
    without touching the route.

    The string form is the operator-facing sentence and nothing else. The goal,
    the assembled context (which carries soul recall — Tee's own rulings), and
    the raw model output never reach it, because this message is rendered in the
    Command Center and returned over HTTP. The provider, field, and failure
    category ride as structured attributes for the server log instead.
    """

    MESSAGE = (
        "DEVON received a malformed plan from the active intelligence provider. "
        "One repair attempt failed. No action was executed."
    )

    def __init__(self, *, provider: str, field: str, category: str) -> None:
        self.provider = provider
        self.field = field
        self.category = category
        super().__init__(self.MESSAGE)

    def as_dict(self) -> Dict[str, str]:
        """The safe triple, for logs and structured reporting."""
        return {
            "provider": self.provider,
            "field": self.field,
            "category": self.category,
        }


class _CriteriaTypeError(ValueError):
    """Internal: `completion_criteria` was not a list.

    The one violation the planner will ask the provider to correct. It never
    escapes `plan()` — it is either repaired or reraised as a
    PlannerContractError.
    """


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
            "Return one JSON object only, in exactly this shape: "
            f"{PLAN_CONTRACT} "
            "steps is a non-empty list of objects, each with title, tool, "
            "arguments, reason, and expected_outcome. completion_criteria is "
            "always a list of strings; send an empty list when there are none."
        )
        payload = {
            "goal": clean_goal,
            "context": context,
            "tools": catalog,
            "limits": {"max_steps": self.max_steps},
        }
        prompt = json.dumps(payload, ensure_ascii=False, default=str)
        response = await self.provider.complete(
            CompletionRequest(
                system=system,
                messages=[ChatMessage(role="user", content=prompt)],
                model=self.model,
                max_tokens=1800,
                temperature=0.1,
                json_mode=True,
                metadata={"component": "devon-agent-planner"},
            )
        )
        parsed = extract_json(response.text)
        try:
            return self._validate(clean_goal, parsed, tools)
        except _CriteriaTypeError:
            # The one repairable slip. Every other rejection has already raised
            # past this handler and stays a first-answer failure.
            pass
        return await self._repair(clean_goal, system, prompt, response.text, tools)

    async def _repair(
        self,
        goal: str,
        system: str,
        prompt: str,
        previous_text: str,
        tools: ToolRegistry,
    ) -> AgentPlan:
        """One correction request to the same provider, then the same rules again.

        The correction names the offending field and the required type; it never
        restates the goal or the context, so a repair cannot become a second
        channel for prompt content. `previous_text` goes back only to the
        provider that just produced it.
        """
        provider_name = str(getattr(self.provider, "name", "unknown"))

        def stop(category: str) -> PlannerContractError:
            error = PlannerContractError(
                provider=provider_name, field=CRITERIA_FIELD, category=category
            )
            logger.error(
                "planner contract failure provider=%s field=%s category=%s",
                error.provider,
                error.field,
                error.category,
            )
            return error

        correction = CompletionRequest(
            system=system,
            messages=[
                ChatMessage(role="user", content=prompt),
                ChatMessage(role="assistant", content=previous_text),
                ChatMessage(
                    role="user",
                    content=(
                        f"Your previous reply set {CRITERIA_FIELD} to the wrong "
                        f"type. {CRITERIA_FIELD} must be a JSON list of strings, "
                        "for example [\"criterion one\"]; use an empty list if "
                        "there are no criteria. Reply again with ONLY the "
                        f"corrected single JSON object in this shape: {PLAN_CONTRACT}"
                    ),
                ),
            ],
            model=self.model,
            max_tokens=1800,
            temperature=0.0,
            json_mode=True,
            metadata={"component": "devon-agent-planner", "repair": True},
        )

        try:
            repaired = await self.provider.complete(correction)
        except ProviderError as exc:
            raise stop("provider_error_on_repair") from exc

        try:
            reparsed = extract_json(repaired.text)
        except ValueError as exc:
            raise stop("unparsable_repair") from exc

        try:
            return self._validate(goal, reparsed, tools)
        except _CriteriaTypeError as exc:
            raise stop("invalid_type") from exc

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

        # An absent key and an explicit null both mean "no criteria". That
        # leniency predates the repair path and is kept deliberately: a benign
        # omission should not cost a provider round-trip. A wrong *type* —
        # string, object, number — is the repairable slip, and it raises the
        # internal error `plan()` watches for rather than failing outright.
        raw_criteria = parsed.get(CRITERIA_FIELD, [])
        if raw_criteria is None:
            raw_criteria = []
        if not isinstance(raw_criteria, list):
            raise _CriteriaTypeError(f"{CRITERIA_FIELD} must be a list")
        criteria = tuple(str(item).strip() for item in raw_criteria if str(item).strip())
        return AgentPlan(goal=goal, steps=steps, completion_criteria=criteria)
