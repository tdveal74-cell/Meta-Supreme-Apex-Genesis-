"""Fix PR 14 from the DEVON and Hermes audit: what the ledger's approval row says.

The Live State Ledger opened an approval row as 'pending' and moved it to
'approved' when the ruling-key lane ruled, and then never touched it again.
The knowledge loop spent the approval, the operator refused cards, the store
expired them, and the ledger row kept saying 'approved' or 'pending' forever.
The row is the authority's own record of what it did, so it disagreed with the
queue about what happened.

018 widens the check constraint to carry 'consumed', and the three settlements
now run at the three places that already know: the commit that spends, the
route that refuses, and the sweep that expires.

The same migration closes the divergence the new CI step was written to catch:
knowledge_items.content lives in the SQL build and had no Alembic counterpart,
so an Alembic-built database, which is what Railway deploys, was missing a
column every ingest path writes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services.live_state_ledger import LedgerRefused, ledger

RULING_KEY = "test-ruling-key-not-a-jwt"
LESSON = "Lesson: the row says what the authority did, not what it intended."


@pytest.fixture(autouse=True)
def _ruling_key_env(monkeypatch):
    monkeypatch.setenv("DEVON_RULING_KEY", RULING_KEY)


def _ruled(auth_headers):
    return {**auth_headers, "X-Devon-Ruling-Key": RULING_KEY}


async def _owner_id(db_session, email: str = "council-tester@example.com") -> str:
    row = await db_session.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    )
    return str(row.scalar_one())


async def _proposed(client, auth_headers, body_text: str = LESSON):
    response = await client.post(
        "/api/v1/soul/propose", headers=auth_headers, json={"text": body_text}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["intent_id"], body["approval"]["request_id"], body["approval"]["token"]


async def _approved(client, auth_headers, body_text: str = LESSON):
    intent_id, request_id, token = await _proposed(client, auth_headers, body_text)
    approved = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert approved.status_code == 200, approved.text
    return intent_id, request_id


async def _row_state(db_session, request_id: str) -> str | None:
    await db_session.commit()
    row = await db_session.execute(
        text("SELECT state FROM approvals WHERE approval_request_id = :r"),
        {"r": request_id},
    )
    value = row.scalar_one_or_none()
    return None if value is None else str(value)


async def test_the_table_accepts_the_state_the_commit_path_writes(db_session):
    """018 is applied: 'consumed' is a state the constraint allows."""
    definition = await db_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_approvals_state'"
        )
    )
    allowed = definition.scalar_one()
    for state in ("pending", "approved", "consumed", "refused", "expired"):
        assert f"'{state}'" in allowed, allowed


async def test_the_alembic_column_every_ingest_path_writes_is_present(db_session):
    """knowledge_items.content: the divergence the CI schema diff caught."""
    row = await db_session.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'knowledge_items' AND column_name = 'content'"
        )
    )
    assert row.scalar_one() == 1


async def test_a_spent_approval_reads_consumed_on_the_ledger(
    client, auth_headers, db_session
):
    intent_id, request_id = await _approved(client, auth_headers)
    assert await _row_state(db_session, request_id) == "approved"

    committed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert committed.status_code == 200, committed.text
    assert await _row_state(db_session, request_id) == "consumed"


async def test_a_refused_card_reads_refused_on_the_ledger(
    client, auth_headers, db_session
):
    _, request_id, token = await _proposed(
        client, auth_headers, "Lesson: a refusal is an outcome the ledger records."
    )
    assert await _row_state(db_session, request_id) == "pending"

    refused = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": request_id, "token": token, "decision": "refuse"},
    )
    assert refused.status_code == 200, refused.text
    assert refused.json()["ok"] is True
    assert await _row_state(db_session, request_id) == "refused"


async def test_a_settlement_that_is_not_lawful_is_refused(
    client, auth_headers, db_session
):
    """A pending row cannot jump to consumed, and a consumed row cannot go back."""
    intent_id, request_id, _token = await _proposed(
        client, auth_headers, "Lesson: the ledger refuses a transition it cannot justify."
    )
    owner_id = await _owner_id(db_session)

    with pytest.raises(LedgerRefused):
        await ledger.settle_approval(
            db_session, request_id=request_id, state="consumed", owner_id=owner_id
        )
    with pytest.raises(LedgerRefused):
        await ledger.settle_approval(
            db_session, request_id=request_id, state="promoted", owner_id=owner_id
        )
    await db_session.rollback()
    assert await _row_state(db_session, request_id) == "pending"


async def test_settling_a_request_the_ledger_never_opened_is_a_no_op(db_session):
    """Only the knowledge loop opens ledger rows; every other card has none."""
    assert (
        await ledger.settle_approval(
            db_session, request_id="req-no-such-card", state="refused"
        )
        is None
    )


async def test_settling_twice_does_not_raise(client, auth_headers, db_session):
    intent_id, request_id = await _approved(
        client, auth_headers, "Lesson: a retried settlement is not an error."
    )
    owner_id = await _owner_id(db_session)

    first = await ledger.settle_approval(
        db_session, request_id=request_id, state="consumed", owner_id=owner_id
    )
    second = await ledger.settle_approval(
        db_session, request_id=request_id, state="consumed", owner_id=owner_id
    )
    assert first is not None and first["changed"] is True
    assert second is not None and second["changed"] is False
