"""
Executive Controller — central intelligence router.

Responsibilities:
- Understand user intent (fast-model tier)
- Accept retrieved context (knowledge + memories) from the app layer
- Select and route to agents
- Coordinate agent execution (parallel with a concurrency cap by default;
  sequential opt-in) across one or two deliberation rounds
- Produce final synthesis (synthesis-model tier)
- Emit progress events for live streaming
- Emit memory update candidates

Execution flow:
USER REQUEST
  → CONTEXT ANALYSIS
  → EXECUTIVE CONTROLLER
  → AGENT ROUTING
  → SPECIALIZED ANALYSIS (round 1 [, round 2 deliberation])
  → SYNTHESIS
  → FINAL RESPONSE
  → MEMORY UPDATE (candidates; persisted by the app layer)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.agents.executor import AgentExecutor, AgentResult, AgentTask
from services.agents.registry import AGENT_REGISTRY, AgentDefinition, list_agent_slugs
from services.intelligence.providers import (
    REQUIRED_KEYS_MARKER,
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)
from services.intelligence.synthesizer import SynthesisOutput, Synthesizer

logger = logging.getLogger(__name__)

# Progress events: awaited callback receiving small JSON-serializable dicts.
EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class IntentCategory(str, Enum):
    QUESTION = "question"
    DECISION = "decision"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    GENERAL = "general"


class CouncilExecutionError(Exception):
    """Raised when no agent could produce a contribution at all."""

    def __init__(self, message: str, failures: Optional[List[AgentResult]] = None):
        self.failures = failures or []
        super().__init__(message)


@dataclass
class ContextPacket:
    """Everything the controller needs about the current request."""

    user_id: str
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str = ""
    intent: Optional[IntentCategory] = None  # None → controller analyzes
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    retrieved_knowledge: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_memories: List[Dict[str, Any]] = field(default_factory=list)
    requested_agents: List[str] = field(default_factory=list)  # explicit override
    full_council: bool = False  # activate all nine agents
    deliberate: bool = False  # request a second (deliberation) round
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContribution:
    """One agent's contribution, preserved transparently in the result."""

    agent_slug: str
    agent_name: str
    status: str  # "completed" | "failed"
    content: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    error: Optional[str] = None
    round: int = 1  # deliberation round that produced the final content


@dataclass
class SynthesisResult:
    """Final structured output of a Council run."""

    request_id: str
    final_response: str
    intent: IntentCategory = IntentCategory.GENERAL
    intent_source: str = "model"  # "model" | "heuristic" | "provided"
    agents_consulted: List[str] = field(default_factory=list)
    contributions: List[AgentContribution] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    points_of_agreement: List[str] = field(default_factory=list)
    points_of_tension: List[str] = field(default_factory=list)
    confidence: float = 0.0
    synthesis_mode: str = "model"  # "model" | "fallback"
    deliberation_rounds: int = 1
    provider: str = ""
    model: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: int = 0
    memory_updates: List[Dict[str, Any]] = field(default_factory=list)


# Intent → minimal useful agent set. Full Council activation is opt-in.
_ROUTING_TABLE: Dict[IntentCategory, List[str]] = {
    IntentCategory.DECISION: ["analyst", "strategist", "guardian", "skeptic"],
    IntentCategory.PLANNING: ["architect", "engineer", "guardian"],
    IntentCategory.ANALYSIS: ["analyst", "librarian", "skeptic"],
    IntentCategory.KNOWLEDGE: ["librarian", "analyst"],
    IntentCategory.QUESTION: ["analyst", "strategist"],
    IntentCategory.GENERAL: ["analyst", "strategist"],
}

_INTENT_SYSTEM = (
    "You classify user requests for an Intelligence Operating System.\n"
    "Categories:\n"
    "- question: a direct question seeking an answer\n"
    "- decision: the user must choose between options / wants a recommendation\n"
    "- analysis: the user wants something examined, researched, or explained in depth\n"
    "- planning: the user wants a plan, roadmap, or implementation approach\n"
    "- knowledge: the user is asking about their stored knowledge or documents\n"
    "- general: anything else\n\n"
    "--- Output contract ---\n"
    "Respond with a single JSON object containing exactly these keys.\n"
    f"{REQUIRED_KEYS_MARKER} intent, reasoning\n"
    "- intent: exactly one of question|decision|analysis|planning|knowledge|general\n"
    "- reasoning: one short sentence\n"
    "- No markdown fences, no text outside the JSON object."
)


async def _noop_event(_: Dict[str, Any]) -> None:
    return None


class ExecutiveController:
    """
    Central orchestrator for the Intelligence Operating System.

    Phase 4: parallel-by-default execution with a concurrency cap, optional
    round-2 deliberation (agents see each other's round-1 contributions),
    per-stage model tiers (fast intent / default agents / synthesis), and
    progress events for live streaming.
    """

    def __init__(
        self,
        provider: AIProvider,
        *,
        parallel: bool = True,
        max_concurrency: int = 3,
        deliberation_rounds: int = 1,
        fast_model: Optional[str] = None,
        synthesis_model: Optional[str] = None,
        synthesis_persona: str = "",
        max_tokens_per_agent: int = 1200,
        synthesis_max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider
        self.parallel = parallel
        self.max_concurrency = max(1, max_concurrency)
        self.deliberation_rounds = 2 if deliberation_rounds >= 2 else 1
        self.fast_model = fast_model
        self.synthesis_model = synthesis_model
        self.executor = AgentExecutor(
            provider, max_tokens=max_tokens_per_agent, temperature=temperature
        )
        self.synthesizer = Synthesizer(
            provider,
            max_tokens=synthesis_max_tokens,
            temperature=temperature,
            model=synthesis_model,
            persona=synthesis_persona,
        )
        self.request_id = str(uuid4())

    # ------------------------------------------------------------------ #
    # Intent
    # ------------------------------------------------------------------ #

    async def analyze_intent(self, message: str) -> tuple[IntentCategory, str]:
        """
        Classify intent with the provider (fast-model tier); fall back to
        keyword heuristics if the model output is unusable. The source is
        always reported.
        """
        request = CompletionRequest(
            system=_INTENT_SYSTEM,
            messages=[ChatMessage(role="user", content=message)],
            model=self.fast_model,  # None → provider default
            max_tokens=200,
            temperature=0.0,
            json_mode=True,
            metadata={"stage": "intent"},
        )
        try:
            response = await self.provider.complete(request)
            parsed = extract_json(response.text)
            candidate = str(parsed.get("intent", "")).strip().lower()
            if candidate in IntentCategory._value2member_map_:
                return IntentCategory(candidate), "model"
        except (ProviderError, ValueError) as exc:
            logger.warning("intent analysis via model failed (%s); using heuristic", exc)

        return self._heuristic_intent(message), "heuristic"

    @staticmethod
    def _heuristic_intent(message: str) -> IntentCategory:
        lower = message.lower()
        if any(w in lower for w in ["decide", "should i", "should we", "option", "recommend"]):
            return IntentCategory.DECISION
        if any(w in lower for w in ["analyze", "research", "what is", "explain"]):
            return IntentCategory.ANALYSIS
        if any(w in lower for w in ["plan", "how to", "implement", "build"]):
            return IntentCategory.PLANNING
        if any(w in lower for w in ["upload", "document", "knowledge", "find"]):
            return IntentCategory.KNOWLEDGE
        return IntentCategory.QUESTION

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #

    def select_agents(self, intent: IntentCategory, context: ContextPacket) -> List[str]:
        """Route to a minimal useful set of agents (full Council is opt-in)."""
        if context.full_council:
            return list_agent_slugs()
        if context.requested_agents:
            valid = [slug for slug in context.requested_agents if slug in AGENT_REGISTRY]
            if valid:
                return valid
            logger.warning(
                "requested agents %s not found in registry; falling back to routing table",
                context.requested_agents,
            )
        return list(_ROUTING_TABLE.get(intent, _ROUTING_TABLE[IntentCategory.GENERAL]))

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    async def run(
        self,
        context: ContextPacket,
        on_event: Optional[EventCallback] = None,
    ) -> SynthesisResult:
        emit = on_event or _noop_event
        started = time.monotonic()

        await emit({"type": "run_started", "request_id": self.request_id})
        await emit(
            {
                "type": "context",
                "knowledge_retrieved": len(context.retrieved_knowledge),
                "memories_recalled": len(context.retrieved_memories),
            }
        )

        # 1. Intent
        if context.intent is not None:
            intent, intent_source = context.intent, "provided"
        else:
            intent, intent_source = await self.analyze_intent(context.message)
        await emit({"type": "intent", "intent": intent.value, "source": intent_source})

        # 2. Routing
        agent_slugs = self.select_agents(intent, context)
        agents = [AGENT_REGISTRY[slug] for slug in agent_slugs]
        rounds = 2 if (context.deliberate or self.deliberation_rounds >= 2) and len(agents) > 1 else 1
        await emit(
            {"type": "agents_selected", "agents": agent_slugs, "rounds": rounds}
        )

        # 3. Specialized analysis — round 1
        task = AgentTask(
            message=context.message,
            intent=intent.value,
            conversation_history=context.conversation_history,
            retrieved_knowledge=context.retrieved_knowledge,
            retrieved_memories=context.retrieved_memories,
        )
        round1 = await self._execute_round(agents, task, round_number=1, emit=emit)

        completed_round1 = [r for r in round1 if r.status == "completed"]
        if not completed_round1:
            raise CouncilExecutionError(
                "No Council agent could produce a contribution. "
                + "; ".join(f"{r.agent_slug}: {r.error}" for r in round1),
                failures=round1,
            )

        # 4. Optional deliberation — round 2 (agents see peers' round-1 output)
        results = round1
        if rounds == 2:
            results = await self._deliberation_round(agents, task, round1, emit=emit)

        # 5. Synthesis
        await emit({"type": "synthesis_started"})
        synthesis: SynthesisOutput = await self.synthesizer.synthesize(
            message=context.message, intent=intent.value, results=results
        )

        # 6. Memory update candidates (persisted by the app layer; emitted
        #    transparently so the user can see what the system would learn).
        memory_updates = [
            {
                "type": "interaction_summary",
                "status": "candidate",
                "content": {
                    "intent": intent.value,
                    "agents_consulted": agent_slugs,
                    "confidence": synthesis.confidence,
                },
            }
        ]

        contributions = [_to_contribution(r) for r in results]
        round1_tokens_in = sum(r.input_tokens for r in round1)
        round1_tokens_out = sum(r.output_tokens for r in round1)
        final_tokens_in = sum(c.input_tokens for c in contributions)
        final_tokens_out = sum(c.output_tokens for c in contributions)
        # When deliberating, round-1 token spend is real even though only
        # round-2 content ships — account for both, never double-count round 1.
        extra_in = round1_tokens_in if rounds == 2 else 0
        extra_out = round1_tokens_out if rounds == 2 else 0

        return SynthesisResult(
            request_id=self.request_id,
            final_response=synthesis.response,
            intent=intent,
            intent_source=intent_source,
            agents_consulted=agent_slugs,
            contributions=contributions,
            recommended_actions=synthesis.recommended_actions,
            points_of_agreement=synthesis.points_of_agreement,
            points_of_tension=synthesis.points_of_tension,
            confidence=synthesis.confidence,
            synthesis_mode=synthesis.synthesis_mode,
            deliberation_rounds=rounds,
            provider=self.provider.name,
            model=synthesis.model or self.provider.default_model,
            total_input_tokens=final_tokens_in + extra_in + synthesis.input_tokens,
            total_output_tokens=final_tokens_out + extra_out + synthesis.output_tokens,
            total_latency_ms=int((time.monotonic() - started) * 1000),
            memory_updates=memory_updates,
        )

    # ------------------------------------------------------------------ #

    async def _execute_round(
        self,
        agents: List[AgentDefinition],
        task: AgentTask,
        *,
        round_number: int,
        emit: EventCallback,
        peers_by_slug: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        own_by_slug: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[AgentResult]:
        """
        Execute one round. Parallel (default) uses a semaphore so at most
        `max_concurrency` provider calls are in flight — rate-limit friendly
        without giving up wall-clock wins.
        """

        async def run_one(agent: AgentDefinition) -> AgentResult:
            await emit(
                {"type": "agent_started", "agent": agent.slug, "round": round_number}
            )
            result = await self.executor.execute(
                agent,
                task,
                round_number=round_number,
                peer_contributions=(peers_by_slug or {}).get(agent.slug),
                own_round1=(own_by_slug or {}).get(agent.slug),
            )
            await emit(
                {
                    "type": "agent_completed",
                    "agent": agent.slug,
                    "round": round_number,
                    "status": result.status,
                    "confidence": result.confidence,
                    "latency_ms": result.latency_ms,
                }
            )
            return result

        if not self.parallel:
            return [await run_one(agent) for agent in agents]

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def bounded(agent: AgentDefinition) -> AgentResult:
            async with semaphore:
                return await run_one(agent)

        return list(await asyncio.gather(*(bounded(agent) for agent in agents)))

    async def _deliberation_round(
        self,
        agents: List[AgentDefinition],
        task: AgentTask,
        round1: List[AgentResult],
        *,
        emit: EventCallback,
    ) -> List[AgentResult]:
        """
        Round 2: every agent sees the Council's round-1 contributions and
        revises. A failed revision falls back to that agent's round-1 result —
        a good contribution is never lost to a failed rewrite.
        """
        by_slug = {r.agent_slug: r for r in round1}
        contributions_r1 = [
            {"agent": r.agent_slug, "confidence": r.confidence, "contribution": r.content}
            for r in round1
            if r.status == "completed"
        ]
        peers_by_slug = {
            agent.slug: [c for c in contributions_r1 if c["agent"] != agent.slug]
            for agent in agents
        }
        own_by_slug = {
            r.agent_slug: r.content
            for r in round1
            if r.status == "completed" and r.content
        }

        round2 = await self._execute_round(
            agents,
            task,
            round_number=2,
            emit=emit,
            peers_by_slug=peers_by_slug,
            own_by_slug=own_by_slug,
        )

        final: List[AgentResult] = []
        for result in round2:
            if result.status == "completed":
                final.append(result)
                continue
            fallback = by_slug.get(result.agent_slug)
            if fallback is not None and fallback.status == "completed":
                logger.warning(
                    "agent=%s round-2 revision failed (%s); keeping round-1 contribution",
                    result.agent_slug,
                    result.error,
                )
                final.append(fallback)
            else:
                final.append(result)
        return final


def _to_contribution(result: AgentResult) -> AgentContribution:
    return AgentContribution(
        agent_slug=result.agent_slug,
        agent_name=result.agent_name,
        status=result.status,
        content=result.content,
        confidence=result.confidence,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=result.model,
        provider=result.provider,
        error=result.error,
        round=result.round,
    )
