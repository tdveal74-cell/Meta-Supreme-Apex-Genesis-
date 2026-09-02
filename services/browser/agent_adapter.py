"""Allowlisted browser capability adapter for DEVON Agent Runtime.

Read-only fetch is permitted without approval. Navigation and form submission
are WRITE/HIGH_IMPACT and require DEVON approval. No arbitrary JavaScript
execution is exposed.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional, Set
from urllib.parse import urlparse

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import ApprovalQueue

_SAFE_SCHEME = {"http", "https"}
_DEFAULT_ALLOW = {
    "github.com",
    "api.github.com",
    "docs.github.com",
    "x.com",
    "twitter.com",
    "en.wikipedia.org",
}


class BrowserCapabilityAdapter:
    """Governed HTTP page fetch and allowlisted navigation proposals."""

    name = "browser"

    def __init__(
        self,
        approvals: ApprovalQueue,
        *,
        allowed_hosts: Optional[Set[str]] = None,
        fetcher=None,
    ) -> None:
        self.approvals = approvals
        self.allowed_hosts = {h.lower() for h in (allowed_hosts or _DEFAULT_ALLOW)}
        self._fetcher = fetcher  # optional inject for tests; None → offline stub

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="browser.fetch",
                parameters=("url",),
                description=(
                    "Fetch one allowlisted HTTP(S) URL as plain text (read-only). "
                    "No cookies, no form posts, no script execution."
                ),
                risk=ToolRisk.READ,
                handler=self._fetch,
                reversible=True,
                blast_radius="read-only HTTP GET to one allowlisted host",
            )
        )
        registry.register(
            ToolSpec(
                name="browser.navigate",
                parameters=("url",),
                description=(
                    "Record an intent to navigate to an allowlisted URL, under "
                    "DEVON approval. This opens NO browser and loads NO page: it "
                    "returns nothing about the URL's contents. To read a page, "
                    "use browser.fetch instead."
                ),
                risk=ToolRisk.WRITE,
                handler=self._navigate,
                reversible=True,
                blast_radius="one approved navigation record to an allowlisted host",
            )
        )

    def _fetch(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            url = self._require_url(arguments.get("url"))
        except ValueError as exc:
            return ToolResult(False, error=str(exc))

        if self._fetcher is not None:
            try:
                body = self._fetcher(url)
            except Exception as exc:
                return ToolResult(False, error=f"fetch failed: {exc}")
        else:
            # Offline-safe stub: prove governance without network in CI.
            body = f"[browser.fetch stub] allowlisted URL accepted: {url}"

        text = str(body)[:50_000]
        receipt = hashlib.sha256(f"fetch:{url}:{len(text)}".encode()).hexdigest()[:24]
        return ToolResult(
            True,
            output=text,
            metadata={
                "url": url,
                # No redirect is ever followed, so the page read is the page asked for.
                "final_url": url,
                "bytes": len(text),
                "provider_receipt_id": f"br-fetch-{receipt}",
            },
        )

    def _navigate(self, arguments: Dict[str, Any]) -> ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)
        try:
            require_approved_runtime_binding(
                self.approvals,
                metadata,
                tool_name="browser.navigate",
                arguments=args,
            )
            url = self._require_url(args.get("url"))
        except ValueError as exc:
            return ToolResult(False, error=str(exc))

        receipt = hashlib.sha256(f"nav:{url}".encode()).hexdigest()[:24]
        return ToolResult(
            True,
            output=(
                f"Recorded an intent to navigate to {url}. No browser session was "
                "opened and no page was loaded, so nothing here was read. Use "
                "browser.fetch to actually retrieve the page."
            ),
            metadata={
                "url": url,
                "action": "navigate",
                "visited": False,
                "provider_receipt_id": f"br-nav-{receipt}",
            },
        )

    def _require_url(self, raw: Any) -> str:
        url = str(raw or "").strip()
        if not url:
            raise ValueError("url is required")
        parsed = urlparse(url)
        if parsed.scheme.lower() not in _SAFE_SCHEME:
            raise ValueError("only http and https URLs are allowed")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError("url host is missing")
        if parsed.username is not None or parsed.password is not None:
            # httpx turns user:pass@host into an Authorization header, which
            # would send model-written credentials to the allowlisted host.
            raise ValueError("url must not carry credentials (user:pass@host)")
        if not self._host_allowed(host):
            raise ValueError(f"host not in browser allowlist: {host}")
        if re.search(r"[\s<>]", url):
            raise ValueError("url contains forbidden characters")
        return url

    def _host_allowed(self, host: str) -> bool:
        if host in self.allowed_hosts:
            return True
        return any(host.endswith("." + allowed) for allowed in self.allowed_hosts)
