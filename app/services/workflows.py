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

import hashlib
import json
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
    WorkflowDefinitionError,
    WorkflowEngine,
    render_template,
)
from services.workflows.engine import StepResult, StepStatus

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

PENDING_HASH_KEY = "pending_payload_sha256"


def render_pending(
    workflow: Workflow,
    run: WorkflowRun,
    definition: Optional[WorkflowDefinition] = None,
) -> Optional[Dict[str, Any]]:
    """The rendered config of the step a paused run is in front of.

    This is what the gate shows and what the approval binds to: the step id,
    its type and the rendered preview, from the live definition and the
    completed results, never the template that produced it.
    """
    if run.status != RunStatus.AWAITING_APPROVAL or not run.pending_step_id:
        return None
    try:
        definition = definition or parse_definition(workflow.definition)
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
    # The write target is part of what the approver agrees to: a memory is
    # filed under the workflow's project, so the project is in the seal.
    return {
        "step_id": step.id,
        "step_type": step.type.value,
        "preview": preview,
        "project_id": str(workflow.project_id) if workflow.project_id else None,
    }


def pending_payload_sha256(rendered: Mapping[str, Any]) -> str:
    """One hash over exactly what the gate showed."""
    canonical = json.dumps(rendered, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    expected_payload_sha256: Optional[str] = None,
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

    try:
        definition = parse_definition(workflow.definition)
    except WorkflowDefinitionError:
        # The definition changed behind the gate into one that does not hold.
        # Nothing can execute from it, and the run must not stay trapped:
        # the owner closes it by rejecting the pending step.
        if run.pending_step_id and dict(decisions) == {run.pending_step_id: "rejected"}:
            return await _halt_unparseable(db, workflow=workflow, run=run, actor_id=actor_id)
        raise
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
        if run.pending_step_id and step_id != run.pending_step_id:
            # A later gate renders its own preview when the run reaches it.
            # Deciding it now would execute a payload nobody has seen.
            raise WorkflowStateError(
                f"This run is waiting on step {run.pending_step_id!r}; step "
                f"{step_id!r} has not been previewed yet. Decide only the pending step."
            )
    if run.pending_step_id and run.pending_step_id not in decisions:
        raise WorkflowStateError(
            f"This run is waiting on step {run.pending_step_id!r} — decide that one"
        )
    if run.pending_step_id and decisions[run.pending_step_id] == "approved":
        # The seal binds the approval, not the rejection. A rejection closes
        # the run without executing anything, so the owner can always close a
        # run whose definition changed behind the gate; only an approval has
        # to render what was previewed.
        sealed = (run.meta or {}).get(PENDING_HASH_KEY)
        rendered = render_pending(workflow, run, definition)
        live = pending_payload_sha256(rendered) if rendered is not None else None
        if sealed and live != sealed:
            logger.warning(
                "workflow gate seal mismatch: workflow=%s run=%s step=%s sealed=%s live=%s",
                workflow.id,
                run.id,
                run.pending_step_id,
                sealed,
                live,
            )
            raise WorkflowStateError(
                "The pending step no longer renders what was previewed: the "
                "definition changed while this run waited at the gate. Nothing "
                "was written. Reject this run to close it, then start a new one "
                "to preview the current definition."
            )
        if expected_payload_sha256 and expected_payload_sha256 != (sealed or live):
            raise WorkflowStateError(
                "The approval names a pending payload hash that is not the one "
                "this run is waiting on."
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


async def _halt_unparseable(
    db: AsyncSession,
    *,
    workflow: Workflow,
    run: WorkflowRun,
    actor_id: str,
) -> WorkflowRun:
    """Close a run by rejection when its definition no longer parses.

    The engine cannot run the definition, so the halt is written directly in
    the shape the engine writes: the rejected step result, the recorded
    decision, the seal removed, the run halted.
    """
    step_id = run.pending_step_id or ""
    raw_steps = (workflow.definition or {}).get("steps") or []
    raw = next(
        (s for s in raw_steps if isinstance(s, dict) and s.get("id") == step_id), {}
    )
    now = datetime.now(timezone.utc)
    run.approvals = {
        **(run.approvals or {}),
        step_id: {"decision": "rejected", "actor_id": actor_id, "at": now.isoformat()},
    }
    run.step_results = [
        *(run.step_results or []),
        StepResult(
            step_id=step_id,
            step_type=str(raw.get("type") or "effect"),
            status=StepStatus.REJECTED,
            summary=(
                "Rejected by the workflow owner; the definition no longer holds, "
                "run halted before this step."
            ),
        ).to_dict(),
    ]
    run.status = RunStatus.HALTED
    run.pending_step_id = None
    run.meta = {k: v for k, v in (run.meta or {}).items() if k != PENDING_HASH_KEY}
    run.completed_at = now
    await db.flush()
    await db.refresh(run)
    return run


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
    # Seal what the gate shows. Approval later checks the live rendering
    # against this, so a definition edited while the run waited cannot
    # execute under the approval given to the previewed payload.
    rendered = render_pending(workflow, run, definition)
    if rendered is not None:
        run.meta = {**run.meta, PENDING_HASH_KEY: pending_payload_sha256(rendered)}
    else:
        run.meta = {k: v for k, v in run.meta.items() if k != PENDING_HASH_KEY}
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
