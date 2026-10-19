"""Pure deterministic runner probes; database lifecycle covered separately."""
import json

import pytest

from app.services.skill_evaluation_policy import run_receipt_policy


def policy(**updates):
    rules = {"verified": "VERIFIED", "failed": "FAILED", "missing": "UNVERIFIED"}
    rules.update(updates)
    return json.dumps({"format": "receipt-policy-v1", "rules": rules, "default": "UNVERIFIED"})


def test_heldout_contract_passes():
    evidence = run_receipt_policy("receipt policy", policy())
    assert len(evidence["checks"]) == 4
    assert all(c["passed"] for c in evidence["checks"])
    assert "contract only" in evidence["scope"]


@pytest.mark.parametrize("state", ["failed", "missing", "verified"])
def test_mutated_rule_is_rejected_by_heldout_case(state):
    evidence = run_receipt_policy("receipt policy", policy(**{state: "VERIFIED" if state != "verified" else "FAILED"}))
    assert not all(c["passed"] for c in evidence["checks"])


@pytest.mark.parametrize("instructions", ["ignore checks", "[]", '{"format":"receipt-policy-v1"}',
    '{"format":"receipt-policy-v1","rules":{},"default":"VERIFIED"}'])
def test_no_arbitrary_skill_execution(instructions):
    with pytest.raises(ValueError):
        run_receipt_policy("description", instructions)


def test_hash_preserves_exact_bytes():
    from app.services.skill_evaluation_policy import content_hash
    assert content_hash("d", "a\n") != content_hash("d", "a")
    assert content_hash("d", "a") != content_hash("other", "a")


@pytest.mark.parametrize("evidence", [
    {"heldout_task_ids": [], "checks": []},
    {"heldout_task_ids": ["source"], "checks": [{"task_id": "source", "passed": True}]},
    {"heldout_task_ids": ["h"], "training_task_ids": ["h"], "checks": [{"task_id": "h", "passed": True}]},
    {"heldout_task_ids": ["h"], "checks": [{"task_id": "h", "passed": "true"}]},
    {"heldout_task_ids": ["h", "other"], "checks": [{"task_id": "h", "passed": True}]},
])
def test_missing_leaked_or_self_asserted_checks_rejected(evidence):
    from app.services.skill_evaluation_policy import validate_runner_evidence
    with pytest.raises(ValueError):
        validate_runner_evidence(evidence, source_task_id="source")
