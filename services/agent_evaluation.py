"""Offline evaluation primitives. No execution, promotion, or runtime wiring.

Inputs must come from trusted test runners, never model-authored receipts.
An evidence reference names an artifact; this module does not authenticate it.
"""
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping, Optional, Sequence, Tuple

VERDICTS = frozenset({'VERIFIED', 'FAILED', 'UNVERIFIED'})


@dataclass(frozen=True)
class CheckResult:
    requirement_id: str
    verdict: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError('requirement_id is empty')
        if self.verdict not in VERDICTS:
            raise ValueError('invalid verdict')
        if self.verdict != 'UNVERIFIED' and not self.evidence_ref.strip():
            raise ValueError('conclusive checks require evidence')


def outcome_verdict(required: Sequence[str], checks: Sequence[CheckResult]) -> str:
    """Fail closed on missing checks; judges are deliberately not an input."""
    if not required or any(not item.strip() for item in required):
        raise ValueError('at least one named requirement is required')
    if len(set(required)) != len(required):
        raise ValueError('duplicate requirement')
    by_id = {}
    for check in checks:
        if check.requirement_id not in required:
            raise ValueError('check names an unknown requirement')
        if check.requirement_id in by_id:
            raise ValueError('duplicate check')
        by_id[check.requirement_id] = check.verdict
    if 'FAILED' in by_id.values():
        return 'FAILED'
    if any(by_id.get(item) != 'VERIFIED' for item in required):
        return 'UNVERIFIED'
    return 'VERIFIED'


@dataclass(frozen=True)
class Agreement:
    paired: int
    agreed: int
    missing: int
    disagreements: Tuple[str, ...]
    rate: Optional[float]
    kappa: Optional[float]


def evaluator_agreement(
    task_ids: Sequence[str],
    left: Mapping[str, str],
    right: Mapping[str, str],
) -> Agreement:
    """Nominal verdict agreement over a declared task universe.

    Missing votes are disclosed, not counted as agreement. Kappa is undefined
    for no overlap or degenerate marginal distributions and returned as None.
    This statistic does not measure correctness or evaluator independence.
    """
    universe = set(task_ids)
    if len(universe) != len(task_ids) or any(not t.strip() for t in task_ids):
        raise ValueError('task IDs must be unique and nonempty')
    for votes in (left, right):
        if set(votes) - universe:
            raise ValueError('vote outside declared tasks')
        if any(v not in VERDICTS for v in votes.values()):
            raise ValueError('invalid vote')
    paired = tuple(t for t in task_ids if t in left and t in right)
    n = len(paired)
    disagreements = tuple(t for t in paired if left[t] != right[t])
    agreed = n - len(disagreements)
    rate = agreed / n if n else None
    chance = sum(
        sum(left[t] == v for t in paired) * sum(right[t] == v for t in paired)
        for v in VERDICTS
    ) / (n * n) if n else None
    kappa = (rate - chance) / (1 - chance) if chance is not None and chance < 1 else None
    return Agreement(n, agreed, len(task_ids) - n, disagreements, rate, kappa)


def all_evaluator_pairs(
    task_ids: Sequence[str], votes: Mapping[str, Mapping[str, str]],
) -> Mapping[Tuple[str, str], Agreement]:
    """Report each pair separately instead of hiding disagreement in a mean."""
    if len(votes) < 2:
        raise ValueError('at least two evaluators are required')
    return {
        (a, b): evaluator_agreement(task_ids, votes[a], votes[b])
        for a, b in combinations(sorted(votes), 2)
    }
