"""Deterministic route benchmarks over trusted runner traces, never LLM claims.

Records are immutable versioned values. Storage/receipt authentication belongs to
an authorized runner. Synthetic examples establish arithmetic, not performance.
"""
import json
import math
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Mapping, Optional, Sequence, Tuple

from services.agent_evaluation import VERDICTS, all_evaluator_pairs


def fingerprint(value: Mapping) -> str:
    """Hash strict canonical JSON; caller must include all non-treatment settings."""
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def _named(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('nonempty identifier required')


def _count(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError('count must be a nonnegative integer')


def _metric(value: Optional[float]) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not math.isfinite(value) or value < 0):
        raise ValueError('metric must be finite and nonnegative or absent')


@dataclass(frozen=True)
class RouteTrace:
    """One frozen task execution; counters are established by runner receipts.

    investigator means investigation was observed, not that the answer is right.
    Boundary pauses are excluded from failure classification. Evidence coverage
    measures requirements with evidence, not correctness. None is unmeasured.
    """
    trace_id: str
    task_id: str
    task_family: str
    task_hash: str
    route_version: str
    model_version: str
    prompt_version: str
    skill_version: str
    suite_version: str
    config_fingerprint: str
    treatment: str
    stop_reason: str
    receipt_refs: Tuple[str, ...]
    required: int
    unresolved: int
    evidenced: int
    investigated: bool
    unsupported_answer: bool
    stopped_with_available_next_step: bool
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        for key in ('trace_id', 'task_id', 'task_family', 'route_version', 'model_version',
                    'prompt_version', 'skill_version', 'suite_version'):
            _named(getattr(self, key))
        for key in ('task_hash', 'config_fingerprint'):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('SHA256 fingerprint required')
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise ValueError('unsupported schema version')
        if self.treatment not in ('baseline', 'orchestration', 'compaction'):
            raise ValueError('unknown treatment')
        if self.stop_reason not in ('completed', 'voluntary_stop', 'approval_pause',
                                    'tool_unavailable', 'budget_exhausted', 'error'):
            raise ValueError('unknown stop reason')
        if not isinstance(self.receipt_refs, tuple) or len(set(self.receipt_refs)) != len(self.receipt_refs):
            raise ValueError('receipt refs must be an immutable unique tuple')
        for ref in self.receipt_refs:
            _named(ref)
        for value in (self.required, self.unresolved, self.evidenced):
            _count(value)
        if self.unresolved > self.required or self.evidenced > self.required:
            raise ValueError('coverage exceeds declared requirements')
        for value in (self.investigated, self.unsupported_answer, self.stopped_with_available_next_step):
            if type(value) is not bool:
                raise ValueError('behavior flags must be boolean')
        _metric(self.latency_ms)
        _metric(self.cost_usd)

    @property
    def classification(self) -> str:
        if not self.receipt_refs or not self.required:
            return 'insufficient'
        if self.stop_reason in ('approval_pause', 'tool_unavailable', 'budget_exhausted', 'error'):
            return 'insufficient'
        early = (self.stop_reason == 'voluntary_stop' and self.unresolved > 0
                 and self.stopped_with_available_next_step)
        labels = (['investigator'] if self.investigated else [])
        if self.unsupported_answer:
            labels.append('premature_answerer')
        if early:
            labels.append('early_stopper')
        return labels[0] if len(labels) == 1 else 'mixed' if labels else 'insufficient'

    @property
    def content_hash(self) -> str:
        return fingerprint(asdict(self))


def _unique(traces: Sequence[RouteTrace]) -> None:
    ids = [t.trace_id for t in traces]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate trace')
    cases = [(t.route_version, t.model_version, t.prompt_version, t.skill_version,
              t.suite_version, t.config_fingerprint, t.treatment, t.task_id) for t in traces]
    if len(cases) != len(set(cases)):
        raise ValueError('duplicate task execution in stratum')
    contents = [(t.route_version, t.model_version, t.prompt_version, t.skill_version,
                 t.suite_version, t.config_fingerprint, t.treatment, t.task_hash) for t in traces]
    if len(contents) != len(set(contents)):
        raise ValueError('duplicate frozen task content in stratum')


def aggregate_routes(traces: Sequence[RouteTrace]) -> list:
    """Keep version/config strata separate; disclose every metric denominator."""
    _unique(traces)
    groups = {}
    for trace in traces:
        key = tuple(getattr(trace, name) for name in (
            'route_version', 'task_family', 'model_version', 'prompt_version',
            'skill_version', 'suite_version', 'config_fingerprint', 'treatment'))
        groups.setdefault(key, []).append(trace)
    results = []
    for key, rows in sorted(groups.items()):
        required = sum(t.required for t in rows)
        report = dict(zip(('route_version', 'task_family', 'model_version', 'prompt_version',
                           'skill_version', 'suite_version', 'config_fingerprint', 'treatment'), key, strict=True))
        report.update(tasks=len(rows), required=required,
                      unresolved=sum(t.unresolved for t in rows),
                      evidenced=sum(t.evidenced for t in rows),
                      evidence_coverage=sum(t.evidenced for t in rows) / required if required else None,
                      classifications={label: sum(t.classification == label for t in rows) for label in
                                       ('investigator', 'premature_answerer', 'early_stopper', 'mixed', 'insufficient')})
        for metric in ('latency_ms', 'cost_usd'):
            recorded = [getattr(t, metric) for t in rows if getattr(t, metric) is not None]
            report[metric] = {'recorded': len(recorded), 'missing': len(rows) - len(recorded),
                              'mean': sum(recorded) / len(recorded) if recorded else None}
        results.append(report)
    return results


def compare_paired(baseline: Sequence[RouteTrace], treated: Sequence[RouteTrace]) -> dict:
    """Refuse changed tasks/configurations, duplicates and unpaired comparisons."""
    _unique(baseline)
    _unique(treated)
    if not baseline or len(baseline) != len(treated):
        raise ValueError('nonempty paired frozen suite required')
    if any(t.treatment != 'baseline' for t in baseline):
        raise ValueError('baseline required')
    treatments = {t.treatment for t in treated}
    if len(treatments) != 1 or 'baseline' in treatments:
        raise ValueError('one treatment required')
    left = {t.task_id: t for t in baseline}
    right = {t.task_id: t for t in treated}
    if len(left) != len(baseline) or len(right) != len(treated) or left.keys() != right.keys():
        raise ValueError('identical unique task universe required')
    compare_fields = ('task_hash', 'task_family', 'required', 'route_version', 'model_version',
                      'prompt_version', 'skill_version', 'suite_version', 'config_fingerprint')
    for task_id, trace in left.items():
        if any(getattr(trace, f) != getattr(right[task_id], f) for f in compare_fields):
            raise ValueError('frozen task or non-treatment configuration changed')
    result = {'paired': len(left), 'treatment': next(iter(treatments)),
              'baseline': aggregate_routes(baseline), 'treated': aggregate_routes(treated)}
    for metric in ('latency_ms', 'cost_usd'):
        deltas = [getattr(right[k], metric) - getattr(left[k], metric) for k in left
                  if getattr(right[k], metric) is not None and getattr(left[k], metric) is not None]
        result[metric + '_delta'] = {'paired': len(deltas), 'missing': len(left) - len(deltas),
                                     'mean': sum(deltas) / len(deltas) if deltas else None}
    return result


@dataclass(frozen=True)
class KnownAnswer:
    task_id: str
    task_hash: str
    verdict: str
    evidence_ref: str

    def __post_init__(self) -> None:
        _named(self.task_id)
        _named(self.evidence_ref)
        if (len(self.task_hash) != 64 or any(c not in '0123456789abcdef' for c in self.task_hash)
                or self.verdict not in VERDICTS):
            raise ValueError('invalid known answer')


def calibrate(answers: Sequence[KnownAnswer], votes: Mapping[str, Mapping[str, str]],
              *, training_hashes: Sequence[str] = ()) -> dict:
    """Known answers must be independent trusted fixtures, never judge outputs.

    False approvals are VERIFIED votes against a non-VERIFIED known answer.
    Agreement does not establish correctness or independence. Missing votes do
    not count as correct, incorrect, false approval or shared error.
    """
    ids = [a.task_id for a in answers]
    hashes = [a.task_hash for a in answers]
    if not answers or len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes):
        raise ValueError('nonempty unique held-out answers required')
    if set(hashes) & set(training_hashes):
        raise ValueError('training leakage into held-out suite')
    for judge in votes:
        _named(judge)
    pairs = all_evaluator_pairs(ids, votes)
    truth = {a.task_id: a.verdict for a in answers}
    per_judge = {}
    for judge, ballot in votes.items():
        correct = sum(value == truth[task] for task, value in ballot.items())
        per_judge[judge] = {'total': len(ids), 'voted': len(ballot), 'missing': len(ids) - len(ballot),
                            'correct': correct, 'incorrect': len(ballot) - correct,
                            'accuracy_on_votes': correct / len(ballot) if ballot else None,
                            'false_approvals': tuple(t for t, v in ballot.items()
                                                     if v == 'VERIFIED' and truth[t] != 'VERIFIED')}
    shared_errors = tuple({'task_id': task, 'verdict': verdict,
                           'judges': tuple(j for j in sorted(votes) if votes[j].get(task) == verdict)}
                          for task in ids for verdict in sorted(VERDICTS)
                          if verdict != truth[task]
                          and sum(votes[j].get(task) == verdict for j in votes) >= 2)
    return {'total': len(ids), 'judges': per_judge, 'shared_errors': shared_errors,
            'agreement': tuple({'judges': pair, **asdict(value)} for pair, value in pairs.items())}


def synthetic_example() -> dict:
    """Deterministic synthetic votes; no provider called or route measured."""
    answers = tuple(KnownAnswer(t, fingerprint({'synthetic': t}), v, 'fixture:' + t)
                    for t, v in (('a', 'VERIFIED'), ('b', 'FAILED')))
    return {'provenance': 'SYNTHETIC FIXTURE; NO REAL LLM PERFORMANCE CLAIM',
            'calibration': calibrate(answers, {'synthetic-judge-1': {'a': 'VERIFIED', 'b': 'VERIFIED'},
                                             'synthetic-judge-2': {'a': 'VERIFIED', 'b': 'VERIFIED'}})}


if __name__ == '__main__':
    print(json.dumps(synthetic_example(), sort_keys=True, indent=2))
