"""Notion capability adapter for DEVON Agent Runtime.

Ruled by Tee 2026-10-24: DEVON executes, with direct access to Notion. The
create is a WRITE, so it runs only on an approved card whose binding matches
these exact arguments, the same gate every GitHub write passes. The page is
read back before the step reports success.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue
from services.notion.client import NotionRESTClient, NotionRESTError

CREATE_TOOL = "notion.create_page"
READ_TOOL = "notion.read_page"


class NotionCapabilityAdapter:
    """Expose page creation in the allowlisted DEVON databases, and reading back."""

    name = "notion"

    def __init__(self, client: NotionRESTClient, approvals: ApprovalQueue) -> None:
        self.client = client
        self.approvals = approvals

    def _scope(self) -> str:
        parts = []
        for name in self.client.database_names:
            spec = self.client.databases[name]
            props = "; ".join(
                f"{prop} ({kind}{': ' + ', '.join(options) if options else ''})"
                for prop, (kind, options) in spec["properties"].items()
            )
            parts.append(f"{name} = {spec['title']}, properties: {props}")
        return " Databases: " + " | ".join(parts) + "."

    def register(self, registry: ToolRegistry) -> None:
        scope = self._scope()
        registry.register(
            ToolSpec(
                name=CREATE_TOOL,
                parameters=("database", "title", "properties", "body"),
                description=(
                    "Create one page in an allowlisted DEVON Notion database after "
                    "DEVON approval, then read it back. properties maps a property "
                    "name to a value; a select takes one of its listed options, a "
                    "multi_select a list of them, a date YYYY-MM-DD. body is plain "
                    "text, paragraphs split on blank lines." + scope
                ),
                risk=ToolRisk.WRITE,
                handler=self._create_page,
                reversible=True,
                blast_radius="one new page in one allowlisted DEVON Notion database",
            )
        )
        registry.register(
            ToolSpec(
                name=READ_TOOL,
                parameters=("page_id",),
                description=(
                    "Read one page's properties, only when it sits in an allowlisted "
                    "DEVON Notion database." + scope
                ),
                risk=ToolRisk.READ,
                handler=self._read_page,
                reversible=True,
                blast_radius="read-only Notion page request in one allowlisted database",
            )
        )

    async def _create_page(self, arguments: Dict[str, Any]) -> ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        properties = args.get("properties") or {}
        if not isinstance(properties, dict):
            return ToolResult(False, error="properties must be an object of name to value")
        # Everything cheap and refusable happens before the approval is spent,
        # so a bad option or a missing token costs a correction, not a ruling.
        if not self.client.configured:
            return self._not_configured()
        try:
            self.client.build_page(
                str(args.get("database") or ""),
                title=str(args.get("title") or ""),
                properties=properties,
                body=str(args.get("body") or ""),
            )
        except NotionRESTError as exc:
            return ToolResult(False, error=f"{exc}. Nothing ran and the approval was not spent.")
        try:
            require_approved_runtime_binding(
                self.approvals, metadata, tool_name=CREATE_TOOL, arguments=args
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        return await self._call(
            lambda: self.client.create_page(
                str(args.get("database") or ""),
                title=str(args.get("title") or ""),
                properties=properties,
                body=str(args.get("body") or ""),
            )
        )

    async def _read_page(self, arguments: Dict[str, Any]) -> ToolResult:
        return await self._call(
            lambda: self.client.read_page(str(arguments.get("page_id") or ""))
        )

    async def _call(self, call: Callable[[], Awaitable[Dict[str, Any]]]) -> ToolResult:
        if not self.client.configured:
            return self._not_configured()
        try:
            data = await call()
        except (NotionRESTError, ValueError, TypeError) as exc:
            return ToolResult(False, error=str(exc))
        metadata: Dict[str, Any] = {
            key: data[key] for key in ("database", "page_id", "url", "read_back") if key in data
        }
        if data.get("page_id"):
            metadata["provider_receipt_id"] = str(data["page_id"])
        return ToolResult(
            True,
            output=json.dumps(data, ensure_ascii=False, sort_keys=True, default=str),
            metadata=metadata,
        )

    @staticmethod
    def _not_configured() -> ToolResult:
        return ToolResult(
            False,
            error=(
                "Notion adapter is not configured. Set DEVON_NOTION_TOKEN and share "
                "each DEVON database with the integration. Nothing ran."
            ),
        )
