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
        return await self._request("GET", "/api/health")

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
