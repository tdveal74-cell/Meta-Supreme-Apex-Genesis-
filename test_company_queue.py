"""The Marketing queue's storage and routes. Needs the database.

Pinned: a draft without disclosure or with a dash never reaches the table, a
decision records the signed-in account and happens once, one account never sees
or decides another's drafts, and no route publishes anything.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

GOOD = {
    "show": "TQO",
    "episode_ref": "ep-12",
    "platform": "youtube_community",
    "text": "New episode: three steps to audit your role for AI risk.",
    "ai_disclosure": "Made with an AI voice and avatar.",
}
BASE = "/api/v1/company/marketing/drafts"


async def test_a_clean_draft_is_stored_as_drafted(client, auth_headers):
    r = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "drafted" and body["decided_by"] is None
    listed = (await client.get(BASE, headers=auth_headers)).json()
    assert [d["draft_id"] for d in listed] == [body["draft_id"]]


@pytest.mark.parametrize("patch", [
    {"ai_disclosure": ""},
    {"ai_disclosure": "   "},
    {"text": "before — after"},
    {"text": "before – after"},
    {"ai_disclosure": "AI — voice"},
])
async def test_refused_drafts_never_reach_the_table(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


async def test_approval_records_the_signed_in_account_once(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={"note": "ok"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["decided_by"] == me["email"]
    again = await client.post(f"{BASE}/{d['draft_id']}/reject", json={}, headers=auth_headers)
    assert again.status_code == 409


async def test_rejection_is_recorded(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/reject", json={"note": "off tone"}, headers=auth_headers)
    assert r.json()["status"] == "rejected" and r.json()["decision_note"] == "off tone"
    only = (await client.get(BASE + "?status=drafted", headers=auth_headers)).json()
    assert only == []


async def test_unknown_draft_is_404(client, auth_headers):
    r = await client.post(f"{BASE}/nope/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_routes_need_a_session(client):
    assert (await client.get(BASE)).status_code in (401, 403)
    assert (await client.post(BASE, json=GOOD)).status_code in (401, 403)


async def test_one_account_cannot_see_or_decide_another_accounts_draft(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_queue import insert_draft

    async with AsyncSessionLocal() as s:
        other = await insert_draft(
            s, "some-other-account", show="TQO", episode_ref="x", platform="p",
            post_text="hello", ai_disclosure="Made with AI voice.",
        )
        await s.commit()
    assert (await client.get(BASE, headers=auth_headers)).json() == []
    r = await client.post(f"{BASE}/{other.draft_id}/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    """The CHECK constraints hold what must survive code that skips the module."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text(
                "INSERT INTO company_post_drafts (owner_id, draft_id, show, episode_ref, platform, text, ai_disclosure) "
                "VALUES ('o','d','s','e','p','t','   ')"))
        await s.rollback()
        with pytest.raises(IntegrityError):
            await s.execute(text(
                "INSERT INTO company_post_drafts (owner_id, draft_id, show, episode_ref, platform, text, ai_disclosure, status) "
                "VALUES ('o','d2','s','e','p','t','AI','approved')"))
        await s.rollback()


async def test_two_simultaneous_decisions_cannot_both_win(client, auth_headers, monkeypatch):
    """The python guard sees a stale 'drafted' copy in a race. The SQL guard must still refuse."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_queue
    from services.company.marketing import QueueRefusal

    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    stale = await _read(me["id"], d["draft_id"])
    first = await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)
    assert first.status_code == 200

    async def stale_get(db, owner_id, draft_id):
        return stale

    monkeypatch.setattr(company_queue, "get_draft", stale_get)
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="already decided"):
            await company_queue.decide_draft(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note=None
            )
        await s.rollback()
    monkeypatch.undo()
    final = await client.get(BASE, headers=auth_headers)
    assert final.json()[0]["status"] == "approved"


async def _read(owner_id, draft_id):
    from app.db.session import AsyncSessionLocal
    from app.services import company_queue

    async with AsyncSessionLocal() as s:
        return await company_queue.get_draft(s, owner_id, draft_id)


@pytest.mark.parametrize("patch", [
    {"text": "a\x00b"},
    {"show": "a\x00b"},
    {"ai_disclosure": "AI\x00made"},
])
async def test_a_nul_byte_is_refused_with_422_not_a_500(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


@pytest.mark.parametrize("patch", [
    {"text": "x" * 4001},
    {"ai_disclosure": "x" * 1001},
])
async def test_oversized_fields_are_refused(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    ok = await client.post(BASE, json={**GOOD, "text": "x" * 4000}, headers=auth_headers)
    assert ok.status_code == 201, ok.text


@pytest.mark.parametrize("patch", [
    {"ai_disclosure": "."},
    {"ai_disclosure": "\u200b"},
    {"text": "before \u2015 after"},
])
async def test_lookalike_dashes_and_junk_disclosures_are_refused_by_the_route(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []
