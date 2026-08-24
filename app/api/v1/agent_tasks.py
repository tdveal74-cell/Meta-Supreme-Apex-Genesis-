"""Authenticated durable Agent Tasks surface for DEVON.

This router exposes task state and learning records. DEVON core remains
execution-free; tool execution happens through registered capability adapters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.security.deps import CurrentUser
from app.services.agent_tasks import agent_tasks_service
from services.agent_runtime.runtime import AgentRuntimeError

router = APIRouter(prefix="/agent-tasks", tags=["DEVON Agent Tasks"])


class PlannedStepBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    tool: str = Field(..., min_length=1, max_length=200)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=4000)
    expected_outcome: str = Field(default="", max_length=4000)


class TaskCreateBody(BaseModel):
    goal: str = Field(..., min_length=1, max_length=20_000)
    context: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None
    steps: Optional[List[PlannedStepBody]] = Field(default=None, max_length=12)


class TaskRunBody(BaseModel):
    max_steps: int = Field(default=20, ge=1, le=100)


class TaskCancelBody(BaseModel):
    reason: str = Field(default="cancelled by operator", min_length=1, max_length=2000)


class TaskRollbackBody(BaseModel):
    checkpoint_id: str = Field(..., min_length=1, max_length=100)


class MemoryCreateBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)
    tags: List[str] = Field(default_factory=list, max_length=50)
    source: str = Field(default="operator", min_length=1, max_length=120)
    project_id: Optional[str] = None


class SkillUpsertBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=20_000)
    instructions: str = Field(..., min_length=1, max_length=100_000)
    provenance: str = Field(default="operator", min_length=1, max_length=120)


async def _ensure_owned_project(
    project_id: Optional[str],
    *,
    owner_id: str,
    db: AsyncSession,
) -> None:
    if not project_id:
        return
    result = await db.execute(
        select(Project.id).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _task_view(task) -> Dict[str, Any]:
    return task.to_dict()


@router.get("/tools")
async def tool_catalog(current_user: CurrentUser) -> Dict[str, object]:
    del current_user
    return agent_tasks_service.tool_catalog()


@router.get("")
async def list_tasks(
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    tasks = await agent_tasks_service.list_tasks(
        db,
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [_task_view(task) for task in tasks]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    await _ensure_owned_project(body.project_id, owner_id=current_user.id, db=db)
    try:
        task = await agent_tasks_service.create_task(
            db,
            owner_id=current_user.id,
            goal=body.goal,
            context=body.context,
            project_id=body.project_id,
            planned_steps=[step.model_dump() for step in body.steps]
            if body.steps is not None
            else None,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _task_view(task)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    task = await agent_tasks_service.get_task(
        db,
        owner_id=current_user.id,
        task_id=task_id,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return _task_view(task)


@router.post("/{task_id}/run")
async def run_task(
    task_id: str,
    body: TaskRunBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        result = await agent_tasks_service.run_until_blocked(
            db,
            owner_id=current_user.id,
            task_id=task_id,
            max_steps=body.max_steps,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent task not found") from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result.to_dict()


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    body: TaskCancelBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        task = await agent_tasks_service.cancel(
            db,
            owner_id=current_user.id,
            task_id=task_id,
            reason=body.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent task not found") from exc
    return _task_view(task)


@router.post("/{task_id}/rollback")
async def rollback_task(
    task_id: str,
    body: TaskRollbackBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        task = await agent_tasks_service.rollback(
            db,
            owner_id=current_user.id,
            task_id=task_id,
            checkpoint_id=body.checkpoint_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent task not found") from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _task_view(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    deleted = await agent_tasks_service.delete_task(
        db,
        owner_id=current_user.id,
        task_id=task_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/learning/memories")
async def list_memories(
    current_user: CurrentUser,
    project_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, object]]:
    await _ensure_owned_project(project_id, owner_id=current_user.id, db=db)
    records = await agent_tasks_service.learning.list_memories(
        db,
        owner_id=current_user.id,
        project_id=project_id,
        limit=limit,
    )
    return [record.to_dict() for record in records]


@router.post("/learning/memories", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: MemoryCreateBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, object]:
    await _ensure_owned_project(body.project_id, owner_id=current_user.id, db=db)
    try:
        record = await agent_tasks_service.learning.remember(
            db,
            owner_id=current_user.id,
            text=body.text,
            tags=body.tags,
            source=body.source,
            project_id=body.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return record.to_dict()


@router.delete("/learning/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    deleted = await agent_tasks_service.learning.forget(
        db,
        owner_id=current_user.id,
        memory_id=memory_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/learning/skills")
async def list_skills(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, object]]:
    records = await agent_tasks_service.learning.list_skills(db, owner_id=current_user.id)
    return [record.to_dict() for record in records]


@router.put("/learning/skills/{name}")
async def upsert_skill(
    name: str,
    body: SkillUpsertBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, object]:
    try:
        record = await agent_tasks_service.learning.upsert_skill(
            db,
            owner_id=current_user.id,
            name=name,
            description=body.description,
            instructions=body.instructions,
            provenance=body.provenance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return record.to_dict()
