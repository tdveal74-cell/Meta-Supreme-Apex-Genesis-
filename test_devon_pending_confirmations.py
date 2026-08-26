"""Confirmations the server remembers, so a "yes" cannot be manufactured.

The property under test is narrow and load bearing: a confirmation names an
action DEVON proposed, not one the client chose. The old shape -- a SHA-256 of
the turn id, tool name, and arguments -- was a hash of public inputs, which any
caller could compute for any call it liked. That turned "confirm this" into an
unmetered tool-invocation API for anything holding a session cookie.

So the handle here is random, the action is stored, and the claim is single use.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from services.agent_runtime.pending import (
    MAX_PENDING,
    PendingConfirmationRegistry,
)

OWNER = "conv-1"
ACTOR = "tee"


def offer(registry: PendingConfirmationRegistry, **overrides):
    payload = {
        "turn_id": "TURN-1",
        "owner": OWNER,
        "actor": ACTOR,
        "tool": "soul.commit",
        "arguments": {"claim": "x"},
        "observations": (("ledger.read", "8 jobs"),),
        "message": "remember that",
    }
    payload.update(overrides)
    return registry.offer(**payload)


def test_a_handle_is_random_and_not_derivable_from_the_call() -> None:
    registry = PendingConfirmationRegistry()
    first = offer(registry)
    second = offer(registry)

    # Identical calls, different handles. A client cannot compute one for an
    # action DEVON never proposed, which is the whole point.
    assert first.handle != second.handle
    assert "soul.commit" not in first.handle


def test_claiming_returns_the_stored_call_not_a_supplied_one() -> None:
    registry = PendingConfirmationRegistry()
    record = offer(registry)

    claimed = registry.claim(record.handle, owner=OWNER, actor=ACTOR)

    assert claimed is not None
    assert claimed.tool == "soul.commit"
    assert claimed.arguments == {"claim": "x"}
    assert claimed.turn_id == "TURN-1"
    # The work that led to the question comes back too, so the resumed turn does
    # not re-run the steps that preceded it.
    assert claimed.observations == (("ledger.read", "8 jobs"),)
    assert claimed.message == "remember that"


def test_a_handle_is_spent_on_use() -> None:
    registry = PendingConfirmationRegistry()
    record = offer(registry)

    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is not None
    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is None


def test_a_handle_does_not_travel_to_another_conversation() -> None:
    registry = PendingConfirmationRegistry()
    record = offer(registry)

    assert registry.claim(record.handle, owner="conv-2", actor=ACTOR) is None
    # Refused, and NOT consumed: the rightful owner can still answer.
    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is not None


def test_a_handle_does_not_travel_to_another_user() -> None:
    registry = PendingConfirmationRegistry()
    record = offer(registry)

    assert registry.claim(record.handle, owner=OWNER, actor="someone-else") is None
    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is not None


def test_an_expired_question_lapses_rather_than_waiting() -> None:
    """An inline question is asked of someone reading the stream right now.

    If he has gone, the right outcome is that DEVON asks again -- not that a
    stale yes lands on an effect twenty minutes later. The 72-hour instrument
    for an absent human is the approval card, and this is deliberately not it.
    """
    registry = PendingConfirmationRegistry()
    record = offer(registry)
    stale = replace(record, expires_at=record.created_at - timedelta(seconds=1))
    registry._pending[record.handle] = stale  # noqa: SLF001 - clock control

    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is None


def test_an_unknown_handle_is_refused_without_saying_why() -> None:
    registry = PendingConfirmationRegistry()
    offer(registry)

    # Wrong owner, wrong user, unknown handle and expired all return None. A
    # miss that distinguished them would be an oracle for which confirmations
    # are outstanding.
    assert registry.claim("CONFIRM-nope", owner=OWNER, actor=ACTOR) is None
    assert registry.claim("", owner=OWNER, actor=ACTOR) is None
    assert registry.claim(None, owner=OWNER, actor=ACTOR) is None


def test_discarding_a_question_leaves_nothing_to_answer() -> None:
    registry = PendingConfirmationRegistry()
    record = offer(registry)

    registry.discard(record.handle)
    registry.discard(record.handle)  # twice is safe

    assert registry.claim(record.handle, owner=OWNER, actor=ACTOR) is None


def test_a_question_needs_a_turn_an_owner_and_a_tool() -> None:
    registry = PendingConfirmationRegistry()
    with pytest.raises(ValueError):
        offer(registry, turn_id="  ")
    with pytest.raises(ValueError):
        offer(registry, owner="")
    with pytest.raises(ValueError):
        offer(registry, tool="")


def test_unanswered_questions_do_not_grow_without_bound() -> None:
    registry = PendingConfirmationRegistry()
    for index in range(MAX_PENDING + 20):
        offer(registry, turn_id=f"TURN-{index}")

    assert registry.outstanding <= MAX_PENDING


def test_the_arguments_are_copied_not_aliased() -> None:
    """A caller mutating its own dict afterwards must not move the target."""
    registry = PendingConfirmationRegistry()
    args = {"claim": "x"}
    record = offer(registry, arguments=args)
    args["claim"] = "something else entirely"

    claimed = registry.claim(record.handle, owner=OWNER, actor=ACTOR)
    assert claimed.arguments == {"claim": "x"}
