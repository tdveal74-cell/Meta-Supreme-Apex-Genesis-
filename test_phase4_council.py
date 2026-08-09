"""Phase 4 tests — streaming, deliberation rounds, model tiers, concurrency."""

import asyncio
import json

from services.intelligence import ContextPacket, ExecutiveController, IntentCategory
from services.intelligence.providers import CompletionRequest, MockProvider

# ---------------------------------------------------------------------------
# Deliberation rounds
# ---------------------------------------------------------------------------

async def test_deliberation_runs_two_rounds_with_peer_context():
    captured: list[CompletionRequest] = []

    def responder(request: CompletionRequest) -> str:
        captured.append(request)
        if request.metadata.get("stage") == "synthesis":
            return json.dumps(
                {
                    "response": "Deliberated synthesis.",
                    "recommended_actions": [],
                    "points_of_agreement": [],
                    "points_of_tension": [],
                    "confidence": 0.8,
                }
            )
        round_number = request.metadata.get("round", 1)
        return json.dumps(
            {"analysis": f"round-{round_number} view", "confidence": 0.7}
        )

    controller = ExecutiveController(MockProvider(responder=responder))
    result = await controller.run(
        ContextPacket(
            user_id="u",
            message="Evaluate the expansion",
            intent=IntentCategory.GENERAL,  # deterministic: skip intent stage
            deliberate=True,
        )
    )

    assert result.deliberation_rounds == 2
    # Final contributions come from round 2.
    assert all(c.round == 2 for c in result.contributions)
    assert all(c.content["analysis"] == "round-2 view" for c in result.contributions)

    # Round-2 prompts contained the peers' round-1 contributions.
    round2_requests = [r for r in captured if r.metadata.get("round") == 2]
    assert len(round2_requests) == 2  # analyst + strategist (GENERAL routing)
    for request in round2_requests:
        prompt = request.messages[0].content
        assert "Council deliberation (round 2)" in prompt
        assert "round-1 view" in prompt  # peer content visible

    # Token accounting includes both rounds (round 1 spend is real).
    single_round = await ExecutiveController(
        MockProvider(responder=responder)
    ).run(
        ContextPacket(
            user_id="u", message="Evaluate the expansion", intent=IntentCategory.GENERAL
        )
    )
    assert result.total_input_tokens > single_round.total_input_tokens


async def test_failed_round2_revision_keeps_round1_contribution():
    calls = {"n": 0}

    def responder(request: CompletionRequest) -> str:
        if request.metadata.get("stage") == "synthesis":
            return json.dumps(
                {
                    "response": "ok",
                    "recommended_actions": [],
                    "points_of_agreement": [],
                    "points_of_tension": [],
                    "confidence": 0.5,
                }
            )
        if request.metadata.get("round") == 2:
            calls["n"] += 1
            return "broken revision"  # round 2 always fails (incl. repair)
        return json.dumps({"analysis": "solid round-1", "confidence": 0.9})

    controller = ExecutiveController(MockProvider(responder=responder))
    result = await controller.run(
        ContextPacket(
            user_id="u",
            message="anything",
            intent=IntentCategory.GENERAL,
            deliberate=True,
        )
    )

    # Round-1 content survives failed revisions; nothing is lost or fabricated.
    assert all(c.status == "completed" for c in result.contributions)
    assert all(c.round == 1 for c in result.contributions)
    assert all(c.content["analysis"] == "solid round-1" for c in result.contributions)


async def test_single_agent_never_deliberates():
    controller = ExecutiveController(MockProvider())
    result = await controller.run(
        ContextPacket(
            user_id="u",
            message="long view",
            intent=IntentCategory.GENERAL,
            requested_agents=["oracle"],
            deliberate=True,  # requested, but one agent has no peers
        )
    )
    assert result.deliberation_rounds == 1


# ---------------------------------------------------------------------------
# Model tiers
# ---------------------------------------------------------------------------

async def test_model_tiers_route_per_stage():
    models_seen: dict[str, str | None] = {}

    def responder(request: CompletionRequest) -> str:
        stage = request.metadata.get("stage") or "agent"
        models_seen[stage] = request.model
        if stage == "intent":
            return json.dumps({"intent": "question", "reasoning": "test"})
        if stage == "synthesis":
            return json.dumps(
                {
                    "response": "ok",
                    "recommended_actions": [],
                    "points_of_agreement": [],
                    "points_of_tension": [],
                    "confidence": 0.5,
                }
            )
        return json.dumps({"analysis": "ok", "confidence": 0.5})

    controller = ExecutiveController(
        MockProvider(responder=responder),
        fast_model="tier-fast",
        synthesis_model="tier-synthesis",
    )
    await controller.run(ContextPacket(user_id="u", message="what is churn?"))

    assert models_seen["intent"] == "tier-fast"
    assert models_seen["synthesis"] == "tier-synthesis"
    assert models_seen["agent"] is None  # agents use the provider default


# ---------------------------------------------------------------------------
# Concurrency cap
# ---------------------------------------------------------------------------

class _InstrumentedProvider(MockProvider):
    """Counts concurrent in-flight completions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.in_flight = 0
        self.max_in_flight = 0

    async def _complete_once(self, request):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.02)
            return await super()._complete_once(request)
        finally:
            self.in_flight -= 1


async def test_parallel_execution_respects_concurrency_cap():
    provider = _InstrumentedProvider()
    controller = ExecutiveController(provider, parallel=True, max_concurrency=2)
    result = await controller.run(
        ContextPacket(
            user_id="u",
            message="everything",
            intent=IntentCategory.GENERAL,
            full_council=True,  # nine agents
        )
    )
    assert len(result.contributions) == 9
    assert provider.max_in_flight <= 2


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

async def test_run_emits_ordered_progress_events():
    events: list[dict] = []

    async def on_event(event: dict) -> None:
        events.append(event)

    controller = ExecutiveController(MockProvider())
    await controller.run(
        ContextPacket(user_id="u", message="plan the rollout"),
        on_event=on_event,
    )

    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert "context" in types
    assert "intent" in types
    assert types.index("agents_selected") < types.index("agent_started")
    assert types.count("agent_started") == types.count("agent_completed")
    assert types[-1] == "synthesis_started"

    selected = next(e for e in events if e["type"] == "agents_selected")
    started = {e["agent"] for e in events if e["type"] == "agent_started"}
    assert started == set(selected["agents"])


# ---------------------------------------------------------------------------
# Streaming endpoint (integration)
# ---------------------------------------------------------------------------

def _parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.strip().split("\n\n"):
        if block.startswith("data: "):
            events.append(json.loads(block[len("data: "):]))
    return events


async def test_stream_endpoint_emits_events_and_persists(client, auth_headers):
    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    conversation_id = conversation.json()["id"]

    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "Should we launch the beta next month?", "deliberate": True},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = (await response.aread()).decode("utf-8")

    events = _parse_sse(raw)
    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert types[-1] == "complete"
    assert "agent_started" in types and "synthesis_started" in types
    # Deliberation produced round-2 events.
    assert any(
        e["type"] == "agent_completed" and e.get("round") == 2 for e in events
    )

    complete = events[-1]["payload"]
    assert complete["deliberation_rounds"] == 2
    assert complete["assistant_message"]["content"]
    assert all(c["round"] == 2 for c in complete["contributions"])

    # Everything was persisted before `complete` was emitted.
    detail = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=auth_headers
    )
    roles = [m["role"] for m in detail.json()["messages"]]
    assert roles == ["user", "assistant"]

    runs = await client.get(
        f"/api/v1/conversations/{conversation_id}/runs", headers=auth_headers
    )
    assert len(runs.json()) == 4  # decision routing


async def test_stream_endpoint_reports_errors_as_events(client, auth_headers, monkeypatch):
    from app.services import intelligence as intel

    async def broken_run(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(intel, "run_council_for_message", broken_run)
    # The router imported the symbol directly — patch it there too.
    import app.api.v1.conversations as conversations_module

    monkeypatch.setattr(conversations_module, "run_council_for_message", broken_run)

    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conversation.json()['id']}/messages/stream",
        json={"content": "hi"},
        headers=auth_headers,
    ) as response:
        raw = (await response.aread()).decode("utf-8")

    events = _parse_sse(raw)
    assert events[-1]["type"] == "error"
    assert events[-1]["status"] == 500
