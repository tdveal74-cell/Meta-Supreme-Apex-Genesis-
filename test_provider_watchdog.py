"""The provider refusal watchdog, driven by strings these vendors really sent.

The load bearing test is `test_it_would_have_fired_on_the_real_2026_09_17_outage`,
which replays the actual failures of that day through the real verdict function
and asserts ALARM. A watchdog written after an outage that cannot be shown to
catch that outage is decoration.

`classify` is tested against verbatim vendor text rather than invented text,
because the whole judgement rests on matching what they actually say. Two of
these strings are copied from real records: the Cerebras 402 read out of
execution 410 on 2026-09-17, and the Anthropic message quoted in the 2026-08-14
teardown.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts.provider_watchdog import (
    ALARM,
    AUTH,
    CANNOT_CHECK,
    OK,
    PAYMENT,
    RATE,
    classify,
    parse_iso,
    refusals_in_run_data,
    saves_no_success_data,
    swallowing_provider_nodes,
    verdict,
)

NOW = datetime(2026, 9, 17, 19, 30, tzinfo=timezone.utc)


def at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


def failure(hours_ago: float, kind: str, node: str = "Write Packaging (Cerebras)") -> dict:
    return {
        "id": 400 + int(hours_ago),
        "workflow_id": "qEkGOUsNyVaRAmm6",
        "node": node,
        "started_at": at(hours_ago),
        "kind": kind,
    }


# --------------------------------------------------------------------------
# classify, against real vendor text
# --------------------------------------------------------------------------

def test_the_real_cerebras_402_is_a_payment_refusal():
    """Verbatim from execution 410, TQO FINAL V5, 2026-09-17T19:00:00Z."""
    assert classify("Payment required - perhaps check your payment details?", 402) == PAYMENT
    # and on the message alone, in case a caller loses the code
    assert classify("Payment required - perhaps check your payment details?") == PAYMENT


def test_the_real_anthropic_message_is_a_payment_refusal():
    """Verbatim from the 2026-08-14 teardown, executions 1938 and 1942."""
    message = (
        "Your credit balance is too low to access the Anthropic API. "
        "Please go to Plans & Billing to upgrade or purchase credits."
    )
    assert classify(message, 400) == PAYMENT


def test_the_real_rate_limit_message_is_rate_not_payment():
    """Verbatim from execution 271, 2026-09-16. It must not alarm on its own."""
    assert classify("The service is receiving too many requests from you") == RATE
    assert classify(None, 429) == RATE


def test_auth_failures_are_their_own_kind():
    assert classify("invalid api key provided", 401) == AUTH
    assert classify("Unauthorized") == AUTH
    assert classify(None, 403) == AUTH


def test_an_ordinary_failure_is_not_a_refusal():
    """The one that keeps this from alarming on everything."""
    assert classify("Filter validation failed: Column(s) \"status\" do not exist") is None
    assert classify("connect ETIMEDOUT 10.0.0.1:443") is None
    assert classify("Cannot read properties of undefined") is None
    assert classify("") is None
    assert classify(None) is None


def test_the_http_code_wins_over_the_message():
    """A 402 is a payment refusal whatever prose the vendor wraps it in."""
    assert classify("something went wrong", 402) == PAYMENT


def test_a_garbled_http_code_falls_back_to_the_message():
    assert classify("Payment required", "not-a-number") == PAYMENT
    assert classify("some unrelated failure", "not-a-number") is None


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

def test_no_failures_is_ok():
    code, line = verdict([], NOW)
    assert code == OK
    assert "no payment or auth refusal" in line


def test_a_payment_refusal_alarms_and_says_how_long():
    code, line = verdict([failure(1, PAYMENT), failure(5, PAYMENT)], NOW)
    assert code == ALARM
    assert "2 run(s)" in line
    assert "5.0h ago" in line, "the oldest in window sets the age, not the newest"
    assert "Write Packaging (Cerebras)" in line
    assert "qEkGOUsNyVaRAmm6" in line


def test_an_auth_refusal_alarms_too():
    code, line = verdict([failure(2, AUTH)], NOW)
    assert code == ALARM
    assert "auth" in line


def test_a_rate_limit_alone_does_not_alarm_but_is_reported():
    code, line = verdict([failure(1, RATE), failure(2, RATE)], NOW)
    assert code == OK
    assert "2 rate limited run(s)" in line
    assert "clears itself" in line


def test_a_rate_limit_beside_a_payment_refusal_still_alarms():
    code, _ = verdict([failure(1, RATE), failure(2, PAYMENT)], NOW)
    assert code == ALARM


def test_a_refusal_outside_the_window_does_not_alarm():
    """So a fixed outage stops alarming rather than lingering."""
    code, line = verdict([failure(9, PAYMENT)], NOW, window_h=6.0)
    assert code == OK
    assert "no payment or auth refusal in the last 6h" in line


def test_the_window_boundary_is_inclusive():
    code, _ = verdict([failure(6, PAYMENT)], NOW, window_h=6.0)
    assert code == ALARM


def test_an_unreadable_timestamp_is_skipped_rather_than_guessed():
    bad = failure(1, PAYMENT)
    bad["started_at"] = "not a timestamp"
    code, _ = verdict([bad], NOW)
    assert code == OK, "a failure with no readable time cannot be placed in the window"


def test_truncation_is_disclosed_on_an_ok_verdict():
    code, line = verdict([], NOW, truncated=True)
    assert code == OK
    assert "row cap" in line and "recurs" in line


# --------------------------------------------------------------------------
# the outage this was written for
# --------------------------------------------------------------------------

def test_it_would_have_fired_on_the_real_2026_09_17_outage():
    """Replay of the real failures, from the execution ids read that day.

    Eight runs failed on the Cerebras 402 between 01:00Z and 19:00Z. Nothing
    reported it for eighteen hours. Pointed at any three hour slice of that
    day, this returns ALARM.
    """
    real = [
        ("330", "2026-09-17T01:00:00Z"),
        ("340", "2026-09-17T04:00:00Z"),
        ("352", "2026-09-17T07:00:00Z"),
        ("364", "2026-09-17T10:00:00Z"),
        ("369", "2026-09-17T10:20:00Z"),
        ("392", "2026-09-17T13:00:00Z"),
        ("400", "2026-09-17T16:00:00Z"),
        ("410", "2026-09-17T19:00:00Z"),
    ]
    failures = [
        {
            "id": i,
            "workflow_id": "qEkGOUsNyVaRAmm6",
            "node": "Write Packaging (Cerebras)",
            "started_at": stamp,
            "kind": classify("Payment required - perhaps check your payment details?", 402),
        }
        for i, stamp in real
    ]

    # as it would have run at 04:00Z, three hours into the outage
    code, line = verdict(failures, datetime(2026, 9, 17, 4, 30, tzinfo=timezone.utc))
    assert code == ALARM
    assert "starving" in line

    # and at the end of the day, still alarming rather than having given up
    code, line = verdict(failures, datetime(2026, 9, 17, 19, 30, tzinfo=timezone.utc))
    assert code == ALARM
    assert "Write Packaging (Cerebras)" in line


def test_the_three_outcomes_are_distinct():
    """OK, ALARM and CANNOT CHECK are never the same number."""
    assert len({OK, ALARM, CANNOT_CHECK}) == 3
    assert OK == 0 and ALARM == 1 and CANNOT_CHECK == 2


def test_parse_iso_handles_the_shapes_this_api_returns():
    assert parse_iso("2026-09-17T19:00:00.070Z") is not None
    assert parse_iso("2026-09-17T19:00:00+00:00") is not None
    assert parse_iso("2026-09-17T19:00:00") is not None, "naive is read as UTC"
    assert parse_iso("") is None
    assert parse_iso(None) is None
    assert parse_iso(12345) is None


@pytest.mark.parametrize("phrase", ["billing", "quota exceeded"])
def test_the_broad_payment_phrases_are_deliberate(phrase):
    """These two are wider than the rest, and the direction is on purpose.

    A false alarm costs a look. A missed refusal costs the pipeline, which is
    what happened. So these stay broad, and this test records that as a choice
    rather than an accident.
    """
    assert classify(f"the request failed: {phrase}") == PAYMENT


# ---------------------------------------------------------------------------
# The soft failure path, added 2026-09-17 after reading the live nodes.
#
# Every node fixture below is copied from the real workflow as the n8n API
# returned it that day, trimmed to the keys the functions read. Inventing the
# shape would test the invention, and the whole reason this path exists is that
# the real shape was not what the first version assumed.
# ---------------------------------------------------------------------------

#: DEVON Face (Build 15), node `Cerebras Chat`. Swallows twice over.
FACE_PROVIDER_NODE = {
    "name": "Cerebras Chat",
    "type": "n8n-nodes-base.httpRequest",
    "parameters": {
        "method": "POST",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "options": {
            "timeout": 45000,
            "response": {"response": {"fullResponse": True, "neverError": True}},
        },
    },
    "onError": "continueRegularOutput",
}

#: DEVON Face, node `File Job`. Swallows identically, and is not a provider.
#: The negative control that stops the host check being decorative.
FACE_INTAKE_NODE = {
    "name": "File Job",
    "type": "n8n-nodes-base.httpRequest",
    "parameters": {
        "method": "POST",
        "url": "https://n8n.editforge.online/webhook/devon-intake",
        "options": {
            "timeout": 240000,
            "response": {"response": {"fullResponse": True, "neverError": True}},
        },
    },
    "onError": "continueRegularOutput",
}


def test_it_finds_the_real_face_provider_node():
    workflow = {"nodes": [FACE_PROVIDER_NODE, FACE_INTAKE_NODE]}
    assert swallowing_provider_nodes(workflow) == ["Cerebras Chat"]


def test_it_ignores_a_swallowing_node_that_is_not_a_provider():
    assert swallowing_provider_nodes({"nodes": [FACE_INTAKE_NODE]}) == []


def test_it_ignores_a_provider_node_that_throws():
    """A lane that errors is already covered by the error list; counting it here
    would double report the same outage under two node names."""
    throwing = {
        "name": "Write Script (Cerebras)",
        "parameters": {
            "url": "https://api.cerebras.ai/v1/chat/completions",
            "options": {"timeout": 60000},
        },
    }
    assert swallowing_provider_nodes({"nodes": [throwing]}) == []


def test_never_error_alone_is_enough_to_swallow():
    node = {
        "name": "Quiet",
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "options": {"response": {"response": {"neverError": True}}},
        },
    }
    assert swallowing_provider_nodes({"nodes": [node]}) == ["Quiet"]


def test_on_error_alone_is_enough_to_swallow():
    node = {
        "name": "Quiet Too",
        "parameters": {"url": "https://api.anthropic.com/v1/messages"},
        "onError": "continueRegularOutput",
    }
    assert swallowing_provider_nodes({"nodes": [node]}) == ["Quiet Too"]


def test_a_workflow_with_no_nodes_key_does_not_throw():
    assert swallowing_provider_nodes({}) == []
    assert swallowing_provider_nodes({"nodes": [None, "junk", 7]}) == []


def test_the_drive_draft_writer_settings_read_as_unwatchable():
    """Copied from the live workflow on 2026-09-17."""
    workflow = {
        "settings": {
            "executionOrder": "v1",
            "availableInMCP": True,
            "errorWorkflow": "bqcnIS0Qv4RkTCU1",
            "saveDataSuccessExecution": "none",
            "executionTimeout": 120,
        }
    }
    assert saves_no_success_data(workflow) is True


def test_the_face_settings_read_as_watchable():
    workflow = {
        "settings": {
            "executionOrder": "v1",
            "availableInMCP": True,
            "errorWorkflow": "bqcnIS0Qv4RkTCU1",
            "executionTimeout": 300,
        }
    }
    assert saves_no_success_data(workflow) is False
    assert saves_no_success_data({}) is False


def _run_data(node: str, payload):
    """The shape n8n returns for one node, one run, one output branch."""
    return {node: [{"data": {"main": [[{"json": payload}]]}}]}


def test_a_402_inside_a_successful_run_is_a_payment_refusal():
    data = _run_data("Cerebras Chat", {"statusCode": 402, "body": {}})
    assert refusals_in_run_data(data, ["Cerebras Chat"]) == [("Cerebras Chat", PAYMENT)]


def test_a_200_inside_a_successful_run_is_not_a_refusal():
    data = _run_data("Cerebras Chat", {"statusCode": 200, "body": {"choices": []}})
    assert refusals_in_run_data(data, ["Cerebras Chat"]) == []


def test_a_429_inside_a_successful_run_is_counted_as_rate():
    data = _run_data("Cerebras Chat", {"statusCode": 429})
    assert refusals_in_run_data(data, ["Cerebras Chat"]) == [("Cerebras Chat", RATE)]


def test_a_200_carrying_an_error_object_is_still_read():
    """Some providers answer 200 with the refusal in the body. The status code
    says nothing there, so the message is what has to be read."""
    data = _run_data(
        "Cerebras Chat",
        {"statusCode": 200, "body": {"error": {"message": "Your credit balance is too low"}}},
    )
    assert refusals_in_run_data(data, ["Cerebras Chat"]) == [("Cerebras Chat", PAYMENT)]


def test_only_the_named_nodes_are_read():
    """Every other node's output is model text or ledger rows, and scanning it
    for a status code would invent refusals out of ordinary data."""
    data = _run_data("Parse Reply", {"statusCode": 402})
    assert refusals_in_run_data(data, ["Cerebras Chat"]) == []


def test_the_walk_is_bounded():
    items = [{"json": {"statusCode": 402}} for _ in range(50)]
    data = {"Cerebras Chat": [{"data": {"main": [items]}}]}
    found = refusals_in_run_data(data, ["Cerebras Chat"], max_items=3)
    assert len(found) == 3


def test_malformed_run_data_never_throws():
    for junk in (None, [], "text", {"Cerebras Chat": "not a list"},
                 {"Cerebras Chat": [{"data": {"main": "no"}}]},
                 {"Cerebras Chat": [{"data": {"main": [[None, 7, {"json": None}]]}}]}):
        assert refusals_in_run_data(junk, ["Cerebras Chat"]) == []


def test_a_soft_refusal_alone_raises_the_alarm():
    """The whole point. No errored execution anywhere, and the alarm still fires."""
    now = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)
    soft = [
        {
            "id": "812",
            "workflow_id": "sPv6Cq7elbjoi5Nw",
            "node": "Cerebras Chat",
            "started_at": "2026-09-17T19:30:00.000Z",
            "kind": PAYMENT,
        }
    ]
    code, line = verdict(soft, now)
    assert code == ALARM
    assert "Cerebras Chat" in line


def test_the_unwatchable_lane_is_named_on_a_clean_run():
    now = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)
    code, line = verdict([], now, blind=["DEVON — Drive Draft Writer (Build 16)"])
    assert code == OK
    assert "NOT WATCHED" in line
    assert "Drive Draft Writer" in line


def test_the_unwatchable_lane_is_named_on_an_alarming_run_too():
    """A live alarm does not make the unwatched lane watched."""
    now = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)
    failures = [
        {
            "id": "410",
            "workflow_id": "qEkGOUsNyVaRAmm6",
            "node": "Write Script (Cerebras)",
            "started_at": "2026-09-17T19:00:00.070Z",
            "kind": PAYMENT,
        }
    ]
    code, line = verdict(failures, now, blind=["DEVON — Drive Draft Writer (Build 16)"])
    assert code == ALARM
    assert "NOT WATCHED" in line


def test_a_clean_estate_reads_clean():
    """No blind lanes means no disclosure sentence, so the note carries signal."""
    now = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)
    code, line = verdict([], now, blind=[])
    assert code == OK
    assert "NOT WATCHED" not in line
