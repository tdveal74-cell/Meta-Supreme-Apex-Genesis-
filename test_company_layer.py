"""The company layer: six functions beside the Council, and the Ops and Finance scoreboard.

Claims pinned here, each one a thing a refactor could quietly falsify:

  1. Business functions never join the Council. AGENT_REGISTRY stays nine and
     shares no slug with a company function, because the full council flag, the
     spend cap arithmetic and test_intelligence_api.py all assume nine.
  2. Revenue that was not measured is None, never zero. A zero would read as a
     measurement and a plausible invented number is the failure to prevent.
  3. Status is honest: only ops_finance is built, and its built_in file exists.
  4. The scoreboard route is read only and reports the same cap /usage enforces.
"""

from __future__ import annotations

import pathlib

import pytest

from services.agents.registry import AGENT_REGISTRY
from services.company.functions import (
    COMPANY_FUNCTIONS,
    TARGET_MONTHLY_USD,
    Impact,
    Status,
    list_functions,
)
from services.company.scoreboard import build_scoreboard

ROOT = pathlib.Path(__file__).resolve().parent


def test_the_council_stays_nine_and_shares_no_slug():
    assert len(AGENT_REGISTRY) == 9
    assert not set(AGENT_REGISTRY) & set(COMPANY_FUNCTIONS)


def test_six_functions_in_ruled_build_order():
    funcs = list_functions()
    assert len(funcs) == 6
    assert [f.slug for f in funcs][:4] == ["ops_finance", "marketing", "sales", "support"]


def test_only_a_function_with_code_is_marked_built_or_partial():
    with_code = [f for f in COMPANY_FUNCTIONS.values() if f.status is not Status.PLANNED]
    assert {f.slug: f.status for f in with_code} == {
        "ops_finance": Status.BUILT,
        "marketing": Status.PARTIAL,
        "sales": Status.PARTIAL,
        "support": Status.PARTIAL,
        "research": Status.PARTIAL,
        "product": Status.PARTIAL,
    }
    for f in with_code:
        assert (ROOT / f.built_in).is_file()
    assert all(f.built_in is None for f in COMPANY_FUNCTIONS.values() if f.status is Status.PLANNED)


def test_outward_functions_stay_gated_above_read():
    assert COMPANY_FUNCTIONS["marketing"].max_impact is Impact.HIGH_IMPACT
    assert COMPANY_FUNCTIONS["sales"].max_impact is Impact.HIGH_IMPACT
    assert COMPANY_FUNCTIONS["ops_finance"].max_impact is Impact.READ


def test_unmeasured_revenue_is_none_not_zero():
    b = build_scoreboard(revenue_month_usd=None, calls_today=0, tokens_today=0, cap_tokens=500_000)
    assert b.revenue_month_usd is None and b.revenue_measured is False
    assert b.gap_to_target_usd is None and b.pct_of_target is None
    assert any("not measured" in n for n in b.notes)


def test_measured_zero_revenue_is_a_real_zero_with_full_gap():
    b = build_scoreboard(revenue_month_usd=0.0, calls_today=0, tokens_today=0, cap_tokens=None)
    assert b.revenue_measured is True
    assert b.gap_to_target_usd == TARGET_MONTHLY_USD and b.pct_of_target == 0.0


def test_gap_and_percent_from_measured_revenue():
    b = build_scoreboard(revenue_month_usd=2_500.0, calls_today=3, tokens_today=125_000, cap_tokens=500_000)
    assert b.gap_to_target_usd == 7_500.0 and b.pct_of_target == 25.0
    assert b.spend_headroom_tokens == 375_000 and b.cap_pct_used == 25.0


def test_over_target_gap_floors_at_zero_and_negative_revenue_refused():
    assert build_scoreboard(revenue_month_usd=12_000.0, calls_today=0, tokens_today=0, cap_tokens=None).gap_to_target_usd == 0.0
    with pytest.raises(ValueError):
        build_scoreboard(revenue_month_usd=-1.0, calls_today=0, tokens_today=0, cap_tokens=None)


def test_overspent_cap_headroom_floors_at_zero():
    b = build_scoreboard(revenue_month_usd=None, calls_today=1, tokens_today=600_000, cap_tokens=500_000)
    assert b.spend_headroom_tokens == 0 and b.cap_pct_used == 120.0


def test_company_layer_cannot_reach_the_network():
    import ast

    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp"}
    for path in (ROOT / "services" / "company").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            assert not banned & set(mods), f"{path.name} imports {banned & set(mods)}"


@pytest.mark.asyncio
async def test_functions_route_lists_six_without_a_session(client):
    r = await client.get("/api/v1/company/functions")
    assert r.status_code == 200, r.text
    assert len(r.json()) == 6


@pytest.mark.asyncio
async def test_scoreboard_route_reports_unmeasured_revenue_and_the_enforced_cap(client, auth_headers, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 1_234)
    r = await client.get("/api/v1/company/scoreboard", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["revenue_month_usd"] is None and body["revenue_measured"] is False
    assert body["spend_cap_tokens"] == 1_234
    assert body["target_monthly_usd"] == TARGET_MONTHLY_USD


@pytest.mark.asyncio
async def test_scoreboard_route_needs_a_session(client):
    assert (await client.get("/api/v1/company/scoreboard")).status_code in (401, 403)
