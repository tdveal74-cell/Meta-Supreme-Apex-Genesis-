"""The Support knowledge base's storage and routes, and the citation rule. Needs the database.

Pinned: an article is a draft until a human approves it, one account never sees
or decides another's, a reply cites an approved article of its own account or is
refused, and the table holds the rules for a caller that skips the service.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

ARTICLES = "/api/v1/company/support/articles"
DRAFTS = "/api/v1/company/support/drafts"
ART = {"article_id": "checklist-guide", "title": "The episode checklist",
       "body": "Steps one to three need no code. Step four is optional for a manager."}
DRAFT = {
    "video_id": "dQw4w9WgXcQ", "comment_id": "UgxABC123_-xyz", "commenter_name": "Jordan Lee",
    "comment_text": "Does the checklist work for a manager?",
    "reply_text": "Yes. Steps one to three need no code.",
    "reply_basis": "Episode script, checklist section.",
    "ai_disclosure": "Drafted with AI, posted by Tee.", "article_id": "checklist-guide",
}


async def post_article(client, headers, **patch):
    return await client.post(ARTICLES, json={**ART, **patch}, headers=headers)


async def test_an_article_is_stored_as_a_draft_and_listed(client, auth_headers):
    r = await post_article(client, auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "drafted" and r.json()["decided_by"] is None
    listed = (await client.get(ARTICLES, headers=auth_headers)).json()
    assert [a["article_id"] for a in listed] == ["checklist-guide"]
    assert (await client.get(f"{ARTICLES}?status=approved", headers=auth_headers)).json() == []


async def test_an_article_id_is_used_once_per_account(client, auth_headers):
    assert (await post_article(client, auth_headers)).status_code == 201
    again = await post_article(client, auth_headers, title="Another title")
    assert again.status_code == 409 and "already exists" in again.json()["detail"]


@pytest.mark.parametrize("patch", [
    {"article_id": "Bad Id"}, {"article_id": "x"}, {"title": "A — B title"},
    {"body": "too short"}, {"body": "a\x00" + "b" * 40},
])
async def test_a_bad_article_is_a_422_and_stores_nothing(client, auth_headers, patch):
    r = await post_article(client, auth_headers, **patch)
    assert r.status_code == 422, r.text
    assert (await client.get(ARTICLES, headers=auth_headers)).json() == []


async def test_a_decision_records_the_signed_in_account_once(client, auth_headers):
    await post_article(client, auth_headers)
    r = await client.post(f"{ARTICLES}/checklist-guide/approve", json={"note": "Checked."}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"]
    again = await client.post(f"{ARTICLES}/checklist-guide/reject", json={}, headers=auth_headers)
    assert again.status_code == 409
    missing = await client.post(f"{ARTICLES}/no-such-article/approve", json={}, headers=auth_headers)
    assert missing.status_code == 404


async def test_a_dash_in_an_article_decision_note_is_a_422(client, auth_headers):
    await post_article(client, auth_headers)
    r = await client.post(f"{ARTICLES}/checklist-guide/approve", json={"note": "ok — go"}, headers=auth_headers)
    assert r.status_code == 422


async def test_a_reply_citing_a_drafted_article_is_refused(client, auth_headers):
    await post_article(client, auth_headers)
    r = await client.post(DRAFTS, json=DRAFT, headers=auth_headers)
    assert r.status_code == 422 and "drafted" in r.json()["detail"]
    assert (await client.get(DRAFTS, headers=auth_headers)).json() == []


async def test_a_reply_citing_a_rejected_article_is_refused(client, auth_headers):
    await post_article(client, auth_headers)
    await client.post(f"{ARTICLES}/checklist-guide/reject", json={}, headers=auth_headers)
    r = await client.post(DRAFTS, json=DRAFT, headers=auth_headers)
    assert r.status_code == 422 and "rejected" in r.json()["detail"]


async def test_a_reply_citing_no_article_or_a_missing_one_is_refused(client, auth_headers):
    body = {k: v for k, v in DRAFT.items() if k != "article_id"}
    assert (await client.post(DRAFTS, json=body, headers=auth_headers)).status_code == 422
    r = await client.post(DRAFTS, json={**DRAFT, "article_id": "never-written"}, headers=auth_headers)
    assert r.status_code == 422 and "does not exist" in r.json()["detail"]
    r = await client.post(DRAFTS, json={**DRAFT, "article_id": "Not A Slug"}, headers=auth_headers)
    assert r.status_code == 422


async def test_a_reply_citing_an_approved_article_is_stored_with_the_citation(client, auth_headers):
    await post_article(client, auth_headers)
    await client.post(f"{ARTICLES}/checklist-guide/approve", json={}, headers=auth_headers)
    r = await client.post(DRAFTS, json=DRAFT, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["article_id"] == "checklist-guide"
    assert (await client.get(DRAFTS, headers=auth_headers)).json()[0]["article_id"] == "checklist-guide"


async def test_another_accounts_approved_article_cannot_be_cited(client, auth_headers):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        await s.execute(text(
            "INSERT INTO company_support_articles (owner_id, article_id, title, body, status, decided_by) "
            "VALUES ('some-other-account', 'checklist-guide', 'T', 'Steps one to three need no code at all.', "
            "'approved', 'tee@example.com')"))
        await s.commit()
    r = await client.post(DRAFTS, json=DRAFT, headers=auth_headers)
    assert r.status_code == 422 and "does not exist" in r.json()["detail"]
    assert (await client.get(ARTICLES, headers=auth_headers)).json() == []
    assert (await client.post(f"{ARTICLES}/checklist-guide/approve", json={}, headers=auth_headers)).status_code == 404


async def test_the_routes_need_a_session(client):
    assert (await client.get(ARTICLES)).status_code in (401, 403)
    assert (await client.post(ARTICLES, json=ART)).status_code in (401, 403)
    assert (await client.post(f"{ARTICLES}/checklist-guide/approve", json={})).status_code in (401, 403)


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    base = "INSERT INTO company_support_articles (owner_id, article_id, title, body, status, decided_by) VALUES "
    bad_rows = [
        "('o','Bad Id','t','body text here','drafted',NULL)",
        "('o','x','t','body text here','drafted',NULL)",
        "('o','ok-id','   ','body text here','drafted',NULL)",
        "('o','ok-id','t','   ','drafted',NULL)",
        "('o','ok-id','t','body text here','approved',NULL)",
        "('o','ok-id','t','body text here','drafted','tee@example.com')",
        "('o','ok-id','t','body text here','published',NULL)",
        "('o',E'ok-id\\n','t','body text here','drafted',NULL)",
    ]
    async with AsyncSessionLocal() as s:
        for row in bad_rows:
            with pytest.raises(IntegrityError):
                await s.execute(text(base + row))
            await s.rollback()


async def test_the_table_will_not_hold_a_reply_citing_an_article_that_is_not_there(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    sql = ("INSERT INTO company_comment_drafts (owner_id, draft_id, video_id, comment_id, commenter_name, "
           "comment_text, reply_text, reply_basis, ai_disclosure, article_id) VALUES "
           "('o','d1','dQw4w9WgXcQ','c1','n','t','r','basis here ok','AI disclosure here', :a)")
    async with AsyncSessionLocal() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text(sql), {"a": "ghost-article"})
        await s.rollback()
        # a NULL citation is what rows from before the migration carry, and it is allowed
        await s.execute(text(sql), {"a": None})
        await s.rollback()
