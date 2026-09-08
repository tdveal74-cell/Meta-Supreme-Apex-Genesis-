"""One WebSocket conversation: the state machine and the turn loop.

States move idle, listening, thinking, speaking, listening. ``listening``
is where the session rests between turns. A ``say`` moves it to
``thinking`` while tokens stream from the router, ``speaking`` once the
synthesiser starts producing frames, and back to ``listening`` when the
audio timeline runs out. An ``interrupt`` cancels the in flight turn from
either working state and lands on ``listening`` at once.

The turn loop runs as a background task so the socket keeps reading
while the face talks: an interrupt, a render report or a ping is handled
mid turn without waiting for the turn to end. Sends are serialised
through one lock, because the turn task and the receive loop both write
to the same socket.

Pacing is behind a ``Pacer`` so the audio clock can be real
(``RealTimePacer``) in service and virtual (``VirtualPacer``) in tests,
where twelve seconds of mock speech would otherwise be twelve seconds of
waiting and an interrupt could never be placed mid turn on purpose.

What it refuses
---------------
- Frames from any synthesiser go through ``validate_frame`` before they
  are buffered. A frame naming a shape outside the ARKit 52 or a weight
  outside 0..1 fails the turn with an error naming it; it is not clamped.
- ``interrupt`` for a turn other than the in flight one acks with
  ``flushed_frames`` 0 and cancels nothing. A late interrupt for turn one
  must not kill turn two.
- A ``say`` while a turn is in flight is a barge in: the in flight turn is
  cancelled and flushed, its metrics are sent, and the new turn starts.

``server_latency_ms`` on the interrupt ack is measured with
``time.perf_counter`` from receipt of the interrupt to the state change.
It is a measurement, never a constant.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from apps.presence.breaker import InferenceRouter, InferenceUnavailable, TurnMetrics
from apps.presence.buffer import SlidingWindowBuffer
from apps.presence.protocol import (
    ERR_INFERENCE_UNAVAILABLE,
    ERR_SPEECH_NOT_CONFIGURED,
    ERR_TURN_FAILED,
    FrameValidationError,
    audio_message,
    error_message,
    frame_message,
    interrupt_ack_message,
    metrics_message,
    state_message,
    token_message,
    validate_frame,
)
from apps.presence.speech import (
    CHUNK_AUDIO,
    CHUNK_FRAME,
    CHUNK_STATE,
    SpeechNotConfigured,
    SpeechSynthesizer,
)

logger = logging.getLogger(__name__)

SendFn = Callable[[Dict[str, Any]], Awaitable[None]]


def _check_timeline(at_ms: float) -> None:
    """A chunk's place on the audio timeline has to be a real, non negative
    number. An infinite ``at_ms`` would hold the drain loop open forever, and
    NaN would reach the wire as a token JSON does not have; both fail the turn
    by name instead."""
    if not isinstance(at_ms, (int, float)) or isinstance(at_ms, bool):
        raise FrameValidationError(f"chunk at_ms must be a number, got {at_ms!r}")
    if at_ms != at_ms or at_ms in (float("inf"), float("-inf")) or at_ms < 0:
        raise FrameValidationError(f"chunk at_ms must be finite and not negative, got {at_ms!r}")


class SessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class Pacer(Protocol):
    """The audio clock the drain loop runs on."""

    def now_ms(self) -> float: ...

    async def sleep_ms(self, ms: float) -> None: ...


class RealTimePacer:
    """Wall clock pacing for a running service."""

    def now_ms(self) -> float:
        return time.perf_counter() * 1000.0

    async def sleep_ms(self, ms: float) -> None:
        await asyncio.sleep(max(0.0, ms) / 1000.0)


class VirtualPacer:
    """Deterministic pacing for tests.

    With ``auto_advance`` every sleep moves the clock forward by the
    requested amount and yields to the loop once, so a whole utterance
    drains in a handful of loop iterations. Without it a sleep blocks
    until the task is cancelled, which holds a turn in flight until an
    interrupt arrives.
    """

    def __init__(self, *, auto_advance: bool = True, start_ms: float = 0.0) -> None:
        self._now = float(start_ms)
        self.auto_advance = auto_advance
        self.sleeps = 0

    def now_ms(self) -> float:
        return self._now

    def advance(self, ms: float) -> None:
        self._now += float(ms)

    async def sleep_ms(self, ms: float) -> None:
        self.sleeps += 1
        if self.auto_advance:
            self._now += max(0.0, float(ms))
            await asyncio.sleep(0)
        else:
            await asyncio.Event().wait()


class PresenceSession:
    """Owns one conversation over one socket."""

    def __init__(
        self,
        *,
        session_id: str,
        user_id: str,
        router: InferenceRouter,
        speech: SpeechSynthesizer,
        send: SendFn,
        window_ms: float = 250.0,
        pacer: Optional[Pacer] = None,
        send_audio: bool = True,
        drain_interval_ms: Optional[float] = None,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.router = router
        self.speech = speech
        self._send = send
        self.window_ms = float(window_ms)
        self.pacer: Pacer = pacer if pacer is not None else RealTimePacer()
        self.send_audio = send_audio
        self.drain_interval_ms = (
            float(drain_interval_ms) if drain_interval_ms else self.window_ms / 2.0
        )
        self.state = SessionState.IDLE
        self.turn_id: Optional[str] = None
        self.behind_ms = 0.0
        self.fps = 0.0
        self.turns_started = 0
        self.turns_completed = 0
        self.turns_interrupted = 0
        self.last_interrupt_client_at_ms: Optional[float] = None
        self._active_turn_id: Optional[str] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._buffer: Optional[SlidingWindowBuffer] = None
        self._metrics: Optional[TurnMetrics] = None
        self._send_lock = asyncio.Lock()
        self._closed = False

    # -- socket -------------------------------------------------------------

    @property
    def closed(self) -> bool:
        return self._closed

    async def emit(self, message: Dict[str, Any]) -> bool:
        """Send one message. Returns False once the socket is gone."""
        if self._closed:
            return False
        async with self._send_lock:
            if self._closed:
                return False
            try:
                await self._send(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any send failure means the socket is gone
                self._closed = True
                logger.debug(
                    "presence session %s: send failed, socket treated as closed: %s",
                    self.session_id,
                    exc,
                )
                return False
        return True

    async def _set_state(self, state: SessionState, turn_id: Optional[str]) -> None:
        self.state = state
        self.turn_id = turn_id
        await self.emit(state_message(state.value, turn_id))

    async def open(self) -> None:
        await self._set_state(SessionState.LISTENING, None)

    async def close(self) -> None:
        """The socket is gone. Stop the turn without trying to say so."""
        self._closed = True
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait({task})
        self._task = None
        self.state = SessionState.IDLE
        self.turn_id = None

    # -- telemetry ----------------------------------------------------------

    def report_render(self, turn_id: str, behind_ms: float, fps: float) -> None:
        self.behind_ms = max(0.0, float(behind_ms))
        self.fps = float(fps)

    @property
    def in_flight(self) -> bool:
        return self._task is not None and not self._task.done()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "turn_id": self.turn_id,
            "behind_ms": self.behind_ms,
            "fps": self.fps,
            "turns_started": self.turns_started,
            "turns_completed": self.turns_completed,
            "turns_interrupted": self.turns_interrupted,
            "buffer": self._buffer.snapshot() if self._buffer is not None else None,
        }

    # -- turns --------------------------------------------------------------

    async def begin_turn(self, turn_id: str, text: str) -> "asyncio.Task[None]":
        """Start a turn in the background. An in flight turn is barged in on."""
        if self.in_flight:
            await self._cancel_inflight()
            self.turns_interrupted += 1
            await self._emit_metrics()
        self.turns_started += 1
        self._active_turn_id = turn_id
        self._task = asyncio.create_task(
            self._run_guarded(turn_id, text), name=f"presence-turn-{turn_id}"
        )
        return self._task

    async def _run_guarded(self, turn_id: str, text: str) -> None:
        try:
            await self.run_turn(turn_id, text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the socket must hear about any failure
            logger.exception("presence turn %s failed", turn_id)
            await self.emit(
                error_message(
                    ERR_TURN_FAILED, f"turn {turn_id} failed: {type(exc).__name__}: {exc}"
                )
            )
            await self._finish_turn()

    async def run_turn(self, turn_id: str, text: str) -> None:
        """Stream tokens, then speak the reply on the audio clock."""
        metrics = TurnMetrics(turn_id=turn_id)
        buffer = SlidingWindowBuffer(window_ms=self.window_ms)
        self._metrics = metrics
        self._buffer = buffer
        await self._set_state(SessionState.THINKING, turn_id)

        parts: List[str] = []
        try:
            async for token in self.router.stream(text, metrics):
                parts.append(token)
                await self.emit(token_message(turn_id, token))
        except InferenceUnavailable as exc:
            await self.emit(error_message(ERR_INFERENCE_UNAVAILABLE, str(exc)))
            await self._finish_turn()
            return

        reply = "".join(parts)
        await self._set_state(SessionState.SPEAKING, turn_id)
        try:
            await self._speak(turn_id, reply, buffer)
        except SpeechNotConfigured as exc:
            await self.emit(error_message(ERR_SPEECH_NOT_CONFIGURED, str(exc)))
        except FrameValidationError as exc:
            await self.emit(
                error_message(
                    ERR_TURN_FAILED, f"speech produced a frame this protocol refuses: {exc}"
                )
            )
        await self._finish_turn()

    async def _speak(self, turn_id: str, reply: str, buffer: SlidingWindowBuffer) -> None:
        speech_start = self.pacer.now_ms()
        timeline_end = 0.0
        audio_seq = 0
        frames_ready = asyncio.Event()

        async def produce() -> None:
            nonlocal timeline_end, audio_seq
            async for chunk in self.speech.synthesize(reply, turn_id):
                if chunk.kind == CHUNK_FRAME:
                    weights = validate_frame(chunk.weights)
                    _check_timeline(chunk.at_ms)
                    buffer.push(chunk.at_ms, weights, chunk.priority)
                    timeline_end = max(timeline_end, chunk.at_ms)
                    frames_ready.set()
                elif chunk.kind == CHUNK_AUDIO:
                    # Audio is never buffered: it leaves the moment it exists.
                    _check_timeline(chunk.at_ms)
                    timeline_end = max(timeline_end, chunk.at_ms + chunk.audio_duration_ms)
                    if self.send_audio:
                        await self.emit(audio_message(turn_id, audio_seq, chunk.at_ms, chunk.pcm))
                        audio_seq += 1
                elif chunk.kind == CHUNK_STATE:
                    _check_timeline(chunk.at_ms)
                    timeline_end = max(timeline_end, chunk.at_ms)

        producer = asyncio.create_task(produce())
        try:
            while True:
                # Clear before draining so a frame pushed between the drain
                # and the wait still wakes the next iteration.
                frames_ready.clear()
                audio_ms = self.pacer.now_ms() - speech_start
                for frame in buffer.drain(audio_ms, self.behind_ms):
                    await self.emit(
                        frame_message(turn_id, frame.seq, frame.at_ms, frame.priority, frame.weights)
                    )
                if producer.done():
                    producer.result()
                    if len(buffer) == 0 and audio_ms >= timeline_end:
                        break
                await self._wait_for_tick(frames_ready)
        finally:
            if not producer.done():
                producer.cancel()
                await asyncio.gather(producer, return_exceptions=True)

    async def _wait_for_tick(self, frames_ready: asyncio.Event) -> None:
        """Sleep one drain interval, or less if the synthesiser pushes a frame first.

        Waking on the push is what lets the first window leave as soon as
        it exists instead of half a window later; with a real clock that
        was up to 125 ms of face behind voice at the start of every reply.
        """
        sleeper = asyncio.ensure_future(self.pacer.sleep_ms(self.drain_interval_ms))
        waiter = asyncio.ensure_future(frames_ready.wait())
        try:
            await asyncio.wait({sleeper, waiter}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for pending in (sleeper, waiter):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(sleeper, waiter, return_exceptions=True)

    async def _finish_turn(self) -> None:
        self.turns_completed += 1
        self._active_turn_id = None
        await self._emit_metrics()
        await self._set_state(SessionState.LISTENING, None)

    async def _emit_metrics(self) -> None:
        metrics = self._metrics
        buffer = self._buffer
        if metrics is None:
            return
        await self.emit(
            metrics_message(
                turn_id=metrics.turn_id,
                provider=metrics.provider,
                fell_back=metrics.fell_back,
                ttft_ms=metrics.ttft_ms,
                breaker=self.router.breaker.state.value,
                frames_sent=buffer.sent if buffer is not None else 0,
                frames_dropped=buffer.dropped_total if buffer is not None else 0,
                tokens=metrics.tokens,
            )
        )

    async def _cancel_inflight(self) -> int:
        """Cancel the turn task, wait for it, flush the buffer. Returns frames flushed."""
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait({task})
        self._task = None
        self._active_turn_id = None
        if self._buffer is not None:
            return self._buffer.flush()
        return 0

    async def interrupt(self, turn_id: str, at_ms: Optional[float]) -> Dict[str, Any]:
        """Stop the named turn if it is the one in flight. Always acks."""
        received = time.perf_counter()
        flushed = 0
        cancelled = False
        if self.in_flight and turn_id == self._active_turn_id:
            flushed = await self._cancel_inflight()
            cancelled = True
            self.turns_interrupted += 1
        self.state = SessionState.LISTENING
        self.turn_id = None
        latency_ms = (time.perf_counter() - received) * 1000.0
        self.last_interrupt_client_at_ms = at_ms
        ack = interrupt_ack_message(turn_id, flushed, latency_ms)
        await self.emit(ack)
        await self.emit(state_message(self.state.value, None))
        if cancelled:
            await self._emit_metrics()
        return ack
