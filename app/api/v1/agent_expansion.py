"""Hermes expansion HTTP surface: schedules, skill proposals, subagents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services.agent_tasks import agent_tasks_service
from app.services.hermes_expansion_persistence import HermesExpansionRepository
from services.agent_runtime.expansion import SkillProposalStore

router = APIRouter(prefix="/agent-expansion", tags=["DEVON Agent Expansion"])
_repo = HermesExpansionRepository()


class ScheduleCreateBody(BaseModel):
    goal: str = Field(..., min_length=1, max_length=20_000)
    delay_seconds: int = Field(default=0, ge=0, le=31_536_000)
    context: Dict[str, Any] = Field(default_factory=dict)


class SkillProposeBody(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64)
    goal: str = Field(..., min_length=1, max_length=20_000)
    observations: List[str] = Field(default_factory=list, max_length=50)


class SkillDecideBody(BaseModel):
    approve: bool
    promote: bool = True


class SubagentSpawnBody(BaseModel):
    parent_task_id: str = Field(..., min_length=1, max_length=64)
    goal: str = Field(..., min_length=1, max_length=20_000)
    max_steps: int = Field(default=8, ge=1, le=12)
    inherit_context_keys: List[str] = Field(default_factory=list, max_length=20)


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreateBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    run_at = datetime.now(timezone.utc) + timedelta(seconds=body.delay_seconds)
    try:
        item = await _repo.create_schedule(
            db,
            owner_id=current_user.id,
            goal=body.goal,
            run_at=run_at,
            context=body.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return item.to_dict()


@router.get("/schedules")
async def list_schedules(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    items = await _repo.list_schedules(db, owner_id=current_user.id)
    return [item.to_dict() for item in items]


@router.get("/schedules/due")
async def list_due_schedules(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    items = await _repo.due_schedules(db, owner_id=current_user.id)
    await db.commit()
    return [item.to_dict() for item in items]


@router.post("/schedules/materialize")
async def materialize_due_schedules(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Create durable agent tasks for due schedules. Does not auto-run effects."""
    try:
        created = await agent_tasks_service.materialize_due_schedules(
            db, owner_id=current_user.id
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return created


@router.post("/subagents", status_code=status.HTTP_201_CREATED)
async def spawn_subagent(
    body: SubagentSpawnBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a durable child task under a parent. Does not auto-run."""
    try:
        task = await agent_tasks_service.spawn_subagent_task(
            db,
            owner_id=current_user.id,
            parent_task_id=body.parent_task_id,
            goal=body.goal,
            max_steps=body.max_steps,
            inherit_context_keys=body.inherit_context_keys,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return task.to_dict()


@router.post("/skill-proposals", status_code=status.HTTP_201_CREATED)
async def propose_skill(
    body: SkillProposeBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    store = SkillProposalStore()
    proposal = store.propose_from_task(
        task_id=body.task_id,
        goal=body.goal,
        observations=body.observations,
    )
    saved = await _repo.save_skill_proposal(
        db, owner_id=current_user.id, proposal=proposal
    )
    await db.commit()
    return saved.to_dict()


@router.get("/skill-proposals")
async def list_skill_proposals(
    current_user: CurrentUser,
    state: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    items = await _repo.list_skill_proposals(
        db, owner_id=current_user.id, state=state
    )
    return [item.to_dict() for item in items]


@router.post("/skill-proposals/{proposal_id}/decide")
async def decide_skill_proposal(
    proposal_id: str,
    body: SkillDecideBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        decided = await _repo.decide_skill_proposal(
            db,
            owner_id=current_user.id,
            proposal_id=proposal_id,
            approve=body.approve,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    result: Dict[str, Any] = {"proposal": decided.to_dict(), "skill": None}
    if body.approve and body.promote:
        skill = await agent_tasks_service.learning.upsert_skill(
            db,
            owner_id=current_user.id,
            name=decided.name,
            description=decided.description,
            instructions=decided.instructions,
            provenance=f"proposal:{decided.proposal_id}:{decided.source_task_id}",
        )
        result["skill"] = skill.to_dict()

    await db.commit()
    return result
