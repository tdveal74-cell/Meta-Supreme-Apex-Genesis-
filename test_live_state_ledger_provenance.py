"""The hash chain and the signed receipt against a real PostgreSQL 16 database.

The pure laws are proved in ``test_devon_provenance.py``. These prove the
writer applies them on every row it writes, that the receipt binds to the chain
head and verifies under the receipt key, and that the invariants migration 019
gave the database hold even for a caller that goes around the writer:

* an event or a receipt cannot be rewritten in place (BEFORE UPDATE trigger),
* an event, a receipt or an intent cannot be deleted except inside the cascade
  from its owner (BEFORE DELETE triggers, ENABLE ALWAYS), and
* a rewrite that does get past a trigger is named by the verifier, not hidden.

The negative controls disable a trigger for one statement, which only the
table owner can do, and re-enable it before the test ends. That is the model
CLAUDE.md asks for: a fix without a negative control is not proven.
"""

from __future__ import annotations

import pathlib
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
    # Signed under the receipt key, which is derived from SECRET_KEY when no
    # dedicated key is set, and is never SECRET_KEY itself.
    receipt_key = provenance.derive_receipt_key(settings.SECRET_KEY)
    assert issued["signature_key_id"] == provenance.key_id(receipt_key)
    assert provenance.verify_signature(issued["digest"], issued["signature"], receipt_key)

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
    assert any("verifies under none of the keys" in f for f in payload["receipt"]["findings"])


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


# ---------------------------------------------------------------------------
# What the 2026-09-08 gauntlet added. Each of these was a confirmed finding.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    [-0.0, 1e16, 1e21, 1.2345678901234567e19, 1.5e300, 1e-7, 0.1, 100.0, 12345678901234567890123],
)
async def test_numbers_hash_the_way_the_database_stores_them(db_session, value):
    """Python renders 1e16 as 1e+16 and JSONB renders it as 10000000000000000.
    The first cut hashed Python's rendering and every such event read as
    altered on verification. The writer now hashes what the database stores."""
    owner_id = await _owner(db_session)
    opened = await ledger.open_intent(
        db_session, owner_id=owner_id, channel="chat_voice", stated="numbers"
    )
    intent_id = opened["intent_id"]
    await ledger.append_event(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        name="CONTEXT_LOADED",
        payload={"v": value, "nested": {"list": [value, {"again": value}]}},
    )
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is True, payload["chain"]["findings"]
    assert payload["chain"]["complete"] is True
    # The stored payload is what the writer hashed, and it round trips again.
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="PLAN_CREATED"
    )
    again = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert again["chain"]["intact"] is True


async def test_a_payload_json_cannot_carry_is_refused_before_the_insert(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, [])
    for bad in ({"v": float("nan")}, {"v": float("inf")}, {"text": "lone \udcff surrogate"}):
        with pytest.raises(LedgerRefused) as caught:
            await ledger.append_event(
                db_session,
                owner_id=owner_id,
                intent_id=intent_id,
                name="CONTEXT_LOADED",
                payload=bad,
            )
        assert any("payload carries" in reason for reason in caught.value.reasons)
    # Nothing was written: the intent still holds only its opening event.
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert [event["name"] for event in read["events"]] == ["INTENT_RECEIVED"]


async def test_a_nan_payload_over_http_is_a_refusal_not_a_500(client, auth_headers):
    opened = await client.post(
        "/api/v1/ledger/intents",
        json={"channel": "chat_voice", "stated": "nan over http"},
        headers=auth_headers,
    )
    intent_id = opened.json()["intent_id"]
    # json.loads at the API door accepts NaN; the ledger must refuse it by name.
    response = await client.post(
        f"/api/v1/ledger/intents/{intent_id}/events",
        content='{"name": "CONTEXT_LOADED", "payload": {"x": NaN}}',
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 409, response.text
    assert "cannot represent" in response.text


async def test_the_database_refuses_a_direct_delete_of_an_event_or_a_receipt(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("DELETE FROM events WHERE intent_id = :i AND sequence_no >= 4"),
            {"i": intent_id},
        )
    assert "may not be deleted" in str(caught.value)
    # The refusal aborted the transaction, and the rollback that clears it
    # also takes the uncommitted intent and receipt with it. Build them again
    # so the second DELETE has a row to aim at; a DELETE that matches nothing
    # fires no trigger and would pass this test for the wrong reason.
    await db_session.rollback()
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("DELETE FROM universal_receipts WHERE intent_id = :i"), {"i": intent_id}
        )
    assert "may not be deleted" in str(caught.value)
    await db_session.rollback()


async def test_removing_the_owner_still_cascades(db_session):
    """An owner's right to be removed outranks the audit trail: the cascade
    from users is admitted through intents, events and receipts. A statement
    aimed at any of those three tables is refused (proved separately)."""
    owner_id = await _owner(db_session)
    first = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, first)
    second = await _open_and_walk(db_session, owner_id, ["CONTEXT_LOADED"])

    await db_session.execute(text("DELETE FROM users WHERE id = :o"), {"o": owner_id})
    for intent_id in (first, second):
        intents = await db_session.execute(
            text("SELECT COUNT(*) FROM intents WHERE id = :i"), {"i": intent_id}
        )
        assert intents.scalar_one() == 0
        left = await db_session.execute(
            text("SELECT COUNT(*) FROM events WHERE intent_id = :i"), {"i": intent_id}
        )
        assert left.scalar_one() == 0
    receipts = await db_session.execute(
        text("SELECT COUNT(*) FROM universal_receipts WHERE intent_id = :i"), {"i": first}
    )
    assert receipts.scalar_one() == 0


async def test_a_tail_deleted_behind_the_trigger_is_named_and_cannot_be_appended_to(db_session):
    """Negative control for the DELETE trigger: disable it, remove the tail
    and the receipt, and the receipt's head no longer exists. Verification
    reports the receipt as gone, and the chain that remains is still intact
    only because it is a prefix; a receipt certifying the missing head can
    no longer be produced by the writer since one receipt per intent already
    stood (the row is gone, so a new one is possible, and that is the
    residual exposure a role that disables triggers has by definition)."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    issued = await _receipt(db_session, owner_id, intent_id)

    await db_session.execute(text("ALTER TABLE events DISABLE TRIGGER trg_events_no_delete"))
    try:
        await db_session.execute(
            text("DELETE FROM events WHERE intent_id = :i AND sequence_no >= 4"),
            {"i": intent_id},
        )
    finally:
        await db_session.execute(text("ALTER TABLE events ENABLE TRIGGER trg_events_no_delete"))

    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["verified"] is False
    assert payload["receipt"]["head_hash"] == issued["head_hash"]
    assert any("after the receipt was issued" in f for f in payload["receipt"]["findings"])
    assert any("certifies 5 events" in f for f in payload["receipt"]["findings"])


async def test_an_unhashed_row_planted_after_hashed_rows_is_a_break_and_blocks_appends(db_session):
    """The second gauntlet finding: an INSERT with an empty hash used to read
    as pre-chain history and the next append linked to genesis behind it."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, ["CONTEXT_LOADED"])
    await db_session.execute(
        text(
            "INSERT INTO events (intent_id, owner_id, name, sequence_no, payload, hash, prev_hash) "
            "VALUES (:i, :o, 'PLAN_CREATED', 3, '{}'::jsonb, '', '')"
        ),
        {"i": intent_id, "o": owner_id},
    )
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is False
    assert any("written around the writer" in f for f in payload["chain"]["findings"])

    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session, owner_id=owner_id, intent_id=intent_id, name="ACTION_STARTED"
        )
    assert any("nothing can be appended" in reason for reason in caught.value.reasons)


async def test_an_intent_without_a_receipt_is_not_verified(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["chain"]["intact"] is True
    assert payload["receipted"] is False
    assert payload["verified"] is False
    assert payload["receipt"]["present"] is False
    assert any("no receipt" in f for f in payload["receipt"]["findings"])


async def test_receipts_are_signed_under_a_key_that_is_not_the_jwt_key(db_session, monkeypatch):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEY", "")
    issued = await _receipt(db_session, owner_id, intent_id)
    assert issued["signature_key_id"] != provenance.key_id(settings.SECRET_KEY)
    assert issued["signature_key_id"] == provenance.key_id(
        provenance.derive_receipt_key(settings.SECRET_KEY)
    )
    assert not provenance.verify_signature(issued["digest"], issued["signature"], settings.SECRET_KEY)


async def test_a_rotated_key_still_verifies_through_the_ring(db_session, monkeypatch):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    old_key = "receipt-key-of-last-quarter-0123456789abcdef0123456789"
    new_key = "receipt-key-of-this-quarter-0123456789abcdef0123456789"

    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEY", old_key)
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", "")
    issued = await _receipt(db_session, owner_id, intent_id)
    assert issued["signature_key_id"] == provenance.key_id(old_key)

    # Rotate: the new key signs, the old one stays in the ring.
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEY", new_key)
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", f" {old_key} ,")
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["verified"] is True
    assert payload["receipt"]["verified"] is True
    assert payload["receipt"]["signed_with_current_key"] is False
    assert payload["receipt"]["verified_with_key_id"] == provenance.key_id(old_key)

    # Drop the old key from the ring and the receipt no longer verifies, by name.
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", "")
    payload = await ledger.verify_provenance(
        db_session, owner_id=owner_id, intent_id=intent_id
    )
    assert payload["verified"] is False
    assert any("not in the ring" in f for f in payload["receipt"]["findings"])


# ---------------------------------------------------------------------------
# What the second gauntlet pass added (2026-09-08).
# ---------------------------------------------------------------------------

async def test_a_nul_in_a_payload_is_refused_at_the_door(db_session):
    """jsonb refuses a NUL escape at the cast, mid transaction, which was a
    500. The door refuses it first, by name, and nothing is written."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, [])
    with pytest.raises(LedgerRefused) as caught:
        await ledger.append_event(
            db_session,
            owner_id=owner_id,
            intent_id=intent_id,
            name="CONTEXT_LOADED",
            payload={"k": "a\u0000b"},
        )
    assert any("NUL" in reason for reason in caught.value.reasons)
    # The transaction is still usable: the refusal happened before any SQL.
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert len(read["events"]) == 1


async def test_a_nul_over_http_is_a_409(client, auth_headers):
    opened = await client.post(
        "/api/v1/ledger/intents",
        json={"channel": "chat_voice", "stated": "nul over http"},
        headers=auth_headers,
    )
    intent_id = opened.json()["intent_id"]
    response = await client.post(
        f"/api/v1/ledger/intents/{intent_id}/events",
        json={"name": "CONTEXT_LOADED", "payload": {"k": "a\u0000b"}},
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert "NUL" in response.text


async def test_the_database_refuses_a_direct_delete_of_an_intent(db_session):
    """The parent row: deleting it, re-inserting its id and replaying a
    different history read as verified in the second pass."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(text("DELETE FROM intents WHERE id = :i"), {"i": intent_id})
    assert "intents" in str(caught.value) and "may not be deleted" in str(caught.value)
    await db_session.rollback()


async def test_replica_mode_does_not_silence_the_ledger_triggers(db_session):
    """session_replication_role = replica disables ordinary triggers. Every
    ledger trigger is ENABLE ALWAYS, so it still fires there. Only a
    superuser can set the role at all, and the test runs as one."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await db_session.execute(text("SET LOCAL session_replication_role = replica"))
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("UPDATE events SET payload = '{}'::jsonb WHERE intent_id = :i"),
            {"i": intent_id},
        )
    assert "append only" in str(caught.value)
    await db_session.rollback()
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await db_session.execute(text("SET LOCAL session_replication_role = replica"))
    with pytest.raises(DBAPIError) as caught:
        await db_session.execute(
            text("DELETE FROM events WHERE intent_id = :i"), {"i": intent_id}
        )
    assert "may not be deleted" in str(caught.value)
    await db_session.rollback()


async def test_a_pre_chain_prefix_is_receipted_on_trust_not_on_proof(db_session):
    """An intent whose first rows predate the chain can still be receipted,
    but the verifier says the prefix is unproved rather than calling the
    whole thing verified: it cannot tell pre 019 history from rows planted
    to look like it."""
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
            text("ALTER TABLE events ENABLE ALWAYS TRIGGER trg_events_append_only")
        )
    for name in WALK:
        await ledger.append_event(db_session, owner_id=owner_id, intent_id=intent_id, name=name)
    await _receipt(db_session, owner_id, intent_id)
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["chain"]["intact"] is True
    assert payload["chain"]["complete"] is False
    assert payload["chain"]["unhashed"] == 1
    assert payload["receipt"]["verified"] is True
    assert payload["verified"] is False
    assert any("on trust" in f for f in payload["receipt"]["findings"])


async def test_moving_from_the_derived_key_to_a_dedicated_one_keeps_old_receipts(
    db_session, monkeypatch
):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEY", "")
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", "")
    issued = await _receipt(db_session, owner_id, intent_id)

    monkeypatch.setattr(
        settings, "RECEIPT_SIGNING_KEY", "a-dedicated-key-0123456789abcdef0123456789abcdef"
    )
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True
    assert payload["receipt"]["signed_with_current_key"] is False
    assert payload["receipt"]["verified_with_key_id"] == issued["signature_key_id"]


async def test_a_rotated_secret_verifies_through_a_secret_entry_in_the_ring(
    db_session, monkeypatch
):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    old_secret = "an-old-estate-secret-0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(settings, "SECRET_KEY", old_secret)
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEY", "")
    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", "")
    await _receipt(db_session, owner_id, intent_id)

    monkeypatch.setattr(
        settings, "SECRET_KEY", "a-new-estate-secret-0123456789abcdef0123456789abcdef"
    )
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is False

    monkeypatch.setattr(settings, "RECEIPT_SIGNING_KEYS_PREVIOUS", f"secret:{old_secret}")
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True
    assert payload["receipt"]["verified_with_key_id"] == provenance.key_id(
        provenance.derive_receipt_key(old_secret)
    )


ROLE_SQL = (
    pathlib.Path(__file__).parent / "infrastructure" / "docker" / "initdb" / "sql" / "api-role.sql"
)


async def test_the_runtime_role_from_the_compose_stack_cannot_rewrite_history(db_session):
    """The production compose connects the API as devon_api, created by
    initdb/sql/api-role.sql. Run that file against the test database and
    prove the role's limits: it can write the ledger and cannot create a
    table, truncate one, disable a trigger, enter replica mode, or delete
    an event, a receipt or an intent directly."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)

    await _become_devon_api(db_session)

    # DML works: the role can append through the writer.
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=intent_id, name="VERIFICATION_PASSED"
    )

    refusals = {
        "create table": "CREATE TABLE scratch_for_a_trigger (id int)",
        "truncate": "TRUNCATE events",
        "disable trigger": "ALTER TABLE events DISABLE TRIGGER trg_events_no_delete",
        "replica mode": "SET session_replication_role = replica",
        "delete event": f"DELETE FROM events WHERE intent_id = '{intent_id}'",
        "delete receipt": f"DELETE FROM universal_receipts WHERE intent_id = '{intent_id}'",
        "delete intent": f"DELETE FROM intents WHERE id = '{intent_id}'",
    }
    for label, statement in refusals.items():
        await db_session.execute(text("SAVEPOINT probe"))
        with pytest.raises(DBAPIError):
            await db_session.execute(text(statement))
        await db_session.execute(text("ROLLBACK TO SAVEPOINT probe"))
        assert label
    await db_session.execute(text("RESET ROLE"))
    await db_session.rollback()


# ---------------------------------------------------------------------------
# What the third gauntlet pass added (2026-09-08).
# ---------------------------------------------------------------------------

GRANTS_SQL = pathlib.Path(__file__).parent / "database" / "grants" / "devon_api.sql"


def _sql_statements(script: str) -> list[str]:
    """Split a script into statements, dropping comment lines and keeping a
    dollar quoted body whole."""
    lines = [line for line in script.splitlines() if not line.strip().startswith("--")]
    statements: list[str] = []
    buffer: list[str] = []
    in_body = False
    for line in lines:
        buffer.append(line)
        if line.count("$$") == 1:
            in_body = not in_body
        if line.rstrip().endswith(";") and not in_body:
            statements.append("\n".join(buffer).strip())
            buffer = []
    return [statement for statement in statements if statement]


async def _become_devon_api(db) -> None:
    """Run the role script and the grants file the way the compose stack
    does (role at init, grants after migration), then take the role."""
    role_script = (
        ROLE_SQL.read_text(encoding="utf-8")
        .replace(":'api_password'", "'role-test-password'")
        .replace(':"target_database"', '"meta_supreme_test"')
    )
    grants_script = GRANTS_SQL.read_text(encoding="utf-8").replace(':"owner_role"', '"postgres"')
    # The SQL built test database has no alembic_version; production does,
    # and the grants file guards it. Give the test the table so the guard's
    # branch runs and the probe below has something to be refused on.
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
    )
    for statement in _sql_statements(role_script) + _sql_statements(grants_script):
        await db.execute(text(statement))
    await db.execute(text("SET LOCAL ROLE devon_api"))
    assert (await db.execute(text("SELECT current_user"))).scalar_one() == "devon_api"


async def _refused(db, statement: str) -> str:
    await db.execute(text("SAVEPOINT probe"))
    with pytest.raises(DBAPIError) as caught:
        await db.execute(text(statement))
    await db.execute(text("ROLLBACK TO SAVEPOINT probe"))
    return str(caught.value)


async def test_the_runtime_role_cannot_make_a_temporary_table_or_a_function_of_its_own(db_session):
    """The third pass deleted a receipted history through a temporary table's
    trigger: TEMP is granted to PUBLIC by default, and the delete fired at
    trigger depth 2 was admitted. TEMP is revoked from PUBLIC and the
    delete guard no longer asks about depth at all."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    await _become_devon_api(db_session)

    assert "permission denied" in await _refused(db_session, "CREATE TEMP TABLE zz (id int)")
    assert "permission denied" in await _refused(
        db_session,
        "CREATE FUNCTION pg_temp.wipe() RETURNS trigger AS $f$ BEGIN RETURN OLD; END $f$ LANGUAGE plpgsql",
    )
    await db_session.execute(text("RESET ROLE"))
    await db_session.rollback()


async def test_a_trigger_that_deletes_at_depth_two_is_refused_while_the_parent_stands(db_session):
    """Negative control for the guard itself, as the owner: build the exact
    scratch table and trigger the third pass used, and fire it. The events
    and receipt triggers now ask whether the intent is gone, not how deep
    the call stack is, so the delete is refused and the chain stands."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    issued = await _receipt(db_session, owner_id, intent_id)

    await db_session.execute(text("CREATE TEMP TABLE zz_probe (id int)"))
    await db_session.execute(
        text(
            "CREATE FUNCTION pg_temp.zz_wipe() RETURNS trigger AS $f$ BEGIN "
            f"DELETE FROM events WHERE intent_id = '{intent_id}' AND sequence_no > 4; "
            f"DELETE FROM universal_receipts WHERE intent_id = '{intent_id}'; "
            "RETURN OLD; END $f$ LANGUAGE plpgsql"
        )
    )
    await db_session.execute(
        text("CREATE TRIGGER zz_fire BEFORE DELETE ON zz_probe FOR EACH ROW EXECUTE FUNCTION pg_temp.zz_wipe()")
    )
    await db_session.execute(text("INSERT INTO zz_probe VALUES (1)"))
    refusal = await _refused(db_session, "DELETE FROM zz_probe")
    assert "may not be deleted" in refusal

    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True
    assert payload["chain"]["length"] == 5
    assert payload["receipt"]["head_hash"] == issued["head_hash"]
    await db_session.rollback()


async def test_the_runtime_role_cannot_delete_users_but_can_delete_what_the_app_deletes(db_session):
    """The owner cascade is the one door through the ledger's guards, and
    the runtime role is not allowed through it: no DELETE on users. Where
    the application does delete (a workflow and its runs), the role can."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    workflow_id = str(uuid.uuid4())
    await db_session.execute(
        text(
            "INSERT INTO workflows (id, owner_id, name, definition) "
            "VALUES (:w, :o, 'probe', '{}'::jsonb)"
        ),
        {"w": workflow_id, "o": owner_id},
    )
    await _become_devon_api(db_session)

    assert "permission denied" in await _refused(
        db_session, f"DELETE FROM users WHERE id = '{owner_id}'"
    )
    assert "permission denied" in await _refused(
        db_session, "UPDATE alembic_version SET version_num = '000_bogus'"
    )
    await db_session.execute(text("DELETE FROM workflows WHERE id = :w"), {"w": workflow_id})
    left = await db_session.execute(
        text("SELECT COUNT(*) FROM workflows WHERE id = :w"), {"w": workflow_id}
    )
    assert left.scalar_one() == 0

    # And the chain it could not touch still verifies.
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True
    await db_session.execute(text("RESET ROLE"))
    await db_session.rollback()


async def test_an_intent_row_may_move_its_state_and_nothing_else(db_session):
    owner_id = await _owner(db_session)
    thief = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    for column, value in (
        ("owner_id", f"'{thief}'"),
        ("stated", "'something else'"),
        ("channel", "'email'"),
        ("is_effect", "TRUE"),
        ("created_at", "NOW()"),
    ):
        refusal = await _refused(
            db_session, f"UPDATE intents SET {column} = {value} WHERE id = '{intent_id}'"
        )
        assert "may only move its state" in refusal, column
    # The writer's own moves are admitted.
    await db_session.execute(
        text("UPDATE intents SET state = 'failed', updated_at = NOW() WHERE id = :i"),
        {"i": intent_id},
    )
    await db_session.rollback()


async def test_a_handed_over_or_reworded_intent_is_named_by_the_verifier(db_session):
    """Negative control behind the intents trigger: disable it, hand the row
    to another owner, and the opening event's hash no longer matches the
    row. The thief's read of the chain is not verified, and says why."""
    owner_id = await _owner(db_session)
    thief = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)

    await db_session.execute(text("ALTER TABLE intents DISABLE TRIGGER trg_intents_state_only"))
    try:
        await db_session.execute(
            text("UPDATE intents SET owner_id = :t, stated = 'x' WHERE id = :i"),
            {"t": thief, "i": intent_id},
        )
    finally:
        await db_session.execute(
            text("ALTER TABLE intents ENABLE ALWAYS TRIGGER trg_intents_state_only")
        )

    payload = await ledger.verify_provenance(db_session, owner_id=thief, intent_id=intent_id)
    assert payload["verified"] is False
    assert payload["chain"]["intact"] is False
    assert any("different owner" in f for f in payload["chain"]["findings"])
    assert any("reworded" in f for f in payload["chain"]["findings"])


async def test_the_written_out_escape_for_nul_is_ordinary_text(db_session):
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id, [])
    await ledger.append_event(
        db_session,
        owner_id=owner_id,
        intent_id=intent_id,
        name="CONTEXT_LOADED",
        payload={"k": "the six characters backslash u 0 0 0 0: \\u0000"},
    )
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["chain"]["intact"] is True


# ---------------------------------------------------------------------------
# What the fourth gauntlet pass added (2026-09-08).
# ---------------------------------------------------------------------------


async def test_a_row_on_another_owners_intent_leaves_with_its_own_owner(db_session):
    """An event carries its own owner as well as its intent, and both foreign
    keys cascade. The fourth pass planted a row owned by B on A's intent and
    found that B could no longer be deleted: the guard asked about the intent
    only. It now admits the delete when either parent is gone, and still
    refuses the row while both stand."""
    owner_id = await _owner(db_session)
    other = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    issued = await _receipt(db_session, owner_id, intent_id)
    await db_session.execute(
        text(
            "INSERT INTO events (intent_id, owner_id, name, sequence_no, payload) "
            "VALUES (:i, :o, 'CONTEXT_LOADED', 99, '{}'::jsonb)"
        ),
        {"i": intent_id, "o": other},
    )
    # Planted, the row is named: an unhashed row after hashed ones.
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is False
    # Aimed at directly, it is refused while its intent and its owner stand.
    refusal = await _refused(
        db_session, f"DELETE FROM events WHERE intent_id = '{intent_id}' AND sequence_no = 99"
    )
    assert "may not be deleted" in refusal
    # Its own owner's removal takes it, and A's chain is whole again.
    await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": other})
    left = await db_session.execute(
        text("SELECT COUNT(*) FROM events WHERE intent_id = :i AND sequence_no = 99"),
        {"i": intent_id},
    )
    assert left.scalar_one() == 0
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True
    assert payload["chain"]["length"] == 5
    assert payload["receipt"]["head_hash"] == issued["head_hash"]
    await db_session.rollback()


async def test_a_rerouted_intent_or_a_flipped_effect_flag_is_named_by_the_verifier(db_session):
    """Negative control behind the intents trigger: the channel and the effect
    flag are hashed in the opening event, so a change to either behind the
    trigger is named rather than read on trust."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    await _receipt(db_session, owner_id, intent_id)
    await db_session.execute(text("ALTER TABLE intents DISABLE TRIGGER trg_intents_state_only"))
    try:
        await db_session.execute(
            text("UPDATE intents SET channel = 'email', is_effect = TRUE WHERE id = :i"),
            {"i": intent_id},
        )
    finally:
        await db_session.execute(
            text("ALTER TABLE intents ENABLE ALWAYS TRIGGER trg_intents_state_only")
        )
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is False
    assert payload["chain"]["intact"] is False
    assert any("rerouted" in f for f in payload["chain"]["findings"])
    assert any("effect flag" in f for f in payload["chain"]["findings"])
    await db_session.rollback()


async def test_a_state_moved_by_hand_is_named_by_the_verifier(db_session):
    """The trigger admits a state move because the writer makes them. A state
    the events do not derive is a hand on the row, from any role with
    UPDATE, and the verifier says so. The writer's own moves still verify."""
    owner_id = await _owner(db_session)
    intent_id = await _open_and_walk(db_session, owner_id)
    read = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    assert read["intent"]["state"] == "completed"
    await _receipt(db_session, owner_id, intent_id)
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is True

    await db_session.execute(
        text("UPDATE intents SET state = 'received' WHERE id = :i"), {"i": intent_id}
    )
    payload = await ledger.verify_provenance(db_session, owner_id=owner_id, intent_id=intent_id)
    assert payload["verified"] is False
    assert any(
        "'received'" in f and "'receipted'" in f and "moved by hand" in f
        for f in payload["chain"]["findings"]
    )
