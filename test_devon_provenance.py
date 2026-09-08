"""The provenance doctrine, proved without a database.

``services.devon.provenance`` hashes, chains, verifies and signs. These tests
walk every break the verifier is supposed to name and prove the signature
holds only over the exact text it was issued for. The database half (the
append-only triggers, the writer applying this on every row) is proved in
``test_live_state_ledger_provenance.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.devon import provenance

INTENT = "3d2c0b8a-1c2e-4f5a-9b6d-7e8f9a0b1c2d"
KEY = "a-test-signing-key-that-is-long-enough-000000"


def _chain(names, *, start=None):
    """Build a well formed chain the way the writer does, one link at a time."""
    start = start or datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
    links = []
    prev = provenance.GENESIS
    for index, name in enumerate(names, start=1):
        occurred = provenance.format_time(start + timedelta(milliseconds=index))
        payload = {"step": index, "name": name}
        digest = provenance.event_hash(
            prev_hash=prev,
            intent_id=INTENT,
            sequence_no=index,
            name=name,
            action_id=None,
            payload=payload,
            occurred_at=occurred,
        )
        links.append(
            provenance.ChainLink(
                sequence_no=index,
                name=name,
                prev_hash=prev,
                hash=digest,
                action_id=None,
                payload=payload,
                occurred_at=occurred,
            )
        )
        prev = digest
    return links


def _replace(link, **changes):
    fields = {
        "sequence_no": link.sequence_no,
        "name": link.name,
        "prev_hash": link.prev_hash,
        "hash": link.hash,
        "action_id": link.action_id,
        "payload": link.payload,
        "occurred_at": link.occurred_at,
    }
    fields.update(changes)
    return provenance.ChainLink(**fields)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def test_the_same_material_always_hashes_the_same_and_key_order_does_not_matter():
    common = dict(
        prev_hash=provenance.GENESIS,
        intent_id=INTENT,
        sequence_no=1,
        name="INTENT_RECEIVED",
        action_id=None,
        occurred_at="2026-09-08T12:00:00.000000+00:00",
    )
    first = provenance.event_hash(payload={"a": 1, "b": [1, 2]}, **common)
    second = provenance.event_hash(payload={"b": [1, 2], "a": 1}, **common)
    assert first == second
    assert len(first) == 64


def test_every_field_of_the_material_changes_the_hash():
    base = dict(
        prev_hash=provenance.GENESIS,
        intent_id=INTENT,
        sequence_no=1,
        name="INTENT_RECEIVED",
        action_id=None,
        payload={"channel": "chat_voice"},
        occurred_at="2026-09-08T12:00:00.000000+00:00",
    )
    reference = provenance.event_hash(**base)
    for key, value in (
        ("prev_hash", "ab" * 32),
        ("intent_id", INTENT[:-1] + "e"),
        ("sequence_no", 2),
        ("name", "CONTEXT_LOADED"),
        ("action_id", "ACT-1"),
        ("payload", {"channel": "email"}),
        ("occurred_at", "2026-09-08T12:00:00.000001+00:00"),
    ):
        changed = provenance.event_hash(**{**base, key: value})
        assert changed != reference, key


def test_a_payload_json_cannot_carry_is_refused_not_coerced():
    with pytest.raises(TypeError):
        provenance.canonical({"when": datetime(2026, 9, 8, tzinfo=timezone.utc)})


def test_a_naive_datetime_cannot_be_hashed():
    with pytest.raises(ValueError, match="naive"):
        provenance.format_time(datetime(2026, 9, 8, 12, 0, 0))


def test_format_time_is_utc_to_the_microsecond():
    eastern = timezone(timedelta(hours=-5))
    moment = datetime(2026, 9, 8, 7, 0, 0, 123456, tzinfo=eastern)
    assert provenance.format_time(moment) == "2026-09-08T12:00:00.123456+00:00"


# ---------------------------------------------------------------------------
# Verifying the chain
# ---------------------------------------------------------------------------

def test_a_well_formed_chain_is_intact_and_complete():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
    verdict = provenance.verify_chain(INTENT, links)
    assert verdict.intact
    assert verdict.complete
    assert verdict.length == 3
    assert verdict.hashed == 3
    assert verdict.unhashed == 0
    assert verdict.head_hash == links[-1].hash
    assert verdict.findings == ()


def test_an_empty_chain_is_intact_but_not_complete():
    verdict = provenance.verify_chain(INTENT, [])
    assert verdict.intact
    assert not verdict.complete
    assert verdict.head_hash == provenance.GENESIS


def test_an_altered_payload_is_named_by_sequence_number():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
    links[1] = _replace(links[1], payload={"step": 2, "name": "something else"})
    verdict = provenance.verify_chain(INTENT, links)
    assert not verdict.intact
    assert any("sequence 2" in f and "altered" in f for f in verdict.findings)


def test_a_broken_link_is_named():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED"])
    # Recompute the second hash over a foreign prev_hash so its own material is
    # consistent and only the link is wrong.
    foreign = "cd" * 32
    rehashed = provenance.event_hash(
        prev_hash=foreign,
        intent_id=INTENT,
        sequence_no=2,
        name="CONTEXT_LOADED",
        action_id=None,
        payload=links[1].payload,
        occurred_at=links[1].occurred_at,
    )
    links[1] = _replace(links[1], prev_hash=foreign, hash=rehashed)
    verdict = provenance.verify_chain(INTENT, links)
    assert not verdict.intact
    assert any("does not link" in f for f in verdict.findings)
    assert not any("altered" in f for f in verdict.findings)


def test_a_missing_event_shows_as_a_gap_and_a_broken_link():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
    del links[1]
    verdict = provenance.verify_chain(INTENT, links)
    assert not verdict.intact
    assert any("missing or out of order" in f for f in verdict.findings)
    assert any("does not link" in f for f in verdict.findings)


def test_a_reordered_chain_is_refused():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
    links[1], links[2] = links[2], links[1]
    verdict = provenance.verify_chain(INTENT, links)
    assert not verdict.intact
    assert len(verdict.findings) >= 2


def test_a_wrong_intent_id_breaks_every_hashed_link():
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED"])
    verdict = provenance.verify_chain(INTENT[:-1] + "e", links)
    assert not verdict.intact
    assert sum("altered" in f for f in verdict.findings) == 2


def test_rows_from_before_the_chain_are_counted_not_condemned():
    """A pre 019 row has an empty hash. The chain restarts after it."""
    old = provenance.ChainLink(
        sequence_no=1,
        name="INTENT_RECEIVED",
        prev_hash="",
        hash="",
        action_id=None,
        payload={},
        occurred_at="2026-08-26T00:00:00.000000+00:00",
    )
    fresh = _chain(["CONTEXT_LOADED"])[0]
    fresh = _replace(fresh, sequence_no=2)
    fresh = _replace(
        fresh,
        hash=provenance.event_hash(
            prev_hash=provenance.GENESIS,
            intent_id=INTENT,
            sequence_no=2,
            name="CONTEXT_LOADED",
            action_id=None,
            payload=fresh.payload,
            occurred_at=fresh.occurred_at,
        ),
    )
    verdict = provenance.verify_chain(INTENT, [old, fresh])
    assert verdict.intact
    assert not verdict.complete
    assert verdict.unhashed == 1
    assert verdict.hashed == 1


def test_the_verdict_serialises_with_its_algorithm():
    verdict = provenance.verify_chain(INTENT, _chain(["INTENT_RECEIVED"]))
    rendered = verdict.to_dict()
    assert rendered["algorithm"] == "sha256"
    assert rendered["chain_version"] == provenance.CHAIN_VERSION
    assert rendered["intact"] is True


# ---------------------------------------------------------------------------
# Signing the receipt
# ---------------------------------------------------------------------------

def _digest(**overrides):
    fields = dict(
        intent_id=INTENT,
        head_hash="ab" * 32,
        chain_length=5,
        what_happened="filed the capture",
        verification="read the row back",
        provenance="ledger writer",
        artifacts=["estate://x"],
        learned="",
        next_steps="",
        issued_at="2026-09-08T12:00:01.000000+00:00",
    )
    fields.update(overrides)
    return provenance.receipt_digest(**fields)


def test_a_signature_verifies_under_its_key_and_under_no_other():
    digest = _digest()
    signature = provenance.sign(digest, KEY)
    assert len(signature) == 64
    assert provenance.verify_signature(digest, signature, KEY)
    assert not provenance.verify_signature(digest, signature, KEY + "x")
    assert not provenance.verify_signature(digest, "", KEY)
    assert not provenance.verify_signature(digest, signature, "")


def test_changing_any_receipt_field_breaks_the_signature():
    signature = provenance.sign(_digest(), KEY)
    for key, value in (
        ("head_hash", "cd" * 32),
        ("chain_length", 6),
        ("what_happened", "filed the capture twice"),
        ("verification", "did not read it back"),
        ("provenance", "someone else"),
        ("artifacts", []),
        ("learned", "a lesson"),
        ("next_steps", "one more"),
        ("issued_at", "2026-09-08T12:00:01.000001+00:00"),
    ):
        assert not provenance.verify_signature(_digest(**{key: value}), signature, KEY), key


def test_signing_with_an_empty_key_is_refused():
    with pytest.raises(ValueError, match="empty key"):
        provenance.sign(_digest(), "")


def test_the_key_id_names_the_key_without_revealing_it():
    identifier = provenance.key_id(KEY)
    assert len(identifier) == 16
    assert identifier == provenance.key_id(KEY)
    assert identifier != provenance.key_id(KEY + "x")
    assert KEY not in identifier
    assert provenance.key_id("") == ""


def test_the_module_declares_where_it_came_from():
    assert provenance.SOURCE["supplied_by"] == "Tee"
    assert provenance.SOURCE["file_as"].startswith("SYS_SPEC_")


# ---------------------------------------------------------------------------
# What the 2026-09-08 gauntlet added
# ---------------------------------------------------------------------------

def test_nan_and_infinity_are_refused_at_the_door():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            provenance.canonical({"v": value})
        assert "cannot represent" in (provenance.check_payload({"v": value}) or "")


def test_a_lone_surrogate_is_refused_by_name():
    problem = provenance.check_payload({"text": "bad \udcff text"})
    assert problem is not None
    assert "UTF-8" in problem


def test_a_clean_payload_passes_the_door():
    assert provenance.check_payload({"n": 1e16, "z": -0.0, "s": "caf\u00e9", "l": [1, {"k": None}]}) is None


def test_an_unhashed_row_after_hashed_rows_is_a_break_not_a_grace():
    """The pre 019 grace is a prefix. A planted empty hash behind hashed
    rows was written around the writer and the verifier says so."""
    links = _chain(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
    planted = _replace(links[2], prev_hash="", hash="")
    verdict = provenance.verify_chain(INTENT, [links[0], links[1], planted])
    assert not verdict.intact
    assert verdict.unhashed == 1
    assert any("written around the writer" in f for f in verdict.findings)


def test_the_receipt_key_is_derived_from_the_secret_and_is_not_the_secret():
    derived = provenance.derive_receipt_key(KEY)
    assert len(derived) == 64
    assert derived != KEY
    assert derived == provenance.derive_receipt_key(KEY)
    assert derived != provenance.derive_receipt_key(KEY + "x")
    with pytest.raises(ValueError, match="empty secret"):
        provenance.derive_receipt_key("")


def test_the_ring_finds_the_key_that_signed_and_reports_none_otherwise():
    digest = _digest()
    old_key = "an-older-receipt-key-000000000000000000000000"
    signature = provenance.sign(digest, old_key)
    assert provenance.find_signing_key(digest, signature, [KEY, old_key]) == old_key
    assert provenance.find_signing_key(digest, signature, [KEY]) is None
    assert provenance.find_signing_key(digest, signature, ["", old_key]) == old_key
    assert provenance.find_signing_key(digest, "", [KEY, old_key]) is None
