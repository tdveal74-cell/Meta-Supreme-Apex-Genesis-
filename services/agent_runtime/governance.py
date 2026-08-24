"""Shared approval binding helpers for DEVON Agent Runtime adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

from services.devon.approval import ApprovalQueue, ApprovalState

APPROVAL_METADATA_KEY = "_devon_runtime_approval"
APPROVAL_MARKER_PREFIX = "DEVON-RUNTIME-BINDING:"


def approval_binding(
    *,
    task_id: str,
    step_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> str:
    payload = {
        "task_id": task_id,
        "step_id": step_id,
        "tool": tool_name,
        "arguments": arguments,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approval_marker(binding: str) -> str:
    return f"{APPROVAL_MARKER_PREFIX}{binding}"


def require_approved_runtime_binding(
    approvals: ApprovalQueue,
    metadata: object,
) -> Tuple[str, str]:
    """Verify adapter metadata against the exact approved DEVON consequence."""
    if not isinstance(metadata, dict):
        raise ValueError("runtime approval metadata is missing")
    request_id = str(metadata.get("request_id") or "").strip()
    binding = str(metadata.get("binding") or "").strip()
    if not request_id or not binding:
        raise ValueError("runtime approval metadata is incomplete")

    record = approvals.get(request_id)
    if record is None:
        raise ValueError("runtime approval request no longer exists")
    if record.state is not ApprovalState.APPROVED:
        raise ValueError(f"approval state is {record.state.value}, not approved")
    if approval_marker(binding) not in record.what_happens:
        raise ValueError("runtime approval binding does not match this effect")
    return request_id, binding
