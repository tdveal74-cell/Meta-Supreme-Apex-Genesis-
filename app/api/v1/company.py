"""
The company layer's read surface: the six business functions and the
Operations and Finance scoreboard.

Both routes are GET and mutate nothing. The scoreboard reads the same spend
ledger and cap setting that /usage reads. Revenue has no source connected, so
it is reported as not measured rather than as zero.
"""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services import company_queue, company_sales_queue
from app.services.provider_usage import read_usage, utc_today
from services.company.functions import list_functions
from services.company.marketing import PostDraft, QueueRefusal
from services.company.sales import LeadDraft
from services.company.scoreboard import build_scoreboard

router = APIRouter(prefix="/company", tags=["Company"])


class FunctionOut(BaseModel):
    slug: str
    function: str
    mission: str
    key_tools: List[str]
    outcome: str
    max_impact: str
    status: str
    built_in: Optional[str]
    build_order: int
    notes: List[str]


class ScoreboardOut(BaseModel):
    date: str
    target_monthly_usd: int
    revenue_month_usd: Optional[float]
    revenue_measured: bool
    gap_to_target_usd: Optional[float]
    pct_of_target: Optional[float]
    spend_calls_today: int
    spend_tokens_today: int
    spend_cap_tokens: Optional[int]
    spend_headroom_tokens: Optional[int]
    cap_pct_used: Optional[float]
    notes: List[str]


@router.get("/functions", response_model=List[FunctionOut], summary="The six business functions")
async def read_functions() -> List[FunctionOut]:
    return [
        FunctionOut(
            slug=f.slug,
            function=f.function,
            mission=f.mission,
            key_tools=list(f.key_tools),
            outcome=f.outcome,
            max_impact=f.max_impact.value,
            status=f.status.value,
            built_in=f.built_in,
            build_order=f.build_order,
            notes=list(f.notes),
        )
        for f in list_functions()
    ]


@router.get("/scoreboard", response_model=ScoreboardOut, summary="Ops and Finance scoreboard")
async def read_scoreboard(current_user: CurrentUser) -> ScoreboardOut:
    day = utc_today()
    usage = await read_usage(str(current_user.id), day)
    cap = int(settings.PROVIDER_DAILY_TOKEN_CAP or 0)
    board = build_scoreboard(
        revenue_month_usd=None,
        calls_today=usage.calls,
        tokens_today=usage.total_tokens,
        cap_tokens=cap if cap > 0 else None,
    )
    return ScoreboardOut(date=day.isoformat(), notes=list(board.notes), **{
        k: getattr(board, k) for k in ScoreboardOut.model_fields if k not in ("date", "notes")
    })


# ---------------------------------------------------------------------------
# The Marketing approval queue. Draft and queue only: no route here schedules,
# sends or publishes, and none can, because the queue rules module has no way
# to reach a platform. A decision is the signed-in account's own.
# ---------------------------------------------------------------------------

DbSession = Annotated[AsyncSession, Depends(get_db)]


class DraftIn(BaseModel):
    show: str = Field(..., max_length=120)
    episode_ref: str = Field(..., max_length=200)
    platform: str = Field(..., max_length=80)
    # Storage guards only. These are not platform limits, which are unverified.
    text: str = Field(..., max_length=4000)
    ai_disclosure: str = Field(..., max_length=1000)


class DecisionIn(BaseModel):
    # The pattern refuses a NUL byte, which the database cannot store. It is a
    # pattern and not a validator because a validator's ValueError cannot be
    # serialised by this app's validation error handler, which turns a 422 into a 500.
    note: Optional[str] = Field(None, max_length=2000, pattern=r"^[^\x00]*$")


class DraftOut(BaseModel):
    draft_id: str
    show: str
    episode_ref: str
    platform: str
    text: str
    ai_disclosure: str
    status: str
    decided_by: Optional[str]
    decision_note: Optional[str]


def _draft_out(d: PostDraft) -> DraftOut:
    return DraftOut(
        draft_id=d.draft_id, show=d.show, episode_ref=d.episode_ref, platform=d.platform,
        text=d.text, ai_disclosure=d.ai_disclosure, status=d.status.value,
        decided_by=d.decided_by, decision_note=d.decision_note,
    )


@router.post("/marketing/drafts", response_model=DraftOut, status_code=201,
             summary="Queue a post draft for approval")
async def queue_draft(body: DraftIn, current_user: CurrentUser, db: DbSession) -> DraftOut:
    try:
        draft = await company_queue.insert_draft(
            db, str(current_user.id), show=body.show, episode_ref=body.episode_ref,
            platform=body.platform, post_text=body.text, ai_disclosure=body.ai_disclosure,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _draft_out(draft)


@router.get("/marketing/drafts", response_model=List[DraftOut], summary="List the caller's drafts")
async def list_queue(
    current_user: CurrentUser, db: DbSession,
    status: Optional[str] = Query(None, pattern="^(drafted|approved|rejected)$"),
) -> List[DraftOut]:
    drafts = await company_queue.list_drafts(db, str(current_user.id), status)
    return [_draft_out(d) for d in drafts]


async def _decide(draft_id: str, approved: bool, body: DecisionIn,
                  current_user, db: AsyncSession) -> DraftOut:
    try:
        decided = await company_queue.decide_draft(
            db, str(current_user.id), draft_id, approved=approved,
            decided_by=current_user.email, note=body.note,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if decided is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _draft_out(decided)


@router.post("/marketing/drafts/{draft_id}/approve", response_model=DraftOut,
             summary="Record an approval. Does not schedule or publish.")
async def approve_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                        body: DecisionIn = DecisionIn()) -> DraftOut:
    return await _decide(draft_id, True, body, current_user, db)


@router.post("/marketing/drafts/{draft_id}/reject", response_model=DraftOut,
             summary="Record a rejection.")
async def reject_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                       body: DecisionIn = DecisionIn()) -> DraftOut:
    return await _decide(draft_id, False, body, current_user, db)


# ---------------------------------------------------------------------------
# The Sales approval queue. Qualify and draft only: no route here sends a
# message, and none can. A decision is the signed-in account's own.
# ---------------------------------------------------------------------------


class LeadDraftIn(BaseModel):
    source: str = Field(..., max_length=16)
    contact_name: str = Field(..., max_length=200)
    contact_email: str = Field(..., max_length=320)
    # Storage guards only, not product limits.
    inbound_excerpt: str = Field(..., max_length=8000)
    qualification: str = Field(..., max_length=16)
    qualification_reason: str = Field(..., max_length=2000)
    reply_text: str = Field(..., max_length=8000)
    ai_disclosure: str = Field(..., max_length=1000)


class LeadDraftOut(BaseModel):
    draft_id: str
    source: str
    contact_name: str
    contact_email: str
    inbound_excerpt: str
    qualification: str
    qualification_reason: str
    reply_text: str
    ai_disclosure: str
    status: str
    decided_by: Optional[str]
    decision_note: Optional[str]


def _lead_out(d: LeadDraft) -> LeadDraftOut:
    return LeadDraftOut(
        draft_id=d.draft_id, source=d.source, contact_name=d.contact_name,
        contact_email=d.contact_email, inbound_excerpt=d.inbound_excerpt,
        qualification=d.qualification.value, qualification_reason=d.qualification_reason,
        reply_text=d.reply_text, ai_disclosure=d.ai_disclosure, status=d.status.value,
        decided_by=d.decided_by, decision_note=d.decision_note,
    )


@router.post("/sales/drafts", response_model=LeadDraftOut, status_code=201,
             summary="Queue a qualified lead and drafted reply for approval")
async def queue_lead_draft(body: LeadDraftIn, current_user: CurrentUser, db: DbSession) -> LeadDraftOut:
    try:
        draft = await company_sales_queue.insert_lead_draft(
            db, str(current_user.id), source=body.source, contact_name=body.contact_name,
            contact_email=body.contact_email, inbound_excerpt=body.inbound_excerpt,
            qualification=body.qualification, qualification_reason=body.qualification_reason,
            reply_text=body.reply_text, ai_disclosure=body.ai_disclosure,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _lead_out(draft)


@router.get("/sales/drafts", response_model=List[LeadDraftOut], summary="List the caller's lead drafts")
async def list_lead_queue(
    current_user: CurrentUser, db: DbSession,
    status: Optional[str] = Query(None, pattern="^(drafted|approved|rejected)$"),
) -> List[LeadDraftOut]:
    drafts = await company_sales_queue.list_lead_drafts(db, str(current_user.id), status)
    return [_lead_out(d) for d in drafts]


async def _decide_lead(draft_id: str, approved: bool, body: DecisionIn,
                       current_user, db: AsyncSession) -> LeadDraftOut:
    try:
        decided = await company_sales_queue.decide_lead_draft(
            db, str(current_user.id), draft_id, approved=approved,
            decided_by=current_user.email, note=body.note,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if decided is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _lead_out(decided)


@router.post("/sales/drafts/{draft_id}/approve", response_model=LeadDraftOut,
             summary="Record an approval. Does not send anything.")
async def approve_lead_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                             body: DecisionIn = DecisionIn()) -> LeadDraftOut:
    return await _decide_lead(draft_id, True, body, current_user, db)


@router.post("/sales/drafts/{draft_id}/reject", response_model=LeadDraftOut,
             summary="Record a rejection.")
async def reject_lead_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                            body: DecisionIn = DecisionIn()) -> LeadDraftOut:
    return await _decide_lead(draft_id, False, body, current_user, db)
