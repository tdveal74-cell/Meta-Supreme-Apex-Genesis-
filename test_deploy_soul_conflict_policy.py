"""Behaviour tests for the Build 12 conflict policy in the soul service.

The first gate rule — any active match blocks — made merely adjacent rulings
a permanent veto on learning: the live close-out matched five real tee
rulings at scores 0.10-0.22 and every one of them parked the candidate with
a human. The policy under test bands matches by score instead: weak matches
(shared territory) may clear, adjacent and strong matches defer to a human,
and a strong match carrying prohibition language is labeled a conflict
outright. "clear" is only ever issued from a complete recall with both souls
read — a timeout, failure, or partial read stays requires_human whatever was
matched.

Run through a subprocess probe for the same reason test_deploy_soul.py uses
one: importing deploy/soul in-process would pin the vendored trimmed
`services` tree on sys.path for the rest of the pytest session.
"""

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"


@pytest.fixture(scope="module")
def probe():
    result = subprocess.run(
        [sys.executable, str(DEPLOY / "_conflict_selftest.py")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"the conflict policy could not be exercised:\n{result.stderr[-3000:]}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_live_close_out_shape_now_clears(probe):
    """Five real rulings at 0.10-0.22 are shared territory, not a conflict."""
    found = probe["weak_only"]
    assert found["complete"] is True
    assert found["conflict_status"] == "clear"
    assert found["bands"] == ["weak"] * 5
    assert "not a contradiction" in found["decision"]


def test_prohibition_language_in_a_weak_match_does_not_block(probe):
    """A weak match saying "never" is someone else's rule about someone
    else's territory; only strength makes prohibition language relevant."""
    found = probe["weak_only"]
    assert "r-boundary" in found["matched_ids"]  # the record carrying "never"
    assert found["conflict_status"] == "clear"


def test_an_adjacent_match_defers_to_a_human(probe):
    found = probe["adjacent"]
    assert found["conflict_status"] == "requires_human"
    assert "adjacent" in found["bands"]


def test_the_adjacent_band_starts_exactly_at_the_weak_line(probe):
    found = probe["adjacent_boundary"]
    assert found["bands"] == ["adjacent"]
    assert found["conflict_status"] == "requires_human"


def test_a_strong_match_defers_even_without_opposing_language(probe):
    found = probe["strong_no_cue"]
    assert found["bands"] == ["strong"]
    assert found["conflict_status"] == "requires_human"
    assert "ruled territory" in found["decision"]


def test_a_strong_prohibition_is_named_a_conflict(probe):
    found = probe["strong_cue"]
    assert found["conflict_status"] == "conflict"
    assert "must not" in found["decision"]


def test_the_strong_band_starts_exactly_at_the_declared_line(probe):
    found = probe["strong_boundary"]
    assert found["bands"] == ["strong"]
    assert found["conflict_status"] == "requires_human"


def test_a_typographic_apostrophe_still_reads_as_prohibition(probe):
    """Rulings pasted from a word processor carry U+2019, not ASCII '."""
    found = probe["strong_cue_typographic"]
    assert found["conflict_status"] == "conflict"
    assert "don't" in found["decision"]


def test_prohibition_in_an_adjacent_match_defers_but_is_not_a_conflict(probe):
    """Only strength makes prohibition language a conflict; an adjacent
    match with a cue is still just a human's call."""
    found = probe["adjacent_cue_is_not_a_conflict"]
    assert found["conflict_status"] == "requires_human"
    assert found["bands"] == ["adjacent"]


def test_a_strong_match_outranks_an_adjacent_one_in_the_decision(probe):
    found = probe["mixed_strong_and_adjacent"]
    assert found["conflict_status"] == "requires_human"
    assert "ruled territory" in found["decision"]


def test_a_scoreless_hit_cannot_count_toward_clear(probe):
    """A returned hit with no positive score is malformed upstream data,
    not a measured dissimilarity — it defers to a human."""
    found = probe["zero_score"]
    assert found["bands"] == ["unknown"]
    assert found["conflict_status"] == "requires_human"
    assert "no usable score" in found["decision"]


def test_a_superseded_ruling_cannot_block_however_strong(probe):
    """status:active is still binding: a superseded 0.90 hit is filtered
    before the policy ever sees it."""
    found = probe["superseded_strong_filtered"]
    assert found["matched_ids"] == ["r-live"]
    assert found["conflict_status"] == "clear"


def test_no_matches_still_clears(probe):
    found = probe["no_matches"]
    assert found["complete"] is True
    assert found["conflict_status"] == "clear"


def test_a_window_full_of_superseded_near_duplicates_cannot_clear(probe):
    """The active filter runs after retrieval, so superseded revisions
    spend window slots. A full window whose floor sits above the weak line
    could be hiding the live revision below the cutoff — that is not a
    clearance, it is a blind spot."""
    found = probe["saturated_window"]
    assert found["matched_ids"] == []
    assert found["complete"] is True
    assert found["conflict_status"] == "requires_human"
    assert "below the cutoff" in found["decision"]


def test_a_full_window_with_a_weak_floor_conceals_only_weaker_hits(probe):
    """Everything unretrieved scores at or below the window floor, so a
    weak floor proves nothing non-weak is hiding — the clear stands."""
    found = probe["saturated_window_weak_floor"]
    assert found["conflict_status"] == "clear"
    assert "r-old-top" not in found["matched_ids"]


def test_a_whitespace_padded_claim_is_refused_not_cleared(probe):
    """Eight spaces pass the schema's raw min_length, strip to nothing,
    and an empty recall would mint a 'clear' receipt with zero records
    read. The endpoint refuses instead."""
    assert probe["whitespace_claim"] == 422


def test_an_unexpected_failure_stays_requires_human(probe):
    found = probe["unexpected_error"]
    assert found["complete"] is False
    assert found["conflict_status"] == "requires_human"
    assert "unexpected" in found["notes"]


def test_a_timeout_stays_requires_human(probe):
    found = probe["timeout"]
    assert found["complete"] is False
    assert found["conflict_status"] == "requires_human"
    assert "timed out" in found["notes"]


def test_a_provider_failure_stays_requires_human(probe):
    found = probe["provider_error"]
    assert found["complete"] is False
    assert found["conflict_status"] == "requires_human"


def test_a_recall_that_read_nothing_cannot_clear(probe):
    found = probe["failed_both"]
    assert found["complete"] is False
    assert found["conflict_status"] == "requires_human"


def test_a_partial_recall_cannot_clear(probe):
    """Weak evidence from one soul says nothing about the soul that went
    unread. Escalation may stand on partial evidence; clearance may not."""
    found = probe["partial_weak"]
    assert found["complete"] is True
    assert found["conflict_status"] == "requires_human"
    assert "partial" in found["decision"]


def test_the_issuer_still_requires_the_token(probe):
    assert probe["anonymous"] == 401


def test_the_receipt_shape_is_stable(probe):
    """The n8n Learning Gate reads named fields; every Build 12 field is
    still present, and the additions (band, policy) are strictly additive."""
    assert probe["receipt_keys"] == sorted(
        [
            "receipt_id",
            "complete",
            "sources",
            "conflict_status",
            "matched_records",
            "notes",
            "policy",
            "issued_at",
            "issued_by",
        ]
    )
    assert probe["matched_record_keys"] == sorted(
        ["id", "text", "score", "band", "source", "kind", "heading", "area", "dated"]
    )
    assert probe["policy_keys"] == sorted(
        ["version", "weak_below", "strong_at", "decision"]
    )


def test_the_score_bands_sit_exactly_where_declared(probe):
    assert probe["bands"] == {
        "-0.10": "unknown",
        "0.00": "unknown",
        "0.01": "weak",
        "0.3499": "weak",
        "0.35": "adjacent",
        "0.5999": "adjacent",
        "0.60": "strong",
        "1.00": "strong",
    }


def test_opposition_cues_match_words_not_fragments(probe):
    assert probe["cues"]["nevertheless"] is None
    assert probe["cues"]["must_not_upper"] == "must not"
    assert probe["cues"]["plain"] is None
    assert probe["cues"]["read_only"] == "read-only"
    assert probe["cues"]["donot_joined"] is None
    assert probe["cues"]["typographic"] == "don't"
