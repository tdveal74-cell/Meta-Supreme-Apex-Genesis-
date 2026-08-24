"""Shared approval binding helpers for DEVON Agent Runtime adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

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
