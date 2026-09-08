"""Sliding window frame buffer (system gap 1: state desynchronisation).

The face and the voice come from different clocks. Audio plays on the
client's audio clock; face frames arrive over a WebSocket and are applied
by a renderer that may stall, tab away, or simply run slower than 60 fps.
Left alone, the two drift apart: the mouth keeps moving after the voice
stops, or lags a syllable behind it.

This buffer keeps face frames on the audio timeline. Each frame carries
``at_ms``, its position in milliseconds from the start of the utterance,
and a priority. ``drain(audio_ms, behind_ms)`` hands back the frames due
within ``window_ms`` ahead of where the audio is now, so the client always
holds a short lookahead and never a long backlog.

Audio is not in this buffer at all
----------------------------------
Audio chunks are sent the moment the synthesiser produces them; nothing in
this module ever sees one. That is what makes audio real time by
construction: there is no queue in which it could wait, so the buffer
cannot delay or drop it. Only the face adapts to the audio, never the
other way round.

Compression
-----------
``behind_ms`` is the renderer's own report of how far it is behind the
audio clock. While it is within ``window_ms`` nothing is dropped. Once it
exceeds the window the backlog is shed in a fixed order, each stage in
full before the next, until the backlog fits:

1. every priority 2 frame (ambient motion), then
2. every priority 1 frame (brows, eyes, blinks), then
3. priority 0 (lip sync) thinned to every other frame, repeated while
   still over budget. Each pass keeps the first frame and the last, so
   the floor is two frames: the mouth still opens and still lands on the
   utterance's final pose rather than mid shape. Below that the audio
   plays on, untouched.

"Fits" means the queue is no longer than what the renderer can absorb:
the frames it is behind by, at ``frame_ms`` per frame, are taken off the
queue length as the budget. Counters record what went where so a session's
``metrics`` message reports real numbers, not an estimate.
"""

from __future__ import annotations

import math
from bisect import bisect_right, insort
from dataclasses import dataclass, field
from typing import Dict, List, Mapping

from apps.presence.protocol import FRAME_PRIORITIES

DEFAULT_WINDOW_MS = 250.0
DEFAULT_FRAME_MS = 1000.0 / 60.0


@dataclass
class BufferedFrame:
    """One face frame on the audio timeline."""

    seq: int
    at_ms: float
    priority: int
    weights: Dict[str, float] = field(default_factory=dict)


class SlidingWindowBuffer:
    """Frames in on the audio timeline, frames out within a lookahead window."""

    def __init__(
        self, window_ms: float = DEFAULT_WINDOW_MS, *, frame_ms: float = DEFAULT_FRAME_MS
    ) -> None:
        if window_ms <= 0:
            raise ValueError(f"window_ms must be greater than zero, got {window_ms}")
        if frame_ms <= 0:
            raise ValueError(f"frame_ms must be greater than zero, got {frame_ms}")
        self.window_ms = float(window_ms)
        self.frame_ms = float(frame_ms)
        self._frames: List[BufferedFrame] = []
        self._next_seq = 0
        self.pushed = 0
        self.sent = 0
        self.dropped_by_priority: Dict[int, int] = {priority: 0 for priority in FRAME_PRIORITIES}
        self.compressions = 0

    # -- observability ------------------------------------------------------

    def __len__(self) -> int:
        return len(self._frames)

    @property
    def dropped_total(self) -> int:
        return sum(self.dropped_by_priority.values())

    def snapshot(self) -> Dict[str, object]:
        return {
            "queued": len(self._frames),
            "pushed": self.pushed,
            "sent": self.sent,
            "dropped_by_priority": dict(self.dropped_by_priority),
            "dropped_total": self.dropped_total,
            "compressions": self.compressions,
            "window_ms": self.window_ms,
        }

    # -- producer side ------------------------------------------------------

    def push(self, at_ms: float, weights: Mapping[str, float], priority: int) -> int:
        """Queue a frame. Returns its sequence number. Order is by ``at_ms``."""
        if priority not in FRAME_PRIORITIES:
            raise ValueError(f"priority must be one of {FRAME_PRIORITIES}, got {priority!r}")
        if at_ms < 0:
            raise ValueError(f"at_ms cannot be negative, got {at_ms}")
        seq = self._next_seq
        self._next_seq += 1
        frame = BufferedFrame(seq=seq, at_ms=float(at_ms), priority=priority, weights=dict(weights))
        insort(self._frames, frame, key=lambda item: item.at_ms)
        self.pushed += 1
        return seq

    # -- consumer side ------------------------------------------------------

    def drain(self, audio_ms: float, behind_ms: float = 0.0) -> List[BufferedFrame]:
        """Frames due within ``window_ms`` ahead of ``audio_ms``, in timeline order.

        Compresses first when the renderer reports it is further behind than
        the window. Frames whose ``at_ms`` is already in the past are still
        returned: skipping them silently is how a mouth gets stuck open.
        """
        if behind_ms > self.window_ms and self._frames:
            self._compress(behind_ms)
        horizon = float(audio_ms) + self.window_ms
        count = bisect_right(self._frames, horizon, key=lambda item: item.at_ms)
        due = self._frames[:count]
        del self._frames[:count]
        self.sent += len(due)
        return due

    def flush(self) -> int:
        """Empty the queue (an interrupt). Returns how many frames were dropped."""
        dropped = len(self._frames)
        for frame in self._frames:
            self.dropped_by_priority[frame.priority] += 1
        self._frames = []
        return dropped

    # -- compression --------------------------------------------------------

    def budget_for(self, behind_ms: float) -> int:
        """How many queued frames still fit when the renderer is ``behind_ms`` behind."""
        excess_ms = max(0.0, float(behind_ms) - self.window_ms)
        shed = int(math.ceil(excess_ms / self.frame_ms))
        return max(1, len(self._frames) - shed)

    def _compress(self, behind_ms: float) -> None:
        budget = self.budget_for(behind_ms)
        if len(self._frames) <= budget:
            return
        self.compressions += 1
        self._drop_priority(2)
        if len(self._frames) <= budget:
            return
        self._drop_priority(1)
        while len(self._frames) > budget:
            before = len(self._frames)
            self._thin_priority_zero()
            if len(self._frames) == before:
                # Down to the first and last lip sync frame, or nothing left to
                # thin. That is the floor; the audio still plays, untouched.
                break

    def _drop_priority(self, priority: int) -> None:
        kept: List[BufferedFrame] = []
        for frame in self._frames:
            if frame.priority == priority:
                self.dropped_by_priority[priority] += 1
            else:
                kept.append(frame)
        self._frames = kept

    def _thin_priority_zero(self) -> None:
        """Keep every other priority 0 frame. The last one always survives."""
        zero_indexes = [i for i, frame in enumerate(self._frames) if frame.priority == 0]
        if len(zero_indexes) < 2:
            return
        last = zero_indexes[-1]
        to_drop = {index for position, index in enumerate(zero_indexes) if position % 2 == 1}
        to_drop.discard(last)
        kept: List[BufferedFrame] = []
        for i, frame in enumerate(self._frames):
            if i in to_drop:
                self.dropped_by_priority[0] += 1
            else:
                kept.append(frame)
        self._frames = kept
