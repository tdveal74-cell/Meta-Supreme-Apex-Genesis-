"""
Standalone API for the flattened GitHub snapshot.

Runs without Postgres and without monorepo package paths. Full Intelligence OS
still requires `app.*` / `services.*` restore — see HOW_TO_TEST.md.

  GET  /                       identity + non-negotiables
  GET  /health                 liveness
  GET  /billing/plans          Phase 6 plan catalog
  GET  /billing/plans/{id}     single plan
  POST /billing/check          limit evaluation
  POST /workflows/validate     pure workflow definition validation
  GET  /system/charter         platform non-negotiables

Run:
  pip install fastapi uvicorn pydantic
  uvicorn standalone_api:app --reload --port 8000
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from billing import (
    UsageSnapshot,
    all_plans,
    check_council_run,
    check_knowledge_item,
    check_token_budget,
    check_workflow_run,
    get_plan,
    plan_summary,
)
from definition import (
    EFFECT_STEP_TYPES,
    WorkflowDefinition,
    WorkflowDefinitionError,
)

NON_NEGOTIABLES = [
    "Not a chatbot — multi-agent Council + synthesis only",
    "Humans decide; agents recommend",
    "Automation never commits effects unattended",
    "Memory is transparent, editable, deletable",
    "Simulated output is always labeled simulated",
]

app = FastAPI(
    title="Meta Supreme Apex Genesis (standalone)",
    description=(
        "Offline-capable surface for the flattened repo mirror. "
        "Full Intelligence OS requires monorepo restore — see HOW_TO_TEST.md."
    ),
    version="0.6.1-standalone",
)


@app.get("/")
async def root():
    return {
        "name": "Meta Supreme Apex Genesis",
        "mode": "standalone",
        "version": "0.6.1-standalone",
        "status": "operational",
        "phase": "6-billing-scaffold",
        "docs": "/docs",
        "non_negotiables": NON_NEGOTIABLES,
        "endpoints": [
            "/health",
            "/billing/plans",
            "/billing/check",
            "/workflows/validate",
            "/system/charter",
        ],
        "note": "Full API (Council, Memory, Knowledge) needs monorepo package paths.",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "meta-supreme-apex-genesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.6.1-standalone",
        "mode": "standalone",
        "database": "not_required",
        "ai_provider": "not_wired_in_standalone",
    }


@app.get("/system/charter")
async def charter():
    return {
        "non_negotiables": NON_NEGOTIABLES,
        "effect_step_types": sorted(t.value for t in EFFECT_STEP_TYPES),
        "rule": "Reads flow; effects pause for human approval.",
    }


@app.get("/billing/plans")
async def billing_plans():
    return {"plans": all_plans()}


@app.get("/billing/plans/{plan_id}")
async def billing_plan(plan_id: str):
    return plan_summary(plan_id)


class UsageBody(BaseModel):
    council_runs: int = 0
    workflow_runs: int = 0
    knowledge_items: int = 0
    memory_items: int = 0
    tokens: int = 0


class CheckBody(BaseModel):
    plan_id: str = Field(default="free")
    action: str = Field(description="council_run | workflow_run | knowledge_item | tokens")
    usage: UsageBody = Field(default_factory=UsageBody)
    additional_tokens: int = 0


@app.post("/billing/check")
async def billing_check(body: CheckBody):
    plan = get_plan(body.plan_id)
    usage = UsageSnapshot(
        council_runs=body.usage.council_runs,
        workflow_runs=body.usage.workflow_runs,
        knowledge_items=body.usage.knowledge_items,
        memory_items=body.usage.memory_items,
        tokens=body.usage.tokens,
    )
    action = body.action.strip().lower()
    if action == "council_run":
        result = check_council_run(plan, usage)
    elif action == "workflow_run":
        result = check_workflow_run(plan, usage)
    elif action == "knowledge_item":
        result = check_knowledge_item(plan, usage)
    elif action == "tokens":
        result = check_token_budget(plan, usage, body.additional_tokens)
    else:
        return {
            "error": "unknown action",
            "valid": ["council_run", "workflow_run", "knowledge_item", "tokens"],
        }
    return {
        "plan": plan.id.value,
        "action": action,
        "allowed": result.allowed,
        "reason": result.reason,
        "limit": result.limit,
        "current": result.current,
    }


class ValidateBody(BaseModel):
    definition: Dict[str, Any]


@app.post("/workflows/validate")
async def validate_workflow(body: ValidateBody):
    """Pure definition validation — no DB, no execution."""
    try:
        parsed = WorkflowDefinition.from_dict(body.definition)
    except WorkflowDefinitionError as exc:
        return {"valid": False, "error": str(exc)}
    return {
        "valid": True,
        "version": parsed.version,
        "trigger": parsed.trigger.to_dict(),
        "steps": [s.to_dict() for s in parsed.steps],
        "effect_steps": [s.id for s in parsed.effect_steps],
        "awaits_dispatcher": parsed.trigger.awaiting_dispatcher,
    }
