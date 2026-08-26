"""The kill switch: "DEVON, stop."

Presence authority buys instant action, and instant action is only safe if it
can be interrupted. Before Build 15 the runtime had no interrupt path at all --
stopping DEVON meant unpublishing a workflow, which is a rollback, not a brake.

What halting does and does not promise
--------------------------------------
A halt stops the NEXT thing. It cannot un-run what already ran: a shell command
that executed, executed, and an honest brake says so rather than implying an
undo. This is why the receipt matters more than the brake -- the receipt is what
makes an action recoverable, the brake is what stops the one after it.

So the guarantee is exactly this: once a halt is set, no further tool executes
in that turn. The check sits immediately before execution rather than at the top
of the loop, so a halt that arrives while a slow tool is running still prevents
the next one.

Halting is deliberately cheap to ask for and impossible to miss: any surface
that can reach the registry can stop a turn by id, and the turn re-checks before
every effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, Optional


class Halted(Exception):
    """Raised inside a turn when a halt was requested.

    Carries the reason so the stream can tell Tee why it stopped, and so a halt
    he asked for never looks like a crash.
    """

    def __init__(self, reason: str = "") -> None:
        self.reason = (reason or "").strip() or "stopped on request"
        super().__init__(self.reason)


@dataclass
class HaltSignal:
    """One turn's brake. Set once, stays set."""

    _halted: bool = field(default=False, repr=False)
    _reason: str = field(default="", repr=False)

    @property
    def halted(self) -> bool:
        return self._halted

    @property
    def reason(self) -> str:
        return self._reason

    def halt(self, reason: str = "") -> None:
        """Request the stop. Idempotent, and the FIRST reason is kept.

        Keeping the first reason matters: "Tee said stop" should not be
        overwritten by a later generic "turn ended", or the receipt would
        misreport who stopped it.
        """
        if self._halted:
            return
        self._halted = True
        self._reason = (reason or "").strip() or "stopped on request"

    def check(self) -> None:
        """Raise if halted. Call immediately before every effect."""
        if self._halted:
            raise Halted(self._reason)


class HaltRegistry:
    """Process-local map of turn id to brake.

    A stop arrives on a different request than the turn it stops, so the signal
    has to be reachable by id from outside the running coroutine. Locked because
    those two requests are genuinely concurrent.
    """

    def __init__(self) -> None:
        self._signals: Dict[str, HaltSignal] = {}
        self._lock = RLock()

    def open(self, turn_id: str) -> HaltSignal:
        """Register a turn and get its brake. Re-opening an id returns the same one."""
        key = (turn_id or "").strip()
        if not key:
            raise ValueError("turn id is required to open a halt signal")
        with self._lock:
            signal = self._signals.get(key)
            if signal is None:
                signal = HaltSignal()
                self._signals[key] = signal
            return signal

    def halt(self, turn_id: str, reason: str = "") -> bool:
        """Stop a turn by id. Returns False when the id is not running.

        A miss is reported rather than raised: asking a finished turn to stop is
        a normal race, not an error, and Tee saying "stop" a half second late
        should not produce a failure.
        """
        key = (turn_id or "").strip()
        with self._lock:
            signal = self._signals.get(key)
        if signal is None:
            return False
        signal.halt(reason)
        return True

    def close(self, turn_id: str) -> None:
        """Forget a finished turn. Safe to call twice."""
        with self._lock:
            self._signals.pop((turn_id or "").strip(), None)

    def is_running(self, turn_id: str) -> bool:
        with self._lock:
            return (turn_id or "").strip() in self._signals

    @property
    def running_turns(self) -> int:
        with self._lock:
            return len(self._signals)


def signal_or_open(registry: Optional[HaltRegistry], turn_id: str) -> HaltSignal:
    """Get a brake even when no registry was supplied.

    A turn run without a registry is still interruptible in principle; it simply
    has nobody to interrupt it. Returning a real signal keeps the execution path
    identical either way, so the halt check is never conditional on wiring.
    """
    if registry is None:
        return HaltSignal()
    return registry.open(turn_id)
