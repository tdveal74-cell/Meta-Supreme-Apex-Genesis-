"""
Standalone smoke entry for the flattened GitHub snapshot.

The full product expects a monorepo (`app.*`, `services.*`). Until that layout
is restored, this module exposes a minimal FastAPI surface that exercises the
modules that already live at repo root and need no database:

  GET  /                  — identity
  GET  /health            — liveness
  GET  /billing/plans     — Phase 6 plan catalog
  POST /billing/check     — limit evaluation (pure, offline)

Run:
  pip install fastapi uvicorn
  uvicorn standalone_api:app --reload --port 8000

Then open http://localhost:8000/health and http://localhost:8000/billing/plans
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from billing import (
    PlanId,
    UsageSnapshot,
    all_plans,
    check_council_run,
    check_knowledge_item,
    check_token_budget,
    check_workflow_run,
    get_plan,
    plan_summary,
)

app = FastAPI(
    title="Meta Supreme Apex Genesis (standalone smoke)",
    description=(
        "Offline-capable surface for the flattened repo mirror. "
        "Full Intelligence OS requires monorepo restore — see HOW_TO_TEST.md."
    ),
    version="0.6.0-smoke",
)


@app.get("/")
async def root():
    return {
        "name": "Meta Supreme Apex Genesis",
        "mode": "standalone-smoke",
        "version": "0.6.0-smoke",
        "status": "operational",
        "phase": "6-billing-scaffold",
        "docs": "/docs",
        "note": "Full API lives behind monorepo package paths (app.*, services.*).",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "meta-supreme-apex-genesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.6.0-smoke",
        "mode": "standalone",
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
