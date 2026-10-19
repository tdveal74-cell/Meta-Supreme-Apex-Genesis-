"""Pure, fail-closed adapter for advisory Markup AI results. Not wired to production."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any


def normalize(text: str, brand: str, required_agents: Sequence[str],
              raw: Mapping[str, Any] | None, *, voice_profile: str | None = None,
              style_guide: str | None = None) -> dict:
    """Capture check coverage and risk, never any permission to release."""
    if not text.strip() or not brand.strip() or not required_agents:
        raise ValueError("Text, brand and required agents are mandatory")
    if len(set(required_agents)) != len(required_agents):
        raise ValueError("Required agents must be unique")
    receipt = {
        "brand": brand,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "markup_ai_status": "NOT_RUN",
        "agents_required": list(required_agents),
        "agents_completed": [],
        "warnings": [],
        "issues": [],
        "script_doctor_score": None,
        "release_approved": False,
    }
    if raw is None:
        receipt["warnings"].append("Review not run")
        return receipt
    if not isinstance(raw, Mapping):
        receipt["markup_ai_status"] = "INCOMPLETE"
        receipt["warnings"].append("Malformed result envelope")
        return receipt
    checked = raw.get("checked")
    results = raw.get("results")
    warnings = raw.get("warnings")
    if not isinstance(checked, Mapping) or not isinstance(results, list) or not isinstance(warnings, list):
        receipt["markup_ai_status"] = "INCOMPLETE"
        receipt["warnings"].append("Missing checked, results or warnings")
        return receipt
    for warning in warnings:
        receipt["warnings"].append(str(warning.get("code", "warning")) if isinstance(warning, Mapping) else "Invalid warning")
    if checked.get("characters") != len(text):
        receipt["warnings"].append("Reviewed character count mismatch")
    if voice_profile and checked.get("voice_profile") != voice_profile:
        receipt["warnings"].append("Voice profile mismatch")
    if style_guide and checked.get("style_guide") != style_guide:
        receipt["warnings"].append("Style guide mismatch")
    recorded = checked.get("agents_run")
    if not isinstance(recorded, list) or not set(required_agents).issubset(set(recorded)):
        receipt["warnings"].append("Requested agent list not confirmed")
    completed = set()
    for item in results:
        if not isinstance(item, Mapping) or not isinstance(item.get("agent"), str) or not isinstance(item.get("issues"), list):
            receipt["warnings"].append("Malformed agent result")
            continue
        name = item["agent"]
        if name in completed:
            receipt["warnings"].append("Duplicate agent result")
            continue
        completed.add(name)
        for issue in item["issues"]:
            if not isinstance(issue, Mapping):
                receipt["warnings"].append("Malformed issue")
                continue
            pos = issue.get("position", {})
            if not isinstance(pos, Mapping):
                pos = {}
            start, end = pos.get("start"), pos.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or end > len(text):
                receipt["warnings"].append("Invalid issue range")
            receipt["issues"].append({
                "agent": name,
                "severity": str(issue.get("severity", "unknown")),
                "category": str(issue.get("category", "unknown")),
                "start": start,
                "end": end,
            })
    receipt["agents_completed"] = sorted(completed)
    missing = sorted(set(required_agents) - completed)
    if missing:
        receipt["warnings"].append("Missing agents: " + ", ".join(missing))
    receipt["markup_ai_status"] = (
        "INCOMPLETE" if receipt["warnings"]
        else "EDITORIAL_ISSUES" if receipt["issues"]
        else "EDITORIAL_CLEAR"
    )
    return receipt
