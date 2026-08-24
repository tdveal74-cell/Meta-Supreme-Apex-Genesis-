"""Governed tool registry for DEVON Agent Runtime.

Tools are capability adapters. The runtime can inspect their declared risk before
calling them. Registering a handler here does not bypass approval policy.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Union

from services.agent_runtime.contracts import ToolRisk

ToolHandlerResult = Union["ToolResult", str, Mapping[str, Any], None]
ToolHandler = Callable[[Dict[str, Any]], Union[ToolHandlerResult, Awaitable[ToolHandlerResult]]]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    handler: ToolHandler
    reversible: bool = False
    blast_radius: str = "runtime adapter only"

    @property
    def approval_required(self) -> bool:
        return self.risk in {ToolRisk.WRITE, ToolRisk.HIGH_IMPACT}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk": self.risk.value,
            "approval_required": self.approval_required,
            "reversible": self.reversible,
            "blast_radius": self.blast_radius,
        }


class ToolRegistry:
    """Explicit registry. Unknown tool names fail closed."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        name = (spec.name or "").strip()
        if not name:
            raise ValueError("tool name is empty")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get((name or "").strip())

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"unknown tool: {name}")
        return spec

    def describe(self) -> List[Dict[str, Any]]:
        return [self._tools[name].to_dict() for name in sorted(self._tools)]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        spec = self.require(name)
        if spec.risk is ToolRisk.BLOCKED:
            return ToolResult(False, error=f"tool is blocked by policy: {spec.name}")

        try:
            raw = spec.handler(dict(arguments))
            if inspect.isawaitable(raw):
                raw = await raw
        except Exception as exc:  # adapters must surface failures as observations
            return ToolResult(False, error=f"{type(exc).__name__}: {exc}")

        if isinstance(raw, ToolResult):
            return raw
        if raw is None:
            return ToolResult(True)
        if isinstance(raw, str):
            return ToolResult(True, output=raw)
        if isinstance(raw, Mapping):
            return ToolResult(True, output=str(dict(raw)), metadata=dict(raw))
        return ToolResult(True, output=str(raw))
