"""Read-only EditForge capability for DEVON Agent Runtime.

The generic browser adapter intentionally carries no application credentials.
EditForge status therefore travels through this narrow adapter, which receives
an authenticated status reader from the application layer and never exposes
the underlying bearer token to the planner, observation, or receipt.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, Mapping

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec

StatusReader = Callable[[], Awaitable[Mapping[str, Any]]]


class EditForgeCapabilityAdapter:
    """Expose the authenticated EditForge status boundary as one READ tool."""

    name = "editforge"

    def __init__(self, status_reader: StatusReader) -> None:
        self._status_reader = status_reader

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="editforge.status",
                description=(
                    "Read DEVON's authenticated live EditForge execution status. "
                    "Use this tool for configured, live_verified, executionReady, "
                    "workerReachable, health, provider readiness, and private "
                    "reference readiness. It never starts a render."
                ),
                risk=ToolRisk.READ,
                handler=self._status,
                reversible=True,
                blast_radius="one authenticated read from the EditForge health boundary",
                parameters=("scope",),
            )
        )

    async def _status(self, arguments: Dict[str, Any]) -> ToolResult:
        scope = str(arguments.get("scope") or "execution").strip().lower()
        if scope != "execution":
            return ToolResult(False, error="scope must be execution")
        try:
            payload = dict(await self._status_reader())
        except Exception as exc:
            return ToolResult(False, error=f"EditForge status failed: {exc}")

        return ToolResult(
            True,
            output=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            metadata=payload,
        )
