"""Regression coverage for DEVON's governed EditForge capability."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue
from services.editforge.agent_adapter import EditForgeCapabilityAdapter

HASH = "a" * 64


def intent(**overrides: Any) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "commandId": "cmd-20260829-001",
        "projectId": "project-tsws-001",
        "cutId": "cut-tsws-001",
        "property": "tsws",
        "deliverable": "micro-drama",
        "source": {
            "uri": "https://media.example/tsws-source.mp4",
            "sha256": HASH,
        },
        "identity": {
            "cloneId": "tee-identity-v1",
            "voiceId": "ypnKDQtIhp4N3yn4UnqO",
            "version": "tee-identity-v1",
            "consentRecorded": True,
        },
        "canon": {"version": "tsws-canon-v1", "locked": True},
        "operations": [
            {
                "id": "motion",
                "type": "generate-full-motion",
                "params": {"maxCredits": 10},
            },
            {"id": "preview", "type": "render-preview", "params": {}},
        ],
        "output": {
            "mode": "preview",
            "width": 1080,
            "height": 1920,
            "fps": 24,
            "container": "mp4",
        },
    }
    value.update(overrides)
    return value


def approved_arguments(
    approvals: ApprovalQueue,
    *,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    binding = approval_binding(
        task_id="TASK-EDITFORGE",
        step_id="STEP-01",
        tool_name=tool_name,
        arguments=arguments,
    )
    record, token = approvals.request(
        title=f"Approve {tool_name}",
        what_happens=f"Execute exact EditForge effect. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert approvals.decide(record.request_id, token, "approve").approved is True
    return {
        **arguments,
        APPROVAL_METADATA_KEY: {
            "request_id": record.request_id,
            "binding": binding,
            "task_id": "TASK-EDITFORGE",
            "step_id": "STEP-01",
            "tool_name": tool_name,
        },
    }


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


@pytest.mark.asyncio
async def test_validate_is_read_only_and_render_spends_exact_approval_once() -> None:
    submitted = []
    approvals = ApprovalQueue()

    async def read_status():
        return {"configured": True}

    async def write_command(command):
        submitted.append(command)
        return {"id": command["commandId"], "status": "queued"}

    registry = ToolRegistry()
    EditForgeCapabilityAdapter(
        read_status,
        command_writer=write_command,
        approvals=approvals,
    ).register(registry)

    validate_spec = registry.require("editforge.validate")
    render_spec = registry.require("editforge.render")
    assert validate_spec.risk is ToolRisk.READ
    assert render_spec.risk is ToolRisk.HIGH_IMPACT
    assert render_spec.approval_required is True
    assert validate_spec.parameters == ("intent",)
    assert render_spec.parameters == ("intent",)

    render_intent = intent()
    validated = await registry.execute("editforge.validate", {"intent": render_intent})
    assert validated.ok is True
    assert json.loads(validated.output) == {"issues": [], "valid": True}

    unapproved = await registry.execute(
        "editforge.render",
        {"intent": render_intent},
    )
    assert unapproved.ok is False
    assert "approval metadata is missing" in unapproved.error
    assert submitted == []

    arguments = approved_arguments(
        approvals,
        tool_name="editforge.render",
        arguments={"intent": render_intent},
    )
    rendered = await registry.execute("editforge.render", arguments)
    assert rendered.ok is True
    assert len(submitted) == 1
    command = submitted[0]
    assert command["issuedBy"] == "DEVON"
    assert command["identity"]["voiceId"] == "ypnKDQtIhp4N3yn4UnqO"
    assert command["authorization"]["approvalId"] == rendered.metadata["approval_request_id"]
    assert rendered.metadata["command_id"] == render_intent["commandId"]

    replayed = await registry.execute("editforge.render", arguments)
    assert replayed.ok is False
    assert len(submitted) == 1


@pytest.mark.asyncio
async def test_execution_read_redacts_transport_urls_and_verifies_receipt() -> None:
    async def read_status():
        return {"configured": True}

    async def read_execution(command_id: str, poll: bool):
        assert command_id == "cmd-20260829-001"
        assert poll is False
        return {
            "id": command_id,
            "status": "completed",
            "revisionId": "rev-001",
            "command": {
                **intent(),
                "output": {
                    **intent()["output"],
                    "uploadUrl": "https://signed.example/upload?secret=1",
                },
            },
            "receipt": {
                "schema": "editforge.edit-receipt.v1",
                "commandId": command_id,
                "revisionId": "rev-001",
                "status": "completed",
                "artifacts": [
                    {
                        "uri": "https://artifacts.example/render.mp4",
                        "sha256": HASH,
                    }
                ],
            },
        }

    registry = ToolRegistry()
    EditForgeCapabilityAdapter(
        read_status,
        execution_reader=read_execution,
    ).register(registry)

    spec = registry.require("editforge.execution")
    assert spec.risk is ToolRisk.READ
    assert spec.parameters == ("command_id", "poll")

    result = await registry.execute(
        "editforge.execution",
        {"command_id": "cmd-20260829-001", "poll": False},
    )
    assert result.ok is True
    payload = json.loads(result.output)
    assert payload["receipt_valid"] is True
    assert payload["receipt_issues"] == []
    assert "source" not in payload["command"]
    assert "uploadUrl" not in payload["command"]["output"]


@pytest.mark.asyncio
async def test_retry_and_cancel_are_exact_approval_bound() -> None:
    actions = []
    approvals = ApprovalQueue()

    async def read_status():
        return {"configured": True}

    async def write_action(command_id: str, action: str):
        actions.append((command_id, action))
        return {"id": command_id, "status": "cancelled"}

    registry = ToolRegistry()
    EditForgeCapabilityAdapter(
        read_status,
        action_writer=write_action,
        approvals=approvals,
    ).register(registry)

    spec = registry.require("editforge.control")
    assert spec.risk is ToolRisk.HIGH_IMPACT
    assert spec.approval_required is True
    assert spec.parameters == ("command_id", "action")

    invalid = await registry.execute(
        "editforge.control",
        {"command_id": "cmd-20260829-001", "action": "publish"},
    )
    assert invalid.ok is False
    assert "retry or cancel" in invalid.error
    assert actions == []

    arguments = approved_arguments(
        approvals,
        tool_name="editforge.control",
        arguments={"command_id": "cmd-20260829-001", "action": "cancel"},
    )
    result = await registry.execute("editforge.control", arguments)
    assert result.ok is True
    assert actions == [("cmd-20260829-001", "cancel")]
