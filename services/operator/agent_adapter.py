"""DEVON Agent Runtime adapter for the existing Operator Bridge."""

from __future__ import annotations

from typing import Any, Dict

from services.agent_runtime.governance import APPROVAL_METADATA_KEY
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue
from services.operator.bridge import OperatorBridge, OperatorError, Risk


class OperatorCapabilityAdapter:
    """Expose governed local-process tools without moving them into DEVON core."""

    name = "operator"

    def __init__(self, bridge: OperatorBridge, approvals: ApprovalQueue) -> None:
        self.bridge = bridge
        self.approvals = approvals

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="operator.read",
                description=(
                    "Run one command that the Operator Bridge classifies read-only. "
                    "No shell pipes, redirects, glob expansion, or shell built-ins."
                ),
                risk=self._read_risk(),
                handler=self._read,
                reversible=True,
                blast_radius="read-only process on the configured operator host",
            )
        )
        registry.register(
            ToolSpec(
                name="operator.command",
                description=(
                    "Run one mutating local command only after DEVON human approval. "
                    "Blocked host-destruction commands remain refused at the bridge."
                ),
                risk=self._command_risk(),
                handler=self._command,
                reversible=False,
                blast_radius=(
                    "local operator host and resources reachable by the API process user"
                ),
            )
        )

    @staticmethod
    def _read_risk():
        from services.agent_runtime.contracts import ToolRisk

        return ToolRisk.READ

    @staticmethod
    def _command_risk():
        from services.agent_runtime.contracts import ToolRisk

        return ToolRisk.HIGH_IMPACT

    def _ready(self) -> ToolResult | None:
        if self.bridge.configured:
            return None
        return ToolResult(
            False,
            error=(
                "Operator Bridge is not configured. Set DEVON_OPERATOR_ENABLED=1, "
                "DEVON_OPERATOR_KEY, and DEVON_OPERATOR_ROOT on the private host."
            ),
        )

    def _read(self, arguments: Dict[str, Any]) -> ToolResult:
        not_ready = self._ready()
        if not_ready:
            return not_ready
        command = str(arguments.get("command") or "").strip()
        cwd = arguments.get("cwd")
        timeout = int(arguments.get("timeout_seconds") or 60)
        try:
            plan = self.bridge.plan(command, str(cwd) if cwd else None)
            if plan.risk is not Risk.READ:
                return ToolResult(
                    False,
                    error=(
                        f"operator.read refused {plan.risk.value} command: {plan.reason}. "
                        "Use operator.command for a governed effect."
                    ),
                )
            result = self.bridge.execute_read(plan, timeout)
        except (OperatorError, ValueError, TypeError) as exc:
            return ToolResult(False, error=str(exc))
        return self._tool_result(result.to_dict())

    def _command(self, arguments: Dict[str, Any]) -> ToolResult:
        not_ready = self._ready()
        if not_ready:
            return not_ready
        args = dict(arguments)
        approval = args.pop(APPROVAL_METADATA_KEY, None)
        if not isinstance(approval, dict):
            return ToolResult(False, error="runtime approval metadata is missing")
        request_id = str(approval.get("request_id") or "").strip()
        binding = str(approval.get("binding") or "").strip()
        if not request_id or not binding:
            return ToolResult(False, error="runtime approval metadata is incomplete")

        command = str(args.get("command") or "").strip()
        cwd = args.get("cwd")
        timeout = int(args.get("timeout_seconds") or 60)
        try:
            plan = self.bridge.plan(command, str(cwd) if cwd else None)
            if plan.risk is Risk.BLOCKED:
                return ToolResult(False, error=plan.reason)
            if plan.risk is Risk.READ:
                return ToolResult(
                    False,
                    error="operator.command is for effectful work; use operator.read for reads",
                )
            result = self.bridge.execute_runtime_approved(
                plan,
                request_id=request_id,
                binding=binding,
                approvals=self.approvals,
                timeout_seconds=timeout,
            )
        except (OperatorError, ValueError, TypeError) as exc:
            return ToolResult(False, error=str(exc))
        return self._tool_result(result.to_dict())

    @staticmethod
    def _tool_result(data: Dict[str, object]) -> ToolResult:
        returncode = int(data.get("returncode") or 0)
        stdout = str(data.get("stdout") or "")
        stderr = str(data.get("stderr") or "")
        return ToolResult(
            ok=returncode == 0,
            output=stdout,
            error=stderr if returncode else "",
            metadata=dict(data),
        )
