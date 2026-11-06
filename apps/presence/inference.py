"""Token streamers: the thing the router asks for tokens.

A ``TokenStreamer`` is anything with a ``name`` and an async ``stream``
that yields text tokens for a prompt. The router in ``breaker.py`` only
cares about two moments: when the first token arrives (time to first
token, the number the breaker watches) and whether the stream ends
cleanly.

Three implementations live here.

``MockTokenStreamer`` is for tests and the offline lane. Its timing is
scripted (``first_token_delay_ms``, ``delay_ms``, ``fail_before_first``)
so a slow or failing primary can be reproduced without a network and
without a sleep longer than the test allows.

``ProviderTokenStreamer`` adapts an ``AIProvider`` from
``services.intelligence.providers``. Stated plainly: that base class has
no streaming API today. ``complete()`` returns the whole reply, so this
adapter's time to first token is the whole completion latency, and the
"tokens" it yields are the reply split into words after the fact. That is
honest enough to drive the breaker (a slow completion is a slow first
token) but it is not real streaming. Real provider streaming is a separate gate. It was not verified in this
build and nothing here pretends otherwise.

Configured real providers use ``RelayTokenStreamer`` from ``relay.py``. Its
API call carries the session JWT; the API selects its configured provider,
checks the tenant cap and commits provider usage before returning text.
``ProviderTokenStreamer`` remains the mock and injected offline adapter only.

The system prompt reuses the DEVON persona from ``services.devon.persona``
rather than inventing a second voice for the face.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List, Optional, Protocol, runtime_checkable

from apps.presence.settings import PresenceSettings
from services.intelligence.presence import PRESENCE_SYSTEM_PROMPT
from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderConfigError,
)
from services.intelligence.providers.factory import create_provider

DEFAULT_MOCK_TEXT = "This is the offline mock voice. The face you see is driven by this text."




class StreamerError(RuntimeError):
    """A streamer failed before or during its reply."""


@runtime_checkable
class TokenStreamer(Protocol):
    """Anything that can stream text tokens for a prompt."""

    name: str

    def stream(self, prompt: str) -> AsyncIterator[str]: ...


def split_tokens(text: str) -> List[str]:
    """Words with their trailing space, so joining the tokens rebuilds the text."""
    words = text.split()
    if not words:
        return []
    return [word + " " for word in words[:-1]] + [words[-1]]


class MockTokenStreamer:
    """Scripted streamer for tests. No network, deterministic text and timing."""

    def __init__(
        self,
        text: str = DEFAULT_MOCK_TEXT,
        *,
        delay_ms: float = 0.0,
        first_token_delay_ms: float = 0.0,
        fail_before_first: bool = False,
        name: str = "mock",
    ) -> None:
        self.text = text
        self.delay_ms = float(delay_ms)
        self.first_token_delay_ms = float(first_token_delay_ms)
        self.fail_before_first = fail_before_first
        self.name = name
        self.calls = 0
        self.last_prompt = ""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        self.last_prompt = prompt
        if self.first_token_delay_ms > 0:
            await asyncio.sleep(self.first_token_delay_ms / 1000.0)
        if self.fail_before_first:
            raise StreamerError(f"{self.name}: failing before the first token, as scripted")
        for index, token in enumerate(split_tokens(self.text)):
            if index and self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000.0)
            yield token


class ProviderTokenStreamer:
    """Adapt a whole completion provider to the streamer shape.

    Time to first token here equals whole completion latency, because the
    provider base class has no streaming call. See the module docstring.
    """

    def __init__(
        self,
        provider: AIProvider,
        *,
        system: Optional[str] = PRESENCE_SYSTEM_PROMPT,
        max_tokens: int = 200,
        temperature: float = 0.4,
    ) -> None:
        self._provider = provider
        self._system = system
        self._max_tokens = max_tokens
        self._temperature = temperature

    @property
    def name(self) -> str:
        return self._provider.name

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        request = CompletionRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            system=self._system,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            metadata={"component": "devon-presence"},
        )
        response = await self._provider.complete(request)
        for token in split_tokens(response.text):
            yield token


def build_streamer(name: str, settings: PresenceSettings) -> Optional[TokenStreamer]:
    """Build the configured streamer, or None for an empty name.

    Mock stays local. Every real provider is served by the authenticated API,
    where the daily cap and durable ledger live. Presence never calls a vendor
    directly, and the API refuses a name other than its configured provider.
    """
    chosen = (name or "").strip().lower()
    if not chosen:
        return None
    if chosen == "mock":
        return ProviderTokenStreamer(create_provider("mock", max_retries=0))
    if chosen not in ("gemini", "cerebras", "anthropic", "openai"):
        raise ProviderConfigError(
            "presence inference name is not supported", provider=chosen
        )
    from apps.presence.relay import RelayTokenStreamer

    return RelayTokenStreamer(chosen, settings.PRESENCE_API_BASE)
