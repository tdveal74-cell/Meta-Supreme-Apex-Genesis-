"""Admission for externally attested live experiments; no signing or promotion.

The caller supplies an operator-controlled public-key registry. Candidates must
never supply or edit that registry. Signatures authenticate a verifier's claim,
not its truth: the external verifier remains accountable for source authority,
blindness and run independence. Empty registries and missing evidence hold.

Ed25519 API: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tools.devon_rsi.kernel import Refused, canonical, decide, digest, gain_evidence, strict_load

SCHEMA = "devon-rsi-experiment-v1"
ATTESTATION_SCHEMA = "devon-rsi-attestation-v1"
SURFACES = frozenset({"review_policy", "routing_policy", "capture_policy", "operator_policy", "health_policy"})
MIN_BLOCKS, MAX_BLOCKS, MAX_CASES, MAX_COMPARISONS = 20, 256, 500, 32
SOURCE_KINDS = frozenset({"charter", "canon", "reflections"})
COMMON = {"schema", "purpose", "issuer_id", "session_id", "issued_at", "expires_at", "protocol_sha256"}
PROTOCOL_KEYS = {"schema", "experiment_id", "surface", "producer_id", "producer_session_id",
                 "baseline_sha256", "candidate_sha256", "suite_sha256", "scorer_sha256",
                 "sources", "cases", "blocks", "comparisons", "frozen_at", "expires_at",
                 "holdout", "mode"}
PURPOSE_KEYS = {
    "freeze": {"sources_verified", "holdout_blind", "independence_plan_verified"},
    "trial": {"block_id", "sample_sha256", "control_run_id", "candidate_run_id",
              "started_at", "finished_at", "mode", "holdout_blind", "independence_verified",
              "baseline", "candidate"},
    "review": {"decision_sha256", "verdict"},
}


def _need(value, code):
    if not value:
        raise Refused(code)


def _shape(value, keys, code):
    _need(isinstance(value, dict) and set(value) == keys, code)


def _id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) is not None


def _sha(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _time(value):
    _need(type(value) is str and 20 <= len(value) <= 35, "TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refused("TIMESTAMP") from None
    _need(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), "TIMESTAMP")
    return parsed


def _now(value):
    if value is None:
        return datetime.now(timezone.utc)
    _need(isinstance(value, datetime) and value.tzinfo is not None
          and value.utcoffset() == timedelta(0), "CLOCK")
    return value


def _copy(value):
    # Also rejects overlarge, non-JSON, nonfinite and deeply nested input.
    try:
        return strict_load(canonical(value))
    except (TypeError, ValueError, RecursionError):
        raise Refused("INPUT_SCHEMA") from None


def _protocol(value, now):
    p = _copy(value)
    _shape(p, PROTOCOL_KEYS, "PROTOCOL_SCHEMA")
    _need(p["schema"] == SCHEMA and p["surface"] in SURFACES, "SURFACE_OR_SCHEMA")
    _need(all(_id(p[k]) for k in ("experiment_id", "producer_id", "producer_session_id")), "IDENTITY")
    _need(all(_sha(p[k]) for k in ("baseline_sha256", "candidate_sha256", "suite_sha256", "scorer_sha256")), "FINGERPRINT")
    _need(p["candidate_sha256"] != p["baseline_sha256"], "IDENTICAL_CANDIDATE")
    _need(p["mode"] == "live_control" and p["holdout"] == "private_blind", "LIVE_BLIND_EVIDENCE_REQUIRED")
    frozen, expires = _time(p["frozen_at"]), _time(p["expires_at"])
    _need(frozen <= now < expires and timedelta(0) < expires - frozen <= timedelta(days=30), "PROTOCOL_TIME")
    _need(type(p["comparisons"]) is int and 1 <= p["comparisons"] <= MAX_COMPARISONS, "COMPARISONS")
    _need(isinstance(p["sources"], list) and len(p["sources"]) == len(SOURCE_KINDS), "AUTHORITATIVE_SOURCES_REQUIRED")
    kinds = set()
    for source in p["sources"]:
        _shape(source, {"kind", "ref", "version", "sha256", "observed_at"}, "SOURCE_SCHEMA")
        _need(type(source["kind"]) is str and source["kind"] in SOURCE_KINDS
              and source["kind"] not in kinds, "AUTHORITATIVE_SOURCES_REQUIRED")
        kinds.add(source["kind"])
        _need(type(source["ref"]) is str and len(source["ref"]) <= 1000, "SOURCE_REF")
        parsed = urlsplit(source["ref"])
        _need(parsed.scheme == "https" and parsed.hostname in {
            "drive.google.com", "notion.so", "www.notion.so", "github.com", "raw.githubusercontent.com"
        } and parsed.username is None and parsed.password is None and bool(parsed.path.strip("/")), "SOURCE_REF")
        _need(type(source["version"]) is str and 0 < len(source["version"].strip()) <= 100
              and _sha(source["sha256"]), "SOURCE_VERSION")
        observed = _time(source["observed_at"])
        _need(frozen - timedelta(days=7) <= observed <= frozen, "STALE_SOURCE_OBSERVATION")
    _need(isinstance(p["cases"], list) and 1 <= len(p["cases"]) <= MAX_CASES, "CASE_COUNT")
    ids = set()
    for case in p["cases"]:
        _shape(case, {"id", "critical"}, "CASE_SCHEMA")
        _need(_id(case["id"]) and case["id"] not in ids and type(case["critical"]) is bool, "CASE_SCHEMA")
        ids.add(case["id"])
    _need(any(c["critical"] for c in p["cases"]), "CRITICAL_CASE_REQUIRED")
    _need(isinstance(p["blocks"], list) and MIN_BLOCKS <= len(p["blocks"]) <= MAX_BLOCKS, "BLOCK_COUNT")
    ids, samples = set(), set()
    for block in p["blocks"]:
        _shape(block, {"id", "sample_sha256"}, "BLOCK_SCHEMA")
        _need(_id(block["id"]) and block["id"] not in ids and _sha(block["sample_sha256"])
              and block["sample_sha256"] not in samples, "BLOCK_INDEPENDENCE")
        ids.add(block["id"])
        samples.add(block["sample_sha256"])
    return p


def _signed(envelope, purpose, p, keys, now):
    e = _copy(envelope)
    _shape(e, {"key_id", "payload", "signature"}, "ATTESTATION_SCHEMA")
    _need(_id(e["key_id"]) and isinstance(keys, dict) and e["key_id"] in keys, "EXTERNAL_SIGNER_REQUIRED")
    _need(len(keys) <= 64, "KEY_REGISTRY_CAPACITY")
    public_keys = set()
    for registered in keys.values():
        _need(isinstance(registered, dict) and _sha(registered.get("public_key_hex")), "KEY_REGISTRY_SCHEMA")
        public_key = registered["public_key_hex"]
        _need(public_key not in public_keys, "REGISTRY_IDENTITY_ALIAS")
        public_keys.add(public_key)
    key = _copy(keys[e["key_id"]])
    _shape(key, {"issuer_id", "public_key_hex", "roles", "revoked"}, "KEY_REGISTRY_SCHEMA")
    _need(_id(key["issuer_id"]) and _sha(key["public_key_hex"]) and key["revoked"] is False, "KEY_REVOKED_OR_INVALID")
    role = "human_reviewer" if purpose == "review" else "independent_verifier"
    _need(isinstance(key["roles"], list) and key["roles"] and set(key["roles"]) <= {
        "independent_verifier", "human_reviewer"
    } and role in key["roles"], "SIGNER_ROLE")
    _need(type(e["payload"]) is str and type(e["signature"]) is str and len(e["signature"]) == 88, "ATTESTATION_SCHEMA")
    raw = e["payload"].encode("utf-8")
    body = strict_load(raw)
    _need(canonical(body) == raw, "NONCANONICAL_ATTESTATION")
    try:
        signature = base64.b64decode(e["signature"], validate=True)
        _need(len(signature) == 64, "SIGNATURE")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key["public_key_hex"])).verify(signature, raw)
    except (ValueError, InvalidSignature, UnsupportedAlgorithm, binascii.Error):
        raise Refused("SIGNATURE") from None
    _shape(body, COMMON | PURPOSE_KEYS[purpose], "ATTESTATION_PAYLOAD")
    _need(body["schema"] == ATTESTATION_SCHEMA and body["purpose"] == purpose
          and body["protocol_sha256"] == digest(p), "ATTESTATION_BINDING")
    _need(body["issuer_id"] == key["issuer_id"] and _id(body["session_id"])
          and body["issuer_id"] != p["producer_id"]
          and body["session_id"] != p["producer_session_id"], "INDEPENDENCE")
    issued, expiry = _time(body["issued_at"]), _time(body["expires_at"])
    _need(_time(p["frozen_at"]) <= issued <= now < expiry <= _time(p["expires_at"]), "ATTESTATION_TIME")
    return body


def _freeze(p, envelope, keys, now):
    frozen = _signed(envelope, "freeze", p, keys, now)
    _need(frozen["issued_at"] == p["frozen_at"], "FREEZE_TIME")
    _need(frozen["sources_verified"] is True and frozen["holdout_blind"] is True
          and frozen["independence_plan_verified"] is True, "INDEPENDENT_ADMISSION_REQUIRED")
    return frozen


def _result(state, reason, **fields):
    return {"state": state, "reason": reason, "gain_claim": False, "promoted": False,
            "production_effects": [], **fields}


def admit_protocol(protocol, signed_freeze, trusted_keys, *, now=None):
    """Verify an independently signed, predeclared protocol; never run it."""
    try:
        current = _now(now)
        p = _protocol(protocol, current)
        _freeze(p, signed_freeze, trusted_keys, current)
        return _result("ADMITTED_FOR_CONTROLLED_TRIALS", "EXTERNAL_FREEZE_VERIFIED",
                       protocol_sha256=digest(p), candidate_sha256=p["candidate_sha256"],
                       comparisons=p["comparisons"], expected_blocks=len(p["blocks"]))
    except (Refused, ValueError, TypeError, KeyError, OverflowError, UnicodeError) as exc:
        return _result("HOLD", str(exc) if isinstance(exc, Refused) else "INPUT_SCHEMA")


def _rows(rows, cases):
    _need(isinstance(rows, list) and len(rows) == len(cases), "INCOMPLETE_SUITE")
    for row, case in zip(rows, cases, strict=True):
        _shape(row, {"id", "critical", "passed", "output_sha256"}, "RESULT_SCHEMA")
        _need(row["id"] == case["id"] and type(row["critical"]) is bool
              and row["critical"] == case["critical"] and type(row["passed"]) is bool
              and _sha(row["output_sha256"]), "RESULT_SCHEMA")
    return rows


def assess_trials(protocol, signed_freeze, signed_trials, trusted_keys, *, now=None):
    """Assess complete external trials. Signal is evidence for review, not approval.

    No individual repeated case is counted as a statistical sample. Blocks and
    their distinct source/sample digests must be frozen before the first run.
    """
    try:
        current = _now(now)
        p = _protocol(protocol, current)
        freeze = _freeze(p, signed_freeze, trusted_keys, current)
        _need(isinstance(signed_trials, list) and len(signed_trials) == len(p["blocks"]), "INCOMPLETE_BLOCKS")
        expected = {b["id"]: b["sample_sha256"] for b in p["blocks"]}
        blocks, runs, receipts, pairs = set(), set(), set(), []
        for envelope in signed_trials:
            trial = _signed(envelope, "trial", p, trusted_keys, current)
            fingerprint = digest(envelope)
            _need(fingerprint not in receipts, "REPLAYED_RECEIPT")
            receipts.add(fingerprint)
            block = trial["block_id"]
            _need(_id(block) and block in expected and block not in blocks
                  and trial["sample_sha256"] == expected[block], "BLOCK_BINDING")
            blocks.add(block)
            _need(trial["mode"] == "live_control" and trial["holdout_blind"] is True
                  and trial["independence_verified"] is True, "LIVE_BLIND_EVIDENCE_REQUIRED")
            _need(_id(trial["control_run_id"]) and _id(trial["candidate_run_id"])
                  and trial["control_run_id"] != trial["candidate_run_id"]
                  and not {trial["control_run_id"], trial["candidate_run_id"]} & runs, "RUN_REPLAY")
            runs.update((trial["control_run_id"], trial["candidate_run_id"]))
            _need(trial["session_id"] != freeze["session_id"], "TRIAL_SESSION_INDEPENDENCE")
            _need(_time(p["frozen_at"]) < _time(trial["started_at"]) <= _time(trial["finished_at"])
                  <= _time(trial["issued_at"]), "TRIAL_PRECEDES_FREEZE")
            baseline = _rows(trial["baseline"], p["cases"])
            candidate = _rows(trial["candidate"], p["cases"])
            verdict, reason = decide(baseline, candidate)
            if verdict == "REJECT":
                return _result("REJECT", reason, protocol_sha256=digest(p), block_id=block)
            pairs.append({"block_id": block,
                          "control": sum(r["passed"] for r in baseline) / len(baseline),
                          "candidate": sum(r["passed"] for r in candidate) / len(candidate)})
        pairs.sort(key=lambda row: row["block_id"])
        signal = gain_evidence(pairs, fixture=False, comparisons=p["comparisons"])
        eligible = signal.get("statistical_signal") is True
        reason = "NO_SIGNIFICANT_GAIN" if signal.get("statistical_signal") is False else signal["reason"]
        return _result("ACCEPT_FOR_HUMAN_REVIEW" if eligible else "HOLD",
                       "ADMISSIBLE_GAIN_EVIDENCE" if eligible else reason,
                       protocol_sha256=digest(p), candidate_sha256=p["candidate_sha256"],
                       admissible_gain_evidence=eligible, statistics=signal, blocks=len(pairs),
                       trial_set_sha256=digest(sorted(receipts)))
    except (Refused, ValueError, TypeError, KeyError, OverflowError, UnicodeError) as exc:
        return _result("HOLD", str(exc) if isinstance(exc, Refused) else "INPUT_SCHEMA")


def review_recommendation(protocol, signed_freeze, signed_trials, signed_review, trusted_keys, *, now=None):
    """Verify external human review of a recomputed exact decision; execute nothing."""
    try:
        current = _now(now)
        decision = assess_trials(protocol, signed_freeze, signed_trials, trusted_keys, now=current)
        if decision["state"] != "ACCEPT_FOR_HUMAN_REVIEW":
            return _result("HOLD", "ADMISSIBLE_DECISION_REQUIRED")
        p = _protocol(protocol, current)
        review = _signed(signed_review, "review", p, trusted_keys, current)
        _need(review["decision_sha256"] == digest(decision), "REVIEW_DECISION_BINDING")
        verifiers = {_signed(signed_freeze, "freeze", p, trusted_keys, current)["issuer_id"]}
        latest_trial = _time(p["frozen_at"])
        sessions = {p["producer_session_id"]}
        for envelope in [signed_freeze, *signed_trials]:
            purpose = "freeze" if envelope is signed_freeze else "trial"
            verified = _signed(envelope, purpose, p, trusted_keys, current)
            verifiers.add(verified["issuer_id"])
            sessions.add(verified["session_id"])
            latest_trial = max(latest_trial, _time(verified["issued_at"]))
        _need(review["issuer_id"] not in verifiers and review["session_id"] not in sessions, "REVIEW_INDEPENDENCE")
        _need(_time(review["issued_at"]) >= latest_trial, "REVIEW_PRECEDES_TRIALS")
        _need(review["verdict"] in {"APPROVE_RECOMMENDATION", "REJECT"}, "REVIEW_VERDICT")
        return _result("REVIEWED_RECOMMENDATION" if review["verdict"] == "APPROVE_RECOMMENDATION" else "REJECT",
                       "EXTERNAL_REVIEW_VERIFIED", protocol_sha256=digest(p),
                       candidate_sha256=p["candidate_sha256"], decision_sha256=digest(decision),
                       review_sha256=digest(signed_review), external_authorization_required=True)
    except (Refused, ValueError, TypeError, KeyError, OverflowError, UnicodeError) as exc:
        return _result("HOLD", str(exc) if isinstance(exc, Refused) else "INPUT_SCHEMA")
