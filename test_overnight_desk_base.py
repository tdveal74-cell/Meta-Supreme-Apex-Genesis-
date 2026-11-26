"""The Overnight Desk paper engine's base: settings, data types, position math.

Offline. No network, no database, no clock. These pin the contract the other
desk modules are built on: every setting has a known origin and range, the
owner-only numbers have no default, nothing in the package imports outside the
standard library, and nothing in it can reach a trading venue.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "tools" / "overnight_desk"
# Appended, never inserted first, so no other top-level name is shadowed.
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from overnight_desk import model, positions  # noqa: E402
from overnight_desk.settings import (  # noqa: E402
    INVENTED_SETTINGS,
    OWNER_SETTINGS,
    SPECS,
    Settings,
    SettingsError,
)


def _snap(**kw) -> model.TokenSnapshot:
    base = dict(ts=1_000, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=0.001)
    base.update(kw)
    return model.TokenSnapshot(**base)


def _buy(qty=1_000.0, price=0.001, cost=1.05, ts=1_000) -> model.Fill:
    return model.Fill(
        order_id="o1", ts=ts, mint="MintA", symbol="AAA", side=model.Side.BUY, qty=qty,
        price=price, gross_usd=qty * price, fees_usd=cost - qty * price,
        cash_delta_usd=-cost, verification=model.Verification.PAPER,
    )


def _sell(qty, price, cash, ts=2_000) -> model.Fill:
    return model.Fill(
        order_id="o2", ts=ts, mint="MintA", symbol="AAA", side=model.Side.SELL, qty=qty,
        price=price, gross_usd=qty * price, fees_usd=qty * price - cash,
        cash_delta_usd=cash, verification=model.Verification.PAPER,
    )


# --- settings -------------------------------------------------------------


def test_every_setting_has_a_spec_and_every_spec_a_setting():
    names = {f.name for f in dataclasses.fields(Settings)}
    assert names == set(SPECS)


def test_origins_are_one_of_three_kinds():
    for name, spec in SPECS.items():
        assert spec.origin in ("invented", "owner") or spec.origin.startswith("doc:"), name
        if spec.origin.startswith("doc:"):
            line = int(spec.origin.split(":")[1])
            assert 1 <= line <= 96, name


def test_owner_settings_have_no_default_and_block_startup():
    assert set(OWNER_SETTINGS) == {
        "max_ticket_usd", "max_open_positions", "max_total_exposure_pct",
        "venue_fee_pct_per_side", "pool_fee_pct_per_side", "fixed_fee_usd_per_side",
    }
    bare = Settings()
    for name in OWNER_SETTINGS:
        assert getattr(bare, name) is None
    with pytest.raises(SettingsError) as err:
        Settings.from_dict({})
    for name in OWNER_SETTINGS:
        assert name in str(err.value)


def test_one_missing_owner_setting_is_enough_to_refuse():
    full = {
        "max_ticket_usd": 25.0, "max_open_positions": 3, "max_total_exposure_pct": 36.0,
        "venue_fee_pct_per_side": 0.5, "pool_fee_pct_per_side": 1.25, "fixed_fee_usd_per_side": 0.0,
    }
    assert Settings.from_dict(full).max_open_positions == 3
    for name in OWNER_SETTINGS:
        partial = {k: v for k, v in full.items() if k != name}
        with pytest.raises(SettingsError, match=name):
            Settings.from_dict(partial)


def test_documented_defaults_match_the_source_lines():
    s = Settings.for_tests()
    assert (s.liquidity_floor_usd, s.top10_max_pct, s.pump_1h_kill_pct, s.scanner_watch_s) == (20_000, 25, 200, 600)
    assert (s.dev_max_pct, s.lp_locked_min_pct, s.pool_age_min_s) == (5, 99, 600)
    assert (s.bundled_wallets_max, s.insiders_max_pct, s.score_pass, s.score_full) == (5, 15, 70, 80)
    assert (s.risk_per_trade_pct, s.stop_loss_pct, s.pool_liquidity_cap_pct) == (3, 25, 2)
    assert (s.dip_from_high_pct, s.take_multiple_green, s.take_multiple_red, s.take_fraction) == (15, 2.0, 1.5, 0.5)
    assert (s.trail_red_pct, s.red_time_stop_s, s.night_stop_pct) == (20, 5_400, 10)
    assert (s.dead_money_after_s, s.dead_money_min_gain_pct) == (10_800, 5)
    assert (s.dip_age_min_s, s.dip_age_max_s) == (600, 21_600)
    assert (s.red_btc_1h_pct, s.red_sol_1h_pct, s.red_fear_greed_max) == (-2.5, -4.0, 20)
    assert (s.paper_nights_required, s.live_first_nights, s.live_first_nights_ticket_cap_usd) == (3, 3, 25)


def test_the_sizing_rule_is_twelve_percent_of_free_cash():
    s = Settings.for_tests()
    assert s.risk_per_trade_pct / s.stop_loss_pct == pytest.approx(0.12)


@pytest.mark.parametrize("name", sorted(SPECS))
def test_each_setting_refuses_a_value_outside_its_range(name):
    spec = SPECS[name]
    for bad in (spec.lo - 1, spec.hi + 1):
        with pytest.raises(SettingsError, match=name):
            Settings.for_tests(**{name: bad})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "25", True, None, [1]])
def test_a_setting_refuses_a_value_that_is_not_a_finite_number(bad):
    with pytest.raises(SettingsError, match="top10_max_pct"):
        Settings.for_tests(top10_max_pct=bad)


def test_a_whole_number_setting_refuses_a_fraction():
    with pytest.raises(SettingsError, match="max_open_positions"):
        Settings.for_tests(max_open_positions=2.5)


def test_unknown_setting_names_are_refused():
    with pytest.raises(SettingsError, match="not_a_setting"):
        Settings.for_tests(not_a_setting=1)


def test_cross_field_rules():
    with pytest.raises(SettingsError, match="score_full"):
        Settings.for_tests(score_pass=90, score_full=80)
    with pytest.raises(SettingsError, match="dip_age_max_s"):
        Settings.for_tests(dip_age_min_s=600, dip_age_max_s=600)
    with pytest.raises(SettingsError, match="max_ticket_usd"):
        Settings.for_tests(max_ticket_usd=0.5, min_ticket_usd=1.0)


def test_from_file_reads_overrides_and_refuses_bad_files(tmp_path):
    good = tmp_path / "s.json"
    good.write_text(json.dumps({
        "max_ticket_usd": 10, "max_open_positions": 2, "max_total_exposure_pct": 20,
        "venue_fee_pct_per_side": 1, "pool_fee_pct_per_side": 1, "fixed_fee_usd_per_side": 0,
    }))
    assert Settings.from_file(good).max_ticket_usd == 10
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(SettingsError):
        Settings.from_file(bad)
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2]")
    with pytest.raises(SettingsError):
        Settings.from_file(arr)
    with pytest.raises(SettingsError):
        Settings.from_file(tmp_path / "missing.json")


def test_describe_names_every_setting_with_its_origin():
    rows = Settings.for_tests().describe()
    assert {r["name"] for r in rows} == set(SPECS)
    invented = {r["name"] for r in rows if r["origin"] == "invented"}
    assert invented == set(INVENTED_SETTINGS) and "trail_green_pct" in invented


def test_settings_are_frozen():
    s = Settings.for_tests()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.stop_loss_pct = 50  # type: ignore[misc]


# --- position math --------------------------------------------------------


def test_open_position_puts_the_stop_a_quarter_below_the_fill():
    s = Settings.for_tests()
    pos = positions.open_position(_buy(), _snap(), model.Strategy.DIP, s)
    assert pos.stop_price == pytest.approx(0.00075)
    assert pos.cost_usd == pytest.approx(1.05)
    assert pos.peak_price == 0.001 and pos.took_first_take is False
    assert pos.entry_liquidity_usd == 40_000.0


def test_open_position_refuses_a_sell_fill_and_a_zero_fill():
    s = Settings.for_tests()
    with pytest.raises(positions.PositionError):
        positions.open_position(_sell(10, 0.001, 0.01), _snap(), model.Strategy.DIP, s)
    with pytest.raises(positions.PositionError):
        positions.open_position(_buy(qty=0), _snap(), model.Strategy.DIP, s)


def test_a_half_sale_halves_cost_and_keeps_the_stop():
    s = Settings.for_tests()
    pos = positions.open_position(_buy(), _snap(), model.Strategy.DIP, s)
    fill = _sell(500.0, 0.002, 0.98)
    assert positions.realized_pnl(pos, fill) == pytest.approx(0.98 - 0.525)
    rest = positions.apply_exit_fill(pos, fill)
    assert rest is not None
    assert rest.qty == pytest.approx(500.0) and rest.cost_usd == pytest.approx(0.525)
    assert rest.stop_price == pos.stop_price and rest.peak_price == pos.peak_price
    assert pos.qty == 1_000.0  # the original is untouched


def test_a_full_sale_closes_the_position():
    s = Settings.for_tests()
    pos = positions.open_position(_buy(), _snap(), model.Strategy.DIP, s)
    fill = _sell(1_000.0, 0.00075, 0.74)
    assert positions.apply_exit_fill(pos, fill) is None
    assert positions.realized_pnl(pos, fill) == pytest.approx(0.74 - 1.05)


def test_a_sale_larger_than_the_position_or_for_another_coin_is_refused():
    s = Settings.for_tests()
    pos = positions.open_position(_buy(), _snap(), model.Strategy.DIP, s)
    with pytest.raises(positions.PositionError):
        positions.apply_exit_fill(pos, _sell(1_000.5, 0.001, 1.0))
    other = dataclasses.replace(_sell(10.0, 0.001, 0.01), mint="MintB")
    with pytest.raises(positions.PositionError):
        positions.realized_pnl(pos, other)
    with pytest.raises(positions.PositionError):
        positions.apply_exit_fill(pos, _buy())


# --- the model ------------------------------------------------------------


def test_red_is_a_mode_and_no_strategy():
    assert {m.value for m in model.Mode} == {"GREEN", "RED", "QUIET"}
    assert "RED" not in {s.value for s in model.Strategy}
    assert model.BUILT_STRATEGIES == {model.Strategy.DIP, model.Strategy.GRAD}


def test_a_paper_fill_is_never_counted_as_verified():
    assert model.Verification.PAPER is not model.Verification.VERIFIED
    assert {v.value for v in model.Verification} == {"paper", "verified", "unverified"}


def test_size_decision_skipped_follows_the_ticket():
    assert model.SizeDecision(0.0, "night_stop").skipped
    assert not model.SizeDecision(12.0).skipped


def test_snapshots_and_positions_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _snap().price_usd = 2.0  # type: ignore[misc]


# --- what the package may not do -------------------------------------------


def _py_files():
    return sorted(PKG.rglob("*.py"))


def test_the_package_imports_only_the_standard_library_and_itself():
    assert _py_files(), "the package has no python files"
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # a relative import stays inside the package
                    continue
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for root in roots:
                assert root in sys.stdlib_module_names, f"{path.name} imports {root}"


FORBIDDEN_IMPORTS = {
    "socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp", "websockets",
    "subprocess", "playwright", "selenium", "webbrowser", "ftplib", "smtplib", "asyncio",
}


def test_no_module_can_open_a_connection_or_start_a_process():
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [(node.module or "").split(".")[0]]
            hit = FORBIDDEN_IMPORTS.intersection(names)
            assert not hit, f"{path.name} imports {sorted(hit)}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "__import__"), f"{path.name} calls {node.func.id}"


def test_no_file_names_the_venue_or_carries_a_credential_word():
    banned = ("fomo.family", "prod-api", "session token", "bearer ", "private key", "seed phrase")
    for path in _py_files():
        text = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"{path.name} contains {word!r}"


def test_no_dashes_in_any_package_file_or_desk_test_file():
    for path in sorted(PKG.rglob("*")) + sorted(ROOT.glob("test_overnight_desk_*.py")):
        if path.is_file() and path.suffix in (".py", ".md", ".json", ".jsonl", ".txt"):
            text = path.read_text(encoding="utf-8")
            assert chr(0x2014) not in text and chr(0x2013) not in text, path.name


def test_no_module_shadows_a_standard_library_name():
    for path in _py_files():
        assert path.stem not in sys.stdlib_module_names, path.name
