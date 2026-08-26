"""The Live State Ledger against a real PostgreSQL 16 database.

The pure laws are proved in ``test_devon_ecosystem.py``. These prove the writer
actually applies them, and that the two invariants the database owns hold even
when a caller tries to go around the checker:

* one receipt per intent (unique constraint), and
* only the thirteen universal events, each at one position.

Every test that mutates uses the shared ``db_session`` fixture, so rows are
truncated between tests by ``conftest``.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.services.live_state_ledger import LedgerConflict, LedgerRefused, ledger
from services.devon import ecosystem


async def _owner(db) -> str:
    """A user row to own the ledger records under test."""
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, full_name, is_active) "
            "VALUES (:id, :email, 'x', 'Ledger Test', TRUE)"
        ),
        {"id": owner_id, "email": f"ledger-{owner_id}@example.com"},
    )
    await db.flush()
    return owner_id


async def _open(db, owner_id: str, *, is_effect: bool = False) -> str:
    opened = await ledger.open_intent(
        db,
        owner_id=owner_id,
        channel="chat_voice",
        stated="do the thing",
        is_effect=is_effect,
    )
    return opened["intent_id"]


async def _walk(db, owner_id: str, intent_id: str, names) -> None:
    for name in names:
        await ledger.append_event(
            db, owner_id=owner_id, intent_id=intent_id, name=name
        )


async def test_opening_an_intent_mints_a_uuid_and_writes_the_first_event(db_session):
    owner_id = await _owner(db_session)
    opened = await ledger.open_intent(
        db_session, owner_id=owner_id, channel="Chat/Voice", stated="remember this"
    )
    uuid.UUID(opened["intent_id"])
    assert opened["channel"] == "chat_voice"
    assert opened["state"] == "received"

    read = await ledger.read_intent(
        db_session, owner_id=owner_id, intent_id=opened["intent_id"]
    )
    assert [event["name"] for event in read["events"]] == ["INTENT_RECEIVED"]
    assert read["events"][0]["sequence_no"] == 1


async def test_an_unrecorded_channel_is_refused_before_anything_is_written(db_session):
    owner_id = await _owner(db_session)
    with pytest.raises(ValueError, match="not a recorded input channel"):
        await ledger.open_intent(
            db_session, owner_id=owner_id, channel="smoke signal", stated="hello"
        )
    count = await db_session.execute(
        text("SELECT COUNT(*) FROM intents WHERE owner_id = :o"), {"o": owner_id}
    )
    assert count.scalar_one() == 0


async def test_events_append_in_order_and_the_state_follows_them(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)

    await _walk(db_session, owner_id, intent_id, ["CONTEXT_LOADED", "PLAN_CREATED"])
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert read["intent"]["state"] == "planned"

    await _walk(db_session, owner_id, intent_id, ["ACTION_STARTED", "ACTION_COMPLETED"])
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert read["intent"]["state"] == "completed"
    assert [event["sequence_no"] for event in read["events"]] == [1, 2, 3, 4, 5]


async def test_an_out_of_order_event_is_refused_with_its_reason(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_COMPLETED"
        )
    assert any("ACTION_STARTED" in reason for reason in caught.value.reasons)


async def test_an_event_outside_the_thirteen_is_refused(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="SOMETHING_ELSE"
        )
    assert any("thirteen" in reason for reason in caught.value.reasons)


async def test_the_database_itself_rejects_an_event_outside_the_thirteen(db_session):
    """The check constraint holds even for a caller that never touches the writer."""
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO events (intent_id, owner_id, name, sequence_no) "
                "VALUES (:i, :o, 'NOT_AN_EVENT', 99)"
            ),
            {"i": intent_id, "o": owner_id},
        )
        await db_session.flush()


async def test_an_effect_action_cannot_start_without_an_approval_on_the_record(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id, is_effect=True)
    await _walk(db_session, owner_id, intent_id, ["CONTEXT_LOADED", "PLAN_CREATED"])

    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
        )
    assert any("unattended" in reason for reason in caught.value.reasons)

    await _walk(
        db_session, owner_id, intent_id, ["APPROVAL_REQUESTED", "APPROVAL_GRANTED"]
    )
    started = await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
    )
    assert started["event"] == "ACTION_STARTED"


async def test_the_emergency_stop_refuses_a_start_and_only_tee_releases_it(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    await _walk(db_session, owner_id, intent_id, ["CONTEXT_LOADED", "PLAN_CREATED"])

    await ledger.engage_emergency_stop(
        db_session, owner_id=owner_id, reason="a bad deploy is running", changed_by="tee"
    )
    assert await ledger.emergency_stopped(db_session, owner_id=owner_id)

    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
        )
    assert any("Emergency stop is engaged" in reason for reason in caught.value.reasons)

    with pytest.raises(LedgerRefused):
        await ledger.release_emergency_stop(
            db_session,
            owner_id=owner_id,
            actor=ecosystem.Authority.AUTOMATION,
            changed_by="a worker",
        )
    assert await ledger.emergency_stopped(db_session, owner_id=owner_id)

    await ledger.release_emergency_stop(
        db_session, owner_id=owner_id, actor=ecosystem.Authority.TEE, changed_by="tee"
    )
    assert not await ledger.emergency_stopped(db_session, owner_id=owner_id)
    resumed = await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
    )
    assert resumed["event"] == "ACTION_STARTED"


async def test_an_action_routes_to_an_executor_and_an_unknown_duty_parks(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)

    internal = await ledger.plan_action(
        db_session, owner_id=owner_id, intent_id=intent_id, duty="devon workflows"
    )
    assert internal["executor"] == "n8n"

    external = await ledger.plan_action(
        db_session, owner_id=owner_id, intent_id=intent_id, duty="crm"
    )
    assert external["executor"] == "zapier"

    parked = await ledger.plan_action(
        db_session, owner_id=owner_id, intent_id=intent_id, duty="teleport the thing"
    )
    assert parked["executor"] == "UNROUTED"
    assert "not a recorded duty" in parked["routing_reason"]


async def test_the_executor_registry_ships_seeded(db_session):
    rows = await db_session.execute(text("SELECT name FROM executors ORDER BY name"))
    assert [row[0] for row in rows.all()] == ["n8n", "zapier"]


async def test_one_receipt_per_intent_and_a_second_is_refused(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    await _walk(
        db_session,
        owner_id,
        intent_id,
        ["CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"],
    )

    issued = await ledger.issue_receipt(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        what_happened="filed the capture",
        verification="read the row back",
        provenance="ledger writer",
    )
    assert issued["state"] == "receipted"

    with pytest.raises(LedgerRefused) as caught:
        await ledger.issue_receipt(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            what_happened="filed it again",
            verification="read it again",
            provenance="ledger writer",
        )
    assert any("already holds its one receipt" in reason for reason in caught.value.reasons)


async def test_the_database_itself_refuses_a_second_receipt(db_session):
    """The unique constraint holds for a caller that bypasses the writer."""
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    await _walk(
        db_session,
        owner_id,
        intent_id,
        ["CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"],
    )
    await ledger.issue_receipt(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        what_happened="did it",
        verification="read it back",
        provenance="writer",
    )
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO universal_receipts "
                "(id, intent_id, owner_id, what_happened, verification, provenance) "
                "VALUES ('RCP-DUP', :i, :o, 'again', 'again', 'again')"
            ),
            {"i": intent_id, "o": owner_id},
        )
        await db_session.flush()


async def test_an_intent_that_reached_nothing_cannot_be_receipted(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(LedgerRefused) as caught:
        await ledger.issue_receipt(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            what_happened="nothing yet",
            verification="none",
            provenance="writer",
        )
    assert any("terminal event" in reason for reason in caught.value.reasons)


async def test_a_receipt_without_verification_is_refused(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    await _walk(
        db_session,
        owner_id,
        intent_id,
        ["CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"],
    )
    with pytest.raises(LedgerRefused) as caught:
        await ledger.issue_receipt(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            what_happened="did it",
            verification="   ",
            provenance="writer",
        )
    assert any("claim, not a receipt" in reason for reason in caught.value.reasons)


async def test_a_verification_without_evidence_is_refused(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(LedgerRefused) as caught:
        await ledger.record_verification(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            method="read back",
            passed=True,
            evidence="  ",
        )
    assert any("no evidence is a claim" in reason for reason in caught.value.reasons)


async def test_the_ledger_records_an_approval_but_never_grants_one(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id, is_effect=True)
    recorded = await ledger.record_approval(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        approval_request_id="REQ-1",
        state="approved",
        what_happens="sends the message",
        decided_by="tee",
    )
    assert recorded["state"] == "approved"

    # Recording the ruling does not put APPROVAL_GRANTED on the event log, so an
    # effect action still cannot start until the event is appended in order.
    await _walk(db_session, owner_id, intent_id, ["CONTEXT_LOADED", "PLAN_CREATED"])
    with pytest.raises(LedgerRefused):
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
        )


async def test_the_same_approval_request_cannot_be_recorded_twice(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    await ledger.record_approval(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        approval_request_id="REQ-UNIQUE",
        state="pending",
        what_happens="does the thing",
    )
    with pytest.raises(LedgerConflict):
        await ledger.record_approval(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            approval_request_id="REQ-UNIQUE",
            state="approved",
            what_happens="does the thing",
        )


async def test_an_approval_with_no_stated_consequence_is_refused(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)
    with pytest.raises(LedgerRefused) as caught:
        await ledger.record_approval(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            approval_request_id="REQ-EMPTY",
            state="pending",
            what_happens="   ",
        )
    assert any("consented to" in reason for reason in caught.value.reasons)


async def test_artifacts_errors_and_learning_candidates_hang_off_the_intent(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id)

    await ledger.record_artifact(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        path="docs/devon/thing.md",
        sha256="a" * 64,
    )
    await ledger.record_error(
        db_session, owner_id=owner_id, intent_id=intent_id, message="it broke"
    )
    candidate = await ledger.record_learning_candidate(
        db_session, owner_id=owner_id, intent_id=intent_id, summary="do it earlier next time"
    )
    assert candidate["status"] == "candidate"

    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert read["artifacts"][0]["path"] == "docs/devon/thing.md"

    errors = await db_session.execute(
        text("SELECT message FROM errors WHERE intent_id = :i"), {"i": intent_id}
    )
    assert errors.scalar_one() == "it broke"


async def test_another_owners_intent_is_not_readable_or_writable(db_session):
    first = await _owner(db_session)
    second = await _owner(db_session)
    intent_id = await _open(db_session, first)

    with pytest.raises(LedgerRefused):
        await ledger.read_intent(db_session, owner_id=second, intent_id=intent_id)
    with pytest.raises(LedgerRefused):
        await ledger.append_event(
            db_session, owner_id=second, intent_id=intent_id, name="CONTEXT_LOADED"
        )


async def test_read_intent_reports_what_may_legally_happen_next(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open(db_session, owner_id, is_effect=True)
    await _walk(db_session, owner_id, intent_id, ["CONTEXT_LOADED", "PLAN_CREATED"])
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert "ACTION_STARTED" not in read["next_legal_events"]
    assert "APPROVAL_REQUESTED" in read["next_legal_events"]
    assert not read["receiptable"]
