"""Adversarial offline cases, not measurements of any real route."""
import math
from dataclasses import FrozenInstanceError, replace

import pytest

from services.agent_benchmarks import (
    KnownAnswer,
    RouteTrace,
    aggregate_routes,
    calibrate,
    compare_paired,
    fingerprint,
    synthetic_example,
)


def trace(**changes):
    record = RouteTrace('trace-a', 'a', 'research', fingerprint({'task': 'a'}),
                        'route-v1', 'model-v1', 'prompt-v1', 'skill-v1', 'suite-v1',
                        fingerprint({'seed': 42}), 'baseline', 'completed', ('receipt:a',),
                        3, 0, 3, True, False, False)
    return replace(record, **changes)


def answers():
    return (KnownAnswer('a', fingerprint({'task': 'a'}), 'VERIFIED', 'fixture:a'),
            KnownAnswer('b', fingerprint({'task': 'b'}), 'FAILED', 'fixture:b'))


def test_immutable_versioned_trace_with_content_hash():
    record = trace()
    with pytest.raises(FrozenInstanceError):
        record.task_id = 'mutated'
    assert record.content_hash == trace().content_hash
    assert record.content_hash != trace(latency_ms=1).content_hash
    with pytest.raises(ValueError):
        trace(receipt_refs=['mutable'])
    with pytest.raises(ValueError):
        trace(schema_version=2)


@pytest.mark.parametrize('reason', ['approval_pause', 'tool_unavailable', 'budget_exhausted', 'error'])
def test_boundary_pause_never_an_early_stopper(reason):
    record = trace(stop_reason=reason, unresolved=3, stopped_with_available_next_step=True)
    assert record.classification == 'insufficient'


def test_classification_does_not_conflate_investigation_and_correctness():
    assert trace().classification == 'investigator'
    assert trace(unsupported_answer=True).classification == 'mixed'
    assert trace(investigated=False, unsupported_answer=True).classification == 'premature_answerer'
    assert trace(investigated=False, unresolved=1, stop_reason='voluntary_stop',
                 stopped_with_available_next_step=True).classification == 'early_stopper'
    assert trace(investigated=False, unresolved=1, stop_reason='voluntary_stop').classification == 'insufficient'
    assert trace(receipt_refs=()).classification == 'insufficient'
    assert trace(required=0, evidenced=0).classification == 'insufficient'


@pytest.mark.parametrize('field,value', [('required', True), ('required', -1), ('unresolved', 4),
                                         ('evidenced', 4), ('investigated', 1),
                                         ('latency_ms', math.nan), ('cost_usd', math.inf),
                                         ('cost_usd', -1), ('task_hash', 'a'),
                                         ('config_fingerprint', 'x' * 64)])
def test_invalid_trace_inputs_rejected(field, value):
    with pytest.raises(ValueError):
        trace(**{field: value})


def test_aggregate_preserves_denominators_missing_metrics_and_strata():
    rows = [trace(latency_ms=100), trace(task_id='b', trace_id='b', task_hash=fingerprint({'task': 'b'}), unresolved=2, evidenced=1, cost_usd=0)]
    result = aggregate_routes(rows)[0]
    assert (result['tasks'], result['required'], result['unresolved'], result['evidenced']) == (2, 6, 2, 4)
    assert result['evidence_coverage'] == 4 / 6
    assert result['latency_ms'] == {'recorded': 1, 'missing': 1, 'mean': 100}
    assert result['cost_usd'] == {'recorded': 1, 'missing': 1, 'mean': 0}
    assert len(aggregate_routes([trace(), trace(trace_id='b', model_version='v2')])) == 2
    with pytest.raises(ValueError):
        aggregate_routes([trace(), trace()])
    with pytest.raises(ValueError):
        aggregate_routes([trace(), trace(trace_id='other')])


def test_paired_comparison_reports_only_recorded_paired_metrics():
    report = compare_paired([trace(latency_ms=10)], [trace(trace_id='treatment', treatment='compaction', latency_ms=7)])
    assert report['latency_ms_delta'] == {'paired': 1, 'missing': 0, 'mean': -3}
    assert report['cost_usd_delta'] == {'paired': 0, 'missing': 1, 'mean': None}


@pytest.mark.parametrize('change', [{'task_hash': 'a' * 64}, {'task_id': 'b'},
                                   {'config_fingerprint': 'b' * 64}, {'model_version': 'v2'},
                                   {'prompt_version': 'v2'}, {'skill_version': 'v2'},
                                   {'suite_version': 'v2'}, {'required': 4}, {'route_version': 'v2'}])
def test_comparison_rejects_uncontrolled_changes(change):
    with pytest.raises(ValueError):
        compare_paired([trace()], [trace(treatment='orchestration', **change)])


def test_calibration_perfect_agreement_can_share_false_approval():
    report = calibrate(answers(), {'left': {'a': 'VERIFIED', 'b': 'VERIFIED'},
                                   'right': {'a': 'VERIFIED', 'b': 'VERIFIED'}})
    assert report['agreement'][0]['rate'] == 1
    assert report['judges']['left']['correct'] == 1
    assert report['judges']['left']['false_approvals'] == ('b',)
    assert report['shared_errors'] == ({'task_id': 'b', 'verdict': 'VERIFIED', 'judges': ('left', 'right')},)


def test_missing_votes_are_not_accuracy_or_shared_error():
    report = calibrate(answers(), {'left': {'b': 'VERIFIED'}, 'right': {}})
    assert report['judges']['right']['accuracy_on_votes'] is None
    assert report['judges']['right']['missing'] == 2
    assert report['agreement'][0]['missing'] == 2
    assert report['shared_errors'] == ()


def test_calibration_rejects_duplicates_leakage_unknown_votes_and_single_judge():
    cases = [([answers()[0], answers()[0]], {'x': {}, 'y': {}}, ()),
             ([answers()[0], replace(answers()[0], task_id='duplicate-content')], {'x': {}, 'y': {}}, ()),
             (answers(), {'x': {}, 'y': {}}, (answers()[0].task_hash,)),
             (answers(), {'x': {'unknown': 'FAILED'}, 'y': {}}, ()),
             (answers(), {'x': {'a': 'nonsense'}, 'y': {}}, ()),
             (answers(), {'x': {}}, ())]
    for known, votes, training in cases:
        with pytest.raises(ValueError):
            calibrate(known, votes, training_hashes=training)


def test_synthetic_example_is_explicit_and_deterministic():
    assert synthetic_example() == synthetic_example()
    assert 'SYNTHETIC' in synthetic_example()['provenance']
