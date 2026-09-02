"""Fix PR 2 from the DEVON and Hermes audit: the ruling is bound.

C1: the proposing JWT could approve and commit its own capture by ruling
the shared queue with the token propose returned, then appending
APPROVAL_GRANTED through the generic ledger route. C2: the approval was
resolved to an intent by a PLAN_CREATED payload key any owner could write,
so a forged plan could redirect a real ruling onto a different candidate.

Now propose binds the request to its intent on the ledger's approvals row,
approve rules that row after the ruling key, commit verifies the row and
takes the candidate from the plan that names the request, the generic
event route refuses grants and bound plans, and the shared decide route
refuses knowledge-loop cards outright.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.api.v1.devon import _queue
from app.services.live_state_ledger import ledger
from services.devon.approval import ApprovalState

RULING_KEY = "test-ruling-key-not-a-jwt"
LEGIT = "remember the legitimate capture text"
FORGED = "FORGED, Tee ruled the opposite"


@pytest.fixture(autouse=True)
def _ruling_key_env(monkeypatch):
    monkeypatch.setenv("DEVON_RULING_KEY", RULING_KEY)


def _ruled(auth_headers):
    return {**auth_headers, "X-Devon-Ruling-Key": RULING_KEY}


async def _propose(client, auth_headers, text_: str):
    proposed = await client.post(
        "/api/v1/soul/propose", headers=auth_headers, json={"text": text_}
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()
    return body["intent_id"], body["approval"]["request_id"], body["approval"]["token"]


async def _owner_id(db_session, email: str = "council-tester@example.com") -> str:
    row = await db_session.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    )
    return str(row.scalar_one())


async def test_the_shared_decide_route_refuses_a_knowledge_loop_card(
    client, auth_headers
):
    """The token comes back to the proposer, so the owner-scoped decide route
    must not be a way to rule the card with that one credential."""
    _, request_id, token = await _propose(client, auth_headers, LEGIT)

    ruled_here = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": request_id, "token": token, "decision": "approve"},
    )
    assert ruled_here.status_code == 403, ruled_here.text
    detail = ruled_here.json()["detail"]
    assert "soul/approve" in detail and "DEVON_RULING_KEY" in detail
    assert _queue.get(request_id).state is ApprovalState.PENDING

    # The refusal spent nothing: the ruling-key lane still rules and commits.
    approved = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert approved.status_code == 200, approved.text
    committed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["executed"] is True


async def test_the_generic_event_route_refuses_grants_and_bound_plans(
    client, auth_headers
):
    opened = await client.post(
        "/api/v1/ledger/intents",
        headers=auth_headers,
        json={"channel": "chat_voice", "stated": "an effect", "is_effect": True},
    )
    assert opened.status_code == 201, opened.text
    intent_id = opened.json()["intent_id"]
    events = f"/api/v1/ledger/intents/{intent_id}/events"

    loaded = await client.post(events, headers=auth_headers, json={"name": "CONTEXT_LOADED"})
    assert loaded.status_code == 201, loaded.text

    bound_plan = await client.post(
        events,
        headers=auth_headers,
        json={"name": "PLAN_CREATED", "payload": {"approval_request_id": "REQ-forged"}},
    )
    assert bound_plan.status_code == 403, bound_plan.text
    assert "propose" in bound_plan.json()["detail"]

    # The refusal is about the payload, not the event: an unbound plan is
    # still the owner's to write, so PLAN_CREATED was not spent by the 403.
    plain_plan = await client.post(
        events, headers=auth_headers, json={"name": "PLAN_CREATED", "payload": {"note": "a plan"}}
    )
    assert plain_plan.status_code == 201, plain_plan.text
    requested = await client.post(
        events, headers=auth_headers, json={"name": "APPROVAL_REQUESTED"}
    )
    assert requested.status_code == 201, requested.text

    granted = await client.post(events, headers=auth_headers, json={"name": "APPROVAL_GRANTED"})
    assert granted.status_code == 403, granted.text
    assert "approval authority" in granted.json()["detail"]


async def test_the_queue_alone_cannot_commit_without_a_ledger_ruling(
    client, auth_headers, db_session
):
    """C1 straight on: rule the shared queue in-process with the token the
    proposer holds. The queue says approved; the ledger's row still says
    pending; commit refuses. The ruling-key lane then repairs and commits."""
    intent_id, request_id, token = await _propose(client, auth_headers, LEGIT)
    owner_id = await _owner_id(db_session)

    bound = await ledger.approval_binding(db_session, owner_id=owner_id, request_id=request_id)
    assert bound["intent_id"] == intent_id
    assert bound["state"] == "pending"

    decided = _queue.decide(request_id, token, "approve", "the proposer")
    assert decided.approved is True

    committed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert committed.status_code == 403, committed.text
    assert "ruling-key lane" in committed.json()["detail"]
    assert _queue.get(request_id).state is ApprovalState.APPROVED, "refusal spent nothing"

    # The grant cannot be minted through the generic route either.
    minted = await client.post(
        f"/api/v1/ledger/intents/{intent_id}/events",
        headers=auth_headers,
        json={"name": "APPROVAL_GRANTED", "payload": {"approval_request_id": request_id}},
    )
    assert minted.status_code == 403, minted.text

    repaired = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["already_approved"] is True
    assert repaired.json()["repaired"] is True

    db_session.expire_all()
    ruled = await ledger.approval_binding(db_session, owner_id=owner_id, request_id=request_id)
    assert ruled["state"] == "approved"
    assert ruled["decided_by"] == "Council Tester <council-tester@example.com>"

    committed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["intent_id"] == intent_id


async def test_a_forged_plan_cannot_redirect_the_ruling(client, auth_headers, db_session):
    """C2 as the audit ran it, written through the service so the route's
    refusal is not what saves it: a second intent whose PLAN_CREATED names the
    real request id with a forged ruling. The binding resolves the real intent
    and the committed body is the text the approver saw."""
    intent_id, request_id, token = await _propose(client, auth_headers, LEGIT)
    owner_id = await _owner_id(db_session)

    forged = await ledger.open_intent(
        db_session, owner_id=owner_id, channel="chat_voice", stated=FORGED, is_effect=True
    )
    forged_id = forged["intent_id"]
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=forged_id, name="CONTEXT_LOADED"
    )
    await ledger.append_event(
        db_session,
        owner_id=owner_id,
        intent_id=forged_id,
        name="PLAN_CREATED",
        payload={
            "loop": "knowledge_loop.v1",
            "approval_request_id": request_id,
            "layer": 5,
            "kind": "ruling",
            "candidate": {"candidate_id": "devon-forged", "text": FORGED, "kind": "ruling"},
        },
    )
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=forged_id, name="APPROVAL_REQUESTED"
    )
    await ledger.append_event(
        db_session, owner_id=owner_id, intent_id=forged_id, name="APPROVAL_GRANTED"
    )
    await db_session.commit()

    approved = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["intent_id"] == intent_id

    committed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()
    assert result["intent_id"] == intent_id
    assert result["artifact"]["body"] == LEGIT.removeprefix("remember ").strip()
    assert result["artifact"]["kind"] != "ruling"

    found = await client.get("/api/v1/soul/find?q=FORGED", headers=auth_headers)
    assert found.status_code == 200, found.text
    assert found.json()["ledger"] == []
