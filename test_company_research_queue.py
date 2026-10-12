"""The Research findings queue's storage and routes. Needs the database.

Pinned: a bad finding never reaches the table, a claim is recorded once per
account, an unverified finding cannot be adopted silently, a decision records
the signed-in account and happens once, one account never sees or decides
another's findings, and no route acts on a finding.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

GOOD = {
    "claim": "Mid-career PMs search for AI career strategy more than for AI tools.",
    "evidence_kind": "source",
    "evidence_ref": "https://example.com/report?year=2026#section-3",
    "evidence_excerpt": "Searches for career strategy rose 40% year over year.",
    "recommendation": "Lead the next TQO episode with the career strategy angle.",
}
UNVERIFIED = {**GOOD, "claim": "Older viewers prefer the longer episodes.",
              "evidence_kind": "unverified",
              "evidence_ref": "Needs the channel analytics export to settle."}
BASE = "/api/v1/company/research/findings"


async def test_a_clean_finding_is_stored_as_drafted_and_listed(client, auth_headers):
    r = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "drafted" and body["decided_by"] is None
    listed = (await client.get(BASE, headers=auth_headers)).json()
    assert [d["draft_id"] for d in listed] == [body["draft_id"]]


@pytest.mark.parametrize("patch", [
    {"evidence_kind": "rumour"},
    {"evidence_ref": "http://example.com/plain"},
    {"evidence_ref": "https://exa mple.com/x"},
    {"claim": "short"},
    {"recommendation": "short"},
    {"claim": "a — b claim that is long enough"},
    {"claim": "a\x00b claim that is long enough"},
])
async def test_refused_findings_never_reach_the_table(client, auth_headers, patch):
    r = await client.post(BASE, json={**GOOD, **patch}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(BASE, headers=auth_headers)).json() == []


async def test_oversized_fields_are_refused(client, auth_headers):
    r = await client.post(BASE, json={**GOOD, "evidence_excerpt": "x" * 8001}, headers=auth_headers)
    assert r.status_code == 422, r.text


async def test_a_claim_is_recorded_once_whatever_state_its_finding_is_in(client, auth_headers):
    first = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    again = await client.post(BASE, json=GOOD, headers=auth_headers)
    assert again.status_code == 409 and "already on record" in again.text
    spaced = {**GOOD, "claim": GOOD["claim"].upper().replace(" ", "  ")}
    assert (await client.post(BASE, json=spaced, headers=auth_headers)).status_code == 409
    await client.post(f"{BASE}/{first['draft_id']}/reject", json={}, headers=auth_headers)
    assert (await client.post(BASE, json=GOOD, headers=auth_headers)).status_code == 409
    assert len((await client.get(BASE, headers=auth_headers)).json()) == 1


async def test_the_same_claim_is_allowed_for_a_different_account(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_research_queue import insert_finding

    await client.post(BASE, json=GOOD, headers=auth_headers)
    async with AsyncSessionLocal() as s:
        other = await insert_finding(s, "some-other-account", **GOOD)
        await s.commit()
    assert other.claim == GOOD["claim"]


async def test_adoption_records_the_signed_in_account_once(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={"note": "adopt"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["decided_by"] == me["email"]
    again = await client.post(f"{BASE}/{d['draft_id']}/reject", json={}, headers=auth_headers)
    assert again.status_code == 409


async def test_an_unverified_finding_is_not_adopted_without_a_note(client, auth_headers):
    d = (await client.post(BASE, json=UNVERIFIED, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)
    assert r.status_code == 409 and "unverified" in r.text
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "drafted"
    ok = await client.post(f"{BASE}/{d['draft_id']}/approve",
                           json={"note": "Adopting as a lead, not a fact."}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


async def test_dismissal_is_recorded_and_filterable(client, auth_headers):
    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    r = await client.post(f"{BASE}/{d['draft_id']}/reject", json={"note": "not useful"}, headers=auth_headers)
    assert r.json()["status"] == "rejected" and r.json()["decision_note"] == "not useful"
    assert (await client.get(BASE + "?status=drafted", headers=auth_headers)).json() == []
    assert len((await client.get(BASE + "?status=rejected", headers=auth_headers)).json()) == 1


async def test_unknown_finding_is_404(client, auth_headers):
    assert (await client.post(f"{BASE}/nope/approve", json={}, headers=auth_headers)).status_code == 404


async def test_routes_need_a_session(client):
    assert (await client.get(BASE)).status_code in (401, 403)
    assert (await client.post(BASE, json=GOOD)).status_code in (401, 403)


async def test_one_account_cannot_see_or_decide_another_accounts_finding(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.services.company_research_queue import insert_finding

    async with AsyncSessionLocal() as s:
        other = await insert_finding(s, "some-other-account", **GOOD)
        await s.commit()
    assert (await client.get(BASE, headers=auth_headers)).json() == []
    r = await client.post(f"{BASE}/{other.draft_id}/approve", json={}, headers=auth_headers)
    assert r.status_code == 404


async def test_two_simultaneous_decisions_cannot_both_win(client, auth_headers, monkeypatch):
    """The python guard sees a stale 'drafted' copy in a race. The SQL guard must still refuse."""
    from app.db.session import AsyncSessionLocal
    from app.services import company_research_queue
    from services.company.marketing import QueueRefusal

    d = (await client.post(BASE, json=GOOD, headers=auth_headers)).json()
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as s:
        stale = await company_research_queue.get_finding(s, me["id"], d["draft_id"])
    assert (await client.post(f"{BASE}/{d['draft_id']}/approve", json={}, headers=auth_headers)).status_code == 200

    async def stale_get(db, owner_id, draft_id):
        return stale

    monkeypatch.setattr(company_research_queue, "get_finding", stale_get)
    async with AsyncSessionLocal() as s:
        with pytest.raises(QueueRefusal, match="already decided"):
            await company_research_queue.decide_finding(
                s, me["id"], d["draft_id"], approved=False, decided_by="Tee", note=None
            )
        await s.rollback()
    monkeypatch.undo()
    assert (await client.get(BASE, headers=auth_headers)).json()[0]["status"] == "approved"


async def test_the_table_refuses_a_row_a_caller_wrote_around_the_rules(client, auth_headers):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import AsyncSessionLocal

    k = "a" * 64
    base = ("INSERT INTO company_findings (owner_id, draft_id, claim_key, claim, evidence_kind, "
            "evidence_ref, recommendation, status) VALUES ")
    bad_rows = [
        f"('o','a','{k}','c','rumour','ref text here','r','drafted')",
        f"('o','b','{k}','c','source','http://plain.example.com','r','drafted')",
        f"('o','c','{k}','c','source','https://has space.example.com','r','drafted')",
        "('o','d','NOTAHASH','c','measured','ref text here','r','drafted')",
        f"('o','e','{k}','c','measured','   ','r','drafted')",
        f"('o','f','{k}','c','measured','ref text here','r','approved')",
    ]
    async with AsyncSessionLocal() as s:
        for row in bad_rows:
            with pytest.raises(IntegrityError):
                await s.execute(text(base + row))
            await s.rollback()
        ok = f"('o','g','{k}','c','measured','ref text here','r','drafted')"
        dup = f"('o','h','{k}','c2','measured','ref text here','r','drafted')"
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


async def test_the_same_claim_spelled_another_way_is_still_a_duplicate(client, auth_headers):
    import unicodedata

    assert (await client.post(BASE, json=GOOD, headers=auth_headers)).status_code == 201
    for claim in (unicodedata.normalize("NFD", GOOD["claim"].replace("PMs", "caf\u00e9s")),):
        first = await client.post(BASE, json={**GOOD, "claim": GOOD["claim"].replace("PMs", "caf\u00e9s")},
                                  headers=auth_headers)
        again = await client.post(BASE, json={**GOOD, "claim": claim}, headers=auth_headers)
        assert first.status_code == 201 and again.status_code == 409, again.text
    zw = GOOD["claim"][:10] + "\u200b" + GOOD["claim"][10:]
    assert (await client.post(BASE, json={**GOOD, "claim": zw}, headers=auth_headers)).status_code == 422
