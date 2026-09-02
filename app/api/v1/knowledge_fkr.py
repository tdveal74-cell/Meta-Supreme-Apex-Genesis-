"""FKR endpoints: federated ingest and hybrid query.

Mounted alongside the existing knowledge router. Does not replace
POST /knowledge or POST /knowledge/search (pure-semantic remains).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from services.intelligence.providers import ProviderConfigError
from services.knowledge.pipeline import ingest_and_distill, query_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge FKR"])


class FederatedIngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=500_000)
    source_type: str = Field("manual", max_length=64)
    source: Optional[str] = Field(None, max_length=64)
    external_id: Optional[str] = Field(None, max_length=512)
    source_uri: Optional[str] = Field(None, max_length=2000)
    project_id: Optional[str] = None
    acl_tokens: List[str] = Field(default_factory=list)


class FederatedIngestResponse(BaseModel):
    id: str
    title: str
    status: str
    source: Optional[str] = None
    external_id: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FederatedQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(6, ge=1, le=20)
    # A uuid or nothing: the ACL predicate casts it, and a string that is
    # not a uuid must be refused here as 422, not inside the SQL as 500.
    project_id: Optional[UUID] = None
    user_tokens: List[str] = Field(default_factory=list)


@router.post(
    "/ingest",
    response_model=FederatedIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def federated_ingest(
    payload: FederatedIngestRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await ingest_and_distill(
            db,
            owner_id=current_user.id,
            title=payload.title,
            content=payload.content,
            source_type=payload.source_type,
            source=payload.source,
            external_id=payload.external_id,
            source_uri=payload.source_uri,
            project_id=payload.project_id,
            acl_tokens=payload.acl_tokens,
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding provider is not configured: {exc}",
        ) from exc

    meta = item.meta or {}
    return FederatedIngestResponse(
        id=item.id,
        title=item.title,
        status=item.status,
        source=getattr(item, "source", None),
        external_id=getattr(item, "external_id", None),
        chunk_count=int(meta.get("chunk_count", 0)),
        metadata=meta,
    )


@router.post("/query")
async def federated_query(
    payload: FederatedQueryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await query_knowledge(
            db,
            owner_id=current_user.id,
            query=payload.query,
            limit=payload.limit,
            project_id=str(payload.project_id) if payload.project_id else None,
            user_tokens=payload.user_tokens,
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding provider is not configured: {exc}",
        ) from exc
