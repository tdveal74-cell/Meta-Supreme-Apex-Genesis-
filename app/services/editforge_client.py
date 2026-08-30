"""Authenticated EditForge transport at the application effect boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib.parse import quote

import httpx

from services.devon.editforge_execution import EditForgeExecutionError


@dataclass(frozen=True)
class EditForgeConfig:
    base_url: str
    token: str
    timeout_seconds: float = 60.0

    @property
    def configured(self) -> bool:
        return bool(self.base_url.strip() and self.token.strip())


class EditForgeClient:
    """Fail-closed HTTP client with an injectable transport for verification."""

    def __init__(
        self,
        config: EditForgeConfig,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.config = config
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        if not self.config.configured:
            raise EditForgeExecutionError("EditForge URL and token are required")
        return {"Authorization": f"Bearer {self.config.token}"}

    async def _request(
        self, method: str, path: str, *, payload: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        headers = self._headers()
        async with httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            timeout=self.config.timeout_seconds,
            transport=self.transport,
            trust_env=False,
        ) as client:
            response = await client.request(
                method,
                path,
                headers=headers,
                json=dict(payload) if payload is not None else None,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise EditForgeExecutionError(
                f"EditForge returned non-JSON HTTP {response.status_code}"
            ) from exc
        if response.status_code >= 400:
            raise EditForgeExecutionError(
                str(data.get("error") or f"EditForge HTTP {response.status_code}")
            )
        return data

    async def status(self) -> Dict[str, Any]:
        """Health only. EditForge leaves this route open, so it proves nothing
        about the credential — see `read_editforge_status`."""
        return await self._request("GET", "/api/health")

    async def executions(self) -> Dict[str, Any]:
        """Authenticated read of the edit lane.

        Read-only, spends nothing, and travels the same `/api/edits` boundary
        every command does, so reaching it proves the credential works for the
        thing execution actually needs.
        """
        return await self._request("GET", "/api/edits")

    async def execute(self, command: Mapping[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/edits", payload=command)

    async def execution(self, command_id: str, *, poll: bool = True) -> Dict[str, Any]:
        suffix = "?poll=1" if poll else ""
        return await self._request(
            "GET", f"/api/edits/{quote(command_id, safe='')}{suffix}"
        )

    async def action(self, command_id: str, action: str) -> Dict[str, Any]:
        if action not in {"retry", "cancel"}:
            raise EditForgeExecutionError("action must be retry or cancel")
        return await self._request(
            "POST",
            f"/api/edits/{quote(command_id, safe='')}",
            payload={"action": action},
        )


async def read_editforge_status(
    config: EditForgeConfig,
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """Return the normalized live status without ever returning the credential.

    `live_verified` means the configured token actually works, not merely that
    something answered. EditForge deliberately leaves `/api/health` outside its
    access gate so uptime checks survive a private deployment, so reading it
    proves reachability and nothing else: a wrong `EDITFORGE_TOKEN` reported a
    fully verified studio and only surfaced later, as a 401 on the first real
    command. Verifying costs one authenticated read of the same `/api/edits`
    lane every command travels.

    The three outcomes stay distinguishable rather than collapsing into one
    false negative: not configured, unreachable, and reachable-but-rejected.
    The last keeps the health payload, because "the studio is up and your token
    is wrong" is a different fix from "the studio is down".
    """
    client = EditForgeClient(config, transport=transport)
    if not config.configured:
        return {
            "configured": False,
            "live_verified": False,
            "reason": "EDITFORGE_URL and EDITFORGE_TOKEN must be configured",
        }
    try:
        status = await client.status()
    except EditForgeExecutionError as exc:
        return {"configured": True, "live_verified": False, "reason": str(exc)}
    try:
        await client.executions()
    except EditForgeExecutionError as exc:
        return {
            "configured": True,
            "live_verified": False,
            # States what was observed, then the overwhelmingly likely remedy.
            # `_request` does not surface the status code, so this cannot claim
            # the refusal was specifically a 401 — a failing edit store would
            # land here too, and naming a cause it did not verify would send an
            # operator to rotate a token that was never wrong.
            "reason": (
                f"EditForge is reachable but refused an authenticated read: {exc}"
                " — EDITFORGE_TOKEN must match the studio's EDITFORGE_MCP_TOKEN"
            ),
            "editforge": status,
        }
    return {"configured": True, "live_verified": True, "editforge": status}
