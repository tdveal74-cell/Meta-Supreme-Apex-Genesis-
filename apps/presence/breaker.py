"""Circuit breaker and inference router (system gap 2: TTFT degradation).

A presence turn dies on latency before it dies on quality. If the first
token takes a second, the face sits frozen for a second, and no amount of
eloquence afterwards repairs that. So the number watched here is time to
first token (TTFT), per turn, against ``ttft_threshold_ms``.

``CircuitBreaker`` counts consecutive breaches on the primary provider. A
breach is either a TTFT above the threshold or a failure before the first
token (rate limit, timeout, provider error). After ``failure_threshold``
consecutive breaches it opens; while open the router does not ask the
primary at all. After ``cooldown_s`` it half opens: the next turn probes
the primary, one success closes it, one breach reopens it. The clock is
injectable so the cooldown is tested with time that is advanced, not
waited for.

``InferenceRouter`` holds a primary streamer and an optional fallback.
The one property that matters to the person on the other end: the
WebSocket never drops because of a provider. When the primary is open,
slow, or failing before its first token, the same turn continues from
the fallback, and the only thing that changes is which streamer produced
the tokens. ``TurnMetrics`` records which one, the TTFT the user actually
saw, and what the primary did wrong.

What it refuses
---------------
- A turn does not change provider after the first token. A reply that
  starts on one model and finishes on another is two half replies; the
  router raises ``InferenceUnavailable`` instead and the session reports
  the error on the open socket.
- With no fallback configured, a breach raises ``InferenceUnavailable``
  with the reason and the variable to set. An open breaker with no
  fallback does not refuse the turn: there is nowhere else to send it,
  so the primary is tried and its result recorded, which is also how
  the breaker learns the provider recovered.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Callable, Dict, Optional

from apps.presence.inference import TokenStreamer

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_TTFT_THRESHOLD_MS = 500.0
DEFAULT_COOLDOWN_S = 30.0


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class InferenceUnavailable(RuntimeError):
    """No streamer could serve this turn. The message says why and what to set."""


class CircuitBreaker:
    """Consecutive breach counter with a timed half open probe."""

    def __init__(
        self,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        ttft_threshold_ms: float = DEFAULT_TTFT_THRESHOLD_MS,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        clock: Callable[[], float] = time.monotonic,
        name: str = "primary",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if ttft_threshold_ms <= 0:
            raise ValueError("ttft_threshold_ms must be greater than zero")
        if cooldown_s <= 0:
            raise ValueError("cooldown_s must be greater than zero")
        self.failure_threshold = int(failure_threshold)
        self.ttft_threshold_ms = float(ttft_threshold_ms)
        self.cooldown_s = float(cooldown_s)
        self.name = name
        self._clock = clock
        self._state = BreakerState.CLOSED
        self._opened_at: Optional[float] = None
        self.consecutive_breaches = 0
        self.total_breaches = 0
        self.opens = 0
        self.closes = 0
        self.last_reason = ""
        self.last_ttft_ms: Optional[float] = None

    @property
    def state(self) -> BreakerState:
        """Current state. Reading it is what moves open to half open after the cooldown."""
        if (
            self._state is BreakerState.OPEN
            and self._opened_at is not None
            and self._clock() - self._opened_at >= self.cooldown_s
        ):
            self._state = BreakerState.HALF_OPEN
        return self._state

    def allows_primary(self) -> bool:
        return self.state is not BreakerState.OPEN

    def record_success(self, ttft_ms: float) -> bool:
        """Record a served turn. Returns True when it still counted as a breach.

        A reply that arrived, but after the threshold, is a breach: the
        face froze for that long whether or not text followed.
        """
        self.last_ttft_ms = float(ttft_ms)
        if ttft_ms > self.ttft_threshold_ms:
            self._breach(
                f"first token after {ttft_ms:.0f} ms, threshold {self.ttft_threshold_ms:.0f} ms"
            )
            return True
        if self.state is not BreakerState.CLOSED:
            self.closes += 1
        self._state = BreakerState.CLOSED
        self._opened_at = None
        self.consecutive_breaches = 0
        self.last_reason = ""
        return False

    def record_failure(self, reason: str) -> None:
        """Record a failure before the first token: rate limit, timeout, error."""
        self._breach(reason or "failure with no reason given")

    def _breach(self, reason: str) -> None:
        self.last_reason = reason
        self.total_breaches += 1
        self.consecutive_breaches += 1
        current = self.state
        if current is BreakerState.CLOSED:
            if self.consecutive_breaches >= self.failure_threshold:
                self._open()
        else:
            # A half open probe failed, or a call made while open (no fallback
            # to route to) failed. Reopen and restart the cooldown.
            self._open()

    def _open(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()
        self.opens += 1

    def snapshot(self) -> Dict[str, object]:
        state = self.state
        open_for_s: Optional[float] = None
        if self._opened_at is not None and state is BreakerState.OPEN:
            open_for_s = round(self._clock() - self._opened_at, 3)
        return {
            "name": self.name,
            "state": state.value,
            "consecutive_breaches": self.consecutive_breaches,
            "failure_threshold": self.failure_threshold,
            "ttft_threshold_ms": self.ttft_threshold_ms,
            "cooldown_s": self.cooldown_s,
            "open_for_s": open_for_s,
            "last_reason": self.last_reason,
            "last_ttft_ms": self.last_ttft_ms,
            "opens": self.opens,
            "closes": self.closes,
            "total_breaches": self.total_breaches,
        }


@dataclass
class TurnMetrics:
    """What one turn's inference actually did. Filled in by the router."""

    turn_id: str
    provider: str = ""
    fell_back: bool = False
    ttft_ms: float = 0.0
    breaker: str = BreakerState.CLOSED.value
    tokens: int = 0
    primary_error: str = ""


async def _next_token(gen: AsyncIterator[str]) -> str:
    return await gen.__anext__()


async def _close_quietly(gen: AsyncIterator[str]) -> None:
    aclose = getattr(gen, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:  # noqa: BLE001 - a streamer that fails on close has already failed
        return


class InferenceRouter:
    """Primary with a TTFT guard, fallback on breach, same turn, same socket."""

    def __init__(
        self,
        primary: TokenStreamer,
        fallback: Optional[TokenStreamer] = None,
        *,
        breaker: Optional[CircuitBreaker] = None,
        ttft_threshold_ms: float = DEFAULT_TTFT_THRESHOLD_MS,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if ttft_threshold_ms <= 0:
            raise ValueError("ttft_threshold_ms must be greater than zero")
        self.primary = primary
        self.fallback = fallback
        self.ttft_threshold_ms = float(ttft_threshold_ms)
        self.breaker = breaker or CircuitBreaker(ttft_threshold_ms=ttft_threshold_ms)
        self._clock = clock

    @property
    def fallback_name(self) -> str:
        return self.fallback.name if self.fallback is not None else ""

    async def stream(self, prompt: str, turn: TurnMetrics) -> AsyncIterator[str]:
        """Yield the turn's tokens, filling ``turn`` with who served and how fast."""
        started = self._clock()
        turn.breaker = self.breaker.state.value

        if self.breaker.state is BreakerState.OPEN and self.fallback is not None:
            turn.primary_error = f"{self.primary.name}: breaker open ({self.breaker.last_reason})"
            async for token in self._serve_fallback(prompt, turn, started):
                yield token
            return

        gen = self.primary.stream(prompt)
        first = ""
        reason = ""
        try:
            first = await asyncio.wait_for(
                _next_token(gen), timeout=self.ttft_threshold_ms / 1000.0
            )
        except asyncio.TimeoutError:
            reason = (
                f"{self.primary.name}: no first token within {self.ttft_threshold_ms:.0f} ms"
            )
        except StopAsyncIteration:
            reason = f"{self.primary.name}: empty reply"
        except asyncio.CancelledError:
            await _close_quietly(gen)
            raise
        except Exception as exc:  # noqa: BLE001 - any failure before the first token is a breach
            reason = f"{self.primary.name}: {type(exc).__name__}: {exc}"

        if reason:
            await _close_quietly(gen)
            self.breaker.record_failure(reason)
            turn.primary_error = reason
            turn.breaker = self.breaker.state.value
            if self.fallback is None:
                raise InferenceUnavailable(
                    f"{reason}; no fallback is configured (PRESENCE_FALLBACK_INFERENCE is "
                    "empty), so this turn cannot be served"
                )
            async for token in self._serve_fallback(prompt, turn, started):
                yield token
            return

        ttft_ms = (self._clock() - started) * 1000.0
        self.breaker.record_success(ttft_ms)
        turn.provider = self.primary.name
        turn.fell_back = False
        turn.ttft_ms = ttft_ms
        turn.breaker = self.breaker.state.value
        try:
            turn.tokens += 1
            yield first
            async for token in gen:
                turn.tokens += 1
                yield token
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failure = f"{self.primary.name}: {type(exc).__name__}: {exc}"
            self.breaker.record_failure(failure)
            turn.primary_error = failure
            turn.breaker = self.breaker.state.value
            raise InferenceUnavailable(
                f"{failure} after {turn.tokens} token(s); a turn does not change provider "
                "after its first token"
            ) from exc
        finally:
            await _close_quietly(gen)
        turn.breaker = self.breaker.state.value

    async def _serve_fallback(
        self, prompt: str, turn: TurnMetrics, started: float
    ) -> AsyncIterator[str]:
        fallback = self.fallback
        if fallback is None:  # pragma: no cover - guarded by every caller
            raise InferenceUnavailable("no fallback configured")
        turn.fell_back = True
        turn.provider = fallback.name
        gen = fallback.stream(prompt)
        got_first = False
        try:
            async for token in gen:
                if not got_first:
                    got_first = True
                    turn.ttft_ms = (self._clock() - started) * 1000.0
                turn.tokens += 1
                yield token
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise InferenceUnavailable(
                f"primary failed ({turn.primary_error}) and fallback {fallback.name} failed "
                f"too: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            await _close_quietly(gen)
        if not got_first:
            raise InferenceUnavailable(
                f"primary failed ({turn.primary_error}) and fallback {fallback.name} "
                "returned an empty reply"
            )
        turn.breaker = self.breaker.state.value
