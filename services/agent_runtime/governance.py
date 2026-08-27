"""Shared approval binding helpers for DEVON Agent Runtime adapters."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Tuple

from services.devon.approval import ApprovalQueue, ApprovalState

APPROVAL_METADATA_KEY = "_devon_runtime_approval"
APPROVAL_MARKER_PREFIX = "DEVON-RUNTIME-BINDING:"
RUNTIME_REQUESTED_BY = "DEVON Agent Runtime"


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
    *,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Tuple[str, str]:
    """Verify the approved record is bound to these exact effect arguments.

    Metadata from the runtime is not trusted as proof by itself. The capability
    boundary recomputes the SHA-256 binding from the task identity, step identity,
    known tool name, and the arguments it is about to use, then compares that
    value to both the runtime metadata and the authoritative DEVON approval
    consequence.
    """
    if not isinstance(metadata, dict):
        raise ValueError("runtime approval metadata is missing")

    request_id = str(metadata.get("request_id") or "").strip()
    supplied_binding = str(metadata.get("binding") or "").strip()
    task_id = str(metadata.get("task_id") or "").strip()
    step_id = str(metadata.get("step_id") or "").strip()
    metadata_tool = str(metadata.get("tool_name") or "").strip()
    clean_tool = (tool_name or "").strip()

    if not request_id or not supplied_binding or not task_id or not step_id or not metadata_tool:
        raise ValueError("runtime approval metadata is incomplete")
    if not clean_tool or not hmac.compare_digest(metadata_tool, clean_tool):
        raise ValueError("runtime approval metadata names a different tool")

    expected_binding = approval_binding(
        task_id=task_id,
        step_id=step_id,
        tool_name=clean_tool,
        arguments=arguments,
    )
    if not hmac.compare_digest(supplied_binding, expected_binding):
        raise ValueError("runtime approval binding does not match these arguments")

    record = approvals.get(request_id)
    if record is None:
        raise ValueError("runtime approval request no longer exists")
    if record.state is not ApprovalState.APPROVED:
        raise ValueError(f"approval state is {record.state.value}, not approved")
    if record.requested_by != RUNTIME_REQUESTED_BY:
        raise ValueError("approval request was not raised by DEVON Agent Runtime")
    if approval_marker(expected_binding) not in record.what_happens:
        raise ValueError("runtime approval binding does not match this effect")

    # Last, and only once everything else has passed. Until this line an
    # approval was a standing permission: APPROVED and bound to these arguments
    # were both permanently true, so the same governed effect could be replayed
    # forever by anyone still holding the metadata. Spending it here makes it
    # permission to do one thing once.
    #
    # This runs BEFORE the handler, which means an effect whose handler then
    # fails leaves the approval spent and needs a fresh one. That is deliberate.
    # The alternative is to spend it afterwards, which leaves a live approval
    # sitting behind a half-finished effect, and a partial write is exactly the
    # situation where a silent replay does the most damage.
    spent = approvals.consume(request_id)
    if not spent.ok:
        raise ValueError(
            f"runtime approval could not be spent: {spent.message}"
        )
    return request_id, expected_binding
