"""Stage 2 record-shape and separate-DB readback tests; mocked DB rows only."""
from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.services.arf_evidence_source import (
    BoundEvidenceSource,
    EvidenceReadRefused,
    GateAttestations,
    collect_evidence,
    reconcile_records,
)
from app.services.agent_effect_receipts import arguments_hash
from services.agent_runtime.governance import (
    APPROVAL_MARKER_PREFIX,
    RUNTIME_REQUESTED_BY,
    approval_binding,
)

TENANT = "owner-01"
TASK = "TASK-3"
DOMAIN = "devon"
POLICY = "sha256-trusted-policy"


def setup():
    task = {"task_id": TASK, "goal": "perform exactly one governed write",
            "state": "completed", "plan": {"steps": [{
                "step_id": "step-1", "title": "write", "state": "completed",
                "approval_request_id": None,
                "tool_call": {"name": "repo.write", "arguments": {"path": "foo"}},
            }], "completion_criteria": ["result read back"]},
            "verification": {"verdict": "VERIFIED"},
            "context": {"approved": True, "verified_gates": ["all"]}}
    row = NS(id=TASK, owner_id=TENANT, state="completed", payload=task,
             updated_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
             execution_generation=1)
    intent = NS(id="EIR-1", intent_id="INT-1", owner_id=TENANT, task_id=TASK,
                step_id="step-1", tool_name="repo.write",
                arguments_hash=arguments_hash({"path": "foo"}),
                execution_generation=1, lease_token="lease-1")
    receipt = NS(id="ERR-1", intent_id="INT-1", owner_id=TENANT, task_id=TASK,
                 status="succeeded", execution_generation=1, lease_token="lease-1",
                 provider_receipt_id="PROVIDER-1")
    binding = approval_binding(task_id=TASK, step_id="step-1", tool_name="repo.write", arguments={"path": "foo"})
    approval = {"request_id": "REQ-1", "owner_id": TENANT,
                "requested_by": RUNTIME_REQUESTED_BY,
                "state": "consumed", "decided_by": "Tee",
                "what_happens": "Run tool repo.write. " + APPROVAL_MARKER_PREFIX + binding}
    gates = GateAttestations(TASK, TENANT, DOMAIN, "review", POLICY,
                             frozenset({"objective_defined"}), frozenset(),
                             ("gate:checked-1",), "QC-r1")
    return row, [intent], [receipt], [approval], gates


def reconcile(row=None, intents=None, receipts=None, approvals=None, gates=None):
    base = setup()
    vals = [base[i] if x is None else x for i, x in enumerate((row, intents, receipts, approvals, gates))]
    return reconcile_records(task_row=vals[0], intents=vals[1], receipts=vals[2],
                             approvals=vals[3], gates=vals[4], tenant_id=TENANT,
                             domain=DOMAIN, workflow_stage="review", policy_digest=POLICY)


class RowValidationTests(unittest.TestCase):
    def test_owner_scoped_matching_records_are_recognized(self):
        result = reconcile()
        self.assertEqual(result.approved_step_ids, {"step-1"})
        self.assertEqual(result.receipted_step_ids, {"step-1"})
        self.assertFalse(result.ambiguous_step_ids)
        self.assertIn("effect-receipt:ERR-1", result.evidence_refs)
        self.assertNotIn("verified_gates:all", str(result))

    def test_no_gate_reader_cannot_assert_domain_qc(self):
        row, intents, receipts, approvals, _ = setup()
        result = reconcile_records(task_row=row, intents=intents, receipts=receipts,
                                   approvals=approvals, gates=None, tenant_id=TENANT,
                                   domain=DOMAIN, workflow_stage="review", policy_digest=POLICY)
        self.assertEqual(result.verified_gate_ids, frozenset())
        self.assertEqual(result.reviewed_gate_ids, frozenset())

    def test_consumed_approval_required_not_merely_approved(self):
        row, intents, receipts, approvals, gates = setup()
        approvals[0]["state"] = "approved"
        self.assertFalse(reconcile(approvals=approvals).approved_step_ids)

    def test_approved_in_other_tenant_does_not_count(self):
        row, intents, receipts, approvals, gates = setup()
        approvals[0]["owner_id"] = "someone_else"
        self.assertFalse(reconcile(approvals=approvals).approved_step_ids)

    def test_fake_plan_approval_request_id_ignored(self):
        row, intents, receipts, approvals, gates = setup()
        row.payload["plan"]["steps"][0]["approval_request_id"] = "fake-req"
        self.assertFalse(reconcile(row=row, approvals=[]).approved_step_ids)

    def test_approval_binding_rejects_rewritten_arguments(self):
        row, intents, receipts, approvals, gates = setup()
        row.payload["plan"]["steps"][0]["tool_call"]["arguments"]["path"] = "other"
        with self.assertRaisesRegex(EvidenceReadRefused, "binding mismatch"):
            reconcile(row=row)

    def test_orphan_intent_blocks_automatic_retry(self):
        result = reconcile(receipts=[])
        self.assertEqual(result.ambiguous_step_ids, {"step-1"})
        self.assertEqual(result.receipted_step_ids, frozenset())

    def test_failed_receipt_does_not_count(self):
        row, intents, receipts, approvals, gates = setup()
        receipts[0].status = "failed"
        self.assertEqual(reconcile(receipts=receipts).ambiguous_step_ids, {"step-1"})

    def test_mismatched_lease_fence_does_not_count(self):
        row, intents, receipts, approvals, gates = setup()
        receipts[0].lease_token = "stale-lease"
        self.assertEqual(reconcile(receipts=receipts).ambiguous_step_ids, {"step-1"})

    def test_mismatched_execution_generation_does_not_count(self):
        row, intents, receipts, approvals, gates = setup()
        receipts[0].execution_generation = 2
        self.assertEqual(reconcile(receipts=receipts).ambiguous_step_ids, {"step-1"})

    def test_duplicate_intents_are_ambiguous(self):
        row, intents, receipts, approvals, gates = setup()
        extra = NS(**vars(intents[0]))
        extra.intent_id = "INT-2"
        self.assertEqual(reconcile(intents=intents + [extra]).ambiguous_step_ids, {"step-1"})

    def test_unexpected_receipt_refuses_collection(self):
        row, intents, receipts, approvals, gates = setup()
        receipts[0].intent_id = "FAKE"
        with self.assertRaisesRegex(EvidenceReadRefused, "orphan or duplicate"):
            reconcile(receipts=receipts)

    def test_duplicate_matching_approvals_refuses_collection(self):
        row, intents, receipts, approvals, gates = setup()
        other = copy.deepcopy(approvals[0])
        other["request_id"] = "REQ-2"
        with self.assertRaisesRegex(EvidenceReadRefused, "multiple matching"):
            reconcile(approvals=approvals + [other])

    def test_gate_scope_rejected(self):
        row, intents, receipts, approvals, gates = setup()
        with self.assertRaisesRegex(EvidenceReadRefused, "unscoped"):
            reconcile(gates=replace(gates, tenant_id="other"))
        with self.assertRaisesRegex(EvidenceReadRefused, "unscoped"):
            reconcile(gates=replace(gates, policy_digest="stale"))

    def test_wrong_owner_and_missing_task_rejected(self):
        row, intents, receipts, approvals, gates = setup()
        row.owner_id = "other"
        with self.assertRaisesRegex(EvidenceReadRefused, "owner"):
            reconcile(row=row)
        with self.assertRaisesRegex(EvidenceReadRefused, "owner"):
            reconcile(row=None if False else NS(id=TASK, owner_id="x"))

    def test_payload_completion_claim_does_not_mark_qc(self):
        result = reconcile()
        self.assertEqual(result.verified_gate_ids, {"objective_defined"})
        self.assertNotIn("VERIFIED", str(result))

    def test_bound_source_rejects_cross_domain_lookup(self):
        source = BoundEvidenceSource(reconcile())
        with self.assertRaisesRegex(EvidenceReadRefused, "scope mismatch"):
            source.load(task_id=TASK, tenant_id=TENANT, domain="tsws",
                        workflow_stage="review", policy_digest=POLICY)


class FakeResult:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
    def scalar_one_or_none(self):
        return self.row
    def scalars(self):
        return self
    def mappings(self):
        return self
    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return self.results.pop(0)


class StaticGateReader:
    def __init__(self, gates):
        self.gates = gates
    async def load_gates(self, **kwargs):
        return self.gates


class AsyncCollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_persisted_rows_including_separate_approval_db(self):
        row, intents, receipts, approvals, gates = setup()
        db = FakeSession([FakeResult(row=row), FakeResult(rows=intents), FakeResult(rows=receipts)])
        approval_db = FakeSession([FakeResult(rows=approvals)])
        saved, snapshot = await collect_evidence(db=db, approval_db=approval_db, task_id=TASK,
                                                   owner_id=TENANT, domain=DOMAIN,
                                                   workflow_stage="review", policy_digest=POLICY,
                                                   gate_reader=StaticGateReader(gates))
        self.assertEqual(saved, row.payload)
        self.assertIn("owner_id", db.calls[0][0])
        self.assertIn("owner_id", db.calls[1][0])
        self.assertIn("owner_id", db.calls[2][0])
        self.assertIn("FROM devon_approvals", approval_db.calls[0][0])
        self.assertEqual(approval_db.calls[0][1]["owner"], TENANT)
        self.assertEqual(snapshot.approved_step_ids, {"step-1"})

    async def test_missing_approval_database_fails_closed_for_approval(self):
        row, intents, receipts, approvals, gates = setup()
        db = FakeSession([FakeResult(row=row), FakeResult(rows=intents), FakeResult(rows=receipts)])
        _, snapshot = await collect_evidence(db=db, approval_db=None, task_id=TASK,
                                              owner_id=TENANT, domain=DOMAIN,
                                              workflow_stage="review", policy_digest=POLICY)
        self.assertFalse(snapshot.approved_step_ids)
        self.assertFalse(snapshot.verified_gate_ids)

    async def test_db_exception_is_not_forged_as_empty_success(self):
        class BrokenDb:
            async def execute(self, *args, **kwargs):
                raise OSError("db unavailable")
        with self.assertRaises(OSError):
            await collect_evidence(db=BrokenDb(), approval_db=None, task_id=TASK,
                                   owner_id=TENANT, domain=DOMAIN,
                                   workflow_stage="review", policy_digest=POLICY)


class EndToEndShadowTests(unittest.IsolatedAsyncioTestCase):
    async def test_persisted_task_with_partial_qc_would_hold(self):
        from pathlib import Path

        from app.services.arf_evidence_source import observe_persisted_task
        from services.agent_runtime.reliability import ReliabilityPolicy
        p = ReliabilityPolicy.from_json(Path(__file__).resolve().parents[2] / 'policies/reliability/profiles.v1.json')
        row, intents, receipts, approvals, gates = setup()
        gates = replace(gates, policy_digest=p.digest)
        db = FakeSession([FakeResult(row=row), FakeResult(rows=intents), FakeResult(rows=receipts)])
        ap = FakeSession([FakeResult(rows=approvals)])
        result = await observe_persisted_task(db=db, approval_db=ap, owner_id=TENANT,
                         task_id=TASK, domain=DOMAIN, workflow_stage='review', policy=p,
                         tool_registry=RegistryWrite(), gate_reader=StaticGateReader(gates))
        self.assertEqual(result.verdict, 'WOULD_HOLD')
        self.assertEqual(result.selected_control, 'evidence_gate')
        self.assertIn('missing_verified_gates:', result.blocking_reasons[0])

    async def test_no_qc_adapter_never_signs_off_completion(self):
        from pathlib import Path

        from app.services.arf_evidence_source import observe_persisted_task
        from services.agent_runtime.reliability import ReliabilityPolicy
        p = ReliabilityPolicy.from_json(Path(__file__).resolve().parents[2] / 'policies/reliability/profiles.v1.json')
        row, intents, receipts, approvals, gates = setup()
        db = FakeSession([FakeResult(row=row), FakeResult(rows=intents), FakeResult(rows=receipts)])
        ap = FakeSession([FakeResult(rows=approvals)])
        result = await observe_persisted_task(db=db, approval_db=ap, owner_id=TENANT,
                         task_id=TASK, domain=DOMAIN, workflow_stage='review', policy=p,
                         tool_registry=RegistryWrite(), gate_reader=None)
        self.assertEqual(result.verdict, 'WOULD_HOLD')
        self.assertNotEqual(result.selected_control, 'completion_gate')


class RegistryWrite:
    def get(self, name):
        return NS(risk='write') if name == 'repo.write' else None


if __name__ == "__main__":
    unittest.main()
