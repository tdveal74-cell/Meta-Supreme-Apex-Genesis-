"""
Soul endpoints — recall over HTTP, honestly gated.

The read lane only. Recall queries both souls (tee-soul-layer, then
devon-soul) and returns the records plus DEVON's phrased reply, hierarchy
intact. The write lane (propose → approve → commit) deliberately has no HTTP
surface yet: a devon-soul write is an effect, and its approval flow runs
through the live queue, not through an endpoint that could be scripted.

Switched off, the lane says so with a 503 rather than pretending: soul
recall exists only when SOUL_RECALL_ENABLED and PINECONE_API_KEY are set.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.security.deps import CurrentUser
from app.services import soul as soul_service
from services.devon.assistant import Devon
from services.intelligence.providers.base import ProviderError

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
