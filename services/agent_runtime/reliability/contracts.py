"""Pure immutable contracts for read-only ARF shadow observation.

WARNING: EvidenceSnapshot data is trustworthy ONLY when returned by a
privileged app-layer evidence source. Never populate it from model output,
AgentTask.context, a request payload, or user-provided JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Protocol, Tuple


@dataclass(frozen=True)
class EvidenceSnapshot:
    task_id: str
    tenant_id: str
    domain: str
    workflow_stage: str
    policy_digest: str
    verified_gate_ids: FrozenSet[str] = frozenset()
    reviewed_gate_ids: FrozenSet[str] = frozenset()
    approved_step_ids: FrozenSet[str] = frozenset()
    receipted_step_ids: FrozenSet[str] = frozenset()
    ambiguous_step_ids: FrozenSet[str] = frozenset()
    evidence_refs: Tuple[str, ...] = ()
    revision: str = ""


class EvidenceSource(Protocol):
    """Must be implemented by an app-layer adapter reading authoritative stores.

    In particular: independently verify approval bindings and receipt/intent
    matching, verify tenant ownership and canon/reviewer provenance, and never
    accept the completion assertions on the supplied task as evidence.
    """

    def load(self, *, task_id: str, tenant_id: str, domain: str,
             workflow_stage: str, policy_digest: str) -> EvidenceSnapshot: ...


@dataclass(frozen=True)
class ShadowDecision:
    task_id: str
    domain: str
    policy_version: str
    policy_digest: str
    workflow_stage: str
    verdict: str
    selected_control: str
    blocking_reasons: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    evidence_revision: str
    scope: str = "read_only_shadow_observation_not_execution_authority"

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "workflow_stage": self.workflow_stage,
            "verdict": self.verdict,
            "selected_control": self.selected_control,
            "blocking_reasons": list(self.blocking_reasons),
            "evidence_refs": list(self.evidence_refs),
            "evidence_revision": self.evidence_revision,
            "scope": self.scope,
        }
