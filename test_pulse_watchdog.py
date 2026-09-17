"""The external Pulse watchdog decides correctly, including when it must refuse.

``scripts/pulse_watchdog.py`` is the only thing in the estate that can notice the
Build 13 Pulse has STOPPED, because ``missed_beat`` is computed by the Pulse and
a workflow that never runs writes nothing. That makes its decision function worth
pinning hard, and one case in particular.

THE CASE THAT CARRIES THIS FILE is ``test_a_fresh_reflection_never_masks_a_dead_
pulse``. ``devon_heartbeat_log`` holds both ``pulse`` rows and ``reflection``
rows. The obvious implementation takes the newest row in the table, and the
obvious implementation is silently broken: DEVON's reflection would keep writing
fresh rows while the Pulse lay dead, and the watchdog would report OK forever. So
that test builds exactly that table and asserts the watchdog alarms, then asserts
that the newest-row-of-any-kind reading WOULD have said the log was fresh. That
second assertion is the negative control. Without it the test passes against a
broken implementation and proves nothing, which this repository has shipped
before.

Everything here is pure: rows in, verdict out. No network, no API key, no clock.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.pulse_watchdog import (
    ALARM,
    CANNOT_CHECK,
    MISSED_BEAT_H,
    OK,
    PAGE,
    newest_beat,
    parse_iso,
    verdict,
)

NOW = datetime(2026, 9, 17, 4, 0, 0, tzinfo=timezone.utc)


def beat(hours_ago: float, kind: str = "pulse") -> dict:
    stamp = NOW - timedelta(hours=hours_ago)
    return {
        "kind": kind,
        "beat_at": stamp.isoformat().replace("+00:00", "Z"),
        "vitals": "",
        "findings": "",
    }


# --------------------------------------------------------------------------
# The load bearing case
# --------------------------------------------------------------------------


def test_a_fresh_reflection_never_masks_a_dead_pulse():
    """A reflection is not a beat, and must not be mistaken for one."""
    rows = [
        beat(30.0, kind="pulse"),  # the Pulse died thirty hours ago
        beat(0.2, kind="reflection"),  # the reflection wrote twelve minutes ago
    ]

    code, message = verdict(rows, NOW)

    assert code == ALARM, (
        "a reflection row written minutes ago made the watchdog believe the Pulse was "
        f"alive. It is not: the newest PULSE row is 30h old. Got {code}: {message}"
    )
    assert "30.0h ago" in message

    # Negative control. Had the watchdog taken the newest row of any kind, this
    # is what it would have concluded, and it would have been wrong. If this
    # assertion ever fails the test above has stopped discriminating.
    newest_any_kind = max(parse_iso(r["beat_at"]) for r in rows)
    assert (NOW - newest_any_kind).total_seconds() / 3600.0 < MISSED_BEAT_H, (
        "the negative control no longer reproduces the naive reading, so the case "
        "above no longer proves the kind filter is doing anything"
    )


# --------------------------------------------------------------------------
# The ordinary verdicts
# --------------------------------------------------------------------------


def test_a_recent_beat_is_ok():
    code, message = verdict([beat(1.0), beat(7.0)], NOW)
    assert code == OK, message
    assert "1.0h ago" in message


def test_a_beat_inside_the_threshold_is_still_ok():
    code, message = verdict([beat(MISSED_BEAT_H - 0.1)], NOW)
    assert code == OK, message


def test_a_beat_past_the_threshold_alarms():
    code, message = verdict([beat(MISSED_BEAT_H + 0.1)], NOW)
    assert code == ALARM, message
    assert "missed beat" in message


def test_the_newest_beat_wins_whatever_order_the_rows_arrive_in():
    """The rows API promises no order, so the verdict must not depend on one."""
    scattered = [beat(40.0), beat(2.0), beat(19.0), beat(100.0)]
    code, message = verdict(scattered, NOW)
    assert code == OK, message
    assert "2.0h ago" in message

    reversed_code, reversed_message = verdict(list(reversed(scattered)), NOW)
    assert (reversed_code, reversed_message) == (code, message)


# --------------------------------------------------------------------------
# Refusing, rather than guessing
# --------------------------------------------------------------------------


def test_an_empty_log_alarms_rather_than_passing():
    code, message = verdict([], NOW)
    assert code == ALARM, message
    assert "never beaten" in message


def test_a_log_with_no_pulse_rows_alarms():
    code, message = verdict([beat(0.1, kind="reflection")], NOW)
    assert code == ALARM, message


def test_unreadable_timestamps_are_cannot_check_not_healthy():
    rows = [
        {"kind": "pulse", "beat_at": ""},
        {"kind": "pulse", "beat_at": "not a date"},
        {"kind": "pulse"},
    ]
    code, message = verdict(rows, NOW)
    assert code == CANNOT_CHECK, message
    assert "cannot tell" in message


def test_a_read_at_the_row_cap_refuses_because_it_may_be_truncated():
    """A full page may be short, and the API cannot page or promise an order."""
    rows = [beat(0.5) for _ in range(PAGE)]
    code, message = verdict(rows, NOW)
    assert code == CANNOT_CHECK, (
        "a read at the cap was judged on its face. The newest beat may not be in it, "
        f"so the verdict is unsound. Got {code}: {message}"
    )
    assert str(PAGE) in message


def test_some_unreadable_rows_do_not_stop_a_verdict_but_are_declared():
    rows = [beat(1.0), {"kind": "pulse", "beat_at": "rubbish"}]
    code, message = verdict(rows, NOW)
    assert code == OK, message
    assert "1 pulse row(s) had no readable beat_at" in message


# --------------------------------------------------------------------------
# Parsing, and the drift guard
# --------------------------------------------------------------------------


def test_parse_iso_reads_the_shapes_this_table_actually_holds():
    assert parse_iso("2026-09-16T22:00:15.101Z") == datetime(
        2026, 9, 16, 22, 0, 15, 101000, tzinfo=timezone.utc
    )
    assert parse_iso("2026-09-16T22:00:15+00:00") == datetime(
        2026, 9, 16, 22, 0, 15, tzinfo=timezone.utc
    )
    # Naive timestamps are read as UTC rather than rejected, because the Pulse
    # writes UTC and a missing suffix should not become an outage.
    assert parse_iso("2026-09-16T22:00:15") == datetime(
        2026, 9, 16, 22, 0, 15, tzinfo=timezone.utc
    )
    for junk in ("", "   ", "not a date", None, 17, {}):
        assert parse_iso(junk) is None, junk


def test_kind_matching_tolerates_case_and_padding():
    newest, seen, unreadable = newest_beat([{"kind": " Pulse ", "beat_at": beat(3.0)["beat_at"]}])
    assert seen == 1 and unreadable == 0 and newest is not None


def test_the_threshold_still_matches_the_pulse_that_writes_the_log():
    """The watchdog and the Pulse must agree on what a missed beat is.

    ``MISSED_BEAT_H`` is duplicated: once in the n8n Code node mirrored at
    ``n8n/devon/heartbeat/compose_pulse.js``, once in the watchdog. Two copies of
    a number drift, and drift here means the two disagree about whether the
    estate is healthy. This reads the real file rather than trusting a comment.
    """
    source = Path(__file__).parent / "n8n" / "devon" / "heartbeat" / "compose_pulse.js"
    assert source.exists(), f"{source} is missing; the Pulse's own copy of the threshold is gone"

    match = re.search(r"^const MISSED_BEAT_H = ([0-9.]+);", source.read_text(encoding="utf-8"), re.M)
    assert match, "could not find MISSED_BEAT_H in compose_pulse.js; the guard cannot run"

    assert float(match.group(1)) == MISSED_BEAT_H, (
        f"compose_pulse.js says a missed beat is {match.group(1)}h and "
        f"scripts/pulse_watchdog.py says {MISSED_BEAT_H}h. Reconcile them: while they "
        "disagree the watchdog is measuring something the Pulse does not mean."
    )
