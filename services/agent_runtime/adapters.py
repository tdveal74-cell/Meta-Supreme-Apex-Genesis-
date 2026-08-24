"""Capability adapter contract for DEVON Agent Runtime."""

from __future__ import annotations

from typing import Protocol

from services.agent_runtime.tools import ToolRegistry


class CapabilityAdapter(Protocol):
    """A named capability package that registers governed runtime tools."""

    name: str

    def register(self, registry: ToolRegistry) -> None: ...


def register_adapters(registry: ToolRegistry, *adapters: CapabilityAdapter) -> ToolRegistry:
    seen: set[str] = set()
    for adapter in adapters:
        name = (adapter.name or "").strip()
        if not name:
            raise ValueError("capability adapter name is empty")
        if name in seen:
            raise ValueError(f"capability adapter already registered: {name}")
        adapter.register(registry)
        seen.add(name)
    return registry
