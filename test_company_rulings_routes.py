"""Tee's rulings of 2026-10-14 through the real routes and tables. Needs the database."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

ROOT = "/api/v1/company"
SALES = {
    "source": "email", "contact_name": "Jordan Lee", "contact_email": "jordan@example.com",
    "inbound_excerpt": "I am a mid-career PM worried about AI. Do you coach?",
    "qualification": "qualified", "qualification_reason": "Mid-career professional asking about AI.",
    "reply_text": "Thanks for writing. The Quiet Operator covers exactly this.",
}
ARTICLE = {"article_id": "checklist-guide", "title": "The episode checklist",
           "body": "Steps one to three need no code. Step four is optional for a manager."}


@pytest.fixture(autouse=True)
async def approved_article(client, auth_headers):
    """Every Support reply cites an approved article, so the account has one."""
    base = "/api/v1/company/support/articles"
    assert (await client.post(base, json=ARTICLE, headers=auth_headers)).status_code == 201
    assert (await client.post(f"{base}/{ARTICLE['article_id']}/approve", json={}, headers=auth_headers)).status_code == 200


QUEUES = {
    "marketing": (f"{ROOT}/marketing/drafts", {
        "show": "TQO", "episode_ref": "ep-1", "platform": "youtube_community",
        "text": "New episode out now.", "ai_disclosure": "Made with an AI voice."}),
    "sales": (f"{ROOT}/sales/drafts", {**SALES, "ai_disclosure": "Drafted with AI, sent by Tee."}),
    "support": (f"{ROOT}/support/drafts", {
        "video_id": "dQw4w9WgXcQ", "comment_id": "UgxABC123", "commenter_name": "Jordan Lee",
        "comment_text": "Does the checklist work for a manager?",
        "reply_text": "Yes. Steps one to three need no code.",
        "reply_basis": "Episode script, checklist section.", "ai_disclosure": "Drafted with AI, posted by Tee.",
        "article_id": "checklist-guide"}),
    "research": (f"{ROOT}/research/findings", {
        "claim": "Career strategy searches rose in 2026.", "evidence_kind": "source",
        "evidence_ref": "https://example.com/report", "recommendation": "Lead the next episode with it."}),
    "product": (f"{ROOT}/product/proposals", {
        "title": "Weekly revenue digest", "problem": "Revenue is not visible outside Stripe.",
        "proposal": "Read the month total into the scoreboard.",
        "acceptance_check": "The scoreboard equals the Stripe total.",
        "reference_artifact": "services/company/scoreboard.py", "size": "small"}),
}


async def test_a_sales_draft_can_be_queued_with_no_disclosure(client, auth_headers):
    base = QUEUES["sales"][0]
    for i, patch in enumerate(({}, {"ai_disclosure": None}, {"ai_disclosure": ""}, {"ai_disclosure": "   "})):
        body = {**SALES, "contact_email": f"lead{i}@example.com", **patch}
        r = await client.post(base, json=body, headers=auth_headers)
        assert r.status_code == 201, r.text
        assert r.json()["ai_disclosure"] is None
    listed = (await client.get(base, headers=auth_headers)).json()
    assert len(listed) == 4 and all(d["ai_disclosure"] is None for d in listed)


async def test_a_sales_disclosure_that_is_given_must_still_be_real(client, auth_headers):
    base = QUEUES["sales"][0]
    for junk in (".", "AI", "⠀" * 12, "ㅤ" * 12, "Drafted — with AI by Tee"):
        r = await client.post(base, json={**SALES, "ai_disclosure": junk}, headers=auth_headers)
        assert r.status_code == 422, (junk, r.text)
    assert (await client.get(base, headers=auth_headers)).json() == []


async def test_a_given_sales_disclosure_is_stored_and_a_sales_draft_with_none_can_be_approved(client, auth_headers):
    base = QUEUES["sales"][0]
    given = (await client.post(base, json={**SALES, "ai_disclosure": "Drafted with AI, sent by Tee."},
                               headers=auth_headers)).json()
    assert given["ai_disclosure"] == "Drafted with AI, sent by Tee."
    bare = (await client.post(base, json={**SALES, "contact_email": "other@example.com"},
                              headers=auth_headers)).json()
    r = await client.post(f"{base}/{bare['draft_id']}/approve", json={}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["ai_disclosure"] is None


@pytest.mark.parametrize("queue", ["marketing", "support"])
async def test_marketing_and_support_still_require_a_disclosure(client, auth_headers, queue):
    base, body = QUEUES[queue]
    for patch in ({"ai_disclosure": None}, {"ai_disclosure": ""}, {"ai_disclosure": "⠀" * 12}):
        r = await client.post(base, json={**body, **patch}, headers=auth_headers)
        assert r.status_code == 422, (queue, patch, r.text)
    missing = {k: v for k, v in body.items() if k != "ai_disclosure"}
    assert (await client.post(base, json=missing, headers=auth_headers)).status_code == 422
    assert (await client.get(base, headers=auth_headers)).json() == []


@pytest.mark.parametrize("queue", list(QUEUES))
@pytest.mark.parametrize("dash", ["—", "–", "―", "︱"])
async def test_a_dash_in_a_decision_note_is_a_422_on_every_queue(client, auth_headers, queue, dash):
    base, body = QUEUES[queue]
    d = (await client.post(base, json=body, headers=auth_headers)).json()
    for verb in ("approve", "reject"):
        r = await client.post(f"{base}/{d['draft_id']}/{verb}", json={"note": f"fine {dash} ship"},
                              headers=auth_headers)
        assert r.status_code == 422, (queue, verb, r.text)
    assert (await client.get(base, headers=auth_headers)).json()[0]["status"] == "drafted"
    ok = await client.post(f"{base}/{d['draft_id']}/reject", json={"note": "not now, a‐b − fine"},
                           headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["status"] == "rejected"


async def test_the_rules_refuse_a_dash_note_even_when_the_route_pattern_is_skipped(client, auth_headers):
    """Defense in depth: a caller that goes around the route still hits the rule."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_product_queue
    from services.company.marketing import QueueRefusal

    base, body = QUEUES["product"]
    d = (await client.post(base, json=body, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="dash"):
            await company_product_queue.decide_proposal(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note="no — thanks")
        await s.rollback()


async def test_acceptance_checks_and_references_take_the_dash_rule_through_the_route(client, auth_headers):
    base, body = QUEUES["product"]
    for patch in ({"acceptance_check": "works — measured against the total"},
                  {"reference_artifact": "the scoreboard file – extended"}):
        r = await client.post(base, json={**body, **patch}, headers=auth_headers)
        assert r.status_code == 422, r.text
    url = "https://example.com/docs/a–b/page"
    assert (await client.post(base, json={**body, "reference_artifact": url}, headers=auth_headers)).status_code == 201

    base, body = QUEUES["research"]
    for kind in ("measured", "unverified"):
        r = await client.post(base, json={**body, "evidence_kind": kind,
                                          "evidence_ref": "pytest run — 41 passed"}, headers=auth_headers)
        assert r.status_code == 422, r.text
    ok = await client.post(base, json={**body, "evidence_ref": "https://example.com/a–b/report"},
                           headers=auth_headers)
    assert ok.status_code == 201


async def test_the_lead_table_allows_a_null_disclosure_and_still_refuses_a_blank_one(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    base = ("INSERT INTO company_lead_drafts (owner_id, draft_id, source, contact_name, contact_email, "
            "inbound_excerpt, qualification, qualification_reason, reply_text, ai_disclosure) VALUES ")
    async with AsyncSessionLocal() as s:
        await s.execute(text(base + "('o','a','email','n','e@x.co','i','qualified','r','t',NULL)"))
        await s.execute(text(base + "('o','b','email','n','e@x.co','i','qualified','r','t','Drafted with AI')"))
        for blank in ("''", "'   '"):
            with pytest.raises(IntegrityError):
                async with s.begin_nested():
                    await s.execute(text(base + f"('o','c','email','n','e@x.co','i','qualified','r','t',{blank})"))
        await s.rollback()
