"""
Embedding provider abstraction — model-agnostic text embeddings.

Mirrors the completion-provider design: one interface, swappable
implementations, retries in the base class, explicit errors.

Implementations:
- OpenAIEmbeddingProvider — text-embedding-3-small (1536 dims, matches the
  `embeddings.embedding vector(1536)` column)
- MockEmbeddingProvider — deterministic, offline, zero keys. Produces
  normalized hashed bag-of-words vectors, so overlapping vocabulary yields
  genuinely higher cosine similarity: retrieval behaves lexically, which is
  honest for a simulation and useful for tests. Clearly labeled simulated.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from services.intelligence.providers.base import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536  # matches database/schemas vector(1536)


@dataclass
class EmbeddingResponse:
    """Provider-agnostic embedding result (index-aligned with the input)."""

    vectors: List[List[float]]
    model: str
    provider: str
    input_tokens: int = 0
    latency_ms: int = 0
    metadata: dict = field(default_factory=dict)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers with bounded retries."""

    name: str = "abstract"

    def __init__(
        self,
        *,
        default_model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)

    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        """Embed a batch of texts. Never fails silently."""
        if not texts:
            return EmbeddingResponse(vectors=[], model=self.default_model, provider=self.name)

        attempt = 0
        started = time.monotonic()
        while True:
            try:
                response = await self._embed_once(texts)
                response.latency_ms = int((time.monotonic() - started) * 1000)
                return response
            except ProviderError as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                delay = min(2.0 ** attempt, 30.0)
                logger.warning(
                    "embedding provider=%s retryable error (attempt %d/%d): %s",
                    self.name, attempt + 1, self.max_retries, exc,
                )
                await asyncio.sleep(delay)
                attempt += 1

    @abstractmethod
    async def _embed_once(self, texts: List[str]) -> EmbeddingResponse:
        """Perform a single embedding attempt. Raise ProviderError subtypes."""


# ---------------------------------------------------------------------------
# Mock — deterministic hashed bag-of-words
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _mock_vector(text: str) -> List[float]:
    """Deterministic normalized vector; shared vocabulary → higher cosine similarity."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline embeddings for development and tests."""

    name = "mock"

    def __init__(self, *, default_model: str = "mock-embed-v1") -> None:
        super().__init__(default_model=default_model, max_retries=0)

    async def _embed_once(self, texts: List[str]) -> EmbeddingResponse:
        return EmbeddingResponse(
            vectors=[_mock_vector(t) for t in texts],
            model=self.default_model,
            provider=self.name,
            input_tokens=sum(max(1, len(t) // 4) for t in texts),
            metadata={"simulated": True},
        )


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

_OPENAI_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings via the REST API (no vendor SDK)."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "text-embedding-3-small",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "OPENAI_API_KEY is not set. Set it, or use EMBEDDING_PROVIDER=mock "
                "for offline development.",
                provider=self.name,
            )
        super().__init__(
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._api_key = api_key
        self._transport = transport

    async def _embed_once(self, texts: List[str]) -> EmbeddingResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    _OPENAI_URL,
                    json={
                        "model": self.default_model,
                        "input": texts,
                        "dimensions": EMBEDDING_DIMENSIONS,
                    },
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"OpenAI embeddings timed out after {self.timeout_seconds}s",
                provider=self.name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                f"Network error calling OpenAI embeddings: {exc}", provider=self.name
            ) from exc

        if response.status_code == 401:
            raise ProviderAuthError("OpenAI embeddings auth failed", provider=self.name)
        if response.status_code == 429:
            raise ProviderRateLimitError("OpenAI embeddings rate limit", provider=self.name)
        if response.status_code >= 500:
            raise ProviderServerError(
                f"OpenAI embeddings server error ({response.status_code})",
                provider=self.name,
            )
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"OpenAI embeddings rejected ({response.status_code}): {response.text[:200]}",
                provider=self.name,
            )

        payload = response.json()
        rows = sorted(payload.get("data", []), key=lambda r: r.get("index", 0))
        vectors = [row.get("embedding", []) for row in rows]
        if len(vectors) != len(texts):
            raise ProviderResponseError(
                "OpenAI embeddings returned a mismatched batch", provider=self.name
            )
        return EmbeddingResponse(
            vectors=vectors,
            model=payload.get("model", self.default_model),
            provider=self.name,
            input_tokens=int(payload.get("usage", {}).get("prompt_tokens", 0)),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

SUPPORTED_EMBEDDING_PROVIDERS = ("mock", "openai")


def create_embedding_provider(
    provider_name: str,
    *,
    openai_api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
) -> EmbeddingProvider:
    """Build the configured embedding provider. Misconfiguration fails loudly."""
    name = (provider_name or "").strip().lower()
    if name == "mock":
        return MockEmbeddingProvider(default_model=model or "mock-embed-v1")
    if name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=openai_api_key or "",
            default_model=model or "text-embedding-3-small",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    raise ProviderConfigError(
        f"Unknown embedding provider '{provider_name}'. "
        f"Supported: {', '.join(SUPPORTED_EMBEDDING_PROVIDERS)}."
    )
