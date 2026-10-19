"""Versioned deterministic held-out suite for declarative receipt-policy skills.

This checks decision-table execution, not natural-language skill quality. The
runner interprets a closed JSON policy format; it executes no candidate code.
"""
import hashlib
import json

SUITE_ID = "receipt-decision-policy"
SUITE_VERSION = "1"


def run_receipt_policy(description: str, instructions: str) -> dict:
    policy = json.loads(instructions)
    if not isinstance(policy, dict) or set(policy) != {"format", "rules", "default"}:
        raise ValueError("unsupported declarative policy format")
    if policy["format"] != "receipt-policy-v1" or policy["default"] != "UNVERIFIED":
        raise ValueError("policy must fail closed")
    rules = policy["rules"]
    allowed = {"verified", "failed", "missing"}
    if not isinstance(rules, dict) or set(rules) != allowed:
        raise ValueError("policy must define all receipt states")
    if any(value not in {"VERIFIED", "FAILED", "UNVERIFIED"} for value in rules.values()):
        raise ValueError("unknown verdict")
    fixtures = (("heldout:receipt:verified:v1", "verified", "VERIFIED"),
                ("heldout:receipt:failed:v1", "failed", "FAILED"),
                ("heldout:receipt:absent:v1", "missing", "UNVERIFIED"),
                ("heldout:receipt:unknown:v1", "unknown", "UNVERIFIED"))
    return {"scope": "deterministic receipt decision contract only",
            "training_task_ids": [], "heldout_task_ids": [f[0] for f in fixtures],
            "checks": [{"task_id": task, "passed": rules.get(state, policy["default"]) == expected}
                       for task, state, expected in fixtures]}


def content_hash(description: str, instructions: str) -> str:
    return hashlib.sha256(json.dumps([description, instructions], ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def validate_runner_evidence(evidence: dict, *, source_task_id: str) -> None:
    heldout = evidence.get("heldout_task_ids", [])
    training = evidence.get("training_task_ids", [])
    checks = evidence.get("checks", [])
    if (not heldout or not checks or not isinstance(heldout, list)
            or not isinstance(training, list) or not isinstance(checks, list)):
        raise ValueError("nonempty held-out tasks and deterministic checks required")
    if len(set(heldout)) != len(heldout) or set(heldout) & (set(training) | {source_task_id}):
        raise ValueError("held-out task leakage")
    if any(not isinstance(c, dict) or c.get("passed") is not True
           or c.get("task_id") not in heldout for c in checks):
        raise ValueError("held-out checks failed or unverified")
    if set(c["task_id"] for c in checks) != set(heldout):
        raise ValueError("every held-out task requires a check")

