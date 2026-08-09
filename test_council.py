"""Agent executor + Executive Controller tests (offline via MockProvider)."""

import json

import pytest

from services.agents.executor import AgentExecutor, AgentTask
from services.agents.registry import AGENT_REGISTRY, ANALYST
from services.intelligence import (
    ContextPacket,
    CouncilExecutionError,
    ExecutiveController,
    IntentCategory,
)
from services.intelligence.providers import CompletionRequest, MockProvider

# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

async def test_executor_produces_contract_matching_output():
    executor = AgentExecutor(MockProvider())
    result = await executor.execute(
        ANALYST, AgentTask(message="What drives churn?", intent="analysis")
    )
    assert result.status == "completed"
    assert result.agent_slug == "analyst"
    # Declared output_format fields + confidence are all present.
    for field in ANALYST.output_format["fields"]:
        assert field in result.content
    assert 0.0 <= result.confidence <= 1.0
    assert result.input_tokens > 0 and result.output_tokens > 0


async def test_executor_repairs_invalid_json_once():
    calls = {"n": 0}

    def responder(request: CompletionRequest) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "definitely not json"
        return json.dumps({"findings": ["x"], "confidence": 0.7})

    executor = AgentExecutor(MockProvider(responder=responder))
    result = await executor.execute(ANALYST, AgentTask(message="q"))
    assert result.status == "completed"
    assert calls["n"] == 2  # original + one repair attempt
    assert result.confidence == 0.7


async def test_executor_fails_explicitly_when_output_is_unusable():
    executor = AgentExecutor(MockProvider(responder=lambda r: "garbage"))
    result = await executor.execute(ANALYST, AgentTask(message="q"))
    assert result.status == "failed"
    assert result.content is None
    assert "did not match" in result.error


# ---------------------------------------------------------------------------
# Controller routing
# ---------------------------------------------------------------------------

def _controller(**kwargs) -> ExecutiveController:
    return ExecutiveController(MockProvider(), **kwargs)


def test_routing_table_per_intent():
    controller = _controller()
    packet = ContextPacket(user_id="u")
    assert controller.select_agents(IntentCategory.DECISION, packet) == [
        "analyst", "strategist", "guardian", "skeptic",
    ]
    assert controller.select_agents(IntentCategory.PLANNING, packet) == [
        "architect", "engineer", "guardian",
    ]
    assert controller.select_agents(IntentCategory.KNOWLEDGE, packet) == [
        "librarian", "analyst",
    ]


def test_full_council_activates_all_nine_agents():
    controller = _controller()
    packet = ContextPacket(user_id="u", full_council=True)
    assert set(controller.select_agents(IntentCategory.GENERAL, packet)) == set(
        AGENT_REGISTRY
    )


def test_requested_agents_override_routing():
    controller = _controller()
    packet = ContextPacket(user_id="u", requested_agents=["oracle", "skeptic"])
    assert controller.select_agents(IntentCategory.GENERAL, packet) == [
        "oracle", "skeptic",
    ]


def test_unknown_requested_agents_fall_back_to_routing():
    controller = _controller()
    packet = ContextPacket(user_id="u", requested_agents=["nonexistent"])
    assert controller.select_agents(IntentCategory.GENERAL, packet) == [
        "analyst", "strategist",
    ]


async def test_heuristic_intent_fallback_categories():
    controller = _controller()
    intent, source = await controller.analyze_intent("Should we hire a CTO now?")
    assert intent == IntentCategory.DECISION
    assert source in ("model", "heuristic")


# ---------------------------------------------------------------------------
# Controller end-to-end (mock provider)
# ---------------------------------------------------------------------------

async def test_run_produces_transparent_synthesis():
    controller = _controller()
    result = await controller.run(
        ContextPacket(user_id="u", message="Plan how to build the knowledge engine")
    )
    assert result.intent == IntentCategory.PLANNING
    assert result.agents_consulted == ["architect", "engineer", "guardian"]
    assert len(result.contributions) == 3
    assert all(c.status == "completed" for c in result.contributions)
    assert result.final_response
    assert result.synthesis_mode == "model"
    assert result.total_input_tokens > 0
    assert result.total_latency_ms >= 0
    assert result.memory_updates and result.memory_updates[0]["status"] == "candidate"


async def test_run_survives_partial_agent_failure():
    calls = {"n": 0}

    def responder(request: CompletionRequest) -> str:
        # First agent call (and its repair) fail; everything else succeeds.
        calls["n"] += 1
        if calls["n"] <= 2:
            return "not json"
        stage = request.metadata.get("stage")
        if stage == "synthesis":
            return json.dumps(
                {
                    "response": "Synthesized despite one failure.",
                    "recommended_actions": ["proceed"],
                    "points_of_agreement": [],
                    "points_of_tension": [],
                    "confidence": 0.5,
                }
            )
        return json.dumps({"analysis": "ok", "confidence": 0.8})

    controller = ExecutiveController(MockProvider(responder=responder))
    result = await controller.run(
        ContextPacket(
            user_id="u",
            message="anything",
            intent=IntentCategory.GENERAL,  # skip intent stage for determinism
        )
    )
    statuses = {c.agent_slug: c.status for c in result.contributions}
    assert "failed" in statuses.values()
    assert "completed" in statuses.values()
    assert result.final_response == "Synthesized despite one failure."


async def test_run_raises_when_every_agent_fails():
    def responder(request: CompletionRequest) -> str:
        return "never valid json"

    controller = ExecutiveController(MockProvider(responder=responder))
    with pytest.raises(CouncilExecutionError):
        await controller.run(
            ContextPacket(
                user_id="u", message="anything", intent=IntentCategory.GENERAL
            )
        )


async def test_synthesis_falls_back_to_verbatim_contributions():
    def responder(request: CompletionRequest) -> str:
        if request.metadata.get("stage") == "synthesis":
            return "synthesis broke"
        return json.dumps({"analysis": "solid work", "confidence": 0.9})

    controller = ExecutiveController(MockProvider(responder=responder))
    result = await controller.run(
        ContextPacket(user_id="u", message="anything", intent=IntentCategory.GENERAL)
    )
    assert result.synthesis_mode == "fallback"
    assert "solid work" in result.final_response  # real content, never fabricated
    assert result.confidence == 0.9  # min of contribution confidences


async def test_parallel_execution_matches_sequential_results():
    sequential = await _controller(parallel=False).run(
        ContextPacket(user_id="u", message="compare", intent=IntentCategory.GENERAL)
    )
    parallel = await _controller(parallel=True).run(
        ContextPacket(user_id="u", message="compare", intent=IntentCategory.GENERAL)
    )
    assert [c.agent_slug for c in sequential.contributions] == [
        c.agent_slug for c in parallel.contributions
    ]
    assert sequential.final_response == parallel.final_response
