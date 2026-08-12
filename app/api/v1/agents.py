"""
Agents endpoints — expose the AI Council registry.

Phase 2: imports the canonical AgentDefinition objects directly from
`services/agents/registry.py` (the Phase 1 static mirror is gone). The
registry remains the single source of truth.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.agents.registry import AGENT_REGISTRY, list_active_agents

router = APIRouter(prefix="/agents", tags=["Agents"])


class AgentSummary(BaseModel):
    slug: str
    name: str
    purpose: str
    mission: str
    version: str
    is_active: bool


class AgentDetail(AgentSummary):
    capabilities: List[str]
    limitations: List[str]
    output_format: Dict[str, Any]
    evaluation_criteria: List[str]


@router.get("", response_model=List[AgentSummary])
async def list_agents():
    """List all active AI Council agents."""
    return [
        AgentSummary(
            slug=agent.slug,
            name=agent.name,
            purpose=agent.purpose,
            mission=agent.mission,
            version=agent.version,
            is_active=agent.is_active,
        )
        for agent in list_active_agents()
    ]


@router.get("/{slug}", response_model=AgentDetail)
async def get_agent(slug: str):
    """Get a single agent's full definition by slug."""
    agent = AGENT_REGISTRY.get(slug)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDetail(
        slug=agent.slug,
        name=agent.name,
        purpose=agent.purpose,
        mission=agent.mission,
        version=agent.version,
        is_active=agent.is_active,
        capabilities=agent.capabilities,
        limitations=agent.limitations,
        output_format=agent.output_format,
        evaluation_criteria=agent.evaluation_criteria,
    )
