"""ARF Stage 2: app-layer, read-only DEVON evidence collector.

This module reads existing owner-scoped task, intent, receipt and DEVON approval
records. It NEVER edits tasks, grants approval, retries tools, or certifies
project-specific QC without a separately trusted gate reader.

IMPORTANT: `devon_approvals` may live in a separate PostgreSQL database. Pass
its actual read-only session as `approval_db`; do not silently fall back to the
task database. Both sessions must originate from trusted authenticated app
configuration, NOT caller-supplied connection strings or user input.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, FrozenSet, Protocol, Tuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import (
    AgentEffectIntentRecord,
    AgentEffectReceiptRecord,
    AgentTaskRecord,
)
from app.services.agent_effect_receipts import arguments_hash
from services.agent_runtime.governance import (
    APPROVAL_MARKER_PREFIX,
    RUNTIME_REQUESTED_BY,
    approval_binding,
)
from services.agent_runtime.reliability.contracts import EvidenceSnapshot


class EvidenceReadRefused(RuntimeError):
    """Required trusted evidence is missing, contradictory or out of scope."""


@dataclass(frozen=True)
class GateAttestations:
    """Result of a separately AUDITED gate reader, never task/request content.

    Reader contract: verify owner, task, domain, stage, exact policy digest,
    reviewer identity and supporting stored artifacts BEFORE returning any ID.
    This struct by itself authenticates nothing.
    """
    task_id: str
    tenant_id: str
    domain: str
    workflow_stage: str
    policy_digest: str
    verified_gates: FrozenSet[str] = frozenset()
    reviewed_gates: FrozenSet[str] = frozenset()
    evidence_refs: Tuple[str, ...] = ()
    revision: str = ""


class GateReader(Protocol):
    async def load_gates(self, *, task_id: str, tenant_id: str,
                         domain: str, workflow_stage: str,
                         policy_digest: str) -> GateAttestations: ...


class BoundEvidenceSource:
    """One-shot in-process bridge to the stage-1 synchronous observer.

    Construct only with a fresh snapshot from collect_evidence(), never with
    caller-supplied JSON. The observer rechecks all five scope properties.
    """

    def __init__(self, evidence: EvidenceSnapshot):
        self._evidence = evidence

    def load(self, *, task_id: str, tenant_id: str, domain: str,
             workflow_stage: str, policy_digest: str) -> EvidenceSnapshot:
        if (self._evidence.task_id, self._evidence.tenant_id,
            self._evidence.domain, self._evidence.workflow_stage,
            self._evidence.policy_digest) != (
            task_id, tenant_id, domain, workflow_stage, policy_digest
        ):
            raise EvidenceReadRefused("read-only evidence scope mismatch")
        return self._evidence


def _value(record: Any, name: str, default: Any = None) -> Any:
    return record.get(name, default) if isinstance(record, dict) else getattr(record, name, default)


def _fingerprint(parts: list[str]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reconcile_records(*, task_row: Any, intents: list[Any], receipts: list[Any],
                      approvals: list[Any], tenant_id: str, domain: str,
                      workflow_stage: str, policy_digest: str,
                      gates: GateAttestations | None) -> EvidenceSnapshot:
    """Pure check of the exact persisted DEVON row shapes.

    Caller must already fetch all rows with owner+task predicates. It must
    supply the entire result sets and never a partial or pagination-limited
    subset. The checks below are defense-in-depth, not authentication.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise EvidenceReadRefused("missing authenticated owner")
    if task_row is None or _value(task_row, "owner_id") != tenant_id:
        raise EvidenceReadRefused("missing owner-scoped task")
    task_id = _value(task_row, "id")
    if not isinstance(task_id, str) or not task_id:
        raise EvidenceReadRefused("invalid persisted task id")
    payload = _value(task_row, "payload")
    if not isinstance(payload, dict) or payload.get("task_id") != task_id:
        raise EvidenceReadRefused("persisted task payload is missing or mismatched")
    if payload.get("state") != _value(task_row, "state"):
        raise EvidenceReadRefused("persisted task state diverged from payload")
    plan = payload.get("plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        raise EvidenceReadRefused("persisted task has no trustworthy plan steps")
    step_map: dict[str, tuple[str, dict]] = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("step_id"), str):
            raise EvidenceReadRefused("malformed persisted plan step")
        sid = step["step_id"]
        tool = step.get("tool_call")
        if not sid or sid in step_map or not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not isinstance(tool.get("arguments"), dict):
            raise EvidenceReadRefused("duplicate or incomplete persisted plan")
        step_map[sid] = (tool["name"], tool["arguments"])

    if gates is not None and (
        gates.task_id, gates.tenant_id, gates.domain,
        gates.workflow_stage, gates.policy_digest
    ) != (task_id, tenant_id, domain, workflow_stage, policy_digest):
        raise EvidenceReadRefused("unscoped independent QC/review attestation")

    # All approvals come from owner-scoped devon_approvals readback and MUST be
    # in consumed state: approved alone does not prove an effect was spent.
    accepted_approvals: set[str] = set()
    approval_refs: list[str] = []
    for sid, (tool_name, args) in step_map.items():
        binding = approval_binding(task_id=task_id, step_id=sid,
                                   tool_name=tool_name, arguments=args)
        marker = APPROVAL_MARKER_PREFIX + binding
        matches = [r for r in approvals if _value(r, "requested_by") == RUNTIME_REQUESTED_BY
                   and _value(r, "owner_id") == tenant_id
                   and str(_value(r, "what_happens", "")).rstrip().endswith(marker)]
        if len(matches) > 1:
            raise EvidenceReadRefused("multiple matching approval decisions")
        if matches:
            approved = matches[0]
            if _value(approved, "state") == "consumed" and _value(approved, "decided_by"):
                accepted_approvals.add(sid)
                approval_refs.append("approval:" + str(_value(approved, "request_id")))

    intents_by_step: dict[str, list[Any]] = {}
    intent_ids: set[str] = set()
    for intent in intents:
        if (_value(intent, "owner_id") != tenant_id or _value(intent, "task_id") != task_id):
            raise EvidenceReadRefused("unscoped effect intent")
        sid = _value(intent, "step_id")
        if sid not in step_map:
            raise EvidenceReadRefused("effect intent references unknown step")
        tool_name, args = step_map[sid]
        if (_value(intent, "tool_name") != tool_name or
                _value(intent, "arguments_hash") != arguments_hash(args)):
            raise EvidenceReadRefused("effect intent plan binding mismatch")
        iid = _value(intent, "intent_id")
        if not iid or iid in intent_ids:
            raise EvidenceReadRefused("duplicate effect intent identity")
        intent_ids.add(iid)
        intents_by_step.setdefault(sid, []).append(intent)

    receipts_by_intent: dict[str, Any] = {}
    for receipt in receipts:
        if (_value(receipt, "owner_id") != tenant_id or
                _value(receipt, "task_id") != task_id):
            raise EvidenceReadRefused("unscoped effect receipt")
        iid = _value(receipt, "intent_id")
        if iid not in intent_ids or iid in receipts_by_intent:
            raise EvidenceReadRefused("orphan or duplicate effect receipt")
        receipts_by_intent[iid] = receipt

    receipted: set[str] = set()
    ambiguous: set[str] = set()
    receipt_refs: list[str] = []
    for sid, entries in intents_by_step.items():
        # Re-execution is not automatically safe even if every individual
        # invocation returned success. Avoid laundering duplicated effects.
        if len(entries) != 1:
            ambiguous.add(sid)
            continue
        intent = entries[0]
        receipt = receipts_by_intent.get(_value(intent, "intent_id"))
        if receipt is None:
            ambiguous.add(sid)
            continue
        if (_value(receipt, "execution_generation") != _value(intent, "execution_generation") or
                not _value(intent, "lease_token") or
                _value(receipt, "lease_token") != _value(intent, "lease_token") or
                _value(receipt, "status") != "succeeded"):
            ambiguous.add(sid)
            continue
        receipted.add(sid)
        receipt_refs.append("effect-receipt:" + str(_value(receipt, "id")))

    # Build the revision ONLY from provenance references and stored metadata;
    # never include access tokens, full provider responses, or private data.
    refs = tuple(sorted(set(approval_refs + receipt_refs + list(gates.evidence_refs if gates else ()))))
    revision = _fingerprint([task_id, str(_value(task_row, "updated_at")), policy_digest,
                             domain, workflow_stage, str(_value(task_row, "execution_generation")),
                             *refs, *(sorted(ambiguous)), gates.revision if gates else "NO_QC"]) if refs else ""
    return EvidenceSnapshot(
        task_id=task_id, tenant_id=tenant_id, domain=domain,
        workflow_stage=workflow_stage, policy_digest=policy_digest,
        verified_gate_ids=gates.verified_gates if gates else frozenset(),
        reviewed_gate_ids=gates.reviewed_gates if gates else frozenset(),
        approved_step_ids=frozenset(accepted_approvals),
        receipted_step_ids=frozenset(receipted),
        ambiguous_step_ids=frozenset(ambiguous),
        evidence_refs=refs, revision=revision,
    )


async def collect_evidence(*, db: AsyncSession, approval_db: AsyncSession | None,
                           task_id: str, owner_id: str, domain: str,
                           workflow_stage: str, policy_digest: str,
                           gate_reader: GateReader | None = None) -> tuple[dict, EvidenceSnapshot]:
    """Owner-scoped readback. No queries use task context as a trust source.

    `approval_db` MUST be the actual configured approval database session.
    When unavailable, returned evidence never marks effect approvals verified.
    A separately implemented GateReader must authenticate and scope its data.
    """
    if not task_id or not owner_id or not domain or not policy_digest or workflow_stage not in {"build", "review", "release"}:
        raise EvidenceReadRefused("invalid authenticated read scope")
    result = await db.execute(select(AgentTaskRecord).where(
        AgentTaskRecord.owner_id == owner_id, AgentTaskRecord.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise EvidenceReadRefused("task is missing or not owned")
    ir = await db.execute(select(AgentEffectIntentRecord).where(
        AgentEffectIntentRecord.owner_id == owner_id,
        AgentEffectIntentRecord.task_id == task_id))
    rr = await db.execute(select(AgentEffectReceiptRecord).where(
        AgentEffectReceiptRecord.owner_id == owner_id,
        AgentEffectReceiptRecord.task_id == task_id))
    intents = list(ir.scalars().all())
    receipts = list(rr.scalars().all())

    approval_rows: list[Any] = []
    if approval_db is not None:
        # Restrict reads to this task's bounded, exact runtime bindings.
        # No caller-supplied SQL fragments. `endswith(marker)` in reconcile_records
        # remains the final independent proof after this filtered lookup.
        plan = task.payload.get("plan") if isinstance(task.payload, dict) else None
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
            raise EvidenceReadRefused("invalid plan for approval readback")
        markers = set()
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("tool_call"), dict):
                raise EvidenceReadRefused("invalid plan step for approval readback")
            call = step["tool_call"]
            if not isinstance(step.get("step_id"), str) or not isinstance(call.get("name"), str) or not isinstance(call.get("arguments"), dict):
                raise EvidenceReadRefused("invalid approval binding inputs")
            markers.add(APPROVAL_MARKER_PREFIX + approval_binding(
                task_id=task_id, step_id=step["step_id"],
                tool_name=call["name"], arguments=call["arguments"],
            ))
        bindings = sorted(markers)
        params = {"owner": owner_id, "requested": RUNTIME_REQUESTED_BY}
        predicates = []
        for i, marker in enumerate(bindings):
            name = f"marker_{i}"
            params[name] = "%" + marker
            predicates.append("what_happens LIKE :" + name)
        ar = await approval_db.execute(text("""
            SELECT request_id, owner_id, requested_by, state, decided_by, what_happens
            FROM devon_approvals WHERE owner_id = :owner AND requested_by = :requested
              AND (""" + " OR ".join(predicates) + ")"), params)
        approval_rows = list(ar.mappings().all())
    gates = (await gate_reader.load_gates(task_id=task_id, tenant_id=owner_id,
                                         domain=domain, workflow_stage=workflow_stage,
                                         policy_digest=policy_digest)) if gate_reader else None
    snap = reconcile_records(task_row=task, intents=intents, receipts=receipts,
                             approvals=approval_rows, tenant_id=owner_id,
                             domain=domain, workflow_stage=workflow_stage,
                             policy_digest=policy_digest, gates=gates)
    # Return the persisted task, rather than any caller-provided task snapshot.
    return dict(task.payload), snap


async def observe_persisted_task(*, db: AsyncSession,
                                 approval_db: AsyncSession | None,
                                 owner_id: str, task_id: str, domain: str,
                                 workflow_stage: str, policy: Any,
                                 tool_registry: Any,
                                 gate_reader: GateReader | None = None):
    """Explicit trusted app entry point: read current records, then observe.

    This is not mounted as an HTTP route and does not call any runtime tool.
    Caller authenticates owner_id and selects domain/stage using trusted app
    configuration, never task.context or a model-produced answer.
    """
    from services.agent_runtime.reliability.observer import assess

    task, evidence = await collect_evidence(
        db=db, approval_db=approval_db, owner_id=owner_id, task_id=task_id,
        domain=domain, workflow_stage=workflow_stage, policy_digest=policy.digest,
        gate_reader=gate_reader,
    )
    return assess(task, domain=domain, tenant_id=owner_id,
                  workflow_stage=workflow_stage, policy=policy,
                  tool_registry=tool_registry,
                  evidence_source=BoundEvidenceSource(evidence))
