"""The six business functions, and what is actually built for each.

Source: Table I of the "Anthropic Engineering Note #04" screenshot Tee supplied
on 2026-10-12, which Tee confirmed as an Anthropic publication. Claude has not
opened the original; the structure is taken from the screenshot only.

Status is a measurement, not an aspiration. "built" means code and a test exist
in this repository. "planned" means neither does. Tee ruled the build order on
2026-10-12: Operations and Finance first, then Marketing, Sales, Support.

Data only. Nothing here opens a socket or writes anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# Tee's stated revenue target for the whole ecosystem. A target, not a measurement.
TARGET_MONTHLY_USD = 10_000


class Impact(str, Enum):
    """Mirrors the platform tiers. WRITE and HIGH_IMPACT stay human gated."""

    READ = "READ"
    WRITE = "WRITE"
    HIGH_IMPACT = "HIGH_IMPACT"


class Status(str, Enum):
    BUILT = "built"
    PARTIAL = "partial"
    PLANNED = "planned"


@dataclass(frozen=True)
class FunctionAgent:
    slug: str
    function: str
    mission: str
    key_tools: List[str]
    outcome: str
    max_impact: Impact
    status: Status
    built_in: Optional[str] = None
    build_order: int = 0
    notes: List[str] = field(default_factory=list)


COMPANY_FUNCTIONS: Dict[str, FunctionAgent] = {
    f.slug: f
    for f in (
        FunctionAgent(
            slug="ops_finance",
            function="Operations and Finance",
            mission="Report spend, output and revenue against the monthly target.",
            key_tools=["provider usage ledger", "internal reports"],
            outcome="Efficient operations, lower costs, a measured baseline",
            max_impact=Impact.READ,
            status=Status.BUILT,
            built_in="services/company/scoreboard.py",
            build_order=1,
            notes=["Revenue is not connected yet, so it reports as not measured.", "Ruled 2026-10-12: Stripe is the revenue source. It needs Tee to authorize it in connector settings first."],
        ),
        FunctionAgent(
            slug="marketing",
            function="Marketing and Content",
            mission="Prepare distribution of finished episodes for human approval.",
            key_tools=["content lanes", "social scheduler"],
            outcome="Grow brand and audience",
            max_impact=Impact.HIGH_IMPACT,
            status=Status.PARTIAL,
            built_in="services/company/marketing.py",
            build_order=2,
            notes=[
                "Ruled 2026-10-12: draft and queue only. Nothing is scheduled or published by the agent.",
                "Built: the approval queue rules, storage (migration 022) and routes. Not built: a Blotato read and an episode feed.",
                "Every post stays human approved and carries AI disclosure.",
            ],
        ),
        FunctionAgent(
            slug="sales",
            function="Sales and Acquisition",
            mission="Qualify leads and draft follow-ups for the career-strategy audience.",
            key_tools=["lead source", "email drafts"],
            outcome="Increase qualified leads and revenue",
            max_impact=Impact.HIGH_IMPACT,
            status=Status.PARTIAL,
            built_in="services/company/sales.py",
            build_order=3,
            notes=[
                "Ruled 2026-10-12: leads arrive as email or form replies. Outreach stays gated, Tee approves every send.",
                "Built: the qualify-and-draft approval queue rules, storage (migration 023) and routes. Not built: reading the inbox or the form, and sending.",
            ],
        ),
        FunctionAgent(
            slug="support",
            function="Customer Support",
            mission="Answer audience questions from a knowledge base built from episodes.",
            key_tools=["knowledge base", "ticketing"],
            outcome="High quality support, 24/7",
            max_impact=Impact.WRITE,
            status=Status.PARTIAL,
            built_in="services/company/support.py",
            build_order=4,
            notes=[
                "Ruled 2026-10-12: audience questions arrive as YouTube comments. Every reply is human approved.",
                "Built: the draft-reply approval queue rules, storage (migration 024) and routes. Not built: reading comments (the vidIQ reader needs credits), the episode knowledge base, and posting.",
            ],
        ),
        FunctionAgent(
            slug="research",
            function="Research and Strategy",
            mission="Market research and opportunity discovery.",
            key_tools=["web search", "data analysis"],
            outcome="Identify new markets, strategic insights",
            max_impact=Impact.READ,
            status=Status.PARTIAL,
            built_in="services/company/research.py",
            build_order=5,
            notes=[
                "The Council's Analyst and Oracle seats already cover part of this.",
                "Built: the findings log rules (every finding declares source, measured or unverified), storage (migration 025) and routes. Not built: the search itself.",
            ],
        ),
        FunctionAgent(
            slug="product",
            function="Product Development",
            mission="Ideation, coding, testing and documentation.",
            key_tools=["code tools"],
            outcome="Build and ship products faster",
            max_impact=Impact.WRITE,
            status=Status.PARTIAL,
            built_in="services/company/product.py",
            build_order=6,
            notes=[
                "The Council's Engineer seat and the EditForge lane already cover part of this.",
                "Built: the change-proposal rules (each carries an acceptance check and a reference artifact), storage (migration 026) and routes. Not built: anything that writes code or opens a pull request.",
            ],
        ),
    )
}


def list_functions() -> List[FunctionAgent]:
    return sorted(COMPANY_FUNCTIONS.values(), key=lambda f: f.build_order)
