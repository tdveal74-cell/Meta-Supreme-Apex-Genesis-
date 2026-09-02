"""
Application-layer intelligence service.

Bridges the FastAPI app and the framework-free services layer:
- Builds the configured AI provider from application settings
- Seeds the `agents` table from the canonical registry (idempotent upsert)
- Runs the Executive Controller for a conversation message and persists
  the full audit trail: user message, agent runs, and the synthesized
  assistant message.

Dependency direction is app → services; the services layer never imports
application code.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent, AgentRun
from app.models.conversation import Conversation, Message
from app.services.provider_usage import MeteredProvider
from services.agents.registry import AGENT_REGISTRY
from services.intelligence import (
    ContextPacket,
    ExecutiveController,
    SynthesisResult,
)
from services.intelligence.providers import AIProvider, create_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

@lru_cache
def get_provider() -> AIProvider:
    """Build the configured AI provider once per process.

    Every lane that reaches a provider (councils, agent turns, workflows,
    the planner) takes its provider from here, so the per-tenant spend cap
    is installed here and nowhere else: the provider returned is the
    configured one wrapped in `MeteredProvider`, which refuses an account at
    its daily cap before the call and records the usage after it.
    """
    name = settings.DEFAULT_AI_PROVIDER
    model = settings.AI_MODEL or (
        settings.ANTHROPIC_MODEL if name == "anthropic"
        else settings.OPENAI_MODEL if name == "openai"
        else settings.CEREBRAS_MODEL if name == "cerebras"
        else None
    )
    provider = create_provider(
        name,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        cerebras_api_key=settings.CEREBRAS_API_KEY,
        model=model,
        timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
    )
    logger.info(
        "AI provider initialized: %s (model=%s)", provider.name, provider.default_model
    )
    return MeteredProvider(provider)


@lru_cache
def get_enrichment_provider() -> AIProvider:
    """Build the provider used to tag captures with an Area and a summary.

    Kept separate from `get_provider` on purpose. Enrichment is high volume,
    latency sensitive and mechanical, so it belongs on the cheapest model that
    can do it, while the Council keeps the model chosen for judgement. Routing
    mechanical work downward is most of the volume in a studio this size.

    Whatever this returns, the Area it suggests is still validated against the
    nine before anything is filed. The provider is a suggestion engine, never an
    authority.
    """
    name = settings.ENRICHMENT_PROVIDER
    model = (
        settings.CEREBRAS_MODEL if name == "cerebras"
        else settings.OPENAI_MODEL if name == "openai"
        else settings.ANTHROPIC_MODEL if name == "anthropic"
        else None
    )
    provider = create_provider(
        name,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        cerebras_api_key=settings.CEREBRAS_API_KEY,
        model=model,
        timeout_seconds=min(settings.AI_TIMEOUT_SECONDS, 30.0),
        max_retries=settings.AI_MAX_RETRIES,
    )
    logger.info(
        "Enrichment provider initialized: %s (model=%s)",
        provider.name,
        provider.default_model,
    )
    return MeteredProvider(provider)


def build_controller(provider: Optional[AIProvider] = None) -> ExecutiveController:
    """Construct an ExecutiveController wired to application settings."""
    return ExecutiveController(
        provider or get_provider(),
        parallel=settings.COUNCIL_PARALLEL_EXECUTION,
        max_concurrency=settings.COUNCIL_MAX_CONCURRENCY,
        deliberation_rounds=settings.COUNCIL_DELIBERATION_ROUNDS,
        fast_model=settings.AI_MODEL_FAST,
        synthesis_model=settings.AI_MODEL_SYNTHESIS,
        synthesis_persona=settings.SYNTHESIS_PERSONA,
        max_tokens_per_agent=settings.AI_MAX_TOKENS_PER_AGENT,
        synthesis_max_tokens=settings.AI_MAX_TOKENS_SYNTHESIS,
        temperature=settings.AI_TEMPERATURE,
    )


# ---------------------------------------------------------------------------
# Agent seeding
# ---------------------------------------------------------------------------

async def seed_agents(db: AsyncSession) -> None:
    """
    Upsert the canonical registry into the `agents` table.

    Idempotent: safe to run on every startup. The registry remains the
    single source of truth; the table exists so agent_runs can reference
    agents by stable UUID.
    """
    for definition in AGENT_REGISTRY.values():
        stmt = (
            pg_insert(Agent)
            .values(
                slug=definition.slug,
                name=definition.name,
                purpose=definition.purpose,
                system_instructions=definition.system_instructions,
                capabilities=definition.capabilities,
                limitations=definition.limitations,
                output_format=definition.output_format,
                evaluation_criteria=definition.evaluation_criteria,
                version=definition.version,
                is_active=definition.is_active,
            )
            .on_conflict_do_update(
                index_elements=[Agent.slug],
                set_={
                    "name": definition.name,
                    "purpose": definition.purpose,
                    "system_instructions": definition.system_instructions,
                    "capabilities": definition.capabilities,
                    "limitations": definition.limitations,
                    "output_format": definition.output_format,
                    "evaluation_criteria": definition.evaluation_criteria,
                    "version": definition.version,
                    "is_active": definition.is_active,
                },
            )
        )
        await db.execute(stmt)
    await db.flush()


async def get_agent_id_map(db: AsyncSession) -> Dict[str, str]:
    """Return slug → agent UUID, seeding the table if rows are missing."""
    result = await db.execute(select(Agent.slug, Agent.id))
    mapping = {row.slug: row.id for row in result.all()}
    if set(AGENT_REGISTRY) - set(mapping):
        await seed_agents(db)
        result = await db.execute(select(Agent.slug, Agent.id))
        mapping = {row.slug: row.id for row in result.all()}
    return mapping


# ---------------------------------------------------------------------------
# Council execution with persistence
# ---------------------------------------------------------------------------

async def run_council_for_message(
    db: AsyncSession,
    *,
    conversation: Conversation,
    user_id: str,
    content: str,
    requested_agents: Optional[List[str]] = None,
    full_council: bool = False,
    deliberate: bool = False,
    on_event=None,
) -> tuple[Message, Message, SynthesisResult]:
    """
    Full message flow (Phases 2+3+5):

    1. Load recent history for context
    2. Retrieve relevant knowledge (pgvector) and recall memories
    3. Persist the user message
    4. Run the Executive Controller (intent → routing → agents → synthesis)
    5. Persist one agent_run per contribution (audit trail)
    6. Persist the synthesized assistant message (with knowledge sources)
    7. Persist the Council's memory candidates as transparent memories

    Returns (user_message, assistant_message, synthesis_result).
    Raises CouncilExecutionError / ProviderError upward for the API layer
    to translate into meaningful HTTP responses.
    """
    from app.services.knowledge import retrieve_for_context
    from app.services.memory import persist_memory_candidates, recall_memories

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(settings.COUNCIL_HISTORY_LIMIT)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_result.scalars().all())
    ]

    retrieved_knowledge = await retrieve_for_context(
        db, owner_id=user_id, message=content, project_id=conversation.project_id
    )
    retrieved_memories = await recall_memories(
        db, user_id=user_id, message=content, project_id=conversation.project_id
    )

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        meta={},
    )
    db.add(user_message)
    await db.flush()

    controller = build_controller()
    context = ContextPacket(
        user_id=user_id,
        project_id=conversation.project_id,
        conversation_id=conversation.id,
        message=content,
        conversation_history=history,
        retrieved_knowledge=retrieved_knowledge,
        retrieved_memories=retrieved_memories,
        requested_agents=requested_agents or [],
        full_council=full_council,
        deliberate=deliberate,
    )

    # The exchange persists atomically: if the Council fails entirely, the
    # transaction rolls back and the client receives an explicit error —
    # no orphaned user messages, no fabricated responses.
    result = await controller.run(context, on_event=on_event)

    agent_ids = await get_agent_id_map(db)
    for contribution in result.contributions:
        agent_uuid = agent_ids.get(contribution.agent_slug)
        if agent_uuid is None:
            logger.error("no agents-table row for slug=%s; skipping run row", contribution.agent_slug)
            continue
        db.add(
            AgentRun(
                conversation_id=conversation.id,
                agent_id=agent_uuid,
                user_id=user_id,
                input_payload={
                    "message": content,
                    "intent": result.intent.value,
                    "request_id": result.request_id,
                    "round": contribution.round,
                    "deliberation_rounds": result.deliberation_rounds,
                },
                output_payload=contribution.content,
                status=contribution.status,
                error_message=contribution.error,
                token_usage={
                    "input_tokens": contribution.input_tokens,
                    "output_tokens": contribution.output_tokens,
                    "total_tokens": contribution.input_tokens + contribution.output_tokens,
                },
                latency_ms=contribution.latency_ms,
            )
        )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.final_response,
        token_count=result.total_output_tokens,
        meta={
            "request_id": result.request_id,
            "intent": result.intent.value,
            "intent_source": result.intent_source,
            "agents_consulted": result.agents_consulted,
            "recommended_actions": result.recommended_actions,
            "points_of_agreement": result.points_of_agreement,
            "points_of_tension": result.points_of_tension,
            "confidence": result.confidence,
            "synthesis_mode": result.synthesis_mode,
            "deliberation_rounds": result.deliberation_rounds,
            "provider": result.provider,
            "model": result.model,
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "total_latency_ms": result.total_latency_ms,
            "memory_updates": result.memory_updates,
            # Transparency: which stored knowledge informed this response.
            "knowledge_sources": [
                {
                    "knowledge_item_id": hit["knowledge_item_id"],
                    "title": hit["source"],
                    "chunk_index": hit["chunk_index"],
                    "distance": hit["distance"],
                }
                for hit in retrieved_knowledge
            ],
            "memories_recalled": len(retrieved_memories),
        },
    )
    db.add(assistant_message)

    # Persist the Council's memory candidates (transparent, editable, deletable).
    await persist_memory_candidates(
        db,
        user_id=user_id,
        project_id=conversation.project_id,
        conversation_id=conversation.id,
        message=content,
        result=result,
    )

    # First exchange titles the conversation (trimmed user message).
    if not conversation.title:
        conversation.title = content.strip()[:80] or "New conversation"

    await db.flush()
    await db.refresh(user_message)
    await db.refresh(assistant_message)
    return user_message, assistant_message, result
