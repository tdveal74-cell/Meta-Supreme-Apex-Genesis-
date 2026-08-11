"""Agent package."""
from services.agents.registry import (  # noqa: F401
    AGENT_REGISTRY,
    get_agent,
    list_active_agents,
    list_agent_slugs,
)
