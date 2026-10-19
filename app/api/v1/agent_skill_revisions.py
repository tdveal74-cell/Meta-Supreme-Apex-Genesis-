"""Owner-scoped skill history, explicit rollback and trusted evaluation."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services import skill_revisions as revisions

router = APIRouter(prefix="/agent-tasks/learning/skills", tags=["DEVON Agent Tasks"])


class RollbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)


class EvaluationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=20000)
    instructions: str = Field(min_length=1, max_length=100000)
    source_task_id: str = Field(min_length=1, max_length=64)
    suite_id: str = Field(min_length=1, max_length=200)
    suite_version: str = Field(min_length=1, max_length=120)


@router.get("/{name}/revisions")
async def history(name: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    return {"items": await revisions.history(db, owner_id=current_user.id, name=name)}


@router.post("/{name}/rollback")
async def rollback(name: str, body: RollbackBody, current_user: CurrentUser,
                   db: AsyncSession = Depends(get_db)) -> dict:
    try:
        result = await revisions.rollback(db, owner_id=current_user.id, name=name,
                                         **body.model_dump())
    except KeyError as exc:
        raise HTTPException(404, "Skill revision not found") from exc
    except revisions.RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return result


@router.post("/{name}/evaluations")
async def evaluate(name: str, body: EvaluationBody, current_user: CurrentUser,
                   db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    try:
        evaluation_id = await revisions.evaluate(db, owner_id=current_user.id, name=name,
                                                **body.model_dump())
    except KeyError as exc:
        raise HTTPException(404, "Source task not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result = await revisions.get_evaluation(db, owner_id=current_user.id, name=name,
                                            evaluation_id=evaluation_id)
    await db.commit()
    return {"evaluation_id": evaluation_id,
            "evaluation_status": result["evidence"]["evaluation_status"]}


@router.get("/{name}/evaluations/{evaluation_id}")
async def get_evaluation(name: str, evaluation_id: str, current_user: CurrentUser,
                         db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await revisions.get_evaluation(db, owner_id=current_user.id, name=name,
                                              evaluation_id=evaluation_id)
    except KeyError as exc:
        raise HTTPException(404, "Evaluation not found") from exc
