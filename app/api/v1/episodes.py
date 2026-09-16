"""Episode transcripts, and whether an idea has already been on air.

Both routes are account gated rather than service key gated, deliberately.
A transcript belongs to an owner and the service key's principal is
``machine``, which owns nothing: a machine route would have to take an
``owner_id`` in its body, and a leaked key could then write into any owner's
catalogue. The render lane's own authentication is a real question and it is
not answered by widening this door, so it stays an account door until it is.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.knowledge import KnowledgeItem
from app.security.deps import CurrentUser
from app.services.episodes import (
    COVERAGE_FLOOR,
    EPISODE_SOURCE_TYPE,
    MAX_COVERAGE_HITS,
    already_covered,
    record_episode_transcript,
)
from services.intelligence.providers import ProviderConfigError

router = APIRouter(prefix="/episodes", tags=["Episodes"])


class TranscriptIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    transcript: str = Field(..., min_length=1, max_length=500_000)
    show: Optional[str] = Field(None, max_length=120)
    source_uri: Optional[str] = Field(None, max_length=2000)
    spoken_at: Optional[str] = Field(None, max_length=64)
    transcript_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    provider: Optional[str] = Field(None, max_length=64)


class TranscriptOut(BaseModel):
    id: str
    title: str
    show: str = ""
    created: bool
    fingerprint: str
    chunk_count: int = 0
    status: str


class CoverageOut(BaseModel):
    covered: bool
    answerable: bool = True
    question: str
    reason: str
    floor: float
    matches: List[Dict[str, Any]]
    nearest: Optional[Dict[str, Any]] = None


@router.post("/transcripts", response_model=TranscriptOut, status_code=status.HTTP_201_CREATED)
async def add_transcript(
    body: TranscriptIn,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TranscriptOut:
    """Store one episode transcript, or hand back the one already held.

    A repeat is a 201 with ``created`` false rather than a 409. Re-running a
    render is normal and the caller wants the item either way; what it must
    not get is a silent second copy, which would let one episode outvote the
    catalogue on every later search.
    """
    try:
        item, created = await record_episode_transcript(
            db,
            owner_id=str(user.id),
            title=body.title,
            transcript=body.transcript,
            show=body.show,
            source_uri=body.source_uri,
            spoken_at=body.spoken_at,
            transcript_confidence=body.transcript_confidence,
            provider=body.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"the embedding provider is not configured: {exc}",
        ) from exc

    await db.commit()
    await db.refresh(item)
    meta = item.meta or {}
    return TranscriptOut(
        id=str(item.id),
        title=item.title,
        show=str(meta.get("show") or ""),
        created=created,
        fingerprint=str(item.external_id or ""),
        chunk_count=int(meta.get("chunk_count") or 0),
        status=item.status,
    )


@router.get("/covered", response_model=CoverageOut)
async def covered(
    user: CurrentUser,
    q: str = "",
    limit: int = MAX_COVERAGE_HITS,
    floor: float = COVERAGE_FLOOR,
    db: AsyncSession = Depends(get_db),
) -> CoverageOut:
    """Have I already said this on air, and where.

    Episode transcripts only. A draft outline matching is not coverage.
    """
    if floor <= 0 or floor > 2:
        raise HTTPException(
            status_code=422,
            detail="floor is a cosine distance ceiling and must be within (0, 2].",
        )
    try:
        answer = await already_covered(
            db, owner_id=str(user.id), question=q, floor=floor, limit=limit
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"the embedding provider is not configured: {exc}",
        ) from exc
    return CoverageOut(**answer)


@router.get("/transcripts")
async def list_transcripts(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """The owner's stored episodes, newest first. Titles and provenance only."""
    result = await db.execute(
        select(KnowledgeItem)
        .where(
            KnowledgeItem.owner_id == str(user.id),
            KnowledgeItem.source_type == EPISODE_SOURCE_TYPE,
        )
        .order_by(KnowledgeItem.created_at.desc())
        .limit(100)
    )
    items = result.scalars().all()
    return {
        "count": len(items),
        "episodes": [
            {
                "id": str(item.id),
                "title": item.title,
                "show": str((item.meta or {}).get("show") or ""),
                "spoken_at": str((item.meta or {}).get("spoken_at") or ""),
                "source_uri": item.source_uri or "",
                "fingerprint": item.external_id or "",
                "status": item.status,
                "chunk_count": int((item.meta or {}).get("chunk_count") or 0),
            }
            for item in items
        ],
    }
