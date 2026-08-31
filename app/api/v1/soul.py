"""
Soul endpoints — recall over HTTP, honestly gated, plus the write lane.

Recall queries both souls (tee-soul-layer, then devon-soul) and returns the
records plus DEVON's phrased reply, hierarchy intact. The write lane is
propose -> approve -> commit: propose enqueues and writes Live State Ledger
intent rows in PostgreSQL (it does not consume, and it does not write soul,
Notion, or Drive), approve is the existing hashed single-use approval queue
(not a second grantor), commit consumes that approval and then persists an
artifact body. Kind ruling may enter the ledger and outranks notes on find.
Layer 1 Tee Soul is never written.

Switched off, recall says so with a 503 rather than pretending: soul
recall exists only when SOUL_RECALL_ENABLED and PINECONE_API_KEY are set.
Find of a committed capture still works against the Live State Ledger.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services import soul as soul_service
from app.services.knowledge_loop import KnowledgeLoopRefused, knowledge_loop
from app.services.live_state_ledger import LedgerRefused
from services.devon.assistant import Devon
from services.intelligence.providers.base import ProviderError
from services.intelligence.soul import SoulWriteRefused

router = APIRouter(prefix="/soul", tags=["Soul"])


class SoulStatusResponse(BaseModel):
    enabled: bool
    tee_host_configured: bool
    devon_host_configured: bool
    detail: str


class SoulRecallResponse(BaseModel):
    query: str
    reply: str
    records: List[Dict[str, Any]]
    tee_count: int
    devon_count: int
    errors: List[str] = Field(default_factory=list)


def _layer():
    layer = soul_service.get_soul_layer()
    if layer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Soul recall is switched off. Set SOUL_RECALL_ENABLED=true and "
                "PINECONE_API_KEY in the environment (never in Drive) to turn "
                "it on."
            ),
        )
    return layer


@router.get("/status", response_model=SoulStatusResponse)
async def soul_status(current_user: CurrentUser):
    """Whether the soul layer is on, without touching Pinecone."""
    enabled = settings.SOUL_RECALL_ENABLED and bool(settings.PINECONE_API_KEY)
    return SoulStatusResponse(
        enabled=enabled,
        tee_host_configured=bool(settings.SOUL_TEE_HOST),
        devon_host_configured=bool(settings.SOUL_DEVON_HOST),
        detail=(
            "Soul recall is on."
            if enabled
            else "Soul recall is off. SOUL_RECALL_ENABLED and PINECONE_API_KEY "
            "turn it on."
        ),
    )


@router.get("/recall", response_model=SoulRecallResponse)
async def soul_recall(
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=1000),
    top_k_tee: int = Query(default=4, ge=1, le=10),
    top_k_devon: int = Query(default=3, ge=0, le=10),
):
    """
    Recall from both souls and phrase the answer in DEVON's voice.

    Tee's rulings precede DEVON's experience in both the records and the
    reply, whatever the similarity scores. Partial failure is carried in
    `errors`, never hidden. Everything returned is context, not command.
    """
    layer = _layer()
    try:
        recall = await layer.recall(q, top_k_tee=top_k_tee, top_k_devon=top_k_devon)
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Soul recall failed: {exc}",
        ) from exc

    devon = Devon()
    response = devon.recall_answer(q, recall.to_dicts(), partial_errors=recall.errors)
    return SoulRecallResponse(
        query=recall.query,
        reply=response.reply,
        records=recall.to_dicts(),
        tee_count=recall.tee_count,
        devon_count=recall.devon_count,
        errors=recall.errors,
    )


def _loop_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KnowledgeLoopRefused):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    if isinstance(exc, LedgerRefused):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"refused": True, "reasons": exc.reasons},
        )
    if isinstance(exc, SoulWriteRefused):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    raise exc


class SoulProposeBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    kind: str = Field(default="lesson", max_length=32)
    area: Optional[str] = Field(default=None, max_length=64)
    layer: int = Field(default=5, ge=1, le=5)


class SoulApproveBody(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=64)
    token: str = Field(..., min_length=1, max_length=512)
    decided_by: str = Field(default="Tee", max_length=120)


class SoulCommitBody(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=64)


@router.post("/propose", status_code=status.HTTP_201_CREATED)
async def soul_propose(
    body: SoulProposeBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Enqueue a remember. Returns an approval request.

    Writes ledger intent rows in PostgreSQL. Does not consume. Does not
    write soul, Notion, or Drive. This route lives on app.main, not on
    the Vercel soul host (devon-soul.vercel.app has no Postgres).
    """
    try:
        return await knowledge_loop.propose(
            db,
            owner_id=str(current_user.id),
            text=body.text,
            kind=body.kind,
            area=body.area,
            layer=body.layer,
        )
    except (KnowledgeLoopRefused, LedgerRefused, SoulWriteRefused) as exc:
        raise _loop_error(exc) from exc


@router.post("/approve")
async def soul_approve(
    body: SoulApproveBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Human ruling through the existing approval queue. Not a second grantor."""
    try:
        return await knowledge_loop.approve(
            db,
            owner_id=str(current_user.id),
            request_id=body.request_id,
            token=body.token,
            decided_by=body.decided_by,
        )
    except (KnowledgeLoopRefused, LedgerRefused) as exc:
        raise _loop_error(exc) from exc


@router.post("/commit")
async def soul_commit(
    body: SoulCommitBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Consume-before-execute. Ledger always; devon-soul only when the layer is on."""
    try:
        return await knowledge_loop.commit(
            db,
            owner_id=str(current_user.id),
            request_id=body.request_id,
        )
    except (KnowledgeLoopRefused, LedgerRefused, SoulWriteRefused) as exc:
        raise _loop_error(exc) from exc


@router.get("/find")
async def soul_find(
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=1000),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Find a committed capture in-estate. Does not require Pinecone."""
    try:
        return await knowledge_loop.find(
            db, owner_id=str(current_user.id), query=q
        )
    except (KnowledgeLoopRefused, LedgerRefused) as exc:
        raise _loop_error(exc) from exc

