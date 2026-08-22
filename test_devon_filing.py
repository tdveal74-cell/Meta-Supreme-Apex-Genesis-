"""Tests for the eight filing laws."""

from datetime import date

from services.devon import filing
from services.devon.filing import (
    ChangeKind,
    DuplicateClass,
    FileFacts,
    SiblingRead,
    Verdict,
    WriteRequest,
    check_write,
)

TODAY = date(2026, 8, 22)


def test_there_are_eight_laws_each_naming_its_failure():
    assert len(filing.LAWS) == 8
    assert [law.number for law in filing.LAWS] == list(range(1, 9))
    for law in filing.LAWS:
        assert law.failure_prevented.strip()


# -- Law 1 -------------------------------------------------------------------


def test_law1_refuses_a_write_to_root():
    result = filing.law1_check_destination("root")
    assert result.verdict is Verdict.REFUSE
    assert "Root holds only Devon 2nd Brain" in result.message


def test_law1_allows_a_write_inside_the_tree():
    assert filing.law1_check_destination("1wvKmGuaWQTxOT6Q8XQCU3Zv825VvbgdO").allowed


# -- Law 2 -------------------------------------------------------------------


def test_law2_refuses_a_new_version_without_listing_the_folder():
    result = filing.law2_require_sibling_read(writing_new_version=True, evidence=None)
    assert result.verdict is Verdict.REFUSE
    assert "list the folder" in result.message


def test_law2_refuses_when_the_newest_sibling_was_found_but_not_read():
    evidence = SiblingRead(
        folder_listed=True,
        siblings_seen=("a_v1.md", "a_v2.md"),
        newest_sibling="a_v2.md",
        newest_sibling_read=False,
    )
    result = filing.law2_require_sibling_read(True, evidence)
    assert result.verdict is Verdict.REFUSE
    assert "may already be the merge" in result.message


def test_law2_allows_once_the_newest_sibling_is_read():
    evidence = SiblingRead(
        folder_listed=True, newest_sibling="a_v2.md", newest_sibling_read=True
    )
    assert filing.law2_require_sibling_read(True, evidence).allowed


def test_law2_does_not_gate_a_first_write():
    assert filing.law2_require_sibling_read(writing_new_version=False).allowed


# -- Law 3, the read-back ----------------------------------------------------


def test_law3_finds_a_payload_under_any_documented_key():
    for key in ("body", "data", "text", "content", "part", "fileContent"):
        result = filing.law3_validate_readback({key: "real content here"})
        assert result.ok
        assert result.value == "real content here"
        assert result.location == key


def test_law3_finds_a_nested_payload():
    result = filing.law3_validate_readback({"response": {"data": {"text": "nested value"}}})
    assert result.ok
    assert "text" in result.location


def test_law3_fails_loudly_on_an_empty_read():
    """A read that returns nothing is not a read."""
    result = filing.law3_validate_readback({"body": ""})
    assert not result.ok
    assert result.value is None


def test_law3_require_raises_rather_than_returning_an_empty_string():
    """Every content check silently passes against an empty string."""
    result = filing.law3_validate_readback({"body": ""})
    try:
        result.require()
        raise AssertionError("require() should have raised on an empty read")
    except ValueError as exc:
        assert "not a read" in str(exc)


def test_law3_handles_none_and_missing_payloads():
    assert not filing.law3_validate_readback(None).ok
    assert not filing.law3_validate_readback({}).ok
    assert not filing.law3_validate_readback({"unrelated": 42}).ok


def test_law3_searches_lists():
    result = filing.law3_validate_readback([{"body": ""}, {"body": "found it"}])
    assert result.ok
    assert result.value == "found it"


def test_law3_respects_a_minimum_length():
    assert not filing.law3_validate_readback({"body": "ab"}, min_length=10).ok
    assert filing.law3_validate_readback({"body": "a" * 20}, min_length=10).ok


# -- Law 4 -------------------------------------------------------------------


def test_law4_exact_duplicate_is_auto_trashable():
    a = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000, "2026-08-01T00:00:00Z")
    b = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000, "2026-08-02T00:00:00Z")
    kind, result = filing.law4_classify(a, b)
    assert kind is DuplicateClass.EXACT_DUPLICATE
    assert result.verdict is Verdict.ALLOW


def test_law4_a_twenty_five_byte_difference_is_a_distinct_version():
    a = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000)
    b = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1025)
    kind, result = filing.law4_classify(a, b)
    assert kind is DuplicateClass.DISTINCT_VERSION
    assert result.verdict is Verdict.NEEDS_RULING


def test_law4_version_label_governs_over_the_timestamp():
    a = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000)
    b = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000)
    kind, _ = filing.law4_classify(a, b)
    assert kind is DuplicateClass.EXACT_DUPLICATE


def test_law4_unknown_size_cannot_prove_a_duplicate():
    a = FileFacts("SYS_DOC_a_v1_2026-08-01.md", None)
    b = FileFacts("SYS_DOC_a_v1_2026-08-01.md", 1000)
    kind, result = filing.law4_classify(a, b)
    assert result.verdict is Verdict.NEEDS_RULING


def test_law4_different_names_are_unrelated():
    kind, _ = filing.law4_classify(FileFacts("a.md", 1), FileFacts("b.md", 1))
    assert kind is DuplicateClass.UNRELATED


# -- Law 5 -------------------------------------------------------------------


def test_law5_surfaces_warning_markers_before_anything_acts():
    flagged = filing.law5_filename_warnings(
        [
            "SYS_DOC_a_v1_2026-08-01.md",
            "SYS_DOC_b_v1_2026-08-01_KEEP.md",
            "SUPERSEDED_SYS_DOC_c_v1_2026-08-01.md",
            "SYS_DOC_d_v1_2026-08-01_ruling-owed.md",
        ]
    )
    names = {name for name, _ in flagged}
    assert "SYS_DOC_b_v1_2026-08-01_KEEP.md" in names
    assert "SUPERSEDED_SYS_DOC_c_v1_2026-08-01.md" in names
    assert "SYS_DOC_d_v1_2026-08-01_ruling-owed.md" in names
    assert "SYS_DOC_a_v1_2026-08-01.md" not in names


# -- Law 6 -------------------------------------------------------------------


def test_law6_retires_by_renaming_with_a_prefix():
    retirement = filing.law6_retire("SYS_SPEC_thing_v1_2026-08-01.md")
    assert retirement.new_name.startswith("SUPERSEDED_")
    assert retirement.destination == "4. Archive"
    assert "never deleted" in retirement.note


def test_law6_strips_canonical_from_a_withdrawn_document():
    """CANONICAL never remains in the title of a document whose claim was withdrawn."""
    retirement = filing.law6_retire("TEE_MEMORY_CANONICAL_v1_2026-08-13.md")
    assert "CANONICAL" not in retirement.new_name
    assert "WITHDRAWN" in retirement.new_name


def test_law6_refuses_deletion_outright():
    result = filing.law6_refuse_deletion("anything.md")
    assert result.verdict is Verdict.REFUSE
    assert "permanent" in result.message


# -- Law 7 -------------------------------------------------------------------


def test_law7_names_a_dated_holding_folder():
    assert filing.law7_sweep_folder(TODAY) == "0. Inbox / ROOT SWEEP 2026-08-22"


def test_law7_refuses_a_holding_folder_that_outlived_its_session():
    result = filing.law7_check_holding_folder(date(2026, 8, 20), TODAY)
    assert result.verdict is Verdict.REFUSE
    assert "outlived its session" in result.message


def test_law7_allows_a_holding_folder_created_today():
    assert filing.law7_check_holding_folder(TODAY, TODAY).allowed


# -- Law 8 -------------------------------------------------------------------


def test_law8_substance_always_bumps():
    assert filing.law8_version_decision(ChangeKind.SUBSTANCE, False).allowed


def test_law8_correction_with_the_lane_fixes_in_place():
    result = filing.law8_version_decision(ChangeKind.CORRECTION, True)
    assert result.allowed
    assert "same file id" in result.message


def test_law8_correction_without_the_lane_must_not_bump():
    """Bumping per correction produced six directory versions in a single day."""
    result = filing.law8_version_decision(ChangeKind.CORRECTION, False, pending_corrections=3)
    assert result.verdict is Verdict.REFUSE
    assert "bump once" in result.message


# -- Aggregate ---------------------------------------------------------------


def test_check_write_refuses_a_root_write_with_a_bad_name():
    check = check_write(WriteRequest(filename="SKILL.md", parent_id="root"))
    assert not check.allowed
    assert "Law 1" in check.summary()
    assert check.naming_violations


def test_check_write_allows_a_clean_write():
    check = check_write(
        WriteRequest(
            filename="SYS_SPEC_devon-merge_v1_2026-08-22.md",
            parent_id="17chQD2DTfzbnZy2oGwiJxEk7PHvnstBp",
        )
    )
    assert check.allowed


def test_check_write_surfaces_folder_warnings_without_blocking():
    check = check_write(
        WriteRequest(
            filename="SYS_SPEC_devon-merge_v1_2026-08-22.md",
            parent_id="17chQD2DTfzbnZy2oGwiJxEk7PHvnstBp",
            folder_contents=("SYS_DOC_old_v1_2026-08-01_KEEP.md",),
        )
    )
    assert check.allowed
    assert check.folder_warnings
