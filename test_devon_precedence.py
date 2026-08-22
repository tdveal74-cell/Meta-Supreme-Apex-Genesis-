"""Tests for the precedence doctrine, including the failures that produced it."""

from datetime import date

from services.devon.precedence import (
    Candidate,
    Outcome,
    Signal,
    establish_precedence,
    live_tree,
    resolve,
)

TODAY = date(2026, 8, 22)


def test_filename_date_is_the_first_signal():
    candidate = Candidate(name="SYS_DOC_thing_v1_2026-08-20.md", modified_time="2026-01-01")
    resolved = establish_precedence(candidate, TODAY)
    assert resolved.signal is Signal.FILENAME_DATE
    assert resolved.established_date == date(2026, 8, 20)


def test_falls_through_to_document_date_then_modified_time():
    candidate = Candidate(name="notes.md", document_date="2026-08-15", modified_time="2026-08-01")
    resolved = establish_precedence(candidate, TODAY)
    assert resolved.signal is Signal.DOCUMENT_DATE

    candidate = Candidate(name="notes.md", modified_time="2026-08-01")
    resolved = establish_precedence(candidate, TODAY)
    assert resolved.signal is Signal.MODIFIED_TIME


def test_a_future_date_is_not_a_date():
    """Dating a file forward so it sorts to the top does not work."""
    candidate = Candidate(
        name="SYS_DOC_thing_v1_2027-01-14.md", modified_time="2026-08-01"
    )
    resolved = establish_precedence(candidate, TODAY)
    assert resolved.future_dated
    assert resolved.signal is Signal.MODIFIED_TIME
    assert resolved.established_date == date(2026, 8, 1)
    assert any("Future dated" in note for note in resolved.notes)


def test_most_recent_means_closest_to_today():
    near = Candidate(name="SYS_DOC_a_v1_2026-08-21.md")
    far = Candidate(name="SYS_DOC_a_v2_2026-01-01.md")
    ruling = resolve([near, far], today=TODAY)
    assert ruling.outcome is Outcome.SUPERSEDE
    assert ruling.winner.name == near.name


def test_future_dated_candidate_does_not_win():
    """One file misdated 2027 must not win every comparison it enters."""
    misdated = Candidate(name="SYS_DOC_a_v1_2027-01-14.md")
    real = Candidate(name="SYS_DOC_a_v2_2026-08-21.md")
    ruling = resolve([misdated, real], today=TODAY)
    assert "future-dated" in ruling.refusal_codes
    assert ruling.winner.name == real.name


def test_the_forty_seven_byte_case_is_refused():
    """A stub looks exactly like a legitimate new version to a date comparison."""
    stub = Candidate(name="SYS_DOC_a_v2_2026-08-21.md", size_bytes=47)
    real = Candidate(name="SYS_DOC_a_v1_2026-08-01.md", size_bytes=11204)
    ruling = resolve([stub, real], today=TODAY)
    assert ruling.outcome is Outcome.REFUSED
    assert "winner-drastically-smaller" in ruling.refusal_codes
    assert "47 bytes against 11204 bytes" in " ".join(ruling.reasons)


def test_a_trivially_small_loser_does_not_trigger_the_size_guard():
    tiny = Candidate(name="SYS_DOC_a_v1_2026-08-01.md", size_bytes=40)
    newer = Candidate(name="SYS_DOC_a_v2_2026-08-21.md", size_bytes=200)
    ruling = resolve([tiny, newer], today=TODAY)
    assert "winner-drastically-smaller" not in ruling.refusal_codes


def test_protected_files_are_never_auto_superseded():
    protected = Candidate(name="SYS_PROOF_codex-draft_v1_2026-07-28_EVIDENCE.md")
    newer = Candidate(name="SYS_PROOF_codex-draft_v2_2026-08-21.md")
    ruling = resolve([protected, newer], today=TODAY)
    assert "protected-superseded" in ruling.refusal_codes
    assert "Keep both" in " ".join(ruling.reasons)


def test_archive_counts_as_protected():
    archived = Candidate(name="SYS_DOC_a_v1_2026-07-01.md", parent_path="4. Archive/old")
    newer = Candidate(name="SYS_DOC_a_v2_2026-08-21.md")
    ruling = resolve([archived, newer], today=TODAY)
    assert "protected-superseded" in ruling.refusal_codes


def test_canon_is_never_resolved_unilaterally():
    a = Candidate(name="TSWS_CANON_bible_v2_2026-08-01.md", is_canon=True)
    b = Candidate(name="TSWS_CANON_bible_v3_2026-08-21.md")
    ruling = resolve([a, b], today=TODAY)
    assert "canon" in ruling.refusal_codes
    assert "studio-canon-intake" in " ".join(ruling.reasons)


def test_ambiguous_date_refuses_rather_than_falling_back():
    """Never fall back to alphabetical, file size, or read order."""
    a = Candidate(name="thing.md")
    b = Candidate(name="other.md")
    ruling = resolve([a, b], today=TODAY)
    assert "ambiguous-date" in ruling.refusal_codes


def test_a_load_bearing_disagreement_is_a_conflict_not_a_supersession():
    """Recency does not settle a contradiction. The newer one may be wrong."""
    a = Candidate(name="SYS_DOC_a_v1_2026-08-01.md", size_bytes=1000)
    b = Candidate(name="SYS_DOC_a_v2_2026-08-21.md", size_bytes=1100)
    ruling = resolve([a, b], today=TODAY, disagrees_on_load_bearing=True)
    assert ruling.outcome is Outcome.CONFLICT
    assert not ruling.auto_resolvable


def test_conflict_row_carries_concrete_evidence():
    stub = Candidate(name="SYS_DOC_a_v2_2026-08-21.md", size_bytes=47, drive_id="abc")
    real = Candidate(name="SYS_DOC_a_v1_2026-08-01.md", size_bytes=11204, drive_id="def")
    row = resolve([stub, real], today=TODAY).conflict_row()
    assert row["status"] == "Open"
    assert row["table_id"] == "tblbenoy1QF9KAftn"
    assert row["base_id"] == "app28z7XnKzjfTXwc"
    assert any("47 bytes" in e for e in row["evidence"])


def test_single_candidate_resolves_trivially():
    ruling = resolve([Candidate(name="SYS_DOC_a_v1_2026-08-21.md")], today=TODAY)
    assert ruling.outcome is Outcome.SUPERSEDE
    assert ruling.losers == []


def test_live_tree_picks_the_tree_holding_the_newest_content():
    trees = {
        "abandoned": [Candidate(name="SYS_DOC_a_v1_2026-02-01.md")],
        "live": [Candidate(name="SYS_DOC_b_v1_2026-08-21.md")],
    }
    assert live_tree(trees, TODAY) == "live"


def test_live_tree_ignores_future_dated_files():
    """A file misdated 2027 must not make a dead tree look alive."""
    trees = {
        "dead": [Candidate(name="SYS_DOC_a_v1_2027-05-05.md")],
        "live": [Candidate(name="SYS_DOC_b_v1_2026-08-20.md")],
    }
    assert live_tree(trees, TODAY) == "live"
