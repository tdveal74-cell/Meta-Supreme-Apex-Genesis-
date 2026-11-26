"""Offline tests for the Overnight Desk market mode and lessons modules.

No network, no clock, no files outside tmp_path.
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

from overnight_desk import lessons, market_mode, model  # noqa: E402
from overnight_desk.lessons import Check, LessonBook, LessonError  # noqa: E402
from overnight_desk.model import Mode  # noqa: E402
from overnight_desk.settings import Settings, SettingsError  # noqa: E402

S = Settings.for_tests()


def _market(btc=0.0, sol=0.0, fg=50, grads=50, ts=1_000) -> model.MarketSnapshot:
    return model.MarketSnapshot(
        ts=ts, btc_change_1h_pct=btc, sol_change_1h_pct=sol, fear_greed=fg, graduations_last_hour=grads
    )


def _snap(**kw) -> model.TokenSnapshot:
    base = dict(ts=10_000, mint="MintA", symbol="AAA", liquidity_usd=40_000.0, price_usd=0.001)
    base.update(kw)
    return model.TokenSnapshot(**base)


# --- market_mode ----------------------------------------------------------


def test_a_calm_market_is_green_and_allows_buys():
    st = market_mode.assess(_market(), S)
    assert st.mode is Mode.GREEN and st.data_ok and not st.blocks_new_buys and st.reasons == ()


@pytest.mark.parametrize(
    "field,limit",
    [("btc", S.red_btc_1h_pct), ("sol", S.red_sol_1h_pct)],
)
def test_the_two_one_hour_changes_trip_red_at_and_below_the_limit(field, limit):
    just_below = market_mode.assess(_market(**{field: limit - 0.01}), S)
    at = market_mode.assess(_market(**{field: limit}), S)
    just_above = market_mode.assess(_market(**{field: limit + 0.01}), S)
    assert just_below.mode is Mode.RED and just_below.blocks_new_buys
    assert at.mode is Mode.RED and at.blocks_new_buys
    assert just_above.mode is Mode.GREEN and not just_above.blocks_new_buys


def test_fear_greed_trips_red_at_and_below_the_limit():
    lim = S.red_fear_greed_max
    assert market_mode.assess(_market(fg=lim - 1), S).mode is Mode.RED
    assert market_mode.assess(_market(fg=lim), S).mode is Mode.RED
    assert market_mode.assess(_market(fg=lim + 1), S).mode is Mode.GREEN


def test_quiet_at_and_below_the_graduation_limit_and_green_above():
    lim = S.quiet_max_graduations_per_hour
    below = market_mode.assess(_market(grads=lim - 1), S)
    at = market_mode.assess(_market(grads=lim), S)
    above = market_mode.assess(_market(grads=lim + 1), S)
    assert below.mode is Mode.QUIET and below.blocks_new_buys
    assert at.mode is Mode.QUIET and at.blocks_new_buys
    assert above.mode is Mode.GREEN and not above.blocks_new_buys


def test_red_beats_quiet_when_both_would_fire():
    st = market_mode.assess(_market(btc=-9.0, grads=0), S)
    assert st.mode is Mode.RED
    assert not any(r.startswith("graduations") for r in st.reasons)


def test_each_red_trip_is_named_in_plain_words():
    st = market_mode.assess(_market(btc=-3.1, sol=-5.0, fg=10), S)
    assert st.reasons == ("btc_1h -3.10 <= -2.50", "sol_1h -5.00 <= -4.00", "fear_greed 10 <= 20")


def test_quiet_reason_is_named():
    st = market_mode.assess(_market(grads=2), S)
    assert st.reasons == ("graduations 2 <= 5",)


@pytest.mark.parametrize(
    "field,word",
    [
        ("btc_change_1h_pct", "btc_1h missing"),
        ("sol_change_1h_pct", "sol_1h missing"),
        ("fear_greed", "fear_greed missing"),
        ("graduations_last_hour", "graduations missing"),
    ],
)
def test_one_missing_input_blocks_buys_and_is_named(field, word):
    st = market_mode.assess(dataclasses.replace(_market(), **{field: None}), S)
    assert not st.data_ok and st.blocks_new_buys
    assert word in st.reasons
    assert st.mode is Mode.GREEN


def test_a_known_red_trip_still_reads_red_when_another_input_is_missing():
    st = market_mode.assess(dataclasses.replace(_market(btc=-3.0), fear_greed=None), S)
    assert st.mode is Mode.RED and not st.data_ok and st.blocks_new_buys


def test_every_input_none_and_no_market_at_all():
    empty = market_mode.assess(model.MarketSnapshot(ts=1), S)
    assert not empty.data_ok and empty.blocks_new_buys and empty.mode is Mode.GREEN
    assert len(empty.reasons) == 4 and all(r.endswith("missing") for r in empty.reasons)
    gone = market_mode.assess(None, S)
    assert not gone.data_ok and gone.blocks_new_buys and gone.reasons


def test_assess_does_not_touch_its_arguments():
    mk = _market(btc=-5.0)
    settings = Settings.for_tests()
    mk_before, settings_before = copy.deepcopy(mk), copy.deepcopy(settings)
    market_mode.assess(mk, settings)
    assert mk == mk_before and settings == settings_before


def test_thresholds_follow_the_settings():
    tight = Settings.for_tests(red_btc_1h_pct=-1.0)
    assert market_mode.assess(_market(btc=-1.0), tight).mode is Mode.RED
    assert market_mode.assess(_market(btc=-1.0), S).mode is Mode.GREEN


# --- parse_check ----------------------------------------------------------


@pytest.mark.parametrize("field", lessons.CHECK_FIELDS)
@pytest.mark.parametrize("op", [">", ">=", "<", "<="])
def test_parse_check_accepts_every_field_and_operator(field, op):
    assert lessons.parse_check(f"{field} {op} 12.5") == Check(field, op, 12.5)


def test_parse_check_reads_negative_and_exponent_numbers():
    assert lessons.parse_check("change_1h_pct <= -30").value == -30.0
    assert lessons.parse_check("liquidity_usd <= 1e4").value == 10_000.0


@pytest.mark.parametrize(
    "text",
    [
        "",
        "liquidity_usd",
        "liquidity_usd >=",
        "liquidity_usd >= 1 2",
        "price_usd >= 1",
        "liquidity_usd == 1",
        "liquidity_usd != 1",
        "liquidity_usd >= abc",
        "liquidity_usd >= nan",
        "liquidity_usd >= inf",
        "liquidity_usd >= 1_000",
        "liquidity_usd >= 1e999",
        "__import__('os') >= 1",
        "liquidity_usd >= 1; import os",
        "liquidity_usd >=1",
    ],
)
def test_parse_check_refuses_anything_else(text):
    with pytest.raises(LessonError):
        lessons.parse_check(text)


def test_parse_check_refuses_a_non_string():
    with pytest.raises(LessonError):
        lessons.parse_check(None)  # type: ignore[arg-type]


def test_lesson_error_is_a_value_error():
    assert issubclass(LessonError, ValueError)


# --- check_hits -----------------------------------------------------------


@pytest.mark.parametrize(
    "op,limit,expected",
    [
        (">", 9.0, True), (">", 10.0, False), (">", 11.0, False),
        (">=", 9.0, True), (">=", 10.0, True), (">=", 11.0, False),
        ("<", 9.0, False), ("<", 10.0, False), ("<", 11.0, True),
        ("<=", 9.0, False), ("<=", 10.0, True), ("<=", 11.0, True),
    ],
)
def test_check_hits_with_the_limit_just_below_at_and_above_the_value(op, limit, expected):
    snap = _snap(top10_pct=10.0)
    assert lessons.check_hits(Check("top10_pct", op, limit), snap) is expected


@pytest.mark.parametrize(
    "field,kw",
    [
        ("liquidity_usd", dict(liquidity_usd=50.0)),
        ("change_1h_pct", dict(change_1h_pct=50.0)),
        ("top10_pct", dict(top10_pct=50.0)),
        ("dev_pct", dict(dev_pct=50.0)),
        ("lp_locked_or_burned_pct", dict(lp_locked_or_burned_pct=50.0)),
        ("bundled_wallets", dict(bundled_wallets=50)),
        ("insiders_pct", dict(insiders_pct=50.0)),
        ("holders", dict(holders=50)),
        ("buys_5m", dict(buys_5m=50)),
        ("sells_5m", dict(sells_5m=50)),
        ("pool_age_s", dict(pool_created_ts=9_950)),
    ],
)
def test_each_field_reads_its_own_value_at_the_edge(field, kw):
    snap = _snap(**kw)
    assert lessons.check_hits(Check(field, ">", 49.0), snap)
    assert not lessons.check_hits(Check(field, ">", 50.0), snap)
    assert lessons.check_hits(Check(field, ">=", 50.0), snap)
    assert not lessons.check_hits(Check(field, ">=", 51.0), snap)
    assert lessons.check_hits(Check(field, "<", 51.0), snap)
    assert not lessons.check_hits(Check(field, "<", 50.0), snap)
    assert lessons.check_hits(Check(field, "<=", 50.0), snap)
    assert not lessons.check_hits(Check(field, "<=", 49.0), snap)


def test_pool_age_is_the_snapshot_time_less_the_pool_creation_time():
    snap = _snap(ts=10_000, pool_created_ts=9_400)
    assert lessons.check_hits(Check("pool_age_s", ">=", 600.0), snap)
    assert not lessons.check_hits(Check("pool_age_s", ">=", 601.0), snap)


@pytest.mark.parametrize("field", lessons.CHECK_FIELDS)
@pytest.mark.parametrize("op", [">", ">=", "<", "<="])
def test_an_unknown_value_always_hits(field, op):
    blank = model.TokenSnapshot(ts=1, mint="M", symbol="M")
    assert lessons.check_hits(Check(field, op, 5.0), blank) is True


# --- LessonBook -----------------------------------------------------------


def _lesson(check="top10_pct >= 20.0", lid="L1", mint="MintA") -> model.Lesson:
    return model.Lesson(lesson_id=lid, created_ts=5, source_mint=mint, check=check, why="w")


def test_add_validates_the_check():
    book = LessonBook()
    with pytest.raises(LessonError):
        book.add(_lesson(check="price_usd >= 1"))
    assert book.to_json() == []


def test_add_returns_the_existing_lesson_for_the_same_check_text():
    book = LessonBook()
    first = book.add(_lesson(lid="L1"))
    again = book.add(_lesson(lid="L2"))
    assert again is first
    assert [r["lesson_id"] for r in book.to_json()] == ["L1"]


def test_blocking_returns_the_first_added_lesson_that_hits():
    book = LessonBook()
    book.add(_lesson("top10_pct >= 20.0", "L1"))
    book.add(_lesson("dev_pct >= 3.0", "L2"))
    both = _snap(top10_pct=30.0, dev_pct=4.0)
    only_second = _snap(top10_pct=10.0, dev_pct=4.0)
    neither = _snap(top10_pct=10.0, dev_pct=1.0)
    assert book.blocking(both).lesson_id == "L1"
    assert book.blocking(only_second).lesson_id == "L2"
    assert book.blocking(neither) is None


def test_blocking_edges_follow_the_check():
    book = LessonBook()
    book.add(_lesson("top10_pct >= 20.0"))
    assert book.blocking(_snap(top10_pct=20.0)) is not None
    assert book.blocking(_snap(top10_pct=20.01)) is not None
    assert book.blocking(_snap(top10_pct=19.99)) is None


def test_an_unknown_field_value_is_blocked_by_a_lesson():
    book = LessonBook()
    book.add(_lesson("top10_pct >= 20.0"))
    assert book.blocking(_snap(top10_pct=None)) is not None


def test_an_empty_book_blocks_nothing():
    assert LessonBook().blocking(_snap()) is None


def test_the_book_has_no_way_to_remove_or_weaken_a_lesson():
    public = {n for n in dir(LessonBook) if not n.startswith("_")}
    assert public == {"add", "blocking", "to_json", "from_json"}


def test_a_lesson_cannot_pass_a_coin_only_block_it():
    # Whatever is added, the set of coins that get through can only shrink.
    book = LessonBook()
    coins = [_snap(top10_pct=v) for v in (5.0, 15.0, 25.0)]
    passed_before = [c for c in coins if book.blocking(c) is None]
    book.add(_lesson("top10_pct >= 20.0"))
    passed_after = [c for c in coins if book.blocking(c) is None]
    assert set(map(id, passed_after)) <= set(map(id, passed_before))
    assert len(passed_after) < len(passed_before)


def test_json_round_trip_keeps_order_and_content():
    book = LessonBook()
    book.add(_lesson("top10_pct >= 20.0", "L1"))
    book.add(_lesson("liquidity_usd <= 25000.0", "L2"))
    rows = book.to_json()
    again = LessonBook.from_json(rows)
    assert again.to_json() == rows
    assert rows[0] == {
        "lesson_id": "L1", "created_ts": 5, "source_mint": "MintA", "check": "top10_pct >= 20.0", "why": "w"
    }


def test_to_json_returns_copies():
    book = LessonBook()
    book.add(_lesson())
    rows = book.to_json()
    rows[0]["check"] = "top10_pct >= 99.0"
    rows.clear()
    assert book.to_json()[0]["check"] == "top10_pct >= 20.0"


def test_from_json_refuses_bad_rows():
    good = _lesson()
    row = dataclasses.asdict(good)
    with pytest.raises(LessonError):
        LessonBook.from_json([{**row, "extra": 1}])
    with pytest.raises(LessonError):
        LessonBook.from_json([{k: v for k, v in row.items() if k != "check"}])
    with pytest.raises(LessonError):
        LessonBook.from_json([{**row, "check": "price_usd >= 1"}])
    with pytest.raises(LessonError):
        LessonBook.from_json(["not a row"])  # type: ignore[list-item]


def test_from_json_does_not_touch_its_rows():
    rows = [dataclasses.asdict(_lesson())]
    before = copy.deepcopy(rows)
    LessonBook.from_json(rows)
    assert rows == before


def test_from_json_collapses_duplicate_checks():
    rows = [dataclasses.asdict(_lesson(lid="L1")), dataclasses.asdict(_lesson(lid="L2"))]
    assert len(LessonBook.from_json(rows).to_json()) == 1


# --- derive_lesson --------------------------------------------------------


def _position(**snap_kw) -> model.Position:
    snap = _snap(**snap_kw)
    return model.Position(
        mint="MintA", symbol="AAA", strategy=model.Strategy.DIP, entry_ts=9_000, entry_price=0.001,
        qty=1_000.0, cost_usd=1.0, stop_price=0.00075, peak_price=0.001, took_first_take=False,
        entry_liquidity_usd=snap.liquidity_usd or 0.0, entry_snapshot=snap,
    )


def _sell_fill(cash, qty=1_000.0, ts=9_500) -> model.Fill:
    return model.Fill(
        order_id="o2", ts=ts, mint="MintA", symbol="AAA", side=model.Side.SELL, qty=qty, price=0.0007,
        gross_usd=cash, fees_usd=0.0, cash_delta_usd=cash, verification=model.Verification.PAPER,
    )


LOSS = _sell_fill(0.7)


def test_the_closest_field_wins_for_a_higher_is_worse_field():
    pos = _position(top10_pct=20.0, dev_pct=4.5, insiders_pct=1.0, bundled_wallets=1, liquidity_usd=1e9)
    # ratios: top10 20/25 = 0.8, dev 4.5/5 = 0.9, insiders 1/15, bundled 1/5
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None
    assert lesson.check == "dev_pct >= 4.5"
    assert lesson.lesson_id == "L-MintA-9500" and lesson.created_ts == 9_500
    assert lesson.source_mint == "MintA"
    assert lessons.parse_check(lesson.check) == Check("dev_pct", ">=", 4.5)


def test_liquidity_uses_limit_over_value_and_a_lower_or_equal_check():
    pos = _position(top10_pct=1.0, liquidity_usd=21_000.0)  # 20000/21000 = 0.952 beats 1/25
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None and lesson.check == "liquidity_usd <= 21000.0"


def test_a_tie_goes_to_the_field_listed_first():
    # top10 12.5/25 = 0.5 and dev 2.5/5 = 0.5 tie; top10 is listed first.
    pos = _position(top10_pct=12.5, dev_pct=2.5, liquidity_usd=1e9)
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None and lesson.check.startswith("top10_pct >= ")


def test_bundled_wallets_check_reads_back_through_parse_check():
    pos = _position(bundled_wallets=4, liquidity_usd=1e9)
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None
    assert lessons.parse_check(lesson.check) == Check("bundled_wallets", ">=", 4.0)


def test_unknown_and_non_positive_fields_are_left_out():
    pos = _position(top10_pct=0.0, dev_pct=None, insiders_pct=-1.0, bundled_wallets=0, liquidity_usd=0.0)
    assert lessons.derive_lesson(pos, LOSS, S) is None
    only_dev = _position(top10_pct=0.0, dev_pct=0.5, liquidity_usd=None)
    assert lessons.derive_lesson(only_dev, LOSS, S).check == "dev_pct >= 0.5"


def test_a_non_positive_limit_leaves_the_field_out():
    s = Settings.for_tests(dev_max_pct=0)
    pos = _position(dev_pct=3.0, top10_pct=None, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, s) is None


def test_no_qualifying_field_returns_none():
    blank = _position(liquidity_usd=None)
    assert lessons.derive_lesson(blank, LOSS, S) is None


def test_a_position_that_did_not_lose_leaves_no_lesson():
    pos = _position(top10_pct=24.0)
    assert lessons.derive_lesson(pos, _sell_fill(1.0), S) is None  # breakeven
    assert lessons.derive_lesson(pos, _sell_fill(2.0), S) is None  # gain
    assert lessons.derive_lesson(pos, _sell_fill(0.99), S) is not None  # a small loss


def test_derive_lesson_does_not_touch_its_arguments():
    pos = _position(top10_pct=24.0)
    fill = _sell_fill(0.5)
    before = (copy.deepcopy(pos), copy.deepcopy(fill), copy.deepcopy(S))
    lessons.derive_lesson(pos, fill, S)
    assert (pos, fill, S) == before


# --- apply_review ---------------------------------------------------------


APPROVAL = model.HumanApproval(order_id="review", approved_by="owner", approved_ts=1)


def test_a_review_without_approval_is_refused():
    with pytest.raises(LessonError):
        lessons.apply_review(S, {"stop_loss_pct": 20.0}, None)


def test_a_review_may_change_three_settings_and_not_four():
    three = {"stop_loss_pct": 20.0, "top10_max_pct": 20.0, "dev_max_pct": 4.0}
    out = lessons.apply_review(S, three, APPROVAL)
    assert (out.stop_loss_pct, out.top10_max_pct, out.dev_max_pct) == (20.0, 20.0, 4.0)
    four = {**three, "insiders_max_pct": 10.0}
    with pytest.raises(LessonError):
        lessons.apply_review(S, four, APPROVAL)


def test_the_four_change_refusal_comes_with_a_valid_approval():
    four = {"stop_loss_pct": 20.0, "top10_max_pct": 20.0, "dev_max_pct": 4.0, "insiders_max_pct": 10.0}
    with pytest.raises(LessonError, match="at most 3"):
        lessons.apply_review(S, four, APPROVAL)


def test_a_review_keeps_every_other_setting():
    out = lessons.apply_review(S, {"stop_loss_pct": 20.0}, APPROVAL)
    assert dataclasses.replace(out, stop_loss_pct=S.stop_loss_pct) == S
    assert out.max_ticket_usd == S.max_ticket_usd


def test_an_empty_review_returns_equal_settings():
    assert lessons.apply_review(S, {}, APPROVAL) == S


def test_a_review_runs_the_range_checks():
    with pytest.raises(SettingsError, match="stop_loss_pct"):
        lessons.apply_review(S, {"stop_loss_pct": 95.0}, APPROVAL)
    with pytest.raises(SettingsError, match="not_a_setting"):
        lessons.apply_review(S, {"not_a_setting": 1}, APPROVAL)
    with pytest.raises(SettingsError, match="score_full"):
        lessons.apply_review(S, {"score_pass": 90.0}, APPROVAL)


def test_a_review_does_not_touch_its_arguments():
    changes = {"stop_loss_pct": 20.0}
    settings = Settings.for_tests()
    before = (copy.deepcopy(changes), copy.deepcopy(settings))
    out = lessons.apply_review(settings, changes, APPROVAL)
    assert (changes, settings) == before
    assert out is not settings


# --- the modules' own source ----------------------------------------------


@pytest.mark.parametrize("name", ["market_mode.py", "lessons.py"])
def test_module_docstring_and_no_dash_characters(name):
    text = (ROOT / "tools" / "overnight_desk" / name).read_text(encoding="utf-8")
    assert text.lstrip().startswith('"""')
    assert "source line" in text.lower()
    assert chr(0x2014) not in text and chr(0x2013) not in text


def test_lessons_module_marks_its_invented_parts():
    text = (ROOT / "tools" / "overnight_desk" / "lessons.py").read_text(encoding="utf-8")
    assert "INVENTED" in text.split('"""')[1]
    assert "INVENTED" in (ROOT / "tools" / "overnight_desk" / "market_mode.py").read_text(encoding="utf-8").split('"""')[1]


# --- round 1: gaps found by mutation ---------------------------------------


def test_no_market_snapshot_is_green_but_blocks_buys_and_says_why():
    st = market_mode.assess(None, S)
    assert st.mode is Mode.GREEN
    assert st.data_ok is False
    assert st.blocks_new_buys is True
    assert st.reasons == ("market snapshot missing",)


def test_all_four_missing_input_reasons_are_exact_and_in_order():
    st = market_mode.assess(model.MarketSnapshot(ts=1), S)
    assert st.reasons == ("btc_1h missing", "sol_1h missing", "fear_greed missing", "graduations missing")


def test_a_quiet_result_carries_the_graduation_reason_and_red_does_not():
    quiet = market_mode.assess(_market(grads=3), S)
    assert quiet.mode is Mode.QUIET and quiet.reasons == ("graduations 3 <= 5",)
    red = market_mode.assess(_market(btc=-9.0, grads=3), S)
    assert red.mode is Mode.RED
    assert red.reasons == ("btc_1h -9.00 <= -2.50",)


def test_pool_age_checks_parse_and_evaluate():
    assert "pool_age_s" in lessons.CHECK_FIELDS
    assert lessons.parse_check("pool_age_s >= 600") == Check("pool_age_s", ">=", 600.0)
    snap = _snap(ts=10_000, pool_created_ts=9_000)
    assert lessons.check_hits(lessons.parse_check("pool_age_s >= 1000"), snap)
    assert not lessons.check_hits(lessons.parse_check("pool_age_s >= 1001"), snap)


@pytest.mark.parametrize(
    "number",
    [
        "١٢",  # Arabic-Indic digits
        "１２",  # fullwidth digits
        "1٢",
        "nan", "NaN", "inf", "-inf", "+inf", "Infinity",
        "1e999", "-1e999", "+1e999",
        "1_000", "1e1_0",
    ],
)
def test_parse_check_refuses_non_ascii_non_finite_and_underscore_numbers(number):
    with pytest.raises(LessonError):
        lessons.parse_check(f"liquidity_usd >= {number}")


def test_parse_check_refuses_overflow_of_either_sign():
    for text in ("change_1h_pct <= -1e999", "change_1h_pct >= -1e999", "change_1h_pct >= 1e999"):
        with pytest.raises(LessonError, match="finite"):
            lessons.parse_check(text)


def test_a_nan_field_value_is_unknown_and_hits_like_none():
    nan = float("nan")
    for op in (">", ">=", "<", "<="):
        assert lessons.check_hits(Check("top10_pct", op, 5.0), _snap(top10_pct=nan)) is True
    assert lessons.check_hits(Check("pool_age_s", "<", 1.0), _snap(pool_created_ts=nan)) is True
    book = LessonBook()
    book.add(_lesson("top10_pct >= 20.0"))
    assert book.blocking(_snap(top10_pct=nan)) is not None


def test_an_infinite_field_value_is_compared_not_unknown():
    assert not lessons.check_hits(Check("top10_pct", "<", 5.0), _snap(top10_pct=float("inf")))
    assert lessons.check_hits(Check("top10_pct", ">", 5.0), _snap(top10_pct=float("inf")))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_entry_value_is_left_out_of_the_derivation(bad):
    pos = _position(top10_pct=bad, dev_pct=1.0, liquidity_usd=None)
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None and lesson.check == "dev_pct >= 1.0"
    only_bad = _position(top10_pct=bad, liquidity_usd=None)
    assert lessons.derive_lesson(only_bad, LOSS, S) is None
    liq = _position(top10_pct=None, liquidity_usd=bad)
    assert lessons.derive_lesson(liq, LOSS, S) is None


@pytest.mark.parametrize("value", [1e-7, 1.5e22, 0.1, 4.0, 1234567.891])
def test_a_derived_check_is_repr_of_the_float_and_always_parses(value):
    pos = _position(dev_pct=value, top10_pct=None, liquidity_usd=None)
    lesson = lessons.derive_lesson(pos, LOSS, S)
    assert lesson is not None
    assert lesson.check == f"dev_pct >= {float(value)!r}"
    assert lessons.parse_check(lesson.check) == Check("dev_pct", ">=", float(value))


def test_an_integer_bundled_count_is_written_as_a_float():
    pos = _position(bundled_wallets=4, top10_pct=None, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, S).check == "bundled_wallets >= 4.0"


def test_insiders_are_measured_against_the_insiders_limit():
    # insiders 12/15 = 0.8 loses to top10 22/25 = 0.88. Against the dev limit (5) it would win.
    pos = _position(top10_pct=22.0, insiders_pct=12.0, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, S).check == "top10_pct >= 22.0"
    # and it wins when it is really the closest: 14.5/15 beats 20/25
    pos = _position(top10_pct=20.0, insiders_pct=14.5, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, S).check == "insiders_pct >= 14.5"


def test_bundled_wallets_are_measured_against_the_bundled_limit():
    # 4/5 = 0.8 beats top10 15/25 = 0.6. Against the insiders limit (15) it would lose.
    pos = _position(top10_pct=15.0, bundled_wallets=4, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, S).check == "bundled_wallets >= 4.0"


def test_a_tie_between_insiders_and_bundled_goes_to_insiders():
    # 9/15 and 3/5 are both 0.6; insiders_pct is listed first.
    pos = _position(insiders_pct=9.0, bundled_wallets=3, liquidity_usd=None)
    assert lessons.derive_lesson(pos, LOSS, S).check == "insiders_pct >= 9.0"


@pytest.mark.parametrize("missing", ["created_ts", "source_mint", "lesson_id", "check"])
def test_from_json_refuses_a_row_missing_any_required_key(missing):
    row = {k: v for k, v in dataclasses.asdict(_lesson()).items() if k != missing}
    with pytest.raises(LessonError):
        LessonBook.from_json([row])


def test_from_json_accepts_a_row_without_why():
    row = {k: v for k, v in dataclasses.asdict(_lesson()).items() if k != "why"}
    assert len(LessonBook.from_json([row]).to_json()) == 1


def test_check_hits_refuses_an_operator_outside_the_four_even_for_an_unknown_value():
    blank = model.TokenSnapshot(ts=1, mint="M", symbol="M")
    for snap in (blank, _snap(top10_pct=10.0)):
        for op in ("==", "!=", "", "=>"):
            with pytest.raises(LessonError):
                lessons.check_hits(Check("top10_pct", op, 1.0), snap)
