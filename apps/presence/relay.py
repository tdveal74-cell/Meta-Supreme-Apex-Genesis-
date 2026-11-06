"""Authenticated text relay. Presence never holds a ledger connection.

The token belongs to one turn task, copied from that session's hello. Neither
the shared router nor its streamers have a mutable current-user field.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import AsyncIterator

import httpx

from apps.presence.settings import validate_api_base

access_token: ContextVar[str] = ContextVar("presence_access_token", default="")


class InferenceRefused(RuntimeError):
    """A terminal auth, cap or accounting refusal. Never select a fallback."""


class RelayTokenStreamer:
    """A whole completion from the API, committed to its ledger before success."""

    def __init__(
        self, name: str, api_base: str, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.name = name
        self._url = validate_api_base(api_base).rstrip("/") + "/api/v1/presence/complete"
        self._transport = transport

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        from apps.presence.inference import split_tokens

        token = access_token.get()
        if not token:
            raise InferenceRefused("DEVON authentication is required for inference.")
        # No redirect, retry or provider credential. Cancellation of this HTTP
        # wait does not cancel the API's retained completion-and-meter task.
        async with httpx.AsyncClient(
            transport=self._transport, timeout=50.0, follow_redirects=False
        ) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {token}"},
                json={"text": prompt, "provider": self.name},
            )
        if response.status_code != 200:
            if response.status_code in (401, 403):
                message = "DEVON authentication expired or was refused. Sign in again."
            elif response.status_code == 429:
                message = "DEVON refused this inference at its usage or capacity limit."
            else:
                message = "DEVON could not confirm a metered inference. No automatic retry."
            # Do not forward a response body, token, URL or arbitrary exception.
            raise InferenceRefused(message)
        try:
            data = response.json()
            usage = data["usage"]
            counts = [usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")]
            valid = (
                data["provider"] == self.name
                and data["usage_recorded"] is True
                and isinstance(data["text"], str)
                and all(type(v) is int and v >= 0 for v in counts)
                and counts[0] + counts[1] == counts[2]
            )
            if not valid:
                raise ValueError("invalid metered response")
        except (ValueError, TypeError, KeyError, IndexError):
            raise InferenceRefused("DEVON returned an unconfirmed usage record.") from None
        for token_text in split_tokens(data["text"]):
            yield token_text
