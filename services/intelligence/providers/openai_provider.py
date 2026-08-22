"""
OpenAI provider — implements the AIProvider contract via Chat Completions.

Uses `httpx` directly (already a platform dependency) instead of a vendor
SDK, keeping the dependency surface small and the abstraction honest.
API reference: https://platform.openai.com/docs/api-reference/chat
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

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    """OpenAI models via the Chat Completions API.

    `api_url` is a class attribute rather than a module constant so that any
    OpenAI compatible endpoint can reuse this request path by subclassing and
    overriding one line. Cerebras is the first such subclass. The default is
    unchanged, so nothing that used this class before behaves differently.
    """

    name = "openai"
    api_url = _API_URL

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "gpt-5.2",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "OPENAI_API_KEY is not set. Set it in the environment or "
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
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)

        body: dict = {
            "model": self.resolve_model(request),
            "max_completion_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if request.json_mode:
            # Chat Completions JSON mode requires the word "json" to appear in
            # the prompt — our structured prompts always include it.
            body["response_format"] = {"type": "json_object"}
        if request.stop_sequences:
            body["stop"] = request.stop_sequences

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    self.api_url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"OpenAI request timed out after {self.timeout_seconds}s",
                provider=self.name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                f"Network error calling OpenAI: {exc}", provider=self.name
            ) from exc

        self._raise_for_status(response)

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderResponseError(
                "OpenAI returned no choices", provider=self.name
            )
        first = choices[0]
        usage = data.get("usage", {})
        return CompletionResponse(
            text=(first.get("message") or {}).get("content", "") or "",
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            model=data.get("model", self.resolve_model(request)),
            provider=self.name,
            finish_reason=first.get("finish_reason"),
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        detail = _error_detail(response)
        if response.status_code == 401:
            raise ProviderAuthError(
                f"OpenAI authentication failed: {detail}", provider=self.name
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"OpenAI rate limit: {detail}", provider=self.name
            )
        if response.status_code >= 500:
            raise ProviderServerError(
                f"OpenAI server error ({response.status_code}): {detail}",
                provider=self.name,
            )
        raise ProviderResponseError(
            f"OpenAI request rejected ({response.status_code}): {detail}",
            provider=self.name,
        )


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        return payload.get("error", {}).get("message", response.text[:300])
    except Exception:  # noqa: BLE001 — any parse failure falls back to raw text
        return response.text[:300]
