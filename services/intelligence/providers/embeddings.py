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
from typing import Any, List, Optional

import httpx

from services.intelligence.providers.base import (
    ProviderAuthError,
    ProviderBillingError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    billing_message,
    billing_refusal,
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

        # Funding first, for the same reason as the completion path: OpenAI
        # answers an empty account with 429, which used to be retried here.
        if response.status_code >= 400:
            detail = response.text[:400]
            reason = billing_refusal(response.status_code, detail)
            if reason:
                raise ProviderBillingError(
                    billing_message(
                        "OpenAI embeddings", response.status_code, detail, reason
                    ),
                    provider=self.name,
                )
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

#: Providers whose DISTANCES may decide whether a document was found at all.
#:
#: Supporting a provider and trusting its distances are different claims.
#: `mock` is supported, deterministic and useful for tests, and its distances
#: are not usable for a verdict: measured 2026-09-16, a sourdough recipe scored
#: 0.6406 against an episode about jobs while an on topic question scored
#: 0.6170. Ranking an unrelated document higher is not a weak signal, it is a
#: wrong one.
#:
#: An ALLOWLIST, so a provider added to SUPPORTED_EMBEDDING_PROVIDERS has to be
#: measured before its distances are believed rather than trusted until it is
#: caught. Same shape and the same reason as
#: `app.services.episodes.TRUSTED_FOR_COVERAGE`, which answers the narrower
#: question of whether a coverage verdict may be rendered.
TRUSTED_FOR_RETRIEVAL = ("openai",)


def dense_signal_is_trusted(provider_name: str) -> bool:
    """May this provider's distances introduce a retrieval candidate?

    Fails closed on anything unrecognised, including None and an empty string.
    """
    return (provider_name or "").strip().lower() in TRUSTED_FOR_RETRIEVAL


def resolve_embedding_provider_name(settings: Any) -> str:
    """Name the provider that embeds, from the field that names itself.

    THIS EXISTS BECAUSE THE TWO LANES WERE WELDED TO THE CHAT PROVIDER.

    Until 2026-09-17 both embedding resolvers, `app.services.knowledge` and
    `services.knowledge.pipeline`, looked for a settings field called
    `DEFAULT_EMBEDDING_PROVIDER` and fell through to `DEFAULT_AI_PROVIDER`
    when they did not find one. They never found one: that field does not
    exist and never did. `EMBEDDING_PROVIDER` does exist, defaults to "mock",
    and `app/core/config.py` documents it in its own comment as the switch to
    flip for real semantic retrieval. Nothing read it.

    The consequence was not cosmetic. Embeddings inherited the CHAT provider,
    and this estate runs chat on Cerebras, which `SUPPORTED_EMBEDDING_PROVIDERS`
    does not carry. So `EMBEDDING_PROVIDER=openai` on the production api changed
    nothing and every embedding call resolved to 'cerebras' and raised
    ProviderConfigError. Reproduced 2026-09-17 with the production shape:
    EMBEDDING_PROVIDER=openai, DEFAULT_AI_PROVIDER=cerebras, no OPENAI_API_KEY,
    and the documented control was dead.

    An earlier draft of this paragraph said Cerebras has no embeddings endpoint.
    That may well be true and it was not checked: `api.cerebras.ai` is blocked
    by this container's egress policy, so the claim could not be run. It is also
    not the load bearing fact. What breaks the estate is that this factory
    builds 'mock' and 'openai' and nothing else, so a chat provider name
    reaching it raises whatever the vendor does or does not offer.

    There is no fallback to `DEFAULT_AI_PROVIDER` here on purpose. That
    fallback IS the weld. A chat provider name reaching this function is how
    the two got tied together, and re-adding it to be helpful would tie them
    again the first time someone sets a chat provider that cannot embed.

    A deployment that previously got real embeddings by setting
    `DEFAULT_AI_PROVIDER=openai` and leaving `EMBEDDING_PROVIDER` alone now
    gets mock instead, which is a downgrade that must never be silent: mock
    vectors are deterministic and plausible, and under them a sourdough recipe
    scored 0.6406 against the jobs episode while an on topic question scored
    0.6170. So that case warns rather than passing quietly.
    """
    name = getattr(settings, "EMBEDDING_PROVIDER", None)
    resolved = name.strip().lower() if isinstance(name, str) and name.strip() else "mock"

    if resolved == "mock":
        chat = getattr(settings, "DEFAULT_AI_PROVIDER", None)
        chat_name = chat.strip().lower() if isinstance(chat, str) else ""
        if chat_name in SUPPORTED_EMBEDDING_PROVIDERS and chat_name != "mock":
            logger.warning(
                "Embeddings are on mock while DEFAULT_AI_PROVIDER=%s can embed. "
                "Before 2026-09-17 embeddings followed the chat provider and this "
                "would have been real vectors. Set EMBEDDING_PROVIDER=%s if that "
                "is what you meant; mock vectors are deterministic and will happily "
                "rank an unrelated document above a relevant one.",
                chat_name,
                chat_name,
            )
    return resolved


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
