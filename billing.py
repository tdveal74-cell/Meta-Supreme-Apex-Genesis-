"""
Phase 6 — SaaS Layer foundation: plans, limits, and usage metering.

This module defines the plan catalog and pure helpers for usage checks.
It does not charge cards or talk to Stripe yet — that lands when a payment
provider is wired. What it does provide:

- Canonical plan definitions (Free / Professional / Enterprise)
- Per-plan limits for council runs, workflow runs, knowledge items, agents
- Helpers to evaluate whether an action is within plan limits given current usage

Token usage already accumulates on agent_runs and workflow_runs. This module
is the aggregation + enforcement surface those numbers feed into.

Design rules:
- Humans remain the decision makers; billing never auto-acts on effects.
- Limits are explicit and inspectable — never silent.
- Free tier is fully usable offline with the mock provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class PlanId(str, Enum):
    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class PlanLimits:
    """Hard ceilings for a billing period (default: calendar month)."""

    council_runs: int
    workflow_runs: int
    knowledge_items: int
    max_agents_per_run: int
    memory_items: int
    # None means unlimited within practical system bounds
    tokens_per_month: Optional[int] = None


@dataclass(frozen=True)
class Plan:
    id: PlanId
    name: str
    description: str
    price_usd_monthly: int  # 0 for free
    limits: PlanLimits
    features: tuple[str, ...] = field(default_factory=tuple)


PLAN_CATALOG: Dict[PlanId, Plan] = {
    PlanId.FREE: Plan(
        id=PlanId.FREE,
        name="Free",
        description="Full Intelligence OS for individuals. Mock provider works with zero keys.",
        price_usd_monthly=0,
        limits=PlanLimits(
            council_runs=50,
            workflow_runs=20,
            knowledge_items=25,
            max_agents_per_run=3,
            memory_items=100,
            tokens_per_month=100_000,
        ),
        features=(
            "Council (up to 3 agents per run)",
            "Knowledge vault",
            "Transparent memory",
            "Decision tracking",
            "Workflows with human approval gates",
        ),
    ),
    PlanId.PROFESSIONAL: Plan(
        id=PlanId.PROFESSIONAL,
        name="Professional",
        description="Power users and small teams who need full council and higher throughput.",
        price_usd_monthly=49,
        limits=PlanLimits(
            council_runs=500,
            workflow_runs=200,
            knowledge_items=500,
            max_agents_per_run=9,
            memory_items=2_000,
            tokens_per_month=2_000_000,
        ),
        features=(
            "Full 9-agent Council",
            "Higher run and knowledge limits",
            "Priority synthesis models",
            "Usage dashboard",
            "Everything in Free",
        ),
    ),
    PlanId.ENTERPRISE: Plan(
        id=PlanId.ENTERPRISE,
        name="Enterprise",
        description="Organizations that need teams, permissions, compliance, and custom limits.",
        price_usd_monthly=0,  # custom pricing
        limits=PlanLimits(
            council_runs=10_000,
            workflow_runs=5_000,
            knowledge_items=10_000,
            max_agents_per_run=9,
            memory_items=50_000,
            tokens_per_month=None,  # negotiated
        ),
        features=(
            "Teams and RBAC (Phase 7)",
            "Audit logs and compliance exports",
            "Custom limits and SSO",
            "Dedicated support",
            "Everything in Professional",
        ),
    ),
}


def get_plan(plan_id: str | PlanId) -> Plan:
    """Resolve a plan id to its definition. Defaults to Free on unknown."""
    try:
        key = PlanId(plan_id) if not isinstance(plan_id, PlanId) else plan_id
    except ValueError:
        key = PlanId.FREE
    return PLAN_CATALOG[key]


@dataclass(frozen=True)
class UsageSnapshot:
    """Current period usage for a user / org."""

    council_runs: int = 0
    workflow_runs: int = 0
    knowledge_items: int = 0
    memory_items: int = 0
    tokens: int = 0


@dataclass(frozen=True)
class LimitCheck:
    allowed: bool
    reason: Optional[str] = None
    limit: Optional[int] = None
    current: Optional[int] = None


def check_council_run(plan: Plan, usage: UsageSnapshot) -> LimitCheck:
    limit = plan.limits.council_runs
    if usage.council_runs >= limit:
        return LimitCheck(
            allowed=False,
            reason=f"Council run limit reached for the {plan.name} plan ({limit}/period).",
            limit=limit,
            current=usage.council_runs,
        )
    return LimitCheck(allowed=True, limit=limit, current=usage.council_runs)


def check_workflow_run(plan: Plan, usage: UsageSnapshot) -> LimitCheck:
    limit = plan.limits.workflow_runs
    if usage.workflow_runs >= limit:
        return LimitCheck(
            allowed=False,
            reason=f"Workflow run limit reached for the {plan.name} plan ({limit}/period).",
            limit=limit,
            current=usage.workflow_runs,
        )
    return LimitCheck(allowed=True, limit=limit, current=usage.workflow_runs)


def check_knowledge_item(plan: Plan, usage: UsageSnapshot) -> LimitCheck:
    limit = plan.limits.knowledge_items
    if usage.knowledge_items >= limit:
        return LimitCheck(
            allowed=False,
            reason=f"Knowledge item limit reached for the {plan.name} plan ({limit}).",
            limit=limit,
            current=usage.knowledge_items,
        )
    return LimitCheck(allowed=True, limit=limit, current=usage.knowledge_items)


def check_token_budget(plan: Plan, usage: UsageSnapshot, additional: int = 0) -> LimitCheck:
    limit = plan.limits.tokens_per_month
    if limit is None:
        return LimitCheck(allowed=True, limit=None, current=usage.tokens)
    projected = usage.tokens + max(0, additional)
    if projected > limit:
        return LimitCheck(
            allowed=False,
            reason=f"Token budget reached for the {plan.name} plan ({limit}/period).",
            limit=limit,
            current=usage.tokens,
        )
    return LimitCheck(allowed=True, limit=limit, current=usage.tokens)


def plan_summary(plan_id: str | PlanId = PlanId.FREE) -> Dict:
    """JSON-serializable plan card for the API / UI."""
    plan = get_plan(plan_id)
    return {
        "id": plan.id.value,
        "name": plan.name,
        "description": plan.description,
        "price_usd_monthly": plan.price_usd_monthly,
        "limits": {
            "council_runs": plan.limits.council_runs,
            "workflow_runs": plan.limits.workflow_runs,
            "knowledge_items": plan.limits.knowledge_items,
            "max_agents_per_run": plan.limits.max_agents_per_run,
            "memory_items": plan.limits.memory_items,
            "tokens_per_month": plan.limits.tokens_per_month,
        },
        "features": list(plan.features),
    }


def all_plans() -> list[Dict]:
    return [plan_summary(pid) for pid in PlanId]
