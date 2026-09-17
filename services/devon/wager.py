"""
The wager: a prediction made before the measurement, and the miss carried
forward.

Upstream: the AI Impact teardown Tee handed over on 2026-09-17, which found the
pattern in `github.com/starmynd-org/infinite-brain-os` and rated it real while
rating the demo numbers around it illustration dressed as evidence. The loop is
worth having. The numbers he published for it are not, and this module holds
none of them.

WHY THIS IS CODE AND NOT A DOCUMENT

The first law in `CLAUDE.md` already says a fix is not fixed until it is re
measured: reproduce the failure, apply the change, show the same measurement
clean. That closes the loop on whether a change worked. It says nothing about
whether the person making the change knew in advance what it would do, and
those are different questions with different failure modes.

A measurement taken after the fact can be read to fit whatever happened. A
number written down before the run cannot. The gap between the two is the only
honest signal about how well this operation understands its own systems, and
right now nothing anywhere records it.

The teardown paid for that in its own build plan, and said so: nobody knows the
render lane's cycle time from Queued to Ready, the author included, so every
budget in the plan is a guess with no way to tell later how bad a guess it was.
A wager makes the guess a record.

WHAT THIS REFUSES

A baseline with no receipt, because a prediction measured against a remembered
number measures nothing. A settlement with no receipt, for the same reason in
the other direction. A verdict on a wager that has not been settled, because an
open wager is a plan, not evidence, and the one thing a prediction must never
do is get quoted as a result.

THE LINE

This module records and arithmetic. It never decides that a change worked. The
gate a delta has to clear is the caller's, and Tee's.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

SOURCES = {
    "upstream": "AI Impact teardown and level up blueprint, handed over 2026-09-17",
    "pattern": "the wager, read in github.com/starmynd-org/infinite-brain-os",
    "law": "CLAUDE.md first law, a fix is not fixed until it is re measured",
    "read": "2026-09-17",
}


class WagerError(ValueError):
    """Raised when a wager is asked to be evidence it is not."""


@dataclass(frozen=True)
class Measurement:
    """A number and where it came from. One without the other is not a number."""

    value: float
    receipt: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise WagerError(f"measurement value {self.value!r} is not a number")
        if not self.receipt.strip():
            raise WagerError(
                f"measurement of {self.value} carries no receipt. Name the execution "
                "id, the command, the query or the log line it was read from. A "
                "number with no receipt is a memory, and memories are what the first "
                "law exists to stop."
            )


@dataclass(frozen=True)
class Wager:
    """One prediction, its baseline, and its outcome once it has one."""

    subject: str
    metric: str
    baseline: Measurement
    predicted: float
    rationale: str = ""
    outcome: Optional[Measurement] = None

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise WagerError("a wager with no subject cannot be found again")
        if not self.metric.strip():
            raise WagerError(
                f"wager on '{self.subject}' names no metric. 'It will be better' is "
                "not a prediction, because nothing can later show it wrong."
            )
        if not isinstance(self.predicted, (int, float)) or isinstance(self.predicted, bool):
            raise WagerError(f"predicted value {self.predicted!r} is not a number")

    @property
    def settled(self) -> bool:
        return self.outcome is not None

    @property
    def predicted_delta(self) -> float:
        """What the change was expected to move. Known before the run."""
        return float(self.predicted) - float(self.baseline.value)

    def settle(self, outcome: Measurement) -> "Wager":
        """Record what actually happened. Returns the settled wager.

        Settling twice is refused. A second settlement is either a different run,
        which is a different wager, or a number being revised after it was read,
        which is the thing this whole module is against.
        """
        if self.settled:
            raise WagerError(
                f"wager on '{self.subject}' is already settled at "
                f"{self.outcome.value}. Raise a new wager for a new run rather than "
                "revising a recorded outcome."
            )
        if not isinstance(outcome, Measurement):
            raise WagerError("settle takes a Measurement, so the outcome carries its receipt")
        return replace(self, outcome=outcome)

    def _require_settled(self) -> Measurement:
        if self.outcome is None:
            raise WagerError(
                f"wager on '{self.subject}' is open. An open wager is a plan and "
                "cannot be read as a result."
            )
        return self.outcome

    @property
    def actual_delta(self) -> float:
        return float(self._require_settled().value) - float(self.baseline.value)

    @property
    def miss(self) -> float:
        """Signed: positive when reality came in above the prediction."""
        return float(self._require_settled().value) - float(self.predicted)

    @property
    def absolute_miss(self) -> float:
        return abs(self.miss)

    @property
    def direction_held(self) -> bool:
        """Whether the change moved the way it was predicted to move.

        Worth separating from the size of the miss. Predicting a 20 point gain
        and getting 5 is a bad estimate of a real effect. Predicting a 20 point
        gain and getting minus 3 is a wrong theory, and only one of the two is
        a reason to stop.
        """
        predicted, actual = self.predicted_delta, self.actual_delta
        if predicted == 0:
            return actual == 0
        return (predicted > 0) == (actual > 0) and actual != 0

    def within(self, tolerance: float) -> bool:
        if tolerance < 0:
            raise WagerError("tolerance cannot be negative")
        return self.absolute_miss <= tolerance

    def render(self) -> str:
        lines = [
            f"WAGER: {self.subject}",
            f"  metric: {self.metric}",
            f"  baseline: {self.baseline.value} ({self.baseline.receipt})",
            f"  predicted: {self.predicted} (delta {self.predicted_delta:+g})",
        ]
        if self.rationale.strip():
            lines.append(f"  because: {self.rationale.strip()}")
        if self.outcome is None:
            lines.append("  outcome: OPEN. Not evidence until it is settled.")
            return "\n".join(lines)
        lines.append(f"  actual: {self.outcome.value} ({self.outcome.receipt})")
        lines.append(f"  delta: {self.actual_delta:+g}")
        lines.append(f"  miss: {self.miss:+g}")
        lines.append(
            "  direction: " + ("held" if self.direction_held else "WRONG WAY")
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class Calibration:
    """What the settled wagers on a metric say about the estimates themselves."""

    metric: Optional[str]
    count: int
    bias: float
    mean_absolute_miss: float
    direction_hits: int

    @property
    def direction_rate(self) -> float:
        return self.direction_hits / self.count if self.count else 0.0

    def render(self) -> str:
        scope = self.metric or "all metrics"
        return (
            f"CALIBRATION ({scope}): {self.count} settled, "
            f"bias {self.bias:+g}, mean absolute miss {self.mean_absolute_miss:g}, "
            f"direction held {self.direction_hits} of {self.count}"
        )


@dataclass(frozen=True)
class Adjustment:
    """A new prediction, and whether the record was able to inform it."""

    raw: float
    adjusted: float
    applied: bool
    reason: str

    def render(self) -> str:
        if not self.applied:
            return f"{self.raw:g} unadjusted: {self.reason}"
        return f"{self.raw:g} adjusted to {self.adjusted:g}: {self.reason}"


@dataclass
class WagerBook:
    """The wagers made, so the next prediction can be made against the last miss."""

    wagers: List[Wager] = field(default_factory=list)

    def add(self, wager: Wager) -> Wager:
        self.wagers.append(wager)
        return wager

    def settled(self, metric: Optional[str] = None) -> Tuple[Wager, ...]:
        return tuple(
            w
            for w in self.wagers
            if w.settled and (metric is None or w.metric == metric)
        )

    def open(self, metric: Optional[str] = None) -> Tuple[Wager, ...]:
        return tuple(
            w
            for w in self.wagers
            if not w.settled and (metric is None or w.metric == metric)
        )

    def calibration(self, metric: Optional[str] = None) -> Optional[Calibration]:
        """None when nothing is settled, rather than a zero that reads as calibrated.

        A bias of 0.0 over no data and a bias of 0.0 over forty settled wagers
        print the same and mean opposite things. Returning None makes the caller
        handle the difference.
        """
        settled = self.settled(metric)
        if not settled:
            return None
        misses = [w.miss for w in settled]
        return Calibration(
            metric=metric,
            count=len(settled),
            bias=sum(misses) / len(misses),
            mean_absolute_miss=sum(abs(m) for m in misses) / len(misses),
            direction_hits=sum(1 for w in settled if w.direction_held),
        )

    def adjust(self, raw: float, metric: str) -> Adjustment:
        """Carry the miss forward, which is the whole point of keeping the book.

        If this operation has consistently come in five points under its own
        predictions on a metric, the next prediction on that metric starts five
        points lower. When there is no record to carry, the prediction is handed
        back untouched and the reason says so rather than implying a correction
        was applied.
        """
        calibration = self.calibration(metric)
        if calibration is None:
            return Adjustment(
                raw=raw,
                adjusted=raw,
                applied=False,
                reason=(
                    f"no settled wager on '{metric}', so there is no measured bias to "
                    "correct by. This prediction is the first, and it is a guess."
                ),
            )
        return Adjustment(
            raw=raw,
            adjusted=raw + calibration.bias,
            applied=True,
            reason=(
                f"{calibration.count} settled wager(s) on '{metric}' ran "
                f"{calibration.bias:+g} against prediction on average"
            ),
        )

    def render(self) -> str:
        lines: List[str] = []
        counts: Dict[str, int] = {}
        for wager in self.wagers:
            counts[wager.metric] = counts.get(wager.metric, 0) + 1
        lines.append(
            f"BOOK: {len(self.wagers)} wager(s), {len(self.settled())} settled, "
            f"{len(self.open())} open"
        )
        for metric in sorted(counts):
            calibration = self.calibration(metric)
            lines.append(
                "  " + (calibration.render() if calibration else f"CALIBRATION ({metric}): none settled")
            )
        return "\n".join(lines)


def open_wager(
    subject: str,
    metric: str,
    baseline: float,
    baseline_receipt: str,
    predicted: float,
    rationale: str = "",
) -> Wager:
    """Convenience constructor that still forces the baseline's receipt through."""
    return Wager(
        subject=subject,
        metric=metric,
        baseline=Measurement(value=baseline, receipt=baseline_receipt),
        predicted=predicted,
        rationale=rationale,
    )
