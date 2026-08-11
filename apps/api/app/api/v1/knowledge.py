"""
Knowledge endpoints — upload, list, search, and remove knowledge.

Ingestion is synchronous in this phase (chunk + embed inline). Ownership
is enforced on every route; search only ever touches the caller's items.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.knowledge import Embedding, KnowledgeItem
from app.models.project import Project
from app.security.deps import CurrentUser
from app.services.knowledge import ingest_knowledge, search_knowledge
from services.intelligence.providers import ProviderConfigError

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

_SOURCE_TYPES = ("txt", "markdown", "manual", "url")


class KnowledgeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=500_000)
    source_type: str = Field("manual", pattern="^(txt|markdown|manual|url)$")
    source_uri: Optional[str] = Field(None, max_length=2000)
    project_id: Optional[str] = None


class KnowledgeItemResponse(BaseModel):
    id: str
    title: str
    source_type: str
    source_uri: Optional[str] = None
    status: str
    project_id: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(5, ge=1, le=20)
    project_id: Optional[str] = None


class KnowledgeSearchHit(BaseModel):
    knowledge_item_id: str
    title: str
    source_type: str
    chunk_index: int
    content: str
    distance: float


def _to_response(item: KnowledgeItem) -> KnowledgeItemResponse:
    meta = item.meta or {}
    return KnowledgeItemResponse(
        id=item.id,
        title=item.title,
        source_type=item.source_type,
        source_uri=item.source_uri,
        status=item.status,
        project_id=item.project_id,
        chunk_count=int(meta.get("chunk_count", 0)),
        metadata=meta,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _get_owned_item(
    item_id: str, user_id: str, db: AsyncSession
) -> KnowledgeItem:
    result = await db.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id,
            KnowledgeItem.owner_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found"
        )
    return item


@router.get("", response_model=List[KnowledgeItemResponse])
async def list_knowledge(
    current_user: CurrentUser,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(KnowledgeItem)
        .where(
            KnowledgeItem.owner_id == current_user.id,
            KnowledgeItem.status != "archived",
        )
        .order_by(KnowledgeItem.created_at.desc())
    )
    if project_id:
        stmt = stmt.where(KnowledgeItem.project_id == project_id)
    result = await db.execute(stmt)
    return [_to_response(item) for item in result.scalars().all()]


@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    payload: KnowledgeCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if payload.source_type not in _SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source_type must be one of {', '.join(_SOURCE_TYPES)}",
        )
    if payload.project_id:
        owned = await db.execute(
            select(Project).where(
                Project.id == payload.project_id,
                Project.owner_id == current_user.id,
                Project.status != "deleted",
            )
        )
        if owned.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

    try:
        item = await ingest_knowledge(
            db,
            owner_id=current_user.id,
            title=payload.title,
            content=payload.content,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            project_id=payload.project_id,
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding provider is not configured: {exc}",
        ) from exc

    return _to_response(item)


@router.post("/search", response_model=List[KnowledgeSearchHit])
async def search(
    payload: KnowledgeSearchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        hits = await search_knowledge(
            db,
            owner_id=current_user.id,
            query=payload.query,
            limit=payload.limit,
            project_id=payload.project_id,
        )
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding provider is not configured: {exc}",
        ) from exc
    return [KnowledgeSearchHit(**hit) for hit in hits]


@router.get("/{item_id}", response_model=KnowledgeItemResponse)
async def get_knowledge_item(
    item_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(item_id, current_user.id, db)
    count = await db.execute(
        select(func.count(Embedding.id)).where(Embedding.knowledge_item_id == item.id)
    )
    response = _to_response(item)
    response.chunk_count = int(count.scalar_one())
    return response


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_item(
    item_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(item_id, current_user.id, db)
    await db.execute(sa_delete(Embedding).where(Embedding.knowledge_item_id == item.id))
    await db.delete(item)
    await db.flush()
