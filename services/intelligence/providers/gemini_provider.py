"""Gemini through Google's OpenAI-compatible Chat Completions endpoint.

Contract: https://aistudio.google.com/docs/openai
Model changes: https://aistudio.google.com/docs/whats-new-gemini-3.8
This adapter uses max_tokens and omits deprecated sampling for Gemini 3.8.
Offline transport tests do not establish live key, model or deployment readiness.
"""

from __future__ import annotations

import httpx

from services.intelligence.providers.base import (
    CompletionRequest,
    CompletionResponse,
    ProviderConfigError,
    ProviderResponseError,
)
from services.intelligence.providers.openai_provider import OpenAIProvider

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_MODEL = "gemini-3.8-flash"


class GeminiProvider(OpenAIProvider):
    """Share transport, retry rules and metering contract, specialize the body."""

    name = "gemini"
    api_url = GEMINI_API_URL

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = DEFAULT_MODEL,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not set. Set it in the environment or switch "
                "DEFAULT_AI_PROVIDER to 'mock' for offline development.",
                provider=self.name,
            )
        super().__init__(
            api_key=api_key,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
        )

    def _request_body(self, request: CompletionRequest) -> dict:
        body = super()._request_body(request)
        body["max_tokens"] = body.pop("max_completion_tokens")
        if self.resolve_model(request).startswith("gemini-3.8-"):
            # The 3.8 migration contract removes sampling controls. Other
            # configured model families retain their own request contract.
            body["reasoning_effort"] = "low"
            body.pop("temperature", None)
            body.pop("top_p", None)
            body.pop("top_k", None)
        return body

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        try:
            return await super()._complete_once(request)
        except (ValueError, TypeError, AttributeError, IndexError) as exc:
            # Do not echo the provider body or leak untyped parse failures.
            raise ProviderResponseError(
                "Gemini returned a malformed completion response", provider=self.name,
            ) from exc


    def _parse_response(self, request: CompletionRequest, data: dict) -> CompletionResponse:
        def invalid():
            return ProviderResponseError(
                "Gemini returned an invalid completion or token-usage shape", provider=self.name,
            )

        if not isinstance(data, dict):
            raise invalid()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise invalid()
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise invalid()
        usage = data.get("usage")
        if not isinstance(usage, dict):
            raise invalid()
        for field in ("prompt_tokens", "completion_tokens"):
            value = usage.get(field)
            if type(value) is not int or value < 0:
                raise invalid()
        return super()._parse_response(request, data)
