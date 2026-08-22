"""Tests for the DEVON receipt, both formats."""

from datetime import date

import pytest

from services.devon import receipts
from services.devon.areas import AreaError

TODAY = date(2026, 8, 22)

V1_SAMPLE = """
=== DEVON RECEIPT v1 ===
DATE: 2026-08-22
PLATFORM: ChatGPT
AREA: Podcast
TITLE: Vespera jewelry ruled to silver at pack cut
SUMMARY: Reviewed the casting grid against palette law. Gold was reserved for
the bridge between the two, so the drop earrings conflicted.
DECIDED: D18 ruled, Vespera double jewelry goes silver at pack cut
BUILT: none
OPEN: D10 grid md5 still unverified on device
NEXT: Verify the grid hash before the pack cut
CANON: D18 filed
VERIFY: byte count matched at 383953 but the hash was never computed
=== END RECEIPT ===
"""

STANDING_SAMPLE = """
DEVON RECEIPT
platform: Claude
date: 2026-08-22
area: Systems
files_opened: SYS_SPEC_filing-laws-for-llms_v3, SYS_INDEX_master-directory_v6
summary: Compiled the filing laws into executable checks.
decisions: Filing laws are enforced in code rather than prose
open threads: The capture endpoint is still unauthenticated
artifacts: services/devon/filing.py
unverified: NONE
"""


def test_detects_both_formats():
    assert receipts.detect_format(V1_SAMPLE) is receipts.ReceiptFormat.V1_BLOCK
    assert receipts.detect_format(STANDING_SAMPLE) is receipts.ReceiptFormat.STANDING
    assert receipts.detect_format("just some prose") is None


def test_parsing_a_non_receipt_raises():
    with pytest.raises(receipts.ReceiptError, match="No DEVON receipt found"):
        receipts.parse_receipt("hello there")


def test_parses_the_v1_block():
    receipt = receipts.parse_receipt(V1_SAMPLE)
    assert receipt.date == "2026-08-22"
    assert receipt.platform == "ChatGPT"
    assert receipt.areas == ["Podcast"]
    assert "silver at pack cut" in receipt.title
    assert receipt.decided == ["D18 ruled, Vespera double jewelry goes silver at pack cut"]
    assert receipt.next_action.startswith("Verify the grid hash")


def test_multiline_summary_does_not_swallow_the_next_field():
    """The failure mode that makes naive receipt parsers drop DECIDED."""
    receipt = receipts.parse_receipt(V1_SAMPLE)
    assert "bridge between the two" in receipt.summary
    assert receipt.decided != []
    assert "DECIDED" not in receipt.summary


def test_parses_the_standing_format():
    receipt = receipts.parse_receipt(STANDING_SAMPLE)
    assert receipt.platform == "Claude"
    assert receipt.areas == ["Systems"]
    assert len(receipt.files_opened) == 1
    assert receipt.unverified == ["NONE"]


def test_a_valid_receipt_validates():
    assert receipts.is_valid(receipts.parse_receipt(V1_SAMPLE), TODAY)
    assert receipts.is_valid(receipts.parse_receipt(STANDING_SAMPLE), TODAY)


def test_an_invented_area_is_refused_loudly():
    """The parser rejects rather than dropping the row into an untagged void."""
    bad = V1_SAMPLE.replace("AREA: Podcast", "AREA: Business")
    problems = receipts.validate(receipts.parse_receipt(bad), TODAY)
    area_errors = [p for p in problems if p.field_name == "area" and p.severity == "error"]
    assert area_errors
    assert "index fractures" in area_errors[0].message


def test_files_opened_is_load_bearing_in_the_standing_format():
    without = STANDING_SAMPLE.replace(
        "files_opened: SYS_SPEC_filing-laws-for-llms_v3, SYS_INDEX_master-directory_v6\n", ""
    )
    problems = receipts.validate(receipts.parse_receipt(without), TODAY)
    assert any(p.field_name == "files_opened" and p.severity == "error" for p in problems)


def test_unverified_is_load_bearing_in_the_standing_format():
    without = STANDING_SAMPLE.replace("unverified: NONE\n", "")
    problems = receipts.validate(receipts.parse_receipt(without), TODAY)
    assert any(p.field_name == "unverified" and p.severity == "error" for p in problems)


def test_open_threads_are_required_because_a_success_only_log_lies():
    without = STANDING_SAMPLE.replace(
        "open threads: The capture endpoint is still unauthenticated\n", ""
    )
    problems = receipts.validate(receipts.parse_receipt(without), TODAY)
    assert any(p.field_name == "open" and "lies by omission" in p.message for p in problems)


def test_a_future_dated_receipt_is_refused():
    future = STANDING_SAMPLE.replace("date: 2026-08-22", "date: 2027-01-01")
    problems = receipts.validate(receipts.parse_receipt(future), TODAY)
    assert any(p.field_name == "date" and "future" in p.message for p in problems)


def test_an_unknown_platform_is_refused():
    bad = STANDING_SAMPLE.replace("platform: Claude", "platform: Copilot")
    problems = receipts.validate(receipts.parse_receipt(bad), TODAY)
    assert any(p.field_name == "platform" for p in problems)


def test_a_vague_title_warns():
    vague = V1_SAMPLE.replace(
        "TITLE: Vespera jewelry ruled to silver at pack cut",
        "TITLE: discussion about the vault",
    )
    problems = receipts.validate(receipts.parse_receipt(vague), TODAY)
    assert any(p.field_name == "title" and "container" in p.message for p in problems)


def test_require_valid_raises_listing_every_error():
    bad = STANDING_SAMPLE.replace("area: Systems", "area: Business")
    with pytest.raises(receipts.ReceiptError, match="Receipt refused"):
        receipts.require_valid(receipts.parse_receipt(bad), TODAY)


def test_v1_round_trip_preserves_fields():
    original = receipts.parse_receipt(V1_SAMPLE)
    reparsed = receipts.parse_receipt(receipts.render_v1(original))
    assert reparsed.date == original.date
    assert reparsed.areas == original.areas
    assert reparsed.decided == original.decided
    assert reparsed.next_action == original.next_action


def test_standing_round_trip_preserves_the_load_bearing_fields():
    original = receipts.parse_receipt(STANDING_SAMPLE)
    reparsed = receipts.parse_receipt(receipts.render_standing(original))
    assert reparsed.files_opened == original.files_opened
    assert reparsed.unverified == original.unverified


def test_normalize_areas_unifies_the_two_vocabularies():
    """A receipt tagged TSWS and one tagged Podcast must land on one row value."""
    receipt = receipts.parse_receipt(STANDING_SAMPLE.replace("area: Systems", "area: TSWS"))
    receipts.normalize_areas(receipt)
    assert receipt.areas == ["Podcast"]


def test_normalize_areas_refuses_an_invented_area():
    receipt = receipts.parse_receipt(STANDING_SAMPLE.replace("area: Systems", "area: Work"))
    with pytest.raises(AreaError):
        receipts.normalize_areas(receipt)


def test_produced_a_decision_detects_none():
    receipt = receipts.parse_receipt(STANDING_SAMPLE.replace(
        "decisions: Filing laws are enforced in code rather than prose", "decisions: none"
    ))
    assert not receipt.produced_a_decision
