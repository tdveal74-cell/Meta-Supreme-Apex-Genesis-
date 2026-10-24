"""n8n Action Router capability adapter for DEVON Agent Runtime.

One tool, `n8n.dispatch`, which hands one approved job to the Action Router.
It is a WRITE whatever the action, because the router is a door to executors
that write Drive, Airtable and Zapier, and a card is the only consent this
estate recognises. The approval is spent before the post, so one ruling
dispatches once.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue
from services.n8n_actions.client import ACTIONS, N8NActionClient, N8NActionError

DISPATCH_TOOL = "n8n.dispatch"


class N8NActionCapabilityAdapter:
    name = "n8n"

    def __init__(self, client: N8NActionClient, approvals: ApprovalQueue) -> None:
        self.client = client
        self.approvals = approvals

    def register(self, registry: ToolRegistry) -> None:
        actions = ", ".join(f"{name} (ceiling {ceiling})" for name, ceiling in sorted(ACTIONS.items()))
        registry.register(
            ToolSpec(
                name=DISPATCH_TOOL,
                parameters=("action", "summary", "payload", "area"),
                description=(
                    "Hand one job to DEVON's n8n Action Router after DEVON approval. "
                    f"Actions: {actions}. payload is what that executor reads: "
                    "airtable.row takes {airtable: {table, fields}}, zapier.mcp takes "
                    "{zapier: {tool, arguments}}, drive.draft drafts from the summary "
                    "and an optional {note}. The router and the executor each refuse "
                    "anything outside their own allowlist."
                ),
                risk=ToolRisk.WRITE,
                handler=self._dispatch,
                reversible=True,
                blast_radius="one job through one allowlisted n8n executor, at that executor's ceiling",
            )
        )

    async def _dispatch(self, arguments: Dict[str, Any]) -> ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        # Refuse a malformed job before the approval is spent, so a typo in the
        # action name or a bad payload costs nothing but a correction. The dry
        # build uses throwaway approval values; only its refusals matter.
        payload = args.get("payload") or {}
        if not isinstance(payload, dict):
            return ToolResult(False, error="payload must be an object. Nothing ran.")
        try:
            self.client.build_envelope(
                action=str(args.get("action") or ""),
                summary=str(args.get("summary") or ""),
                payload=payload,
                area=None,
                binding="0" * 64,
                request_id="dry-run",
                decided_by=None,
                decided_at=None,
                requested_at=None,
                expires_at=datetime.now(timezone.utc),
                card="",
            )
        except N8NActionError as exc:
            return ToolResult(False, error=f"{exc}. Nothing ran and the approval was not spent.")
        if not self.client.configured:
            return ToolResult(
                False,
                error=(
                    "n8n Action Router is not configured. Set DEVON_N8N_ACTION_KEY "
                    "on the deployment. Nothing ran and the approval was not spent."
                ),
            )
        try:
            request_id, binding = require_approved_runtime_binding(
                self.approvals, metadata, tool_name=DISPATCH_TOOL, arguments=args
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        record = self.approvals.get(request_id)
        if record is None:
            return ToolResult(False, error="the approval vanished after it was spent")
        try:
            envelope = self.client.build_envelope(
                action=str(args.get("action") or ""),
                summary=str(args.get("summary") or ""),
                payload=payload,
                area=str(args.get("area") or "") or None,
                binding=binding,
                request_id=request_id,
                decided_by=record.decided_by,
                decided_at=record.decided_at,
                requested_at=record.created_at,
                expires_at=record.expires_at,
                card=record.what_happens,
            )
            result = await self.client.dispatch(envelope)
        except N8NActionError as exc:
            return ToolResult(False, error=str(exc))
        metadata_out: Dict[str, Any] = {
            "action": result["action"],
            "intent_id": result["intent_id"],
            "state": result["state"],
            "provider_receipt_id": result.get("artifact_uri") or result["intent_id"],
        }
        return ToolResult(
            True,
            output=json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
            metadata=metadata_out,
        )
