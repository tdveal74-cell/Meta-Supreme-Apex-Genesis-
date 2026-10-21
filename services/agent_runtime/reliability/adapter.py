"""Pure post-run adapter for DEVON's existing AgentRuntime result contract.

Use this as a read-only instrumentation seam AFTER an already-authorized
AgentRuntime call. It does not call run_next(), request approval, or execute.
"""
from __future__ import annotations

from typing import Any

from .contracts import EvidenceSource, ShadowDecision
from .observer import assess
from .policy import ReliabilityPolicy


def observe_runtime_result(runtime_result: Any, *, domain: str, tenant_id: str,
                           workflow_stage: str, policy: ReliabilityPolicy, tool_registry: Any,
                           evidence_source: EvidenceSource | None) -> ShadowDecision:
    """Accept real RuntimeResult.task.to_dict() without trusting model claims."""
    task = getattr(runtime_result, "task", None)
    serializer = getattr(task, "to_dict", None)
    try:
        snapshot = serializer() if callable(serializer) else {}
    except Exception:
        snapshot = {}
    return assess(snapshot, domain=domain, tenant_id=tenant_id,
                  workflow_stage=workflow_stage, policy=policy, tool_registry=tool_registry,
                  evidence_source=evidence_source)
