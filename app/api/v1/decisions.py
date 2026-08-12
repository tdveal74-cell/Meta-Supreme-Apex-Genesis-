"""
Decisions endpoints — decision intelligence with the human in charge.

The Council recommends; the human decides. A decision can be created
manually or from a Council exchange (the assistant message's synthesis
becomes the recorded recommendation). Recording the final call is always
a human action via PATCH.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.decision import Decision
from app.security.deps import CurrentUser

router = APIRouter(prefix="/decisions", tags=["Decisions"])


class DecisionCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    options: List[str] = Field(default_factory=list, max_length=20)
    recommendation: Optional[str] = Field(None, max_length=20_000)
    project_id: Optional[str] = None


class DecisionFromMessage(BaseModel):
    message_id: str


class DecisionUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=1, max_length=2000)
    options: Optional[List[str]] = Field(None, max_length=20)
    chosen_option: Optional[str] = Field(None, max_length=2000)
    outcome: Optional[str] = Field(None, max_length=20_000)
    outcome_notes: Optional[str] = Field(None, max_length=20_000)
    status: Optional[str] = Field(None, pattern="^(open|decided|reviewed|archived)$")


class DecisionResponse(BaseModel):
    id: str
    question: str
    options: List[str]
    recommendation: Optional[str] = None
    chosen_option: Optional[str] = None
    outcome: Optional[str] = None
    outcome_notes: Optional[str] = None
    status: str
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


def _to_response(decision: Decision) -> DecisionResponse:
    return DecisionResponse(
        id=decision.id,
        question=decision.question,
        options=list(decision.options or []),
        recommendation=decision.recommendation,
        chosen_option=decision.chosen_option,
        outcome=decision.outcome,
        outcome_notes=decision.outcome_notes,
        status=decision.status,
        project_id=decision.project_id,
        metadata=decision.meta or {},
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


async def _get_owned_decision(
    decision_id: str, user_id: str, db: AsyncSession
) -> Decision:
    result = await db.execute(
        select(Decision).where(Decision.id == decision_id, Decision.user_id == user_id)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found"
        )
    return decision


@router.get("", response_model=List[DecisionResponse])
async def list_decisions(
    current_user: CurrentUser,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List the current user's decisions, newest first."""
    stmt = (
        select(Decision)
        .where(Decision.user_id == current_user.id)
        .order_by(Decision.updated_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Decision.status == status_filter)
    result = await db.execute(stmt)
    return [_to_response(d) for d in result.scalars().all()]


@router.post("", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    payload: DecisionCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a decision to track (manual entry)."""
    decision = Decision(
        user_id=current_user.id,
        project_id=payload.project_id,
        question=payload.question.strip(),
        options=[o.strip() for o in payload.options if o.strip()],
        recommendation=payload.recommendation,
        status="open",
        meta={"origin": "manual"},
    )
    db.add(decision)
    await db.flush()
    await db.refresh(decision)
    return _to_response(decision)


@router.post(
    "/from-message",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_decision_from_message(
    payload: DecisionFromMessage,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Track a decision from a Council exchange.

    The assistant message's synthesis becomes the recommendation; the
    Council's recommended actions become the option list. The final call
    stays open until the human records it.
    """
    result = await db.execute(
        select(Message, Conversation)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == payload.message_id,
            Conversation.user_id == current_user.id,
            Message.role == "assistant",
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found",
        )
    message, conversation = row

    # The question is the user message that triggered this response.
    question_result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "user",
            Message.created_at <= message.created_at,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    question_message = question_result.scalar_one_or_none()

    meta = message.meta or {}
    decision = Decision(
        user_id=current_user.id,
        project_id=conversation.project_id,
        question=(question_message.content if question_message else conversation.title or "Council exchange")[:2000],
        options=list(meta.get("recommended_actions", []))[:20],
        recommendation=message.content,
        status="open",
        meta={
            "origin": "council",
            "conversation_id": conversation.id,
            "message_id": message.id,
            "request_id": meta.get("request_id"),
            "agents_consulted": meta.get("agents_consulted", []),
            "confidence": meta.get("confidence"),
            "points_of_tension": meta.get("points_of_tension", []),
        },
    )
    db.add(decision)
    await db.flush()
    await db.refresh(decision)
    return _to_response(decision)


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get one decision (owner only)."""
    decision = await _get_owned_decision(decision_id, current_user.id, db)
    return _to_response(decision)


@router.patch("/{decision_id}", response_model=DecisionResponse)
async def update_decision(
    decision_id: str,
    payload: DecisionUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a decision — including recording the final call.

    Setting `chosen_option` marks the decision `decided` unless a status
    is explicitly provided. The human's choice is the record of truth.
    """
    decision = await _get_owned_decision(decision_id, current_user.id, db)
    if payload.question is not None:
        decision.question = payload.question.strip()
    if payload.options is not None:
        decision.options = [o.strip() for o in payload.options if o.strip()]
    if payload.chosen_option is not None:
        decision.chosen_option = payload.chosen_option.strip()
        if payload.status is None and decision.status == "open":
            decision.status = "decided"
    if payload.outcome is not None:
        decision.outcome = payload.outcome
    if payload.outcome_notes is not None:
        decision.outcome_notes = payload.outcome_notes
    if payload.status is not None:
        decision.status = payload.status
    await db.flush()
    await db.refresh(decision)
    return _to_response(decision)
