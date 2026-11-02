"""Gemini through Google's OpenAI-compatible Chat Completions endpoint.

The compatibility endpoint and gemini-3.8-flash were exercised against Tee's
existing Google credential on 2026-11-02. The supported request used max_tokens,
so this adapter explicitly replaces OpenAI's max_completion_tokens field.
"""

from __future__ import annotations

import httpx

from services.intelligence.providers.base import CompletionRequest, ProviderConfigError
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
        return body
