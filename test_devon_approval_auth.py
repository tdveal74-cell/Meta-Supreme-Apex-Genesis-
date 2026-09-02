"""The approval rail belongs to an account, and registration needs an invite.

Pins the fixes for audit findings C1 (half), H1 and H15 in
docs/devon/SYS_OPS_devon-hermes-agent-audit_v1_2026-09-02.md: the three
/devon routes were unauthenticated, the queue had no owner, decided_by was
caller text, and anyone on the internet could register.
"""

from __future__ import annotations

import os

import pytest

from conftest import TEST_REGISTRATION_KEY

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


async def _account(client, email: str, name: str) -> dict:
    register = await client.post(
        REGISTER, json={"email": email, "password": "a-strong-password-123", "full_name": name}
    )
    assert register.status_code == 201, register.text
    login = await client.post(LOGIN, json={"email": email, "password": "a-strong-password-123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_devon_routes_refuse_anonymous_callers(client):
    anon = {k: v for k, v in dict(client.headers).items() if k.lower() != "authorization"}
    listed = await client.get("/api/v1/devon/approvals", headers=anon)
    assert listed.status_code == 401, listed.text
    spoken = await client.post(
        "/api/v1/devon/command", json={"text": "Devon, shut down the computer"}, headers=anon
    )
    assert spoken.status_code == 401, spoken.text
    ruled = await client.post(
        "/api/v1/devon/approvals/decide",
        json={"request_id": "REQ-NOPE", "token": "nope", "decision": "approve"},
        headers=anon,
    )
    assert ruled.status_code == 401, ruled.text


@pytest.mark.asyncio
async def test_approval_cards_are_scoped_to_the_account_that_raised_them(client, auth_headers):
    bob = await _account(client, "bob-ruler@example.com", "Bob")

    raised = await client.post(
        "/api/v1/devon/command",
        json={"text": "Devon, shut down the computer"},
        headers=auth_headers,
    )
    assert raised.status_code == 200, raised.text
    request_id = raised.json()["approval"]["request_id"]
    assert request_id

    mine = await client.get("/api/v1/devon/approvals", headers=auth_headers)
    assert request_id in {row["request_id"] for row in mine.json()["pending"]}

    theirs = await client.get("/api/v1/devon/approvals", headers=bob)
    assert request_id not in {row["request_id"] for row in theirs.json()["pending"]}

    # Bob cannot rule on it even with the id, and learns nothing about it.
    ruling = await client.post(
        "/api/v1/devon/approvals/decide",
        json={"request_id": request_id, "token": "guess", "decision": "approve"},
        headers=bob,
    )
    assert ruling.status_code == 200
    assert ruling.json()["ok"] is False
    assert ruling.json()["request_id"] == "NO_MATCH"

    still_mine = await client.get("/api/v1/devon/approvals", headers=auth_headers)
    row = next(r for r in still_mine.json()["pending"] if r["request_id"] == request_id)
    assert row["title"].startswith("shutdown")


@pytest.mark.asyncio
async def test_ruling_is_signed_by_the_login_not_the_body(client, auth_headers):
    from app.api.v1.devon import _queue

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    # /command never returns the plaintext token by design, so raise the
    # card the way an adapter does and rule with the real token.
    record, token = _queue.request(
        title="Signed-by-login probe",
        what_happens="Nothing runs. This card exists to see who signs it.",
        requested_by="test",
        owner_id=me.json()["id"],
    )
    ruling = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": record.request_id,
            "token": token,
            "decision": "refuse",
            "decided_by": "Someone Else",
        },
        headers=auth_headers,
    )
    assert ruling.status_code == 200, ruling.text
    assert ruling.json()["ok"] is True
    stored = _queue.get(record.request_id)
    assert stored is not None
    assert stored.decided_by == "Council Tester <council-tester@example.com>"


@pytest.mark.asyncio
async def test_other_account_gets_the_unknown_id_refusal_byte_for_byte(client, auth_headers):
    from app.api.v1.devon import _queue

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    record, token = _queue.request(
        title="Ownership probe",
        what_happens="Nothing runs.",
        requested_by="test",
        owner_id=me.json()["id"],
    )
    bob = await _account(client, "bob-probe@example.com", "Bob")
    theirs = await client.post(
        "/api/v1/devon/approvals/decide",
        json={"request_id": record.request_id, "token": token, "decision": "approve"},
        headers=bob,
    )
    missing = await client.post(
        "/api/v1/devon/approvals/decide",
        json={"request_id": "REQ-DOESNOTEXIST", "token": token, "decision": "approve"},
        headers=bob,
    )
    assert theirs.status_code == 200 and missing.status_code == 200
    a, b = theirs.json(), missing.json()
    assert a["ok"] is False and a["request_id"] == "NO_MATCH"
    assert {k: a[k] for k in ("ok", "approved", "request_id", "state", "reason")} == {
        k: b[k] for k in ("ok", "approved", "request_id", "state", "reason")
    }
    assert a["message"] == f"No request {record.request_id}."
    assert _queue.get(record.request_id).state.value == "pending"


@pytest.mark.asyncio
async def test_soul_ruling_is_signed_by_the_login(client, auth_headers, monkeypatch):
    monkeypatch.setenv("DEVON_RULING_KEY", "ruling-key-for-this-test-only-0123")
    from app.api.v1.devon import _queue

    proposed = await client.post(
        "/api/v1/soul/propose",
        json={"text": "remember the signed soul ruling probe"},
        headers=auth_headers,
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["approval"]["request_id"]
    token = proposed.json()["approval"]["token"]
    approved = await client.post(
        "/api/v1/soul/approve",
        json={"request_id": request_id, "token": token, "decided_by": "Forged Signer"},
        headers={**auth_headers, "X-Devon-Ruling-Key": "ruling-key-for-this-test-only-0123"},
    )
    assert approved.status_code == 200, approved.text
    assert _queue.get(request_id).decided_by == "Council Tester <council-tester@example.com>"


@pytest.mark.asyncio
async def test_registration_is_closed_without_the_invite(client, monkeypatch):
    # httpx merges per-request headers over the client defaults, so the key
    # cannot be dropped by omission: it has to be sent empty.
    anon = {"X-Devon-Registration-Key": ""}
    body = {"email": "walk-in@example.com", "password": "a-strong-password-123", "full_name": "W"}

    no_key = await client.post(REGISTER, json=body, headers=anon)
    assert no_key.status_code == 403, no_key.text

    wrong = await client.post(
        REGISTER, json={**body, "registration_key": "wrong-key-wrong-key-wrong"}, headers=anon
    )
    assert wrong.status_code == 403, wrong.text

    in_body = await client.post(
        REGISTER, json={**body, "registration_key": TEST_REGISTRATION_KEY}, headers=anon
    )
    assert in_body.status_code == 201, in_body.text

    monkeypatch.setenv("DEVON_REGISTRATION_KEY", "")
    closed = await client.post(
        REGISTER,
        json={**body, "email": "second@example.com", "registration_key": TEST_REGISTRATION_KEY},
        headers=anon,
    )
    assert closed.status_code == 503, closed.text
    assert "closed" in closed.json()["detail"].lower()
    assert os.getenv("DEVON_REGISTRATION_KEY") == ""
