"""Circuit breaker and inference router.

The breaker is driven with an injected clock, so the cooldown is advanced,
not waited for. The router tests use real asyncio time, but no scripted
delay exceeds 40 ms and the router cancels the slow primary at the 20 ms
threshold, so no test sleeps longer than that.
"""

import asyncio
import time
from typing import AsyncIterator, List

import pytest

from apps.presence.breaker import (
    BreakerState,
    CircuitBreaker,
    InferenceRouter,
    InferenceUnavailable,
    TurnMetrics,
)
from apps.presence.inference import MockTokenStreamer, StreamerError, split_tokens


class ManualClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def _collect(router: InferenceRouter, prompt: str, turn: TurnMetrics) -> List[str]:
    return [token async for token in router.stream(prompt, turn)]


# ---------------------------------------------------------------------------
# breaker
# ---------------------------------------------------------------------------


def test_opens_after_three_consecutive_breaches_slow_or_failed():
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=500, cooldown_s=30, clock=clock)

    assert breaker.record_success(900) is True  # served, but late: a breach
    assert breaker.state is BreakerState.CLOSED
    breaker.record_failure("rate limit")
    assert breaker.state is BreakerState.CLOSED
    breaker.record_failure("timeout")
    assert breaker.state is BreakerState.OPEN
    assert breaker.consecutive_breaches == 3
    assert breaker.opens == 1
    assert breaker.allows_primary() is False


def test_a_fast_success_resets_the_consecutive_count():
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=500, clock=ManualClock())
    breaker.record_failure("a")
    breaker.record_failure("b")
    assert breaker.record_success(120) is False
    assert breaker.consecutive_breaches == 0
    breaker.record_failure("c")
    breaker.record_failure("d")
    assert breaker.state is BreakerState.CLOSED


def test_half_opens_after_the_cooldown_and_one_success_closes_it():
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=500, cooldown_s=30, clock=clock)
    for reason in ("one", "two", "three"):
        breaker.record_failure(reason)
    assert breaker.state is BreakerState.OPEN

    clock.advance(29.9)
    assert breaker.state is BreakerState.OPEN
    clock.advance(0.1)
    assert breaker.state is BreakerState.HALF_OPEN
    assert breaker.allows_primary() is True

    breaker.record_success(100)
    assert breaker.state is BreakerState.CLOSED
    assert breaker.closes == 1
    assert breaker.consecutive_breaches == 0


def test_a_breach_while_half_open_reopens_and_restarts_the_cooldown():
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=500, cooldown_s=30, clock=clock)
    for reason in ("one", "two", "three"):
        breaker.record_failure(reason)
    clock.advance(30)
    assert breaker.state is BreakerState.HALF_OPEN

    breaker.record_success(2000)  # the probe answered, far too late
    assert breaker.state is BreakerState.OPEN
    assert breaker.opens == 2
    clock.advance(29)
    assert breaker.state is BreakerState.OPEN
    clock.advance(1)
    assert breaker.state is BreakerState.HALF_OPEN


def test_snapshot_reports_state_and_counters():
    clock = ManualClock()
    breaker = CircuitBreaker(failure_threshold=2, ttft_threshold_ms=500, cooldown_s=10, clock=clock)
    breaker.record_failure("rate limit")
    breaker.record_failure("timeout")
    clock.advance(4)
    snapshot = breaker.snapshot()
    assert snapshot["state"] == "open"
    assert snapshot["consecutive_breaches"] == 2
    assert snapshot["failure_threshold"] == 2
    assert snapshot["ttft_threshold_ms"] == 500.0
    assert snapshot["cooldown_s"] == 10.0
    assert snapshot["open_for_s"] == 4.0
    assert snapshot["last_reason"] == "timeout"
    assert snapshot["total_breaches"] == 2


def test_breaker_refuses_nonsense_thresholds():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(ttft_threshold_ms=0)
    with pytest.raises(ValueError):
        CircuitBreaker(cooldown_s=0)


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------


async def test_primary_serves_when_its_first_token_is_in_time():
    primary = MockTokenStreamer("hello from the primary", name="primary")
    fallback = MockTokenStreamer("should not be used", name="fallback")
    router = InferenceRouter(primary, fallback, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t1")

    tokens = await _collect(router, "hi", turn)

    assert "".join(tokens) == "hello from the primary"
    assert tokens == split_tokens("hello from the primary")
    assert turn.provider == "primary"
    assert turn.fell_back is False
    assert 0 <= turn.ttft_ms < 20
    assert turn.tokens == 4
    assert turn.breaker == "closed"
    assert fallback.calls == 0


async def test_falls_back_when_the_first_token_exceeds_the_threshold():
    primary = MockTokenStreamer("slow primary", first_token_delay_ms=40, name="slow")
    fallback = MockTokenStreamer("fallback reply here", name="fallback")
    router = InferenceRouter(primary, fallback, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t2")

    started = time.perf_counter()
    tokens = await _collect(router, "hi", turn)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert "".join(tokens) == "fallback reply here"
    assert turn.fell_back is True
    assert turn.provider == "fallback"
    assert "no first token within 20 ms" in turn.primary_error
    assert turn.ttft_ms >= 20
    assert elapsed_ms < 40, "the slow primary must be cancelled at the threshold, not waited for"
    assert primary.calls == 1 and fallback.calls == 1
    assert router.breaker.consecutive_breaches == 1
    assert router.breaker.state is BreakerState.CLOSED


async def test_falls_back_when_the_primary_fails_before_its_first_token():
    primary = MockTokenStreamer(fail_before_first=True, name="broken")
    fallback = MockTokenStreamer("fallback reply", name="fallback")
    router = InferenceRouter(primary, fallback, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t3")

    tokens = await _collect(router, "hi", turn)

    assert "".join(tokens) == "fallback reply"
    assert turn.fell_back is True
    assert "StreamerError" in turn.primary_error
    assert router.breaker.last_reason.startswith("broken: StreamerError")


async def test_without_a_fallback_a_breach_raises_and_names_the_variable():
    primary = MockTokenStreamer(fail_before_first=True, name="broken")
    router = InferenceRouter(primary, None, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t4")

    with pytest.raises(InferenceUnavailable) as info:
        await _collect(router, "hi", turn)

    assert "PRESENCE_FALLBACK_INFERENCE" in str(info.value)
    assert router.breaker.consecutive_breaches == 1


async def test_an_open_breaker_routes_to_the_fallback_without_calling_the_primary():
    clock = ManualClock()
    primary = MockTokenStreamer(fail_before_first=True, name="flaky")
    fallback = MockTokenStreamer("fallback", name="fallback")
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=20, cooldown_s=30, clock=clock)
    router = InferenceRouter(primary, fallback, breaker=breaker, ttft_threshold_ms=20)

    for index in range(3):
        await _collect(router, "hi", TurnMetrics(turn_id=f"warm{index}"))
    assert breaker.state is BreakerState.OPEN
    assert primary.calls == 3

    primary.fail_before_first = False  # it recovered, but the breaker does not know yet
    turn = TurnMetrics(turn_id="open")
    tokens = await _collect(router, "hi", turn)

    assert "".join(tokens) == "fallback"
    assert primary.calls == 3, "an open breaker must not touch the primary"
    assert turn.fell_back is True
    assert "breaker open" in turn.primary_error
    assert turn.breaker == "open"


async def test_half_open_probe_closes_on_success_and_serves_from_the_primary():
    clock = ManualClock()
    primary = MockTokenStreamer("primary is back", fail_before_first=True, name="primary")
    fallback = MockTokenStreamer("fallback", name="fallback")
    breaker = CircuitBreaker(failure_threshold=3, ttft_threshold_ms=20, cooldown_s=30, clock=clock)
    router = InferenceRouter(primary, fallback, breaker=breaker, ttft_threshold_ms=20)
    for index in range(3):
        await _collect(router, "hi", TurnMetrics(turn_id=f"warm{index}"))
    assert breaker.state is BreakerState.OPEN

    clock.advance(30)
    primary.fail_before_first = False
    turn = TurnMetrics(turn_id="probe")
    tokens = await _collect(router, "hi", turn)

    assert "".join(tokens) == "primary is back"
    assert turn.fell_back is False
    assert breaker.state is BreakerState.CLOSED
    assert primary.calls == 4


async def test_no_fallback_and_open_breaker_still_tries_the_primary():
    clock = ManualClock()
    primary = MockTokenStreamer("answer", fail_before_first=True, name="only")
    breaker = CircuitBreaker(failure_threshold=2, ttft_threshold_ms=20, cooldown_s=30, clock=clock)
    router = InferenceRouter(primary, None, breaker=breaker, ttft_threshold_ms=20)
    for index in range(2):
        with pytest.raises(InferenceUnavailable):
            await _collect(router, "hi", TurnMetrics(turn_id=f"warm{index}"))
    assert breaker.state is BreakerState.OPEN

    primary.fail_before_first = False
    turn = TurnMetrics(turn_id="try")
    tokens = await _collect(router, "hi", turn)

    assert "".join(tokens) == "answer"
    assert breaker.state is BreakerState.CLOSED


class _DiesMidStream:
    name = "mid"

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield "first "
        raise StreamerError("connection reset after the first token")


async def test_a_failure_after_the_first_token_raises_rather_than_switching_provider():
    fallback = MockTokenStreamer("fallback", name="fallback")
    router = InferenceRouter(_DiesMidStream(), fallback, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t5")
    received: List[str] = []

    with pytest.raises(InferenceUnavailable) as info:
        async for token in router.stream("hi", turn):
            received.append(token)

    assert received == ["first "]
    assert "does not change provider after its first token" in str(info.value)
    assert fallback.calls == 0
    assert router.breaker.consecutive_breaches == 1


async def test_cancelling_the_consumer_mid_stream_is_clean():
    primary = MockTokenStreamer("a b c d e f", delay_ms=5, name="primary")
    router = InferenceRouter(primary, None, ttft_threshold_ms=20)
    turn = TurnMetrics(turn_id="t6")
    received: List[str] = []

    async def consume() -> None:
        async for token in router.stream("hi", turn):
            received.append(token)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.012)
    task.cancel()
    await asyncio.wait({task})

    assert task.cancelled()
    assert 1 <= len(received) < 6
