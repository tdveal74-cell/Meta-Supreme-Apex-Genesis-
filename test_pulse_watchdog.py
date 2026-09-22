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

THE SECOND CASE THAT CARRIES THIS FILE is ``test_the_outage_of_2026_09_20_is_
caught_and_the_beat_alone_would_have_missed_it``. The beat reading above is
necessary and was never sufficient: the Heartbeat writes its row about 150ms
into a run, on a branch parallel to the email, so a run that beats and then dies
at the send leaves a beat that looks perfect. That is exactly what happened for
thirty six hours from 2026-09-20, and this script printed OK four times a day
through it. That test replays the real executions and carries the same kind of
negative control, asserting that the beat reading alone still says OK.

Most cases here are pure: rows in, verdict out, no network and no clock. Three
are not, and say so in their names: they stub the two fetchers and drive
``main`` itself, because ``verdict`` and ``run_verdict`` are separate functions
and main() is the only place that knows both have to run. A pure function
nobody calls is worth nothing.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.pulse_watchdog import (
    ALARM,
    ALARM_LANES,
    CANNOT_CHECK,
    MISSED_BEAT_H,
    NARROW_LIMIT,
    OK,
    PAGE,
    UNWATCHABLE_LANE,
    combine,
    is_newest_first,
    newest_beat,
    newest_failure,
    parse_iso,
    run_verdict,
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


# --------------------------------------------------------------------------
# A fresh beat is not a finished run
#
# Everything below was copied out of the live instance on 2026-09-22, during
# the outage that this script reported OK through. The timestamps, execution
# ids, node name and SMTP reply are verbatim, so these cases replay a real
# failure rather than an imagined one.
# --------------------------------------------------------------------------

def live_beat(hours_ago: float = 0.5) -> dict:
    """A beat stamped against the REAL clock, for the tests that drive main().

    main() calls datetime.now itself and cannot be handed a frozen one, so a
    fixed fixture in a main() test stops meaning what it says the moment real
    time walks past the threshold. That is not hypothetical: on 2026-09-22 the
    unreadable-run-list test below was already failing on main, having passed
    when it was written a few hours earlier, because OUTAGE_BEAT had aged out
    of the 7.5h window. Worse, its sibling kept passing for the wrong reason,
    since a stale beat alarms whether or not the run check works at all.
    """
    stamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"kind": "pulse", "beat_at": stamp.isoformat().replace("+00:00", "Z")}


def live_failed_run(hours_ago: float = 0.2, execution_id: str = "779") -> dict:
    stamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"id": execution_id, "startedAt": stamp.isoformat().replace("+00:00", "Z")}


OUTAGE_NOW = datetime(2026, 9, 22, 5, 0, 0, tzinfo=timezone.utc)

#: Beat row 116, written by execution 729 about 150ms into a run that then took
#: twelve seconds to die. Read from devon_heartbeat_log on 2026-09-22.
OUTAGE_BEAT = {
    "kind": "pulse",
    "beat_at": "2026-09-22T04:00:15.127Z",
    "vitals": "{}",
    "findings": "reflection_missing | No fresh reflection",
}

#: The seven consecutive failures, as /api/v1/executions?status=error returns
#: them. Deliberately not in newest-first order: this API promises none.
OUTAGE_RUNS = [
    {"id": "698", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-21T16:00:15.042Z", "stoppedAt": "2026-09-21T16:00:26.817Z"},
    {"id": "729", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-22T04:00:15.037Z", "stoppedAt": "2026-09-22T04:00:27.596Z"},
    {"id": "714", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-21T22:00:15.037Z", "stoppedAt": "2026-09-21T22:00:27.237Z"},
    {"id": "675", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-21T10:00:15.037Z", "stoppedAt": "2026-09-21T10:00:26.661Z"},
    {"id": "654", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-21T04:00:15.040Z", "stoppedAt": "2026-09-21T04:00:27.237Z"},
    {"id": "639", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-20T22:00:15.025Z", "stoppedAt": "2026-09-20T22:00:26.252Z"},
    {"id": "623", "workflowId": "EEDrp2jLlw2Ssd5b", "status": "error",
     "startedAt": "2026-09-20T16:00:15.036Z", "stoppedAt": "2026-09-20T16:00:27.935Z"},
]

#: Execution 729 opened with includeData=true, trimmed to the keys this script
#: reads. The message is the SMTP server's own reply.
OUTAGE_DETAIL_PAYLOAD = {
    "id": "729",
    "status": "error",
    "data": {
        "resultData": {
            "lastNodeExecuted": "Send Pulse",
            "error": {
                "name": "NodeApiError",
                "httpCode": "EAUTH",
                "node": {"name": "Send Pulse", "type": "n8n-nodes-base.emailSend"},
                "message": (
                    "Invalid login: 535-5.7.8 Username and Password not accepted. For more "
                    "information, go to\n535 5.7.8  https://support.google.com/mail/"
                    "?p=BadCredentials 2adb3069b0e04-5b8d46ad0e9sm155103e87.2 - gsmtp"
                ),
            },
        }
    },
}


def test_the_outage_of_2026_09_20_is_caught_and_the_beat_alone_would_have_missed_it():
    """The load bearing case for the run check, replayed from the real outage.

    The Heartbeat beat on time and died twelve seconds later at the send, four
    times a day for thirty six hours, and this script printed OK through all of
    it. The negative control is the whole point: it asserts that the beat
    reading, on its own, still says everything is fine. Without it this test
    would pass against an implementation that had changed nothing.
    """
    run_code, run_message = run_verdict(OUTAGE_RUNS, OUTAGE_NOW)

    assert run_code == ALARM, (
        "seven consecutive failed Heartbeat runs, the newest an hour old, were not "
        f"an alarm. Got {run_code}: {run_message}"
    )
    assert "729" in run_message, run_message
    assert "7 errored runs were listed" in run_message, run_message

    # Negative control. This is what the watchdog saw for thirty six hours.
    beat_code, beat_message = verdict([OUTAGE_BEAT], OUTAGE_NOW)
    assert beat_code == OK, (
        "the negative control no longer reproduces the blind spot, so the case above "
        f"no longer proves the run check is doing anything. Got {beat_code}: {beat_message}"
    )
    assert "1.0h ago" in beat_message

    assert combine(beat_code, run_code) == ALARM


def test_main_runs_both_checks_so_the_wiring_cannot_rot():
    """A pure function nobody calls is worth nothing, so drive main() itself.

    ``verdict`` and ``run_verdict`` are separate on purpose, which means main()
    is the only place that knows both must run. This stubs the two fetchers and
    asserts the exit code comes back ALARM on a table whose newest beat is fresh.
    """
    from scripts import pulse_watchdog as mod

    calls = []

    def fake_rows(base, key, table_id):
        calls.append("rows")
        return [live_beat()]

    asked = []

    def fake_runs(base, key, workflow_id, limit=mod.MAX_FAILED_RUNS):
        calls.append("runs")
        asked.append(workflow_id)
        return [live_failed_run()]

    original = (mod.fetch_rows, mod.fetch_failed_runs, mod.failure_detail)
    mod.fetch_rows, mod.fetch_failed_runs = fake_rows, fake_runs
    mod.failure_detail = lambda base, key, execution_id: "node Send Pulse: Invalid login"
    os.environ["N8N_VPS_KEY"] = "test-key-not-a-real-one"
    try:
        code = mod.main([])
    finally:
        mod.fetch_rows, mod.fetch_failed_runs, mod.failure_detail = original
        os.environ.pop("N8N_VPS_KEY", None)

    assert calls[0] == "rows" and calls.count("runs") == len(mod.ALARM_LANES), (
        f"main() did not run the beat check plus one run check per lane; it ran {calls}. "
        "A fresh beat on its own is exactly the reading that missed the September outage."
    )
    assert asked == [lane_id for lane_id, _ in mod.ALARM_LANES], (
        f"main() asked about {asked}, not the lanes in ALARM_LANES. Every one of them "
        "sends on the same credential, which is the whole reason they are all watched."
    )
    assert code == ALARM, (
        f"main() returned {code} on a live outage. The beat here is FRESH on purpose, "
        "so the only thing that can raise this alarm is the run check."
    )


def test_an_unreadable_run_list_is_never_reported_healthy():
    """Half a check is not a pass. The beat alone stopped being sufficient."""
    from scripts import pulse_watchdog as mod

    def fake_runs(base, key, workflow_id, limit=mod.MAX_FAILED_RUNS):
        raise RuntimeError("HTTP 401: unauthorized")

    original = (mod.fetch_rows, mod.fetch_failed_runs)
    mod.fetch_rows = lambda base, key, table_id: [live_beat()]
    mod.fetch_failed_runs = fake_runs
    os.environ["N8N_VPS_KEY"] = "test-key-not-a-real-one"
    try:
        code = mod.main([])
    finally:
        mod.fetch_rows, mod.fetch_failed_runs = original
        os.environ.pop("N8N_VPS_KEY", None)

    assert code == CANNOT_CHECK, (
        f"a fresh beat plus an unreadable run list came back as {code}. That is the "
        "shape of reporting green while watching nothing."
    )


def test_a_failure_older_than_the_window_is_not_a_live_outage():
    """Once the credential is fixed the alarm has to stop, or it teaches nothing."""
    later = OUTAGE_NOW + timedelta(hours=MISSED_BEAT_H + 1)
    code, message = run_verdict(OUTAGE_RUNS, later)
    assert code == OK, message
    assert "old news" in message


def test_no_errored_runs_is_ok_and_says_why():
    code, message = run_verdict([], OUTAGE_NOW)
    assert code == OK, message
    assert "finished" in message


def test_the_newest_failure_wins_whatever_order_the_runs_arrive_in():
    newest, execution_id, seen = newest_failure(OUTAGE_RUNS)
    assert execution_id == "729", execution_id
    assert seen == 7
    assert newest == parse_iso("2026-09-22T04:00:15.037Z")

    reversed_newest, reversed_id, reversed_seen = newest_failure(list(reversed(OUTAGE_RUNS)))
    assert (reversed_newest, reversed_id, reversed_seen) == (newest, execution_id, seen)


def test_a_run_with_an_unreadable_start_does_not_become_the_newest():
    runs = list(OUTAGE_RUNS) + [{"id": "999", "startedAt": "not a date"}]
    _, execution_id, seen = newest_failure(runs)
    assert execution_id == "729", execution_id
    assert seen == 8


def test_combine_lets_a_finding_beat_an_absence_of_one():
    assert combine(OK, OK) == OK
    assert combine(OK, ALARM) == ALARM
    assert combine(ALARM, OK) == ALARM
    assert combine(OK, CANNOT_CHECK) == CANNOT_CHECK
    # The one that matters: a known dead Pulse must not be downgraded to
    # "I could not look" because the second read failed.
    assert combine(ALARM, CANNOT_CHECK) == ALARM
    assert combine(CANNOT_CHECK, ALARM) == ALARM


def test_the_alarm_names_the_failing_node_when_it_can_read_it():
    from scripts import pulse_watchdog as mod

    original = mod.get_json
    mod.get_json = lambda base, key, path: OUTAGE_DETAIL_PAYLOAD
    try:
        detail = mod.failure_detail("https://example.invalid", "k", "729")
    finally:
        mod.get_json = original

    assert detail.startswith("node Send Pulse: Invalid login: 535-5.7.8"), detail
    assert len(detail) <= 220, "the detail is not being truncated"

    code, message = run_verdict(OUTAGE_RUNS, OUTAGE_NOW, detail=detail)
    assert code == ALARM
    assert "Send Pulse" in message, message


def test_detail_that_cannot_be_read_never_downgrades_a_good_alarm():
    """The node name is a nicety. Losing it must not lose the finding."""
    from scripts import pulse_watchdog as mod

    original = mod.get_json

    def boom(base, key, path):
        raise RuntimeError("HTTP 500")

    mod.get_json = boom
    try:
        assert mod.failure_detail("https://example.invalid", "k", "729") == ""
    finally:
        mod.get_json = original

    code, _ = run_verdict(OUTAGE_RUNS, OUTAGE_NOW, detail="")
    assert code == ALARM


def test_the_blind_lane_is_named_and_never_silently_counted():
    """The OS Error Handler reports SUCCESS on a failed send, so a status check
    cannot see it. Listing it beside the lanes that CAN answer would be the
    false comfort this whole script exists to refuse, so it lives apart and is
    declared. If somebody later moves it into ALARM_LANES, this fails.
    """
    blind_id = UNWATCHABLE_LANE[0]
    assert blind_id not in [lane_id for lane_id, _ in ALARM_LANES], (
        "the soft failing lane was added to the watched list. An errored-execution "
        "check can never see it, so watching it there reports green on a dead lane."
    )
    assert len({lane_id for lane_id, _ in ALARM_LANES}) == len(ALARM_LANES)


def test_main_declares_the_blind_lane_on_every_run(capsys):
    """Said green or red. A caveat only printed on failure teaches nothing."""
    from scripts import pulse_watchdog as mod

    original = (mod.fetch_rows, mod.fetch_failed_runs)
    mod.fetch_rows = lambda base, key, table_id: [live_beat()]
    mod.fetch_failed_runs = lambda base, key, workflow_id, limit=mod.MAX_FAILED_RUNS: []
    os.environ["N8N_VPS_KEY"] = "test-key-not-a-real-one"
    try:
        code = mod.main([])
    finally:
        mod.fetch_rows, mod.fetch_failed_runs = original
        os.environ.pop("N8N_VPS_KEY", None)

    printed = capsys.readouterr()
    everything = printed.out + printed.err
    assert code == OK, f"a healthy estate came back as {code}"
    assert "NOT WATCHED" in everything, (
        "a fully green run never told anyone that one of the four lanes is invisible"
    )
    assert UNWATCHABLE_LANE[0] in everything


def test_a_narrowed_read_is_only_trusted_when_it_proves_itself():
    """The dangerous case is a server that ignores sortBy and returns the OLDEST
    rows. Acting on those drops the newest beat and manufactures a false alarm,
    which is worse than the cap the narrowing exists to dodge.
    """
    descending = [{"id": n} for n in range(60, 40, -1)]
    assert is_newest_first(descending, NARROW_LIMIT)

    ascending = [{"id": n} for n in range(40, 60)]
    assert not is_newest_first(ascending, NARROW_LIMIT), (
        "an ignored sortBy came back oldest first and was accepted; that is the "
        "false alarm this guard exists to stop"
    )

    assert not is_newest_first([{"id": n} for n in range(300, 0, -1)], NARROW_LIMIT), (
        "a read larger than asked for means the limit was ignored too"
    )
    assert not is_newest_first([{"id": 9}], NARROW_LIMIT), "one row proves no order"
    assert not is_newest_first([{"id": "9"}, {"id": "8"}], NARROW_LIMIT), "ids must be integers"
    assert not is_newest_first([{"id": 5}, {"id": 5}], NARROW_LIMIT), "ties are not an order"


def test_fetch_rows_falls_back_to_the_wide_read_when_narrowing_is_ignored():
    """The fallback is the whole safety of the change: an instance that does not
    support ordering behaves exactly as it did before this, cap and all.
    """
    from scripts import pulse_watchdog as mod

    paths = []
    oldest_first = [{"id": n, "kind": "pulse"} for n in range(1, 51)]
    wide = [{"id": n, "kind": "pulse"} for n in range(1, 121)]

    def fake_rows_at(base, key, path):
        paths.append(path)
        return oldest_first if "sortBy" in path else wide

    original = mod._rows_at
    mod._rows_at = fake_rows_at
    try:
        rows = mod.fetch_rows("https://example.invalid", "k", "tbl")
    finally:
        mod._rows_at = original

    assert len(paths) == 2 and "sortBy" in paths[0] and "sortBy" not in paths[1], paths
    assert rows == wide, "an ignored sortBy was trusted instead of falling back"


def test_fetch_rows_uses_the_narrow_read_when_the_instance_honours_it():
    from scripts import pulse_watchdog as mod

    newest_first = [{"id": n, "kind": "pulse"} for n in range(120, 70, -1)]
    calls = []

    def fake_rows_at(base, key, path):
        calls.append(path)
        return newest_first

    original = mod._rows_at
    mod._rows_at = fake_rows_at
    try:
        rows = mod.fetch_rows("https://example.invalid", "k", "tbl")
    finally:
        mod._rows_at = original

    assert len(calls) == 1, "the wide read still ran after a good narrow one"
    assert rows == newest_first
    assert len(rows) < PAGE, "a narrowed read that still hits the cap has bought nothing"


def test_every_lane_on_the_dead_credential_is_watched_by_id():
    """Pinned to ids, not to ALARM_LANES, or the guard moves with the mistake.

    Written after the first version of this suite let a mutation through: the
    wiring test above compares what main() asked for against ALARM_LANES, so
    deleting a lane from that constant deletes the expectation too and stays
    green. These three ids come from the workflow list of 2026-09-22, counted
    there rather than from the lanes a session happened to open, and recorded in
    SYS_OPS_a-fresh-beat-is-not-a-finished-run_v1_2026-09-22-0624. The fourth
    sender on that credential is deliberately absent; see the test above.
    """
    assert {lane_id for lane_id, _ in ALARM_LANES} == {
        "EEDrp2jLlw2Ssd5b",  # Heartbeat (Build 13), node Send Pulse
        "bqcnIS0Qv4RkTCU1",  # Error Alarm, node Alert Tee
        "IZBVlXQ8Y5dsGTRS",  # Pipeline Watchdog, node Send Watchdog Alert
    }, (
        "a lane that sends on AgSGuaA2pnZsrZcJ stopped being watched. One dead "
        "password takes all of them down together, which is why they are watched "
        "together."
    )
