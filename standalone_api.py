"""
Flagship standalone API — offline Intelligence OS surface.

No Postgres. No monorepo paths. Full Council roster + mock deliberation.

  GET  /                       identity + non-negotiables
  GET  /health                 liveness
  GET  /system/charter         platform rules
  GET  /agents                 9-agent Council registry
  GET  /agents/{slug}          single agent
  POST /council/deliberate     mock multi-agent deliberation (labeled simulated)
  GET  /billing/plans          plan catalog
  POST /billing/check          limit evaluation
  POST /workflows/validate     definition validation

Run:
  pip install fastapi uvicorn pydantic
  uvicorn standalone_api:app --reload --port 8000
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
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
from definition import EFFECT_STEP_TYPES, WorkflowDefinition, WorkflowDefinitionError
from registry import AGENT_REGISTRY, get_agent, list_active_agents

NON_NEGOTIABLES = [
    "Not a chatbot — multi-agent Council + synthesis only",
    "Humans decide; agents recommend",
    "Automation never commits effects unattended",
    "Memory is transparent, editable, deletable",
    "Simulated output is always labeled simulated",
]

app = FastAPI(
    title="Meta Supreme Apex Genesis",
    description="Flagship offline Intelligence OS. Council · Billing · Workflows.",
    version="1.0.0-flagship",
)


@app.get("/")
async def root():
    agents = list_active_agents()
    return {
        "name": "Meta Supreme Apex Genesis",
        "mode": "flagship-standalone",
        "version": "1.0.0-flagship",
        "status": "operational",
        "council_agents": len(agents),
        "non_negotiables": NON_NEGOTIABLES,
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/system/charter",
            "/agents",
            "/council/deliberate",
            "/billing/plans",
            "/billing/check",
            "/workflows/validate",
        ],
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "meta-supreme-apex-genesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0-flagship",
        "mode": "standalone",
        "database": "not_required",
        "ai_provider": "mock",
        "simulated": True,
        "council_agents": len(list_active_agents()),
    }


@app.get("/system/charter")
async def charter():
    return {
        "non_negotiables": NON_NEGOTIABLES,
        "effect_step_types": sorted(t.value for t in EFFECT_STEP_TYPES),
        "rule": "Reads flow; effects pause for human approval.",
        "council": {
            "agents": len(list_active_agents()),
            "slugs": [a.slug for a in list_active_agents()],
        },
    }


@app.get("/agents")
async def agents_list():
    return [
        {
            "slug": a.slug,
            "name": a.name,
            "purpose": a.purpose,
            "mission": a.mission,
            "version": a.version,
            "is_active": a.is_active,
            "capabilities": a.capabilities,
            "limitations": a.limitations,
        }
        for a in list_active_agents()
    ]


@app.get("/agents/{slug}")
async def agent_detail(slug: str):
    agent = get_agent(slug)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "slug": agent.slug,
        "name": agent.name,
        "purpose": agent.purpose,
        "mission": agent.mission,
        "version": agent.version,
        "is_active": agent.is_active,
        "capabilities": agent.capabilities,
        "limitations": agent.limitations,
        "output_format": agent.output_format,
        "evaluation_criteria": agent.evaluation_criteria,
        "system_instructions": agent.system_instructions,
    }


class CouncilRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    agents: Optional[List[str]] = Field(
        default=None,
        description="Agent slugs; default = full active Council",
    )
    full_council: bool = True


@app.post("/council/deliberate")
async def council_deliberate(body: CouncilRequest):
    """Offline mock deliberation — every seat labeled simulated."""
    active = list_active_agents()
    if body.agents:
        seats = []
        for slug in body.agents:
            a = get_agent(slug)
            if a is None or not a.is_active:
                raise HTTPException(status_code=400, detail=f"Unknown or inactive agent: {slug}")
            seats.append(a)
    else:
        seats = active if body.full_council else active[:3]

    topic = " ".join(body.prompt.split())[:120]
    contributions = []
    for agent in seats:
        contributions.append(
            {
                "agent": agent.slug,
                "name": agent.name,
                "purpose": agent.purpose,
                "simulated": True,
                "provider": "mock",
                "insight": (
                    f"[{agent.name}] Simulated perspective on: {topic}. "
                    f"Mission focus: {agent.mission} "
                    "Configure Anthropic/OpenAI for live intelligence."
                ),
                "confidence": 0.55,
            }
        )

    return {
        "simulated": True,
        "provider": "mock",
        "prompt": body.prompt,
        "agents_consulted": [c["agent"] for c in contributions],
        "contributions": contributions,
        "synthesis": {
            "simulated": True,
            "summary": (
                f"Simulated Council synthesis for: {topic}. "
                f"{len(contributions)} agents contributed. "
                "Humans decide; agents recommend."
            ),
            "recommendation": "Review contributions and decide — this run is offline/mock.",
            "dissent_preserved": True,
        },
        "non_negotiable": "Humans decide; agents recommend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
