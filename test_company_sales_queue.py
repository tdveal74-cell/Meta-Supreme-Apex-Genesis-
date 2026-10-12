"""The Sales queue's storage and routes. Needs the database.

Pinned: a bad draft never reaches the table, a decision records the signed-in
account and happens once, one account never sees or decides another's leads,
and no route sends anything.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

GOOD = {
    "source": "email",
    "contact_name": "Jordan Lee",
    "contact_email": "jordan@example.com",
    "inbound_excerpt": "I am a mid-career PM worried about AI. Do you coach?",
    "qualification": "qualified",
    "qualification_reason": "Mid-career professional asking about AI career strategy.",
    "reply_text": "Thanks for writing. The Quiet Operator covers exactly this.",
    "ai_disclosure": "Drafted with AI, sent by Tee.",
}
BASE = "/api/v1/company/sales/drafts"


async def test_a_clean_lead_is_stored_as_drafted_and_listed(client, auth_headers):
    r = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "drafted" and body["decided_by"] is None
    assert body["qualification"] == "qualified"
    listed = (await client.get(BASE, headers=auth_headers)).json()
    assert [d["draft_id"] for d in listed] == [body["draft_id"]]


@pytest.mark.parametrize("patch", [
    {"source": "sms"},
    {"qualification": "maybe"},
    {"qualification_reason": "short"},
    {"contact_email": "nope"},
    {"ai_disclosure": "."},
    {"reply_text": "a — b"},
    {"reply_text": "a\x00b"},
])
async def test_refused_leads_never_reach_the_table(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


async def test_oversized_fields_are_refused(client, auth_headers):
    r = await client.post(BASE, json={**GOOD, "reply_text": "x" * 8001}, headers=auth_headers)
    assert r.status_code == 422, r.text


async def test_approval_records_the_signed_in_account_once(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={"note": "send it"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["decided_by"] == me["email"]
    again = await client.post(f"{BASE}/{d['draft_id']}/reject", json={}, headers=auth_headers)
    assert again.status_code == 409


async def test_rejection_is_recorded_and_filterable(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/reject", json={"note": "not a fit"}, headers=auth_headers)
    assert r.json()["status"] == "rejected" and r.json()["decision_note"] == "not a fit"
    assert (await client.get(BASE + "?status=drafted", headers=auth_headers)).json() == []
    assert len((await client.get(BASE + "?status=rejected", headers=auth_headers)).json()) == 1


async def test_unknown_draft_is_404(client, auth_headers):
    assert (await client.post(f"{BASE}/nope/approve", json={}, headers=auth_headers)).status_code == 404


async def test_routes_need_a_session(client):
    assert (await client.get(BASE)).status_code in (401, 403)
    assert (await client.post(BASE, json=GOOD)).status_code in (401, 403)


async def test_one_account_cannot_see_or_decide_another_accounts_lead(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_sales_queue import insert_lead_draft

    async with AsyncSessionLocal() as s:
        other = await insert_lead_draft(s, "some-other-account", **GOOD)
        await s.commit()
    assert (await client.get(BASE, headers=auth_headers)).json() == []
    r = await client.post(f"{BASE}/{other.draft_id}/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_two_simultaneous_decisions_cannot_both_win(client, auth_headers, monkeypatch):
    """The python guard sees a stale 'drafted' copy in a race. The SQL guard must still refuse."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_sales_queue
    from services.company.marketing import QueueRefusal

    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as s:
        stale = await company_sales_queue.get_lead_draft(s, me["id"], d["draft_id"])
    assert (await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)).status_code == 200

    async def stale_get(db, owner_id, draft_id):
        return stale

    monkeypatch.setattr(company_sales_queue, "get_lead_draft", stale_get)
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="already decided"):
            await company_sales_queue.decide_lead_draft(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note=None
            )
        await s.rollback()
    monkeypatch.undo()
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "approved"


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    base = ("INSERT INTO company_lead_drafts (owner_id, draft_id, source, contact_name, contact_email, "
            "inbound_excerpt, qualification, qualification_reason, reply_text, ai_disclosure, status) VALUES ")
    bad_rows = [
        "('o','a','sms','n','e@x.co','i','qualified','r','t','AI disclosure here','drafted')",
        "('o','b','email','n','e@x.co','i','maybe','r','t','AI disclosure here','drafted')",
        "('o','c','email','n','e@x.co','i','qualified','r','t','   ','drafted')",
        "('o','d','email','n','e@x.co','i','qualified','r','t','AI disclosure here','approved')",
    ]
    async with AsyncSessionLocal() as s:
        for row in bad_rows:
            with pytest.raises(IntegrityError):
                await s.execute(text(base + row))
            await s.rollback()
