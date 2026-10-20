"""Portable ARF retry genealogy and strategy-change tests."""
import unittest

from services.agent_runtime.reliability.lineage import (
    HistoryConflict,
    HistoryEvent,
    advise_retry,
    fingerprint,
    review_history,
)

F = fingerprint(hypothesis="Network timeout", expected_evidence="provider receipt",
                target_failure="render failed", intended_outcome="deliver clip")
G = fingerprint(hypothesis="Security policy", expected_evidence="lease receipt",
                target_failure="approval fails", intended_outcome="read only")
DIGEST = "a"*64


def event(i, *, who="owner1", root="ROOT1", task="T1", fp=F, outcome=DIGEST,
          rev="r0", parent="", delegated="", attempt=None):
    return HistoryEvent(f"EV{i}", who, root, task, parent, delegated,
                        fp, outcome, rev, "root_cause_validator", i if attempt is None else attempt)


class LineageTests(unittest.TestCase):
    def test_fingerprint_stable_across_handoff(self):
        self.assertEqual(F, fingerprint(hypothesis=" network timeout ", expected_evidence="provider receipt",
                                        target_failure="render failed", intended_outcome="deliver clip"))

    def test_blank_failure_identity_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint(hypothesis="", expected_evidence="x", target_failure="y", intended_outcome="z")

    def test_first_occurrence_is_diagnosis_not_approval(self):
        result = advise_retry([], owner_id="owner1", root_task_id="ROOT1",
                              failure_fingerprint=F, outcome_digest=DIGEST, evidence_revision="r0")
        self.assertEqual(result.verdict, "CONTINUE_DIAGNOSIS")

    def test_equivalent_attempts_require_new_strategy(self):
        e = [event(1), event(2, parent="EV1")]
        result = advise_retry(e, owner_id="owner1", root_task_id="ROOT1",
                              failure_fingerprint=F, outcome_digest=DIGEST, evidence_revision="r0")
        self.assertEqual(result.verdict, "CHANGE_STRATEGY")

    def test_three_attempts_escalate_even_with_revision_churn(self):
        prior = [event(1, rev="r1"), event(2, parent="EV1", rev="r2"),
                 event(3, parent="EV2", rev="r3")]
        result = advise_retry(prior, owner_id="owner1", root_task_id="ROOT1",
                              failure_fingerprint=F, outcome_digest="b" * 64,
                              evidence_revision="r4")
        self.assertEqual(result.verdict, "REVIEW_REQUIRED")
        self.assertEqual(result.matching_attempts, 3)

    def test_three_unchanged_attempts_escalate(self):
        e = [event(1), event(2, parent="EV1"), event(3, parent="EV2")]
        result = advise_retry(e, owner_id="owner1", root_task_id="ROOT1",
                              failure_fingerprint=F, outcome_digest=DIGEST, evidence_revision="r0")
        self.assertEqual(result.verdict, "REVIEW_REQUIRED")

    def test_changed_evidence_is_meaningful(self):
        e = [event(1), event(2, parent="EV1")]
        result = advise_retry(e, owner_id="owner1", root_task_id="ROOT1",
                              failure_fingerprint=F, outcome_digest=DIGEST, evidence_revision="provider-fixed")
        self.assertEqual(result.verdict, "CONTINUE_DIAGNOSIS")

    def test_resetting_counter_across_agents_is_rejected(self):
        e = [event(1), event(2, task="subagent", parent="EV1", attempt=1)]
        with self.assertRaisesRegex(HistoryConflict, "counter reset"):
            review_history(e, owner_id="owner1", root_task_id="ROOT1")

    def test_missing_ancestry_is_not_a_new_root(self):
        with self.assertRaisesRegex(HistoryConflict, "unknown ancestor"):
            review_history([event(1, parent="UNKNOWN")], owner_id="owner1", root_task_id="ROOT1")

    def test_cross_tenant_history_is_refused(self):
        with self.assertRaisesRegex(HistoryConflict, "cross-tenant"):
            review_history([event(1, who="other")], owner_id="owner1", root_task_id="ROOT1")

    def test_duplicate_event_id_refused(self):
        with self.assertRaisesRegex(HistoryConflict, "duplicated"):
            review_history([event(1), event(1, attempt=2)], owner_id="owner1", root_task_id="ROOT1")

    def test_different_failure_has_independent_counter(self):
        e = [event(1), event(2, fp=G, attempt=1)]
        self.assertEqual(len(review_history(e, owner_id="owner1", root_task_id="ROOT1")), 2)

    def test_change_of_task_id_does_not_erase_history(self):
        e = [event(1), event(2, task="different-agent", delegated="EV1")]
        self.assertEqual(advise_retry(e, owner_id="owner1", root_task_id="ROOT1",
                         failure_fingerprint=F, outcome_digest=DIGEST,
                         evidence_revision="r0").matching_attempts, 2)


if __name__ == "__main__":
    unittest.main()
