"""
Cerebras Cloud provider.

Already live in Tee's studio: SYS_SPEC_context-pill_v16 section B11 records
Cerebras wired into the iPhone Inbox Capture workflow on 2026-08-22, credential
"Cerebras Cloud" YTVk8Dq2gYPAmUim, model gpt-oss-120b, endpoint
api.cerebras.ai/v1/chat/completions, measured at 42ms. This module brings the
same lane into the platform so the enrichment behaves identically in both places.

WHY IT SUBCLASSES THE OPENAI PROVIDER
Cerebras serves an OpenAI compatible Chat Completions API. Reusing that request
path means one implementation of the body shape, the error mapping and the retry
behaviour, rather than two that drift. The differences are the endpoint, the
default model, and the rate limits.

RATE LIMITS ARE DEFENDED IN PROCESS, NOT DISCOVERED IN PRODUCTION
The recorded free tier allowance is 5 requests per minute, 150 per hour, 2400
per day and 1,000,000 tokens per day. Those are tight enough that a burst from a
capture sweep will hit them. The limiter here refuses locally, before the call,
and says which window was exhausted. Refusing early is deliberate: a 429 from
the vendor costs a round trip and arrives as a retryable error, which the base
class would then retry into the same wall.

A NOTE RECORDED HONESTLY
On 2026-08-20 a fabricated architecture board named Cerebras as live inference
infrastructure, and that board was rejected as reconstructed rather than
retrieved. The wiring was then genuinely built and measured on 2026-08-22. Both
things are true, and the second is the one this module implements. The lesson
kept: an artifact claiming a system exists is not evidence the system exists.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

import httpx

from services.intelligence.providers.base import (
    CompletionRequest,
    CompletionResponse,
    ProviderConfigError,
    ProviderRateLimitError,
)
from services.intelligence.providers.openai_provider import OpenAIProvider

SOURCE = {
    "recorded_in": "SYS_SPEC_context-pill_v16 section B11",
    "credential": "Cerebras Cloud YTVk8Dq2gYPAmUim",
    "measured_latency_ms": 42,
    "read": "2026-08-22",
}

CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
DEFAULT_MODEL = "gpt-oss-120b"

# Recorded allowance. Override at construction if the account tier differs.
LIMIT_PER_MINUTE = 5
LIMIT_PER_HOUR = 150
LIMIT_PER_DAY = 2400
TOKEN_LIMIT_PER_DAY = 1_000_000

# Cerebras serves text models. An image arriving as a bare identifier has
# nothing readable in it, which is a stated limit rather than a defect.
SUPPORTS_IMAGES = False


@dataclass
class RateLimiter:
    """Sliding window request and token counter.

    Deliberately in process and deliberately simple. It protects a single
    operator's assistant from walking into a documented wall. It is not a
    distributed limiter and does not pretend to be: with more than one process
    calling the same key, the vendor's own 429 remains the real backstop.

    Use None for a window to mean unlimited. Zero means zero requests allowed,
    which is a legitimate setting for disabling the lane and is distinct from
    "not configured". Conflating the two is how a limiter silently stops
    limiting.
    """

    per_minute: Optional[int] = LIMIT_PER_MINUTE
    per_hour: Optional[int] = LIMIT_PER_HOUR
    per_day: Optional[int] = LIMIT_PER_DAY
    tokens_per_day: Optional[int] = TOKEN_LIMIT_PER_DAY
    _requests: Deque[float] = field(default_factory=deque)
    _tokens: Deque[tuple] = field(default_factory=deque)

    def _prune(self, now: float) -> None:
        while self._requests and now - self._requests[0] > 86400:
            self._requests.popleft()
        while self._tokens and now - self._tokens[0][0] > 86400:
            self._tokens.popleft()

    def _count_within(self, now: float, seconds: float) -> int:
        return sum(1 for stamp in self._requests if now - stamp <= seconds)

    def tokens_today(self, now: Optional[float] = None) -> int:
        now = now if now is not None else time.monotonic()
        return sum(count for stamp, count in self._tokens if now - stamp <= 86400)

    def check(self, now: Optional[float] = None) -> None:
        """Raise before the call when a window is exhausted."""
        now = now if now is not None else time.monotonic()
        self._prune(now)

        for window_seconds, limit, label in (
            (60.0, self.per_minute, "per minute"),
            (3600.0, self.per_hour, "per hour"),
            (86400.0, self.per_day, "per day"),
        ):
            if limit is not None and self._count_within(now, window_seconds) >= limit:
                raise ProviderRateLimitError(
                    f"Cerebras local limiter: {limit} requests {label} already used. "
                    "Refused before calling so the vendor 429 is not retried into "
                    "the same wall.",
                    provider="cerebras",
                )

        if self.tokens_per_day is not None and self.tokens_today(now) >= self.tokens_per_day:
            raise ProviderRateLimitError(
                f"Cerebras local limiter: daily token allowance of "
                f"{self.tokens_per_day} already used.",
                provider="cerebras",
            )

    def record(self, tokens: int = 0, now: Optional[float] = None) -> None:
        now = now if now is not None else time.monotonic()
        self._requests.append(now)
        if tokens:
            self._tokens.append((now, tokens))
        self._prune(now)

    def snapshot(self, now: Optional[float] = None) -> dict:
        """What has been spent, for observability rather than guesswork."""
        now = now if now is not None else time.monotonic()
        self._prune(now)
        return {
            "last_minute": self._count_within(now, 60.0),
            "last_hour": self._count_within(now, 3600.0),
            "last_day": self._count_within(now, 86400.0),
            "tokens_today": self.tokens_today(now),
            "limits": {
                "per_minute": self.per_minute,
                "per_hour": self.per_hour,
                "per_day": self.per_day,
                "tokens_per_day": self.tokens_per_day,
            },
        }


class CerebrasProvider(OpenAIProvider):
    """Cerebras Cloud via its OpenAI compatible Chat Completions endpoint."""

    name = "cerebras"
    api_url = CEREBRAS_API_URL

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = DEFAULT_MODEL,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: Optional[RateLimiter] = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "CEREBRAS_API_KEY is not set. Set it in the environment or switch "
                "DEFAULT_AI_PROVIDER to 'mock' for offline development. The key "
                "belongs in the environment, never in the vault and never in code.",
                provider=self.name,
            )
        # Skip OpenAIProvider.__init__ so its OPENAI_API_KEY message never fires
        # for a Cerebras misconfiguration, which would send a reader to the wrong
        # environment variable.
        super(OpenAIProvider, self).__init__(
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._api_key = api_key
        self._transport = transport
        self.limiter = limiter if limiter is not None else RateLimiter()

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        self.limiter.check()
        response = await super()._complete_once(request)
        self.limiter.record(tokens=response.usage.total_tokens)
        return response
