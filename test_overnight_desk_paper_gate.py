"""paper.py and live_gate.py of the Overnight Desk, tested against SPEC.md.

Offline. No network, no clock, no files outside tmp_path.
"""
from __future__ import annotations

import copy
import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Appended, never inserted first, so no other top-level name is shadowed.
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from overnight_desk import live_gate, model, paper, positions  # noqa: E402
from overnight_desk.model import (  # noqa: E402
    ExecutorKind,
    ExitReason,
    HumanApproval,
    OrderIntent,
    Side,
    Strategy,
    TokenSnapshot,
    Verification,
)
from overnight_desk.settings import Settings  # noqa: E402

S = Settings.for_tests()  # venue 0.5, pool 1.25, fixed 0.0


def _snap(**kw) -> TokenSnapshot:
    base = dict(ts=1_000, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=0.001)
    base.update(kw)
    return TokenSnapshot(**base)


def _settings(**kw) -> Settings:
    return Settings.for_tests(**kw)


def _intent(side=Side.BUY, usd=100.0, qty=None, order_id="o1", **kw) -> OrderIntent:
    if side is Side.SELL and qty is None:
        qty = 1_000.0
        usd = None
    return OrderIntent(
        order_id=order_id, ts=1_000, mint="MintA", symbol="AAA", side=side,
        reason_code="entry", decision_price=0.001, usd=usd, qty=qty, **kw,
    )


def _buy_fill(usd=100.0, mint="MintA", snap=None, settings=S):
    snap = snap or _snap(mint=mint)
    fill = paper.PaperExecutor(settings).execute(_intent(usd=usd), snap)
    return dataclasses.replace(fill, mint=mint)


def _open(fill, settings=S, snap=None):
    return positions.open_position(fill, snap or _snap(mint=fill.mint), Strategy.DIP, settings)


# --- model_quote: buy -------------------------------------------------------


def test_buy_quote_matches_the_formula_by_hand():
    s = _settings(venue_fee_pct_per_side=1.0, pool_fee_pct_per_side=2.0, fixed_fee_usd_per_side=1.0)
    q = paper.model_quote(Side.BUY, _snap(), s, usd=101.0)
    rq, rt = 20_000.0, 20_000.0 / 0.001
    venue, fixed = 1.01, 1.0
    to_pool = 101.0 - venue - fixed
    pool = 0.02 * to_pool
    eff = to_pool - pool
    qty = rt * eff / (rq + eff)
    assert q.venue_fee_usd == pytest.approx(venue)
    assert q.fixed_fee_usd == fixed
    assert q.pool_fee_usd == pytest.approx(pool)
    assert q.qty == pytest.approx(qty)
    assert q.gross_usd == pytest.approx(to_pool)
    assert q.fill_price == pytest.approx(to_pool / qty)
    assert q.spot_price == 0.001
    assert q.price_impact_pct == pytest.approx((to_pool / qty / 0.001 - 1) * 100)
    assert q.price_impact_pct > 0
    assert q.fees_usd == pytest.approx(venue + pool + fixed)


def test_a_bigger_buy_has_more_impact():
    small = paper.model_quote(Side.BUY, _snap(), S, usd=10.0)
    big = paper.model_quote(Side.BUY, _snap(), S, usd=1_000.0)
    assert big.price_impact_pct > small.price_impact_pct > 0


def test_zero_fees_tiny_buy_fills_near_spot():
    s = _settings(venue_fee_pct_per_side=0, pool_fee_pct_per_side=0, fixed_fee_usd_per_side=0)
    q = paper.model_quote(Side.BUY, _snap(), s, usd=0.01)
    assert q.fill_price == pytest.approx(0.001, rel=1e-5)
    assert q.fees_usd == 0


# --- model_quote: sell ------------------------------------------------------


def test_sell_quote_matches_the_formula_by_hand():
    s = _settings(venue_fee_pct_per_side=1.0, pool_fee_pct_per_side=2.0, fixed_fee_usd_per_side=0.5)
    q = paper.model_quote(Side.SELL, _snap(), s, qty=50_000.0)
    rq, rt = 20_000.0, 20_000.0 / 0.001
    eff = 50_000.0 * 0.98
    gross = rq * eff / (rt + eff)
    assert q.gross_usd == pytest.approx(gross)
    assert q.pool_fee_usd == pytest.approx(50_000.0 * 0.02 * 0.001)
    assert q.venue_fee_usd == pytest.approx(0.01 * gross)
    assert q.fixed_fee_usd == 0.5
    assert q.fill_price == pytest.approx(gross / 50_000.0)
    assert q.qty == 50_000.0
    assert q.price_impact_pct == pytest.approx((gross / 50_000.0 / 0.001 - 1) * 100)
    assert q.price_impact_pct < 0


# --- model_quote: refusals --------------------------------------------------


@pytest.mark.parametrize("liq", [None, 0.0, -1.0])
def test_quote_refuses_missing_or_non_positive_liquidity(liq):
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(liquidity_usd=liq), S, usd=10.0)


@pytest.mark.parametrize("price", [None, 0.0, -0.001])
def test_quote_refuses_missing_or_non_positive_price(price):
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, _snap(price_usd=price), S, qty=10.0)


def test_quote_refuses_both_or_neither_amount():
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), S)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), S, usd=10.0, qty=10.0)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, _snap(), S, usd=10.0, qty=10.0)


def test_a_buy_takes_usd_and_a_sell_takes_qty():
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), S, qty=10.0)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, _snap(), S, usd=10.0)


@pytest.mark.parametrize("amount", [0.0, -1.0, float("nan")])
def test_quote_refuses_a_non_positive_amount(amount):
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), S, usd=amount)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, _snap(), S, qty=amount)


def test_a_buy_eaten_by_fees_is_refused_at_the_boundary():
    s = _settings(fixed_fee_usd_per_side=1.0, venue_fee_pct_per_side=0.0)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), s, usd=1.0)  # to_pool exactly 0
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), s, usd=0.5)  # to_pool negative
    assert paper.model_quote(Side.BUY, _snap(), s, usd=1.01).qty > 0  # just above


def test_quote_mutates_nothing():
    snap = _snap()
    before = copy.deepcopy(snap)
    paper.model_quote(Side.BUY, snap, S, usd=10.0)
    assert snap == before


# --- require_approval -------------------------------------------------------


def test_paper_needs_no_approval():
    paper.require_approval(_intent(), ExecutorKind.PAPER, None)


def test_live_without_approval_is_refused():
    with pytest.raises(paper.ApprovalRequired):
        paper.require_approval(_intent(), ExecutorKind.LIVE, None)


def test_live_with_another_orders_approval_is_refused():
    appr = HumanApproval(order_id="other", approved_by="tee", approved_ts=1)
    with pytest.raises(paper.ApprovalRequired):
        paper.require_approval(_intent(), ExecutorKind.LIVE, appr)


def test_live_with_the_matching_approval_passes_the_gate():
    appr = HumanApproval(order_id="o1", approved_by="tee", approved_ts=1)
    paper.require_approval(_intent(), ExecutorKind.LIVE, appr)


def test_approval_required_is_a_permission_error():
    assert issubclass(paper.ApprovalRequired, PermissionError)
    assert issubclass(paper.PaperError, ValueError)


# --- PaperExecutor ----------------------------------------------------------


def test_executor_kind_is_paper():
    assert paper.PaperExecutor(S).kind is ExecutorKind.PAPER


def test_a_paper_buy_fill():
    snap = _snap()
    fill = paper.PaperExecutor(S).execute(_intent(usd=100.0), snap)
    q = paper.model_quote(Side.BUY, snap, S, usd=100.0)
    assert fill.verification is Verification.PAPER
    assert fill.verification is not Verification.VERIFIED
    assert fill.side is Side.BUY and fill.order_id == "o1" and fill.mint == "MintA"
    assert fill.price == q.fill_price and fill.qty == q.qty
    assert fill.gross_usd == q.gross_usd and fill.fees_usd == q.fees_usd
    assert fill.cash_delta_usd == -100.0
    assert fill.ts == snap.ts
    assert fill.exit_reason is None


def test_a_paper_sell_fill_carries_the_exit_reason():
    snap = _snap()
    intent = _intent(side=Side.SELL, qty=5_000.0, exit_reason=ExitReason.STOP)
    fill = paper.PaperExecutor(S).execute(intent, snap)
    q = paper.model_quote(Side.SELL, snap, S, qty=5_000.0)
    assert fill.exit_reason is ExitReason.STOP
    assert fill.qty == 5_000.0 and fill.price == q.fill_price
    assert fill.cash_delta_usd == pytest.approx(q.gross_usd - q.venue_fee_usd - q.fixed_fee_usd)
    assert fill.fees_usd == q.fees_usd


def test_sell_cash_delta_is_never_below_zero():
    s = _settings(fixed_fee_usd_per_side=1_000.0)
    fill = paper.PaperExecutor(s).execute(_intent(side=Side.SELL, qty=10.0), _snap())
    assert fill.cash_delta_usd == 0.0


def test_executor_needs_usd_for_a_buy_and_qty_for_a_sell():
    ex = paper.PaperExecutor(S)
    with pytest.raises(paper.PaperError):
        ex.execute(_intent(usd=None), _snap())
    sell_no_qty = dataclasses.replace(_intent(side=Side.SELL), qty=None)
    with pytest.raises(paper.PaperError):
        ex.execute(sell_no_qty, _snap())


def test_executor_ignores_a_stray_approval_and_mutates_nothing():
    snap, intent = _snap(), _intent()
    b_snap, b_intent = copy.deepcopy(snap), copy.deepcopy(intent)
    appr = HumanApproval(order_id="zzz", approved_by="x", approved_ts=1)
    paper.PaperExecutor(S).execute(intent, snap, appr)
    assert snap == b_snap and intent == b_intent


def test_executor_propagates_quote_errors():
    with pytest.raises(paper.PaperError):
        paper.PaperExecutor(S).execute(_intent(), _snap(liquidity_usd=None))


# --- Ledger -----------------------------------------------------------------


def test_a_new_ledger_is_flat():
    led = paper.Ledger(1_000.0)
    assert led.cash_usd == 1_000.0 and led.positions == {} and led.fills == []
    assert led.realized_pnl_usd == 0.0 and led.fees_usd == 0.0
    assert led.exposure_usd() == 0.0 and led.equity_usd({}) == 1_000.0


def test_record_buy_moves_cash_and_stores_the_position():
    led = paper.Ledger(1_000.0)
    fill = _buy_fill(100.0)
    pos = _open(fill)
    led.record_buy(fill, pos)
    assert led.cash_usd == pytest.approx(900.0)
    assert led.positions["MintA"] is pos
    assert led.fees_usd == pytest.approx(fill.fees_usd)
    assert led.fills == [fill]
    assert led.exposure_usd() == pytest.approx(100.0)


def test_record_buy_refuses_a_sell_fill():
    led = paper.Ledger(1_000.0)
    sell = paper.PaperExecutor(S).execute(_intent(side=Side.SELL, qty=10.0), _snap())
    with pytest.raises(paper.PaperError):
        led.record_buy(sell, _open(_buy_fill()))
    assert led.fills == [] and led.cash_usd == 1_000.0


def test_record_buy_never_averages_down():
    led = paper.Ledger(1_000.0)
    fill = _buy_fill(100.0)
    led.record_buy(fill, _open(fill))
    with pytest.raises(paper.PaperError):
        led.record_buy(fill, _open(fill))
    assert led.cash_usd == pytest.approx(900.0) and len(led.fills) == 1


def test_record_buy_cost_at_cash_just_below_and_just_above():
    fill = _buy_fill(100.0)
    pos = _open(fill)
    at = paper.Ledger(100.0)
    at.record_buy(fill, pos)  # exactly the cost: allowed
    assert at.cash_usd == pytest.approx(0.0)
    with pytest.raises(paper.PaperError):
        paper.Ledger(99.99).record_buy(fill, pos)
    paper.Ledger(100.01).record_buy(fill, pos)


def _sell_fill(qty, mint="MintA", snap=None):
    f = paper.PaperExecutor(S).execute(_intent(side=Side.SELL, qty=qty), snap or _snap())
    return dataclasses.replace(f, mint=mint)


def test_record_sell_partial_then_full():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    pos = _open(buy)
    led.record_buy(buy, pos)
    half = _sell_fill(buy.qty / 2)
    pnl1 = led.record_sell(half)
    assert pnl1 == pytest.approx(positions.realized_pnl(pos, half))
    assert "MintA" in led.positions
    assert led.positions["MintA"].qty == pytest.approx(buy.qty / 2)
    assert led.cash_usd == pytest.approx(900.0 + half.cash_delta_usd)
    rest = led.positions["MintA"]
    rest_fill = _sell_fill(rest.qty)
    pnl2 = led.record_sell(rest_fill)
    assert "MintA" not in led.positions
    assert led.realized_pnl_usd == pytest.approx(pnl1 + pnl2)
    assert led.fees_usd == pytest.approx(buy.fees_usd + half.fees_usd + rest_fill.fees_usd)
    assert len(led.fills) == 3
    assert pos.qty == buy.qty  # the original position is not mutated


def test_record_sell_without_a_position_is_refused():
    led = paper.Ledger(1_000.0)
    with pytest.raises(paper.PaperError):
        led.record_sell(_sell_fill(10.0))
    assert led.fills == [] and led.cash_usd == 1_000.0


def test_record_sell_oversell_is_refused_and_changes_nothing():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    led.record_buy(buy, _open(buy))
    cash = led.cash_usd
    with pytest.raises(positions.PositionError):
        led.record_sell(_sell_fill(buy.qty * 2))
    assert led.cash_usd == cash and len(led.fills) == 1 and "MintA" in led.positions


def test_a_round_trip_at_the_same_price_loses_the_costs():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    led.record_buy(buy, _open(buy))
    pnl = led.record_sell(_sell_fill(buy.qty))
    assert pnl < 0
    assert led.cash_usd == pytest.approx(1_000.0 + pnl)
    assert led.positions == {}


def test_equity_uses_price_or_falls_back_to_cost():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    pos = _open(buy)
    led.record_buy(buy, pos)
    assert led.equity_usd({}) == pytest.approx(900.0 + pos.cost_usd)
    assert led.equity_usd({"MintA": 0.5}) == pytest.approx(900.0 + pos.qty * 0.5)
    assert led.equity_usd({"Other": 9.0}) == pytest.approx(900.0 + pos.cost_usd)


def test_view_reports_the_account():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    pos = _open(buy)
    led.record_buy(buy, pos)
    prices = {"MintA": 0.002}
    v = led.view(prices, 1_000.0)
    assert v.free_cash_usd == pytest.approx(900.0)
    assert v.open_positions == 1
    assert v.exposure_usd == pytest.approx(pos.cost_usd)
    assert v.equity_usd == pytest.approx(900.0 + pos.qty * 0.002)
    assert v.night_start_equity_usd == 1_000.0
    assert v.night_pnl_usd == pytest.approx(v.equity_usd - 1_000.0)
    assert isinstance(v, model.PortfolioView)


def test_view_mutates_nothing():
    led = paper.Ledger(500.0)
    prices = {"MintA": 1.0}
    before = dict(prices)
    led.view(prices, 500.0)
    assert prices == before and led.cash_usd == 500.0


# --- live_gate --------------------------------------------------------------


def _gate(nights=3, tests=True, typed=True, exists=True, approval=True, settings=S):
    return live_gate.live_gate_blockers(nights, tests, typed, exists, approval, settings)


def test_the_gate_opens_only_when_every_condition_holds():
    assert _gate() == ()


def test_all_blockers_in_the_stated_order():
    assert _gate(0, False, False, False, False) == (
        "paper_nights_short",
        "acceptance_tests_not_passed",
        "owner_has_not_typed_live",
        "no_live_executor",
        "no_per_order_approval",
    )


@pytest.mark.parametrize(
    "kw,code",
    [
        (dict(tests=False), "acceptance_tests_not_passed"),
        (dict(typed=False), "owner_has_not_typed_live"),
        (dict(exists=False), "no_live_executor"),
        (dict(approval=False), "no_per_order_approval"),
    ],
)
def test_each_blocker_alone(kw, code):
    assert _gate(**kw) == (code,)


def test_paper_nights_below_at_and_above_the_requirement():
    s = _settings(paper_nights_required=3)
    assert _gate(nights=2, settings=s) == ("paper_nights_short",)
    assert _gate(nights=3, settings=s) == ()
    assert _gate(nights=4, settings=s) == ()


def test_the_nights_threshold_comes_from_settings():
    s = _settings(paper_nights_required=5)
    assert _gate(nights=4, settings=s) == ("paper_nights_short",)
    assert _gate(nights=5, settings=s) == ()


def test_the_build_has_no_live_executor_so_the_gate_stays_shut():
    assert "no_live_executor" in _gate(exists=False)
    assert not hasattr(paper, "LiveExecutor")


def test_gate_returns_a_tuple():
    assert isinstance(_gate(), tuple)
    assert isinstance(_gate(nights=0), tuple)


# --- contract tightening and mutation gaps ----------------------------------

NAN = float("nan")


def test_p1_exact_buy_and_sell_from_the_spec_formulas_by_hand():
    # Pool: L = 20_000, price 0.001. Rq = L / 2 = 10_000 dollars and
    # Rt = Rq / price = 10_000_000 tokens. v = 20%, p = 20%, f = 250.
    s = _settings(venue_fee_pct_per_side=20.0, pool_fee_pct_per_side=20.0, fixed_fee_usd_per_side=250.0)
    snap = _snap(liquidity_usd=20_000.0, price_usd=0.001)
    # BUY usd = 15_937.5:
    #   venue = 0.2 * 15_937.5 = 3_187.5, fixed = 250
    #   to_pool = 15_937.5 - 3_187.5 - 250 = 12_500
    #   pool fee = 0.2 * 12_500 = 2_500, effective = 10_000
    #   qty = 10_000_000 * 10_000 / (10_000 + 10_000) = 5_000_000
    #   gross = 12_500, fill price = 12_500 / 5_000_000 = 0.0025
    #   impact = (0.0025 / 0.001 - 1) * 100 = 150
    b = paper.model_quote(Side.BUY, snap, s, usd=15_937.5)
    assert b.qty == pytest.approx(5_000_000.0)
    assert b.gross_usd == pytest.approx(12_500.0)
    assert b.venue_fee_usd == pytest.approx(3_187.5)
    assert b.pool_fee_usd == pytest.approx(2_500.0)
    assert b.fixed_fee_usd == 250.0
    assert b.fill_price == pytest.approx(0.0025)
    assert b.price_impact_pct == pytest.approx(150.0)
    assert b.fees_usd == pytest.approx(5_937.5)
    # SELL qty = 12_500_000:
    #   effective = 12_500_000 * (1 - 0.2) = 10_000_000
    #   gross = 10_000 * 10_000_000 / (10_000_000 + 10_000_000) = 5_000
    #   pool fee = 12_500_000 * 0.2 * 0.001 = 2_500
    #   venue = 0.2 * 5_000 = 1_000, fixed = 250
    #   fill price = 5_000 / 12_500_000 = 0.0004
    #   impact = (0.0004 / 0.001 - 1) * 100 = -60
    q = paper.model_quote(Side.SELL, snap, s, qty=12_500_000.0)
    assert q.qty == 12_500_000.0
    assert q.gross_usd == pytest.approx(5_000.0)
    assert q.pool_fee_usd == pytest.approx(2_500.0)
    assert q.venue_fee_usd == pytest.approx(1_000.0)
    assert q.fixed_fee_usd == 250.0
    assert q.fill_price == pytest.approx(0.0004)
    assert q.price_impact_pct == pytest.approx(-60.0)
    # The executor turns the SELL into cash 5_000 - 1_000 - 250 = 3_750.
    fill = paper.PaperExecutor(s).execute(_intent(side=Side.SELL, qty=12_500_000.0), snap)
    assert fill.cash_delta_usd == pytest.approx(3_750.0)
    assert fill.fees_usd == pytest.approx(3_750.0)


@pytest.mark.parametrize("bad", [0.0, NAN])
@pytest.mark.parametrize("field", ["liquidity_usd", "price_usd"])
def test_p2_zero_and_nan_liquidity_or_price_are_refused_on_both_sides(field, bad):
    snap = _snap(**{field: bad})
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, snap, S, usd=10.0)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, snap, S, qty=10.0)


def test_an_order_that_underflows_to_zero_tokens_is_a_paper_error():
    s = _settings(venue_fee_pct_per_side=0, pool_fee_pct_per_side=0, fixed_fee_usd_per_side=0)
    snap = _snap(liquidity_usd=20_000.0, price_usd=1e300)  # Rt = 1e-296
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, snap, s, usd=1e-30)  # 1e-296 * 1e-30 underflows to 0.0


@pytest.mark.parametrize(
    "field",
    ["venue_fee_pct_per_side", "pool_fee_pct_per_side", "fixed_fee_usd_per_side"],
)
def test_c3_a_missing_fee_setting_is_a_paper_error_not_an_assertion(field):
    s = dataclasses.replace(S, **{field: None})
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.BUY, _snap(), s, usd=10.0)
    with pytest.raises(paper.PaperError):
        paper.model_quote(Side.SELL, _snap(), s, qty=10.0)


def test_c1_the_executor_refuses_a_snapshot_of_another_coin():
    ex = paper.PaperExecutor(S)
    with pytest.raises(paper.PaperError):
        ex.execute(_intent(), _snap(mint="MintB"))
    with pytest.raises(paper.PaperError):
        ex.execute(_intent(side=Side.SELL, qty=10.0), _snap(mint="MintB"))


def test_m3_the_fill_ts_is_the_snapshots_not_the_intents():
    fill = paper.PaperExecutor(S).execute(_intent(), _snap(ts=7_777))  # intent.ts is 1_000
    assert fill.ts == 7_777
    sell = paper.PaperExecutor(S).execute(_intent(side=Side.SELL, qty=10.0), _snap(ts=8_888))
    assert sell.ts == 8_888


def test_c2_record_buy_refuses_a_position_of_another_coin():
    led = paper.Ledger(1_000.0)
    fill = _buy_fill(100.0)
    other = _open(dataclasses.replace(fill, mint="MintB"))
    with pytest.raises(paper.PaperError):
        led.record_buy(fill, other)
    assert led.cash_usd == 1_000.0 and led.positions == {} and led.fills == []


def test_m4_a_price_of_zero_values_the_position_at_zero():
    led = paper.Ledger(1_000.0)
    buy = _buy_fill(100.0)
    led.record_buy(buy, _open(buy))
    assert led.equity_usd({"MintA": 0.0}) == pytest.approx(900.0)


@pytest.mark.parametrize(
    "kw",
    [
        dict(tests=None),
        dict(typed=None),
        dict(exists=None),
        dict(approval=None),
        dict(tests=1),
        dict(typed="yes"),
        dict(exists=1),
        dict(approval="yes"),
    ],
)
def test_m6_to_m9_only_exactly_true_clears_a_blocker(kw):
    blockers = _gate(**kw)
    assert len(blockers) == 1
    assert blockers == _gate(**{k: False for k in kw})
