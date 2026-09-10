"""What a schedule runner is allowed to say about a batch it just ran.

Pure: no session, no database, no clock beyond the values the caller hands in.
It is a module of its own for the same reason
apps/web/components/mind/learning-honesty.ts is, so the property below can be
proved by a check that needs nothing but an interpreter.

THE PROPERTY THIS FILE EXISTS FOR

"Could not read the schedule store" and "read it and nothing was due" are two
different answers, and collapsing the first into the second is the estate's
single most repeated defect. A cron lane makes it worse than a panel does,
because nobody is looking: a runner that logs "nothing due" every minute while
its scan raises every minute reads exactly like a quiet, healthy estate.

So:

* ``created_total`` and ``owners_scanned`` are Optional and are ``None``
  whenever the batch did not get far enough to measure them. There is no number
  in that case and 0 would be an invented one.
* ``state`` names the six outcomes a batch can actually have, and
  ``nothing_due`` is reachable only from an enumeration that succeeded and
  returned no owner.
* ``summary()`` never says "nothing due" unless nothing was due, and always
  carries the failure reason when there is one.

An OwnerOutcome is checked on construction rather than trusted, because the one
mistake that would defeat all of the above is a failed owner recorded as a
success with a count of zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

#: Another runner held the lock. Nothing was read and nothing was attempted.
STATE_LOCKED_OUT = "locked_out"
#: The owner enumeration itself failed. What is due is unknown.
STATE_SCAN_FAILED = "scan_failed"
#: The enumeration succeeded and no owner had a due schedule.
STATE_NOTHING_DUE = "nothing_due"
#: Every enumerated owner was materialized without error.
STATE_COMPLETE = "complete"
#: Some owners materialized, some failed. The failed owners' goals are unread.
STATE_PARTIAL = "partial"
#: Owners were due and every one of them failed.
STATE_ALL_FAILED = "all_failed"

#: The closed set. A check asserts every state a report can produce is in here,
#: so a seventh state cannot be added without the vocabulary admitting it.
STATES = frozenset(
    {
        STATE_LOCKED_OUT,
        STATE_SCAN_FAILED,
        STATE_NOTHING_DUE,
        STATE_COMPLETE,
        STATE_PARTIAL,
        STATE_ALL_FAILED,
    }
)

#: States in which no count was measured, so no count may be reported.
UNMEASURED_STATES = frozenset({STATE_LOCKED_OUT, STATE_SCAN_FAILED})


@dataclass(frozen=True)
class OwnerOutcome:
    """One owner's half of a batch: either a count, or a reason there is none.

    Exactly one of the two. A success carries ``created`` and an empty
    ``error``; a failure carries ``error`` and no ``created``, because a failed
    materialization rolled back and its due schedules are unread rather than
    empty. Both at once, or neither, is refused here instead of being rendered
    later.
    """

    owner_id: str
    created: Optional[int] = None
    error: str = ""
    #: Set when a failed owner's due rows were pushed forward so the next tick
    #: does not re-plan them immediately. Meaningless on a success, and refused
    #: there, because a successful owner has nothing to defer.
    deferred_until: str = ""

    def __post_init__(self) -> None:
        if not str(self.owner_id).strip():
            raise ValueError("an owner outcome with no owner is not an outcome")
        reason = (self.error or "").strip()
        if reason and self.created is not None:
            raise ValueError(
                f"owner {self.owner_id} carries both a failure reason and a created "
                f"count of {self.created}; a rolled back owner created nothing and "
                "its due schedules are unread, so the count must be absent"
            )
        if not reason and self.created is None:
            raise ValueError(
                f"owner {self.owner_id} carries neither a created count nor a "
                "failure reason, so nothing can be said about it truthfully"
            )
        if self.created is not None and self.created < 0:
            raise ValueError(f"owner {self.owner_id} created a negative count")
        if self.deferred_until.strip() and not reason:
            raise ValueError(
                f"owner {self.owner_id} succeeded and carries a deferral. A "
                "deferral is what a FAILURE does to stop the next tick re-planning "
                "the same rows; on a success there is nothing to defer"
            )

    @property
    def ok(self) -> bool:
        return not (self.error or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"owner_id": self.owner_id, "ok": self.ok}
        # Absent rather than zero. A consumer that reads `created` off a failed
        # owner should find nothing there, not a number it can add up.
        if self.created is not None:
            payload["created"] = self.created
        if not self.ok:
            payload["error"] = self.error
            # Absent rather than empty, so a reader can tell "deferred to T" from
            # "the deferral itself did not land", which is the state that spins.
            if self.deferred_until.strip():
                payload["deferred_until"] = self.deferred_until.strip()
        return payload


@dataclass(frozen=True)
class ScheduleRunReport:
    """One batch. Immutable, so a summary cannot drift from what was measured.

    THAT SENTENCE WAS FALSE UNTIL 2026-09-10 and an adversary demonstrated it in
    three lines: ``frozen=True`` blocks attribute rebinding only, so
    ``report.outcomes.append(OwnerOutcome(owner_id="b", error="boom"))`` moved a
    report from ``complete``/healthy to ``partial``/unhealthy with a different
    summary. ``__post_init__`` now replaces the list with a tuple through
    ``object.__setattr__``, which is what a frozen dataclass has to do to freeze
    a container, and a check appends to it and asserts the state does not move.
    """

    outcomes: Sequence[OwnerOutcome] = field(default_factory=tuple)
    locked_out: bool = False
    scan_error: str = ""

    def __post_init__(self) -> None:
        # Callers pass a list, which is convenient and mutable. Freeze it here so
        # the docstring above is true rather than aspirational. A tuple also makes
        # a later append raise instead of silently changing the verdict.
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        if self.locked_out and (self.outcomes or self.scan_error.strip()):
            raise ValueError(
                "a locked out batch attempted nothing, so it cannot carry owner "
                "outcomes or a scan error"
            )
        if self.scan_error.strip() and self.outcomes:
            raise ValueError(
                "the owner enumeration failed, so there is no list of owners to "
                "have outcomes for"
            )
        # A blank-but-set scan_error degraded to the comfortable lie: `state`
        # tests `scan_error.strip()`, so scan_error="   " reported nothing_due
        # and healthy True over a scan that had failed. That is precisely the
        # collapse this module exists to refuse, and OwnerOutcome already refuses
        # its own version of it. Not reachable from the current runner, whose
        # _reason() always returns a non-empty string, so this is the hole being
        # closed rather than a live defect.
        if self.scan_error and not self.scan_error.strip():
            raise ValueError(
                "the scan error is set and blank, so the batch would report "
                "nothing_due and healthy over a scan that failed. Give the reason "
                "or do not set it"
            )

    @property
    def succeeded(self) -> List[OwnerOutcome]:
        return [item for item in self.outcomes if item.ok]

    @property
    def failed(self) -> List[OwnerOutcome]:
        return [item for item in self.outcomes if not item.ok]

    @property
    def unresolved_owners(self) -> List[str]:
        """Owners whose due schedules this batch did not manage to read."""
        return [item.owner_id for item in self.failed]

    @property
    def spinning_owners(self) -> List[str]:
        """Failed owners whose rows were NOT pushed forward.

        These are the ones the next tick will re-plan immediately, spending the
        planner again on the same rows. Named separately from
        ``unresolved_owners`` because a deferred failure costs one planner call
        per backoff window and an undeferred one costs one per tick.
        """
        return [
            item.owner_id
            for item in self.failed
            if not item.deferred_until.strip()
        ]

    @property
    def owners_scanned(self) -> Optional[int]:
        """How many owners had a due schedule, or None when that is unknown."""
        if self.state in UNMEASURED_STATES:
            return None
        return len(self.outcomes)

    @property
    def created_total(self) -> Optional[int]:
        """Tasks this batch materialized, or None when nothing was measured.

        Zero is a real answer for a batch that ran and found every due schedule
        already attached to a task. It is not a real answer for a batch that
        never read the store, which is why those states return None.
        """
        if self.state in UNMEASURED_STATES:
            return None
        return sum(item.created or 0 for item in self.succeeded)

    @property
    def state(self) -> str:
        if self.locked_out:
            return STATE_LOCKED_OUT
        if self.scan_error.strip():
            return STATE_SCAN_FAILED
        if not self.outcomes:
            return STATE_NOTHING_DUE
        if not self.failed:
            return STATE_COMPLETE
        if not self.succeeded:
            return STATE_ALL_FAILED
        return STATE_PARTIAL

    @property
    def healthy(self) -> bool:
        """True only when this batch knows it left nothing unread.

        The cron wrapper reads this. ``locked_out`` counts as healthy because
        another runner is doing the work; ``scan_failed`` never does.
        """
        return self.state in {
            STATE_LOCKED_OUT,
            STATE_NOTHING_DUE,
            STATE_COMPLETE,
        }

    def summary(self) -> str:
        state = self.state
        if state == STATE_LOCKED_OUT:
            return (
                "another agent schedule runner holds the lock; nothing read and "
                "nothing materialized"
            )
        if state == STATE_SCAN_FAILED:
            return (
                "the due schedule scan failed, so what is due is unknown and no "
                f"count is reported: {self.scan_error.strip()}"
            )
        if state == STATE_NOTHING_DUE:
            return "no owner has a due schedule; nothing to materialize"
        created = self.created_total
        if state == STATE_COMPLETE:
            return (
                f"{len(self.outcomes)} owner(s) with due schedules, "
                f"{created} task(s) materialized"
            )
        names = ", ".join(self.unresolved_owners)
        if state == STATE_ALL_FAILED:
            return (
                f"{len(self.outcomes)} owner(s) had due schedules and every one "
                f"failed, so none of their goals were read: {names}"
                f"{self._spin_note()}"
            )
        return (
            f"{len(self.succeeded)} of {len(self.outcomes)} owner(s) materialized "
            f"{created} task(s); {len(self.failed)} failed and their due schedules "
            f"are unread: {names}{self._spin_note()}"
        )

    def _spin_note(self) -> str:
        """Named in the log line, because it is the difference between a costed
        failure and an unbounded one."""
        spinning = self.spinning_owners
        if not spinning:
            return ""
        return (
            f" (NOT deferred, so the next tick re-plans the same rows: "
            f"{', '.join(spinning)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "state": self.state,
            "healthy": self.healthy,
            "summary": self.summary(),
        }
        # ABSENT, not empty, in the unmeasured states. On a failed scan the old
        # payload carried `owners: []` and `unresolved_owners: []`, so a
        # dashboard reading only the second key concluded that no owner had been
        # left unread when in truth EVERY owner had and the count is unknown.
        # Same rule the two counts below already followed.
        if self.state not in UNMEASURED_STATES:
            payload["owners"] = [item.to_dict() for item in self.outcomes]
            payload["unresolved_owners"] = self.unresolved_owners
            if self.spinning_owners:
                payload["spinning_owners"] = self.spinning_owners
        # Same rule as OwnerOutcome: an unmeasured count is absent, never 0.
        if self.owners_scanned is not None:
            payload["owners_scanned"] = self.owners_scanned
        if self.created_total is not None:
            payload["created_total"] = self.created_total
        if self.scan_error.strip():
            payload["scan_error"] = self.scan_error.strip()
        return payload
