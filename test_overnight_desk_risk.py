"""The Overnight Desk risk bot: stops, trails, takes and the other exits.

Offline. Tests only tools/overnight_desk/risk.py against SPEC.md "risk.py".
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Appended, never inserted first, so no other top-level name is shadowed.
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from overnight_desk import model  # noqa: E402
from overnight_desk.model import ExitReason, Mode  # noqa: E402
from overnight_desk.risk import evaluate  # noqa: E402
from overnight_desk.settings import Settings  # noqa: E402

S = Settings.for_tests()
HELD = 100  # seconds held in the default snapshot


def _entry_snap(**kw) -> model.TokenSnapshot:
    base = dict(ts=0, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=1.0)
    base.update(kw)
    return model.TokenSnapshot(**base)


def _pos(**kw) -> model.Position:
    base = dict(
        mint="MintA", symbol="AAA", strategy=model.Strategy.DIP, entry_ts=0, entry_price=1.0,
        qty=1_000.0, cost_usd=1_000.0, stop_price=0.75, peak_price=1.0, took_first_take=False,
        entry_liquidity_usd=40_000.0, entry_snapshot=_entry_snap(),
    )
    base.update(kw)
    return model.Position(**base)


def _snap(**kw) -> model.TokenSnapshot:
    base = dict(ts=HELD, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=1.0)
    base.update(kw)
    return model.TokenSnapshot(**base)


def _run(pos=None, snap=None, mode=Mode.GREEN, settings=S):
    return evaluate(pos or _pos(), snap or _snap(), mode, settings)


def _reason(result):
    return result[1].reason if result[1] else None


# --- no price ---------------------------------------------------------------


def test_no_price_returns_the_same_position_and_no_decision():
    pos = _pos()
    out, decision = _run(pos, _snap(price_usd=None, venue_warning="rug", dev_has_sold=True))
    assert out is pos and decision is None


def test_every_input_none_gives_no_decision():
    pos = _pos()
    snap = model.TokenSnapshot(ts=HELD, mint="MintA", symbol="AAA")
    out, decision = _run(pos, snap)
    assert out is pos and decision is None


def test_a_price_with_every_other_input_unknown_gives_no_decision():
    snap = model.TokenSnapshot(ts=HELD, mint="MintA", symbol="AAA", price_usd=1.0)
    out, decision = _run(snap=snap)
    assert decision is None and out.peak_price == 1.0


# --- peak and stop ----------------------------------------------------------


def test_peak_rises_with_price_and_never_falls():
    out, _ = _run(snap=_snap(price_usd=1.5))
    assert out.peak_price == 1.5
    out, _ = _run(_pos(peak_price=1.8), _snap(price_usd=1.2))
    assert out.peak_price == 1.8


def test_stop_does_not_trail_before_the_first_take():
    out, _ = _run(_pos(peak_price=1.0), _snap(price_usd=1.9))
    assert out.stop_price == 0.75


@pytest.mark.parametrize(
    "mode,expected_stop",
    [(Mode.GREEN, 2.0 * 0.7), (Mode.QUIET, 2.0 * 0.7), (Mode.RED, 2.0 * 0.9)],
)
def test_trail_uses_the_red_figure_in_red_and_the_green_figure_otherwise(mode, expected_stop):
    s = Settings.for_tests(trail_green_pct=30, trail_red_pct=10)
    pos = _pos(took_first_take=True, stop_price=0.75, peak_price=2.0)
    out, decision = _run(pos, _snap(price_usd=2.0), mode, s)
    assert decision is None
    assert out.stop_price == pytest.approx(expected_stop)


def test_trail_follows_a_new_peak():
    pos = _pos(took_first_take=True, stop_price=1.6, peak_price=2.0)
    out, decision = _run(pos, _snap(price_usd=3.0))
    assert decision is None
    assert out.peak_price == 3.0 and out.stop_price == pytest.approx(2.25)


def test_the_stop_never_moves_down():
    pos = _pos(took_first_take=True, stop_price=1.9, peak_price=2.0)  # trail would give 1.5
    out, decision = _run(pos, _snap(price_usd=1.95))
    assert decision is None and out.stop_price == 1.9


# --- 1. stop and trail ------------------------------------------------------


@pytest.mark.parametrize("price,fires", [(0.7499, True), (0.75, True), (0.7501, False)])
def test_stop_threshold(price, fires):
    result = _run(snap=_snap(price_usd=price))
    assert (_reason(result) is ExitReason.STOP) is fires
    if fires:
        assert result[1].fraction == 1.0 and result[1].mint == "MintA"


@pytest.mark.parametrize("price,fires", [(1.4999, True), (1.5, True), (1.5001, False)])
def test_trail_threshold_and_name(price, fires):
    pos = _pos(took_first_take=True, stop_price=0.75, peak_price=2.0)
    result = _run(pos, _snap(price_usd=price))
    assert (_reason(result) is ExitReason.TRAIL) is fires
    if fires:
        assert result[1].fraction == 1.0


def test_a_trail_hit_uses_the_stop_brought_up_to_date():
    # The passed-in stop is 0.75, the trailed one is 1.5, and 1.4 is under it.
    pos = _pos(took_first_take=True, stop_price=0.75, peak_price=2.0)
    assert _reason(_run(pos, _snap(price_usd=1.4))) is ExitReason.TRAIL


def test_a_stop_exit_returns_the_updated_position_and_keeps_qty_and_cost():
    pos = _pos(peak_price=1.0)
    out, decision = _run(pos, _snap(price_usd=0.7))
    assert decision.reason is ExitReason.STOP
    assert out.qty == pos.qty and out.cost_usd == pos.cost_usd


# --- 2. venue warning -------------------------------------------------------


@pytest.mark.parametrize("warning,fires", [("honeypot", True), (" ", True), ("", False), (None, False)])
def test_venue_warning(warning, fires):
    result = _run(snap=_snap(venue_warning=warning))
    assert (_reason(result) is ExitReason.VENUE_WARNING) is fires
    if fires:
        assert result[1].fraction == 1.0


# --- 3. dev sold ------------------------------------------------------------


@pytest.mark.parametrize(
    "now,at_entry,fires",
    [
        (True, False, True),
        (True, None, True),
        (True, True, False),
        (False, False, False),
        (None, False, False),
        (False, True, False),
    ],
)
def test_dev_sold_only_when_it_was_not_true_at_entry(now, at_entry, fires):
    pos = _pos(entry_snapshot=_entry_snap(dev_has_sold=at_entry))
    result = _run(pos, _snap(dev_has_sold=now))
    assert (_reason(result) is ExitReason.DEV_SOLD) is fires
    if fires:
        assert result[1].fraction == 1.0


# --- 4. liquidity pulled ----------------------------------------------------


@pytest.mark.parametrize("liq,fires", [(19_999.99, True), (20_000.0, False), (20_000.01, False)])
def test_liquidity_floor_threshold(liq, fires):
    pos = _pos(entry_liquidity_usd=0.0)  # the drop test is off, only the floor can fire
    result = _run(pos, _snap(liquidity_usd=liq))
    assert (_reason(result) is ExitReason.LIQUIDITY_PULLED) is fires


@pytest.mark.parametrize("liq,fires", [(49_999.99, True), (50_000.0, True), (50_000.01, False)])
def test_liquidity_drop_threshold_is_at_or_below(liq, fires):
    pos = _pos(entry_liquidity_usd=100_000.0)  # 50 percent drop gives 50,000
    result = _run(pos, _snap(liquidity_usd=liq))
    assert (_reason(result) is ExitReason.LIQUIDITY_PULLED) is fires
    if fires:
        assert result[1].fraction == 1.0


def test_the_drop_test_follows_its_setting():
    s = Settings.for_tests(liquidity_pull_drop_pct=20)
    pos = _pos(entry_liquidity_usd=100_000.0)  # limit 80,000
    assert _reason(_run(pos, _snap(liquidity_usd=80_000.0), settings=s)) is ExitReason.LIQUIDITY_PULLED
    assert _reason(_run(pos, _snap(liquidity_usd=80_000.01), settings=s)) is None


def test_unknown_liquidity_never_fires_the_liquidity_exit():
    assert _run(snap=_snap(liquidity_usd=None))[1] is None


def test_zero_entry_liquidity_switches_the_drop_test_off():
    pos = _pos(entry_liquidity_usd=0.0)
    assert _run(pos, _snap(liquidity_usd=20_000.0))[1] is None


# --- 5. take ----------------------------------------------------------------


@pytest.mark.parametrize("price,fires", [(1.999999, False), (2.0, True), (2.01, True)])
def test_green_take_threshold(price, fires):
    result = _run(snap=_snap(price_usd=price))
    assert (_reason(result) is ExitReason.TAKE) is fires


@pytest.mark.parametrize("price,fires", [(1.499999, False), (1.5, True), (1.51, True)])
def test_red_take_threshold(price, fires):
    result = _run(snap=_snap(price_usd=price), mode=Mode.RED)
    assert (_reason(result) is ExitReason.TAKE) is fires


def test_quiet_takes_at_the_green_multiple():
    assert _run(snap=_snap(price_usd=1.5), mode=Mode.QUIET)[1] is None
    assert _reason(_run(snap=_snap(price_usd=2.0), mode=Mode.QUIET)) is ExitReason.TAKE


def test_a_take_sells_the_take_fraction_and_flags_the_position():
    s = Settings.for_tests(take_fraction=0.4)
    pos = _pos()
    out, decision = _run(pos, _snap(price_usd=2.2), settings=s)
    assert decision.reason is ExitReason.TAKE and decision.fraction == 0.4
    assert out.took_first_take is True
    assert out.peak_price == 2.2
    assert out.stop_price == pos.stop_price  # the trail starts on the next call
    assert out.qty == pos.qty and out.cost_usd == pos.cost_usd


def test_the_take_fires_once():
    pos = _pos(took_first_take=True, stop_price=1.6, peak_price=2.0)
    assert _run(pos, _snap(price_usd=2.5))[1] is None


# --- 6. RED time stop -------------------------------------------------------


@pytest.mark.parametrize("held,fires", [(5_399, False), (5_400, True), (5_401, True)])
def test_red_time_stop_threshold(held, fires):
    result = _run(snap=_snap(ts=held), mode=Mode.RED)
    assert (_reason(result) is ExitReason.RED_TIME_STOP) is fires
    if fires:
        assert result[1].fraction == 1.0


@pytest.mark.parametrize("mode", [Mode.GREEN, Mode.QUIET])
def test_the_red_time_stop_applies_only_in_red(mode):
    assert _run(snap=_snap(ts=6_000), mode=mode)[1] is None


# --- 7. dead money ----------------------------------------------------------


@pytest.mark.parametrize("held,fires", [(10_799, False), (10_800, True), (10_801, True)])
def test_dead_money_age_threshold(held, fires):
    result = _run(snap=_snap(ts=held))
    assert (_reason(result) is ExitReason.DEAD_MONEY) is fires
    if fires:
        assert result[1].fraction == 1.0


@pytest.mark.parametrize("price,fires", [(1.049, True), (1.05, False), (1.051, False)])
def test_dead_money_gain_threshold(price, fires):
    result = _run(snap=_snap(ts=10_800, price_usd=price))
    assert (_reason(result) is ExitReason.DEAD_MONEY) is fires


def test_dead_money_applies_in_every_mode():
    for mode in (Mode.GREEN, Mode.QUIET, Mode.RED):
        assert _reason(_run(snap=_snap(ts=10_800), mode=mode)) in (
            ExitReason.DEAD_MONEY, ExitReason.RED_TIME_STOP
        )


# --- order of checks: the earlier rule wins ---------------------------------


def test_stop_beats_venue_warning():
    assert _reason(_run(snap=_snap(price_usd=0.7, venue_warning="x"))) is ExitReason.STOP


def test_trail_beats_venue_warning():
    pos = _pos(took_first_take=True, peak_price=2.0)
    assert _reason(_run(pos, _snap(price_usd=1.5, venue_warning="x"))) is ExitReason.TRAIL


def test_venue_warning_beats_dev_sold():
    snap = _snap(venue_warning="x", dev_has_sold=True)
    assert _reason(_run(snap=snap)) is ExitReason.VENUE_WARNING


def test_dev_sold_beats_liquidity_pulled():
    snap = _snap(dev_has_sold=True, liquidity_usd=1_000.0)
    assert _reason(_run(snap=snap)) is ExitReason.DEV_SOLD


def test_liquidity_pulled_beats_take():
    snap = _snap(price_usd=3.0, liquidity_usd=1_000.0)
    assert _reason(_run(snap=snap)) is ExitReason.LIQUIDITY_PULLED


def test_take_beats_red_time_stop_and_dead_money():
    snap = _snap(price_usd=1.6, ts=20_000)
    assert _reason(_run(snap=snap, mode=Mode.RED)) is ExitReason.TAKE


def test_red_time_stop_beats_dead_money():
    snap = _snap(ts=20_000)  # both are due, price 1.0 is under 1.05
    assert _reason(_run(snap=snap, mode=Mode.RED)) is ExitReason.RED_TIME_STOP
    assert _reason(_run(snap=snap, mode=Mode.GREEN)) is ExitReason.DEAD_MONEY


def test_a_losing_take_candidate_cannot_double_fire():
    # Price meets the take and the stop (stop raised above the take line): the stop wins.
    pos = _pos(stop_price=2.5)
    result = _run(pos, _snap(price_usd=2.0))
    assert _reason(result) is ExitReason.STOP


# --- invariants -------------------------------------------------------------


def test_nothing_is_mutated_and_the_stop_never_falls():
    cases = [
        (_pos(), _snap(price_usd=2.5), Mode.GREEN),
        (_pos(took_first_take=True, stop_price=1.9, peak_price=2.0), _snap(price_usd=1.95), Mode.RED),
        (_pos(), _snap(price_usd=0.5), Mode.QUIET),
        (_pos(), _snap(price_usd=None), Mode.GREEN),
    ]
    for pos, snap, mode in cases:
        pos_before, snap_before = dataclasses.replace(pos), dataclasses.replace(snap)
        out, _ = evaluate(pos, snap, mode, S)
        assert pos == pos_before and snap == snap_before
        assert out.stop_price >= pos.stop_price
        assert out.qty == pos.qty and out.cost_usd == pos.cost_usd
        assert out.entry_price == pos.entry_price and out.entry_ts == pos.entry_ts


def test_at_most_one_decision_and_its_mint_is_the_positions():
    out, decision = _run(snap=_snap(price_usd=0.5, venue_warning="x", dev_has_sold=True, liquidity_usd=1.0))
    assert isinstance(decision, model.ExitDecision) and decision.mint == "MintA"
    assert decision.reason is ExitReason.STOP


def test_every_non_take_exit_sells_the_whole_position():
    snaps = [
        (_snap(price_usd=0.5), Mode.GREEN),
        (_snap(venue_warning="x"), Mode.GREEN),
        (_snap(dev_has_sold=True), Mode.GREEN),
        (_snap(liquidity_usd=1.0), Mode.GREEN),
        (_snap(ts=6_000), Mode.RED),
        (_snap(ts=20_000), Mode.GREEN),
    ]
    for snap, mode in snaps:
        _, decision = _run(snap=snap, mode=mode)
        assert decision is not None and decision.fraction == 1.0


def test_a_healthy_position_gets_no_decision():
    out, decision = _run(snap=_snap(price_usd=1.2))
    assert decision is None and out.peak_price == 1.2


# --- the mint guard and the decision's mint ---------------------------------


@pytest.mark.parametrize("price", [1.0, None])
def test_a_snapshot_for_another_mint_raises(price):
    with pytest.raises(ValueError):
        _run(snap=_snap(mint="MintB", price_usd=price))


def test_the_decision_carries_the_positions_own_mint_object():
    class Alias(str):
        def __ne__(self, other):  # equal to any mint, so the guard lets it by
            return False

        __hash__ = str.__hash__

    pos = _pos(mint=Alias("MintA"))
    _, decision = _run(pos, _snap(mint="MintZ", price_usd=0.5))
    assert decision.reason is ExitReason.STOP
    assert decision.mint is pos.mint


# --- held time is measured from entry_ts ------------------------------------


def test_red_time_stop_counts_from_entry_ts():
    pos = _pos(entry_ts=10_000)
    assert _run(pos, _snap(ts=10_000 + 5_399), mode=Mode.RED)[1] is None
    assert _reason(_run(pos, _snap(ts=10_000 + 5_400), mode=Mode.RED)) is ExitReason.RED_TIME_STOP


def test_dead_money_counts_from_entry_ts():
    pos = _pos(entry_ts=10_000)
    assert _run(pos, _snap(ts=10_000 + 10_799))[1] is None
    assert _reason(_run(pos, _snap(ts=10_000 + 10_800))) is ExitReason.DEAD_MONEY


# --- every threshold is read from settings ----------------------------------


def test_take_multiple_green_follows_its_setting():
    s = Settings.for_tests(take_multiple_green=3.0)
    assert _run(snap=_snap(price_usd=2.5), settings=s)[1] is None
    assert _reason(_run(snap=_snap(price_usd=3.0), settings=s)) is ExitReason.TAKE


def test_take_multiple_red_follows_its_setting():
    s = Settings.for_tests(take_multiple_red=1.2)
    assert _reason(_run(snap=_snap(price_usd=1.2), mode=Mode.RED, settings=s)) is ExitReason.TAKE
    assert _run(snap=_snap(price_usd=1.19), mode=Mode.RED, settings=s)[1] is None


def test_take_fraction_follows_its_setting():
    s = Settings.for_tests(take_fraction=0.25)
    assert _run(snap=_snap(price_usd=2.0), settings=s)[1].fraction == 0.25


def test_trail_green_follows_its_setting_alone():
    s = Settings.for_tests(trail_green_pct=40, trail_red_pct=10)
    pos = _pos(took_first_take=True, stop_price=0.75, peak_price=2.0)
    out, _ = _run(pos, _snap(price_usd=2.0), Mode.GREEN, s)
    assert out.stop_price == pytest.approx(1.2)


def test_trail_red_follows_its_setting_alone():
    s = Settings.for_tests(trail_green_pct=50, trail_red_pct=40)
    pos = _pos(took_first_take=True, stop_price=0.75, peak_price=2.0)
    out, _ = _run(pos, _snap(price_usd=2.0), Mode.RED, s)
    assert out.stop_price == pytest.approx(1.2)


def test_the_initial_stop_is_the_one_on_the_position():
    assert _reason(_run(_pos(stop_price=0.9), _snap(price_usd=0.9))) is ExitReason.STOP
    assert _run(_pos(stop_price=0.5), _snap(price_usd=0.6))[1] is None


def test_liquidity_floor_follows_its_setting():
    pos = _pos(entry_liquidity_usd=0.0)
    s = Settings.for_tests(liquidity_floor_usd=30_000)
    assert _reason(_run(pos, _snap(liquidity_usd=25_000.0), settings=s)) is ExitReason.LIQUIDITY_PULLED
    assert _run(pos, _snap(liquidity_usd=30_000.0), settings=s)[1] is None
    s = Settings.for_tests(liquidity_floor_usd=10_000)
    assert _run(pos, _snap(liquidity_usd=15_000.0), settings=s)[1] is None


def test_red_time_stop_follows_its_setting():
    s = Settings.for_tests(red_time_stop_s=3_600)
    assert _run(snap=_snap(ts=3_599), mode=Mode.RED, settings=s)[1] is None
    assert _reason(_run(snap=_snap(ts=3_600), mode=Mode.RED, settings=s)) is ExitReason.RED_TIME_STOP
    s = Settings.for_tests(red_time_stop_s=7_200)
    assert _run(snap=_snap(ts=5_400), mode=Mode.RED, settings=s)[1] is None


def test_dead_money_age_follows_its_setting():
    s = Settings.for_tests(dead_money_after_s=7_200)
    assert _run(snap=_snap(ts=7_199), settings=s)[1] is None
    assert _reason(_run(snap=_snap(ts=7_200), settings=s)) is ExitReason.DEAD_MONEY
    s = Settings.for_tests(dead_money_after_s=14_400)
    assert _run(snap=_snap(ts=10_800), settings=s)[1] is None


def test_dead_money_min_gain_follows_its_setting():
    s = Settings.for_tests(dead_money_min_gain_pct=10)
    assert _reason(_run(snap=_snap(ts=10_800, price_usd=1.09), settings=s)) is ExitReason.DEAD_MONEY
    assert _run(snap=_snap(ts=10_800, price_usd=1.1), settings=s)[1] is None
    s = Settings.for_tests(dead_money_min_gain_pct=2)
    assert _run(snap=_snap(ts=10_800, price_usd=1.03), settings=s)[1] is None


# --- the TAKE call does not trail, the next one does ------------------------


def test_the_stop_trails_from_the_call_after_the_take():
    pos = _pos()
    taken, decision = _run(pos, _snap(price_usd=2.0))
    assert decision.reason is ExitReason.TAKE and taken.stop_price == pos.stop_price
    nxt, decision = _run(taken, _snap(price_usd=2.0))
    assert decision is None and nxt.stop_price == pytest.approx(2.0 * 0.75)
