"""
Cadence parsing and next-slot arithmetic — pure, no database, no clock.

Every case here is a boundary someone gets wrong by hand: the slot exactly
equal to `now`, the weekly slot earlier today on the right weekday, the
month and year rollovers, and DST — which does not apply, because everything
is UTC, and that is itself worth a test so the decision is visible.
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.workflows.schedule import (
    CadenceError,
    describe_cadence,
    next_slot,
    parse_cadence,
)


def utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,kind,hour,minute,weekday",
    [
        ("hourly:15", "hourly", None, 15, None),
        ("daily:07:30", "daily", 7, 30, None),
        ("weekly:mon:07:00", "weekly", 7, 0, 0),
        ("weekly:sun:23:59", "weekly", 23, 59, 6),
        ("  WEEKLY:Fri:09:05  ", "weekly", 9, 5, 4),
    ],
)
def test_valid_cadences_parse(raw, kind, hour, minute, weekday):
    cadence = parse_cadence(raw)
    assert (cadence.kind, cadence.hour, cadence.minute, cadence.weekday) == (
        kind,
        hour,
        minute,
        weekday,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        None,
        "yearly:01:00",
        "weekly:xyz:07:00",
        "daily:25:00",
        "daily:07:60",
        "hourly:60",
        "0 7 * * 1",  # cron is explicitly not supported
        "every monday",
    ],
)
def test_invalid_cadences_are_rejected(raw):
    with pytest.raises(CadenceError):
        parse_cadence(raw)


# ---------------------------------------------------------------------------
# Next slot
# ---------------------------------------------------------------------------


def test_hourly_rolls_to_the_next_hour():
    assert next_slot(parse_cadence("hourly:15"), utc(2026, 8, 9, 10, 20)) == utc(
        2026, 8, 9, 11, 15
    )


def test_hourly_finds_the_slot_later_this_hour():
    assert next_slot(parse_cadence("hourly:45"), utc(2026, 8, 9, 10, 20)) == utc(
        2026, 8, 9, 10, 45
    )


def test_a_slot_exactly_now_is_not_returned():
    """Strictly after. An inclusive boundary fires the same slot twice."""
    now = utc(2026, 8, 9, 10, 15)
    assert next_slot(parse_cadence("hourly:15"), now) == utc(2026, 8, 9, 11, 15)


def test_daily_crosses_midnight():
    assert next_slot(parse_cadence("daily:07:00"), utc(2026, 8, 9, 23, 30)) == utc(
        2026, 8, 10, 7, 0
    )


def test_weekly_finds_the_same_day_later():
    # 2026-08-10 is a Monday.
    assert next_slot(parse_cadence("weekly:mon:07:00"), utc(2026, 8, 10, 6, 0)) == utc(
        2026, 8, 10, 7, 0
    )


def test_weekly_rolls_a_full_week_when_today_has_passed():
    assert next_slot(parse_cadence("weekly:mon:07:00"), utc(2026, 8, 10, 8, 0)) == utc(
        2026, 8, 17, 7, 0
    )


def test_month_and_year_rollover():
    assert next_slot(parse_cadence("daily:09:00"), utc(2026, 8, 31, 10, 0)) == utc(
        2026, 9, 1, 9, 0
    )
    assert next_slot(parse_cadence("daily:09:00"), utc(2026, 12, 31, 10, 0)) == utc(
        2027, 1, 1, 9, 0
    )


def test_leap_day_is_just_another_day():
    assert next_slot(parse_cadence("daily:09:00"), utc(2028, 2, 28, 10, 0)) == utc(
        2028, 2, 29, 9, 0
    )


def test_slots_are_utc_and_do_not_shift_across_a_dst_boundary():
    """
    Cadences are UTC by definition, so a workflow scheduled for 07:00 fires at
    07:00 UTC year-round — it does NOT track a user's local wall clock. That is
    a real product limitation, recorded here so the choice is deliberate.
    """
    # Europe/London moves to GMT on 2026-10-25; UTC does not.
    before = next_slot(parse_cadence("daily:07:00"), utc(2026, 10, 24, 8, 0))
    after = next_slot(parse_cadence("daily:07:00"), utc(2026, 10, 26, 8, 0))
    assert before.hour == 7 and after.hour == 7


def test_naive_datetimes_are_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        next_slot(parse_cadence("hourly:00"), datetime(2026, 8, 9, 10, 0))


def test_successive_slots_never_repeat():
    """Feeding a slot back in must always advance — the dispatcher's core loop."""
    cadence = parse_cadence("hourly:30")
    current = utc(2026, 8, 9, 0, 0)
    seen = []
    for _ in range(30):
        current = next_slot(cadence, current)
        seen.append(current)
    assert len(set(seen)) == 30
    assert seen == sorted(seen)
    assert seen[-1] - seen[0] == timedelta(hours=29)


def test_descriptions_are_human_readable():
    assert describe_cadence(parse_cadence("weekly:mon:07:00")) == "every Mon at 07:00 UTC"
    assert describe_cadence(parse_cadence("daily:18:05")) == "every day at 18:05 UTC"
    assert describe_cadence(parse_cadence("hourly:05")) == "every hour at :05 UTC"
