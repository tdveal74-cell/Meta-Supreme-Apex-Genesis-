"""Stage 3: conservative read-only bridge for DEVON declared-check receipts.

A passing deterministic runtime check is evidence for requirement_evidence only.
It never asserts source provenance, visual quality, canon, human review, or
publication. Every check is recomputed from immutable captured result bytes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.agent_effect_receipts import arguments_hash
from app.services.arf_evidence_source import EvidenceReadRefused, GateAttestations
from services.agent_runtime.verification import check_captured, digest


def _get(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _json(text: str) -> Any:
    def reject(name: str) -> None:
        raise ValueError("nonfinite numeric constant")

    value = json.loads(text, parse_constant=reject)
    json.dumps(value, allow_nan=False)
    return value


def _scope(task_id: str, tenant_id: str, domain: str, workflow_stage: str,
           policy_digest: str) -> dict[str, str]:
    return dict(task_id=task_id, tenant_id=tenant_id, domain=domain,
                workflow_stage=workflow_stage, policy_digest=policy_digest)


def verify_declared_gate(*, task: Any, receipt: Any, results: list[Any],
                         task_id: str, tenant_id: str, domain: str,
                         workflow_stage: str, policy_digest: str) -> GateAttestations:
    """Re-evaluate current declared checks against owner-scoped immutable rows.

    The caller is responsible for trusted owner/task DB queries. This check
    independently rejects cross-owner, cross-task, stale and corrupt records.
    Absent evidence returns zero gates; contradictory evidence raises closed.
    """
    scope = _scope(task_id, tenant_id, domain, workflow_stage, policy_digest)
    empty = GateAttestations(**scope)
    if not tenant_id or not task_id or not policy_digest or workflow_stage not in {"build", "review", "release"}:
        raise EvidenceReadRefused("invalid declared-check reader scope")
    if task is None or _get(task, "id") != task_id or _get(task, "owner_id") != tenant_id:
        raise EvidenceReadRefused("task identity or owner mismatch")
    payload = _get(task, "payload")
    if not isinstance(payload, dict) or payload.get("task_id") != task_id or payload.get("state") != _get(task, "state"):
        raise EvidenceReadRefused("task payload identity mismatch")
    if payload.get("state") != "completed":
        return empty
    checks = payload.get("verification_requirements")
    if not isinstance(checks, list) or not checks:
        return empty
    task_v = payload.get("verification")
    if not isinstance(task_v, dict) or task_v.get("verdict") != "VERIFIED":
        return empty
    rid, rhash = task_v.get("receipt_id"), task_v.get("receipt_sha256")
    if not isinstance(rid, str) or not rid or not isinstance(rhash, str) or len(rhash) != 64:
        return empty
    if receipt is None:
        return empty
    generation = _get(task, "execution_generation")
    if (_get(receipt, "id") != rid or _get(receipt, "owner_id") != tenant_id
            or _get(receipt, "task_id") != task_id or _get(receipt, "generation") != generation):
        raise EvidenceReadRefused("current verification receipt binding mismatch")
    body = _get(receipt, "body")
    if not isinstance(body, str) or digest(body) != rhash or _get(receipt, "content_hash") != rhash:
        raise EvidenceReadRefused("verification receipt hash mismatch")
    try:
        obj = _json(body)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise EvidenceReadRefused("malformed immutable verification receipt") from exc
    v = obj.get("verification") if isinstance(obj, dict) else None
    if (not isinstance(v, dict) or v.get("verdict") != "VERIFIED"
            or v.get("scope") != "declared_checks_only" or v.get("checker_version") != "runtime-checks-v1"
            or v.get("plan_completed") is not True):
        raise EvidenceReadRefused("verification receipt is not a declared-check pass")
    if len(checks) > 50 or not isinstance(v.get("checks"), list):
        raise EvidenceReadRefused("invalid verification checklist")
    plan = payload.get("plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        raise EvidenceReadRefused("current plan unavailable")
    by_step = {}
    for s in steps:
        if not isinstance(s, dict) or not isinstance(s.get("step_id"), str) or not isinstance(s.get("tool_call"), dict):
            raise EvidenceReadRefused("invalid persisted plan step")
        if not s["step_id"] or s["step_id"] in by_step:
            raise EvidenceReadRefused("duplicate persisted plan step")
        by_step[s["step_id"]] = s["tool_call"]
    by_result = {}
    for row in results:
        if (_get(row, "owner_id") != tenant_id or _get(row, "task_id") != task_id or
                _get(row, "generation") != generation):
            raise EvidenceReadRefused("unscoped tool evidence")
        sid = _get(row, "step_id")
        if sid in by_result or sid not in by_step:
            raise EvidenceReadRefused("duplicate or unknown tool-result step")
        text = _get(row, "body")
        sha = _get(row, "content_hash")
        if not isinstance(text, str) or not isinstance(sha, str) or digest(text) != sha:
            raise EvidenceReadRefused("tool-result integrity mismatch")
        try:
            parsed = _json(text)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise EvidenceReadRefused("malformed captured tool result") from exc
        call = by_step[sid]
        if (not isinstance(parsed, dict) or parsed.get("schema_version") != 1
                or parsed.get("step_id") != sid or parsed.get("tool") != call.get("name")
                or parsed.get("arguments_hash") != arguments_hash(call.get("arguments"))
                or type(parsed.get("ok")) is not bool):
            raise EvidenceReadRefused("captured result does not match current plan")
        by_result[sid] = (row, parsed)
    verdict_rows = v["checks"]
    declared_ids = [c.get("id") for c in checks if isinstance(c, dict)]
    reported_ids = [c.get("requirement_id") for c in verdict_rows if isinstance(c, dict)]
    if (len(declared_ids) != len(checks) or len(reported_ids) != len(verdict_rows)
            or any(not isinstance(i, str) or not i for i in declared_ids + reported_ids)
            or len(set(declared_ids)) != len(declared_ids) or set(declared_ids) != set(reported_ids)
            or len(verdict_rows) != len(checks)):
        raise EvidenceReadRefused("receipt checklist differs from declared requirements")
    refs = ["runtime-verification:" + rid + ":" + rhash]
    for c in checks:
        sid = c.get("step_id")
        if sid not in by_step or sid not in by_result:
            raise EvidenceReadRefused("missing independently captured tool result")
        row, parsed = by_result[sid]
        evidence_ref = str(_get(row, "id")) + ":" + _get(row, "content_hash")
        try:
            checked = check_captured(c, parsed, evidence_ref)
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
            raise EvidenceReadRefused("malformed declared checker") from exc
        recorded = next(z for z in verdict_rows if z["requirement_id"] == c["id"])
        if (checked.verdict != "VERIFIED" or recorded.get("verdict") != "VERIFIED"
                or recorded.get("evidence_ref") != evidence_ref):
            raise EvidenceReadRefused("stored and recomputed checks disagree")
        refs.append("runtime-result:" + evidence_ref)
    refs = sorted(set(refs))
    revision = hashlib.sha256(json.dumps([task_id, tenant_id, str(generation), policy_digest, *refs],
                                         separators=(",", ":")).encode()).hexdigest()
    return GateAttestations(**scope, verified_gates=frozenset({"requirement_evidence"}),
                            evidence_refs=tuple(refs), revision=revision)


class RuntimeDeclaredChecksGateReader:
    """Owner-scoped DB adapter with no authorization, writes or review claims."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def load_gates(self, *, task_id: str, tenant_id: str, domain: str,
                         workflow_stage: str, policy_digest: str) -> GateAttestations:
        from sqlalchemy import select

        from app.models.agent_evidence import AgentToolResultRecord, AgentVerificationRecord
        from app.models.agent_runtime import AgentTaskRecord

        task = await self._db.scalar(select(AgentTaskRecord).where(
            AgentTaskRecord.id == task_id, AgentTaskRecord.owner_id == tenant_id))
        if task is None:
            raise EvidenceReadRefused("task not found for owner")
        data = task.payload if isinstance(task.payload, dict) else {}
        v = data.get("verification") if isinstance(data.get("verification"), dict) else {}
        rid = v.get("receipt_id")
        receipt = None
        rows = []
        if isinstance(rid, str) and rid:
            receipt = await self._db.scalar(select(AgentVerificationRecord).where(
                AgentVerificationRecord.id == rid,
                AgentVerificationRecord.task_id == task_id,
                AgentVerificationRecord.owner_id == tenant_id))
            if receipt is not None:
                rows = list((await self._db.scalars(select(AgentToolResultRecord).where(
                    AgentToolResultRecord.task_id == task_id,
                    AgentToolResultRecord.owner_id == tenant_id,
                    AgentToolResultRecord.generation == task.execution_generation))).all())
        return verify_declared_gate(task=task, receipt=receipt, results=rows,
                                    task_id=task_id, tenant_id=tenant_id, domain=domain,
                                    workflow_stage=workflow_stage, policy_digest=policy_digest)
