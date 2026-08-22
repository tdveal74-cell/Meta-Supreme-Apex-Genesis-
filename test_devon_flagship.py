"""Tests for the Flagship Bar scoring gate."""

import pytest

from services.devon.flagship import (
    CLAUSES,
    DIMENSIONS,
    Assessment,
    CriticMode,
    Finding,
    ScoringError,
    Verdict,
    blank_scores,
    requires_gauntlet,
)


def passing_scores():
    scores = blank_scores(5)
    return scores


def make(scores=None, clauses=None, verification=5, critic=CriticMode.FRESH, cycle=0):
    return Assessment(
        subject="test deliverable",
        scores=scores or passing_scores(),
        clauses_met=clauses if clauses is not None else {1: True, 2: True, 3: True},
        verification_score=verification,
        critic_mode=critic,
        revision_cycle=cycle,
    )


def test_the_three_clauses_are_present():
    assert len(CLAUSES) == 3
    assert [c.number for c in CLAUSES] == [1, 2, 3]


def test_twelve_dimensions_are_scored():
    assert len(DIMENSIONS) == 12
    assert "security" in DIMENSIONS
    assert "flagship bar" in DIMENSIONS


def test_a_clean_sheet_passes():
    assert make().verdict is Verdict.PASS


def test_every_dimension_must_be_scored():
    partial = {"security": 5}
    with pytest.raises(ScoringError, match="Missing"):
        Assessment("x", partial, {1: True, 2: True, 3: True}, 5, CriticMode.FRESH)


def test_an_unknown_dimension_is_refused():
    scores = passing_scores()
    scores["vibes"] = 5
    with pytest.raises(ScoringError, match="Unknown dimensions"):
        Assessment("x", scores, {1: True, 2: True, 3: True}, 5, CriticMode.FRESH)


def test_scores_must_be_integers_one_to_five():
    scores = passing_scores()
    scores["correctness"] = 7
    with pytest.raises(ScoringError, match="1 to 5"):
        Assessment("x", scores, {1: True, 2: True, 3: True}, 5, CriticMode.FRESH)


def test_security_must_be_exactly_five():
    scores = passing_scores()
    scores["security"] = 4
    assessment = make(scores)
    assert assessment.verdict is not Verdict.PASS
    assert any("security" in reason for reason in assessment.failures())


def test_a_dimension_below_the_floor_quarantines():
    scores = passing_scores()
    scores["correctness"] = 2
    assert make(scores).verdict is Verdict.QUARANTINE


def test_verification_below_four_blocks_the_pass():
    assessment = make(verification=3)
    assert assessment.verdict is not Verdict.PASS
    assert any("verification" in reason for reason in assessment.failures())


def test_a_missed_clause_means_the_bar_is_not_met():
    assessment = make(clauses={1: True, 2: False, 3: True})
    assert not assessment.bar_met
    assert assessment.verdict is Verdict.QUARANTINE
    assert any("clause 2" in reason for reason in assessment.failures())


def test_a_low_mean_alone_is_conditional_not_quarantine():
    scores = blank_scores(3)
    scores["security"] = 5
    assessment = make(scores, verification=4)
    assert assessment.mean < 4.0
    assert assessment.verdict is Verdict.PASS_WITH_CONDITIONS


def test_burning_the_revision_cycles_quarantines():
    scores = blank_scores(3)
    scores["security"] = 5
    assert make(scores, verification=4, cycle=3).verdict is Verdict.QUARANTINE


def test_a_finding_without_evidence_does_not_exist():
    with pytest.raises(ScoringError, match="no evidence"):
        Finding(
            location="somewhere",
            problem="something",
            consequence="something bad",
            owner="someone",
            evidence="",
        )


def test_a_finding_with_evidence_renders_it():
    finding = Finding(
        location="backend/feature.py:211",
        problem="unsanitised speech concatenated into a shell command",
        consequence="command injection from voice input",
        owner="upstream",
        evidence='os.system("start " + query)',
    )
    assert "backend/feature.py:211" in finding.render()
    assert "evidence:" in finding.render()


def test_a_simulated_critic_pass_needs_human_review():
    assessment = make(critic=CriticMode.SIMULATED)
    assert assessment.verdict is Verdict.PASS
    assert assessment.needs_human_review
    assert "needing human review" in assessment.render()


def test_a_fresh_critic_pass_does_not_flag_for_review():
    assert not make(critic=CriticMode.FRESH).needs_human_review


def test_the_verdict_renders_the_required_shape():
    rendered = make().render()
    for section in ("VERDICT:", "Scores:", "Findings:", "Receipts:", "Recommendation:"):
        assert section in rendered
    assert "critic_mode:" in rendered


def test_a_verdict_with_no_receipts_says_so():
    """Assertion is not result."""
    assert "A verdict with no receipts is an assertion" in make().render()


def test_the_human_owns_ship():
    assert "The human owns SHIP" in make().render()


@pytest.mark.parametrize(
    "kind", ["code change", "a diff", "automation", "workflow", "config edit", "content", "plan"]
)
def test_ship_worthy_work_requires_the_gauntlet(kind):
    assert requires_gauntlet(kind)


@pytest.mark.parametrize("kind", ["a question", "conversational answer", "one liner"])
def test_conversational_work_skips_the_gauntlet(kind):
    assert not requires_gauntlet(kind)
