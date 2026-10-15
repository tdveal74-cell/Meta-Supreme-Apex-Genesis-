"""Scoreboard revenue from Stripe: the counting rules, the reader, and the route. No real network."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.services import company_revenue
from app.services.company_revenue import MAX_PAGES, PAGE_LIMIT, read_month_revenue
from services.company.revenue import RevenueUnreadable, sum_month_revenue

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
KEY = "rk_live_" + "x" * 24


def charge(id_="ch_1", amount=10000, refunded=0, status="succeeded", paid=True, currency="usd", **extra):
    return {"id": id_, "amount": amount, "amount_refunded": refunded, "status": status,
            "paid": paid, "currency": currency, **extra}


# ---- the counting rules

def test_no_charges_is_a_measured_zero():
    r = sum_month_revenue([])
    assert r.revenue_usd == 0.0 and r.charge_count == 0


def test_paid_charges_sum_in_dollars_net_of_refunds():
    r = sum_month_revenue([charge("a", 10000), charge("b", 2550, refunded=550)])
    assert r.revenue_usd == 120.0 and r.charge_count == 2


@pytest.mark.parametrize("c", [
    charge(status="failed"), charge(status="pending"), charge(paid=False),
])
def test_unpaid_or_unsucceeded_charges_do_not_count(c):
    assert sum_month_revenue([c]).revenue_usd == 0.0


def test_a_disputed_charge_counts_at_face_value_and_says_so():
    r = sum_month_revenue([charge(disputed=True)])
    assert r.revenue_usd == 100.0 and r.disputed_count == 1
    assert "disputed" in r.notes[0]


@pytest.mark.parametrize("bad", [
    charge(currency="eur"),
    charge(amount="100"), charge(amount=None), charge(amount=-5), charge(amount=True),
    charge(refunded=None), charge(amount=100, refunded=200),
    "not a dict",
])
def test_anything_uncountable_is_refused_rather_than_guessed(bad):
    with pytest.raises(RevenueUnreadable):
        sum_month_revenue([bad])


def test_a_foreign_currency_charge_that_failed_is_ignored_not_refused():
    assert sum_month_revenue([charge(currency="eur", status="failed")]).revenue_usd == 0.0


# ---- the reader

def stripe(pages):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        i = len(seen) - 1
        if i >= len(pages):
            return httpx.Response(500)
        page = pages[i]
        if isinstance(page, int):
            return httpx.Response(page)
        return httpx.Response(200, json=page)

    return httpx.MockTransport(handler), seen


@pytest.mark.asyncio
async def test_no_key_is_not_measured_and_makes_no_request(monkeypatch):
    monkeypatch.setattr(company_revenue.settings, "STRIPE_READ_KEY", None, raising=False)
    transport, seen = stripe([])
    rev, notes = await read_month_revenue(NOW, transport=transport)
    assert rev is None and seen == [] and "not connected" in notes[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["sk_live_" + "x" * 24, "rk_test_" + "x" * 24, "pk_live_abc", "garbage"])
async def test_only_a_live_restricted_key_is_accepted(key):
    transport, seen = stripe([])
    rev, notes = await read_month_revenue(NOW, key=key, transport=transport)
    assert rev is None and seen == [] and "rk_live_" in notes[0]
    assert key not in " ".join(notes)


@pytest.mark.asyncio
async def test_reads_one_page_from_the_start_of_the_month():
    transport, seen = stripe([{"data": [charge("a", 5000), charge("b", 7000)], "has_more": False}])
    rev, notes = await read_month_revenue(NOW, key=KEY, transport=transport)
    assert rev == 120.0
    req = seen[0]
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.method == "GET" and req.url.params["created[gte]"] == "1790812800"
    assert "2 paid charge(s) since 2026-10-01" in notes[0]
    assert KEY not in " ".join(notes)


@pytest.mark.asyncio
async def test_follows_pagination_with_starting_after():
    transport, seen = stripe([
        {"data": [charge("a", 1000)], "has_more": True},
        {"data": [charge("b", 2000)], "has_more": False},
    ])
    rev, _ = await read_month_revenue(NOW, key=KEY, transport=transport)
    assert rev == 30.0 and seen[1].url.params["starting_after"] == "a"


@pytest.mark.asyncio
@pytest.mark.parametrize("pages,needle", [
    ([401], "HTTP 401"),
    ([500], "HTTP 500"),
    ([{"data": "nope"}], "unreadable"),
    ([{"data": [charge(currency="eur")], "has_more": False}], "not in USD"),
    ([{"data": [], "has_more": True}], "pagination"),
])
async def test_every_failure_is_not_measured_never_zero(pages, needle):
    transport, _ = stripe(pages)
    rev, notes = await read_month_revenue(NOW, key=KEY, transport=transport)
    assert rev is None and needle in notes[0]


@pytest.mark.asyncio
async def test_a_network_error_is_not_measured():
    def boom(request):
        raise httpx.ConnectError("down")

    rev, notes = await read_month_revenue(NOW, key=KEY, transport=httpx.MockTransport(boom))
    assert rev is None and "read failed" in notes[0]


@pytest.mark.asyncio
async def test_too_many_pages_is_not_measured():
    pages = [{"data": [charge(f"c{i}", 100)], "has_more": True} for i in range(MAX_PAGES + 2)]
    transport, seen = stripe(pages)
    rev, notes = await read_month_revenue(NOW, key=KEY, transport=transport)
    assert rev is None and len(seen) == MAX_PAGES
    assert str(MAX_PAGES * PAGE_LIMIT) in notes[0]


# ---- the route

@pytest.mark.asyncio
async def test_scoreboard_route_shows_measured_revenue(client, auth_headers, monkeypatch):
    async def fake(now=None, **kw):
        return 250.0, ["Revenue read from Stripe (live): 3 paid charge(s) since 2026-10-01 UTC."]

    import app.api.v1.company as route

    monkeypatch.setattr(route, "read_month_revenue", fake)
    body = (await client.get("/api/v1/company/scoreboard", headers=auth_headers)).json()
    assert body["revenue_measured"] is True and body["revenue_month_usd"] == 250.0
    assert body["pct_of_target"] == 2.5
    assert any("Stripe" in n for n in body["notes"])


@pytest.mark.asyncio
async def test_scoreboard_route_without_a_key_stays_not_measured(client, auth_headers, monkeypatch):
    monkeypatch.setattr(company_revenue.settings, "STRIPE_READ_KEY", None, raising=False)
    body = (await client.get("/api/v1/company/scoreboard", headers=auth_headers)).json()
    assert body["revenue_month_usd"] is None and body["revenue_measured"] is False
