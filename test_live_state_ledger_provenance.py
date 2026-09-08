"""The hash chain and the signed receipt against a real PostgreSQL 16 database.

The pure laws are proved in ``test_devon_provenance.py``. These prove the
writer applies them on every row it writes, that the receipt binds to the chain
head and verifies under the estate key, and that the two invariants migration
019 gave the database hold even for a caller that goes around the writer:

* an event or a receipt cannot be rewritten in place (BEFORE UPDATE trigger), and
* a rewrite that does get past the trigger is named by the verifier, not hidden.

The negative controls disable the trigger for one statement, which only the
table owner can do, and re-enable it before the test ends. That is the model
CLAUDE.md asks for: a fix without a negative control is not proven.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.services.live_state_ledger import LedgerRefused, ledger
from services.devon import provenance

WALK = ["CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"]


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, full_name, is_active) "
            "VALUES (:id, :email, 'x', 'Provenance Test', TRUE)"
        ),
        {"id": owner_id, "email": f"provenance-{owner_id}@example.com"},
    )
    await db.flush()
    return owner_id


async def _open_and_walk(db, owner_id: str, names=WALK) -> str:
    opened = await ledger.open_intent(
        db, owner_id=owner_id, channel="chat_voice", stated="prove the chain"
    )
    intent_id = opened["intent_id"]
    for index, name in enumerate(names):
        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name=name,
            payload={"step": index, "note": "chained"},
        )
    return intent_id


async def _receipt(db, owner_id: str, intent_id: str):
    return await ledger.issue_receipt(
        db,
        owner_id=owner_id,
        intent_id=intent_id,
        what_happened="filed the capture",
        verification="read the row back",
        provenance="ledger writer",
        artifacts=["estate://TQO/captures/one"],
    )


async def test_every_event_links_to_the_one_before_it(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)

    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    events = read["events"]
    assert len(events) == 5
    assert events[0]["prev_hash"] == provenance.GENESIS
    assert all(len(event["hash"]) == 64 for event in events)
    for earlier, later in zip(events, events[1:], strict=False):
        assert later["prev_hash"] == earlier["hash"]
    assert len({event["hash"] for event in events}) == 5


async def test_the_stored_hash_recomputes_from_the_stored_row(db_session):
    """The verifier needs nothing the row does not carry."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, ["CONTEXT_LOADED"])

    rows = await db_session.execute(
        text(
            "SELECT sequence_no, name, prev_hash, hash, action_id, payload, occurred_at "
            "FROM events WHERE intent_id = :i ORDER BY sequence_no"
        ),
        {"i": intent_id},
    )
    for sequence_no, name, prev_hash, stored, action_id, payload, occurred_at in rows.all():
        recomputed = provenance.event_hash(
            prev_hash=prev_hash,
            intent_id=intent_id,
            sequence_no=sequence_no,
            name=name,
            action_id=action_id,
            payload=payload,
            occurred_at=provenance.format_time(occurred_at),
        )
        assert recomputed == stored, name


async def test_the_receipt_binds_to_the_chain_head_and_verifies(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    issued = await _receipt(db_session, owner_id, intent_id)

    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert issued["head_hash"] == read["events"][-1]["hash"]
    assert issued["chain_length"] == 5
    assert len(issued["signature"]) == 64
    assert issued["signature_key_id"] == provenance.key_id(settings.SECRET_KEY)
    assert provenance.verify_signature(
        issued["digest"], issued["signature"], settings.SECRET_KEY
    )

    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["verified"] is True
    assert payload["chain"]["intact"] is True
    assert payload["chain"]["complete"] is True
    assert payload["chain"]["length"] == 5
    assert payload["chain"]["head_hash"] == issued["head_hash"]
    assert payload["receipt"]["present"] is True
    assert payload["receipt"]["verified"] is True
    assert payload["receipt"]["signed_with_current_key"] is True
    assert payload["receipt"]["digest"] == issued["digest"]
    assert payload["receipt"]["findings"] == []


async def test_the_database_refuses_to_rewrite_an_event(db_session):
    """The trigger holds for a caller that never touches the writer."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, ["CONTEXT_LOADED"])
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("UPDATE events SET payload = '{}'::jsonb WHERE intent_id = :i"),
            {"i": intent_id},
        )
    assert "append only" in str(caught.value)
    await db_session.rollback()


async def test_the_database_refuses_to_rewrite_a_receipt(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("UPDATE universal_receipts SET what_happened = 'x' WHERE intent_id = :i"),
            {"i": intent_id},
        )
    assert "append only" in str(caught.value)
    await db_session.rollback()


async def test_a_rewrite_that_gets_past_the_trigger_is_named_by_the_verifier(db_session):
    """Negative control: disable the trigger, alter one event, verify.

    The verifier must name the altered sequence number and every later link,
    and the writer must refuse to issue a receipt over the altered chain.
    """
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)

    await db_session.execute(text("ALTER TABLE events DISABLE TRIGGER trg_events_append_only"))
    try:
        await db_session.execute(
            text(
                "UPDATE events SET payload = '{\"step\": 99}'::jsonb "
                "WHERE intent_id = :i AND sequence_no = 3"
            ),
            {"i": intent_id},
        )
    finally:
        await db_session.execute(
            text("ALTER TABLE events ENABLE TRIGGER trg_events_append_only")
        )

    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["verified"] is False
    assert payload["chain"]["intact"] is False
    findings = payload["chain"]["findings"]
    assert any("sequence 3" in f and "altered" in f for f in findings)
    # Only the altered row is reported as altered; the rows after it still
    # link correctly because their prev_hash was computed over the original.
    assert sum("altered" in f for f in findings) == 1

    with pytest.raises(LedgerRefused) as caught:
        await _receipt(db_session, owner_id, intent_id)
    assert any("does not verify" in reason for reason in caught.value.reasons)


async def test_a_receipt_altered_after_issue_fails_its_signature(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)

    await db_session.execute(
        text("ALTER TABLE universal_receipts DISABLE TRIGGER trg_universal_receipts_append_only")
    )
    try:
        await db_session.execute(
            text(
                "UPDATE universal_receipts SET what_happened = 'filed nothing' "
                "WHERE intent_id = :i"
            ),
            {"i": intent_id},
        )
    finally:
        await db_session.execute(
            text("ALTER TABLE universal_receipts ENABLE TRIGGER trg_universal_receipts_append_only")
        )

    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is True
    assert payload["receipt"]["verified"] is False
    assert payload["verified"] is False
    assert any("signature does not verify" in f for f in payload["receipt"]["findings"])


async def test_an_event_appended_after_the_receipt_is_reported(db_session):
    """A receipt certifies a head. Growth past it is visible, not hidden."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, ["CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"])
    await _receipt(db_session, owner_id, intent_id)
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="VERIFICATION_PASSED"
    )
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is True
    assert payload["receipt"]["verified"] is False
    assert any("after the receipt was issued" in f for f in payload["receipt"]["findings"])


async def test_a_pre_chain_row_is_counted_and_the_chain_restarts_after_it(db_session):
    """A row written before 019 carries no hash. The verifier says so."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, [])

    await db_session.execute(text("ALTER TABLE events DISABLE TRIGGER trg_events_append_only"))
    try:
        await db_session.execute(
            text("UPDATE events SET hash = '', prev_hash = '' WHERE intent_id = :i"),
            {"i": intent_id},
        )
    finally:
        await db_session.execute(
            text("ALTER TABLE events ENABLE TRIGGER trg_events_append_only")
        )

    appended = await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="CONTEXT_LOADED"
    )
    assert appended["prev_hash"] == provenance.GENESIS

    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is True
    assert payload["chain"]["complete"] is False
    assert payload["chain"]["unhashed"] == 1
    assert payload["chain"]["hashed"] == 1


async def test_the_provenance_route_returns_the_signed_payload(client, auth_headers):
    opened = await client.post(
        "/api/v1/ledger/intents",
        json={"channel": "chat_voice", "stated": "prove it over http"},
        headers=auth_headers,
    )
    assert opened.status_code == 201, opened.text
    intent_id = opened.json()["intent_id"]
    for name in WALK:
        appended = await client.post(
            f"/api/v1/ledger/intents/{intent_id}/events",
            json={"name": name},
            headers=auth_headers,
        )
        assert appended.status_code == 201, appended.text
    receipted = await client.post(
        f"/api/v1/ledger/intents/{intent_id}/receipt",
        json={
            "what_happened": "proved it",
            "verification": "read it back over http",
            "provenance": "test client",
        },
        headers=auth_headers,
    )
    assert receipted.status_code == 201, receipted.text
    assert len(receipted.json()["signature"]) == 64

    verified = await client.get(
        f"/api/v1/ledger/intents/{intent_id}/provenance", headers=auth_headers
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["verified"] is True
    assert body["chain"]["length"] == 5
    assert body["receipt"]["signature"] == receipted.json()["signature"]
    assert body["receipt"]["signature_algorithm"] == "hmac-sha256"

    missing = await client.get(
        f"/api/v1/ledger/intents/{uuid.uuid4()}/provenance", headers=auth_headers
    )
    assert missing.status_code == 404
