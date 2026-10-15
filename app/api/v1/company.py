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
from app.services import (
    company_product_queue,
    company_queue,
    company_research_queue,
    company_sales_queue,
    company_support_queue,
)
from app.services.company_revenue import read_month_revenue
from app.services.provider_usage import read_usage, utc_today
from services.company.functions import list_functions
from services.company.marketing import BANNED_DASHES, PostDraft, QueueRefusal
from services.company.product import DuplicateProposal, Proposal
from services.company.research import DuplicateFinding, Finding
from services.company.sales import LeadDraft
from services.company.scoreboard import build_scoreboard
from services.company.support import CommentDraft

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
    revenue, revenue_notes = await read_month_revenue()
    board = build_scoreboard(
        revenue_month_usd=revenue,
        calls_today=usage.calls,
        tokens_today=usage.total_tokens,
        cap_tokens=cap if cap > 0 else None,
    )
    return ScoreboardOut(date=day.isoformat(), notes=[*revenue_notes, *board.notes], **{
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


# The pattern refuses a NUL byte, which the database cannot store, and the dashes
# a decision note may not carry (ruled by Tee 2026-10-14). It is a pattern and not a
# validator because a validator's ValueError cannot be serialised by this app's
# validation error handler, which turns a 422 into a 500. The rules modules check
# the same thing again, so a caller that skips the route is still refused.
_NOTE_PATTERN = "^[^\\x00" + "".join(f"\\x{{{ord(ch):x}}}" for ch in BANNED_DASHES) + "]*$"


class DecisionIn(BaseModel):
    note: Optional[str] = Field(None, max_length=2000, pattern=_NOTE_PATTERN)


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
    # Optional on one to one email, by Tee's ruling of 2026-10-14.
    ai_disclosure: Optional[str] = Field(None, max_length=1000)


class LeadDraftOut(BaseModel):
    draft_id: str
    source: str
    contact_name: str
    contact_email: str
    inbound_excerpt: str
    qualification: str
    qualification_reason: str
    reply_text: str
    ai_disclosure: Optional[str]
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


# ---------------------------------------------------------------------------
# The Support approval queue. Draft only: no route here posts a comment, and
# none can. A decision is the signed-in account's own.
# ---------------------------------------------------------------------------


class CommentDraftIn(BaseModel):
    video_id: str = Field(..., max_length=11)
    comment_id: str = Field(..., max_length=129)
    commenter_name: str = Field(..., max_length=200)
    # Storage guards only, not product limits.
    comment_text: str = Field(..., max_length=8000)
    reply_text: str = Field(..., max_length=8000)
    reply_basis: str = Field(..., max_length=2000)
    ai_disclosure: str = Field(..., max_length=1000)


class CommentDraftOut(BaseModel):
    draft_id: str
    video_id: str
    comment_id: str
    commenter_name: str
    comment_text: str
    reply_text: str
    reply_basis: str
    ai_disclosure: str
    status: str
    decided_by: Optional[str]
    decision_note: Optional[str]


def _comment_out(d: CommentDraft) -> CommentDraftOut:
    return CommentDraftOut(
        draft_id=d.draft_id, video_id=d.video_id, comment_id=d.comment_id,
        commenter_name=d.commenter_name, comment_text=d.comment_text,
        reply_text=d.reply_text, reply_basis=d.reply_basis, ai_disclosure=d.ai_disclosure,
        status=d.status.value, decided_by=d.decided_by, decision_note=d.decision_note,
    )


@router.post("/support/drafts", response_model=CommentDraftOut, status_code=201,
             summary="Queue a drafted reply to a YouTube comment for approval")
async def queue_comment_draft(body: CommentDraftIn, current_user: CurrentUser,
                              db: DbSession) -> CommentDraftOut:
    try:
        draft = await company_support_queue.insert_comment_draft(
            db, str(current_user.id), video_id=body.video_id, comment_id=body.comment_id,
            commenter_name=body.commenter_name, comment_text=body.comment_text,
            reply_text=body.reply_text, reply_basis=body.reply_basis,
            ai_disclosure=body.ai_disclosure,
        )
    except QueueRefusal as exc:
        status = 409 if "already has a draft" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from None
    return _comment_out(draft)


@router.get("/support/drafts", response_model=List[CommentDraftOut],
            summary="List the caller's comment drafts")
async def list_comment_queue(
    current_user: CurrentUser, db: DbSession,
    status: Optional[str] = Query(None, pattern="^(drafted|approved|rejected)$"),
) -> List[CommentDraftOut]:
    drafts = await company_support_queue.list_comment_drafts(db, str(current_user.id), status)
    return [_comment_out(d) for d in drafts]


async def _decide_comment(draft_id: str, approved: bool, body: DecisionIn,
                          current_user, db: AsyncSession) -> CommentDraftOut:
    try:
        decided = await company_support_queue.decide_comment_draft(
            db, str(current_user.id), draft_id, approved=approved,
            decided_by=current_user.email, note=body.note,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if decided is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _comment_out(decided)


@router.post("/support/drafts/{draft_id}/approve", response_model=CommentDraftOut,
             summary="Record an approval. Does not post anything.")
async def approve_comment_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                                body: DecisionIn = DecisionIn()) -> CommentDraftOut:
    return await _decide_comment(draft_id, True, body, current_user, db)


@router.post("/support/drafts/{draft_id}/reject", response_model=CommentDraftOut,
             summary="Record a rejection.")
async def reject_comment_draft(draft_id: str, current_user: CurrentUser, db: DbSession,
                               body: DecisionIn = DecisionIn()) -> CommentDraftOut:
    return await _decide_comment(draft_id, False, body, current_user, db)


# ---------------------------------------------------------------------------
# The Research findings log. Read only in effect: nothing here searches,
# fetches or acts on a finding. A decision is the signed-in account's own.
# ---------------------------------------------------------------------------


class FindingIn(BaseModel):
    claim: str = Field(..., max_length=4000)
    evidence_kind: str = Field(..., max_length=16)
    evidence_ref: str = Field(..., max_length=2001)
    # Quoted source text, a storage guard only.
    evidence_excerpt: Optional[str] = Field(None, max_length=8000)
    recommendation: str = Field(..., max_length=4000)


class FindingOut(BaseModel):
    draft_id: str
    claim: str
    evidence_kind: str
    evidence_ref: str
    evidence_excerpt: Optional[str]
    recommendation: str
    status: str
    decided_by: Optional[str]
    decision_note: Optional[str]


def _finding_out(f: Finding) -> FindingOut:
    return FindingOut(
        draft_id=f.draft_id, claim=f.claim, evidence_kind=f.evidence_kind,
        evidence_ref=f.evidence_ref, evidence_excerpt=f.evidence_excerpt,
        recommendation=f.recommendation, status=f.status.value,
        decided_by=f.decided_by, decision_note=f.decision_note,
    )


@router.post("/research/findings", response_model=FindingOut, status_code=201,
             summary="Record a finding for review")
async def queue_finding(body: FindingIn, current_user: CurrentUser, db: DbSession) -> FindingOut:
    try:
        f = await company_research_queue.insert_finding(
            db, str(current_user.id), claim=body.claim, evidence_kind=body.evidence_kind,
            evidence_ref=body.evidence_ref, evidence_excerpt=body.evidence_excerpt,
            recommendation=body.recommendation,
        )
    except DuplicateFinding as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except QueueRefusal as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _finding_out(f)


@router.get("/research/findings", response_model=List[FindingOut],
            summary="List the caller's findings")
async def list_finding_queue(
    current_user: CurrentUser, db: DbSession,
    status: Optional[str] = Query(None, pattern="^(drafted|approved|rejected)$"),
) -> List[FindingOut]:
    findings = await company_research_queue.list_findings(db, str(current_user.id), status)
    return [_finding_out(f) for f in findings]


async def _decide_finding(draft_id: str, approved: bool, body: DecisionIn,
                          current_user, db: AsyncSession) -> FindingOut:
    try:
        decided = await company_research_queue.decide_finding(
            db, str(current_user.id), draft_id, approved=approved,
            decided_by=current_user.email, note=body.note,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if decided is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _finding_out(decided)


@router.post("/research/findings/{draft_id}/approve", response_model=FindingOut,
             summary="Record an adoption. Does not act on the finding.")
async def approve_finding(draft_id: str, current_user: CurrentUser, db: DbSession,
                          body: DecisionIn = DecisionIn()) -> FindingOut:
    return await _decide_finding(draft_id, True, body, current_user, db)


@router.post("/research/findings/{draft_id}/reject", response_model=FindingOut,
             summary="Record a dismissal.")
async def reject_finding(draft_id: str, current_user: CurrentUser, db: DbSession,
                         body: DecisionIn = DecisionIn()) -> FindingOut:
    return await _decide_finding(draft_id, False, body, current_user, db)


# ---------------------------------------------------------------------------
# The Product proposals log. Propose only: no route here builds, commits or
# runs anything, and none can. A decision is the signed-in account's own.
# ---------------------------------------------------------------------------


class ProposalIn(BaseModel):
    title: str = Field(..., max_length=200)
    problem: str = Field(..., max_length=4000)
    proposal: str = Field(..., max_length=8000)
    acceptance_check: str = Field(..., max_length=4000)
    reference_artifact: str = Field(..., max_length=2000)
    size: str = Field(..., max_length=8)


class ProposalOut(BaseModel):
    draft_id: str
    title: str
    problem: str
    proposal: str
    acceptance_check: str
    reference_artifact: str
    size: str
    status: str
    decided_by: Optional[str]
    decision_note: Optional[str]


def _proposal_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        draft_id=p.draft_id, title=p.title, problem=p.problem, proposal=p.proposal,
        acceptance_check=p.acceptance_check, reference_artifact=p.reference_artifact,
        size=p.size, status=p.status.value, decided_by=p.decided_by,
        decision_note=p.decision_note,
    )


@router.post("/product/proposals", response_model=ProposalOut, status_code=201,
             summary="Queue a change proposal for approval")
async def queue_proposal(body: ProposalIn, current_user: CurrentUser, db: DbSession) -> ProposalOut:
    try:
        p = await company_product_queue.insert_proposal(
            db, str(current_user.id), title=body.title, problem=body.problem,
            proposal=body.proposal, acceptance_check=body.acceptance_check,
            reference_artifact=body.reference_artifact, size=body.size,
        )
    except DuplicateProposal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except QueueRefusal as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _proposal_out(p)


@router.get("/product/proposals", response_model=List[ProposalOut],
            summary="List the caller's proposals")
async def list_proposal_queue(
    current_user: CurrentUser, db: DbSession,
    status: Optional[str] = Query(None, pattern="^(drafted|approved|rejected)$"),
) -> List[ProposalOut]:
    proposals = await company_product_queue.list_proposals(db, str(current_user.id), status)
    return [_proposal_out(p) for p in proposals]


async def _decide_proposal(draft_id: str, approved: bool, body: DecisionIn,
                           current_user, db: AsyncSession) -> ProposalOut:
    try:
        decided = await company_product_queue.decide_proposal(
            db, str(current_user.id), draft_id, approved=approved,
            decided_by=current_user.email, note=body.note,
        )
    except QueueRefusal as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if decided is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _proposal_out(decided)


@router.post("/product/proposals/{draft_id}/approve", response_model=ProposalOut,
             summary="Record an approval. Does not build anything.")
async def approve_proposal(draft_id: str, current_user: CurrentUser, db: DbSession,
                           body: DecisionIn = DecisionIn()) -> ProposalOut:
    return await _decide_proposal(draft_id, True, body, current_user, db)


@router.post("/product/proposals/{draft_id}/reject", response_model=ProposalOut,
             summary="Record a rejection.")
async def reject_proposal(draft_id: str, current_user: CurrentUser, db: DbSession,
                          body: DecisionIn = DecisionIn()) -> ProposalOut:
    return await _decide_proposal(draft_id, False, body, current_user, db)
