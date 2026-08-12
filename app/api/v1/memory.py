"""
Memory endpoints — transparent, editable, deletable.
Hard deletes only.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.memory import Memory
from app.security.deps import CurrentUser

router = APIRouter(prefix="/memory", tags=["Memory"])

_MEMORY_TYPES = ("preference", "context", "decision", "lesson", "pattern", "other")


class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    memory_type: str = Field("other", pattern="^(preference|context|decision|lesson|pattern|other)$")
    importance: int = Field(5, ge=1, le=10)
    project_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=4000)
    memory_type: Optional[str] = Field(
        None, pattern="^(preference|context|decision|lesson|pattern|other)$"
    )
    importance: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    id: str
    memory_type: str
    content: str
    importance: int
    is_active: bool
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


def _to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        memory_type=memory.memory_type,
        content=memory.content,
        importance=memory.importance,
        is_active=memory.is_active,
        project_id=memory.project_id,
        metadata=memory.meta or {},
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


async def _get_owned_memory(memory_id: str, user_id: str, db: AsyncSession) -> Memory:
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found"
        )
    return memory


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    current_user: CurrentUser,
    memory_type: Optional[str] = None,
    include_inactive: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Memory)
        .where(Memory.user_id == current_user.id)
        .order_by(Memory.updated_at.desc())
    )
    if memory_type:
        if memory_type not in _MEMORY_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"memory_type must be one of {', '.join(_MEMORY_TYPES)}",
            )
        stmt = stmt.where(Memory.memory_type == memory_type)
    if not include_inactive:
        stmt = stmt.where(Memory.is_active.is_(True))
    result = await db.execute(stmt)
    return [_to_response(m) for m in result.scalars().all()]


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    memory = Memory(
        user_id=current_user.id,
        project_id=payload.project_id,
        memory_type=payload.memory_type,
        content=payload.content.strip(),
        importance=payload.importance,
        is_active=True,
        meta={"origin": "user"},
    )
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return _to_response(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    memory = await _get_owned_memory(memory_id, current_user.id, db)
    if payload.content is not None:
        memory.content = payload.content.strip()
    if payload.memory_type is not None:
        memory.memory_type = payload.memory_type
    if payload.importance is not None:
        memory.importance = payload.importance
    if payload.is_active is not None:
        memory.is_active = payload.is_active
    await db.flush()
    await db.refresh(memory)
    return _to_response(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    memory = await _get_owned_memory(memory_id, current_user.id, db)
    await db.delete(memory)
    await db.flush()
