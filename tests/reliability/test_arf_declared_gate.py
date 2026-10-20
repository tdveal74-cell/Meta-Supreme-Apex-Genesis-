"""Adversarial contract tests for ARF's narrow deterministic receipt bridge."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace as NS

from app.services.agent_effect_receipts import arguments_hash
from app.services.arf_declared_gate import RuntimeDeclaredChecksGateReader, verify_declared_gate
from app.services.arf_evidence_source import EvidenceReadRefused
from services.agent_runtime.verification import canonical, digest

OWNER = "owner-A"
TASK = "TASK-1"
CHECK = {"id": "required-1", "step_id": "S1", "kind": "tool_succeeded", "expected": {}}


def fixture():
    captured = {"schema_version": 1, "tool": "repo.inspect", "step_id": "S1",
                "arguments_hash": arguments_hash({"path": "safe.txt"}),
                "ok": True, "output": "ok", "error": "", "metadata": {}, "elapsed_ms": 1.0}
    result_body = canonical(captured)
    result_row = NS(id="RESULT-1", owner_id=OWNER, task_id=TASK, step_id="S1",
                    generation=3, body=result_body, content_hash=digest(result_body))
    evidence_ref = result_row.id + ":" + result_row.content_hash
    verification = {"verdict": "VERIFIED", "scope": "declared_checks_only",
                    "checker_version": "runtime-checks-v1", "plan_completed": True,
                    "checks": [{"requirement_id": "required-1", "verdict": "VERIFIED", "evidence_ref": evidence_ref}]}
    receipt_body = canonical({"verification": verification})
    receipt_row = NS(id="VERIFY-1", owner_id=OWNER, task_id=TASK, generation=3,
                     body=receipt_body, content_hash=digest(receipt_body))
    payload = {"task_id": TASK, "goal": "Inspect safe file", "state": "completed",
               "verification_requirements": [CHECK.copy()],
               "plan": {"steps": [{"step_id": "S1", "tool_call": {
                   "name": "repo.inspect", "arguments": {"path": "safe.txt"}}}]},
               "verification": {"verdict": "VERIFIED", "receipt_id": receipt_row.id,
                                "receipt_sha256": receipt_row.content_hash}}
    task_row = NS(id=TASK, owner_id=OWNER, state="completed", execution_generation=3,
                  payload=payload)
    return task_row, receipt_row, [result_row]


def attest(task=None, receipt=None, results=None):
    original = fixture()
    return verify_declared_gate(
        task=original[0] if task is None else task,
        receipt=original[1] if receipt is None else receipt,
        results=original[2] if results is None else results,
        task_id=TASK, tenant_id=OWNER, domain="devon", workflow_stage="build",
        policy_digest="f" * 64,
    )


class ReceiptBridgeTests(unittest.TestCase):
    def test_recomputes_a_real_declared_check_only(self):
        decision = attest()
        self.assertEqual(decision.verified_gates, frozenset({"requirement_evidence"}))
        self.assertFalse(decision.reviewed_gates)
        self.assertNotIn("source_provenance", decision.verified_gates)
        self.assertEqual(len(decision.evidence_refs), 2)
        self.assertEqual(len(decision.revision), 64)

    def test_empty_receipt_makes_no_positive_claim(self):
        task, _, _ = fixture()
        task.payload["verification"].pop("receipt_id")
        self.assertFalse(attest(task=task).verified_gates)

    def test_empty_checks_make_no_positive_claim(self):
        task, _, _ = fixture()
        task.payload["verification_requirements"] = []
        self.assertFalse(attest(task=task).verified_gates)

    def test_incomplete_task_makes_no_positive_claim(self):
        task, _, _ = fixture()
        task.state = task.payload["state"] = "running"
        self.assertFalse(attest(task=task).verified_gates)

    def test_owner_scope_is_required(self):
        task, _, _ = fixture()
        task.owner_id = "another-owner"
        with self.assertRaisesRegex(EvidenceReadRefused, "owner"):
            attest(task=task)

    def test_stale_generation_receipt_refused(self):
        _, receipt, _ = fixture()
        receipt.generation = 2
        with self.assertRaisesRegex(EvidenceReadRefused, "binding"):
            attest(receipt=receipt)

    def test_forged_verification_bytes_refused(self):
        _, receipt, _ = fixture()
        receipt.body = receipt.body.replace("VERIFIED", "UNVERIFIED")
        with self.assertRaisesRegex(EvidenceReadRefused, "hash"):
            attest(receipt=receipt)

    def test_corrupted_captured_result_refused(self):
        _, _, results = fixture()
        results[0].body += " "
        with self.assertRaisesRegex(EvidenceReadRefused, "integrity"):
            attest(results=results)

    def test_mismatched_current_plan_arguments_refused(self):
        task, receipt, results = fixture()
        task.payload["plan"]["steps"][0]["tool_call"]["arguments"]["path"] = "other"
        with self.assertRaisesRegex(EvidenceReadRefused, "plan"):
            attest(task=task, receipt=receipt, results=results)

    def test_forged_report_with_correct_hash_still_recomputed(self):
        _, receipt, results = fixture()
        result = results[0]
        bad = json.loads(result.body)
        bad["ok"] = False
        result.body = canonical(bad)
        result.content_hash = digest(result.body)
        # Even if attacker updates the report to cite its new hash, negative
        # tool result must not be treated as a passing check.
        report = json.loads(receipt.body)
        report["verification"]["checks"][0]["evidence_ref"] = result.id + ":" + result.content_hash
        receipt.body = canonical(report)
        receipt.content_hash = digest(receipt.body)
        task, _, _ = fixture()
        task.payload["verification"]["receipt_sha256"] = receipt.content_hash
        with self.assertRaisesRegex(EvidenceReadRefused, "disagree"):
            attest(task=task, receipt=receipt, results=results)

    def test_duplicate_results_fail_closed(self):
        _, _, results = fixture()
        with self.assertRaisesRegex(EvidenceReadRefused, "duplicate"):
            attest(results=results + results)

    def test_result_from_other_generation_refused(self):
        _, _, results = fixture()
        results[0].generation = 5
        with self.assertRaisesRegex(EvidenceReadRefused, "unscoped"):
            attest(results=results)

    def test_missing_captured_result_refused(self):
        with self.assertRaisesRegex(EvidenceReadRefused, "missing independently"):
            attest(results=[])

    def test_report_does_not_supply_missing_requirements(self):
        task, receipt, results = fixture()
        task.payload["verification_requirements"].append({"id":"required-2", "step_id":"S1", "kind":"tool_succeeded", "expected":{}})
        with self.assertRaisesRegex(EvidenceReadRefused, "checklist"):
            attest(task=task, receipt=receipt, results=results)

    def test_recorder_does_not_claim_human_review(self):
        result = attest()
        self.assertEqual(result.reviewed_gates, frozenset())


class ReadOnlyAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_queries_are_owner_and_task_scoped(self):
        task, receipt, results = fixture()

        class FakeScalars:
            def all(self):
                return results

        class SpyDB:
            def __init__(self):
                self.statements = []
                self.count = 0

            async def scalar(self, statement):
                self.statements.append(str(statement))
                self.count += 1
                return task if self.count == 1 else receipt

            async def scalars(self, statement):
                self.statements.append(str(statement))
                return FakeScalars()

        db = SpyDB()
        result = await RuntimeDeclaredChecksGateReader(db).load_gates(
            task_id=TASK, tenant_id=OWNER, domain="devon", workflow_stage="build",
            policy_digest="f" * 64,
        )
        self.assertIn("requirement_evidence", result.verified_gates)
        self.assertEqual(len(db.statements), 3)
        for statement in db.statements:
            self.assertIn("owner_id", statement)
            self.assertIn("task_id" if "agent_tasks" not in statement else "id", statement)


if __name__ == "__main__":
    unittest.main()
