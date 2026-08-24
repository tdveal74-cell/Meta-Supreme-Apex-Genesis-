"""Offline tests for effect receipt helpers.

Database-fenced record_intent / record_receipt / find_orphan_intents are
exercised by the PostgreSQL suite once the runtime wiring lands. These tests
prove the pure helpers used by that path.
"""

from __future__ import annotations

from app.services.agent_effect_receipts import arguments_hash, new_intent_id


def test_arguments_hash_is_stable_for_same_payload() -> None:
    a = {"command": "ls", "cwd": "/tmp"}
    b = {"cwd": "/tmp", "command": "ls"}  # different key order
    assert arguments_hash(a) == arguments_hash(b)


def test_arguments_hash_changes_when_values_change() -> None:
    a = {"command": "ls"}
    b = {"command": "pwd"}
    assert arguments_hash(a) != arguments_hash(b)


def test_new_intent_id_has_prefix_and_is_unique() -> None:
    first = new_intent_id()
    second = new_intent_id()
    assert first.startswith("INT-")
    assert second.startswith("INT-")
    assert first != second
