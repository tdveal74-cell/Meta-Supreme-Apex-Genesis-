"""Tests for the approval gate, covering the eight paths verified on the live queue."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from services.devon.approval import (
    NO_MATCH,
    ApprovalError,
    ApprovalQueue,
    ApprovalState,
    RefusalReason,
)


def make_request(queue: ApprovalQueue):
    return queue.request(
        title="restart the render box",
        what_happens="Reboots the machine, killing any in flight render.",
        requested_by="DEVON voice router",
    )


# -- request side ------------------------------------------------------------


def test_a_request_with_no_stated_consequence_is_refused_at_the_door():
    queue = ApprovalQueue()
    with pytest.raises(ApprovalError, match="what happens"):
        queue.request(title="do the thing", what_happens="", requested_by="test")


def test_a_request_with_no_title_is_refused():
    queue = ApprovalQueue()
    with pytest.raises(ApprovalError):
        queue.request(title="  ", what_happens="something", requested_by="test")


def test_a_request_starts_pending_and_appears_in_the_queue():
    queue = ApprovalQueue()
    record, _ = make_request(queue)
    assert record.state is ApprovalState.PENDING
    assert record in queue.pending()


def test_the_summary_states_what_the_approver_is_consenting_to():
    queue = ApprovalQueue()
    record, _ = make_request(queue)
    summary = record.summary()
    assert "What happens:" in summary
    assert "killing any in flight render" in summary
    assert "Reversible:" in summary


def test_tokens_are_unique_per_request():
    queue = ApprovalQueue()
    _, first = make_request(queue)
    _, second = make_request(queue)
    assert first != second


# -- the eight decide paths --------------------------------------------------


def test_path_1_no_id():
    queue = ApprovalQueue()
    result = queue.decide(None, "token", "approve")
    assert not result.ok
    assert result.reason is RefusalReason.NO_ID
    assert result.request_id == NO_MATCH


def test_path_2_unknown_id():
    queue = ApprovalQueue()
    result = queue.decide("REQ-DOESNOTEXIST", "token", "approve")
    assert not result.ok
    assert result.reason is RefusalReason.UNKNOWN_ID
    assert result.request_id == NO_MATCH


def test_path_3_wrong_token():
    queue = ApprovalQueue()
    record, _ = make_request(queue)
    result = queue.decide(record.request_id, "not-the-token", "approve")
    assert not result.ok
    assert result.reason is RefusalReason.WRONG_TOKEN
    assert result.request_id == NO_MATCH


def test_path_4_unrecognised_decision():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    result = queue.decide(record.request_id, token, "maybe")
    assert not result.ok
    assert result.reason is RefusalReason.UNRECOGNISED_DECISION


def test_path_5_expired():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    later = datetime.now(timezone.utc) + timedelta(hours=73)
    result = queue.decide(record.request_id, token, "approve", at=later)
    assert not result.ok
    assert result.reason is RefusalReason.EXPIRED
    assert queue.get(record.request_id).state is ApprovalState.EXPIRED


def test_path_6_already_decided():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    assert queue.decide(record.request_id, token, "approve").approved
    second = queue.decide(record.request_id, token, "approve")
    assert not second.ok
    assert second.reason is RefusalReason.ALREADY_DECIDED


def test_path_7_valid_approve():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    result = queue.decide(record.request_id, token, "approve", decided_by="Tee")
    assert result.approved
    assert queue.get(record.request_id).decided_by == "Tee"


def test_path_8_replay_after_the_token_is_consumed():
    """A token is single use. The replay must not succeed."""
    queue = ApprovalQueue()
    record, token = make_request(queue)
    queue.decide(record.request_id, token, "approve")
    replay = queue.decide(record.request_id, token, "approve")
    assert not replay.ok
    assert not replay.approved


# -- properties that hold regardless of routing ------------------------------


def test_every_refusal_resolves_to_the_sentinel():
    """Fails closed by data shape. A sentinel matches no row however the graph is wired."""
    queue = ApprovalQueue()
    record, _ = make_request(queue)
    for args in [
        (None, "t", "approve"),
        ("REQ-NOPE", "t", "approve"),
        (record.request_id, "wrong", "approve"),
        (record.request_id, "wrong", "nonsense"),
    ]:
        result = queue.decide(*args)
        assert result.request_id == NO_MATCH


def test_a_refusal_decision_is_recorded_not_silently_dropped():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    result = queue.decide(record.request_id, token, "refuse")
    assert result.ok
    assert result.state is ApprovalState.REFUSED
    assert not result.approved


def test_every_refusal_names_its_reason():
    queue = ApprovalQueue()
    result = queue.decide("REQ-NOPE", "t", "approve")
    assert result.reason is not None
    assert result.message


def test_an_expired_request_leaves_the_pending_list():
    queue = ApprovalQueue()
    record, token = make_request(queue)
    later = datetime.now(timezone.utc) + timedelta(hours=73)
    queue.decide(record.request_id, token, "approve", at=later)
    assert record not in queue.pending()


def test_the_plaintext_token_is_never_stored():
    """A store dump must not contain a usable token."""
    queue = ApprovalQueue()
    record, token = make_request(queue)
    stored = queue.get(record.request_id)
    assert token not in stored._token_hash
    assert stored._token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_a_wrong_token_is_distinguished_from_a_consumed_one():
    """Both refuse, and each names the reason a reader would need to debug it."""
    queue = ApprovalQueue()
    record, token = make_request(queue)
    queue.decide(record.request_id, token, "approve")

    consumed = queue.decide(record.request_id, token, "approve")
    assert consumed.reason is RefusalReason.ALREADY_DECIDED

    wrong = queue.decide(record.request_id, "some-other-token", "approve")
    assert wrong.reason is RefusalReason.WRONG_TOKEN
