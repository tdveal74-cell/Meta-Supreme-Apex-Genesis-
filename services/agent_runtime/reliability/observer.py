"""Read-only ARF shadow observer for DEVON's existing AgentTask snapshots.

No execution, mutation, approval, retries, external writes, or task closure.
Caller MUST obtain task from the trusted runtime/store, tenant from authenticated
scope, and evidence_source from an independently trusted application adapter.
Do not expose assess() directly to unauthenticated callers as a trust oracle.
"""
from __future__ import annotations

from typing import Any

from .contracts import EvidenceSnapshot, EvidenceSource, ShadowDecision
from .policy import ReliabilityPolicy


_CONTROL = {
    "scope": "rule_conflict",
    "tool": "permission_and_scope_guard",
    "plan": "goal_lock",
    "evidence": "evidence_gate",
    "effect": "effect_reconciliation",
    "review": "independent_review",
    "running": "completion_gate",
    "done": "completion_gate",
}


def _result(task_id: str, domain: str, policy_version: str, policy_digest: str,
            control: str, reasons: list[str], evidence: EvidenceSnapshot | None = None,
            stage: str = "unknown") -> ShadowDecision:
    if reasons:
        verdict = "WOULD_HOLD"
    elif control == "running":
        verdict = "IN_PROGRESS"
    else:
        verdict = "WOULD_BE_ELIGIBLE_FOR_CLOSURE"
    return ShadowDecision(
        task_id=task_id, domain=domain, policy_version=policy_version,
        policy_digest=policy_digest, workflow_stage=stage, verdict=verdict, selected_control=_CONTROL[control],
        blocking_reasons=tuple(reasons),
        evidence_refs=evidence.evidence_refs if evidence else (),
        evidence_revision=evidence.revision if evidence else "",
    )


def assess(task_snapshot: dict[str, Any], *, domain: str, tenant_id: str,
           workflow_stage: str, policy: ReliabilityPolicy, tool_registry: Any,
           evidence_source: EvidenceSource | None) -> ShadowDecision:
    """Propose exactly one next reliability control; NEVER authorize a tool.

    Inputs must come from the current trusted runtime, tool registry, and auth
    scope. `task_snapshot['context']`, approval IDs embedded in steps, final
    summaries and `verification.verdict` are NOT security attestations.
    """
    if not isinstance(task_snapshot, dict):
        task_snapshot = {}
    task_id = task_snapshot.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        task_id = "<unknown>"
    version = policy.version
    def decide(tid: str, dom: str, ver: str, control: str, reasons: list[str],
               evidence: EvidenceSnapshot | None = None) -> ShadowDecision:
        return _result(tid, dom, ver, policy.digest, control, reasons,
                       evidence, stage=workflow_stage)

    if workflow_stage not in {"build", "review", "release"}:
        return decide(task_id, domain, version, "scope", ["unknown_or_missing_trusted_workflow_stage"])
    if not isinstance(tenant_id, str) or not tenant_id.strip() or task_id == "<unknown>":
        return decide(task_id, domain, version, "scope", ["missing_trusted_task_or_tenant_scope"])
    try:
        profile = policy.domain(domain)
    except ValueError:
        return decide(task_id, domain, version, "scope", ["unknown_domain_policy"])

    # Runtime/registry tools are the authority for tool risk, not an LLM's plan.
    plan = task_snapshot.get("plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        return decide(task_id, domain, version, "plan", ["missing_runtime_steps"])
    if not callable(getattr(tool_registry, "get", None)):
        return decide(task_id, domain, version, "tool", ["trusted_tool_registry_unavailable"])
    effect_ids = []
    step_ids = set()
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("step_id"), str):
            return decide(task_id, domain, version, "plan", ["invalid_runtime_step"])
        step_id = step["step_id"]
        if not step_id or step_id in step_ids:
            return decide(task_id, domain, version, "plan", ["duplicate_or_empty_step_id"])
        step_ids.add(step_id)
        tool_call = step.get("tool_call")
        name = tool_call.get("name") if isinstance(tool_call, dict) else None
        if not isinstance(name, str) or not name:
            return decide(task_id, domain, version, "plan", ["missing_tool_name"])
        spec = tool_registry.get(name)
        if spec is None:
            return decide(task_id, domain, version, "tool", ["unregistered_tool"])
        risk = getattr(spec, "risk", None)
        risk = getattr(risk, "value", risk)
        if risk == "blocked":
            return decide(task_id, domain, version, "tool", ["blocked_tool_in_plan"])
        if risk not in {"read", "write", "high_impact"}:
            return decide(task_id, domain, version, "tool", ["unknown_tool_risk"])
        if risk in {"write", "high_impact"}:
            effect_ids.append(step_id)

    if not isinstance(task_snapshot.get("goal"), str) or not task_snapshot["goal"].strip():
        return decide(task_id, domain, version, "plan", ["missing_objective"])
    criteria = plan.get("completion_criteria")
    if not isinstance(criteria, list) or not criteria or not all(isinstance(c, str) and c.strip() for c in criteria):
        return decide(task_id, domain, version, "plan", ["missing_finite_dod"])

    if evidence_source is None:
        return decide(task_id, domain, version, "evidence", ["authoritative_evidence_source_missing"])
    try:
        e = evidence_source.load(task_id=task_id, tenant_id=tenant_id,
                                 domain=domain, workflow_stage=workflow_stage,
                                 policy_digest=policy.digest)
    except Exception:
        # Never leak adapter failure details or convert outages into proof.
        return decide(task_id, domain, version, "evidence", ["authoritative_evidence_lookup_failed"])
    if (not isinstance(e, EvidenceSnapshot) or e.task_id != task_id
            or e.tenant_id != tenant_id or e.domain != domain
            or e.workflow_stage != workflow_stage or e.policy_digest != policy.digest):
        return decide(task_id, domain, version, "scope", ["evidence_scope_mismatch"])
    if e.ambiguous_step_ids:
        return decide(task_id, domain, version, "effect", ["unknown_external_effect_no_automatic_retry"], e)
    if not set(effect_ids).issubset(e.approved_step_ids):
        return decide(task_id, domain, version, "tool", ["effect_step_approval_not_independently_attested"], e)
    if not set(effect_ids).issubset(e.receipted_step_ids):
        return decide(task_id, domain, version, "effect", ["effect_receipt_not_independently_attested"], e)

    missing = sorted(profile.gates_for(workflow_stage) - e.verified_gate_ids)
    if missing or not e.evidence_refs or not e.revision:
        reasons = (["missing_verified_gates:" + ",".join(missing)] if missing else [])
        if not e.evidence_refs:
            reasons.append("missing_trusted_evidence_references")
        if not e.revision:
            reasons.append("missing_evidence_revision")
        return decide(task_id, domain, version, "evidence", reasons, e)
    missing_review = sorted(profile.reviews_for(workflow_stage) - e.reviewed_gate_ids)
    if missing_review:
        return decide(task_id, domain, version, "review",
                       ["missing_authoritative_human_review:" + ",".join(missing_review)], e)
    if task_snapshot.get("state") in {"failed", "cancelled"}:
        return decide(task_id, domain, version, "done",
                       ["terminal_task_not_successfully_completed"], e)
    if task_snapshot.get("state") != "completed":
        if task_snapshot.get("state") not in {"planned", "running", "waiting_approval"}:
            return decide(task_id, domain, version, "plan", ["unknown_runtime_state"], e)
        return decide(task_id, domain, version, "running", [], e)
    # A passing verdict is a shadow recommendation, NOT permission, a passed
    # production check, or a mutation of AgentTask.state/verification.
    return decide(task_id, domain, version, "done", [], e)
