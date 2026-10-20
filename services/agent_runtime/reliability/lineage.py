"""ARF Stage 2: deterministic retry/lineage assessment, no execution.

State is external and durable only once an authorized app-layer store persists
it. A new task or agent name never resets the root failure's attempt history.
The recommender emits advice, never a new approval or external effect.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence


class HistoryConflict(ValueError):
    """Incomplete or contradictory immutable task ancestry."""


def fingerprint(*, hypothesis: str, expected_evidence: str,
                target_failure: str, intended_outcome: str) -> str:
    """Canonical failure identity stable across renames, delegation or handoff."""
    fields = (hypothesis, expected_evidence, target_failure, intended_outcome)
    if not all(isinstance(v, str) and v.strip() for v in fields):
        raise ValueError("retry identity requires four specific nonempty values")
    payload = json.dumps(["arf-failure-v1", *[s.strip().lower() for s in fields]],
                         ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


@dataclass(frozen=True)
class HistoryEvent:
    event_id: str
    owner_id: str
    root_task_id: str
    task_id: str
    parent_event_id: str
    delegated_from_event_id: str
    failure_fingerprint: str
    outcome_digest: str
    evidence_revision: str
    control: str
    # Monotonically rising for *each* root+failure fingerprint, across agents.
    attempt_no: int


@dataclass(frozen=True)
class RetryAdvice:
    verdict: str
    next_control: str
    reason: str
    matching_attempts: int
    referenced_event_ids: tuple[str, ...]


def review_history(events: Sequence[HistoryEvent], *, owner_id: str,
                   root_task_id: str) -> tuple[HistoryEvent, ...]:
    """Validate entire record history, including parent/delegated ancestry."""
    seen: dict[str, HistoryEvent] = {}
    counters: dict[str, int] = {}
    for event in events:
        if (not event.event_id or event.event_id in seen or
            event.owner_id != owner_id or event.root_task_id != root_task_id or
            not event.task_id or not _sha(event.failure_fingerprint) or
            not _sha(event.outcome_digest) or not event.control or
            not event.evidence_revision):
            raise HistoryConflict("invalid, duplicated, or cross-tenant recovery history")
        for ancestor in (event.parent_event_id, event.delegated_from_event_id):
            if ancestor and ancestor not in seen:
                raise HistoryConflict("unknown ancestor; cannot reset lineage")
        expected = counters.get(event.failure_fingerprint, 0) + 1
        if event.attempt_no != expected:
            raise HistoryConflict("attempt counter reset or gap across lineage")
        counters[event.failure_fingerprint] = expected
        seen[event.event_id] = event
    return tuple(events)


def advise_retry(events: Sequence[HistoryEvent], *, owner_id: str,
                 root_task_id: str, failure_fingerprint: str,
                 outcome_digest: str, evidence_revision: str) -> RetryAdvice:
    """No retry is authorized by this result. New evidence can alter advice.

    Two unchanged completed attempts call for a strategy change; three call for
    bounded human/root-cause review. Never suppress mandatory verification or
    classify an unknown external effect as safely retryable here.
    """
    review_history(events, owner_id=owner_id, root_task_id=root_task_id)
    if not _sha(failure_fingerprint) or not _sha(outcome_digest) or not evidence_revision:
        raise HistoryConflict("invalid proposed recovery evidence")
    related = [e for e in events if e.failure_fingerprint == failure_fingerprint]
    ids = tuple(e.event_id for e in related)
    if not related:
        return RetryAdvice("CONTINUE_DIAGNOSIS", "evidence_gate", "first occurrence", 0, ids)
    last = related[-1]
    if len(related) >= 3:
        return RetryAdvice("REVIEW_REQUIRED", "blocker_validator",
                           "attempt bound reached for this failure fingerprint", len(related), ids)
    if last.outcome_digest != outcome_digest or last.evidence_revision != evidence_revision:
        return RetryAdvice("CONTINUE_DIAGNOSIS", "evidence_gate", "meaningfully changed evidence/outcome", len(related), ids)
    return RetryAdvice("CHANGE_STRATEGY", "strategy_laundering_detector",
                       "repeated outcome without new evidence", len(related), ids)
