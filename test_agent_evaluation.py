"""Adversarial cases for offline verdicts; no provider or database calls."""
import pytest

from services.agent_evaluation import (
    CheckResult,
    all_evaluator_pairs,
    evaluator_agreement,
    outcome_verdict,
)


def test_missing_evidence_never_becomes_success():
    assert outcome_verdict(['schema', 'artifact'], []) == 'UNVERIFIED'
    assert outcome_verdict(['schema', 'artifact'], [
        CheckResult('schema', 'VERIFIED', 'fixture://schema'),
    ]) == 'UNVERIFIED'


def test_failed_check_cannot_be_outvoted():
    checks = [CheckResult('artifact', 'FAILED', 'fixture://bad-hash')]
    assert outcome_verdict(['artifact'], checks) == 'FAILED'
    # Even unanimously positive evaluators are reported independently.
    assert evaluator_agreement(['x'], {'x': 'VERIFIED'}, {'x': 'VERIFIED'}).rate == 1
    assert outcome_verdict(['artifact'], checks) == 'FAILED'


def test_complete_evidence_and_explicit_unknown():
    assert outcome_verdict(['x'], [CheckResult('x', 'VERIFIED', 'fixture://x')]) == 'VERIFIED'
    assert outcome_verdict(['x'], [CheckResult('x', 'UNVERIFIED', '')]) == 'UNVERIFIED'


@pytest.mark.parametrize('required,checks', [
    ([], []), ([''], []), (['x', 'x'], []),
    (['x'], [CheckResult('y', 'VERIFIED', 'fixture://y')]),
    (['x'], [CheckResult('x', 'VERIFIED', 'a'), CheckResult('x', 'FAILED', 'b')]),
])
def test_ambiguous_contracts_are_rejected(required, checks):
    with pytest.raises(ValueError):
        outcome_verdict(required, checks)


@pytest.mark.parametrize('verdict,ref', [('VERIFIED', ''), ('FAILED', ' '), ('PASS', 'x')])
def test_unbacked_or_invalid_check_is_rejected(verdict, ref):
    with pytest.raises(ValueError):
        CheckResult('x', verdict, ref)


def test_agreement_uses_overlap_and_discloses_missing_votes():
    result = evaluator_agreement(
        ['a', 'b', 'c'], {'a': 'VERIFIED', 'b': 'FAILED'},
        {'a': 'VERIFIED', 'b': 'VERIFIED', 'c': 'FAILED'},
    )
    assert (result.paired, result.agreed, result.missing) == (2, 1, 1)
    assert result.disagreements == ('b',)
    assert result.rate == 0.5
    assert result.kappa == 0


def test_empty_and_degenerate_are_not_calibration_success():
    result = evaluator_agreement(['x'], {}, {})
    assert result.rate is None and result.kappa is None
    result = evaluator_agreement(['x'], {'x': 'FAILED'}, {'x': 'FAILED'})
    assert result.rate == 1 and result.kappa is None


def test_systematic_disagreement_and_pairwise_reporting():
    votes = {'a': {'x': 'VERIFIED', 'y': 'FAILED'},
             'b': {'x': 'FAILED', 'y': 'VERIFIED'},
             'c': {'x': 'VERIFIED', 'y': 'FAILED'}}
    pairs = all_evaluator_pairs(['x', 'y'], votes)
    assert len(pairs) == 3
    assert pairs['a', 'b'].kappa == -1
    assert pairs['a', 'c'].kappa == 1


@pytest.mark.parametrize('tasks,left,right', [
    (['x', 'x'], {}, {}), ([''], {}, {}),
    (['x'], {'y': 'FAILED'}, {}), (['x'], {'x': 'PASS'}, {}),
])
def test_invalid_judge_inputs_are_rejected(tasks, left, right):
    with pytest.raises(ValueError):
        evaluator_agreement(tasks, left, right)


def test_one_judge_is_insufficient_for_agreement():
    with pytest.raises(ValueError):
        all_evaluator_pairs(['x'], {'only': {'x': 'VERIFIED'}})
