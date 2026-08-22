"""
Workflows endpoints — automation with the human in charge.

A workflow may read and reason on its own (knowledge search, Council runs),
and may not write memory, open a decision, or prepare an export without the
owner saying so. The approval gate lives in the engine; this router exposes
it honestly: a paused run shows exactly what it would write, the approval is
recorded as a signed act (who, and when), and there is no endpoint that
disables the gate.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.workflow import Workflow, WorkflowRun
from app.security.deps import CurrentUser
from app.services.dispatcher import compute_next_run_at
from app.services.workflows import (
    WorkflowStateError,
    describe_definition,
    parse_definition,
    resume_run,
    start_run,
)
from services.workflows import (
    StepType,
    TriggerType,
    WorkflowDefinitionError,
    render_template,
)
from services.workflows.definition import EFFECT_STEP_TYPES

router = APIRouter(prefix="/workflows", tags=["Workflows"])

_STEP_TYPE_DESCRIPTIONS = {
    StepType.KNOWLEDGE_SEARCH: "Semantic search over the owner's knowledge base.",
    StepType.COUNCIL: "A full Council run on a rendered prompt.",
    StepType.MEMORY_WRITE: "Write a memory the owner has read and approved.",
    StepType.DECISION_DRAFT: "Open a decision for the owner to record the call on.",
    StepType.EXPORT: "Render an export into the run record for the owner to use.",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    definition: Dict[str, Any]
    description: Optional[str] = Field(None, max_length=20_000)
    project_id: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=20_000)
    definition: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|paused|archived)$")


class RunStart(BaseModel):
    input: str = Field(default="", max_length=20_000)


class RunApprove(BaseModel):
    decisions: Dict[str, str] = Field(default_factory=dict)


class RunSummary(BaseModel):
    id: str
    status: str
    pending_step_id: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    project_id: Optional[str] = None
    summary: Dict[str, Any]
    run_count: int
    last_run: Optional[RunSummary] = None
    created_at: datetime
    updated_at: datetime


class PendingStep(BaseModel):
    step_id: str
    step_type: str
    preview: Dict[str, Any]


class RunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger: str
    trigger_input: Optional[str] = None
    steps: List[Dict[str, Any]]
    pending: Optional[PendingStep] = None
    approvals: Dict[str, Any]
    token_usage: Dict[str, int]
    latency_ms: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# View helpers
# ---------------------------------------------------------------------------


def _workflow_to_response(
    workflow: Workflow,
    *,
    run_count: int = 0,
    last_run: Optional[WorkflowRun] = None,
) -> WorkflowResponse:
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        project_id=workflow.project_id,
        summary=describe_definition(workflow.definition),
        run_count=run_count,
        last_run=RunSummary(
            id=last_run.id,
            status=last_run.status,
            pending_step_id=last_run.pending_step_id,
            started_at=last_run.started_at,
            completed_at=last_run.completed_at,
        )
        if last_run is not None
        else None,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def _pending_view(workflow: Workflow, run: WorkflowRun) -> Optional[PendingStep]:
    """
    The rendered config of the step the run is paused in front of — the gate
    shows exactly what would be written, not the template that produced it.
    """
    if run.status != "awaiting_approval" or not run.pending_step_id:
        return None
    try:
        definition = parse_definition(workflow.definition)
    except WorkflowDefinitionError:
        return None
    step = definition.step(run.pending_step_id)
    if step is None:
        return None
    results = {
        r["step_id"]: {
            "summary": r.get("summary", ""),
            "text": r.get("text") or r.get("summary", ""),
        }
        for r in (run.step_results or [])
        if r.get("status") == "completed"
    }
    preview = render_template(
        step.config, trigger_input=run.trigger_input or "", results=results
    )
    return PendingStep(step_id=step.id, step_type=step.type.value, preview=preview)


def _run_to_response(workflow: Workflow, run: WorkflowRun) -> RunResponse:
    usage = run.token_usage or {}
    return RunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        trigger=run.trigger,
        trigger_input=run.trigger_input,
        steps=list(run.step_results or []),
        pending=_pending_view(workflow, run),
        approvals=dict(run.approvals or {}),
        token_usage={
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        },
        latency_ms=int((run.meta or {}).get("latency_ms", 0)),
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


async def _get_owned_workflow(
    workflow_id: str, user_id: str, db: AsyncSession
) -> Workflow:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.owner_id == user_id
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return workflow


async def _get_owned_run(
    workflow: Workflow, run_id: str, db: AsyncSession
) -> WorkflowRun:
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.workflow_id == workflow.id
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    return run


# ---------------------------------------------------------------------------
# Catalog (declared before /{workflow_id} so the path does not shadow it)
# ---------------------------------------------------------------------------


@router.get("/step-types")
async def step_type_catalog(current_user: CurrentUser):
    """The step catalog — the single source of approval semantics."""
    return {
        "step_types": [
            {
                "type": step_type.value,
                "requires_approval": step_type in EFFECT_STEP_TYPES,
                "description": _STEP_TYPE_DESCRIPTIONS.get(step_type, ""),
            }
            for step_type in StepType
        ],
        "approval_required": True,
        # Schedule and event triggers are storable but nothing fires them yet.
        "dispatchable_triggers": [TriggerType.MANUAL.value],
    }


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's workflows, newest first, with their last run."""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.owner_id == current_user.id)
        .order_by(Workflow.created_at.desc(), Workflow.id)
        .limit(limit)
        .offset(offset)
    )
    workflows = result.scalars().all()
    if not workflows:
        return []

    ids = [w.id for w in workflows]
    counts_result = await db.execute(
        select(WorkflowRun.workflow_id, func.count(WorkflowRun.id))
        .where(WorkflowRun.workflow_id.in_(ids))
        .group_by(WorkflowRun.workflow_id)
    )
    counts = dict(counts_result.all())

    last_runs_result = await db.execute(
        select(WorkflowRun)
        .distinct(WorkflowRun.workflow_id)
        .where(WorkflowRun.workflow_id.in_(ids))
        .order_by(
            WorkflowRun.workflow_id,
            WorkflowRun.created_at.desc(),
            WorkflowRun.id,
        )
    )
    last_runs = {run.workflow_id: run for run in last_runs_result.scalars().all()}

    return [
        _workflow_to_response(
            w, run_count=counts.get(w.id, 0), last_run=last_runs.get(w.id)
        )
        for w in workflows
    ]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a workflow. Invalid definitions are refused at save time."""
    try:
        parse_definition(payload.definition)
    except WorkflowDefinitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    workflow = Workflow(
        owner_id=current_user.id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        description=payload.description,
        definition=payload.definition,
        status="draft",
        meta={"origin": "api"},
    )
    workflow.next_run_at = compute_next_run_at(
        workflow, now=datetime.now(timezone.utc)
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return _workflow_to_response(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get one workflow (owner only)."""
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)
    count_result = await db.execute(
        select(func.count(WorkflowRun.id)).where(
            WorkflowRun.workflow_id == workflow.id
        )
    )
    last_result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow.id)
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
        .limit(1)
    )
    return _workflow_to_response(
        workflow,
        run_count=count_result.scalar_one(),
        last_run=last_result.scalar_one_or_none(),
    )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a workflow — including activating it.

    Activation requires a definition that holds: valid, and with at least
    one step. A workflow with no steps has nothing to run.
    """
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)

    if payload.definition is not None:
        try:
            parse_definition(payload.definition)
        except WorkflowDefinitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        workflow.definition = payload.definition

    if payload.status == "active":
        try:
            definition = parse_definition(workflow.definition)
        except WorkflowDefinitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This workflow's definition does not hold: {exc}",
            ) from exc
        if not definition.steps:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This workflow has no steps yet and cannot be activated",
            )

    if payload.name is not None:
        workflow.name = payload.name.strip()
    if payload.description is not None:
        workflow.description = payload.description
    if payload.status is not None:
        workflow.status = payload.status
    if payload.definition is not None or payload.status is not None:
        workflow.next_run_at = compute_next_run_at(
            workflow, now=datetime.now(timezone.utc)
        )

    await db.flush()
    await db.refresh(workflow)
    return _workflow_to_response(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a workflow and its run history.

    Refused while a run sits at an approval gate — the owner decides the
    pending step first, so no gate is ever silently discarded.
    """
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)
    pending_result = await db.execute(
        select(func.count(WorkflowRun.id)).where(
            WorkflowRun.workflow_id == workflow.id,
            WorkflowRun.status == "awaiting_approval",
        )
    )
    if pending_result.scalar_one():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This workflow has a run awaiting approval — "
                "decide it before deleting"
            ),
        )
    await db.execute(delete(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id))
    await db.delete(workflow)
    await db.flush()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@router.post(
    "/{workflow_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow_run(
    workflow_id: str,
    payload: RunStart,
    current_user: CurrentUser,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a run and advance it as far as it can go without a human.

    With an `Idempotency-Key` header, a retried request returns the original
    run (200) rather than starting a duplicate. The key is scoped to the
    workflow, not global.
    """
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)

    if idempotency_key:
        existing_result = await db.execute(
            select(WorkflowRun).where(
                WorkflowRun.workflow_id == workflow.id,
                WorkflowRun.meta["idempotency_key"].astext == idempotency_key,
            )
        )
        existing = existing_result.scalars().first()
        if existing is not None:
            response.status_code = status.HTTP_200_OK  # a replay is not a creation
            return _run_to_response(workflow, existing)

    gate_result = await db.execute(
        select(func.count(WorkflowRun.id)).where(
            WorkflowRun.workflow_id == workflow.id,
            WorkflowRun.status == "awaiting_approval",
        )
    )
    if gate_result.scalar_one():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A run of this workflow is already awaiting approval. "
                "Decide that one first."
            ),
        )

    try:
        run = await start_run(
            db, workflow=workflow, user_id=current_user.id, trigger_input=payload.input
        )
    except WorkflowStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except WorkflowDefinitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if idempotency_key:
        run.meta = {**(run.meta or {}), "idempotency_key": idempotency_key}
        await db.flush()

    return _run_to_response(workflow, run)


@router.get("/{workflow_id}/runs", response_model=List[RunResponse])
async def list_workflow_runs(
    workflow_id: str,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Run history for a workflow, newest first."""
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow.id)
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
        .limit(limit)
        .offset(offset)
    )
    return [_run_to_response(workflow, run) for run in result.scalars().all()]


@router.get("/{workflow_id}/runs/{run_id}", response_model=RunResponse)
async def get_workflow_run(
    workflow_id: str,
    run_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """One run, with its step results and any pending gate."""
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)
    run = await _get_owned_run(workflow, run_id, db)
    return _run_to_response(workflow, run)


@router.post("/{workflow_id}/runs/{run_id}/approve", response_model=RunResponse)
async def approve_workflow_run(
    workflow_id: str,
    run_id: str,
    payload: RunApprove,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Record approval decisions on a paused run and continue it.

    The approval is a signed act — who decided, and when — recorded on the
    run before the engine advances past the gate.
    """
    workflow = await _get_owned_workflow(workflow_id, current_user.id, db)
    run = await _get_owned_run(workflow, run_id, db)
    try:
        run = await resume_run(
            db,
            workflow=workflow,
            run=run,
            decisions=payload.decisions,
            actor_id=current_user.id,
        )
    except WorkflowStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _run_to_response(workflow, run)
