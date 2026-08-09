"""
AI Council agents package.

Import agent definitions from registry.
"""

from .registry import (
    AGENT_REGISTRY,
    ANALYST,
    ARCHITECT,
    CREATOR,
    ENGINEER,
    GUARDIAN,
    LIBRARIAN,
    ORACLE,
    SKEPTIC,
    STRATEGIST,
    get_agent,
    list_active_agents,
    list_agent_slugs,
)

__all__ = [
    "AGENT_REGISTRY",
    "get_agent",
    "list_active_agents",
    "list_agent_slugs",
    "ORACLE",
    "ANALYST",
    "STRATEGIST",
    "ARCHITECT",
    "ENGINEER",
    "GUARDIAN",
    "CREATOR",
    "LIBRARIAN",
    "SKEPTIC",
]
