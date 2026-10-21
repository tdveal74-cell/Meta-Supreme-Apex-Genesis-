"""Network-free observation of sealed fixture runs, with a durable review outbox.

This trusted process never executes candidate code. Existing decisions must be
bound to their journal and recomputed against the unchanged public suite.
"""

import argparse
import hashlib
import os
import time
import uuid

from tools.devon_rsi.kernel import (
    MAX_CANDIDATES,
    MAX_EVALUATIONS,
    Refused,
    canonical,
    digest,
    make_candidate,
    read_json,
    score,
    verify_seal,
)
from tools.devon_rsi.runner import ROOT, run, verify_journal

from .health import summarize
from .store import Store, safe_path

MAX_REPORTS = 2000


def validated_report(path, trust):
    path = safe_path(path)
    manifest = verify_seal(ROOT, trust)
    report = read_json(path)
    if not isinstance(report, dict):
        raise Refused("REPORT_SCHEMA")
    if (report.get("release_manifest_sha256") != trust
            or report.get("gain_claim") is not False
            or report.get("promoted") is not False
            or report.get("production_effects") != []):
        raise Refused("REPORT_AUTHORITY")
    journal = safe_path(path.parent / "journal")
    # Bound directory enumeration before the v1 verifier. No unbounded input.
    files = []
    for p in journal.iterdir():
        if p.is_symlink() or not p.is_file() or p.suffix != ".json":
            raise Refused("JOURNAL_PATH")
        files.append(p)
        if len(files) > 258:
            raise Refused("JOURNAL_CAPACITY")
    verify_journal(journal, report.get("journal_head"))
    decision_event = read_json(sorted(files)[-1])["event"]
    body = {k: v for k, v in report.items() if k != "journal_head"}
    if decision_event != {"kind": "decision", "report": body}:
        raise Refused("DECISION_BINDING")
    if report.get("status") == "REJECT":
        return dict(report, mode="synthetic_fixture")
    if report.get("status") != "ACCEPT_FOR_HUMAN_REVIEW" or report.get("mode") != "synthetic_fixture":
        raise Refused("REPORT_STATUS")
    events = [read_json(p)["event"] for p in sorted(files)]
    evaluations = [e["result"] for e in events if e.get("kind") == "evaluation"]
    searched = {e["fingerprint"] for e in evaluations if e["stage"] != "ablation"}
    if (type(report.get("evaluations_used")) is not int
            or not 1 <= report["evaluations_used"] <= MAX_EVALUATIONS
            or type(report.get("evaluated_candidates")) is not int
            or not 1 <= report["evaluated_candidates"] <= MAX_CANDIDATES
            or report["evaluations_used"] != 1 + len(evaluations)
            or report["evaluated_candidates"] != len(searched)
            or sum(e.get("kind") == "baseline" for e in events) != 1
            or sum(e.get("kind") == "decision" for e in events) != 1
            or any(e.get("kind") not in {"baseline", "evaluation", "decision"} for e in events)):
        raise Refused("REPORT_BUDGET")
    cases = read_json(ROOT / "cases.json")
    best = report["best"]
    rows = score(cases, best["candidate"])
    baseline = score(cases, make_candidate())
    from tools.devon_rsi.kernel import decide
    verdict, reason = decide(baseline, rows)
    deltas = [{"id": p["id"], "delta": int(p["passed"]) - int(b["passed"]),
               "critical": p["critical"]} for b, p in zip(baseline, rows, strict=True)]
    if (report["suite_sha256"] != manifest["cases.json"]
            or best["fingerprint"] != digest(best["candidate"])
            or best["trace"] != rows or best["deltas"] != deltas
            or best["verdict"] != verdict or best["reason"] != reason
            or verdict == "REJECT" or best["total"] != len(rows)
            or best["passed"] != sum(r["passed"] for r in rows)
            or report["baseline_passed"] != sum(r["passed"] for r in baseline)):
        raise Refused("REPORT_RECOMPUTATION")
    return report


def discover(inbox):
    """Exactly /inbox/run/evaluation/decision.json, never recursive vault scans."""
    inbox = safe_path(inbox)
    found = []
    for index, directory in enumerate(inbox.iterdir()):
        if index >= MAX_REPORTS:
            raise Refused("INBOX_CAPACITY")
        if directory.is_symlink():
            raise Refused("INBOX_SYMLINK")
        if not directory.is_dir():
            continue
        path = directory / "evaluation" / "decision.json"
        if path.exists():
            found.append(safe_path(path))
    return sorted(found)


def tick(state, inbox, trust, execute=True):
    state, inbox = safe_path(state), safe_path(inbox)
    if state == inbox or inbox in state.parents or state in inbox.parents:
        raise Refused("STATE_INBOX_OVERLAP")
    verify_seal(ROOT, trust)
    health_path = inbox / "health.json"
    health = summarize(read_json(safe_path(health_path))) if health_path.exists() else {
        "status": "REVIEW_REQUIRED", "reason": "HEALTH_EVIDENCE_MISSING",
        "monthly_review_recorded": False, "gain_claim": False, "promoted": False}
    store = Store(state / "operator.sqlite3")
    try:
        for path in discover(inbox):
            report = validated_report(path, trust)
            identity = digest(path.relative_to(inbox).as_posix())
            store.observe(identity, digest(report), report["status"] == "REJECT")
            store.import_proposal(report)
        claim = store.claim() if execute else None
        if claim:
            # Intent is already committed. A crash leaves RUNNING for operator
            # inspection and cannot silently retry or reset the daily ceiling.
            report = run(state / "runs" / claim["window"], trust)
            store.finish(claim, dict(report, mode="synthetic_fixture"))
        snapshot = store.snapshot()
        snapshot.update({"status": "OBSERVING_FIXTURES", "private_trial_status": "HOLD",
                         "reason": "EXTERNAL_PROVENANCE_AND_INDEPENDENT_REVIEW_REQUIRED",
                         "production_effects": [], "paid_model_calls": 0})
        snapshot["health"] = health
        write_status(state, snapshot)
        return snapshot
    finally:
        store.close()


def write_status(state, snapshot):
    state = safe_path(state)
    target = state / (".snapshot-" + uuid.uuid4().hex)
    with target.open("xb") as stream:
        stream.write(canonical(snapshot) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    target.replace(state / "status.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            result = tick(args.state, args.inbox, args.trust_sha256)
            print(canonical({"status": result["status"], "audit_head": result["audit_head"],
                             "observations": result["observation_count"],
                             "review_count": len(result["review_queue"]),
                             "status_sha256": hashlib.sha256(canonical(result)).hexdigest()}).decode(), flush=True)
        except Exception:
            # No raw source, token, exception text or stack in the service log.
            failure = {"status": "HOLD", "reason": "FAIL_CLOSED", "gain_claim": False,
                       "promoted": False, "production_effects": []}
            print(canonical(failure).decode(), flush=True)
            try:
                write_status(args.state, failure)
            except Exception:
                pass
            raise SystemExit(1) from None
        if not args.watch:
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
