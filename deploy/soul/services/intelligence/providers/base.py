"""
AI Provider abstraction — model-agnostic contracts.

Every provider (Anthropic, OpenAI, Mock, future additions) implements the
same interface so the Executive Controller and agent executor never depend
on a specific vendor. Swapping providers is a configuration change, not a
code change.

Design notes
------------
- Framework-free: this module uses only the standard library so the
  services layer stays independent of FastAPI/Pydantic.
- Retries live in the base class (`AIProvider.complete`) so every provider
  gets identical, predictable retry behavior for retryable failures.
- Token usage is always reported, enabling cost tracking from day one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    """A single message in a completion request."""

    role: str  # "user" | "assistant"
    content: str


@dataclass
class TokenUsage:
    """Token accounting for a single completion."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class CompletionRequest:
    """Provider-agnostic completion request."""

    messages: List[ChatMessage]
    system: Optional[str] = None
    model: Optional[str] = None  # None → provider default
    max_tokens: int = 1024
    temperature: float = 0.2
    json_mode: bool = False  # ask the model for a single JSON object
    stop_sequences: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Provider-agnostic completion response."""

    text: str
    usage: TokenUsage
    model: str
    provider: str
    latency_ms: int = 0
    finish_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base error for all provider failures."""

    def __init__(self, message: str, *, provider: str = "unknown", retryable: bool = False):
        self.provider = provider
        self.retryable = retryable
        super().__init__(message)


class ProviderConfigError(ProviderError):
    """Provider is misconfigured (e.g. missing API key). Never retryable."""


class ProviderAuthError(ProviderError):
    """Authentication failed (invalid API key). Never retryable."""


class ProviderRateLimitError(ProviderError):
    """Rate limited by the provider. Retryable."""

    def __init__(self, message: str, *, provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class ProviderTimeoutError(ProviderError):
    """The provider did not answer in time. Retryable."""

    def __init__(self, message: str, *, provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class ProviderServerError(ProviderError):
    """Provider-side 5xx / overloaded. Retryable."""

    def __init__(self, message: str, *, provider: str = "unknown"):
        super().__init__(message, provider=provider, retryable=True)


class ProviderResponseError(ProviderError):
    """The provider returned something unusable (bad request / malformed body)."""


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------

class AIProvider(ABC):
    """
    Abstract base for all AI providers.

    Subclasses implement `_complete_once`; the public `complete` adds
    timing and bounded retries with exponential backoff for retryable
    failures (rate limits, timeouts, provider 5xx).
    """

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

    # -- public API ---------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Run a completion with bounded retries. Never fails silently."""
        attempt = 0
        started = time.monotonic()
        while True:
            try:
                response = await self._complete_once(request)
                response.latency_ms = int((time.monotonic() - started) * 1000)
                return response
            except ProviderError as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                delay = self._backoff_seconds(attempt)
                logger.warning(
                    "provider=%s retryable error (attempt %d/%d, retrying in %.1fs): %s",
                    self.name, attempt + 1, self.max_retries, delay, exc,
                )
                await asyncio.sleep(delay)
                attempt += 1

    # -- subclass contract --------------------------------------------------

    @abstractmethod
    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        """Perform a single completion attempt. Raise ProviderError subtypes."""

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        """Deterministic exponential backoff: 1s, 2s, 4s… capped at 30s."""
        return min(2.0 ** attempt, 30.0)

    def resolve_model(self, request: CompletionRequest) -> str:
        return request.model or self.default_model


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> Dict[str, Any]:
    """
    Robustly extract a single JSON object from model output.

    Handles code fences and leading/trailing prose. Raises ValueError if no
    valid JSON object can be recovered — callers must handle the failure
    explicitly (never fabricate structure that was not produced).
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("No valid JSON object found in model output")
