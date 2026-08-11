"""Re-export canonical agent registry from repo root."""
from registry import (  # noqa: F401
    AGENT_REGISTRY,
    AgentDefinition,
    get_agent,
    list_active_agents,
    list_agent_slugs,
)
