"""
Conversations endpoints — persisted Council exchanges.

POST /conversations/{id}/messages runs the Executive Controller
(intent → routing → specialized analysis [→ deliberation] → synthesis)
and persists the full audit trail (user message, agent runs, synthesized
assistant message). The /messages/stream variant emits the same flow as
live Server-Sent Events.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db
from app.models.agent import Agent, AgentRun
from app.models.conversation import Conversation, Message
from app.models.project import Project
from app.security.deps import CurrentUser
from app.services.intelligence import run_council_for_message
from services.agents.registry import AGENT_REGISTRY
from services.intelligence import CouncilExecutionError, SynthesisResult
from services.intelligence.providers import ProviderConfigError, ProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    project_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|archived)$")


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    status: str
    project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_count: Optional[int] = None
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=32_000)
    agents: Optional[List[str]] = Field(
        None,
        description="Explicit agent slugs to consult (overrides intent routing).",
    )
    full_council: bool = Field(
        False, description="Activate all nine Council agents for this message."
    )
    deliberate: bool = Field(
        False,
        description="Run a second deliberation round where agents see each other's contributions.",
    )


class ContributionResponse(BaseModel):
    agent_slug: str
    agent_name: str
    status: str
    content: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    round: int = 1


class CouncilResponse(BaseModel):
    """Full transparent result of one Council exchange."""

    request_id: str
    conversation_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse
    intent: str
    intent_source: str
    agents_consulted: List[str]
    contributions: List[ContributionResponse]
    recommended_actions: List[str]
    points_of_agreement: List[str]
    points_of_tension: List[str]
    confidence: float
    synthesis_mode: str
    deliberation_rounds: int = 1
    provider: str
    model: str
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int
    memory_updates: List[Dict[str, Any]]


class AgentRunResponse(BaseModel):
    id: str
    conversation_id: Optional[str] = None
    agent_slug: Optional[str] = None
    status: str
    output_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        metadata=message.meta or {},
        token_count=message.token_count,
        created_at=message.created_at,
    )


def _to_conversation_response(
    conversation: Conversation, message_count: int = 0
) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        status=conversation.status,
        project_id=conversation.project_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
    )


def _to_council_response(
    conversation_id: str,
    user_message: Message,
    assistant_message: Message,
    result: SynthesisResult,
) -> CouncilResponse:
    return CouncilResponse(
        request_id=result.request_id,
        conversation_id=conversation_id,
        user_message=_to_message_response(user_message),
        assistant_message=_to_message_response(assistant_message),
        intent=result.intent.value,
        intent_source=result.intent_source,
        agents_consulted=result.agents_consulted,
        contributions=[
            ContributionResponse(
                agent_slug=c.agent_slug,
                agent_name=c.agent_name,
                status=c.status,
                content=c.content,
                confidence=c.confidence,
                latency_ms=c.latency_ms,
                input_tokens=c.input_tokens,
                output_tokens=c.output_tokens,
                error=c.error,
                round=c.round,
            )
            for c in result.contributions
        ],
        recommended_actions=result.recommended_actions,
        points_of_agreement=result.points_of_agreement,
        points_of_tension=result.points_of_tension,
        confidence=result.confidence,
        synthesis_mode=result.synthesis_mode,
        deliberation_rounds=result.deliberation_rounds,
        provider=result.provider,
        model=result.model,
        total_input_tokens=result.total_input_tokens,
        total_output_tokens=result.total_output_tokens,
        total_latency_ms=result.total_latency_ms,
        memory_updates=result.memory_updates,
    )


async def _get_owned_conversation(
    conversation_id: str, user_id: str, db: AsyncSession
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.status != "deleted",
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: CurrentUser,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List the current user's conversations, newest first."""
    query = (
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.status != "deleted",
        )
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    if project_id:
        query = query.where(Conversation.project_id == project_id)

    result = await db.execute(query)
    return [
        _to_conversation_response(conversation, count)
        for conversation, count in result.all()
    ]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation (optionally attached to a project)."""
    if payload.project_id:
        project = await db.execute(
            select(Project).where(
                Project.id == payload.project_id,
                Project.owner_id == current_user.id,
                Project.status != "deleted",
            )
        )
        if project.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

    conversation = Conversation(
        user_id=current_user.id,
        project_id=payload.project_id,
        title=payload.title,
        status="active",
        meta={},
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return _to_conversation_response(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with its full message history (owner only)."""
    conversation = await _get_owned_conversation(conversation_id, current_user.id, db)
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    messages = [_to_message_response(m) for m in messages_result.scalars().all()]
    base = _to_conversation_response(conversation, len(messages))
    return ConversationDetailResponse(**base.model_dump(), messages=messages)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Rename or archive a conversation (owner only)."""
    conversation = await _get_owned_conversation(conversation_id, current_user.id, db)
    if payload.title is not None:
        conversation.title = payload.title.strip()
    if payload.status is not None:
        conversation.status = payload.status
    await db.flush()
    await db.refresh(conversation)
    return _to_conversation_response(conversation)


@router.post("/{conversation_id}/messages", response_model=CouncilResponse)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message into a conversation and receive the Council's
    synthesized response, including every agent's individual contribution.
    """
    conversation = await _get_owned_conversation(conversation_id, current_user.id, db)

    if payload.agents:
        unknown = [slug for slug in payload.agents if slug not in AGENT_REGISTRY]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown agent slugs: {', '.join(unknown)}",
            )

    try:
        user_message, assistant_message, result = await run_council_for_message(
            db,
            conversation=conversation,
            user_id=current_user.id,
            content=payload.content,
            requested_agents=payload.agents,
            full_council=payload.full_council,
            deliberate=payload.deliberate,
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI provider is not configured: {exc}",
        ) from exc
    except CouncilExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The Council could not process this request: {exc}",
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {exc}",
        ) from exc

    return _to_council_response(conversation.id, user_message, assistant_message, result)


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and stream the Council's live progress as
    Server-Sent Events (`text/event-stream`).

    Event sequence: run_started → context → intent → agents_selected →
    (agent_started / agent_completed per agent, per round) →
    synthesis_started → complete (full CouncilResponse payload) — or a
    terminal `error` event. Persistence commits before `complete` is sent.
    """
    conversation = await _get_owned_conversation(conversation_id, current_user.id, db)

    if payload.agents:
        unknown = [slug for slug in payload.agents if slug not in AGENT_REGISTRY]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown agent slugs: {', '.join(unknown)}",
            )

    queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    async def on_event(event: dict) -> None:
        await queue.put(event)

    async def worker() -> None:
        """Run the full council flow on a dedicated session; commit before `complete`."""
        try:
            async with AsyncSessionLocal() as session:
                # Re-load the conversation inside this session for ownership-safe writes.
                owned = await _get_owned_conversation(
                    conversation.id, current_user.id, session
                )
                user_message, assistant_message, result = await run_council_for_message(
                    session,
                    conversation=owned,
                    user_id=current_user.id,
                    content=payload.content,
                    requested_agents=payload.agents,
                    full_council=payload.full_council,
                    deliberate=payload.deliberate,
                    on_event=on_event,
                )
                await session.commit()
                response = _to_council_response(
                    owned.id, user_message, assistant_message, result
                )
                await queue.put(
                    {"type": "complete", "payload": jsonable_encoder(response)}
                )
        except ProviderConfigError as exc:
            await queue.put({"type": "error", "status": 503, "message": str(exc)})
        except (CouncilExecutionError, ProviderError) as exc:
            await queue.put({"type": "error", "status": 502, "message": str(exc)})
        except Exception:  # noqa: BLE001 — stream must always terminate cleanly
            logger.exception("streaming council run failed")
            await queue.put(
                {"type": "error", "status": 500, "message": "Internal error"}
            )
        finally:
            await queue.put(None)  # sentinel: end of stream

    async def event_stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{conversation_id}/runs", response_model=List[AgentRunResponse])
async def list_agent_runs(
    conversation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Transparent audit trail: every agent run recorded for a conversation."""
    conversation = await _get_owned_conversation(conversation_id, current_user.id, db)
    result = await db.execute(
        select(AgentRun, Agent.slug)
        .join(Agent, Agent.id == AgentRun.agent_id)
        .where(AgentRun.conversation_id == conversation.id)
        .order_by(AgentRun.created_at.asc())
    )
    return [
        AgentRunResponse(
            id=run.id,
            conversation_id=run.conversation_id,
            agent_slug=slug,
            status=run.status,
            output_payload=run.output_payload,
            error_message=run.error_message,
            token_usage=run.token_usage,
            latency_ms=run.latency_ms,
            created_at=run.created_at,
        )
        for run, slug in result.all()
    ]
