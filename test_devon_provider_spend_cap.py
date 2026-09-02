"""The per-tenant provider spend cap (fix PR 15, audit H15).

Every lane that reaches a provider takes it from `get_provider()`, which
returns the configured provider wrapped in `MeteredProvider`. These tests
drive the cap through `settings.PROVIDER_DAILY_TOKEN_CAP` and count calls
on the inner mock provider, so nothing here needs a key or the network.

What is checked: an account at the cap gets 429 and the provider is not
called; the ledger row increments per call by the tokens the provider
reported; a second account is unaffected; cap 0 disables the refusal and
keeps the ledger; work outside a request is spent under the capped system
bucket, and the dispatcher binds a scheduled run to the workflow's owner;
the row survives a request that fails after the spend, including a session
that rolls back; the stream reports the refusal as 429.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.tenant_context import SYSTEM_TENANT, bind_tenant, current_tenant_id, reset_tenant
from app.db.session import engine
from app.models.workflow import Workflow
from app.services.dispatcher import dispatch_due
from app.services.intelligence import get_provider
from app.services.provider_usage import (
    ProviderSpendCapExceeded,
    cap_resets_at,
    read_usage,
    record_usage,
    utc_today,
)
from services.intelligence.providers.base import ChatMessage, CompletionRequest

ASK = "/api/v1/intelligence/ask"
TESTER_EMAIL = "council-tester@example.com"


async def _user_id(email: str) -> str:
    async with engine.connect() as conn:
        row = (
            await conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
        ).first()
    assert row is not None, email
    return str(row.id)


async def _login(client, email: str) -> dict:
    password = "a-strong-password-123"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Second Tenant"},
    )
    assert register.status_code == 201, register.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _count_inner_calls(monkeypatch) -> list:
    """Count completions on the provider under the wrapper; return the responses seen."""
    inner = get_provider().inner
    original = inner._complete_once
    seen: list = []

    async def counting(request):
        response = await original(request)
        seen.append(response)
        return response

    monkeypatch.setattr(inner, "_complete_once", counting)
    return seen


def _cap(monkeypatch, value: int) -> None:
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", value)


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------


async def test_an_account_at_the_cap_is_refused_and_the_provider_is_not_called(
    client, auth_headers, monkeypatch
):
    _cap(monkeypatch, 1_000)
    user_id = await _user_id(TESTER_EMAIL)
    await record_usage(user_id, input_tokens=600, output_tokens=400)
    seen = _count_inner_calls(monkeypatch)

    response = await client.post(ASK, json={"message": "Explain monorepos."}, headers=auth_headers)

    assert response.status_code == 429, response.text
    body = response.json()
    assert body["error"]["code"] == "provider_spend_cap"
    day = utc_today()
    detail = body["detail"]
    assert "1,000 of 1,000 tokens" in detail
    assert day.isoformat() in detail
    assert cap_resets_at(day).isoformat() in detail
    assert "Nothing was sent to the provider" in detail
    assert int(response.headers["Retry-After"]) >= 1
    assert seen == [], "the provider was called for an account at its cap"
    after = await read_usage(user_id)
    assert (after.calls, after.input_tokens, after.output_tokens) == (1, 600, 400)


async def test_the_refusal_is_on_reaching_the_cap_not_on_exceeding_it(db_session, monkeypatch):
    """One token under the cap still runs one call; the call after it is refused.

    A single provider call, bound to an account by hand, because a council
    request makes several calls and the check runs before each of them (the
    next test).
    """
    _cap(monkeypatch, 1_000)
    await record_usage("one-under", input_tokens=999, output_tokens=0)
    seen = _count_inner_calls(monkeypatch)
    request = CompletionRequest(messages=[ChatMessage(role="user", content="hi")])

    token = bind_tenant("one-under")
    try:
        await get_provider().complete(request)
        assert len(seen) == 1, "the call one token under the cap ran"
        with pytest.raises(ProviderSpendCapExceeded):
            await get_provider().complete(request)
    finally:
        reset_tenant(token)

    assert len(seen) == 1, "the call at the cap did not reach the provider"
    usage = await read_usage("one-under")
    assert usage.calls == 2
    assert usage.total_tokens == 999 + seen[0].usage.total_tokens >= 1_000


async def test_a_cap_crossed_mid_council_refuses_the_next_call_of_the_same_request(
    client, auth_headers, monkeypatch
):
    """Overshoot is bounded to the calls already in flight, never a whole request."""
    _cap(monkeypatch, 1_000)
    user_id = await _user_id(TESTER_EMAIL)
    await record_usage(user_id, input_tokens=999, output_tokens=0)
    seen = _count_inner_calls(monkeypatch)

    response = await client.post(ASK, json={"message": "hi"}, headers=auth_headers)

    assert response.status_code == 429, response.text
    assert seen, "the first call ran under the cap"
    usage = await read_usage(user_id)
    assert usage.calls == 1 + len(seen), "every call that ran was recorded before the refusal"


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


async def test_usage_rows_increment_per_call_by_the_tokens_the_provider_reported(
    client, auth_headers, monkeypatch
):
    user_id = await _user_id(TESTER_EMAIL)
    assert (await read_usage(user_id)).calls == 0
    seen = _count_inner_calls(monkeypatch)

    response = await client.post(ASK, json={"message": "Compare two options."}, headers=auth_headers)

    assert response.status_code == 200, response.text
    assert seen, "the council made at least one provider call"
    usage = await read_usage(user_id)
    assert usage.calls == len(seen)
    assert usage.input_tokens == sum(r.usage.input_tokens for r in seen)
    assert usage.output_tokens == sum(r.usage.output_tokens for r in seen)
    assert usage.input_tokens > 0 and usage.output_tokens > 0

    second = await client.post(ASK, json={"message": "And again."}, headers=auth_headers)
    assert second.status_code == 200, second.text
    again = await read_usage(user_id)
    assert again.calls == len(seen)
    assert again.total_tokens == sum(r.usage.total_tokens for r in seen)
    assert (await read_usage(SYSTEM_TENANT)).calls == 0


async def test_a_second_account_is_unaffected_by_the_first_at_its_cap(
    client, auth_headers, monkeypatch
):
    _cap(monkeypatch, 100_000)
    first = await _user_id(TESTER_EMAIL)
    await record_usage(first, input_tokens=100_000, output_tokens=0)
    other_headers = await _login(client, "second-tenant@example.com")
    other = await _user_id("second-tenant@example.com")
    seen = _count_inner_calls(monkeypatch)

    refused = await client.post(ASK, json={"message": "hi"}, headers=auth_headers)
    assert refused.status_code == 429, refused.text
    assert seen == []

    allowed = await client.post(ASK, json={"message": "hi"}, headers=other_headers)
    assert allowed.status_code == 200, allowed.text
    assert (await read_usage(other)).calls == len(seen) > 0
    assert (await read_usage(first)).calls == 1


async def test_cap_zero_disables_the_refusal_and_keeps_the_ledger(
    client, auth_headers, monkeypatch
):
    _cap(monkeypatch, 0)
    user_id = await _user_id(TESTER_EMAIL)
    await record_usage(user_id, input_tokens=10**9, output_tokens=10**9)
    seen = _count_inner_calls(monkeypatch)

    response = await client.post(ASK, json={"message": "hi"}, headers=auth_headers)

    assert response.status_code == 200, response.text
    usage = await read_usage(user_id)
    assert usage.calls == 1 + len(seen)
    assert usage.total_tokens == 2 * 10**9 + sum(r.usage.total_tokens for r in seen)


# ---------------------------------------------------------------------------
# No account in hand
# ---------------------------------------------------------------------------


async def test_work_outside_a_request_is_spent_under_the_system_bucket_which_is_capped(
    db_session, monkeypatch
):
    assert current_tenant_id() is None
    request = CompletionRequest(messages=[ChatMessage(role="user", content="startup job")])

    response = await get_provider().complete(request)

    system = await read_usage(SYSTEM_TENANT)
    assert system.calls == 1
    assert system.input_tokens == response.usage.input_tokens
    assert system.output_tokens == response.usage.output_tokens

    _cap(monkeypatch, system.total_tokens)
    seen = _count_inner_calls(monkeypatch)
    with pytest.raises(ProviderSpendCapExceeded) as refusal:
        await get_provider().complete(request)
    assert refusal.value.tenant_id == SYSTEM_TENANT
    assert refusal.value.status_code == 429
    assert seen == []


async def test_a_lane_that_binds_its_owner_spends_under_the_owner(db_session):
    request = CompletionRequest(messages=[ChatMessage(role="user", content="bound")])
    token = bind_tenant("owner-in-hand")
    try:
        await get_provider().complete(request)
    finally:
        reset_tenant(token)
    assert current_tenant_id() is None
    assert (await read_usage("owner-in-hand")).calls == 1
    assert (await read_usage(SYSTEM_TENANT)).calls == 0


async def test_the_dispatcher_spends_a_scheduled_run_under_the_workflow_owner(
    db_session, auth_headers
):
    owner = await _user_id(TESTER_EMAIL)
    now = datetime.now(timezone.utc)
    workflow = Workflow(
        owner_id=owner,
        name="Scheduled council",
        definition={
            "version": 1,
            "trigger": {"type": "schedule", "config": {"cadence": "daily:07:00"}},
            "steps": [
                {"id": "assess", "type": "council", "config": {"prompt": "Assess the week."}}
            ],
        },
        status="active",
        meta={},
        next_run_at=now - timedelta(minutes=1),
    )
    db_session.add(workflow)
    await db_session.flush()

    report = await dispatch_due(db_session, now=now)

    assert report.started, report.summary()
    assert current_tenant_id() is None
    assert (await read_usage(owner)).calls > 0
    assert (await read_usage(SYSTEM_TENANT)).calls == 0


# ---------------------------------------------------------------------------
# Durability
# ---------------------------------------------------------------------------


async def test_the_record_survives_a_request_that_fails_after_the_spend(
    client, auth_headers, monkeypatch
):
    """The council pays for its calls, then fails; the session rolls back; the spend stays."""
    user_id = await _user_id(TESTER_EMAIL)
    monkeypatch.setattr(get_provider().inner, "_responder", lambda request: "garbage")
    seen = _count_inner_calls(monkeypatch)
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Plan the launch."},
        headers=auth_headers,
    )

    assert response.status_code == 502, response.text
    assert seen, "the provider was called before the council failed"
    listing = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=auth_headers
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["messages"] == [], "the request's own writes rolled back"
    usage = await read_usage(user_id)
    # The message lane also embeds the message for recall and retrieval, and
    # the ledger counts that call too; embeddings report input tokens only.
    assert usage.calls > len(seen)
    assert usage.output_tokens == sum(r.usage.output_tokens for r in seen)
    assert usage.input_tokens > sum(r.usage.input_tokens for r in seen)


async def test_the_stream_reports_the_refusal_as_429(client, auth_headers, monkeypatch):
    _cap(monkeypatch, 10)
    user_id = await _user_id(TESTER_EMAIL)
    await record_usage(user_id, input_tokens=10, output_tokens=0)
    seen = _count_inner_calls(monkeypatch)
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "hi"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    events = [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    errors = [e for e in events if e.get("type") == "error"]
    assert errors and errors[-1]["status"] == 429, events
    assert "Provider spend cap reached" in errors[-1]["message"]
    assert seen == []
