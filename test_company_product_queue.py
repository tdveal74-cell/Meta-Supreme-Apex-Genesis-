"""The Product proposals queue's storage and routes. Needs the database.

Pinned: a bad proposal never reaches the table, a title is recorded once per
account, a large proposal cannot be approved without a note, a decision records
the signed-in account and happens once, one account never sees or decides
another's proposals, and no route builds anything.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

GOOD = {
    "title": "Weekly revenue digest",
    "problem": "Revenue is not visible anywhere except inside Stripe.",
    "proposal": "Read the month total into the scoreboard and send one line a week.",
    "acceptance_check": "The scoreboard revenue equals the Stripe dashboard total to the cent.",
    "reference_artifact": "services/company/scoreboard.py",
    "size": "small",
}
LARGE = {**GOOD, "title": "Rebuild the render lane", "size": "large"}
BASE = "/api/v1/company/product/proposals"


async def test_a_clean_proposal_is_stored_as_drafted_and_listed(client, auth_headers):
    r = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "drafted" and body["decided_by"] is None and body["size"] == "small"
    listed = (await client.get(BASE, headers=auth_headers)).json()
    assert [d["draft_id"] for d in listed] == [body["draft_id"]]


@pytest.mark.parametrize("patch", [
    {"size": "huge"},
    {"title": "abc"},
    {"title": "Bad title here"},
    {"acceptance_check": "short"},
    {"reference_artifact": "short"},
    {"proposal": "a — b proposal that is long enough"},
    {"problem": "a\x00b problem that is long enough"},
])
async def test_refused_proposals_never_reach_the_table(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


async def test_oversized_fields_are_refused(client, auth_headers):
    assert (await client.post(BASE, json={**GOOD, "title": "x" * 201}, headers=auth_headers)).status_code == 422
    assert (await client.post(BASE, json={**GOOD, "proposal": "x" * 8001}, headers=auth_headers)).status_code == 422


async def test_a_title_is_recorded_once_whatever_state_its_proposal_is_in(client, auth_headers):
    first = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    again = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert again.status_code == 409 and "already on record" in again.text
    spaced = {**GOOD, "title": GOOD["title"].upper().replace(" ", "  ")}
    assert (await client.post(BASE, json=spaced, headers=auth_headers)).status_code == 409
    await client.post(f"{BASE}/{first['draft_id']}/reject", json={}, headers=auth_headers)
    assert (await client.post(BASE, json=GOOD, headers=auth_headers)).status_code == 409
    assert len((await client.get(BASE, headers=auth_headers)).json()) == 1


async def test_the_same_title_is_allowed_for_a_different_account(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_product_queue import insert_proposal

    await client.post(BASE, json=GOOD, headers=auth_headers)
    async with AsyncSessionLocal() as s:
        other = await insert_proposal(s, "some-other-account", **GOOD)
        await s.commit()
    assert other.title == GOOD["title"]


async def test_approval_records_the_signed_in_account_once(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["decided_by"] == me["email"]
    again = await client.post(f"{BASE}/{d['draft_id']}/reject", json={}, headers=auth_headers)
    assert again.status_code == 409


async def test_a_large_proposal_is_not_approved_without_a_note(client, auth_headers):
    d = (await client.post(BASE, json=LARGE, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)
    assert r.status_code == 409 and "large" in r.text
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "drafted"
    ok = await client.post(f"{BASE}/{d['draft_id']}/approve",
                           json={"note": "Taking this on knowingly, two weeks."}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


async def test_rejection_is_recorded_and_filterable(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/reject", json={"note": "not now"}, headers=auth_headers)
    assert r.json()["status"] == "rejected" and r.json()["decision_note"] == "not now"
    assert (await client.get(BASE + "?status=drafted", headers=auth_headers)).json() == []
    assert len((await client.get(BASE + "?status=rejected", headers=auth_headers)).json()) == 1


async def test_unknown_proposal_is_404(client, auth_headers):
    assert (await client.post(f"{BASE}/nope/approve", json={}, headers=auth_headers)).status_code == 404


async def test_routes_need_a_session(client):
    assert (await client.get(BASE)).status_code in (401, 403)
    assert (await client.post(BASE, json=GOOD)).status_code in (401, 403)


async def test_one_account_cannot_see_or_decide_another_accounts_proposal(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_product_queue import insert_proposal

    async with AsyncSessionLocal() as s:
        other = await insert_proposal(s, "some-other-account", **GOOD)
        await s.commit()
    assert (await client.get(BASE, headers=auth_headers)).json() == []
    r = await client.post(f"{BASE}/{other.draft_id}/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_two_simultaneous_decisions_cannot_both_win(client, auth_headers, monkeypatch):
    """The python guard sees a stale 'drafted' copy in a race. The SQL guard must still refuse."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_product_queue
    from services.company.marketing import QueueRefusal

    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as s:
        stale = await company_product_queue.get_proposal(s, me["id"], d["draft_id"])
    assert (await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)).status_code == 200

    async def stale_get(db, owner_id, draft_id):
        return stale

    monkeypatch.setattr(company_product_queue, "get_proposal", stale_get)
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="already decided"):
            await company_product_queue.decide_proposal(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note=None
            )
        await s.rollback()
    monkeypatch.undo()
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "approved"


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    k = "b" * 64
    base = ("INSERT INTO company_proposals (owner_id, draft_id, title_key, title, problem, proposal, "
            "acceptance_check, reference_artifact, size, status) VALUES ")
    bad_rows = [
        f"('o','a','{k}','t','p','pp','ac','ra','huge','drafted')",
        "('o','b','NOTAHASH','t','p','pp','ac','ra','small','drafted')",
        f"('o','c','{k}','t','p','pp','   ','ra','small','drafted')",
        f"('o','d','{k}','t','p','pp','ac','   ','small','drafted')",
        f"('o','e','{k}','t','p','pp','ac','ra','small','approved')",
    ]
    async with AsyncSessionLocal() as s:
        for row in bad_rows:
            with pytest.raises(IntegrityError):
                await s.execute(text(base + row))
            await s.rollback()
        ok = f"('o','f','{k}','t','p','pp','ac','ra','small','drafted')"
        dup = f"('o','g','{k}','t2','p','pp','ac','ra','small','drafted')"
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


async def test_the_same_title_spelled_another_way_is_still_a_duplicate(client, auth_headers):
    import unicodedata

    title = "Caf\u00e9 menu update"
    assert (await client.post(BASE, json={**GOOD, "title": title}, headers=auth_headers)).status_code == 201
    nfd = unicodedata.normalize("NFD", title)
    r = await client.post(BASE, json={**GOOD, "title": nfd}, headers=auth_headers)
    assert r.status_code == 409, r.text
    assert len((await client.get(BASE, headers=auth_headers)).json()) == 1
