"""Regression coverage for DEVON's private EditForge status capability."""

from __future__ import annotations

import json

import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry
from services.editforge.agent_adapter import EditForgeCapabilityAdapter


@pytest.mark.asyncio
async def test_editforge_status_is_read_only_and_returns_live_fields() -> None:
    async def read_status():
        return {
            "configured": True,
            "live_verified": True,
            "editforge": {
                "health": "healthy",
                "executionReady": True,
                "workerReachable": True,
            },
        }

    registry = ToolRegistry()
    EditForgeCapabilityAdapter(read_status).register(registry)

    spec = registry.require("editforge.status")
    assert spec.risk is ToolRisk.READ
    assert spec.approval_required is False
    assert spec.parameters == ("scope",)

    result = await registry.execute("editforge.status", {})
    assert result.ok is True
    payload = json.loads(result.output)
    assert payload["configured"] is True
    assert payload["live_verified"] is True
    assert payload["editforge"]["executionReady"] is True
    assert payload["editforge"]["workerReachable"] is True
    assert payload["editforge"]["health"] == "healthy"

    refused = await registry.execute("editforge.status", {"scope": "render"})
    assert refused.ok is False
    assert "scope must be execution" in refused.error


@pytest.mark.asyncio
async def test_editforge_status_failure_stays_inside_tool_result() -> None:
    async def fail_status():
        raise RuntimeError("boundary unavailable")

    registry = ToolRegistry()
    EditForgeCapabilityAdapter(fail_status).register(registry)

    result = await registry.execute("editforge.status", {})
    assert result.ok is False
    assert "boundary unavailable" in result.error
