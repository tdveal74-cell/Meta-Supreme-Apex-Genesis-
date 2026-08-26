"""The planner's one-shot repair path for a malformed plan contract.

A model that answers in the wrong shape gets exactly one correction request to
the same provider, then faces the identical validator. These tests pin the
boundary in both directions: a repairable slip is repaired, and everything else
still fails on the first answer. The validator is never relaxed for the second
response.

The load-bearing safety property is the last one: nothing executes until a plan
has passed validation, so a provider that never produces a valid contract can
cost tokens but can never cost an action.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.planner import (
    CRITERIA_FIELD,
    LLMPlanner,
    PlannerContractError,
)
from services.agent_runtime.runtime import AgentRuntime
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolRisk, ToolSpec
from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    TokenUsage,
)

VALID_STEP = (
    '{"title":"Inspect","tool":"repo.inspect","arguments":{},'
    '"reason":"need evidence","expected_outcome":"status"}'
)


def plan_json(criteria: str) -> str:
    """A structurally valid plan whose completion_criteria is `criteria` verbatim."""
    return f'{{"steps":[{VALID_STEP}],"{CRITERIA_FIELD}":{criteria}}}'


class ScriptedProvider(AIProvider):
    """Returns queued replies in order and records every request it received."""

    name = "scripted-test"

    def __init__(self, *replies: str) -> None:
        super().__init__(default_model="scripted-test", max_retries=0)
        self._replies = list(replies)
        self.requests: list[CompletionRequest] = []

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if not self._replies:
            raise AssertionError(
                "planner asked for more completions than the test scripted; "
                "the repair path must attempt exactly one correction"
            )
        return CompletionResponse(
            text=self._replies.pop(0),
            usage=TokenUsage(),
            model="scripted-test",
            provider=self.name,
        )


class ExplodingRepairProvider(AIProvider):
    """Answers once, then fails the way a provider outage does."""

    name = "exploding-test"

    def __init__(self, first: str) -> None:
        super().__init__(default_model="exploding-test", max_retries=0)
        self._first = first
        self.calls = 0

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        del request
        self.calls += 1
        if self.calls == 1:
            return CompletionResponse(
                text=self._first,
                usage=TokenUsage(),
                model="exploding-test",
                provider=self.name,
            )
        raise ProviderError("upstream is down", provider=self.name)


def build_tools() -> tuple[ToolRegistry, list[str]]:
    """A registry whose one tool records every invocation."""
    invoked: list[str] = []

    def handler(args: dict) -> ToolResult:
        invoked.append("repo.inspect")
        return ToolResult(ok=True, output="ok")

    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.inspect",
            description="Inspect",
            risk=ToolRisk.READ,
            handler=handler,
        )
    )
    return tools, invoked


# ---------------------------------------------------------------------------
# 1. A correct list is accepted, with no correction request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_list_is_accepted_without_a_repair_attempt() -> None:
    tools, _ = build_tools()
    provider = ScriptedProvider(plan_json('["status captured"]'))

    plan = await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert plan.completion_criteria == ("status captured",)
    assert plan.steps[0].tool_call.name == "repo.inspect"
    # The happy path must not cost a second round-trip.
    assert len(provider.requests) == 1
    assert provider.requests[0].metadata.get("repair") is None


# ---------------------------------------------------------------------------
# 2. A string is repaired into a valid regenerated plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_string_criteria_is_repaired_into_a_valid_plan() -> None:
    tools, _ = build_tools()
    provider = ScriptedProvider(
        plan_json('"status captured"'),  # wrong type: a bare string
        plan_json('["status captured"]'),  # the corrected answer
    )

    plan = await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert plan.completion_criteria == ("status captured",)
    assert plan.steps[0].tool_call.name == "repo.inspect"
    assert len(provider.requests) == 2

    repair = provider.requests[1]
    assert repair.metadata.get("repair") is True
    # The correction goes to the same provider, carrying the model's own bad
    # answer back to the model that produced it.
    assert repair.messages[1].role == "assistant"
    assert repair.messages[1].content == plan_json('"status captured"')
    # It names the field and the required type.
    assert CRITERIA_FIELD in repair.messages[-1].content


# ---------------------------------------------------------------------------
# 3. An object is rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_object_criteria_is_rejected_when_the_repair_repeats_it() -> None:
    tools, invoked = build_tools()
    provider = ScriptedProvider(
        plan_json('{"first":"status captured"}'),
        plan_json('{"first":"status captured"}'),  # unchanged: still an object
    )

    with pytest.raises(PlannerContractError) as caught:
        await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert caught.value.category == "invalid_type"
    assert caught.value.field == CRITERIA_FIELD
    assert invoked == []


# ---------------------------------------------------------------------------
# 4. A second malformed response fails closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_malformed_response_fails_closed() -> None:
    tools, invoked = build_tools()
    provider = ScriptedProvider(
        plan_json("42"),
        plan_json("42"),
    )
    goal = "Rotate the production credential"
    context = {"soul_recall": {"context": "TEE RULING: never rotate unattended"}}

    with pytest.raises(PlannerContractError) as caught:
        await LLMPlanner(provider).plan(goal, context, tools)

    error = caught.value

    # Exactly one correction was attempted; ScriptedProvider would have raised
    # AssertionError on a third request.
    assert len(provider.requests) == 2

    # The operator-facing string is the Command Center sentence, verbatim.
    assert str(error) == (
        "DEVON received a malformed plan from the active intelligence provider. "
        "One repair attempt failed. No action was executed."
    )

    # Provider, field, and category are reported as structured facts.
    assert error.as_dict() == {
        "provider": "scripted-test",
        "field": CRITERIA_FIELD,
        "category": "invalid_type",
    }

    # No prompt content leaks into the message that reaches the Command Center:
    # not the goal, not the recalled ruling, not the model's own reply.
    rendered = str(error)
    assert goal not in rendered
    assert "TEE RULING" not in rendered
    assert "42" not in rendered

    # It stays a ValueError, so the API keeps mapping it to 422 rather than 500.
    assert isinstance(error, ValueError)
    assert invoked == []


@pytest.mark.asyncio
async def test_provider_failure_during_repair_fails_closed() -> None:
    tools, invoked = build_tools()
    provider = ExplodingRepairProvider(plan_json('"status captured"'))

    with pytest.raises(PlannerContractError) as caught:
        await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert caught.value.category == "provider_error_on_repair"
    assert caught.value.provider == "exploding-test"
    assert "down" not in str(caught.value)
    assert invoked == []


@pytest.mark.asyncio
async def test_unparsable_repair_fails_closed() -> None:
    tools, invoked = build_tools()
    provider = ScriptedProvider(
        plan_json('"status captured"'),
        "I cannot produce JSON for this request.",
    )

    with pytest.raises(PlannerContractError) as caught:
        await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert caught.value.category == "unparsable_repair"
    assert invoked == []


# ---------------------------------------------------------------------------
# The validator is not weakened: refusals still fail on the first answer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_tool_is_never_given_a_second_attempt() -> None:
    """A governance refusal is not a typo. Retrying it would invite the model
    to try the same door twice."""
    invoked: list[str] = []
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.destroy",
            description="Destroy",
            risk=ToolRisk.BLOCKED,
            handler=lambda args: invoked.append("repo.destroy"),
        )
    )
    provider = ScriptedProvider(
        '{"steps":[{"title":"Wipe","tool":"repo.destroy","arguments":{},'
        '"reason":"","expected_outcome":""}],'
        f'"{CRITERIA_FIELD}":"also the wrong type"}}'
    )

    with pytest.raises(ValueError, match="blocked tool"):
        await LLMPlanner(provider).plan("Wipe it", {}, tools)

    # One request only: the blocked tool was refused before the criteria type
    # was ever reached, and no correction was offered.
    assert len(provider.requests) == 1
    assert invoked == []


@pytest.mark.asyncio
async def test_empty_steps_still_fail_on_the_first_answer() -> None:
    tools, _ = build_tools()
    provider = ScriptedProvider(f'{{"steps":[],"{CRITERIA_FIELD}":"wrong type too"}}')

    with pytest.raises(ValueError, match="no steps"):
        await LLMPlanner(provider).plan("Inspect Meta", {}, tools)

    assert len(provider.requests) == 1


# ---------------------------------------------------------------------------
# 5. No task executes before validation passes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_task_is_created_or_executed_before_validation_passes() -> None:
    """The runtime plans before it stores. A contract failure therefore leaves
    no task to run, which is why a bad provider can cost tokens but never an
    action."""
    tools, invoked = build_tools()
    provider = ScriptedProvider(
        plan_json('"status captured"'),
        plan_json('"still a string"'),
    )
    runtime = AgentRuntime(planner=LLMPlanner(provider), tools=tools)

    with pytest.raises(PlannerContractError):
        await runtime.create_task("Inspect Meta")

    # No tool ran.
    assert invoked == []
    # No task was stored, so there is nothing for run_next to pick up.
    assert runtime.store.list() == []
