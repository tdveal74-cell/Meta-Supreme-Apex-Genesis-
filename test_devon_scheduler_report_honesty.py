"""A schedule runner that could not read the store may never read as idle.

WHY THIS FILE EXISTS

The agent schedule runner landed on 2026-09-10 as a cron lane, and a cron lane
is the worst place in the estate for the defect this repository repeats most: a
failed read rendered as an empty state. A panel that gets it wrong is looked at
by a person who might notice. A cron that gets it wrong logs "nothing due" every
minute while its scan raises every minute, and the estate reads as quiet and
healthy while every recorded goal rots.

So services/agent_runtime/scheduler_report.py is pure and this file is its
proof. No database, no session, no clock: the report is constructed directly and
its own vocabulary is checked, which is why these cases can run in the
standalone lane that has no cluster at all.

The load bearing assertions are the two that separate unknown from zero:
`created_total` and `owners_scanned` are None whenever the batch never measured
them, and `summary()` says "nothing due" only when the enumeration succeeded and
returned nobody.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.agent_runtime.scheduler_report import (
    STATE_ALL_FAILED,
    STATE_COMPLETE,
    STATE_LOCKED_OUT,
    STATE_NOTHING_DUE,
    STATE_PARTIAL,
    STATE_SCAN_FAILED,
    STATES,
    OwnerOutcome,
    ScheduleRunReport,
)

OWNER_A = "11111111-1111-4111-8111-111111111111"
OWNER_B = "22222222-2222-4222-8222-222222222222"


# ---------------------------------------------------------------------------
# The property this whole door is graded on
# ---------------------------------------------------------------------------


def test_a_failed_scan_is_not_an_empty_store() -> None:
    """The one that matters. Unknown and zero must not render alike."""
    broken = ScheduleRunReport(scan_error="OperationalError: connection refused")
    empty = ScheduleRunReport(outcomes=[])

    assert broken.state == STATE_SCAN_FAILED
    assert empty.state == STATE_NOTHING_DUE
    assert broken.state != empty.state

    # No number was measured, so none is reported. A 0 here is the invented
    # number the first law bans.
    assert broken.created_total is None
    assert broken.owners_scanned is None
    assert empty.created_total == 0
    assert empty.owners_scanned == 0

    assert "nothing to materialize" in empty.summary()
    assert "nothing to materialize" not in broken.summary()
    assert "unknown" in broken.summary()
    assert "connection refused" in broken.summary(), (
        "a failure that does not carry its reason forces the reader back to the "
        "logs, which for a cron lane means nobody reads it at all"
    )

    assert empty.healthy is True
    assert broken.healthy is False, (
        "the cron wrapper exits on healthy; a failed scan reading healthy is "
        "the silent failure this file exists to stop"
    )


def test_a_failed_owner_is_not_an_owner_with_nothing_due() -> None:
    partial = ScheduleRunReport(
        outcomes=[
            OwnerOutcome(owner_id=OWNER_A, created=2),
            OwnerOutcome(owner_id=OWNER_B, error="ValueError: agent goal is empty"),
        ]
    )
    assert partial.state == STATE_PARTIAL
    # Only what actually committed is counted. The failed owner's schedules were
    # rolled back unread, so they contribute no number in either direction.
    assert partial.created_total == 2
    assert partial.unresolved_owners == [OWNER_B]
    assert partial.healthy is False
    assert OWNER_B in partial.summary()
    assert "unread" in partial.summary()
    assert "nothing to materialize" not in partial.summary()


def test_every_owner_failing_is_not_a_quiet_night() -> None:
    dead = ScheduleRunReport(
        outcomes=[
            OwnerOutcome(owner_id=OWNER_A, error="ProviderSpendCapExceeded: cap"),
            OwnerOutcome(owner_id=OWNER_B, error="ProviderSpendCapExceeded: cap"),
        ]
    )
    assert dead.state == STATE_ALL_FAILED
    assert dead.healthy is False
    assert dead.created_total == 0, (
        "zero is measured here: both owners rolled back, so nothing committed"
    )
    assert sorted(dead.unresolved_owners) == sorted([OWNER_A, OWNER_B])
    assert "every one" in dead.summary()
    assert "nothing to materialize" not in dead.summary()


def test_a_locked_out_batch_reports_no_counts_at_all() -> None:
    locked = ScheduleRunReport(locked_out=True)
    assert locked.state == STATE_LOCKED_OUT
    # It never read the store, so it knows nothing about what is due. That is
    # not a failure, because another runner holds the lock and is doing the
    # work, which is why this one state is healthy with no numbers.
    assert locked.created_total is None
    assert locked.owners_scanned is None
    assert locked.healthy is True
    assert "holds the lock" in locked.summary()
    assert "nothing to materialize" not in locked.summary()


def test_a_complete_batch_says_what_it_did() -> None:
    done = ScheduleRunReport(
        outcomes=[
            OwnerOutcome(owner_id=OWNER_A, created=1),
            OwnerOutcome(owner_id=OWNER_B, created=0),
        ]
    )
    assert done.state == STATE_COMPLETE
    assert done.healthy is True
    assert done.owners_scanned == 2
    assert done.created_total == 1
    assert "2 owner(s)" in done.summary()
    assert "1 task(s)" in done.summary()


# ---------------------------------------------------------------------------
# The outcome cannot be built into a lie
# ---------------------------------------------------------------------------


def test_an_outcome_cannot_be_both_a_failure_and_a_count() -> None:
    """The exact shape a swallowed failure would take."""
    with pytest.raises(ValueError, match="must be absent"):
        OwnerOutcome(owner_id=OWNER_A, created=0, error="OperationalError: gone")


def test_an_outcome_that_says_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="neither a created count"):
        OwnerOutcome(owner_id=OWNER_A)


def test_an_outcome_needs_an_owner() -> None:
    with pytest.raises(ValueError, match="no owner"):
        OwnerOutcome(owner_id="   ", created=1)


def test_a_negative_count_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        OwnerOutcome(owner_id=OWNER_A, created=-1)


def test_a_locked_out_report_cannot_also_carry_work() -> None:
    with pytest.raises(ValueError, match="attempted nothing"):
        ScheduleRunReport(
            outcomes=[OwnerOutcome(owner_id=OWNER_A, created=1)], locked_out=True
        )


def test_a_failed_scan_cannot_also_carry_owners() -> None:
    with pytest.raises(ValueError, match="no list of owners"):
        ScheduleRunReport(
            outcomes=[OwnerOutcome(owner_id=OWNER_A, created=1)],
            scan_error="OperationalError: gone",
        )


# ---------------------------------------------------------------------------
# What a consumer serialising the report is handed
# ---------------------------------------------------------------------------


def test_an_unmeasured_count_is_absent_from_the_payload_not_zero() -> None:
    """A dict a dashboard could read one day. Absent beats a default."""
    broken = ScheduleRunReport(scan_error="OperationalError: gone").to_dict()
    assert "created_total" not in broken
    assert "owners_scanned" not in broken
    assert broken["scan_error"] == "OperationalError: gone"
    assert broken["healthy"] is False

    failed_owner = OwnerOutcome(owner_id=OWNER_A, error="boom").to_dict()
    assert "created" not in failed_owner
    assert failed_owner["ok"] is False
    assert failed_owner["error"] == "boom"

    good_owner = OwnerOutcome(owner_id=OWNER_A, created=3).to_dict()
    assert good_owner["created"] == 3
    assert "error" not in good_owner


# ---------------------------------------------------------------------------
# Anti-vacuity
# ---------------------------------------------------------------------------


def test_every_state_a_report_can_produce_is_in_the_declared_vocabulary() -> None:
    """A seventh state added without a name would slip past every case above."""
    produced = {
        ScheduleRunReport(locked_out=True).state,
        ScheduleRunReport(scan_error="x").state,
        ScheduleRunReport(outcomes=[]).state,
        ScheduleRunReport(outcomes=[OwnerOutcome(owner_id=OWNER_A, created=0)]).state,
        ScheduleRunReport(outcomes=[OwnerOutcome(owner_id=OWNER_A, error="e")]).state,
        ScheduleRunReport(
            outcomes=[
                OwnerOutcome(owner_id=OWNER_A, created=1),
                OwnerOutcome(owner_id=OWNER_B, error="e"),
            ]
        ).state,
    }
    assert produced == STATES, (
        f"the six constructions above produced {sorted(produced)} while the "
        f"declared vocabulary is {sorted(STATES)}; one of the two moved"
    )
    for state in produced:
        assert state in STATES


def test_no_summary_is_empty_and_none_of_them_are_the_same() -> None:
    reports = [
        ScheduleRunReport(locked_out=True),
        ScheduleRunReport(scan_error="OperationalError: gone"),
        ScheduleRunReport(outcomes=[]),
        ScheduleRunReport(outcomes=[OwnerOutcome(owner_id=OWNER_A, created=0)]),
        ScheduleRunReport(outcomes=[OwnerOutcome(owner_id=OWNER_A, error="e")]),
        ScheduleRunReport(
            outcomes=[
                OwnerOutcome(owner_id=OWNER_A, created=1),
                OwnerOutcome(owner_id=OWNER_B, error="e"),
            ]
        ),
    ]
    sentences = [report.summary() for report in reports]
    for sentence in sentences:
        assert len(sentence.strip()) >= 40, f"too terse to act on: {sentence!r}"
    assert len(set(sentences)) == len(sentences), (
        "two different outcomes render the same sentence, so the log cannot be "
        "used to tell them apart"
    )


# ---------------------------------------------------------------------------
# Added 2026-09-10, after an adversary read this module's own claims back to it
# ---------------------------------------------------------------------------


def test_a_blank_scan_error_is_refused_rather_than_degraded() -> None:
    """The one hole in "checked on construction rather than trusted".

    A scan_error of "   " is truthy, so it set the field, and every consumer
    tested `scan_error.strip()`, so the batch reported `nothing_due` and healthy
    True over a scan that had failed. That is the exact collapse this module
    exists to refuse, arriving through the module's own front door. OwnerOutcome
    already refused its version of it; the report did not.

    Not reachable from the runner, whose `_reason()` always returns a non-empty
    string, so this is a hole being closed rather than a live defect.
    """
    for blank in ("", "   ", "\n\t "):
        if blank == "":
            # An empty string is the genuine "no scan error" case and must stay
            # legal, or a healthy batch cannot be constructed at all.
            assert ScheduleRunReport().state == STATE_NOTHING_DUE
            continue
        with pytest.raises(ValueError) as caught:
            ScheduleRunReport(scan_error=blank)
        assert "blank" in str(caught.value)


def test_a_reports_outcomes_cannot_be_appended_to_after_construction() -> None:
    """"Immutable, so a summary cannot drift from what was measured."

    That was the class docstring and it was false. `frozen=True` blocks
    attribute rebinding only, and the default was a list, so three lines moved a
    report from complete and healthy to partial and unhealthy with a different
    summary. Measured by an adversary on 2026-09-10.
    """
    report = ScheduleRunReport(outcomes=[OwnerOutcome(owner_id=OWNER_A, created=1)])
    assert report.state == STATE_COMPLETE
    assert report.healthy is True
    before = report.summary()

    # The container itself now refuses the mutation.
    with pytest.raises(AttributeError):
        report.outcomes.append(  # type: ignore[attr-defined]
            OwnerOutcome(owner_id=OWNER_B, error="boom")
        )
    # And rebinding is still refused, which is what frozen=True was doing alone.
    with pytest.raises(FrozenInstanceError):
        report.locked_out = True  # type: ignore[misc]

    assert report.state == STATE_COMPLETE
    assert report.healthy is True
    assert report.summary() == before


def test_a_failed_scan_omits_the_owner_lists_rather_than_sending_them_empty() -> None:
    """`unresolved_owners: []` on a failed scan reads as "nobody was missed".

    In truth EVERY owner was missed and the count is unknown. The two counts
    already followed the absent-not-zero rule; the two lists did not, so a
    dashboard keyed on the list drew the comfortable conclusion.
    """
    for report in (
        ScheduleRunReport(scan_error="OperationalError: connection refused"),
        ScheduleRunReport(locked_out=True),
    ):
        payload = report.to_dict()
        assert "owners" not in payload, payload
        assert "unresolved_owners" not in payload, payload
        assert "owners_scanned" not in payload
        assert "created_total" not in payload
        # What IS there has to be enough to act on.
        assert payload["state"] in {STATE_SCAN_FAILED, STATE_LOCKED_OUT}
        assert isinstance(payload["summary"], str) and payload["summary"].strip()

    # A measured batch still carries both lists, or the omission above would be
    # hiding the answer rather than refusing to invent one.
    measured = ScheduleRunReport(
        outcomes=[
            OwnerOutcome(owner_id=OWNER_A, created=2),
            OwnerOutcome(owner_id=OWNER_B, error="IntegrityError: dup"),
        ]
    )
    payload = measured.to_dict()
    assert payload["unresolved_owners"] == [OWNER_B]
    assert len(payload["owners"]) == 2
    assert payload["created_total"] == 2
    assert payload["owners_scanned"] == 2


def test_a_deferred_failure_and_a_spinning_one_are_told_apart() -> None:
    """One costs a plan per backoff window, the other one per tick.

    A reader who cannot tell them apart cannot tell a contained failure from an
    unbounded one, which is the whole reason the field exists.
    """
    deferred = OwnerOutcome(
        owner_id=OWNER_A,
        error="IntegrityError: dup",
        deferred_until="2026-09-10T12:15:00+00:00",
    )
    spinning = OwnerOutcome(owner_id=OWNER_B, error="OperationalError: no session")

    report = ScheduleRunReport(outcomes=[deferred, spinning])
    assert report.unresolved_owners == [OWNER_A, OWNER_B]
    assert report.spinning_owners == [OWNER_B], (
        "a deferred owner is being counted as spinning, or a spinning one is not"
    )
    sentence = report.summary()
    assert "NOT deferred" in sentence, sentence
    assert OWNER_B in sentence.split("NOT deferred")[1]

    payload = report.to_dict()
    assert payload["spinning_owners"] == [OWNER_B]
    assert payload["owners"][0]["deferred_until"] == "2026-09-10T12:15:00+00:00"
    assert "deferred_until" not in payload["owners"][1], (
        "a failure with no deferral carries an empty deferral key, so a reader "
        "cannot tell it from one that landed"
    )

    # A batch with every failure deferred says nothing about spinning.
    contained = ScheduleRunReport(outcomes=[deferred])
    assert contained.spinning_owners == []
    assert "NOT deferred" not in contained.summary()

    # And a SUCCESS may not carry a deferral: there is nothing to defer.
    with pytest.raises(ValueError) as caught:
        OwnerOutcome(owner_id=OWNER_A, created=1, deferred_until="2026-09-10T12:15:00Z")
    assert "nothing to defer" in str(caught.value)
