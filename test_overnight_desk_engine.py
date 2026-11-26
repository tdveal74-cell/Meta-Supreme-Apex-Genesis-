"""The Overnight Desk paper engine end to end: desk, morning report, replay.

Offline. No network, no database, no clock. A night is a list of ticks built
in this file. These tests pin the order of the bots, the sells-before-buys
rule, the per-order human gate, the loss autopsy and its lesson, the report's
four morning checks and the replay's refusal of malformed input.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "tools" / "overnight_desk"
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from overnight_desk import lessons, model, replay, report  # noqa: E402
from overnight_desk.engine import Desk  # noqa: E402
from overnight_desk.settings import Settings  # noqa: E402

T0 = 1_800_000_000
WATCH = 600


def market(ts, **kw):
    base = dict(ts=ts, btc_change_1h_pct=0.2, sol_change_1h_pct=-0.4, fear_greed=55, graduations_last_hour=30)
    base.update(kw)
    return model.MarketSnapshot(**base)


def coin(ts, mint="GOOD", **kw):
    """A coin that passes every rule and sits exactly on a 15% dip."""
    base = dict(
        ts=ts, mint=mint, symbol=mint, name=mint, pool_created_ts=T0 - 1_200,
        from_pumpfun_graduation=True, liquidity_usd=40_000.0, price_usd=0.00085,
        high_10m_usd=0.001, change_1h_pct=20.0, buys_5m=40, sells_5m=20,
        sell_volume_5m_usd=400.0, sell_volume_prev_5m_usd=1_000.0, holders=500,
        holders_prev=495, top10_pct=10.0, dev_pct=1.0, dev_has_sold=False,
        mint_authority_revoked=True, freeze_authority_revoked=True,
        lp_locked_or_burned_pct=100.0, bundled_wallets=1, insiders_pct=3.0,
        dangerous_delegation=False,
    )
    base.update(kw)
    return model.TokenSnapshot(**base)


def desk(cash=1_000.0, **settings_kw) -> Desk:
    return Desk(Settings.for_tests(**settings_kw), cash)


def warm(d: Desk, *mints, **kw):
    """First sighting at T0, so each coin passes the scanner at T0 + WATCH."""
    return d.tick(T0, market(T0), [coin(T0, m, **kw) for m in mints])


def reasons(d: Desk, mint="GOOD"):
    return [(s.stage, s.reason_code) for s in d.skips if s.mint == mint]


# --- the happy path ---------------------------------------------------------


def test_a_coin_is_watched_then_bought_on_paper():
    d = desk()
    first = warm(d, "GOOD")
    assert first.fills == () and reasons(d) == [("scanner", "watching")]
    second = d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH)])
    assert len(second.fills) == 1
    fill = second.fills[0]
    assert fill.side is model.Side.BUY and fill.verification is model.Verification.PAPER
    assert fill.cash_delta_usd == pytest.approx(-25.0)  # the max_ticket placeholder
    assert d.ledger.cash_usd == pytest.approx(975.0)
    pos = d.ledger.positions["GOOD"]
    assert pos.strategy is model.Strategy.GRAD
    assert pos.stop_price == pytest.approx(pos.entry_price * 0.75)
    assert pos.entry_price > 0.00085  # fees and price impact are in the fill


def test_the_ticket_is_twelve_percent_of_free_cash_when_no_cap_binds():
    d = desk(cash=100.0)
    warm(d, "GOOD")
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH)])
    assert d.ledger.fills[0].cash_delta_usd == pytest.approx(-12.0)


def test_a_half_score_buys_half_size():
    d = desk(cash=100.0)
    # organic 15 + flush 25 + anti-chase 25 + alive 25 * (6 / 30) = 70: the half tier
    kw = dict(buys_5m=4, sells_5m=2)
    warm(d, "GOOD", **kw)
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, **kw)])
    assert d.ledger.fills[0].cash_delta_usd == pytest.approx(-6.0)


# --- every stage can say no, with a reason -----------------------------------


@pytest.mark.parametrize(
    "kw, expected",
    [
        (dict(liquidity_usd=15_000.0), ("scanner", "liquidity_below_floor")),
        (dict(top10_pct=30.0), ("scanner", "top10_above_max")),
        (dict(change_1h_pct=250.0), ("scanner", "pumped_1h")),
        (dict(copycat_of="OLDCOIN"), ("scanner", "copycat_name")),
        (dict(top10_pct=25.0), ("analyst", "layer_4_red")),
        (dict(mint_authority_revoked=None), ("analyst", "layer_1_unknown")),
        (dict(dangerous_delegation=True), ("analyst", "layer_8_red")),
        (dict(buys_5m=0, sells_5m=0), ("brain", "score_below_pass")),
        (dict(price_usd=0.0009), ("executor", "no_entry_signal")),  # a 10% pullback: scores, but no dip
    ],
)
def test_a_refusal_names_its_stage_and_reason(kw, expected):
    d = desk()
    warm(d, "GOOD", **kw)
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, **kw)])
    assert d.ledger.fills == []
    assert reasons(d)[-1] == expected


def test_no_entry_signal_lists_each_strategy_reason():
    d = desk()
    warm(d, "GOOD", price_usd=0.0009)
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, price_usd=0.0009)])
    detail = d.skips[-1].detail
    assert "GRAD:no_dip" in detail and "DIP:no_dip" in detail


def test_a_scanner_kill_is_permanent():
    d = desk()
    warm(d, "GOOD", liquidity_usd=15_000.0)
    for step in (1, 2, 3):
        ts = T0 + WATCH * step
        d.tick(ts, market(ts), [coin(ts)])  # liquidity is back; the kill stands
    assert d.ledger.fills == []
    assert reasons(d) == [("scanner", "liquidity_below_floor")]


def test_a_skip_is_recorded_once_per_reason_not_once_per_tick():
    d = desk()
    warm(d, "GOOD", price_usd=0.0009)
    for step in (1, 2, 3, 4):
        ts = T0 + WATCH * step
        d.tick(ts, market(ts), [coin(ts, price_usd=0.0009)])
    assert reasons(d) == [("scanner", "watching"), ("executor", "no_entry_signal")]


@pytest.mark.parametrize(
    "mkt, code",
    [
        (dict(btc_change_1h_pct=-2.5), "market_blocks_buys"),
        (dict(sol_change_1h_pct=-4.0), "market_blocks_buys"),
        (dict(fear_greed=20), "market_blocks_buys"),
        (dict(graduations_last_hour=5), "market_blocks_buys"),
        (dict(fear_greed=None), "market_blocks_buys"),
    ],
)
def test_red_quiet_or_missing_market_data_blocks_every_buy(mkt, code):
    d = desk()
    warm(d, "GOOD")
    out = d.tick(T0 + WATCH, market(T0 + WATCH, **mkt), [coin(T0 + WATCH)])
    assert out.blocks_new_buys and d.ledger.fills == []
    assert reasons(d)[-1] == ("brain", code)


def test_no_market_reading_at_all_blocks_every_buy():
    d = desk()
    warm(d, "GOOD")
    out = d.tick(T0 + WATCH, None, [coin(T0 + WATCH)])
    assert out.blocks_new_buys and d.ledger.fills == []


def test_a_lesson_blocks_and_the_skip_names_it():
    book = lessons.LessonBook()
    book.add(model.Lesson("L-OLD-1", T0 - 99, "OLD", "top10_pct >= 10", "lost on OLD"))
    d = Desk(Settings.for_tests(), 1_000.0, lesson_book=book)
    warm(d, "GOOD")
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH)])
    assert d.ledger.fills == []
    last = d.skips[-1]
    assert (last.stage, last.reason_code) == ("brain", "lesson_blocks")
    assert "L-OLD-1" in last.detail and "top10_pct >= 10" in last.detail


def test_open_position_limit_holds_within_one_tick():
    d = desk()  # max_open_positions placeholder is 3
    names = ["A1", "A2", "A3", "A4"]
    warm(d, *names)
    out = d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, n) for n in names])
    assert [f.mint for f in out.fills] == ["A1", "A2", "A3"]  # equal scores, so mint order
    assert reasons(d, "A4")[-1] == ("brain", "max_open_positions")
    assert d.ledger.cash_usd == pytest.approx(925.0)


def test_the_best_score_is_tried_first():
    d = desk(max_open_positions=1)
    warm(d, "A1", "B2")
    out = d.tick(
        T0 + WATCH, market(T0 + WATCH),
        [coin(T0 + WATCH, "A1", top10_pct=20.0), coin(T0 + WATCH, "B2", top10_pct=5.0)],
    )
    assert [f.mint for f in out.fills] == ["B2"]


# --- exits -------------------------------------------------------------------


def _bought(d: Desk, mint="GOOD"):
    warm(d, mint)
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, mint)])
    return d.ledger.positions[mint]


def test_the_stop_sells_everything_and_writes_an_autopsy_and_a_lesson():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [coin(ts, price_usd=pos.stop_price * 0.99)])
    assert [f.side for f in out.fills] == [model.Side.SELL]
    assert out.fills[0].exit_reason is model.ExitReason.STOP
    assert "GOOD" not in d.ledger.positions
    loss = d.losses[0]
    assert loss["exit_reason"] == "stop" and loss["pnl_usd"] < 0
    assert loss["cash_at_entry_usd"] == pytest.approx(1_000.0)
    assert loss["loss_pct_of_cash"] == pytest.approx(-loss["pnl_usd"] / 1_000.0 * 100)
    # liquidity was the entry reading closest to its limit, so the lesson is about liquidity
    assert loss["lesson"] == out.lessons_added[0].check
    assert out.lessons_added[0].check.startswith("liquidity_usd <= ")
    assert d.violations == []  # a $25 ticket cannot lose 3% of $1,000


def test_a_gap_through_the_stop_is_reported_as_a_violation():
    d = desk(cash=100.0)  # ticket $12, budget $3
    _bought(d)
    ts = T0 + WATCH + 60
    d.tick(ts, market(ts), [coin(ts, price_usd=0.0002)])  # far below the stop
    loss = d.losses[0]
    assert -loss["pnl_usd"] > loss["budget_usd"] == pytest.approx(3.0)
    assert [v["rule"] for v in d.violations] == ["loss_exceeded_risk_budget"]
    text = report.render_morning(d.night_report(), d.settings.risk_per_trade_pct)
    assert "[FAIL] every loss within 3% of cash" in text
    assert "[FAIL] zero rule violations" in text


def test_take_half_at_double_then_trail_the_rest():
    d = desk()
    pos = _bought(d)
    t1 = T0 + WATCH + 60
    first = d.tick(t1, market(t1), [coin(t1, price_usd=pos.entry_price * 2.0, high_10m_usd=pos.entry_price * 2.0)])
    assert first.fills[0].exit_reason is model.ExitReason.TAKE
    assert first.fills[0].qty == pytest.approx(pos.qty * 0.5)
    left = d.ledger.positions["GOOD"]
    assert left.took_first_take and left.qty == pytest.approx(pos.qty * 0.5)
    t2 = t1 + 60
    peak = pos.entry_price * 3.0
    d.tick(t2, market(t2), [coin(t2, price_usd=peak, high_10m_usd=peak)])
    trailed = d.ledger.positions["GOOD"]
    assert trailed.stop_price == pytest.approx(peak * 0.75)
    assert trailed.stop_price >= left.stop_price
    t3 = t2 + 60
    last = d.tick(t3, market(t3), [coin(t3, price_usd=peak * 0.74, high_10m_usd=peak)])
    assert last.fills[0].exit_reason is model.ExitReason.TRAIL
    assert "GOOD" not in d.ledger.positions
    assert d.losses == [] and d.lessons_added == []
    assert d.ledger.realized_pnl_usd > 0


def test_red_takes_at_one_and_a_half_times():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts, btc_change_1h_pct=-3.0), [coin(ts, price_usd=pos.entry_price * 1.5)])
    assert out.mode is model.Mode.RED
    assert out.fills[0].exit_reason is model.ExitReason.TAKE


def test_sells_run_before_buys_in_the_same_tick():
    d = desk()
    pos = _bought(d, "HELD")
    warm_ts = T0 + WATCH + 10
    # NEXT has deeper liquidity, so the lesson HELD's loss writes in this tick does not block it
    deep = dict(liquidity_usd=90_000.0)
    d.tick(warm_ts, market(warm_ts), [coin(warm_ts, "HELD"), coin(warm_ts, "NEXT", **deep)])
    ts = warm_ts + WATCH
    out = d.tick(ts, market(ts), [coin(ts, "HELD", price_usd=pos.stop_price * 0.9), coin(ts, "NEXT", **deep)])
    assert [(f.side, f.mint) for f in out.fills] == [(model.Side.SELL, "HELD"), (model.Side.BUY, "NEXT")]


def test_a_coin_is_not_bought_twice_in_one_night():
    d = desk()
    pos = _bought(d)
    t1 = T0 + WATCH + 60
    d.tick(t1, market(t1), [coin(t1, price_usd=pos.stop_price * 0.99)])
    t2 = t1 + 60
    out = d.tick(t2, market(t2), [coin(t2, liquidity_usd=90_000.0)])  # clear of the new lesson
    assert out.fills == ()
    assert reasons(d)[-1] == ("desk", "already_traded_tonight")


def test_a_held_coin_with_no_reading_or_no_price_alerts_once_and_is_kept():
    d = desk()
    _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [])
    assert out.fills == () and "GOOD" in d.ledger.positions
    assert len(out.alerts) == 1 and "no_reading_for_position GOOD" in out.alerts[0]
    again = d.tick(ts + 30, market(ts + 30), [])
    assert again.alerts == ()  # the same trouble is not repeated on every tick it lasts
    out2 = d.tick(ts + 60, market(ts + 60), [coin(ts + 60, price_usd=None)])
    assert len(out2.alerts) == 1 and "no_price_for_position GOOD" in out2.alerts[0]
    fine = d.tick(ts + 120, market(ts + 120), [coin(ts + 120)])
    assert fine.alerts == () and "GOOD" in d.ledger.positions
    back = d.tick(ts + 180, market(ts + 180), [])
    assert len(back.alerts) == 1 and "no_reading_for_position GOOD" in back.alerts[0]  # it cleared, so it alerts anew
    assert len(d.night_report()["alerts"]) == 3


def test_the_night_stop_halts_new_buys():
    d = desk(max_ticket_usd=500.0, max_total_exposure_pct=100.0)
    _bought(d, "BAD")  # a $120 ticket, 12% of $1,000
    t1 = T0 + WATCH + 10
    d.tick(t1, market(t1), [coin(t1, "BAD"), coin(t1, "NEXT", liquidity_usd=80_000.0)])
    t2 = t1 + WATCH
    out = d.tick(
        t2, market(t2),
        [coin(t2, "BAD", price_usd=0.00001), coin(t2, "NEXT", liquidity_usd=80_000.0)],
    )
    assert [f.side for f in out.fills] == [model.Side.SELL]
    assert d.ledger.realized_pnl_usd < -100.0  # past 10% of the night's starting equity
    assert reasons(d, "NEXT")[-1] == ("brain", "night_stop")


# --- the human gate ----------------------------------------------------------


class _FakeLive:
    """A stand-in with kind LIVE. It fills at spot and touches nothing."""

    kind = model.ExecutorKind.LIVE

    def __init__(self):
        self.seen = []

    def execute(self, intent, snapshot, approval=None):
        self.seen.append((intent.order_id, approval))
        price = snapshot.price_usd
        if intent.side is model.Side.BUY:
            usd, qty = intent.usd, intent.usd / price
        else:
            usd, qty = intent.qty * price, intent.qty
        return model.Fill(
            order_id=intent.order_id, ts=intent.ts, mint=intent.mint, symbol=intent.symbol,
            side=intent.side, qty=qty, price=price, gross_usd=usd, fees_usd=0.0,
            cash_delta_usd=-usd if intent.side is model.Side.BUY else usd,
            verification=model.Verification.VERIFIED, exit_reason=intent.exit_reason,
        )


def _live_snapshot(ts):
    return coin(ts, trading_disabled=False, venue_warning="")


def test_a_live_executor_gets_nothing_without_a_human_approval():
    fake = _FakeLive()
    d = Desk(Settings.for_tests(), 1_000.0, executor=fake)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    out = d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    assert out.fills == () and fake.seen == [] and d.ledger.fills == [] and d.ledger.cash_usd == 1_000.0
    assert reasons(d)[-1] == ("executor", "approval_missing")
    assert d.skips[-1].detail == "a human approval is required for this order"


def test_an_approval_for_another_order_is_refused():
    fake = _FakeLive()
    wrong = lambda intent: model.HumanApproval("some-other-order", "tee", intent.ts)  # noqa: E731
    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=wrong)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    assert fake.seen == [] and d.ledger.fills == []
    assert reasons(d)[-1] == ("executor", "approval_missing")
    assert d.skips[-1].detail == "the approval is for a different order"


def test_a_matching_approval_lets_one_order_through_and_is_handed_to_the_executor():
    fake = _FakeLive()
    asked = []

    def approve(intent):
        asked.append(intent.order_id)
        return model.HumanApproval(intent.order_id, "tee", intent.ts, "approved on a card")

    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=approve)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    assert len(asked) == 1 and fake.seen[0][0] == asked[0]
    assert fake.seen[0][1].approved_by == "tee"
    assert d.night_report()["real_orders_sent"] == 1


def test_a_live_run_refuses_a_snapshot_with_no_venue_checks():
    fake = _FakeLive()
    ok = lambda intent: model.HumanApproval(intent.order_id, "tee", intent.ts)  # noqa: E731
    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=ok)
    warm(d, "GOOD")  # trading_disabled and venue_warning are None
    d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH)])
    assert fake.seen == []
    assert reasons(d)[-1] == ("executor", "venue_checks_missing")


def test_the_paper_executor_never_asks_for_approval():
    asked = []
    d = Desk(Settings.for_tests(), 1_000.0, approve=lambda i: asked.append(i))
    _bought(d)
    assert asked == [] and len(d.ledger.fills) == 1


# --- bad input ---------------------------------------------------------------


def test_ticks_and_snapshots_must_be_in_order_and_unique():
    d = desk()
    d.tick(T0, market(T0), [])
    with pytest.raises(ValueError, match="back in time"):
        d.tick(T0 - 1, market(T0 - 1), [])
    with pytest.raises(ValueError, match="two snapshots"):
        d.tick(T0 + 1, market(T0 + 1), [coin(T0 + 1), coin(T0 + 1)])
    with pytest.raises(ValueError, match="after the tick"):
        d.tick(T0 + 2, market(T0 + 2), [coin(T0 + 99)])
    with pytest.raises(ValueError):
        Desk(Settings.for_tests(), 0.0)


# --- the night report and the morning text -----------------------------------


def _story():
    """A short night: one winner, one loser, and a coin the loser's lesson blocks."""
    frames = []

    def add(ts, tokens, **mkt):
        frames.append({"ts": ts, "market": {k: v for k, v in dataclasses.asdict(market(ts, **mkt)).items() if k != "ts"},
                       "tokens": [{k: v for k, v in dataclasses.asdict(t).items()
                                   if k != "ts" and v is not None and v != ()} for t in tokens]})

    t = T0
    add(t, [coin(t, "WINR"), coin(t, "LOSR"), coin(t, "THIN", liquidity_usd=15_000.0)])
    t = T0 + WATCH
    add(t, [coin(t, "WINR"), coin(t, "LOSR"), coin(t, "THIN")])
    t += 60
    add(t, [coin(t, "WINR", price_usd=0.0018, high_10m_usd=0.0018), coin(t, "LOSR", price_usd=0.0006),
            coin(t, "LATE")])
    t += 60
    add(t, [coin(t, "WINR", price_usd=0.0030, high_10m_usd=0.0030), coin(t, "LATE")], btc_change_1h_pct=-3.0)
    t += WATCH
    add(t, [coin(t, "WINR", price_usd=0.0023, high_10m_usd=0.0030), coin(t, "LATE")])
    return frames


def test_the_night_report_is_plain_data_and_adds_up():
    frames = [replay.parse_frame(f) for f in _story()]
    out = replay.run(frames, Settings.for_tests(), 1_000.0)
    json.dumps(out)  # every value is JSON-ready
    assert out["executor"] == "paper" and out["real_orders_sent"] == 0
    assert out["verification"] == {"paper": len(out["fills"]), "verified": 0, "unverified": 0}
    assert out["buys"] == 2 and out["sells"] == 3 and out["open_positions"] == []
    assert out["ending_equity_usd"] == pytest.approx(out["ending_cash_usd"])
    assert out["night_pnl_usd"] == pytest.approx(out["realized_pnl_usd"])
    assert out["ending_cash_usd"] == pytest.approx(1_000.0 + sum(f["cash_delta_usd"] for f in out["fills"]))
    # LOSR's stop and WINR's take fire in the same tick; positions are visited in mint order
    assert [f["exit_reason"] for f in out["fills"] if f["side"] == "SELL"] == ["stop", "take", "trail"]
    assert [loss["symbol"] for loss in out["losses"]] == ["LOSR"]
    assert out["lessons_added_tonight"] == [out["losses"][0]["lesson"]]
    assert out["skips_by_reason"]["scanner:liquidity_below_floor"] == 1
    assert out["skips_by_reason"]["brain:lesson_blocks"] == 1  # LATE, blocked by LOSR's lesson
    assert [m["mode"] for m in out["mode_log"]] == ["GREEN", "RED", "GREEN"]
    assert "no_live_executor" in out["live_gate_blockers"]
    assert sum(out["skips_by_reason"].values()) == len(out["skips"])


def test_the_same_night_twice_gives_the_same_report():
    frames = [replay.parse_frame(f) for f in _story()]
    a = replay.run(frames, Settings.for_tests(), 1_000.0)
    b = replay.run(frames, Settings.for_tests(), 1_000.0)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_the_morning_text_answers_the_four_checks_and_claims_no_verified_order():
    frames = [replay.parse_frame(f) for f in _story()]
    out = replay.run(frames, Settings.for_tests(), 1_000.0)
    text = report.render_morning(out, 3.0)
    assert "This was a paper night. No money moved" in text
    assert "Real orders sent: 0." in text
    assert "order verification was never exercised" in text
    for name in ("a reason for every skip", "every loss within 3% of cash", "zero rule violations"):
        assert f"[pass] {name}" in text
    # A paper night sends no real order, so that check is not a pass. It is not applicable.
    assert "[n/a] zero unverified orders" in text and "[pass] zero unverified orders" not in text
    assert "closed: " in text and "no_live_executor" in text
    assert chr(0x2014) not in text and chr(0x2013) not in text
    checks = report.morning_checks(out, 3.0)
    assert [c["ok"] for c in checks] == [True, True, None, True]
    assert "5 ticks, 13 readings, 4 different coins" in text
    assert f"first tick {T0}, last tick {T0 + 2 * WATCH + 120}" in text
    assert "Not tested by this night" in text
    assert "price drift between the decision and the order" in text


def test_an_empty_night_reports_cleanly():
    out = replay.run([], Settings.for_tests(), 500.0)
    assert out["fills"] == [] and out["night_pnl_usd"] == 0
    text = report.render_morning(out, 3.0)
    assert "no ticks ran" in text and "starting cash    $500.00" in text


# --- replay input -------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {"ts": "soon", "tokens": []},
        {"ts": True, "tokens": []},
        {"ts": 1, "tokens": {}},
        {"ts": 1, "market": [], "tokens": []},
        {"ts": 1, "extra": 1},
        {"ts": 1, "market": {"btc": 1}},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "prise_usd": 1}]},
        {"ts": 1, "tokens": [{"symbol": "S"}]},
        {"ts": 1, "tokens": [{"mint": "", "symbol": "S"}]},
        {"ts": 1, "tokens": ["M"]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "liquidity_usd": "40000"}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "price_usd": "x"}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "liquidity_usd": True}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "liquidity_usd": float("inf")}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "price_usd": float("nan")}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "holders": "5"}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "holders": 5.5}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "ts": 1.5}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "from_pumpfun_graduation": "yes"}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "dev_has_sold": 1}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "copycat_of": 7}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "name": None}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "narrative_tags": 5}]},
        {"ts": 1, "tokens": [{"mint": "M", "symbol": "S", "narrative_tags": ["ai", 3]}]},
        {"ts": 1, "tokens": [{"mint": 5, "symbol": "S"}]},
        {"ts": 1, "market": {"btc_change_1h_pct": "x"}},
        {"ts": 1, "market": {"fear_greed": 55.5}},
        {"ts": 1, "market": {"graduations_last_hour": True}},
        {"ts": 1.0, "tokens": []},
    ],
)
def test_a_malformed_frame_is_refused(bad):
    with pytest.raises(replay.TimelineError):
        replay.parse_frame(bad)


def test_a_token_takes_the_tick_time_unless_it_carries_its_own():
    frame = replay.parse_frame({"ts": 50, "market": None, "tokens": [
        {"mint": "M", "symbol": "S"}, {"mint": "N", "symbol": "T", "ts": 40, "narrative_tags": ["ai"]}]})
    assert [t.ts for t in frame.tokens] == [50, 40]
    assert frame.market is None and frame.tokens[1].narrative_tags == ("ai",)


def test_load_timeline_skips_blank_lines_and_names_the_bad_line(tmp_path):
    good = tmp_path / "night.jsonl"
    good.write_text("\n".join(json.dumps(f) for f in _story()) + "\n\n")
    assert len(replay.load_timeline(good)) == 5
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(_story()[0]) + "\n{oops\n")
    with pytest.raises(replay.TimelineError, match="line 2"):
        replay.load_timeline(bad)
    with pytest.raises(replay.TimelineError):
        replay.load_timeline(tmp_path / "missing.jsonl")


# --- the committed demo -------------------------------------------------------

FIXTURE = PKG / "fixtures" / "synthetic_night.jsonl"
PLACEHOLDERS = PKG / "fixtures" / "settings.test-placeholders.json"


def test_the_committed_fixture_is_exactly_the_story_built_here():
    expected = "".join(json.dumps(f, sort_keys=True) + "\n" for f in _story())
    assert FIXTURE.read_text(encoding="utf-8") == expected


def test_the_placeholder_settings_file_matches_for_tests():
    assert Settings.from_file(PLACEHOLDERS) == Settings.for_tests()


def test_the_command_line_prints_the_report_and_refuses_bad_input(capsys, tmp_path):
    args = ["--timeline", str(FIXTURE), "--settings", str(PLACEHOLDERS), "--cash", "1000"]
    assert replay.main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith("OVERNIGHT DESK, MORNING REPORT") and "LOSR" in out
    assert replay.main(args + ["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["buys"] == 2
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    assert replay.main(["--timeline", str(FIXTURE), "--settings", str(empty), "--cash", "1000"]) == 2
    assert "refused" in capsys.readouterr().err
    assert replay.main(["--timeline", str(tmp_path / "none.jsonl"), "--settings", str(PLACEHOLDERS),
                        "--cash", "1000"]) == 2
    assert replay.main(args[:-1] + ["0"]) == 2


# --- gaps a verifier found by mutating the engine, the report and the replay ---


def test_a_null_reading_and_a_whole_number_for_a_float_are_accepted():
    frame = replay.parse_frame({"ts": 9, "market": {"btc_change_1h_pct": None, "fear_greed": 40},
                                "tokens": [{"mint": "M", "symbol": "S", "liquidity_usd": 40000,
                                            "price_usd": None, "copycat_of": None}]})
    assert frame.tokens[0].liquidity_usd == 40000 and frame.tokens[0].price_usd is None
    assert frame.market.btc_change_1h_pct is None and frame.market.fear_greed == 40


def test_a_token_that_is_not_an_object_is_named_as_such():
    with pytest.raises(replay.TimelineError, match="token 0 must be an object, got str"):
        replay.parse_frame({"ts": 1, "tokens": ["M"]})


def test_a_nan_or_infinity_literal_in_a_timeline_is_refused_with_its_line(tmp_path):
    for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
        bad = tmp_path / "bad.jsonl"
        bad.write_text(json.dumps(_story()[0]) + "\n"
                       + '{"ts": 5, "tokens": [{"mint": "M", "symbol": "S", "price_usd": %s}]}\n' % literal)
        with pytest.raises(replay.TimelineError, match="line 2"):
            replay.load_timeline(bad)


@pytest.mark.parametrize("cash", ["inf", "nan", "-5", "0"])
def test_the_command_line_refuses_a_cash_amount_that_is_not_positive_and_finite(cash, capsys):
    code = replay.main(["--timeline", str(FIXTURE), "--settings", str(PLACEHOLDERS), f"--cash={cash}"])
    assert code == 2 and "refused" in capsys.readouterr().err


def test_the_command_line_refuses_bad_timelines_without_a_traceback(tmp_path, capsys):
    def run(lines):
        path = tmp_path / "t.jsonl"
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        code = replay.main(["--timeline", str(path), "--settings", str(PLACEHOLDERS), "--cash", "1000"])
        return code, capsys.readouterr().err

    tok = {"mint": "M", "symbol": "S"}
    cases = [
        [{"ts": 1, "tokens": [dict(tok, liquidity_usd="40000")]}],
        [{"ts": 1, "tokens": [dict(tok, price_usd="x")]}],
        [{"ts": 1, "market": {"btc_change_1h_pct": "x"}, "tokens": []}],
        [{"ts": 1, "tokens": [dict(tok, narrative_tags=5)]}],
        [{"ts": 1, "tokens": [tok, tok]}],                       # the same mint twice in one tick
        [{"ts": 9, "tokens": []}, {"ts": 3, "tokens": []}],     # ticks out of order
        [{"ts": 1, "tokens": [dict(tok, ts=99)]}],               # a snapshot from after its tick
    ]
    for lines in cases:
        code, err = run(lines)
        assert code == 2 and err.startswith("refused: "), lines
    assert replay.main(["--timeline", str(tmp_path), "--settings", str(PLACEHOLDERS), "--cash", "1000"]) == 2
    assert capsys.readouterr().err.startswith("refused: ")


@pytest.mark.parametrize("cash", [float("inf"), float("nan"), -1.0, 0, True, "1000", None])
def test_a_desk_needs_positive_finite_starting_cash(cash):
    with pytest.raises(ValueError, match="positive, finite"):
        Desk(Settings.for_tests(), cash)


def test_a_snapshot_stamped_at_the_tick_is_accepted_and_one_second_later_is_not():
    d = desk()
    d.tick(T0, market(T0), [coin(T0)])
    with pytest.raises(ValueError, match="after the tick"):
        d.tick(T0 + 10, market(T0 + 10), [coin(T0 + 11)])


def test_a_refused_tick_changes_nothing():
    d = desk()
    pos = _bought(d)
    before = json.dumps(d.night_report(), sort_keys=True)
    ts = T0 + WATCH + 60
    with pytest.raises(ValueError, match="after the tick"):
        d.tick(ts, market(ts), [coin(ts, price_usd=pos.entry_price * 5), coin(ts + 1, "LATER")])
    with pytest.raises(ValueError, match="two snapshots"):
        d.tick(ts, market(ts), [coin(ts, price_usd=pos.entry_price * 5), coin(ts, price_usd=1.0)])
    assert json.dumps(d.night_report(), sort_keys=True) == before
    assert d.ledger.positions["GOOD"] == pos
    d.tick(ts, market(ts), [coin(ts)])  # the same time is still open to a good tick


def test_a_held_coin_is_never_sent_to_the_buy_pass():
    d = desk()
    _bought(d)
    for step in (1, 2, 3):
        ts = T0 + WATCH + 60 * step
        out = d.tick(ts, market(ts), [coin(ts)])
        assert out.fills == () and out.skips == ()
    assert ("desk", "already_traded_tonight") not in reasons(d)
    assert len(d.ledger.fills) == 1


def _stop_loss_night(**settings_kw):
    d = desk(**settings_kw)
    pos = _bought(d)
    ts = T0 + WATCH + 60
    d.tick(ts, market(ts), [coin(ts, price_usd=pos.stop_price * 0.99)])
    return d


def test_the_violation_line_is_the_risk_budget_to_the_cent():
    lost = -_stop_loss_night().losses[0]["pnl_usd"]  # the ticket is capped at $25, so the loss is fixed
    assert 6.5 < lost < 7.5  # above $6.25, so the capped $25 ticket still binds at the budgets below
    # budget = $1,000 of cash * risk_per_trade_pct / 100, so one cent of budget is 0.001 points
    over = _stop_loss_night(risk_per_trade_pct=(lost - 0.01) / 10)
    under = _stop_loss_night(risk_per_trade_pct=(lost + 0.01) / 10)
    assert -over.losses[0]["pnl_usd"] == pytest.approx(lost) == -under.losses[0]["pnl_usd"]
    assert [v["rule"] for v in over.violations] == ["loss_exceeded_risk_budget"]
    assert over.violations[0]["loss_usd"] == pytest.approx(lost)
    assert over.violations[0]["budget_usd"] == pytest.approx(lost - 0.01)
    assert under.violations == []


def test_a_sell_on_a_live_executor_needs_its_own_approval():
    fake = _FakeLive()
    asked = []

    def approve(intent):
        asked.append((intent.side, intent.order_id))
        return model.HumanApproval(intent.order_id, "tee", intent.ts)

    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=approve)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    pos = d.ledger.positions["GOOD"]
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [dataclasses.replace(_live_snapshot(ts), price_usd=pos.stop_price * 0.9)])
    assert [side for side, _ in asked] == [model.Side.BUY, model.Side.SELL]
    assert out.fills[0].side is model.Side.SELL
    sell_id, sell_approval = fake.seen[1]
    assert sell_id == asked[1][1] and sell_approval.order_id == sell_id
    assert "GOOD" not in d.ledger.positions


def test_a_refused_sell_leaves_the_position_and_the_ledger_untouched():
    fake = _FakeLive()

    def buys_only(intent):
        if intent.side is model.Side.BUY:
            return model.HumanApproval(intent.order_id, "tee", intent.ts)
        return None

    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=buys_only)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    pos = d.ledger.positions["GOOD"]
    cash = d.ledger.cash_usd
    ts = T0 + WATCH + 60
    for price in (pos.stop_price * 0.9, pos.entry_price * 2.5):  # a stop, then a take
        out = d.tick(ts, market(ts), [dataclasses.replace(_live_snapshot(ts), price_usd=price)])
        assert out.fills == ()
        assert d.ledger.positions["GOOD"] == pos  # same quantity, same stop, first take not marked
        assert d.ledger.cash_usd == cash and len(d.ledger.fills) == 1 and len(fake.seen) == 1
    # An exit that was decided and not carried out is a rule violation, once per reason.
    assert [(v["rule"], v["exit_reason"]) for v in d.violations] == [
        ("exit_not_executed", "stop"), ("exit_not_executed", "take"),
    ]
    assert [a.split()[1] for a in d.alerts] == ["exit_not_executed", "exit_not_executed"]
    assert "approval_missing" in d.alerts[0]
    assert report.morning_checks(d.night_report(), 3.0)[3]["ok"] is False


def test_a_refused_exit_is_one_violation_however_long_it_lasts_and_clears_when_sold():
    fake = _FakeLive()
    allow = {"sell": False}

    def approve(intent):
        if intent.side is model.Side.BUY or allow["sell"]:
            return model.HumanApproval(intent.order_id, "tee", intent.ts)
        return None

    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=approve)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    low = d.ledger.positions["GOOD"].stop_price * 0.9
    ts = T0 + WATCH
    for step in (60, 120, 180):
        d.tick(ts + step, market(ts + step), [dataclasses.replace(_live_snapshot(ts + step), price_usd=low)])
    assert len(d.violations) == 1 and len(d.alerts) == 1
    allow["sell"] = True
    out = d.tick(ts + 240, market(ts + 240), [dataclasses.replace(_live_snapshot(ts + 240), price_usd=low)])
    assert out.fills[0].exit_reason is model.ExitReason.STOP and "GOOD" not in d.ledger.positions
    assert d._unexecuted == set() and d._alerting == {}


def _loss(**kw):
    base = dict(ts=1, mint="M", symbol="S", strategy="DIP", exit_reason="stop", entry_ts=0, entry_price=1.0,
                exit_price=0.7, pnl_usd=-3.0, cash_at_entry_usd=500.0, loss_pct_of_cash=0.6,
                budget_usd=15.0, over_budget=False, lesson="top10_pct >= 20.0")
    base.update(kw)
    return base


def _fill(**kw):
    base = dict(order_id="1-0001", ts=1, mint="M", symbol="S", side="BUY", qty=1.0, price=1.0, gross_usd=1.0,
                fees_usd=0.0, cash_delta_usd=-1.0, verification="paper", exit_reason=None)
    base.update(kw)
    return base


def _checks(rep):
    return [c["ok"] for c in report.morning_checks(rep, 3.0)]


def _clean_report():
    """A night that gave every one of the four checks something to test, and passed each."""
    rep = replay.run([], Settings.for_tests(), 500.0)
    rep.update(ticks=1, snapshots_seen=1, coins_seen=1, first_ts=1, last_ts=1, real_orders_sent=1)
    rep["fills"] = [_fill(verification="verified")]
    rep["verification"] = {"paper": 0, "verified": 1, "unverified": 0}
    rep["losses"] = [_loss()]
    return rep


def test_a_check_the_night_did_not_test_reads_not_applicable_and_never_pass():
    empty = replay.run([], Settings.for_tests(), 500.0)
    assert _checks(empty) == [None, None, None, None]
    text = report.render_morning(empty, 3.0)
    assert text.count("[n/a]") == 4 and "[pass]" not in text and "[FAIL]" not in text
    assert "NO COIN WAS SEEN" in text and "0 ticks, 0 readings, 0 different coins" in text
    # Each check turns real on exactly the fact that gives it something to test.
    seen = replay.run([], Settings.for_tests(), 500.0)
    seen["coins_seen"] = 1
    assert _checks(seen) == [True, None, None, None]
    lost = replay.run([], Settings.for_tests(), 500.0)
    lost["losses"] = [_loss()]
    assert _checks(lost) == [None, True, None, None]
    sent = replay.run([], Settings.for_tests(), 500.0)
    sent["real_orders_sent"] = 1
    assert _checks(sent) == [None, None, True, None]
    ticked = replay.run([], Settings.for_tests(), 500.0)
    ticked["ticks"] = 1
    assert _checks(ticked) == [None, None, None, True]


def test_each_morning_check_fails_alone_on_the_data_that_should_fail_it():
    assert _checks(_clean_report()) == [True, True, True, True]

    no_reason = _clean_report()
    no_reason["skips"] = [dict(ts=1, mint="M", symbol="S", stage="brain", reason_code="", detail="")]
    assert _checks(no_reason) == [False, True, True, True]

    for bad_loss in (_loss(over_budget=True), _loss(loss_pct_of_cash=None), _loss(exit_reason=""),
                     _loss(exit_reason=None)):
        rep = _clean_report()
        rep["losses"] = [_loss(), bad_loss]
        assert _checks(rep) == [True, False, True, True], bad_loss

    # The desk decides once whether a loss is over its budget, and the report reads that verdict.
    at_limit = _clean_report()
    at_limit["losses"] = [_loss(loss_pct_of_cash=3.0000001, over_budget=False), _loss(lesson=None)]
    assert _checks(at_limit) == [True, True, True, True]  # a missing lesson is counted, not failed
    assert "1 with no lesson written" in report.morning_checks(at_limit, 3.0)[1]["evidence"]

    unverified = _clean_report()
    unverified["fills"] = [_fill(verification="unverified")]
    unverified["verification"] = {"paper": 0, "verified": 0, "unverified": 1}
    assert _checks(unverified) == [True, True, False, True]
    assert report.morning_checks(unverified, 3.0)[2]["evidence"] == "1 real orders sent, 1 unverified"

    violated = _clean_report()
    violated["violations"] = [dict(ts=1, rule="loss_exceeded_risk_budget", mint="M", symbol="S", loss_usd=9.0,
                                   budget_usd=3.0, detail="over")]
    assert _checks(violated) == [True, True, True, False]


def test_the_morning_text_prints_fail_for_each_failed_check():
    rep = _clean_report()
    rep["skips"] = [dict(ts=1, mint="M", symbol="S", stage="brain", reason_code="", detail="")]
    rep["losses"] = [_loss(loss_pct_of_cash=None)]
    rep["fills"] = [_fill(verification="unverified")]
    rep["verification"] = {"paper": 0, "verified": 0, "unverified": 1}
    rep["real_orders_sent"] = 1
    rep["violations"] = [dict(ts=1, rule="r", mint="M", symbol="S", loss_usd=9.0, budget_usd=3.0, detail="d")]
    text = report.render_morning(rep, 3.0)
    assert text.count("[FAIL]") == 4 and "[pass]" not in text
    assert "unknown of the cash held at entry" in text


# --- round 2: an order that cannot be filled is recorded, and the night goes on ---


def test_a_drained_pool_is_written_off_as_a_total_loss_and_the_night_goes_on():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [coin(ts, liquidity_usd=0.0)])  # the price reading has not moved
    assert [f.exit_reason for f in out.fills] == [model.ExitReason.LIQUIDITY_PULLED]
    fill = out.fills[0]
    assert (fill.price, fill.gross_usd, fill.fees_usd, fill.cash_delta_usd) == (0.0, 0.0, 0.0, 0.0)
    assert fill.qty == pytest.approx(pos.qty) and "GOOD" not in d.ledger.positions
    assert d.losses[0]["pnl_usd"] == pytest.approx(-pos.cost_usd)
    assert d.losses[0]["loss_pct_of_cash"] == pytest.approx(2.5)  # all of a $25 ticket on $1,000 of cash
    rep = d.night_report()
    assert rep["ending_equity_usd"] == pytest.approx(1_000.0 - pos.cost_usd)
    assert "Exit: liquidity_pulled" in report.render_morning(rep, 3.0)


def test_a_drained_pool_with_no_price_at_all_is_still_exited():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [coin(ts, liquidity_usd=0.0, price_usd=None)])
    assert [f.exit_reason for f in out.fills] == [model.ExitReason.LIQUIDITY_PULLED]
    assert out.fills[0].cash_delta_usd == 0.0 and "GOOD" not in d.ledger.positions
    assert d.losses[0]["pnl_usd"] == pytest.approx(-pos.cost_usd)


def test_a_total_loss_past_the_risk_budget_is_reported_as_a_violation():
    d = desk(cash=100.0)  # the ticket is 12% of cash, four times the 3% budget
    pos = _bought(d)
    ts = T0 + WATCH + 60
    d.tick(ts, market(ts), [coin(ts, liquidity_usd=0.0)])
    assert d.losses[0]["over_budget"] is True
    assert d.losses[0]["loss_pct_of_cash"] == pytest.approx(pos.cost_usd)  # $12 of $100
    assert [v["rule"] for v in d.violations] == ["loss_exceeded_risk_budget"]
    checks = report.morning_checks(d.night_report(), 3.0)
    assert [c["ok"] for c in checks] == [True, False, None, False]


def test_an_exit_the_model_cannot_price_is_a_violation_and_the_night_goes_on():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    low = pos.stop_price * 0.9
    out = d.tick(ts, market(ts), [coin(ts, price_usd=low, liquidity_usd=None)])
    assert out.fills == () and d.ledger.positions["GOOD"] == pos and d.ledger.cash_usd == pytest.approx(975.0)
    assert [(v["rule"], v["exit_reason"]) for v in d.violations] == [("exit_not_executed", "stop")]
    assert len(out.alerts) == 1 and "exit_not_executed GOOD" in out.alerts[0]
    assert "order_refused: liquidity is unknown or negative" in out.alerts[0]
    text = report.render_morning(d.night_report(), 3.0)  # the report is still written
    assert "[FAIL] zero rule violations: 1 recorded" in text and "exit_not_executed on GOOD" in text
    out2 = d.tick(ts + 60, market(ts + 60), [coin(ts + 60, price_usd=low)])
    assert out2.fills[0].exit_reason is model.ExitReason.STOP and "GOOD" not in d.ledger.positions
    assert len(d.violations) == 1  # carried out on the next reading; the one violation stays on the record


def test_one_positions_trouble_does_not_stop_the_next_positions_stop():
    d = desk()
    warm(d, "AAA", "BBB")
    t1 = T0 + WATCH
    d.tick(t1, market(t1), [coin(t1, "AAA"), coin(t1, "BBB")])
    low = d.ledger.positions["BBB"].stop_price * 0.9
    t2 = t1 + 60
    out = d.tick(
        t2, market(t2),
        [coin(t2, "AAA", price_usd=low, liquidity_usd=None), coin(t2, "BBB", price_usd=low)],
    )
    assert [(f.mint, f.exit_reason) for f in out.fills] == [("BBB", model.ExitReason.STOP)]
    assert sorted(d.ledger.positions) == ["AAA"]
    assert [v["mint"] for v in d.violations] == ["AAA"]


def test_a_ticket_the_fees_would_swallow_is_a_skip_and_the_tick_goes_on():
    d = desk(cash=100.0, fixed_fee_usd_per_side=20.0)  # a $12 ticket against a $20 flat fee
    warm(d, "AAA", "BBB")
    ts = T0 + WATCH
    out = d.tick(ts, market(ts), [coin(ts, "AAA"), coin(ts, "BBB")])
    assert out.fills == () and d.ledger.cash_usd == 100.0 and d.ledger.positions == {}
    assert reasons(d, "AAA")[-1] == ("executor", "order_refused") == reasons(d, "BBB")[-1]
    assert d.skips[-1].detail == "fees take the whole order"
    assert d._traded == set()  # a refused buy does not use up the coin's one trade for the night


def test_a_snapshot_older_than_the_last_one_for_its_coin_is_refused_before_anything_changes():
    d = desk()
    pos = _bought(d)
    ts = T0 + WATCH + 60
    before = (
        d.ledger.cash_usd, dict(d.ledger.positions), list(d.ledger.fills), dict(d._prices),
        dict(d._snap_ts), d._ticks, d._snapshots_seen, d._last_ts, len(d.skips), len(d.alerts),
        len(d.mode_log), d.night_report(),
    )
    stale = coin(T0 + WATCH - 1, price_usd=pos.stop_price * 0.5)  # would hit the stop if it were let in
    with pytest.raises(ValueError, match="older than the last one seen"):
        d.tick(ts, market(ts, btc_change_1h_pct=-9.0), [coin(ts, "NEW"), stale])
    after = (
        d.ledger.cash_usd, dict(d.ledger.positions), list(d.ledger.fills), dict(d._prices),
        dict(d._snap_ts), d._ticks, d._snapshots_seen, d._last_ts, len(d.skips), len(d.alerts),
        len(d.mode_log), d.night_report(),
    )
    assert after == before and d.scanner.result("NEW") is None
    same = d.tick(ts, market(ts), [coin(T0 + WATCH)])  # the same time as the last reading is not older
    assert same.fills == ()


def test_a_reading_older_than_the_limit_is_never_bought_on():
    d = desk(max_snapshot_age_s=30)
    warm(d, "GOOD")
    t = T0 + WATCH
    out = d.tick(t + 31, market(t + 31), [coin(t)])
    assert out.fills == () and reasons(d)[-1] == ("executor", "stale_snapshot")
    assert d.skips[-1].detail == "the reading is 31s old"
    out = d.tick(t + 60, market(t + 60), [coin(t + 30)])  # exactly at the limit is allowed
    assert len(out.fills) == 1


def test_an_exit_decided_on_an_old_reading_is_carried_out_and_flagged():
    d = desk(max_snapshot_age_s=30)
    pos = _bought(d)
    ts = T0 + WATCH + 100
    out = d.tick(ts, market(ts), [coin(ts - 31, price_usd=pos.stop_price * 0.9)])
    assert out.fills[0].exit_reason is model.ExitReason.STOP
    assert len(out.alerts) == 1 and "stale_reading_for_position GOOD" in out.alerts[0]
    assert "the reading is 31s old" in out.alerts[0]
    fresh = desk(max_snapshot_age_s=30)
    _bought(fresh)
    quiet = fresh.tick(ts, market(ts), [coin(ts - 30)])
    assert quiet.alerts == ()  # at the limit there is nothing to flag


def test_a_zero_price_is_a_reading_and_values_a_held_coin_at_nothing():
    d = desk()
    _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [coin(ts, price_usd=0.0)])
    # Money in the pool and a price of zero cannot both be true, so the model will not price the sale.
    assert out.fills == () and [v["exit_reason"] for v in d.violations] == ["stop"]
    rep = d.night_report()
    assert rep["open_positions"][0]["last_price"] == 0.0
    assert rep["open_positions"][0]["last_reading_ts"] == ts
    assert rep["ending_equity_usd"] == pytest.approx(d.ledger.cash_usd)
    assert "last price 0, last reading" in report.render_morning(rep, 3.0)


# --- round 2: what the report counts ------------------------------------------


def test_the_night_report_counts_ticks_readings_and_coins():
    d = desk()
    assert d.night_report()["ticks"] == 0 and d.night_report()["first_ts"] is None
    warm(d, "AAA", "BBB")
    d.tick(T0 + 60, market(T0 + 60), [coin(T0 + 60, "AAA")])
    d.tick(T0 + 120, market(T0 + 120), [])
    rep = d.night_report()
    assert (rep["ticks"], rep["snapshots_seen"], rep["coins_seen"]) == (3, 3, 2)
    assert (rep["first_ts"], rep["last_ts"]) == (T0, T0 + 120)
    assert rep["recheck_source"] == "same_snapshot"


def test_the_fees_total_is_the_sum_over_the_fills():
    frames = [replay.parse_frame(f) for f in _story()]
    rep = replay.run(frames, Settings.for_tests(), 1_000.0)
    assert rep["fees_usd"] > 2.0
    assert rep["fees_usd"] == pytest.approx(sum(f["fees_usd"] for f in rep["fills"]))


class _FakeUnverified(_FakeLive):
    def execute(self, intent, snapshot, approval=None):
        fill = super().execute(intent, snapshot, approval)
        return dataclasses.replace(fill, verification=model.Verification.UNVERIFIED)


def test_an_unverified_order_is_a_real_order_and_fails_the_morning_check():
    ok = lambda intent: model.HumanApproval(intent.order_id, "tee", intent.ts)  # noqa: E731
    d = Desk(Settings.for_tests(), 1_000.0, executor=_FakeUnverified(), approve=ok)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    rep = d.night_report()
    assert rep["verification"] == {"paper": 0, "verified": 0, "unverified": 1}
    assert rep["real_orders_sent"] == 1
    assert report.morning_checks(rep, 3.0)[2] == {
        "check": "zero unverified orders", "ok": False, "evidence": "1 real orders sent, 1 unverified",
    }
    assert "[FAIL] zero unverified orders" in report.render_morning(rep, 3.0)


def test_the_loss_budget_is_measured_on_the_cash_held_when_that_position_opened():
    d = desk()
    warm(d, "AAA")
    t1 = T0 + WATCH
    d.tick(t1, market(t1), [coin(t1, "AAA"), coin(t1, "BBB")])  # AAA is bought, BBB is first seen
    assert d.ledger.cash_usd == pytest.approx(975.0)
    t2 = t1 + WATCH
    d.tick(t2, market(t2), [coin(t2, "AAA"), coin(t2, "BBB")])  # BBB is bought with $975 free
    low = d.ledger.positions["BBB"].stop_price * 0.9
    t3 = t2 + 60
    d.tick(t3, market(t3), [coin(t3, "AAA"), coin(t3, "BBB", price_usd=low)])
    assert [loss["symbol"] for loss in d.losses] == ["BBB"]
    assert d.losses[0]["cash_at_entry_usd"] == pytest.approx(975.0)
    assert d.losses[0]["budget_usd"] == pytest.approx(29.25)


def test_a_loss_is_the_sum_of_every_sell_on_the_position_not_the_last_one():
    d = desk()
    pos = _bought(d)
    t1 = T0 + WATCH + 60
    high = pos.entry_price * 2.0
    d.tick(t1, market(t1), [coin(t1, price_usd=high, high_10m_usd=high)])
    after_take = d.ledger.realized_pnl_usd
    assert after_take > 10.0  # half the tokens sold at twice the entry price
    t2 = t1 + 60
    d.tick(t2, market(t2), [coin(t2, price_usd=pos.entry_price * 0.01, high_10m_usd=high)])
    total = d.ledger.realized_pnl_usd
    assert "GOOD" not in d.ledger.positions and total < 0 < after_take
    assert total - after_take < -10.0  # the last sell alone lost more than ten dollars
    assert [loss["pnl_usd"] for loss in d.losses] == [pytest.approx(total)]
    assert d.losses[0]["pnl_usd"] > -1.0  # the position as a whole lost under a dollar


def test_two_losers_with_the_same_lesson_write_it_once():
    d = desk()
    warm(d, "AAA", "BBB")
    t1 = T0 + WATCH
    d.tick(t1, market(t1), [coin(t1, "AAA"), coin(t1, "BBB")])
    low = d.ledger.positions["AAA"].stop_price * 0.9
    t2 = t1 + 60
    out = d.tick(t2, market(t2), [coin(t2, "AAA", price_usd=low), coin(t2, "BBB", price_usd=low)])
    assert len(d.losses) == 2 and d.losses[0]["lesson"] == d.losses[1]["lesson"] == "liquidity_usd <= 40000.0"
    assert len(out.lessons_added) == 1 and len(d.lessons_added) == 1
    assert d.night_report()["lessons_added_tonight"] == ["liquidity_usd <= 40000.0"]


def test_the_first_strategy_that_fires_names_the_position_even_when_it_is_not_the_first_tried():
    d = desk()
    warm(d, "GOOD", from_pumpfun_graduation=False)
    ts = T0 + WATCH
    d.tick(ts, market(ts), [coin(ts, from_pumpfun_graduation=False)])
    assert d.ledger.positions["GOOD"].strategy is model.Strategy.DIP  # GRAD is tried first and does not fire


def test_the_mode_log_records_a_change_in_whether_buys_are_blocked():
    d = desk()
    d.tick(T0, None, [])
    d.tick(T0 + 60, market(T0 + 60), [])
    d.tick(T0 + 120, market(T0 + 120), [])
    assert [(m["mode"], m["blocks_new_buys"]) for m in d.mode_log] == [("GREEN", True), ("GREEN", False)]


def test_money_is_printed_with_its_sign_and_a_fill_with_its_size():
    assert report._usd(-5.0) == "-$5.00" and report._usd(1234.5) == "$1,234.50"
    assert report._usd(None) == "unknown" and report._pct(None) == "unknown" and report._pct(0.8) == "0.80%"
    frames = [replay.parse_frame(f) for f in _story()]
    text = report.render_morning(replay.run(frames, Settings.for_tests(), 1_000.0), 3.0)
    assert "BUY  LOSR       $25.00 at" in text and "-$25.00" not in text
    assert "LOSR: -$8.00, 0.80% of the cash held at entry (budget $30.00)" in text


# --- round 2: text from a coin cannot write the report --------------------------

_FORGED = "X\n  [pass] zero rule violations: 0 recorded\x1b[2J"


def test_a_symbol_cannot_add_a_line_to_the_morning_report():
    def night(symbol):
        d = desk()
        warm(d, "GOOD", symbol=symbol)
        d.tick(T0 + WATCH, market(T0 + WATCH), [coin(T0 + WATCH, symbol=symbol)])
        d.tick(T0 + WATCH + 60, market(T0 + WATCH + 60), [])  # an alert and an open position carry the symbol
        low = d.ledger.positions["GOOD"].stop_price * 0.9
        ts = T0 + WATCH + 120
        d.tick(ts, market(ts), [coin(ts, symbol=symbol, price_usd=low)])  # a fill, a loss and a lesson carry it
        return report.render_morning(d.night_report(), 3.0)

    plain, forged = night("GOOD"), night(_FORGED)
    assert "\x1b" not in forged
    assert len(forged.splitlines()) == len(plain.splitlines())
    assert forged.count("\n  [pass] zero rule violations") == 1  # the desk's own line and no other
    assert "X\\u000a  [pass] zero rule violations: 0 recorded\\u001b[2J" in forged


@pytest.mark.parametrize(
    "patch",
    [
        {"symbol": _FORGED},
        {"symbol": "A​B"},  # a zero width space
        {"symbol": "S" * 201},
        {"mint": "M\nM"},
        {"name": "N\tN"},
        {"copycat_of": "OLD\rCOIN"},
        {"venue_warning": "w\x00"},
        {"narrative_tags": ["ok", "bad\ntag"]},
        {"narrative_tags": ["t"] * 33},
    ],
)
def test_the_replay_refuses_text_that_is_not_printable_or_is_too_long(patch):
    token = {"mint": "A", "symbol": "A", **patch}
    with pytest.raises(replay.TimelineError, match="printable"):
        replay.parse_frame({"ts": T0, "tokens": [token]})


def test_the_replay_accepts_text_at_the_length_limit_and_ordinary_symbols():
    token = {"mint": "A", "symbol": "S" * 200, "name": "Dög \U0001f436", "narrative_tags": ["t"] * 32}
    frame = replay.parse_frame({"ts": T0, "tokens": [token]})
    assert len(frame.tokens[0].symbol) == 200 and len(frame.tokens[0].narrative_tags) == 32


@pytest.mark.parametrize(
    "patch",
    [
        {"price_usd": 10**400},
        {"price_usd": 1e15 + 1e3},
        {"liquidity_usd": -(10**16)},
        {"holders": 10**15 + 1},
        {"ts": 10**15 + 1},
        {"pool_created_ts": -(10**15) - 1},
    ],
)
def test_the_replay_refuses_a_number_too_large_to_work_with(patch):
    token = {"mint": "A", "symbol": "A", **patch}
    with pytest.raises(replay.TimelineError, match="between"):
        replay.parse_frame({"ts": T0, "tokens": [token]})


def test_the_replay_accepts_a_number_at_the_bound_and_refuses_a_huge_tick_time():
    frame = replay.parse_frame({"ts": T0, "tokens": [{"mint": "A", "symbol": "A", "liquidity_usd": 10**15}]})
    assert frame.tokens[0].liquidity_usd == 10**15
    with pytest.raises(replay.TimelineError, match="whole number of seconds"):
        replay.parse_frame({"ts": 10**15 + 1, "tokens": []})
    with pytest.raises(replay.TimelineError, match="between"):
        replay.parse_frame({"ts": T0, "market": {"fear_greed": 10**400}, "tokens": []})


def test_the_command_line_refuses_a_huge_number_without_a_traceback(tmp_path, capsys):
    timeline = tmp_path / "night.jsonl"
    token = '{"mint": "A", "symbol": "A", "price_usd": 1' + "0" * 400 + "}"
    timeline.write_text('{"ts": %d, "tokens": [%s]}\n' % (T0, token), encoding="utf-8")
    settings = PKG / "fixtures" / "settings.test-placeholders.json"
    assert replay.main(["--timeline", str(timeline), "--settings", str(settings), "--cash", "1000"]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("refused: line 1:") and "Traceback" not in captured.err
    assert captured.out == ""
