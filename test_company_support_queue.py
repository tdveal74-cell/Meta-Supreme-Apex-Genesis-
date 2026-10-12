"""The Support queue's storage and routes. Needs the database.

Pinned: a bad draft never reaches the table, a comment is queued once per
account, a decision records the signed-in account and happens once, one
account never sees or decides another's drafts, and no route posts anything.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

GOOD = {
    "video_id": "dQw4w9WgXcQ",
    "comment_id": "UgxABC123_-xyz",
    "commenter_name": "Jordan Lee",
    "comment_text": "Does the checklist work for a non-technical manager?",
    "reply_text": "Yes. Steps one to three need no code. Step four is optional.",
    "reply_basis": "Episode script, checklist section, steps one to four.",
    "ai_disclosure": "Drafted with AI, posted by Tee.",
}
BASE = "/api/v1/company/support/drafts"


async def test_a_clean_comment_is_stored_as_drafted_and_listed(client, auth_headers):
    r = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "drafted" and body["decided_by"] is None
    listed = (await client.get(BASE, headers=auth_headers)).json()
    assert [d["draft_id"] for d in listed] == [body["draft_id"]]


@pytest.mark.parametrize("patch", [
    {"video_id": "nope"},
    {"comment_id": "a b"},
    {"reply_basis": "short"},
    {"ai_disclosure": "."},
    {"reply_text": "a — b"},
    {"reply_text": "a\x00b"},
    {"commenter_name": "Bob\r\nX"},
])
async def test_refused_comments_never_reach_the_table(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


async def test_a_trailing_newline_cannot_slip_a_comment_past_the_once_only_rule(client, auth_headers):
    assert (await client.post(BASE, json=GOOD, headers=auth_headers)).status_code == 201
    r = await client.post(BASE, json={**GOOD, "comment_id": GOOD["comment_id"] + "\n"}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert len((await client.get(BASE, headers=auth_headers)).json()) == 1


async def test_oversized_fields_are_refused(client, auth_headers):
    r = await client.post(BASE, json={**GOOD, "reply_text": "x" * 8001}, headers=auth_headers)
    assert r.status_code == 422, r.text


async def test_a_comment_is_queued_once_whatever_state_its_draft_is_in(client, auth_headers):
    first = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    again = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert again.status_code == 409 and "already has a draft" in again.text
    await client.post(f"{BASE}/{first['draft_id']}/reject", json={}, headers=auth_headers)
    after = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert after.status_code == 409
    assert len((await client.get(BASE, headers=auth_headers)).json()) == 1


async def test_the_same_comment_id_is_allowed_for_a_different_account(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_support_queue import insert_comment_draft

    await client.post(BASE, json=GOOD, headers=auth_headers)
    async with AsyncSessionLocal() as s:
        other = await insert_comment_draft(s, "some-other-account", **GOOD)
        await s.commit()
    assert other.comment_id == GOOD["comment_id"]


async def test_approval_records_the_signed_in_account_once(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={"note": "post it"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["decided_by"] == me["email"]
    again = await client.post(f"{BASE}/{d['draft_id']}/reject", json={}, headers=auth_headers)
    assert again.status_code == 409


async def test_rejection_is_recorded_and_filterable(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/reject", json={"note": "wrong answer"}, headers=auth_headers)
    assert r.json()["status"] == "rejected" and r.json()["decision_note"] == "wrong answer"
    assert (await client.get(BASE + "?status=drafted", headers=auth_headers)).json() == []
    assert len((await client.get(BASE + "?status=rejected", headers=auth_headers)).json()) == 1


async def test_unknown_draft_is_404(client, auth_headers):
    assert (await client.post(f"{BASE}/nope/approve", json={}, headers=auth_headers)).status_code == 404


async def test_routes_need_a_session(client):
    assert (await client.get(BASE)).status_code in (401, 403)
    assert (await client.post(BASE, json=GOOD)).status_code in (401, 403)


async def test_one_account_cannot_see_or_decide_another_accounts_draft(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_support_queue import insert_comment_draft

    async with AsyncSessionLocal() as s:
        other = await insert_comment_draft(s, "some-other-account", **GOOD)
        await s.commit()
    assert (await client.get(BASE, headers=auth_headers)).json() == []
    r = await client.post(f"{BASE}/{other.draft_id}/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_two_simultaneous_decisions_cannot_both_win(client, auth_headers, monkeypatch):
    """The python guard sees a stale 'drafted' copy in a race. The SQL guard must still refuse."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_support_queue
    from services.company.marketing import QueueRefusal

    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as s:
        stale = await company_support_queue.get_comment_draft(s, me["id"], d["draft_id"])
    assert (await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)).status_code == 200

    async def stale_get(db, owner_id, draft_id):
        return stale

    monkeypatch.setattr(company_support_queue, "get_comment_draft", stale_get)
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="already decided"):
            await company_support_queue.decide_comment_draft(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note=None
            )
        await s.rollback()
    monkeypatch.undo()
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "approved"


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    base = ("INSERT INTO company_comment_drafts (owner_id, draft_id, video_id, comment_id, commenter_name, "
            "comment_text, reply_text, reply_basis, ai_disclosure, status) VALUES ")
    bad_rows = [
        "('o','a','short','c','n','t','r','basis here ok','AI disclosure here','drafted')",
        "('o','b','dQw4w9WgXcQ','c','n','t','r','   ','AI disclosure here','drafted')",
        "('o','c','dQw4w9WgXcQ','c','n','t','r','basis here ok','   ','drafted')",
        "('o','d','dQw4w9WgXcQ','c','n','t','r','basis here ok','AI disclosure here','approved')",
        "('o','g','dQw4w9WgXcQ',E'c\\n','n','t','r','basis here ok','AI disclosure here','drafted')",
        "('o','h','dQw4w9WgXcQ','a b','n','t','r','basis here ok','AI disclosure here','drafted')",
    ]
    async with AsyncSessionLocal() as s:
        for row in bad_rows:
            with pytest.raises(IntegrityError):
                await s.execute(text(base + row))
            await s.rollback()
        # and the unique constraint holds for a caller that skips the service
        ok = "('o','e','dQw4w9WgXcQ','same','n','t','r','basis here ok','AI disclosure here','drafted')"
        dup = "('o','f','dQw4w9WgXcQ','same','n','t','r','basis here ok','AI disclosure here','drafted')"
        await s.execute(text(base + ok))
        with pytest.raises(IntegrityError):
            await s.execute(text(base + dup))
        await s.rollback()


async def test_a_nul_byte_in_a_decision_note_is_a_422_not_a_500(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    for verb in ("approve", "reject"):
        r = await client.post(f"{BASE}/{d['draft_id']}/{verb}", json={"note": "a\x00b"}, headers=auth_headers)
        assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "drafted"
