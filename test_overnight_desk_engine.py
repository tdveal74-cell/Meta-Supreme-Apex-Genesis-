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

from overnight_desk import lessons, model, paper, replay, report  # noqa: E402
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


def test_a_held_coin_with_no_price_raises_an_alert_and_is_kept():
    d = desk()
    _bought(d)
    ts = T0 + WATCH + 60
    out = d.tick(ts, market(ts), [])
    assert out.fills == () and "GOOD" in d.ledger.positions
    assert len(out.alerts) == 1 and "no_price_for_position GOOD" in out.alerts[0]
    out2 = d.tick(ts + 60, market(ts + 60), [coin(ts + 60, price_usd=None)])
    assert "no_price_for_position GOOD" in out2.alerts[0]


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
    with pytest.raises(paper.ApprovalRequired):
        d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    assert fake.seen == [] and d.ledger.fills == [] and d.ledger.cash_usd == 1_000.0


def test_an_approval_for_another_order_is_refused():
    fake = _FakeLive()
    wrong = lambda intent: model.HumanApproval("some-other-order", "tee", intent.ts)  # noqa: E731
    d = Desk(Settings.for_tests(), 1_000.0, executor=fake, approve=wrong)
    d.tick(T0, market(T0), [_live_snapshot(T0)])
    with pytest.raises(paper.ApprovalRequired):
        d.tick(T0 + WATCH, market(T0 + WATCH), [_live_snapshot(T0 + WATCH)])
    assert fake.seen == []


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
    for name in ("a reason for every skip", "every loss within 3% of cash", "zero unverified orders",
                 "zero rule violations"):
        assert f"[pass] {name}" in text
    assert "closed: " in text and "no_live_executor" in text
    assert chr(0x2014) not in text and chr(0x2013) not in text
    checks = report.morning_checks(out, 3.0)
    assert [c["ok"] for c in checks] == [True, True, True, True]


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
        with pytest.raises(paper.ApprovalRequired):
            d.tick(ts, market(ts), [dataclasses.replace(_live_snapshot(ts), price_usd=price)])
        assert d.ledger.positions["GOOD"] == pos  # same quantity, same stop, first take not marked
        assert d.ledger.cash_usd == cash and len(d.ledger.fills) == 1 and len(fake.seen) == 1


def _clean_report():
    return replay.run([], Settings.for_tests(), 500.0)


def _loss(**kw):
    base = dict(ts=1, mint="M", symbol="S", strategy="DIP", exit_reason="stop", entry_ts=0, entry_price=1.0,
                exit_price=0.7, pnl_usd=-3.0, cash_at_entry_usd=500.0, loss_pct_of_cash=0.6,
                budget_usd=15.0, lesson="top10_pct >= 20.0")
    base.update(kw)
    return base


def _fill(**kw):
    base = dict(order_id="1-0001", ts=1, mint="M", symbol="S", side="BUY", qty=1.0, price=1.0, gross_usd=1.0,
                fees_usd=0.0, cash_delta_usd=-1.0, verification="paper", exit_reason=None)
    base.update(kw)
    return base


def _checks(rep):
    return [c["ok"] for c in report.morning_checks(rep, 3.0)]


def test_each_morning_check_fails_alone_on_the_data_that_should_fail_it():
    assert _checks(_clean_report()) == [True, True, True, True]

    no_reason = _clean_report()
    no_reason["skips"] = [dict(ts=1, mint="M", symbol="S", stage="brain", reason_code="", detail="")]
    assert _checks(no_reason) == [False, True, True, True]

    for bad_loss in (_loss(loss_pct_of_cash=3.01), _loss(loss_pct_of_cash=None), _loss(exit_reason=""),
                     _loss(exit_reason=None)):
        rep = _clean_report()
        rep["losses"] = [_loss(), bad_loss]
        assert _checks(rep) == [True, False, True, True], bad_loss

    at_limit = _clean_report()
    at_limit["losses"] = [_loss(loss_pct_of_cash=3.0), _loss(lesson=None)]
    assert _checks(at_limit) == [True, True, True, True]  # at the limit passes; a missing lesson is counted, not failed
    assert "1 with no lesson written" in report.morning_checks(at_limit, 3.0)[1]["evidence"]

    unverified = _clean_report()
    unverified["fills"] = [_fill(verification="unverified")]
    unverified["verification"] = {"paper": 0, "verified": 0, "unverified": 1}
    unverified["real_orders_sent"] = 1
    assert _checks(unverified) == [True, True, False, True]
    assert "was exercised" in report.morning_checks(unverified, 3.0)[2]["evidence"]

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
