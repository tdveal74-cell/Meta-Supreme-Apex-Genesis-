"""
Anthropic provider — implements the AIProvider contract via the Messages API.

Uses `httpx` directly (already a platform dependency) instead of a vendor
SDK, keeping the dependency surface small and the abstraction honest.
API reference: https://docs.anthropic.com/en/api/messages
"""

from __future__ import annotations

import httpx

from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    TokenUsage,
)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

_JSON_MODE_INSTRUCTION = (
    "\n\nRespond with a single valid JSON object only. "
    "No prose before or after it, and no markdown code fences."
)


class AnthropicProvider(AIProvider):
    """Anthropic Claude models via the Messages API."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "claude-sonnet-5",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "ANTHROPIC_API_KEY is not set. Set it in the environment or "
                "switch DEFAULT_AI_PROVIDER to 'mock' for offline development.",
                provider=self.name,
            )
        super().__init__(
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._api_key = api_key
        self._transport = transport  # injectable for tests

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        system = request.system or ""
        if request.json_mode:
            system = (system + _JSON_MODE_INSTRUCTION).strip()

        body: dict = {
            "model": self.resolve_model(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
        }
        if system:
            body["system"] = system
        if request.stop_sequences:
            body["stop_sequences"] = request.stop_sequences

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    _API_URL,
                    json=body,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": _API_VERSION,
                        "content-type": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Anthropic request timed out after {self.timeout_seconds}s",
                provider=self.name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                f"Network error calling Anthropic: {exc}", provider=self.name
            ) from exc

        self._raise_for_status(response)

        data = response.json()
        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        usage = data.get("usage", {})
        return CompletionResponse(
            text="".join(text_parts),
            usage=TokenUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            model=data.get("model", self.resolve_model(request)),
            provider=self.name,
            finish_reason=data.get("stop_reason"),
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        detail = _error_detail(response)
        if response.status_code == 401:
            raise ProviderAuthError(
                f"Anthropic authentication failed: {detail}", provider=self.name
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Anthropic rate limit: {detail}", provider=self.name
            )
        if response.status_code in (500, 502, 503, 529):
            raise ProviderServerError(
                f"Anthropic server error ({response.status_code}): {detail}",
                provider=self.name,
            )
        raise ProviderResponseError(
            f"Anthropic request rejected ({response.status_code}): {detail}",
            provider=self.name,
        )


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        return payload.get("error", {}).get("message", response.text[:300])
    except Exception:  # noqa: BLE001 — any parse failure falls back to raw text
        return response.text[:300]
