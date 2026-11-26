"""Tests for the Overnight Desk brain (ticket sizing) and entry rules.

Offline. Every rule and reason code in SPEC.md's brain.py and entry.py
sections, with each threshold tested just below, exactly at and just above.
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

from overnight_desk import brain, entry, model  # noqa: E402
from overnight_desk.model import ExecutorKind, Strategy  # noqa: E402
from overnight_desk.settings import Settings  # noqa: E402

S = Settings.for_tests()
TS = 100_000


# --- entry helpers ----------------------------------------------------------


def dip_snap(**kw) -> model.TokenSnapshot:
    """A snapshot on which DIP fires: 20% pullback, sellers dried up, age 1000s."""
    base = dict(
        ts=TS, mint="MintA", symbol="AAA", pool_created_ts=TS - 1_000,
        liquidity_usd=40_000.0, price_usd=80.0, high_10m_usd=100.0,
        sell_volume_5m_usd=10.0, sell_volume_prev_5m_usd=100.0,
        from_pumpfun_graduation=True,
    )
    base.update(kw)
    return model.TokenSnapshot(**base)


def aged(age: int, **kw) -> model.TokenSnapshot:
    return dip_snap(pool_created_ts=TS - age, **kw)


def code(snap, strategy=Strategy.DIP, settings=S):
    return entry.entry_signal(snap, strategy, settings).reason_code


# --- entry_signal -----------------------------------------------------------


def test_dip_fires_when_every_check_passes():
    sig = entry.entry_signal(dip_snap(), Strategy.DIP, S)
    assert sig.fires is True and sig.reason_code == "entry" and sig.strategy is Strategy.DIP


def test_grad_fires_when_every_check_passes():
    sig = entry.entry_signal(dip_snap(), Strategy.GRAD, S)
    assert sig.fires is True and sig.reason_code == "entry"


@pytest.mark.parametrize("strategy", [Strategy.NEWS, Strategy.COPY, Strategy.WAVE, Strategy.TREND])
def test_unbuilt_strategies_answer_strategy_not_built(strategy):
    sig = entry.entry_signal(dip_snap(), strategy, S)
    assert (sig.fires, sig.reason_code) == (False, "strategy_not_built")


@pytest.mark.parametrize(
    "field",
    ["price_usd", "high_10m_usd", "pool_created_ts", "liquidity_usd",
     "sell_volume_5m_usd", "sell_volume_prev_5m_usd"],
)
@pytest.mark.parametrize("strategy", [Strategy.DIP, Strategy.GRAD])
def test_each_missing_dip_input_is_dip_data_missing(field, strategy):
    sig = entry.entry_signal(dip_snap(**{field: None}), strategy, S)
    assert (sig.fires, sig.reason_code) == (False, "dip_data_missing")
    assert field in sig.detail


@pytest.mark.parametrize("strategy", [Strategy.DIP, Strategy.GRAD])
def test_a_snapshot_with_every_optional_field_none_never_fires(strategy):
    bare = model.TokenSnapshot(ts=TS, mint="M", symbol="X")
    sig = entry.entry_signal(bare, strategy, S)
    assert (sig.fires, sig.reason_code) == (False, "dip_data_missing")


@pytest.mark.parametrize("high", [0.0, -1.0])
def test_a_non_positive_ten_minute_high_is_dip_data_missing(high):
    assert code(dip_snap(high_10m_usd=high)) == "dip_data_missing"


def test_a_tiny_positive_ten_minute_high_is_not_missing_data():
    assert code(dip_snap(high_10m_usd=1e-9, price_usd=1e-9)) != "dip_data_missing"


@pytest.mark.parametrize(
    "age,expected",
    [(599, "age_outside_window"), (600, "entry"), (601, "entry"),
     (21_599, "entry"), (21_600, "entry"), (21_601, "age_outside_window")],
)
def test_dip_pool_age_window_is_inclusive_at_both_ends(age, expected):
    assert code(aged(age)) == expected


@pytest.mark.parametrize(
    "liq,expected",
    [(19_999.99, "liquidity_below_floor"), (20_000.0, "entry"), (20_000.01, "entry")],
)
def test_dip_liquidity_floor(liq, expected):
    assert code(dip_snap(liquidity_usd=liq)) == expected


def test_grad_does_not_apply_the_dip_age_window_or_liquidity_floor():
    # 300s is outside the DIP window and 100 is under the floor; GRAD checks neither.
    assert code(aged(900, liquidity_usd=100.0), Strategy.GRAD) == "entry"
    assert code(aged(30_000), Strategy.GRAD) == "entry"


def test_grad_graduation_unknown_and_not_a_graduation():
    assert code(dip_snap(from_pumpfun_graduation=None), Strategy.GRAD) == "graduation_unknown"
    assert code(dip_snap(from_pumpfun_graduation=False), Strategy.GRAD) == "not_a_graduation"


def test_dip_ignores_the_graduation_flag():
    assert code(dip_snap(from_pumpfun_graduation=None), Strategy.DIP) == "entry"
    assert code(dip_snap(from_pumpfun_graduation=False), Strategy.DIP) == "entry"


@pytest.mark.parametrize(
    "age,expected", [(599, "grad_wait"), (600, "entry"), (601, "entry")]
)
def test_grad_wait_until_the_scanner_watch_is_over(age, expected):
    assert code(aged(age), Strategy.GRAD) == expected


@pytest.mark.parametrize(
    "price,expected",
    [(85.01, "no_dip"), (85.0, "entry"), (84.99, "entry")],
)
def test_the_dip_must_be_at_least_dip_from_high_pct(price, expected):
    # high 100, so the pullback is 100 - price percent; the limit is 15.
    assert code(dip_snap(price_usd=price)) == expected
    assert code(dip_snap(price_usd=price), Strategy.GRAD) == expected


def test_a_price_above_the_high_is_no_dip():
    assert code(dip_snap(price_usd=120.0)) == "no_dip"


@pytest.mark.parametrize(
    "now,expected",
    [(49.99, "entry"), (50.0, "entry"), (50.01, "sellers_not_drying_up")],
)
def test_sellers_drying_up_ratio(now, expected):
    # previous 5 minute volume is 100 and sell_dryup_ratio is 0.5.
    assert code(dip_snap(sell_volume_5m_usd=now)) == expected


def test_zero_previous_sell_volume_is_not_drying_up():
    assert code(dip_snap(sell_volume_prev_5m_usd=0.0, sell_volume_5m_usd=0.0)) == "sellers_not_drying_up"
    assert code(dip_snap(sell_volume_prev_5m_usd=-1.0, sell_volume_5m_usd=0.0)) == "sellers_not_drying_up"


def test_entry_order_not_built_beats_missing_data():
    bare = model.TokenSnapshot(ts=TS, mint="M", symbol="X")
    assert code(bare, Strategy.NEWS) == "strategy_not_built"


def test_entry_order_missing_data_beats_strategy_rules():
    snap = aged(5, price_usd=None)  # also outside the DIP window
    assert code(snap) == "dip_data_missing"


def test_entry_order_age_beats_liquidity_for_dip():
    assert code(aged(5, liquidity_usd=1.0)) == "age_outside_window"


def test_entry_order_liquidity_beats_no_dip_for_dip():
    assert code(dip_snap(liquidity_usd=1.0, price_usd=99.0)) == "liquidity_below_floor"


def test_entry_order_graduation_unknown_beats_grad_wait():
    assert code(aged(5, from_pumpfun_graduation=None), Strategy.GRAD) == "graduation_unknown"


def test_entry_order_not_a_graduation_beats_grad_wait():
    assert code(aged(5, from_pumpfun_graduation=False), Strategy.GRAD) == "not_a_graduation"


def test_entry_order_grad_wait_beats_no_dip():
    assert code(aged(5, price_usd=99.0), Strategy.GRAD) == "grad_wait"


def test_entry_order_no_dip_beats_sellers():
    assert code(dip_snap(price_usd=99.0, sell_volume_5m_usd=1_000.0)) == "no_dip"


def test_entry_signal_follows_changed_settings():
    tight = Settings.for_tests(dip_from_high_pct=30.0)
    assert code(dip_snap(), settings=tight) == "no_dip"
    loose = Settings.for_tests(sell_dryup_ratio=1.0)
    assert code(dip_snap(sell_volume_5m_usd=100.0), settings=loose) == "entry"


def test_entry_signal_does_not_mutate_its_inputs():
    snap = dip_snap()
    before = copy.deepcopy(snap)
    entry.entry_signal(snap, Strategy.DIP, S)
    entry.entry_signal(snap, Strategy.GRAD, S)
    assert snap == before


# --- pre_trade_recheck ------------------------------------------------------


def decision(**kw) -> model.TokenSnapshot:
    base = dict(ts=TS, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=100.0)
    base.update(kw)
    return model.TokenSnapshot(**base)


def fresh(**kw) -> model.TokenSnapshot:
    base = dict(
        ts=TS + 5, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=100.0,
        trading_disabled=False, venue_warning="",
    )
    base.update(kw)
    return model.TokenSnapshot(**base)


def recheck(dec=None, fr=None, ticket=10.0, cash=100.0, settings=S, kind=ExecutorKind.PAPER):
    return entry.pre_trade_recheck(
        dec or decision(), fr or fresh(), ticket, cash, settings, kind
    )


def test_a_clean_recheck_returns_an_empty_tuple():
    assert recheck() == ()
    assert recheck(kind=ExecutorKind.LIVE) == ()


def test_recheck_returns_a_tuple():
    assert isinstance(recheck(fr=fresh(venue_warning="x")), tuple)


def test_stale_snapshot_only_when_fresh_is_older():
    assert recheck(fr=fresh(ts=TS - 1)) == ("stale_snapshot",)
    assert recheck(fr=fresh(ts=TS)) == ()
    assert recheck(fr=fresh(ts=TS + 1)) == ()


def test_liquidity_unknown():
    assert recheck(fr=fresh(liquidity_usd=None)) == ("liquidity_unknown",)


@pytest.mark.parametrize(
    "liq,expected",
    [(19_999.99, ("liquidity_below_floor",)), (20_000.0, ()), (20_000.01, ())],
)
def test_liquidity_floor_in_the_recheck(liq, expected):
    # a ticket of 10 is far under 2 percent of 20,000, so only the floor can fire
    assert recheck(fr=fresh(liquidity_usd=liq)) == expected


@pytest.mark.parametrize(
    "ticket,expected",
    [(799.99, ()), (800.0, ()), (800.01, ("ticket_exceeds_liquidity_cap",))],
)
def test_ticket_liquidity_cap(ticket, expected):
    # 2 percent of 40,000 is 800
    assert recheck(ticket=ticket, cash=10_000.0) == expected


def test_the_cap_uses_the_fresh_liquidity_not_the_decision_liquidity():
    dec = decision(liquidity_usd=1_000_000.0)
    assert recheck(dec=dec, ticket=801.0, cash=10_000.0) == ("ticket_exceeds_liquidity_cap",)


def test_unknown_liquidity_gives_no_cap_reason():
    assert recheck(fr=fresh(liquidity_usd=None), ticket=10_000.0, cash=20_000.0) == ("liquidity_unknown",)


@pytest.mark.parametrize(
    "dec_price,fresh_price",
    [(None, 100.0), (100.0, None), (0.0, 100.0), (-1.0, 100.0), (None, None)],
)
def test_price_unknown(dec_price, fresh_price):
    got = recheck(dec=decision(price_usd=dec_price), fr=fresh(price_usd=fresh_price))
    assert got == ("price_unknown",)


@pytest.mark.parametrize(
    "fresh_price,expected",
    [(104.99, ()), (105.0, ()), (105.01, ("price_drifted",)),
     (95.01, ()), (95.0, ()), (94.99, ("price_drifted",))],
)
def test_price_drift_is_absolute_and_inclusive_at_the_tolerance(fresh_price, expected):
    # tolerance 5 percent of a decision price of 100
    assert recheck(fr=fresh(price_usd=fresh_price)) == expected


@pytest.mark.parametrize(
    "cash,expected", [(9.99, ("insufficient_cash",)), (10.0, ()), (10.01, ())]
)
def test_insufficient_cash(cash, expected):
    assert recheck(ticket=10.0, cash=cash) == expected


@pytest.mark.parametrize("warning,expected", [("rug risk", ("venue_warning",)), ("", ()), (None, ())])
def test_venue_warning_on_a_paper_run(warning, expected):
    assert recheck(fr=fresh(venue_warning=warning)) == expected


@pytest.mark.parametrize(
    "flag,expected", [(True, ("trading_disabled",)), (False, ()), (None, ())]
)
def test_trading_disabled_on_a_paper_run(flag, expected):
    assert recheck(fr=fresh(trading_disabled=flag)) == expected


def test_a_paper_run_may_proceed_without_venue_checks():
    got = recheck(fr=fresh(trading_disabled=None, venue_warning=None), kind=ExecutorKind.PAPER)
    assert got == ()


@pytest.mark.parametrize(
    "disabled,warning",
    [(None, ""), (False, None), (None, None)],
)
def test_a_live_run_may_not_proceed_without_venue_checks(disabled, warning):
    got = recheck(fr=fresh(trading_disabled=disabled, venue_warning=warning), kind=ExecutorKind.LIVE)
    assert got == ("venue_checks_missing",)


def test_a_live_run_with_both_venue_checks_known_is_clean():
    assert recheck(fr=fresh(trading_disabled=False, venue_warning=""), kind=ExecutorKind.LIVE) == ()


def test_recheck_reports_every_reason_in_spec_order():
    bad = fresh(
        ts=TS - 1, liquidity_usd=1_000.0, price_usd=200.0,
        trading_disabled=True, venue_warning="halted",
    )
    got = recheck(fr=bad, ticket=500.0, cash=1.0)
    assert got == (
        "stale_snapshot", "liquidity_below_floor", "ticket_exceeds_liquidity_cap",
        "price_drifted", "insufficient_cash", "venue_warning", "trading_disabled",
    )


def test_recheck_order_with_unknowns_on_a_live_run():
    bad = fresh(ts=TS - 1, liquidity_usd=None, price_usd=None, trading_disabled=None, venue_warning=None)
    got = recheck(fr=bad, ticket=500.0, cash=1.0, kind=ExecutorKind.LIVE)
    assert got == (
        "stale_snapshot", "liquidity_unknown", "price_unknown",
        "insufficient_cash", "venue_checks_missing",
    )


def test_recheck_does_not_mutate_its_inputs():
    dec, fr = decision(), fresh(venue_warning="w")
    before = (copy.deepcopy(dec), copy.deepcopy(fr))
    recheck(dec=dec, fr=fr)
    assert (dec, fr) == before


# --- brain helpers ----------------------------------------------------------


def tier(name: str, total: float = 85.0) -> model.ScoreBreakdown:
    return model.ScoreBreakdown(
        alive=0.0, organic=0.0, flush=0.0, anti_chase=0.0, social=0.0,
        total=total, passed=name != "none", size_tier=name,
    )


def folio(**kw) -> model.PortfolioView:
    base = dict(
        free_cash_usd=100.0, equity_usd=100.0, open_positions=0, exposure_usd=0.0,
        night_start_equity_usd=100.0, night_pnl_usd=0.0,
    )
    base.update(kw)
    return model.PortfolioView(**base)


GREEN = model.MarketState(mode=model.Mode.GREEN, data_ok=True, blocks_new_buys=False)
BLOCKED = model.MarketState(mode=model.Mode.RED, data_ok=True, blocks_new_buys=True)
LESSON = model.Lesson(lesson_id="L-1", created_ts=1, source_mint="MintZ", check="top10_pct >= 30")


def size(score=None, snap=None, portfolio=None, market=GREEN, lesson=None, settings=S):
    return brain.size_ticket(
        score or tier("full"), snap or dip_snap(), portfolio or folio(), market, lesson, settings
    )


# --- size_ticket ------------------------------------------------------------


def test_a_full_ticket_is_twelve_percent_of_free_cash():
    d = size()
    assert d.skip_reason_code == "" and not d.skipped
    assert d.ticket_usd == pytest.approx(12.0)


def test_a_half_tier_ticket_is_half_the_base():
    assert size(score=tier("half", 75.0)).ticket_usd == pytest.approx(6.0)


@pytest.mark.parametrize("name", ["full", "half"])
def test_a_sized_ticket_has_an_empty_skip_code(name):
    assert size(score=tier(name)).skip_reason_code == ""


def test_every_skip_has_a_zero_ticket_and_a_code():
    cases = [
        size(market=BLOCKED), size(lesson=LESSON), size(portfolio=folio(night_pnl_usd=-50.0)),
        size(score=tier("none", 10.0)), size(portfolio=folio(open_positions=3)),
        size(snap=dip_snap(liquidity_usd=None)), size(portfolio=folio(exposure_usd=40.0)),
        size(portfolio=folio(free_cash_usd=1.0)),
    ]
    for d in cases:
        assert d.ticket_usd == 0.0 and d.skip_reason_code and d.skipped


def test_market_blocks_buys():
    assert size(market=BLOCKED).skip_reason_code == "market_blocks_buys"


def test_a_market_that_does_not_block_lets_a_ticket_through():
    quiet = model.MarketState(mode=model.Mode.GREEN, data_ok=True, blocks_new_buys=False)
    assert not size(market=quiet).skipped


def test_any_lesson_blocks():
    assert size(lesson=LESSON).skip_reason_code == "lesson_blocks"


@pytest.mark.parametrize(
    "pnl,expected",
    [(-9.99, ""), (-10.0, "night_stop"), (-10.01, "night_stop"), (5.0, "")],
)
def test_night_stop_threshold(pnl, expected):
    # night_stop_pct is 10 of starting equity 100, so the line is -10
    assert size(portfolio=folio(night_pnl_usd=pnl)).skip_reason_code == expected


@pytest.mark.parametrize("start", [0.0, -5.0])
def test_night_stop_needs_positive_starting_equity(start):
    assert size(portfolio=folio(night_start_equity_usd=start, night_pnl_usd=-1_000.0)).skip_reason_code == ""


def test_night_stop_uses_starting_equity_not_current_equity():
    p = folio(equity_usd=1_000.0, night_start_equity_usd=100.0, night_pnl_usd=-10.0)
    assert size(portfolio=p).skip_reason_code == "night_stop"


def test_score_below_pass():
    d = size(score=tier("none", 69.9))
    assert d.skip_reason_code == "score_below_pass"


@pytest.mark.parametrize(
    "open_n,expected", [(2, ""), (3, "max_open_positions"), (4, "max_open_positions")]
)
def test_max_open_positions_threshold(open_n, expected):
    assert size(portfolio=folio(open_positions=open_n)).skip_reason_code == expected


def test_brain_liquidity_unknown():
    assert size(snap=dip_snap(liquidity_usd=None)).skip_reason_code == "liquidity_unknown"


@pytest.mark.parametrize(
    "exposure,expected", [(35.98, ""), (36.0, "exposure_cap"), (36.01, "exposure_cap"), (50.0, "exposure_cap")]
)
def test_exposure_cap_threshold(exposure, expected):
    # max_total_exposure_pct is 36 of equity 100, so the room closes at 36.
    # A small minimum ticket lets the 0.02 of room at 35.98 size a ticket.
    s = Settings.for_tests(min_ticket_usd=0.01)
    assert size(portfolio=folio(exposure_usd=exposure), settings=s).skip_reason_code == expected


def test_ticket_is_held_to_the_exposure_room():
    d = size(portfolio=folio(exposure_usd=30.0))
    assert d.ticket_usd == pytest.approx(6.0)  # room 6 against a base of 12


def test_ticket_is_held_to_the_pool_liquidity_cap():
    d = size(snap=dip_snap(liquidity_usd=500.0))
    assert d.ticket_usd == pytest.approx(10.0)  # 2 percent of 500 against a base of 12


def test_ticket_is_held_to_max_ticket():
    d = size(portfolio=folio(free_cash_usd=1_000.0, equity_usd=10_000.0))
    assert d.ticket_usd == pytest.approx(25.0)  # base 120 and room 3600


def test_ticket_is_held_to_free_cash():
    s = Settings.for_tests(risk_per_trade_pct=10.0, stop_loss_pct=1.0, max_ticket_usd=100_000.0)
    d = size(portfolio=folio(free_cash_usd=5.0, equity_usd=1_000.0), settings=s)
    assert d.ticket_usd == pytest.approx(5.0)  # base would be 50


def test_the_smallest_limit_wins_when_several_bind():
    d = size(snap=dip_snap(liquidity_usd=400.0), portfolio=folio(exposure_usd=30.0))
    assert d.ticket_usd == pytest.approx(6.0)  # cap 8, room 6, base 12


@pytest.mark.parametrize(
    "cash,expected_skip", [(9.9, "ticket_below_min"), (10.0, ""), (10.1, "")]
)
def test_min_ticket_threshold(cash, expected_skip):
    s = Settings.for_tests(risk_per_trade_pct=1.0, stop_loss_pct=10.0, min_ticket_usd=1.0)
    d = size(portfolio=folio(free_cash_usd=cash), settings=s)
    assert d.skip_reason_code == expected_skip
    assert d.skipped == bool(expected_skip)


def test_the_half_tier_can_fall_below_the_minimum():
    s = Settings.for_tests(risk_per_trade_pct=1.0, stop_loss_pct=10.0, min_ticket_usd=1.0)
    assert size(score=tier("half"), portfolio=folio(free_cash_usd=10.0), settings=s).skip_reason_code == "ticket_below_min"
    assert size(score=tier("full"), portfolio=folio(free_cash_usd=10.0), settings=s).skip_reason_code == ""


def test_zero_free_cash_skips_below_min():
    assert size(portfolio=folio(free_cash_usd=0.0)).skip_reason_code == "ticket_below_min"


# order of the skips: the earlier one wins when two would fire


def test_order_market_beats_lesson():
    assert size(market=BLOCKED, lesson=LESSON).skip_reason_code == "market_blocks_buys"


def test_order_lesson_beats_night_stop():
    assert size(lesson=LESSON, portfolio=folio(night_pnl_usd=-50.0)).skip_reason_code == "lesson_blocks"


def test_order_night_stop_beats_score():
    got = size(score=tier("none"), portfolio=folio(night_pnl_usd=-50.0)).skip_reason_code
    assert got == "night_stop"


def test_order_score_beats_max_open():
    got = size(score=tier("none"), portfolio=folio(open_positions=9)).skip_reason_code
    assert got == "score_below_pass"


def test_order_max_open_beats_liquidity_unknown():
    got = size(snap=dip_snap(liquidity_usd=None), portfolio=folio(open_positions=9)).skip_reason_code
    assert got == "max_open_positions"


def test_order_liquidity_unknown_beats_exposure_cap():
    got = size(snap=dip_snap(liquidity_usd=None), portfolio=folio(exposure_usd=99.0)).skip_reason_code
    assert got == "liquidity_unknown"


def test_order_exposure_cap_beats_ticket_below_min():
    got = size(portfolio=folio(exposure_usd=99.0, free_cash_usd=0.5)).skip_reason_code
    assert got == "exposure_cap"


def test_the_night_stop_applies_in_every_mode():
    for mode in (model.Mode.GREEN, model.Mode.RED, model.Mode.QUIET):
        m = model.MarketState(mode=mode, data_ok=True, blocks_new_buys=False)
        assert size(market=m, portfolio=folio(night_pnl_usd=-10.0)).skip_reason_code == "night_stop"


def test_the_brain_does_not_mutate_its_inputs():
    score, snap, port = tier("half"), dip_snap(), folio(exposure_usd=3.0)
    before = copy.deepcopy((score, snap, port, GREEN, LESSON))
    size(score=score, snap=snap, portfolio=port, lesson=None)
    size(score=score, snap=snap, portfolio=port, lesson=LESSON)
    assert (score, snap, port, GREEN, LESSON) == before


def test_the_decision_is_frozen():
    d = size()
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.ticket_usd = 99.0  # type: ignore[misc]


def test_the_brain_only_sizes_it_returns_a_size_decision():
    assert isinstance(size(), model.SizeDecision)
    assert isinstance(size(market=BLOCKED), model.SizeDecision)
