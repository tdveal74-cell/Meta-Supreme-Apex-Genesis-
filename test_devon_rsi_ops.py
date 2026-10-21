"""Real contention, crash boundaries and forged-input controls for RSI ops."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from tools.devon_rsi.kernel import Refused, digest
from tools.devon_rsi.runner import ROOT, run
from tools.devon_rsi_ops import meta, service
from tools.devon_rsi_ops.store import Store


@pytest.fixture
def trust():
    return hashlib.sha256((ROOT / "release.json").read_bytes()).hexdigest()


def add(store, count=20, start=0, stream="fixture", failed=True):
    for i in range(start, start + count):
        store.observe(digest([stream, i]), digest(["source", stream, i]), failed, stream)


def test_partial_windows_and_streams_do_not_mix(tmp_path):
    store = Store(tmp_path / "db")
    add(store, 19)
    add(store, 19, stream="operator_observation")
    assert store.claim() is None
    add(store, 1, 19, stream="operator_observation")
    assert store.snapshot()["windows"][0]["state"] == "REVIEW"
    assert store.claim() is None
    add(store, 1, 19)
    assert store.claim() is not None
    store.close()


def test_dedup_drift_and_quiet_windows(tmp_path):
    store = Store(tmp_path / "db")
    add(store, failed=False)
    before = store.snapshot()
    add(store, failed=False)
    assert store.snapshot() == before
    assert store.claim() is None
    assert before["windows"][0]["state"] == "QUIET"
    with pytest.raises(Refused, match="OBSERVATION_DRIFT"):
        add(store, 1)
    assert store.observe(digest("alias"), digest(["source", "fixture", 0]), False)["inserted"] is False
    store.close()


@pytest.mark.parametrize("repeat", range(5))
def test_concurrent_inserts_claims_fences_and_orphan_refusal(tmp_path, repeat):
    path = tmp_path / "db"
    store = Store(path)
    store.close()

    def worker(_):
        connection = Store(path)
        try:
            add(connection)
            return connection.claim()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = [claim for claim in pool.map(worker, range(6)) if claim]
    assert len(claims) == 1
    # Simulated worker death after durable intent: all future workers refuse.
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(worker, range(24))) == [None] * 24
    store = Store(path)
    assert store.snapshot()["observation_count"] == 20
    assert store.snapshot()["window_count"] == 1
    assert store.snapshot()["windows"][0]["state"] == "RUNNING"
    report = {"status": "REJECT", "mode": "synthetic_fixture", "promoted": False,
              "gain_claim": False, "production_effects": []}
    with pytest.raises(Refused, match="STALE_CLAIM"):
        store.finish(dict(claims[0], token="dead"), report)
    store.finish(claims[0], report)
    with pytest.raises(Refused, match="STALE_CLAIM"):
        store.finish(claims[0], report)
    assert store.snapshot()["windows"][0]["state"] == "COMPLETE"
    store.close()


def test_result_failure_rolls_back_but_intent_survives(tmp_path, trust, monkeypatch):
    store = Store(tmp_path / "db")
    add(store)
    claim = store.claim()
    report = run(tmp_path / "report", trust)
    original = store.append
    def crash(event):
        if event["kind"] == "search_result":
            raise RuntimeError("process died before result commit")
        return original(event)
    monkeypatch.setattr(store, "append", crash)
    with pytest.raises(RuntimeError):
        store.finish(claim, report)
    store.close()
    store = Store(tmp_path / "db")
    snapshot = store.snapshot()
    assert snapshot["windows"][0]["state"] == "RUNNING"
    assert snapshot["review_queue"] == []
    assert store.claim() is None
    store.finish(claim, report)
    assert len(store.snapshot()["review_queue"]) == 1
    store.close()


def test_daily_cap_survives_restart(tmp_path):
    path = tmp_path / "db"
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    store = Store(path)
    add(store, 60)
    assert store.claim(now)
    assert store.claim(now)
    store.close()
    store = Store(path)
    assert store.claim(now) is None
    assert store.claim(datetime(2026, 10, 22, tzinfo=timezone.utc))
    with pytest.raises(Refused, match="TIMEZONE"):
        store.claim(datetime(2026, 10, 22))
    store.close()


def test_audit_append_only_and_external_anchor_detects_truncation(tmp_path):
    store = Store(tmp_path / "db")
    add(store, 2)
    head = store.verify()
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM audit")
    with pytest.raises(Refused, match="TRANSACTION"):
        store.append({"bad": True})
    # Privileged tamper can drop the trigger, but not match the retained head.
    store.db.execute("DROP TRIGGER audit_no_delete")
    store.db.execute("DELETE FROM audit WHERE seq=1")
    with pytest.raises(Refused, match="AUDIT_HEAD"):
        store.verify(head)
    store.close()


def test_tick_recomputes_deduplicates_and_never_promotes(tmp_path, trust):
    inbox = tmp_path / "inbox"
    run(inbox / "first/evaluation", trust)
    state = tmp_path / "state"
    first = service.tick(state, inbox, trust)
    second = service.tick(state, inbox, trust)
    assert first == second
    assert first["observation_count"] == 1
    assert len(first["review_queue"]) == 1
    assert first["private_trial_status"] == "HOLD"
    assert first["gain_claim"] is first["promoted"] is False
    assert json.loads((state / "status.json").read_text()) == first


def test_forged_report_and_journal_binding_refuse(tmp_path, trust):
    path = tmp_path / "run"
    report = run(path, trust)
    report["best"]["passed"] = 100
    (path / "decision.json").write_text(json.dumps(report))
    with pytest.raises(Refused, match="DECISION_BINDING"):
        service.validated_report(path / "decision.json", trust)


def test_self_consistent_forged_trace_is_recomputed(tmp_path, trust):
    path = tmp_path / "run"
    report = run(path, trust)
    report["best"]["trace"][0]["passed"] = False
    last = sorted((path / "journal").glob("*.json"))[-1]
    row = json.loads(last.read_text())
    row["event"]["report"]["best"] = report["best"]
    row.pop("sha256")
    row["sha256"] = digest(row)
    last.write_text(json.dumps(row))
    report["journal_head"] = row["sha256"]
    (path / "decision.json").write_text(json.dumps(report))
    with pytest.raises(Refused, match="REPORT_RECOMPUTATION"):
        service.validated_report(path / "decision.json", trust)


@pytest.mark.parametrize("field,value", [("evaluations_used", 1000000), ("evaluated_candidates", 1000000),
                                         ("evaluations_used", 1), ("evaluated_candidates", True)])
def test_journal_bound_impossible_budgets_refuse(tmp_path, trust, field, value):
    path = tmp_path / "run"
    report = run(path, trust)
    report[field] = value
    last = sorted((path / "journal").glob("*.json"))[-1]
    row = json.loads(last.read_text())
    row["event"]["report"][field] = value
    row.pop("sha256")
    row["sha256"] = digest(row)
    last.write_text(json.dumps(row))
    report["journal_head"] = row["sha256"]
    (path / "decision.json").write_text(json.dumps(report))
    with pytest.raises(Refused, match="REPORT_BUDGET"):
        service.validated_report(path / "decision.json", trust)


def test_full_failure_window_triggers_once(tmp_path, trust):
    inbox = tmp_path / "inbox"
    for i in range(20):
        run(inbox / str(i) / "evaluation", trust, evaluations=i + 1)
    state = tmp_path / "state"
    result = service.tick(state, inbox, trust)
    assert result["observation_count"] == 20
    assert result["windows"][0]["state"] == "COMPLETE"
    assert len(result["review_queue"]) == 1
    assert service.tick(state, inbox, trust) == result
    assert len(list((state / "runs").iterdir())) == 1


def test_paths_and_authority_rejected(tmp_path, trust):
    (tmp_path / "actual").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "actual", target_is_directory=True)
    with pytest.raises(Refused, match="STATE_PATH"):
        Store(tmp_path / "link/db")
    with pytest.raises(Refused, match="OVERLAP"):
        service.tick(tmp_path, tmp_path / "inbox", trust)
    store = Store(tmp_path / "db")
    report = run(tmp_path / "report", trust)
    report["promoted"] = True
    with pytest.raises(Refused, match="REPORT_AUTHORITY"):
        store.import_proposal(report)
    assert store.snapshot()["review_queue"] == []
    store.close()


def test_meta_only_compares_bounded_data_strategies(tmp_path, trust):
    result = meta.compare(tmp_path / "meta", trust)
    assert len(result["strategies"]) == 16
    assert len({digest(row["seed"]) for row in result["strategies"]}) == 16
    assert all(row["passed"] == 50 for row in result["strategies"])
    assert result["operator_unchanged"] is True
    assert result["gain_claim"] is result["promoted"] is False
    assert result["production_effects"] == []
    assert result["paid_model_calls"] == 0


def test_durable_preregistration_no_backdating_or_changed_submissions(tmp_path):
    from test_devon_rsi_experiments import NOW, Evidence
    from tools.devon_rsi_ops import registry
    evidence = Evidence()
    store = Store(tmp_path / "db")
    with pytest.raises(Refused, match="PREREGISTRATION"):
        registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW)
    registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys, NOW)
    with pytest.raises(Refused, match="TRIAL_PRECEDES_REGISTRATION"):
        registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW)
    store.close()


def test_admission_result_review_and_replay_are_durable(tmp_path):
    from test_devon_rsi_experiments import NOW, Evidence
    from tools.devon_rsi_ops import registry
    evidence = Evidence()
    path = tmp_path / "db"
    store = Store(path)
    before_trials = datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)
    registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys, before_trials)
    first = registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW)
    assert first["state"] == "ACCEPT_FOR_HUMAN_REVIEW"
    head = store.verify()
    store.close()
    store = Store(path)
    assert registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW) == first
    assert store.verify() == head
    body = evidence.body("review", "human_session", "2026-10-21T03:00:00Z", "reviewer")
    body.update(decision_sha256=digest(first), verdict="APPROVE_RECOMMENDATION")
    receipt = evidence.sign(body, "reviewer")
    result = registry.review(store, evidence.protocol, evidence.freeze(), evidence.trials(), receipt, evidence.keys, NOW)
    assert result["state"] == "REVIEWED_RECOMMENDATION"
    assert result["promoted"] is False
    body["verdict"] = "REJECT"
    with pytest.raises(Refused, match="REVIEW_ALREADY_RECORDED"):
        registry.review(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.sign(body, "reviewer"), evidence.keys, NOW)
    evidence.protocol["experiment_id"] = "renamed"
    evidence.rebind()
    with pytest.raises(Refused, match="EXPERIMENT_FAMILY"):
        registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys, before_trials)
    # A different candidate still cannot recycle physical trial run IDs.
    evidence.protocol["candidate_sha256"] = digest("other_candidate")
    evidence.rebind()
    registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys, before_trials)
    with pytest.raises(Refused, match="CROSS_PROTOCOL_RUN_REPLAY"):
        registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW)
    store.close()


def test_failed_trial_submission_cannot_be_replaced_until_it_passes(tmp_path):
    from test_devon_rsi_experiments import NOW, Evidence
    from tools.devon_rsi_ops import registry
    evidence = Evidence()
    store = Store(tmp_path / "db")
    registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys,
                      datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc))
    result = registry.assess(store, evidence.protocol, evidence.freeze(), [], evidence.keys, NOW)
    assert result["state"] == "HOLD"
    with pytest.raises(Refused, match="REGISTERED_TRIAL_DRIFT"):
        registry.assess(store, evidence.protocol, evidence.freeze(), evidence.trials(), evidence.keys, NOW)
    store.close()


def test_health_unknowns_and_monthly_review_are_never_invented():
    from tools.devon_rsi_ops.health import summarize
    evidence = {"reflection_count": 37, "latest_reflection_at": "2026-10-15T11:44:30Z",
                "canon_count_previous": None, "canon_count_current": None, "disagreements": None,
                "blind_test_distinguishable": None, "monthly_review_at": None, "source_sha256": digest("fixture")}
    result = summarize(evidence, datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
    assert result["reflection_age_hours"] > 144
    assert result["canon_growth"] is None
    assert result["monthly_review_recorded"] is False
    assert len(result["unknown_metrics"]) == 5
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["gain_claim"] is result["promoted"] is False


def test_added_trial_key_cannot_upgrade_hold_or_bypass_registration(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from test_devon_rsi_experiments import NOW, Evidence
    from tools.devon_rsi_ops import registry
    evidence = Evidence()
    evidence.private["trial_verifier"] = Ed25519PrivateKey.generate()
    for body in evidence.trial_bodies:
        body["issuer_id"] = "trial_verifier"
    trials = [evidence.sign(body, "trial_verifier") for body in evidence.trial_bodies]
    store = Store(tmp_path / "db")
    # Deliberately register after the trials have occurred.
    registry.register(store, evidence.protocol, evidence.freeze(), evidence.keys, NOW)
    first = registry.assess(store, evidence.protocol, evidence.freeze(), trials, evidence.keys, NOW)
    assert first["state"] == "HOLD"
    evidence.keys["trial_verifier"] = {"issuer_id": "trial_verifier",
        "public_key_hex": evidence.private["trial_verifier"].public_key().public_bytes_raw().hex(),
        "roles": ["independent_verifier"], "revoked": False}
    with pytest.raises(Refused, match="REGISTERED_DECISION_DRIFT"):
        registry.assess(store, evidence.protocol, evidence.freeze(), trials, evidence.keys, NOW)
    assert store.snapshot()["experiments"][0]["result"] == first
    assert store.db.execute("SELECT count(*) FROM trial_runs").fetchone()[0] == 0
    store.close()
