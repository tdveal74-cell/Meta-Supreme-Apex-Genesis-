"""Offline tests for the Overnight Desk scanner and analyst modules."""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Appended, never inserted first, so no other top-level name is shadowed.
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from overnight_desk import analyst, model, scanner  # noqa: E402
from overnight_desk.model import LayerStatus, ScanState, TokenSnapshot  # noqa: E402
from overnight_desk.settings import Settings  # noqa: E402

S = Settings.for_tests()
T0 = 10_000


def _snap(**kw) -> TokenSnapshot:
    base = dict(ts=T0, mint="MintA", symbol="AAA")
    base.update(kw)
    return TokenSnapshot(**base)


def _clean(**kw) -> TokenSnapshot:
    """A snapshot that passes every scanner kill and all eight audit layers."""
    base = dict(
        ts=T0, mint="MintA", symbol="AAA", pool_created_ts=T0 - 1_000, liquidity_usd=40_000.0,
        price_usd=0.8, high_10m_usd=1.0, change_1h_pct=10.0, buys_5m=20, sells_5m=10,
        holders=100, holders_prev=100, top10_pct=10.0, dev_pct=1.0, dev_has_sold=False,
        mint_authority_revoked=True, freeze_authority_revoked=True, lp_locked_or_burned_pct=100.0,
        bundled_wallets=0, insiders_pct=0.0, dangerous_delegation=False, copycat_of=None,
        trading_disabled=False,
    )
    base.update(kw)
    return TokenSnapshot(**base)


# --- scanner ----------------------------------------------------------------


def _first_kill(**kw):
    sc = scanner.Scanner(S)
    return sc.observe(_snap(**kw))


def test_first_observation_sets_first_seen_and_watches():
    sc = scanner.Scanner(S)
    r = sc.observe(_clean())
    assert r.first_seen_ts == T0 and r.state is ScanState.WATCHING and r.reason_code == "watching"
    assert sc.result("MintA") == r
    assert sc.result("Nope") is None


def test_first_seen_stays_put_on_later_observations():
    sc = scanner.Scanner(S)
    sc.observe(_clean())
    r = sc.observe(_clean(ts=T0 + 100))
    assert r.first_seen_ts == T0


@pytest.mark.parametrize(
    "kw,code",
    [
        (dict(liquidity_usd=19_999.99), "liquidity_below_floor"),
        (dict(top10_pct=25.01), "top10_above_max"),
        (dict(change_1h_pct=200.0), "pumped_1h"),
        (dict(change_1h_pct=250.0), "pumped_1h"),
        (dict(copycat_of="Real"), "copycat_name"),
        (dict(trading_disabled=True), "trading_disabled"),
        (dict(holders=94, holders_prev=100), "holders_leaving"),
    ],
)
def test_each_kill_rule_fires(kw, code):
    r = _first_kill(**kw)
    assert r.state is ScanState.KILLED and r.reason_code == code


@pytest.mark.parametrize(
    "kw",
    [
        dict(liquidity_usd=20_000.0),
        dict(liquidity_usd=20_000.01),
        dict(liquidity_usd=None),
        dict(top10_pct=25.0),
        dict(top10_pct=24.99),
        dict(top10_pct=None),
        dict(change_1h_pct=199.99),
        dict(change_1h_pct=None),
        dict(copycat_of=None),
        dict(copycat_of=""),
        dict(trading_disabled=False),
        dict(trading_disabled=None),
        dict(holders=95, holders_prev=100),
        dict(holders=96, holders_prev=100),
        dict(holders=0, holders_prev=0),
        dict(holders=None, holders_prev=100),
        dict(holders=1, holders_prev=None),
    ],
)
def test_values_at_or_beside_a_threshold_do_not_kill(kw):
    r = _first_kill(**kw)
    assert r.state is not ScanState.KILLED


def test_pump_threshold_just_below_exactly_at_and_above():
    assert _first_kill(change_1h_pct=199.999).state is not ScanState.KILLED
    assert _first_kill(change_1h_pct=200.0).reason_code == "pumped_1h"
    assert _first_kill(change_1h_pct=200.001).reason_code == "pumped_1h"


def test_holders_leaving_threshold_uses_the_setting():
    s = Settings.for_tests(holders_drop_kill_pct=10.0)
    for holders, killed in ((89, True), (90, False), (91, False)):
        r = scanner.Scanner(s).observe(_snap(holders=holders, holders_prev=100))
        assert (r.state is ScanState.KILLED) == killed, holders


def test_all_none_snapshot_is_not_killed():
    r = scanner.Scanner(S).observe(_snap())
    assert r.state is ScanState.WATCHING


def test_kill_order_first_hit_wins():
    everything = dict(
        liquidity_usd=1.0, top10_pct=99.0, change_1h_pct=999.0, copycat_of="X",
        trading_disabled=True, holders=1, holders_prev=100,
    )
    order = [
        ("liquidity_below_floor", "liquidity_usd"),
        ("top10_above_max", "top10_pct"),
        ("pumped_1h", "change_1h_pct"),
        ("copycat_name", "copycat_of"),
        ("trading_disabled", "trading_disabled"),
        ("holders_leaving", "holders"),
    ]
    kw = dict(everything)
    for code, field in order:
        assert _first_kill(**kw).reason_code == code
        kw.pop(field)
        if field == "holders":
            kw.pop("holders_prev")
        # the removed field now reads as unknown, which never kills


def test_a_kill_is_permanent_and_keeps_its_first_reason():
    sc = scanner.Scanner(S)
    first = sc.observe(_clean(liquidity_usd=100.0))
    assert first.reason_code == "liquidity_below_floor"
    later = sc.observe(_clean(ts=T0 + 10_000, top10_pct=99.0))
    assert later.state is ScanState.KILLED and later.reason_code == "liquidity_below_floor"
    clean = sc.observe(_clean(ts=T0 + 20_000))
    assert clean == first
    assert sc.result("MintA") == first


def test_an_older_observation_raises_and_changes_nothing():
    sc = scanner.Scanner(S)
    sc.observe(_clean(ts=T0 + 50))
    before = sc.result("MintA")
    with pytest.raises(ValueError):
        sc.observe(_clean(ts=T0 + 49))
    assert sc.result("MintA") == before
    assert sc.observe(_clean(ts=T0 + 50)).first_seen_ts == T0 + 50  # equal time is allowed


def test_older_observation_raises_even_for_a_killed_coin():
    sc = scanner.Scanner(S)
    sc.observe(_clean(ts=T0 + 50, liquidity_usd=1.0))
    with pytest.raises(ValueError):
        sc.observe(_clean(ts=T0))


def test_staleness_is_tracked_per_mint():
    sc = scanner.Scanner(S)
    sc.observe(_clean(ts=T0 + 500))
    assert sc.observe(_clean(ts=T0, mint="MintB")).first_seen_ts == T0
    assert sc.result("MintA").first_seen_ts == T0 + 500


def test_pass_threshold_just_below_exactly_at_and_above_the_watch():
    sc = scanner.Scanner(S)
    sc.observe(_clean())
    below = sc.observe(_clean(ts=T0 + 599))
    assert below.state is ScanState.WATCHING and below.reason_code == "watching"
    at = sc.observe(_clean(ts=T0 + 600))
    assert at.state is ScanState.PASSED
    above = sc.observe(_clean(ts=T0 + 601))
    assert above.state is ScanState.PASSED


@pytest.mark.parametrize("field", ["liquidity_usd", "top10_pct", "change_1h_pct"])
def test_unknown_key_number_after_the_watch_waits_for_data(field):
    sc = scanner.Scanner(S)
    sc.observe(_clean())
    r = sc.observe(_clean(ts=T0 + 600, **{field: None}))
    assert r.state is ScanState.WATCHING and r.reason_code == "waiting_for_data"


def test_unknown_number_inside_the_watch_is_watching_not_waiting():
    sc = scanner.Scanner(S)
    sc.observe(_clean())
    r = sc.observe(_clean(ts=T0 + 10, top10_pct=None))
    assert r.reason_code == "watching"


def test_a_passed_coin_can_still_be_killed():
    sc = scanner.Scanner(S)
    sc.observe(_clean())
    assert sc.observe(_clean(ts=T0 + 700)).state is ScanState.PASSED
    r = sc.observe(_clean(ts=T0 + 800, trading_disabled=True))
    assert r.state is ScanState.KILLED and r.reason_code == "trading_disabled"
    assert sc.observe(_clean(ts=T0 + 900)).state is ScanState.KILLED


def test_the_watch_follows_the_setting():
    sc = scanner.Scanner(Settings.for_tests(scanner_watch_s=60))
    sc.observe(_clean())
    assert sc.observe(_clean(ts=T0 + 59)).state is ScanState.WATCHING
    assert sc.observe(_clean(ts=T0 + 60)).state is ScanState.PASSED


def test_the_scanner_does_not_mutate_its_input():
    snap = _clean()
    before = dataclasses.asdict(snap)
    scanner.Scanner(S).observe(snap)
    assert dataclasses.asdict(snap) == before


# --- audit ------------------------------------------------------------------

LAYER_NAMES = [
    "mint authority revoked",
    "freeze authority revoked",
    "dev holds under limit and has not sold",
    "top 10 under limit",
    "LP locked or burned",
    "pool age",
    "bundles and insiders",
    "no dangerous delegations",
]


def test_a_clean_coin_has_eight_greens():
    a = analyst.audit(_clean(), S)
    assert a.passed and a.first_failure is None
    assert [x.number for x in a.layers] == list(range(1, 9))
    assert [x.name for x in a.layers] == LAYER_NAMES
    assert all(x.status is LayerStatus.GREEN for x in a.layers)


def _stop(**kw):
    a = analyst.audit(_clean(**kw), S)
    assert not a.passed
    assert a.first_failure is a.layers[-1]
    return a


@pytest.mark.parametrize(
    "n,red,unknown",
    [
        (1, dict(mint_authority_revoked=False), dict(mint_authority_revoked=None)),
        (2, dict(freeze_authority_revoked=False), dict(freeze_authority_revoked=None)),
        (3, dict(dev_has_sold=True), dict(dev_has_sold=None)),
        (4, dict(top10_pct=30.0), dict(top10_pct=None)),
        (5, dict(lp_locked_or_burned_pct=50.0), dict(lp_locked_or_burned_pct=None)),
        (6, dict(pool_created_ts=T0 - 10), dict(pool_created_ts=None)),
        (7, dict(bundled_wallets=9), dict(bundled_wallets=None)),
        (8, dict(dangerous_delegation=True), dict(dangerous_delegation=None)),
    ],
)
def test_each_layer_red_and_unknown_stops_there(n, red, unknown):
    a = _stop(**red)
    assert a.first_failure.number == n and a.first_failure.status is LayerStatus.RED
    assert len(a.layers) == n
    b = _stop(**unknown)
    assert b.first_failure.number == n and b.first_failure.status is LayerStatus.UNKNOWN
    assert len(b.layers) == n


def test_layer_names_and_numbers_at_each_stop():
    for n, kw in enumerate(
        [dict(mint_authority_revoked=False), dict(freeze_authority_revoked=False), dict(dev_has_sold=True),
         dict(top10_pct=99.0), dict(lp_locked_or_burned_pct=0.0), dict(pool_created_ts=T0),
         dict(insiders_pct=99.0), dict(dangerous_delegation=True)],
        start=1,
    ):
        a = _stop(**kw)
        assert a.first_failure.name == LAYER_NAMES[n - 1]


def test_layer_3_dev_percent_threshold_and_halves():
    assert analyst.audit(_clean(dev_pct=4.99), S).passed
    for v in (5.0, 5.01):
        assert _stop(dev_pct=v).first_failure.status is LayerStatus.RED
    assert _stop(dev_pct=None).first_failure.status is LayerStatus.UNKNOWN
    # a red half is red even when the other half is unknown
    assert _stop(dev_pct=None, dev_has_sold=True).first_failure.status is LayerStatus.RED
    assert _stop(dev_pct=50.0, dev_has_sold=None).first_failure.status is LayerStatus.RED
    # green half with unknown other half is unknown
    assert _stop(dev_pct=1.0, dev_has_sold=None).first_failure.status is LayerStatus.UNKNOWN


def test_layer_4_top10_threshold():
    assert analyst.audit(_clean(top10_pct=24.99), S).passed
    assert _stop(top10_pct=25.0).first_failure.number == 4
    assert _stop(top10_pct=25.01).first_failure.number == 4


def test_layer_5_lp_threshold():
    assert _stop(lp_locked_or_burned_pct=98.99).first_failure.number == 5
    assert analyst.audit(_clean(lp_locked_or_burned_pct=99.0), S).passed
    assert analyst.audit(_clean(lp_locked_or_burned_pct=99.01), S).passed


def test_layer_6_pool_age_threshold():
    assert _stop(pool_created_ts=T0 - 599).first_failure.number == 6
    assert analyst.audit(_clean(pool_created_ts=T0 - 600), S).passed
    assert analyst.audit(_clean(pool_created_ts=T0 - 601), S).passed


def test_layer_7_each_half_and_thresholds():
    assert analyst.audit(_clean(bundled_wallets=4), S).passed
    assert _stop(bundled_wallets=5).first_failure.status is LayerStatus.RED
    assert _stop(bundled_wallets=6).first_failure.status is LayerStatus.RED
    assert analyst.audit(_clean(insiders_pct=14.99), S).passed
    assert _stop(insiders_pct=15.0).first_failure.status is LayerStatus.RED
    assert _stop(insiders_pct=15.01).first_failure.status is LayerStatus.RED
    assert _stop(bundled_wallets=None, insiders_pct=15.0).first_failure.status is LayerStatus.RED
    assert _stop(bundled_wallets=5, insiders_pct=None).first_failure.status is LayerStatus.RED
    assert _stop(bundled_wallets=0, insiders_pct=None).first_failure.status is LayerStatus.UNKNOWN
    assert _stop(bundled_wallets=None, insiders_pct=0.0).first_failure.status is LayerStatus.UNKNOWN


def test_audit_stops_at_the_first_failure_when_several_fail():
    a = analyst.audit(
        _clean(freeze_authority_revoked=False, top10_pct=99.0, dangerous_delegation=True), S
    )
    assert a.first_failure.number == 2 and len(a.layers) == 2


def test_an_all_none_snapshot_fails_at_layer_one_as_unknown():
    a = analyst.audit(_snap(), S)
    assert not a.passed and a.first_failure.number == 1
    assert a.first_failure.status is LayerStatus.UNKNOWN and len(a.layers) == 1


def test_audit_follows_the_settings():
    s = Settings.for_tests(dev_max_pct=10.0)
    assert analyst.audit(_clean(dev_pct=9.0), s).passed
    assert not analyst.audit(_clean(dev_pct=10.0), s).passed


# --- score ------------------------------------------------------------------


def test_score_parts_for_a_known_snapshot():
    # alive 30 trades -> 25; organic top10 10 -> 15; flush p=20 -> 25; chase 10 -> 25
    b = analyst.score(_clean(), S)
    assert (b.alive, b.organic, b.flush, b.anti_chase, b.social) == pytest.approx((25.0, 15.0, 25.0, 25.0, 0.0))
    assert b.total == pytest.approx(90.0) and b.passed and b.size_tier == "full"


@pytest.mark.parametrize(
    "trades,expected",
    [(0, 0.0), (14, 25 * 14 / 30), (29, 25 * 29 / 30), (30, 25.0), (31, 25.0), (3000, 25.0)],
)
def test_alive(trades, expected):
    b = analyst.score(_clean(buys_5m=trades, sells_5m=0), S)
    assert b.alive == pytest.approx(expected)


def test_alive_needs_both_counts():
    assert analyst.score(_clean(buys_5m=None), S).alive == 0.0
    assert analyst.score(_clean(sells_5m=None), S).alive == 0.0


@pytest.mark.parametrize(
    "top10,expected",
    [(0.0, 25.0), (12.5, 12.5), (24.99, 25 * (1 - 24.99 / 25)), (25.0, 0.0), (25.01, 0.0), (80.0, 0.0), (-5.0, 25.0)],
)
def test_organic_is_held_to_zero_to_twenty_five(top10, expected):
    assert analyst.score(_clean(top10_pct=top10), S).organic == pytest.approx(expected)


def test_organic_none_is_zero():
    assert analyst.score(_clean(top10_pct=None), S).organic == 0.0


@pytest.mark.parametrize(
    "price,expected",
    [
        (1.0, 0.0),          # p = 0
        (1.1, 0.0),          # p < 0
        (0.925, 12.5),       # p = 7.5, half way up the ramp
        (0.86, 25 * 14 / 15),  # just below lo (14)
        (0.85, 25.0),        # exactly lo (15)
        (0.84, 25.0),        # just above lo (16)
        (0.60, 25.0),        # exactly hi (40)
        (0.59, 25 * (1 - 1 / 25)),  # just above hi (41)
        (0.40, 25 * (1 - 20 / 25)),  # 60, three quarters down
        (0.20, 0.0),         # p = 80, far beyond hi + (hi - lo) = 65
        (0.35, 0.0),         # 65, exactly at the far end
        (0.36, 25 * (1 - 24 / 25)),  # 64, just inside the far end
        (0.0, 0.0),          # 100, far beyond
    ],
)
def test_flush_curve(price, expected):
    b = analyst.score(_clean(price_usd=price, high_10m_usd=1.0), S)
    assert b.flush == pytest.approx(expected, abs=1e-9)


def test_flush_inputs_none_or_bad_high_give_zero():
    assert analyst.score(_clean(price_usd=None), S).flush == 0.0
    assert analyst.score(_clean(high_10m_usd=None), S).flush == 0.0
    assert analyst.score(_clean(high_10m_usd=0.0), S).flush == 0.0
    assert analyst.score(_clean(high_10m_usd=-1.0), S).flush == 0.0


@pytest.mark.parametrize(
    "g,expected",
    [
        (-30.0, 25.0), (49.99, 25.0), (50.0, 25.0),
        (50.01, 25 * (200 - 50.01) / 150), (125.0, 12.5), (199.99, 25 * 0.01 / 150),
        (200.0, 0.0), (200.01, 0.0), (900.0, 0.0),
    ],
)
def test_anti_chase_curve(g, expected):
    assert analyst.score(_clean(change_1h_pct=g), S).anti_chase == pytest.approx(expected)


def test_anti_chase_none_is_zero():
    assert analyst.score(_clean(change_1h_pct=None), S).anti_chase == 0.0


@pytest.mark.parametrize("raw,expected", [(-5.0, 0.0), (0.0, 0.0), (9.99, 9.99), (10.0, 10.0), (10.01, 10.0), (500.0, 10.0)])
def test_social_is_capped_and_never_negative(raw, expected):
    assert analyst.score(_clean(social_score=raw), S).social == pytest.approx(expected)


def test_social_none_is_zero_and_can_only_raise_the_total():
    base = analyst.score(_clean(social_score=None), S)
    for raw in (-50.0, 0.0, 5.0, 50.0):
        assert analyst.score(_clean(social_score=raw), S).total >= base.total


def test_total_is_capped_at_one_hundred():
    s = Settings.for_tests(social_max_bonus=30.0, score_pass=70, score_full=80)
    b = analyst.score(_clean(top10_pct=0.0, social_score=30.0), s)
    assert b.alive + b.organic + b.flush + b.anti_chase + b.social > 100
    assert b.total == 100.0


def test_all_none_snapshot_scores_zero():
    b = analyst.score(_snap(), S)
    assert b.total == 0.0 and b.size_tier == "none" and b.passed is False


def test_tier_boundaries():
    # base without social: alive 25, organic 15, flush 25, chase 0 (g=200) = 65
    base = dict(change_1h_pct=200.0)
    cases = [
        (4.99, "none", False),   # 69.99
        (5.0, "half", True),     # 70 exactly
        (5.01, "half", True),
        (14.99, "half", True),   # 79.99
        (15.0, "full", True),    # 80 exactly
        (15.01, "full", True),
    ]
    s = Settings.for_tests(social_max_bonus=30.0)
    for raw, want_tier, want_pass in cases:
        b = analyst.score(_clean(social_score=raw, **base), s)
        assert b.total == pytest.approx(65.0 + raw)
        assert (b.size_tier, b.passed) == (want_tier, want_pass), raw


def test_tier_follows_the_settings():
    s = Settings.for_tests(score_pass=50, score_full=60)
    b = analyst.score(_clean(change_1h_pct=200.0), s)  # total 65
    assert b.size_tier == "full"
    s2 = Settings.for_tests(score_pass=65, score_full=66)
    assert analyst.score(_clean(change_1h_pct=200.0), s2).size_tier == "half"


def test_score_does_not_mutate_its_input():
    snap = _clean(social_score=3.0)
    before = dataclasses.asdict(snap)
    analyst.score(snap, S)
    analyst.audit(snap, S)
    assert dataclasses.asdict(snap) == before


# --- analyse ----------------------------------------------------------------


def test_analyse_scores_only_a_coin_with_eight_greens():
    a, b = analyst.analyse(_clean(), S)
    assert a.passed and isinstance(b, model.ScoreBreakdown)
    assert b == analyst.score(_clean(), S)


@pytest.mark.parametrize("kw", [dict(mint_authority_revoked=False), dict(dangerous_delegation=None), dict(top10_pct=50.0)])
def test_analyse_returns_no_score_when_the_audit_fails(kw):
    a, b = analyst.analyse(_clean(**kw), S)
    assert not a.passed and b is None
    assert a == analyst.audit(_clean(**kw), S)
