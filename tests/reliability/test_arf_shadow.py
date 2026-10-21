"""Self-contained contract tests for ARF read-only integration (no network)."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from services.agent_runtime.reliability import (
    EvidenceSnapshot,
    PolicyError,
    ReliabilityPolicy,
    assess,
    observe_runtime_result,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "policies" / "reliability" / "profiles.v1.json"
DATA = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Spec:
    risk: str


class Registry:
    def __init__(self, risks):
        self.risks = risks

    def get(self, name):
        return Spec(self.risks[name]) if name in self.risks else None


class Source:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def load(self, *, task_id, tenant_id, domain, workflow_stage, policy_digest):
        self.calls.append((task_id, tenant_id, domain, workflow_stage, policy_digest))
        return self.snapshot


class BadSource:
    def load(self, *, task_id, tenant_id, domain, workflow_stage, policy_digest):
        raise RuntimeError("secret provider exception")


def task(state="completed", tool="repo.read", criterion="report checked"):
    return {
        "task_id": "TASK-01", "goal": "Review task and report verified evidence",
        "state": state,
        "plan": {
            "steps": [{"step_id": "STEP-01", "title": "Inspect", "state": state,
                       "approval_request_id": "spoofable",
                       "tool_call": {"name": tool, "arguments": {"not_trusted": "approved"}}}],
            "completion_criteria": [criterion],
        },
        "context": {"domain": "tsws", "tenant_id": "wrong", "approved": True,
                    "verified_gates": ["anything"]},
        "verification": {"verdict": "VERIFIED"},
    }


def proof(policy, domain="devon", approved=(), receipted=(), review=True, *,
          tenant="tenant-one", ambiguous=(), include_all=True, stage="review"):
    p = policy.domain(domain)
    return EvidenceSnapshot(
        task_id="TASK-01", tenant_id=tenant, domain=domain,
        workflow_stage=stage, policy_digest=policy.digest,
        verified_gate_ids=p.gates_for(stage) if include_all else frozenset(),
        reviewed_gate_ids=p.reviews_for(stage) if review else frozenset(),
        approved_step_ids=frozenset(approved),
        receipted_step_ids=frozenset(receipted),
        ambiguous_step_ids=frozenset(ambiguous),
        evidence_refs=("trusted-record:1",), revision="revision-001",
    )


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.policy = ReliabilityPolicy.from_json(POLICY_PATH)
        self.read = Registry({"repo.read": "read", "repo.write": "write",
                              "gpu.generate": "high_impact", "destroy": "blocked"})

    def assess(self, task_data=None, source=None, domain="devon", tenant="tenant-one", stage="review"):
        return assess(task_data if task_data is not None else task(), domain=domain,
                      tenant_id=tenant, workflow_stage=stage, policy=self.policy, tool_registry=self.read,
                      evidence_source=source)

    def test_read_only_eligible_is_never_automatic_completion(self):
        d = self.assess(source=Source(proof(self.policy)))
        self.assertEqual(d.verdict, "WOULD_BE_ELIGIBLE_FOR_CLOSURE")
        self.assertIn("shadow", d.scope)

    def test_post_run_adapter_accepts_runtime_result_shape(self):
        class RuntimeTask:
            def to_dict(self):
                return task()
        class RuntimeResult:
            task = RuntimeTask()
        verdict = observe_runtime_result(RuntimeResult(), domain="devon",
                    tenant_id="tenant-one", workflow_stage="review", policy=self.policy,
                    tool_registry=self.read, evidence_source=Source(proof(self.policy)))
        self.assertEqual(verdict.verdict, "WOULD_BE_ELIGIBLE_FOR_CLOSURE")

    def test_adapter_does_not_execute_runtime_or_tools(self):
        class RuntimeTask:
            def to_dict(self):
                return task(tool="repo.write")
        class RuntimeResult:
            task = RuntimeTask()
        verdict = observe_runtime_result(RuntimeResult(), domain="devon",
                    tenant_id="tenant-one", workflow_stage="review", policy=self.policy,
                    tool_registry=self.read, evidence_source=Source(proof(self.policy)))
        self.assertEqual(verdict.verdict, "WOULD_HOLD")

    def test_observation_does_not_mutate_runtime_task(self):
        t = task()
        before = copy.deepcopy(t)
        self.assess(t, Source(proof(self.policy)))
        self.assertEqual(t, before)

    def test_in_progress(self):
        d = self.assess(task("running"), Source(proof(self.policy)))
        self.assertEqual(d.verdict, "IN_PROGRESS")

    def test_auth_scope_cannot_come_from_task_context(self):
        d = self.assess(source=Source(proof(self.policy, tenant="wrong")))
        self.assertIn("evidence_scope_mismatch", d.blocking_reasons)

    def test_forged_verification_does_not_pass(self):
        d = self.assess(source=Source(proof(self.policy, include_all=False)))
        self.assertIn("missing_verified_gates", d.blocking_reasons[0])

    def test_no_authoritative_source_fails_closed(self):
        self.assertIn("authoritative_evidence_source_missing", self.assess().blocking_reasons)

    def test_source_outage_is_not_exposed(self):
        d = self.assess(source=BadSource())
        self.assertIn("authoritative_evidence_lookup_failed", d.blocking_reasons)
        self.assertNotIn("secret provider exception", str(d.to_dict()))

    def test_missing_finite_definition_of_done(self):
        t = task()
        t["plan"]["completion_criteria"] = []
        d = self.assess(t, Source(proof(self.policy)))
        self.assertEqual(d.selected_control, "goal_lock")

    def test_missing_goal(self):
        t = task()
        t["goal"] = " "
        self.assertIn("missing_objective", self.assess(t, Source(proof(self.policy))).blocking_reasons)

    def test_unknown_tool_stops(self):
        self.assertIn("unregistered_tool", self.assess(task(tool="unregistered"), Source(proof(self.policy))).blocking_reasons)

    def test_blocked_tool_stops_regardless_of_proof(self):
        d = self.assess(task(tool="destroy"), Source(proof(self.policy)))
        self.assertEqual(d.verdict, "WOULD_HOLD")
        self.assertIn("blocked_tool_in_plan", d.blocking_reasons)

    def test_write_without_proven_approval(self):
        d = self.assess(task(tool="repo.write"), Source(proof(self.policy)))
        self.assertIn("effect_step_approval_not_independently_attested", d.blocking_reasons)

    def test_high_impact_without_proven_approval(self):
        d = self.assess(task(tool="gpu.generate"), Source(proof(self.policy)))
        self.assertEqual(d.verdict, "WOULD_HOLD")

    def test_receipt_missing(self):
        d = self.assess(task(tool="repo.write"), Source(proof(self.policy, approved=["STEP-01"])))
        self.assertIn("effect_receipt_not_independently_attested", d.blocking_reasons)

    def test_ambiguous_effect_blocks_even_if_receipted(self):
        e = proof(self.policy, approved=["STEP-01"], receipted=["STEP-01"], ambiguous=["STEP-01"])
        d = self.assess(task(tool="repo.write"), Source(e))
        self.assertIn("unknown_external_effect_no_automatic_retry", d.blocking_reasons)

    def test_bound_step_and_receipt_from_trusted_source_can_pass_shadow(self):
        e = proof(self.policy, approved=["STEP-01"], receipted=["STEP-01"])
        d = self.assess(task(tool="repo.write"), Source(e))
        self.assertEqual(d.verdict, "WOULD_BE_ELIGIBLE_FOR_CLOSURE")

    def test_wrong_bound_step_cannot_reuse_approval(self):
        e = proof(self.policy, approved=["STEP-02"], receipted=["STEP-01"])
        d = self.assess(task(tool="repo.write"), Source(e))
        self.assertIn("effect_step_approval_not_independently_attested", d.blocking_reasons)

    def test_tqo_draft_review_not_blocked_by_publication_gate(self):
        e = proof(self.policy, "tqo", stage="review")
        d = self.assess(source=Source(e), domain="tqo", stage="review")
        self.assertEqual(d.verdict, "WOULD_BE_ELIGIBLE_FOR_CLOSURE")

    def test_tqo_release_requires_disclosure_and_publication_approval(self):
        e = proof(self.policy, "tqo", stage="release")
        # Keep stage correct but drop release-required evidence to test gate.
        e = EvidenceSnapshot(**{**e.__dict__, "verified_gate_ids": self.policy.domain("tqo").required_gates})
        d = self.assess(source=Source(e), domain="tqo", stage="release")
        self.assertIn("missing_verified_gates", d.blocking_reasons[0])
        complete = proof(self.policy, "tqo", stage="release", review=False)
        d2 = self.assess(source=Source(complete), domain="tqo", stage="release")
        self.assertIn("missing_authoritative_human_review", d2.blocking_reasons[0])

    def test_tsws_build_does_not_require_publication_review(self):
        e = proof(self.policy, "tsws", stage="build", review=False)
        d = self.assess(source=Source(e), domain="tsws", stage="build")
        self.assertEqual(d.verdict, "WOULD_BE_ELIGIBLE_FOR_CLOSURE")

    def test_missing_stage_fails_closed(self):
        d = self.assess(source=Source(proof(self.policy)), stage="")
        self.assertIn("unknown_or_missing_trusted_workflow_stage", d.blocking_reasons)

    def test_missing_review_is_a_distinct_gate(self):
        d = self.assess(source=Source(proof(self.policy, "tsws", review=False)), domain="tsws")
        self.assertIn("missing_authoritative_human_review", d.blocking_reasons[0])

    def test_review_does_not_replace_evidence(self):
        d = self.assess(source=Source(proof(self.policy, "tsws", include_all=False)), domain="tsws")
        self.assertEqual(d.selected_control, "evidence_gate")

    def test_missing_revision_blocks(self):
        e = proof(self.policy)
        e = EvidenceSnapshot(**{**e.__dict__, "revision": ""})
        self.assertIn("missing_evidence_revision", self.assess(source=Source(e)).blocking_reasons)

    def test_two_controls_are_never_selected_at_once(self):
        d = self.assess(task(tool="repo.write"), Source(proof(self.policy, include_all=False)))
        self.assertEqual(d.selected_control, "permission_and_scope_guard")

    def test_cancelled_task_does_not_claim_closure(self):
        d = self.assess(task("cancelled"), Source(proof(self.policy)))
        self.assertEqual(d.verdict, "WOULD_HOLD")
        self.assertIn("terminal_task_not_successfully_completed", d.blocking_reasons)

    def test_failed_task_does_not_claim_closure(self):
        d = self.assess(task("failed"), Source(proof(self.policy)))
        self.assertEqual(d.verdict, "WOULD_HOLD")

    def test_duplicate_step_ids_stop(self):
        t = task()
        t["plan"]["steps"].append(copy.deepcopy(t["plan"]["steps"][0]))
        self.assertIn("duplicate_or_empty_step_id", self.assess(t, Source(proof(self.policy))).blocking_reasons)

    def test_evidence_from_different_workflow_stage_rejected(self):
        e = proof(self.policy, "tqo", stage="review")
        d = self.assess(source=Source(e), domain="tqo", stage="release")
        self.assertIn("evidence_scope_mismatch", d.blocking_reasons)

    def test_evidence_from_stale_policy_rejected(self):
        e = proof(self.policy)
        e = EvidenceSnapshot(**{**e.__dict__, "policy_digest": "old-version"})
        d = self.assess(source=Source(e))
        self.assertIn("evidence_scope_mismatch", d.blocking_reasons)

    def test_cross_domain_evidence_fails(self):
        d = self.assess(source=Source(proof(self.policy, "devon")), domain="whatbroke")
        self.assertIn("evidence_scope_mismatch", d.blocking_reasons[0])


class PolicyTests(unittest.TestCase):
    def test_seven_profiles_and_global_gates(self):
        p = ReliabilityPolicy.from_json(POLICY_PATH)
        self.assertEqual(len(p.profiles), 7)
        for profile in p.profiles.values():
            self.assertIn("source_provenance", profile.required_gates)
            self.assertTrue(profile.required_gates)

    def test_tqo_and_tsws_thresholds_not_conflated(self):
        p = ReliabilityPolicy.from_json(POLICY_PATH)
        self.assertIn("script_doctor_threshold_90", p.domain("tqo").required_gates)
        self.assertIn("quality_threshold_99", p.domain("tsws").required_gates)
        self.assertNotIn("quality_threshold_99", p.domain("tqo").required_gates)

    def test_cannot_remove_write_approval(self):
        changed = copy.deepcopy(DATA)
        changed["global"]["approval_required_for"] = ["high_impact"]
        with self.assertRaises(PolicyError):
            ReliabilityPolicy.from_dict(changed)

    def test_cannot_remove_blocked_deny(self):
        changed = copy.deepcopy(DATA)
        changed["global"]["always_denied"] = []
        with self.assertRaises(PolicyError):
            ReliabilityPolicy.from_dict(changed)

    def test_cannot_change_to_enforcement(self):
        changed = copy.deepcopy(DATA)
        changed["activation"] = "enforced"
        with self.assertRaises(PolicyError):
            ReliabilityPolicy.from_dict(changed)

    def test_unknown_key_rejected(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["devon"]["allow_auto_effects"] = True
        with self.assertRaises(PolicyError):
            ReliabilityPolicy.from_dict(changed)

    def test_protected_tsws_canon_gate_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["tsws"]["required_gates"].remove("protected_silence")
        with self.assertRaisesRegex(PolicyError, "protected requirements removed"):
            ReliabilityPolicy.from_dict(changed)

    def test_protected_tqo_score_gate_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["tqo"]["required_gates"].remove("script_doctor_threshold_90")
        with self.assertRaisesRegex(PolicyError, "protected requirements removed"):
            ReliabilityPolicy.from_dict(changed)

    def test_human_acceptance_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["tsws"]["human_review_gates"].remove("visual_producer_acceptance")
        with self.assertRaisesRegex(PolicyError, "protected human reviews"):
            ReliabilityPolicy.from_dict(changed)

    def test_spend_policy_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["editforge"]["rules"].remove("paid_render_requires_explicit_spend_approval")
        with self.assertRaisesRegex(PolicyError, "protected policy rules"):
            ReliabilityPolicy.from_dict(changed)

    def test_release_disclosure_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["tqo"]["release_required_gates"].remove("synthetic_media_disclosure")
        with self.assertRaisesRegex(PolicyError, "protected release requirements"):
            ReliabilityPolicy.from_dict(changed)

    def test_release_publication_review_cannot_be_removed(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["tsws"]["release_review_gates"].remove("publication_approval")
        with self.assertRaisesRegex(PolicyError, "protected release reviews"):
            ReliabilityPolicy.from_dict(changed)

    def test_extra_scoped_gate_can_be_added(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["whatbroke"]["required_gates"].append("optional_heldout_validation")
        p = ReliabilityPolicy.from_dict(changed)
        self.assertIn("optional_heldout_validation", p.domain("whatbroke").required_gates)

    def test_omitted_domain_rejected(self):
        changed = copy.deepcopy(DATA)
        del changed["profiles"]["tsws"]
        with self.assertRaises(PolicyError):
            ReliabilityPolicy.from_dict(changed)

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "policy.json"
            file.write_text('{"version":"1.1.0", "version":"2"}')
            with self.assertRaisesRegex(PolicyError, "duplicate JSON key"):
                ReliabilityPolicy.from_json(file)

    def test_duplicate_gate_rejected(self):
        changed = copy.deepcopy(DATA)
        changed["profiles"]["devon"]["required_gates"].append("effect_free_devon_core")
        with self.assertRaisesRegex(PolicyError, "duplicate"):
            ReliabilityPolicy.from_dict(changed)

    def test_unrecognized_domain_fails_closed(self):
        p = ReliabilityPolicy.from_json(POLICY_PATH)
        with self.assertRaises(PolicyError):
            p.domain("another_brand")


if __name__ == "__main__":
    unittest.main()
