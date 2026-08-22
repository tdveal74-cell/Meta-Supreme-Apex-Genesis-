"""
Application-layer workflow service.

Binds the framework-free engine (`services.workflows`) to real persistence:

- **Handlers** turn each step type into a real operation — a Council run, a
  pgvector search, a memory row, a decision record, a rendered export.
- **Runs** are persisted after every advance, so a run paused for approval
  survives restarts and shows exactly how far it got.
- **Approval is the product's spine.** Read steps (`council`,
  `knowledge_search`) run unattended. Effect steps (`memory_write`,
  `decision_draft`, `export`) pause every single run until the owner approves
  them — the engine never grants itself permission, and the API exposes no way
  to disable the gate.

Token usage is accumulated per run (`workflow_runs.token_usage`), joining
`agent_runs.token_usage` as the metering foundation for Phase 6.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.decision import Decision
from app.models.memory import Memory
from app.models.workflow import Workflow, WorkflowRun
from app.services.intelligence import build_controller
from app.services.knowledge import retrieve_for_context, search_knowledge
from app.services.memory import recall_memories
from services.intelligence import ContextPacket
from services.workflows import (
    RunStatus,
    StepContext,
    StepOutput,
    StepType,
    WorkflowDefinition,
    WorkflowEngine,
)

logger = logging.getLogger(__name__)

#: How much retrieved knowledge is folded into a step summary. Summaries are
#: interpolated into later prompts, so they are bounded deliberately.
_SUMMARY_CHAR_BUDGET = 4000
_CHUNK_CHAR_BUDGET = 600

#: Manual runs are allowed for draft/active/paused workflows — a human is
#: explicitly asking. Archived workflows refuse.
_RUNNABLE_STATUSES = frozenset({"draft", "active", "paused"})

APPROVAL_DECISIONS = frozenset({"approved", "rejected"})


class WorkflowStateError(RuntimeError):
    """The requested transition does not apply to this run's current state."""


# ---------------------------------------------------------------------------
# Step handlers
# ---------------------------------------------------------------------------

def _build_handlers(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: Optional[str],
    workflow_id: str,
    run_id: str,
) -> Dict[StepType, Any]:
    provenance = {
        "origin": "workflow",
        "workflow_id": workflow_id,
        "workflow_run_id": run_id,
    }

    async def knowledge_search(ctx: StepContext) -> StepOutput:
        query = str(ctx.config.get("query", "")).strip()
        limit = int(ctx.config.get("limit", settings.RETRIEVAL_TOP_K))
        hits = await search_knowledge(
            db, owner_id=user_id, query=query, limit=limit, project_id=project_id
        )
        if not hits:
            return StepOutput(
                summary="No stored knowledge matched this query.",
                data={"hits": [], "count": 0, "query": query},
            )

        lines: List[str] = []
        budget = _SUMMARY_CHAR_BUDGET
        for hit in hits:
            excerpt = hit["content"][:_CHUNK_CHAR_BUDGET].strip()
            line = f"{hit['title']} (chunk {hit['chunk_index']}): {excerpt}"
            if len(line) > budget:
                break
            lines.append(line)
            budget -= len(line)

        return StepOutput(
            summary="\n\n".join(lines),
            data={"hits": hits, "count": len(hits), "query": query},
        )

    async def council(ctx: StepContext) -> StepOutput:
        prompt = str(ctx.config.get("prompt", "")).strip()
        knowledge = await retrieve_for_context(
            db, owner_id=user_id, message=prompt, project_id=project_id
        )
        memories = await recall_memories(
            db, user_id=user_id, message=prompt, project_id=project_id
        )
        controller = build_controller()
        result = await controller.run(
            ContextPacket(
                user_id=user_id,
                project_id=project_id,
                message=prompt,
                retrieved_knowledge=knowledge,
                retrieved_memories=memories,
                requested_agents=list(ctx.config.get("agents") or []),
                full_council=bool(ctx.config.get("full_council", False)),
                deliberate=bool(ctx.config.get("deliberate", False)),
                metadata={"source": "workflow", **provenance},
            )
        )
        return StepOutput(
            summary=result.final_response,
            text=result.final_response,
            data={
                "request_id": result.request_id,
                "intent": result.intent.value,
                "intent_source": result.intent_source,
                "agents_consulted": result.agents_consulted,
                "recommended_actions": result.recommended_actions,
                "points_of_agreement": result.points_of_agreement,
                "points_of_tension": result.points_of_tension,
                "confidence": result.confidence,
                "synthesis_mode": result.synthesis_mode,
                "deliberation_rounds": result.deliberation_rounds,
                "provider": result.provider,
                "model": result.model,
                "knowledge_sources": [
                    {
                        "knowledge_item_id": hit["knowledge_item_id"],
                        "title": hit["source"],
                        "chunk_index": hit["chunk_index"],
                        "distance": hit["distance"],
                    }
                    for hit in knowledge
                ],
                "memories_recalled": len(memories),
            },
            input_tokens=result.total_input_tokens,
            output_tokens=result.total_output_tokens,
        )

    async def memory_write(ctx: StepContext) -> StepOutput:
        content = str(ctx.config.get("content", "")).strip()
        if not content:
            raise ValueError("Nothing to remember — the memory content rendered empty")
        memory = Memory(
            user_id=user_id,
            project_id=project_id,
            memory_type=str(ctx.config.get("memory_type", "context")),
            content=content,
            importance=int(ctx.config.get("importance", 5)),
            is_active=True,
            meta={**provenance, "step_id": ctx.step.id, "approved_by_user": True},
        )
        db.add(memory)
        await db.flush()
        return StepOutput(
            summary=f"Written to memory: {content[:200]}",
            text=content,
            data={
                "memory_id": memory.id,
                "memory_type": memory.memory_type,
                "importance": memory.importance,
            },
        )

    async def decision_draft(ctx: StepContext) -> StepOutput:
        question = str(ctx.config.get("question", "")).strip()
        options = [
            str(o).strip() for o in (ctx.config.get("options") or []) if str(o).strip()
        ][:20]
        recommendation = str(ctx.config.get("recommendation", "")).strip() or None
        decision = Decision(
            user_id=user_id,
            project_id=project_id,
            question=question[:2000],
            options=options,
            recommendation=recommendation,
            status="open",  # the human records the call — always
            meta={**provenance, "step_id": ctx.step.id},
        )
        db.add(decision)
        await db.flush()
        return StepOutput(
            summary=f"Decision drafted and left open: {question[:200]}",
            text=recommendation or "",
            data={
                "decision_id": decision.id,
                "options": options,
                "status": decision.status,
            },
        )

    async def export(ctx: StepContext) -> StepOutput:
        title = str(ctx.config.get("title", "")).strip()
        body = str(ctx.config.get("body", "")).strip()
        # No outbound channel is wired yet: the export is rendered into the run
        # record where the owner can read and copy it. Delivery (email, webhook)
        # lands with the outbound-integration work — claiming otherwise would
        # be dishonest.
        return StepOutput(
            summary=f"Export prepared: {title}",
            text=body,
            data={
                "title": title,
                "body": body,
                "delivered": False,
                "delivery_note": (
                    "Rendered into the run record. Outbound delivery "
                    "(email/webhook) is not implemented yet."
                ),
            },
        )

    return {
        StepType.KNOWLEDGE_SEARCH: knowledge_search,
        StepType.COUNCIL: council,
        StepType.MEMORY_WRITE: memory_write,
        StepType.DECISION_DRAFT: decision_draft,
        StepType.EXPORT: export,
    }


def build_engine(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: Optional[str],
    workflow_id: str,
    run_id: str,
) -> WorkflowEngine:
    """An engine whose handlers are bound to this session, owner, and run."""
    return WorkflowEngine(
        _build_handlers(
            db,
            user_id=user_id,
            project_id=project_id,
            workflow_id=workflow_id,
            run_id=run_id,
        ),
        require_approval_for_effects=settings.WORKFLOW_APPROVAL_REQUIRED,
    )


# ---------------------------------------------------------------------------
# Definition helpers
# ---------------------------------------------------------------------------

def parse_definition(raw: Any) -> WorkflowDefinition:
    """Validate a definition (raises WorkflowDefinitionError on any defect)."""
    return WorkflowDefinition.from_dict(
        raw or {}, max_steps=settings.WORKFLOW_MAX_STEPS
    )


def describe_definition(raw: Any) -> Dict[str, Any]:
    """
    A summary of a stored definition for list views — including whether its
    trigger can actually fire on its own today.
    """
    try:
        definition = parse_definition(raw)
    except Exception as exc:
        return {
            "valid": False,
            "error": str(exc),
            "step_count": 0,
            "approval_steps": [],
            "trigger_type": None,
            "awaiting_dispatcher": False,
        }
    return {
        "valid": True,
        "error": None,
        "step_count": len(definition.steps),
        "approval_steps": [s.id for s in definition.effect_steps],
        "trigger_type": definition.trigger.type.value,
        "awaiting_dispatcher": definition.trigger.awaiting_dispatcher,
    }


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

async def start_run(
    db: AsyncSession,
    *,
    workflow: Workflow,
    user_id: str,
    trigger_input: str = "",
) -> WorkflowRun:
    """
    Start a run and advance it as far as it can go without a human.

    Returns the persisted run — `awaiting_approval` if it reached an effect
    step, otherwise `completed`, `halted`, or `failed`.
    """
    if workflow.status not in _RUNNABLE_STATUSES:
        raise WorkflowStateError(
            f"A workflow with status {workflow.status!r} cannot be run"
        )

    # Callers hand us whatever their layer uses for ids (the dispatcher passes
    # the raw asyncpg uuid.UUID). Normalize once — meta is JSONB and json.dumps
    # refuses UUID objects.
    user_id = str(user_id)

    definition = parse_definition(workflow.definition)
    run = WorkflowRun(
        workflow_id=workflow.id,
        user_id=user_id,
        status="running",
        trigger=definition.trigger.type.value,
        trigger_input=trigger_input.strip() or None,
        step_results=[],
        approvals={},
        meta={
            "definition_version": definition.version,
            "steps_planned": [s.id for s in definition.steps],
            "started_by": user_id,
        },
    )
    db.add(run)
    await db.flush()
    return await _advance(db, workflow=workflow, run=run, definition=definition)


async def resume_run(
    db: AsyncSession,
    *,
    workflow: Workflow,
    run: WorkflowRun,
    decisions: Mapping[str, str],
    actor_id: str,
) -> WorkflowRun:
    """
    Record approval decisions and continue the run.

    The pending step must be among the decisions — you cannot skip past the
    gate the run is actually sitting in front of.
    """
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise WorkflowStateError(
            f"Run is {run.status!r}, not awaiting approval — nothing to approve"
        )

    definition = parse_definition(workflow.definition)
    effect_ids = {s.id for s in definition.effect_steps}

    if not decisions:
        raise WorkflowStateError("No approval decisions were supplied")
    for step_id, decision in decisions.items():
        if step_id not in effect_ids:
            raise WorkflowStateError(
                f"Step {step_id!r} is not an approval step in this workflow"
            )
        if decision not in APPROVAL_DECISIONS:
            raise WorkflowStateError(
                f"Decision for {step_id!r} must be 'approved' or 'rejected'"
            )
    if run.pending_step_id and run.pending_step_id not in decisions:
        raise WorkflowStateError(
            f"This run is waiting on step {run.pending_step_id!r} — decide that one"
        )

    recorded = dict(run.approvals or {})
    now = datetime.now(timezone.utc).isoformat()
    for step_id, decision in decisions.items():
        recorded[step_id] = {"decision": decision, "actor_id": actor_id, "at": now}

    run.approvals = recorded
    run.status = "running"
    run.pending_step_id = None
    await db.flush()
    return await _advance(db, workflow=workflow, run=run, definition=definition)


async def _advance(
    db: AsyncSession,
    *,
    workflow: Workflow,
    run: WorkflowRun,
    definition: WorkflowDefinition,
) -> WorkflowRun:
    engine = build_engine(
        db,
        user_id=run.user_id,
        project_id=workflow.project_id,
        workflow_id=workflow.id,
        run_id=run.id,
    )
    events: List[Dict[str, Any]] = []
    outcome = await engine.run(
        definition,
        trigger_input=run.trigger_input or "",
        prior_results=run.step_results or [],
        approvals=granted_approvals(run.approvals),
        on_event=events.append,
    )

    run.step_results = outcome.results_as_dicts()
    run.status = outcome.status
    run.pending_step_id = outcome.pending_step_id
    run.error_message = outcome.error
    run.token_usage = outcome.token_usage()
    previous_meta = dict(run.meta or {})
    previous_events = previous_meta.get("events")
    history = list(previous_events) if isinstance(previous_events, list) else []
    run.meta = {
        **previous_meta,
        "events": (history + events)[-60:],
        "latency_ms": outcome.latency_ms,
    }
    run.completed_at = (
        datetime.now(timezone.utc) if outcome.is_terminal else None
    )

    if outcome.status == RunStatus.FAILED:
        logger.warning(
            "workflow run failed workflow=%s run=%s error=%s",
            workflow.id,
            run.id,
            outcome.error,
        )

    await db.flush()
    await db.refresh(run)
    return run


def granted_approvals(recorded: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Stored approval records → the flat `{step_id: decision}` the engine wants."""
    approvals: Dict[str, str] = {}
    for step_id, entry in (recorded or {}).items():
        if isinstance(entry, Mapping):
            decision = entry.get("decision")
        else:
            decision = entry
        if decision in APPROVAL_DECISIONS:
            approvals[step_id] = str(decision)
    return approvals
