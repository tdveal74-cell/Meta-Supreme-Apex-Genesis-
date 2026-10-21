"""Durable admission and replay guards around the pure signature verifier."""

from datetime import datetime, timezone

from tools.devon_rsi.kernel import Refused, canonical, digest, strict_load

from .experiments import admit_protocol, assess_trials, review_recommendation


def register(store, protocol, freeze, keys, now=None):
    now = now or datetime.now(timezone.utc)
    result = admit_protocol(protocol, freeze, keys, now=now)
    if result["state"] != "ADMITTED_FOR_CONTROLLED_TRIALS":
        return result
    identity = result["protocol_sha256"]
    with store.transaction():
        row = store.db.execute("SELECT * FROM protocols WHERE experiment_id=?",
                               (protocol["experiment_id"],)).fetchone()
        if row:
            if row["id"] != identity or row["freeze_hash"] != digest(freeze):
                raise Refused("REGISTERED_PROTOCOL_DRIFT")
            return dict(result, registered_at=row["registered_at"])
        family = digest({k: protocol[k] for k in (
            "baseline_sha256", "candidate_sha256", "suite_sha256", "scorer_sha256")})
        if store.db.execute("SELECT 1 FROM protocols WHERE family_id=?", (family,)).fetchone():
            raise Refused("EXPERIMENT_FAMILY_ALREADY_REGISTERED")
        store.db.execute("INSERT INTO protocols VALUES(?,?,?,?,?,NULL,NULL)",
                         (identity, protocol["experiment_id"], family, digest(freeze), now.isoformat()))
        store.append({"kind": "protocol_registered", "protocol_sha256": identity,
                      "freeze_sha256": digest(freeze), "registered_at": now.isoformat()})
    return dict(result, registered_at=now.isoformat())


def assess(store, protocol, freeze, trials, keys, now=None):
    admission = admit_protocol(protocol, freeze, keys, now=now)
    if admission["state"] != "ADMITTED_FOR_CONTROLLED_TRIALS":
        return admission
    identity = admission["protocol_sha256"]
    if not isinstance(trials, list) or len(trials) > 256:
        raise Refused("TRIAL_COUNT")
    submission = digest(trials)
    result = assess_trials(protocol, freeze, trials, keys, now=now)
    with store.transaction():
        row = store.db.execute("SELECT * FROM protocols WHERE id=?", (identity,)).fetchone()
        if not row or row["freeze_hash"] != digest(freeze):
            raise Refused("PREREGISTRATION_REQUIRED")
        if row["result"]:
            if row["submission_hash"] != submission:
                raise Refused("REGISTERED_TRIAL_DRIFT")
            # Reverification cannot upgrade a recorded HOLD after adding a key,
            # bypassing the preregistration and run-reservation checks below.
            if strict_load(row["result"]) != result:
                raise Refused("REGISTERED_DECISION_DRIFT")
            return result
        registered = datetime.fromisoformat(row["registered_at"])
        for trial in trials if result["state"] == "ACCEPT_FOR_HUMAN_REVIEW" else []:
            body = strict_load(trial["payload"].encode())
            if datetime.fromisoformat(body["started_at"].replace("Z", "+00:00")) <= registered:
                raise Refused("TRIAL_PRECEDES_REGISTRATION")
            ids = (body["control_run_id"], body["candidate_run_id"])
            for run_id in ids:
                if store.db.execute("SELECT 1 FROM trial_runs WHERE id=?", (run_id,)).fetchone():
                    raise Refused("CROSS_PROTOCOL_RUN_REPLAY")
                store.db.execute("INSERT INTO trial_runs VALUES(?,?)", (run_id, identity))
            store.db.execute("INSERT INTO trial_receipts VALUES(?,?,?,?)",
                             (digest(trial), identity, *ids))
        # Even a failed/incomplete submission consumes this frozen experiment;
        # retrying different outcomes until significance is forbidden.
        store.db.execute("UPDATE protocols SET result=?,submission_hash=? WHERE id=?",
                         (canonical(result), submission, identity))
        store.append({"kind": "experiment_assessed", "protocol_sha256": identity,
                      "decision_sha256": digest(result), "state": result["state"]})
    return result


def review(store, protocol, freeze, trials, receipt, keys, now=None):
    decision = assess(store, protocol, freeze, trials, keys, now=now)
    if decision["state"] != "ACCEPT_FOR_HUMAN_REVIEW":
        return decision
    result = review_recommendation(protocol, freeze, trials, receipt, keys, now=now)
    if result["reason"] != "EXTERNAL_REVIEW_VERIFIED":
        return result
    identity = result["protocol_sha256"]
    with store.transaction():
        row = store.db.execute("SELECT * FROM reviews WHERE proposal_id=?", (identity,)).fetchone()
        if row:
            if row["receipt_hash"] != digest(receipt):
                raise Refused("REVIEW_ALREADY_RECORDED")
            return strict_load(row["result"])
        store.db.execute("INSERT INTO reviews VALUES(?,?,?,?)",
                         (digest([identity, receipt]), identity, digest(receipt), canonical(result)))
        store.append({"kind": "review_recorded", "protocol_sha256": identity,
                      "review_sha256": digest(receipt), "state": result["state"], "promoted": False})
    return result
