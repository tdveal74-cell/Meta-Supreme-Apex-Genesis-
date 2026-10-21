"""Cryptographic fixtures prove admission behavior, never live gain."""

import base64
import copy
import json
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.devon_rsi.kernel import canonical, digest
from tools.devon_rsi_ops.experiments import (
    ATTESTATION_SCHEMA,
    SCHEMA,
    admit_protocol,
    assess_trials,
    review_recommendation,
)

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
FROZEN = "2026-10-21T00:00:00Z"
EXPIRY = "2026-10-22T00:00:00Z"


class Evidence:
    """Fixture signing is intentionally confined to the test boundary."""

    def __init__(self):
        self.private = {name: Ed25519PrivateKey.generate() for name in ("verifier", "reviewer")}
        self.keys = {
            name: {"issuer_id": name, "public_key_hex": key.public_key().public_bytes_raw().hex(),
                   "roles": ["human_reviewer" if name == "reviewer" else "independent_verifier"],
                   "revoked": False}
            for name, key in self.private.items()
        }
        self.protocol = {
            "schema": SCHEMA, "experiment_id": "experiment_1", "surface": "routing_policy",
            "producer_id": "maker", "producer_session_id": "maker_session",
            "baseline_sha256": digest("baseline"), "candidate_sha256": digest("candidate"),
            "suite_sha256": digest("suite"), "scorer_sha256": digest("scorer"),
            "sources": [{"kind": kind, "ref": "https://github.com/fixture/docs/" + kind,
                         "version": "fixture-commit", "sha256": digest(kind), "observed_at": FROZEN}
                        for kind in ("charter", "canon", "reflections")],
            "cases": [{"id": "case_" + str(i), "critical": i == 0} for i in range(4)],
            "blocks": [{"id": "block_" + str(i), "sample_sha256": digest(["sample", i])}
                       for i in range(20)],
            "comparisons": 1, "frozen_at": FROZEN, "expires_at": EXPIRY,
            "holdout": "private_blind", "mode": "live_control",
        }
        self.freeze_body = self.body("freeze", "freeze_session", FROZEN)
        self.freeze_body.update(sources_verified=True, holdout_blind=True, independence_plan_verified=True)
        self.trial_bodies = []
        for i, block in enumerate(self.protocol["blocks"]):
            body = self.body("trial", "trial_session", "2026-10-21T02:00:00Z")
            body.update(block_id=block["id"], sample_sha256=block["sample_sha256"],
                        control_run_id="control_" + str(i), candidate_run_id="candidate_" + str(i),
                        started_at="2026-10-21T01:00:00Z", finished_at="2026-10-21T01:01:00Z",
                        mode="live_control", holdout_blind=True, independence_verified=True,
                        baseline=self.rows(i, False), candidate=self.rows(i, True))
            self.trial_bodies.append(body)

    def body(self, purpose, session, issued, issuer="verifier"):
        return {"schema": ATTESTATION_SCHEMA, "purpose": purpose, "issuer_id": issuer,
                "session_id": session, "issued_at": issued, "expires_at": EXPIRY,
                "protocol_sha256": digest(self.protocol)}

    def rows(self, block, candidate):
        # Alternating noncritical gains and one tie supply genuine test variance.
        return [{**case, "passed": candidate or i == 0 or block == 19 or i > 1 + block % 2,
                 "output_sha256": digest([block, candidate, i])}
                for i, case in enumerate(self.protocol["cases"])]

    def sign(self, body, key="verifier"):
        raw = canonical(body)
        return {"key_id": key, "payload": raw.decode(),
                "signature": base64.b64encode(self.private[key].sign(raw)).decode()}

    def freeze(self):
        return self.sign(self.freeze_body)

    def trials(self):
        return [self.sign(body) for body in self.trial_bodies]

    def rebind(self):
        for body in [self.freeze_body, *self.trial_bodies]:
            body["protocol_sha256"] = digest(self.protocol)

    def admit(self):
        return admit_protocol(self.protocol, self.freeze(), self.keys, now=NOW)

    def assess(self):
        return assess_trials(self.protocol, self.freeze(), self.trials(), self.keys, now=NOW)

    def review(self, **changes):
        body = self.body("review", "human_session", "2026-10-21T03:00:00Z", "reviewer")
        body.update(decision_sha256=digest(self.assess()), verdict="APPROVE_RECOMMENDATION")
        body.update(changes)
        return review_recommendation(self.protocol, self.freeze(), self.trials(),
                                     self.sign(body, "reviewer"), self.keys, now=NOW)


@pytest.fixture
def evidence():
    return Evidence()


def held(result, reason=None):
    assert result["state"] == "HOLD", result
    if reason:
        assert result["reason"] == reason, result
    assert result["gain_claim"] is False
    assert result["promoted"] is False
    assert result["production_effects"] == []


def test_signed_complete_experiment_and_review_remain_recommendations(evidence):
    assert evidence.admit()["state"] == "ADMITTED_FOR_CONTROLLED_TRIALS"
    decision = evidence.assess()
    assert decision["state"] == "ACCEPT_FOR_HUMAN_REVIEW"
    assert decision["statistics"]["statistical_signal"] is True
    assert decision["statistics"]["claim"] is False
    assert decision["blocks"] == 20
    reviewed = evidence.review()
    assert reviewed["state"] == "REVIEWED_RECOMMENDATION"
    assert reviewed["external_authorization_required"] is True
    for result in (decision, reviewed):
        assert result["gain_claim"] is False
        assert result["promoted"] is False
        assert result["production_effects"] == []


def test_empty_operator_registry_holds(evidence):
    evidence.keys.clear()
    held(evidence.admit(), "EXTERNAL_SIGNER_REQUIRED")
    held(evidence.assess(), "EXTERNAL_SIGNER_REQUIRED")


def test_same_signing_key_cannot_alias_an_independent_reviewer(evidence):
    evidence.keys["reviewer"]["public_key_hex"] = evidence.keys["verifier"]["public_key_hex"]
    held(evidence.admit(), "REGISTRY_IDENTITY_ALIAS")
    held(evidence.assess(), "REGISTRY_IDENTITY_ALIAS")


@pytest.mark.parametrize("field", ["candidate_sha256", "baseline_sha256", "suite_sha256", "scorer_sha256"])
def test_freeze_binds_exact_artifacts(evidence, field):
    evidence.protocol[field] = digest("swapped")
    held(evidence.admit(), "ATTESTATION_BINDING")


def test_freeze_binds_sources_comparisons_and_plan(evidence):
    for field, value in (("comparisons", 2), ("cases", evidence.protocol["cases"][:-1]),
                         ("blocks", list(reversed(evidence.protocol["blocks"])))):
        old = evidence.protocol[field]
        evidence.protocol[field] = value
        held(evidence.admit(), "ATTESTATION_BINDING")
        evidence.protocol[field] = old
    evidence.protocol["sources"][0]["sha256"] = digest("rewritten")
    held(evidence.admit(), "ATTESTATION_BINDING")


@pytest.mark.parametrize("kind", ["charter", "canon", "reflections"])
def test_missing_current_authoritative_sources_hold(evidence, kind):
    evidence.protocol["sources"] = [s for s in evidence.protocol["sources"] if s["kind"] != kind]
    evidence.rebind()
    held(evidence.admit(), "AUTHORITATIVE_SOURCES_REQUIRED")


@pytest.mark.parametrize("ref", ["file:///live/vault", "http://github.com/doc", "https://evil.example/doc",
                                 "https://user:pass@github.com/doc", "https://github.com/"])
def test_source_provenance_requires_operator_verifiable_reference(evidence, ref):
    evidence.protocol["sources"][0]["ref"] = ref
    evidence.rebind()
    held(evidence.admit(), "SOURCE_REF")


def test_stale_source_or_unverified_source_holds(evidence):
    evidence.protocol["sources"][0]["observed_at"] = "2026-10-01T00:00:00Z"
    evidence.rebind()
    held(evidence.admit(), "STALE_SOURCE_OBSERVATION")
    evidence.protocol["sources"][0]["observed_at"] = FROZEN
    evidence.rebind()
    evidence.freeze_body["sources_verified"] = False
    held(evidence.admit(), "INDEPENDENT_ADMISSION_REQUIRED")


@pytest.mark.parametrize("surface", ["canon", "charter", "standing_authorizations", "evaluation_gates", "secrets"])
def test_closed_surfaces_cannot_be_admitted(evidence, surface):
    evidence.protocol["surface"] = surface
    evidence.rebind()
    held(evidence.admit(), "SURFACE_OR_SCHEMA")


@pytest.mark.parametrize("change,reason", [
    ({"revoked": True}, "KEY_REVOKED_OR_INVALID"),
    ({"roles": ["human_reviewer"]}, "SIGNER_ROLE"),
    ({"issuer_id": "maker"}, "INDEPENDENCE"),
])
def test_external_key_registry_role_revocation_identity(evidence, change, reason):
    evidence.keys["verifier"].update(change)
    if "issuer_id" in change:
        evidence.freeze_body["issuer_id"] = change["issuer_id"]
    held(evidence.admit(), reason)


def test_wrong_private_key_signature_and_tampered_payload_hold(evidence):
    signed = evidence.freeze()
    signed["signature"] = evidence.sign(evidence.freeze_body, "reviewer")["signature"]
    held(admit_protocol(evidence.protocol, signed, evidence.keys, now=NOW), "SIGNATURE")
    signed = evidence.freeze()
    signed["payload"] = signed["payload"].replace("freeze_session", "spoof_session")
    held(admit_protocol(evidence.protocol, signed, evidence.keys, now=NOW), "SIGNATURE")


def test_identity_purpose_and_session_spoofing_hold(evidence):
    evidence.freeze_body["issuer_id"] = "unregistered_identity"
    held(evidence.admit(), "INDEPENDENCE")
    evidence.freeze_body["issuer_id"] = "verifier"
    evidence.freeze_body["session_id"] = "maker_session"
    held(evidence.admit(), "INDEPENDENCE")
    evidence.freeze_body["session_id"] = "freeze_session"
    evidence.freeze_body["purpose"] = "trial"
    held(evidence.admit(), "ATTESTATION_BINDING")


@pytest.mark.parametrize("timestamp", ["invalid", "2026-10-21T00:00:00", "2026-10-21T00:00:00+02:00"])
def test_invalid_timestamps_hold(evidence, timestamp):
    evidence.protocol["frozen_at"] = timestamp
    evidence.rebind()
    held(evidence.admit(), "TIMESTAMP")


def test_expired_future_and_posthoc_freeze_hold(evidence):
    evidence.freeze_body["expires_at"] = "2026-10-21T10:00:00Z"
    held(evidence.admit(), "ATTESTATION_TIME")
    evidence.freeze_body["expires_at"] = EXPIRY
    evidence.freeze_body["issued_at"] = "2026-10-21T13:00:00Z"
    held(evidence.admit(), "ATTESTATION_TIME")
    evidence.freeze_body["issued_at"] = "2026-10-21T01:00:00Z"
    held(evidence.admit(), "FREEZE_TIME")


@pytest.mark.parametrize("value", [True, 0, -1, 33, 1.0, "1"])
def test_multiple_comparison_count_cannot_be_relaxed(evidence, value):
    evidence.protocol["comparisons"] = value
    evidence.rebind()
    held(evidence.admit(), "COMPARISONS")


def test_minimum_independent_block_count_is_fixed(evidence):
    evidence.protocol["blocks"].pop()
    evidence.rebind()
    held(evidence.admit(), "BLOCK_COUNT")


def test_reused_samples_in_frozen_plan_hold(evidence):
    evidence.protocol["blocks"][1]["sample_sha256"] = evidence.protocol["blocks"][0]["sample_sha256"]
    evidence.rebind()
    held(evidence.admit(), "BLOCK_INDEPENDENCE")


@pytest.mark.parametrize("field", ["baseline", "candidate"])
def test_missing_reordered_or_untyped_case_results_hold(evidence, field):
    rows = evidence.trial_bodies[0][field]
    evidence.trial_bodies[0][field] = rows[:-1]
    held(evidence.assess(), "INCOMPLETE_SUITE")
    evidence.trial_bodies[0][field] = list(reversed(rows))
    held(evidence.assess(), "RESULT_SCHEMA")
    evidence.trial_bodies[0][field] = rows
    rows[0]["passed"] = 1
    held(evidence.assess(), "RESULT_SCHEMA")


def test_critical_failure_veto_includes_shared_baseline_failure(evidence):
    for rows in ("baseline", "candidate"):
        evidence.trial_bodies[0][rows][0]["passed"] = False
    result = evidence.assess()
    assert result["state"] == "REJECT"
    assert result["reason"] == "CRITICAL_FAILURE"
    assert result["gain_claim"] is False


def test_critical_label_cannot_be_removed_by_trial(evidence):
    evidence.trial_bodies[0]["candidate"][0]["critical"] = False
    held(evidence.assess(), "RESULT_SCHEMA")


def test_noncritical_regression_veto(evidence):
    evidence.trial_bodies[0]["candidate"][3]["passed"] = False
    result = evidence.assess()
    assert result["state"] == "REJECT"
    assert result["reason"] == "REGRESSION"


@pytest.mark.parametrize("field,value,reason", [
    ("mode", "fixture", "LIVE_BLIND_EVIDENCE_REQUIRED"),
    ("holdout_blind", False, "LIVE_BLIND_EVIDENCE_REQUIRED"),
    ("independence_verified", False, "LIVE_BLIND_EVIDENCE_REQUIRED"),
    ("session_id", "freeze_session", "TRIAL_SESSION_INDEPENDENCE"),
    ("session_id", "maker_session", "INDEPENDENCE"),
    ("started_at", FROZEN, "TRIAL_PRECEDES_FREEZE"),
    ("sample_sha256", digest("other"), "BLOCK_BINDING"),
])
def test_fixture_nonindependent_or_posthoc_trials_hold(evidence, field, value, reason):
    evidence.trial_bodies[0][field] = value
    held(evidence.assess(), reason)


def test_complete_blocks_duplicate_receipt_and_reused_run_hold(evidence):
    trials = evidence.trials()
    held(assess_trials(evidence.protocol, evidence.freeze(), trials[:-1], evidence.keys, now=NOW), "INCOMPLETE_BLOCKS")
    trials[1] = trials[0]
    held(assess_trials(evidence.protocol, evidence.freeze(), trials, evidence.keys, now=NOW), "REPLAYED_RECEIPT")
    evidence.trial_bodies[1]["control_run_id"] = evidence.trial_bodies[0]["control_run_id"]
    held(evidence.assess(), "RUN_REPLAY")


def test_different_receipt_cannot_reuse_block(evidence):
    evidence.trial_bodies[1]["block_id"] = evidence.trial_bodies[0]["block_id"]
    evidence.trial_bodies[1]["sample_sha256"] = evidence.trial_bodies[0]["sample_sha256"]
    held(evidence.assess(), "BLOCK_BINDING")


def test_constant_delta_is_not_gain(evidence):
    for trial in evidence.trial_bodies:
        for i, row in enumerate(trial["baseline"]):
            row["passed"] = i != 1
    held(evidence.assess(), "NO_VARIANCE")


def test_multiple_comparison_correction_uses_predeclared_count(evidence):
    # Six wins and fourteen ties: one-sided p=1/64 passes .05 but not .05/4.
    for i, trial in enumerate(evidence.trial_bodies):
        for j, row in enumerate(trial["baseline"]):
            row["passed"] = i >= 6 or j != 1
    assert evidence.assess()["state"] == "ACCEPT_FOR_HUMAN_REVIEW"
    evidence.protocol["comparisons"] = 4
    evidence.rebind()
    held(evidence.assess(), "NO_SIGNIFICANT_GAIN")


def test_input_order_does_not_change_frozen_decision(evidence):
    before = evidence.assess()
    evidence.trial_bodies.reverse()
    assert evidence.assess() == before


def test_review_exact_decision_and_distinct_human_identity(evidence):
    held(evidence.review(decision_sha256=digest("other_decision")), "REVIEW_DECISION_BINDING")
    held(evidence.review(session_id="trial_session"), "REVIEW_INDEPENDENCE")
    evidence.keys["reviewer"]["issuer_id"] = "verifier"
    held(evidence.review(issuer_id="verifier"), "REVIEW_INDEPENDENCE")


def test_review_rejection_and_temporal_order(evidence):
    assert evidence.review(verdict="REJECT")["state"] == "REJECT"
    held(evidence.review(issued_at="2026-10-21T01:30:00Z"), "REVIEW_PRECEDES_TRIALS")
    held(evidence.review(verdict="PROMOTE"), "REVIEW_VERDICT")


def test_review_cannot_skip_admission(evidence):
    evidence.trial_bodies[0]["candidate"][0]["passed"] = False
    held(evidence.review(), "ADMISSIBLE_DECISION_REQUIRED")


@pytest.mark.parametrize("api", [admit_protocol, assess_trials, review_recommendation])
def test_clock_schema_failure_always_holds(evidence, api):
    middle = [] if api is admit_protocol else [evidence.trials()]
    if api is review_recommendation:
        middle.append({})
    held(api(evidence.protocol, evidence.freeze(), *middle, evidence.keys, now="not-a-clock"), "CLOCK")


def test_schema_unknown_fields_payload_bounds_and_noncanonical_json_hold(evidence):
    evidence.protocol["minimum_blocks"] = 1
    held(evidence.admit(), "PROTOCOL_SCHEMA")
    del evidence.protocol["minimum_blocks"]
    signed = evidence.freeze()
    signed["payload"] = "x" * 70000
    held(admit_protocol(evidence.protocol, signed, evidence.keys, now=NOW), "INPUT_SCHEMA")
    signed = evidence.freeze()
    signed["payload"] = json.dumps(evidence.freeze_body)
    held(admit_protocol(evidence.protocol, signed, evidence.keys, now=NOW), "NONCANONICAL_ATTESTATION")
    signed["payload"] = '{"schema":1,"schema":2}'
    held(admit_protocol(evidence.protocol, signed, evidence.keys, now=NOW), "DUPLICATE_KEY")


def test_nan_and_alias_mutation_cannot_modify_callers_inputs(evidence):
    before = copy.deepcopy(evidence.protocol)
    evidence.assess()
    assert evidence.protocol == before
    evidence.protocol["comparisons"] = float("nan")
    held(evidence.admit(), "INPUT_SCHEMA")
