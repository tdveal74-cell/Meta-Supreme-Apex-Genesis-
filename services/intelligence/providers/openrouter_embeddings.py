"""OpenRouter embeddings, pinned to the existing 1536-dimensional model.

No arbitrary endpoint, model fallback, or silent mock downgrade. Provider
identity stays openrouter for usage receipts. Coverage trust is separate.
"""

from __future__ import annotations

import math

import httpx

from .base import (
    ProviderAuthError,
    ProviderBillingError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    billing_refusal,
)
from .embeddings import EMBEDDING_DIMENSIONS, EmbeddingProvider, EmbeddingResponse

MODEL = "openai/text-embedding-3-small"
URL = "https://openrouter.ai/api/v1/embeddings"


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = MODEL,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ProviderConfigError("OPENROUTER_API_KEY is not set.", provider=self.name)
        if default_model != MODEL:
            raise ProviderConfigError(
                f"OpenRouter embeddings require {MODEL} at {EMBEDDING_DIMENSIONS} dimensions.",
                provider=self.name,
            )
        super().__init__(
            default_model=default_model, timeout_seconds=timeout_seconds, max_retries=max_retries
        )
        self._api_key = api_key
        self._transport = transport

    async def _embed_once(self, texts: list[str]) -> EmbeddingResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": MODEL,
                        "input": texts,
                        "dimensions": EMBEDDING_DIMENSIONS,
                        "encoding_format": "float",
                        "provider": {"allow_fallbacks": False, "require_parameters": True},
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "OpenRouter embeddings timed out.", provider=self.name
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                "OpenRouter embeddings network error.", provider=self.name
            ) from exc
        status = response.status_code
        if status >= 400 and billing_refusal(status, response.text[:400]):
            raise ProviderBillingError(
                "OpenRouter embeddings refused funding. Check OpenRouter credits and key limits.",
                provider=self.name,
            )
        if status in (401, 403):
            raise ProviderAuthError(
                "OpenRouter embeddings authorization failed.", provider=self.name
            )
        if status == 429:
            raise ProviderRateLimitError("OpenRouter embeddings rate limit.", provider=self.name)
        if status >= 500:
            raise ProviderServerError(f"OpenRouter embeddings HTTP {status}.", provider=self.name)
        if status != 200:
            raise ProviderResponseError(f"OpenRouter embeddings HTTP {status}.", provider=self.name)
        try:
            payload = response.json()
            if payload.get("model") not in (MODEL, "text-embedding-3-small"):
                raise ValueError("unexpected model")
            rows = payload["data"]
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError("mismatched batch")
            indices = [row["index"] for row in rows]
            if any(type(i) is not int for i in indices) or sorted(indices) != list(
                range(len(texts))
            ):
                raise ValueError("invalid indices")
            vectors = [row["embedding"] for row in sorted(rows, key=lambda r: r["index"])]
            for vector in vectors:
                if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
                    raise ValueError("wrong dimensions")
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                    raise ValueError("non-finite or non-numeric vector")
                norm = sum(v * v for v in vector)
                if not math.isfinite(norm) or norm <= 0:
                    raise ValueError("invalid vector norm")
            tokens = payload["usage"]["prompt_tokens"]
            if type(tokens) is not int or tokens <= 0:
                raise ValueError("invalid usage")
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            raise ProviderResponseError(
                "OpenRouter returned an invalid embedding batch; nothing accepted.",
                provider=self.name,
            ) from exc
        return EmbeddingResponse(
            vectors=vectors, model=MODEL, provider=self.name, input_tokens=tokens
        )
