"""Governed EditForge capability for DEVON Agent Runtime.

The generic browser adapter intentionally carries no application credentials.
EditForge traffic therefore travels through this narrow adapter, which receives
authenticated readers and writers from the application layer and never exposes
the underlying bearer token to the planner, observation, or receipt.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue
from services.devon.editforge_execution import (
    EditForgeExecutionError,
    build_command,
    validate_intent,
    validate_receipt,
)

StatusReader = Callable[[], Awaitable[Mapping[str, Any]]]
CommandWriter = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
ExecutionReader = Callable[[str, bool], Awaitable[Mapping[str, Any]]]
ActionWriter = Callable[[str, str], Awaitable[Mapping[str, Any]]]


class EditForgeCapabilityAdapter:
    """Expose EditForge reads and exact-approval-bound execution controls."""

    name = "editforge"

    def __init__(
        self,
        status_reader: StatusReader,
        *,
        command_writer: Optional[CommandWriter] = None,
        execution_reader: Optional[ExecutionReader] = None,
        action_writer: Optional[ActionWriter] = None,
        approvals: Optional[ApprovalQueue] = None,
    ) -> None:
        self._status_reader = status_reader
        self._command_writer = command_writer
        self._execution_reader = execution_reader
        self._action_writer = action_writer
        self._approvals = approvals

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="editforge.status",
                description=(
                    "Read DEVON's authenticated live EditForge execution status. "
                    "Use this for configured, live_verified, executionReady, "
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
        registry.register(
            ToolSpec(
                name="editforge.validate",
                description=(
                    "Validate one complete EditForge intent before requesting a render. "
                    "This is read-only and spends no provider credits."
                ),
                risk=ToolRisk.READ,
                handler=self._validate,
                reversible=True,
                blast_radius="local validation of one proposed EditForge intent",
                parameters=("intent",),
            )
        )
        registry.register(
            ToolSpec(
                name="editforge.render",
                description=(
                    "Submit one previously validated EditForge intent after Tee confirms "
                    "the exact command and spend ceilings. This may spend Runway or "
                    "ElevenLabs credits and never publishes or deletes media."
                ),
                risk=ToolRisk.HIGH_IMPACT,
                handler=self._render,
                reversible=False,
                blast_radius="one governed EditForge render command for one project cut",
                parameters=("intent",),
            )
        )
        registry.register(
            ToolSpec(
                name="editforge.execution",
                description=(
                    "Read one EditForge execution and verify any terminal receipt. "
                    "This never starts, retries, or cancels a render."
                ),
                risk=ToolRisk.READ,
                handler=self._execution,
                reversible=True,
                blast_radius="one authenticated EditForge execution read",
                parameters=("command_id", "poll"),
            )
        )
        registry.register(
            ToolSpec(
                name="editforge.control",
                description=(
                    "Retry or cancel one EditForge execution after Tee confirms the "
                    "exact command ID and action."
                ),
                risk=ToolRisk.HIGH_IMPACT,
                handler=self._control,
                reversible=False,
                blast_radius="one retry or cancellation for one EditForge command",
                parameters=("command_id", "action"),
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
        return self._result(payload)

    async def _validate(self, arguments: Dict[str, Any]) -> ToolResult:
        intent = arguments.get("intent")
        if not isinstance(intent, Mapping):
            return ToolResult(False, error="intent must be an object")
        issues = validate_intent(intent)
        payload = {"valid": not issues, "issues": issues}
        return ToolResult(
            not issues,
            output=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            error="; ".join(issues),
            metadata=payload,
        )

    async def _render(self, arguments: Dict[str, Any]) -> ToolResult:
        if self._command_writer is None or self._approvals is None:
            return self._not_configured("render")
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        intent = args.get("intent")
        if not isinstance(intent, Mapping):
            return ToolResult(False, error="intent must be an object")
        issues = validate_intent(intent)
        if issues:
            return ToolResult(False, error="; ".join(issues))
        try:
            request_id, binding = require_approved_runtime_binding(
                self._approvals,
                metadata,
                tool_name="editforge.render",
                arguments=args,
            )
            command = build_command(
                intent,
                approval_id=request_id,
                approved_by="Tee",
            )
            payload = dict(await self._command_writer(command))
        except (EditForgeExecutionError, RuntimeError, TypeError, ValueError) as exc:
            return ToolResult(False, error=str(exc))
        result = self._result(payload)
        result.metadata.update(
            {
                "approval_request_id": request_id,
                "approval_binding": binding,
                "command_id": str(
                    payload.get("id")
                    or payload.get("commandId")
                    or intent.get("commandId")
                ),
            }
        )
        return result

    async def _execution(self, arguments: Dict[str, Any]) -> ToolResult:
        if self._execution_reader is None:
            return self._not_configured("execution reads")
        command_id = str(arguments.get("command_id") or "").strip()
        if not command_id:
            return ToolResult(False, error="command_id is required")
        try:
            poll = self._bool_argument(arguments.get("poll"), default=True)
            execution = dict(await self._execution_reader(command_id, poll))
        except (EditForgeExecutionError, RuntimeError, TypeError, ValueError) as exc:
            return ToolResult(False, error=str(exc))

        payload = self._public_execution(execution)
        receipt = execution.get("receipt")
        if isinstance(receipt, Mapping):
            issues = validate_receipt(
                receipt,
                command_id=command_id,
                revision_id=(
                    str(execution.get("revisionId"))
                    if execution.get("revisionId")
                    else None
                ),
            )
            payload["receipt_valid"] = not issues
            payload["receipt_issues"] = issues
        return self._result(payload)

    async def _control(self, arguments: Dict[str, Any]) -> ToolResult:
        if self._action_writer is None or self._approvals is None:
            return self._not_configured("execution controls")
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        command_id = str(args.get("command_id") or "").strip()
        action = str(args.get("action") or "").strip().lower()
        if not command_id:
            return ToolResult(False, error="command_id is required")
        if action not in {"retry", "cancel"}:
            return ToolResult(False, error="action must be retry or cancel")
        args["command_id"] = command_id
        args["action"] = action
        try:
            request_id, binding = require_approved_runtime_binding(
                self._approvals,
                metadata,
                tool_name="editforge.control",
                arguments=args,
            )
            payload = dict(await self._action_writer(command_id, action))
        except (EditForgeExecutionError, RuntimeError, TypeError, ValueError) as exc:
            return ToolResult(False, error=str(exc))
        result = self._result(payload)
        result.metadata.update(
            {
                "approval_request_id": request_id,
                "approval_binding": binding,
                "command_id": command_id,
                "action": action,
            }
        )
        return result

    @staticmethod
    def _bool_argument(value: Any, *, default: bool) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError("poll must be true or false")

    @staticmethod
    def _public_execution(execution: Mapping[str, Any]) -> Dict[str, Any]:
        """Return operational state without signed source or upload URLs."""
        public = {key: value for key, value in execution.items() if key != "command"}
        command = execution.get("command")
        if isinstance(command, Mapping):
            operations = command.get("operations")
            public["command"] = {
                "commandId": command.get("commandId"),
                "projectId": command.get("projectId"),
                "cutId": command.get("cutId"),
                "property": command.get("property"),
                "deliverable": command.get("deliverable"),
                "operations": [
                    {"id": operation.get("id"), "type": operation.get("type")}
                    for operation in operations or []
                    if isinstance(operation, Mapping)
                ],
                "output": {
                    key: value
                    for key, value in dict(command.get("output") or {}).items()
                    if key != "uploadUrl"
                },
            }
        return public

    @staticmethod
    def _not_configured(capability: str) -> ToolResult:
        return ToolResult(
            False,
            error=f"EditForge {capability} are not configured for DEVON Agent Runtime",
        )

    @staticmethod
    def _result(payload: Mapping[str, Any]) -> ToolResult:
        data = dict(payload)
        return ToolResult(
            True,
            output=json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
            metadata=data,
        )
