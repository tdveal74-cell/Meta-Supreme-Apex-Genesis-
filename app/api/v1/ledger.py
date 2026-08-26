"""
Live State Ledger endpoints: the present tense of DEVON.

Every route is owner scoped through the authenticated user. Writes go through
``app.services.live_state_ledger``, which enforces the doctrine in
``services.devon.ecosystem``. A refused write returns 409 with every reason,
never a partial success and never a bare 500.

The ledger observes the approval authority. There is deliberately no route here
that approves anything: approvals are raised and ruled under /devon/approvals,
and this surface only records what that authority did.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services.live_state_ledger import LedgerConflict, LedgerRefused, ledger
from services.devon import ecosystem

router = APIRouter(prefix="/ledger", tags=["Live State Ledger"])


def _refused(exc: LedgerRefused) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"refused": True, "reasons": exc.reasons},
    )


def _conflict(exc: LedgerConflict) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"conflict": True, "reason": str(exc)},
    )


@router.get("/doctrine")
async def ledger_doctrine() -> Dict[str, Any]:
    """The whole organism as inert structure: hierarchy, layers, events, rules."""
    return ecosystem.summary()


class IntentCreate(BaseModel):
    channel: str = Field(..., min_length=1, max_length=64)
    stated: str = Field(..., min_length=1, max_length=20_000)
    is_effect: bool = False


@router.post("/intents", status_code=status.HTTP_201_CREATED)
async def open_intent(
    body: IntentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Mint the one Universal Intent for an input and open its record."""
    try:
        return await ledger.open_intent(
            db,
            owner_id=str(current_user.id),
            channel=body.channel,
            stated=body.stated,
            is_effect=body.is_effect,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/intents/{intent_id}")
async def read_intent(
    intent_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """One intent with its events, actions, artifacts, and receipt."""
    try:
        return await ledger.read_intent(
            db, owner_id=str(current_user.id), intent_id=intent_id
        )
    except LedgerRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"reasons": exc.reasons}
        ) from exc


class EventAppend(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)
    action_id: Optional[str] = Field(default=None, max_length=64)
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/intents/{intent_id}/events", status_code=status.HTTP_201_CREATED)
async def append_event(
    intent_id: str,
    body: EventAppend,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Append one universal event, or refuse and name the law it breaks."""
    try:
        return await ledger.append_event(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            name=body.name,
            action_id=body.action_id,
            payload=body.payload,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc
    except LedgerConflict as exc:
        raise _conflict(exc) from exc


class ActionPlan(BaseModel):
    duty: str = Field(..., min_length=1, max_length=200)
    detail: Dict[str, Any] = Field(default_factory=dict)


@router.post("/intents/{intent_id}/actions", status_code=status.HTTP_201_CREATED)
async def plan_action(
    intent_id: str,
    body: ActionPlan,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Route a duty to n8n or Zapier, or park it UNROUTED rather than guess."""
    try:
        return await ledger.plan_action(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            duty=body.duty,
            detail=body.detail,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc


class ApprovalObservation(BaseModel):
    approval_request_id: str = Field(..., min_length=1, max_length=64)
    state: str = Field(..., min_length=1, max_length=24)
    what_happens: str = Field(..., min_length=1, max_length=10_000)
    action_id: Optional[str] = Field(default=None, max_length=64)
    decided_by: str = Field(default="", max_length=120)


@router.post("/intents/{intent_id}/approvals", status_code=status.HTTP_201_CREATED)
async def record_approval(
    intent_id: str,
    body: ApprovalObservation,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Record what the approval authority did. This route never grants."""
    try:
        return await ledger.record_approval(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            approval_request_id=body.approval_request_id,
            state=body.state,
            what_happens=body.what_happens,
            action_id=body.action_id,
            decided_by=body.decided_by,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc
    except LedgerConflict as exc:
        raise _conflict(exc) from exc


class ArtifactCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=2000)
    sha256: str = Field(default="", max_length=64)
    media_type: str = Field(default="application/octet-stream", max_length=200)
    action_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/intents/{intent_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def record_artifact(
    intent_id: str,
    body: ArtifactCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return await ledger.record_artifact(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            path=body.path,
            sha256=body.sha256,
            media_type=body.media_type,
            action_id=body.action_id,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc


class VerificationCreate(BaseModel):
    method: str = Field(..., min_length=1, max_length=200)
    passed: bool
    evidence: str = Field(..., min_length=1, max_length=10_000)
    action_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/intents/{intent_id}/verifications", status_code=status.HTTP_201_CREATED)
async def record_verification(
    intent_id: str,
    body: VerificationCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Record a read back. Evidence is mandatory; a claim is not a verification."""
    try:
        return await ledger.record_verification(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            method=body.method,
            passed=body.passed,
            evidence=body.evidence,
            action_id=body.action_id,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc


class ErrorCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    intent_id: Optional[str] = Field(default=None, max_length=64)
    action_id: Optional[str] = Field(default=None, max_length=64)
    detail: Dict[str, Any] = Field(default_factory=dict)


@router.post("/errors", status_code=status.HTTP_201_CREATED)
async def record_error(
    body: ErrorCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await ledger.record_error(
        db,
        owner_id=str(current_user.id),
        message=body.message,
        intent_id=body.intent_id,
        action_id=body.action_id,
        detail=body.detail,
    )


class LearningCandidateCreate(BaseModel):
    summary: str = Field(..., min_length=1, max_length=10_000)


@router.post(
    "/intents/{intent_id}/learning-candidates", status_code=status.HTTP_201_CREATED
)
async def record_learning_candidate(
    intent_id: str,
    body: LearningCandidateCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Park something that might become a lesson. The learning lane rules on it."""
    try:
        return await ledger.record_learning_candidate(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            summary=body.summary,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc


class ReceiptCreate(BaseModel):
    what_happened: str = Field(..., min_length=1, max_length=20_000)
    verification: str = Field(..., min_length=1, max_length=20_000)
    provenance: str = Field(..., min_length=1, max_length=10_000)
    artifacts: List[str] = Field(default_factory=list, max_length=200)
    learned: str = Field(default="", max_length=10_000)
    next_steps: str = Field(default="", max_length=10_000)


@router.post("/intents/{intent_id}/receipt", status_code=status.HTTP_201_CREATED)
async def issue_receipt(
    intent_id: str,
    body: ReceiptCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Close an intent with its one Universal Receipt. A second is refused."""
    try:
        return await ledger.issue_receipt(
            db,
            owner_id=str(current_user.id),
            intent_id=intent_id,
            what_happened=body.what_happened,
            verification=body.verification,
            provenance=body.provenance,
            artifacts=body.artifacts,
            learned=body.learned,
            next_steps=body.next_steps,
        )
    except LedgerRefused as exc:
        raise _refused(exc) from exc
    except LedgerConflict as exc:
        raise _conflict(exc) from exc


class EmergencyStopEngage(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


@router.get("/emergency-stop")
async def read_emergency_stop(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    stopped = await ledger.emergency_stopped(db, owner_id=str(current_user.id))
    return {
        "engaged": stopped,
        "rule": ecosystem.EMERGENCY_STOP_RULE,
        "release_authority": ecosystem.EMERGENCY_STOP_AUTHORITY.name,
    }


@router.post("/emergency-stop")
async def engage_emergency_stop(
    body: EmergencyStopEngage,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Engage the stop. Any level may engage: a stop that needs permission is not a stop."""
    return await ledger.engage_emergency_stop(
        db,
        owner_id=str(current_user.id),
        reason=body.reason,
        changed_by=str(current_user.email),
    )


class EmergencyStopRelease(BaseModel):
    actor: str = Field(default="TEE", max_length=32)


@router.post("/emergency-stop/release")
async def release_emergency_stop(
    body: EmergencyStopRelease,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Release the stop. Only Tee, because releasing lets effects run again."""
    try:
        actor = ecosystem.Authority[body.actor.strip().upper()]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{body.actor}' is not a level in the locked hierarchy.",
        ) from exc
    try:
        return await ledger.release_emergency_stop(
            db,
            owner_id=str(current_user.id),
            actor=actor,
            changed_by=str(current_user.email),
        )
    except LedgerRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"refused": True, "reasons": exc.reasons},
        ) from exc
