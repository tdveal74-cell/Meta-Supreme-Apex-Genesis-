"""Trusted I/O wrapper. Only explicit local report directories can be written."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .kernel import (
    ALLOWED,
    BASELINE,
    MAX_CANDIDATES,
    MAX_EVALUATIONS,
    MAX_SECONDS,
    Refused,
    candidate,
    canonical,
    decide,
    digest,
    make_candidate,
    read_json,
    score,
    verify_seal,
)

ROOT = Path(__file__).resolve().parent


class Budget:
    def __init__(self, evaluations=MAX_EVALUATIONS, seconds=MAX_SECONDS):
        if type(evaluations) is not int or not 1 <= evaluations <= MAX_EVALUATIONS:
            raise Refused("BUDGET_CONFIG")
        if type(seconds) not in (float, int) or not 0 < seconds <= MAX_SECONDS:
            raise Refused("BUDGET_CONFIG")
        self.limit, self.seconds = evaluations, seconds
        self.used, self.started = 0, time.monotonic()

    def check(self):
        if time.monotonic() - self.started >= self.seconds:
            raise Refused("TIME_BUDGET")

    def charge(self):
        self.check()
        if self.used >= self.limit:
            raise Refused("EVALUATION_BUDGET")
        self.used += 1


class Journal:
    """Exclusive-create event files with hash linking; operator anchoring is external.

    Hashes detect modification relative to a retained head; they do not make
    files immutable against a privileged host. Containers get a new run dir.
    """
    def __init__(self, directory):
        self.path = Path(directory)
        self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.head, self.sequence = "0" * 64, 0

    def append(self, event):
        row = {"sequence": self.sequence, "previous": self.head, "event": event}
        row["sha256"] = digest(row)
        raw = canonical(row) + b"\n"
        with (self.path / f"{self.sequence:06}.json").open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.head, self.sequence = row["sha256"], self.sequence + 1
        return self.head


def verify_journal(directory, expected_head):
    previous = "0" * 64
    paths = sorted(Path(directory).glob("*.json"))
    if not paths:
        raise Refused("EMPTY_JOURNAL")
    for number, path in enumerate(paths):
        row = read_json(path)
        if path.name != f"{number:06}.json" or row["sequence"] != number or row["previous"] != previous:
            raise Refused("JOURNAL_CHAIN")
        claimed = row.pop("sha256")
        if claimed != digest(row):
            raise Refused("JOURNAL_HASH")
        previous = claimed
    if previous != expected_head:
        raise Refused("JOURNAL_HEAD")
    return True


def evaluate(cases, proposal, baseline, budget, journal, stage):
    proposal = candidate(proposal)
    budget.charge()
    # Snapshot contains candidate data only. No copied vault or host paths.
    with tempfile.TemporaryDirectory(prefix="devon-rsi-") as tmp:
        snapshot = Path(tmp) / "review_policy.json"
        snapshot.write_bytes(canonical(proposal))
        rows = score(cases, read_json(snapshot))
    budget.check()
    verdict, reason = decide(baseline, rows)
    result = {"candidate": proposal, "fingerprint": digest(proposal), "stage": stage,
              "verdict": verdict, "reason": reason,
              "passed": sum(r["passed"] for r in rows), "total": len(rows),
              "deltas": [{"id": p["id"], "delta": int(p["passed"]) - int(b["passed"]),
                          "critical": p["critical"]}
                         for b, p in zip(baseline, rows, strict=True)],
              "trace": rows}
    journal.append({"kind": "evaluation", "result": result})
    return result


def search(cases, seeds, budget, journal):
    if not seeds or len(seeds) > MAX_CANDIDATES:
        raise Refused("CANDIDATE_BUDGET")
    seeds = [candidate(s) for s in seeds]
    budget.charge()
    baseline = score(cases, make_candidate())
    journal.append({"kind": "baseline", "trace": baseline})
    # All 16 states fit the hard search ceiling. Best-first expanding one edit
    # at a time makes the order explicit; no hidden model calls occur here.
    queue = [(0, digest(s), s, "working") for s in seeds]
    visited, evaluated = set(), []
    while queue:
        queue.sort(key=lambda x: (-x[0], x[1]))
        _, fp, prop, stage = queue.pop(0)
        if fp in visited:
            continue
        if len(visited) >= MAX_CANDIDATES:
            raise Refused("SEARCH_BUDGET")
        visited.add(fp)
        result = evaluate(cases, prop, baseline, budget, journal, stage)
        evaluated.append(result)
        if result["verdict"] == "REJECT":
            continue
        for key, values in ALLOWED.items():
            for value in values:
                settings = dict(prop["settings"], **{key: value})
                child = make_candidate(settings)
                if digest(child) not in visited:
                    queue.append((result["passed"], digest(child), child,
                                  "tuning" if stage == "working" else "explore"))
    eligible = [r for r in evaluated if r["verdict"] != "REJECT"]
    if not eligible:
        raise Refused("NO_VALID_CANDIDATE")
    best = sorted(eligible, key=lambda r: (-r["passed"], r["fingerprint"]))[0]
    changes = [k for k in ALLOWED if best["candidate"]["settings"][k] != BASELINE[k]]
    ablations = []
    # Exhaust every subset, cardinality first: minimal changed-key set for this
    # selected candidate and this corpus, not globally minimal source code.
    minimal = best
    found = False
    for size in range(len(changes) + 1):
        for subset in itertools.combinations(changes, size):
            settings = dict(BASELINE)
            for key in subset:
                settings[key] = best["candidate"]["settings"][key]
            result = evaluate(cases, make_candidate(settings), baseline, budget, journal, "ablation")
            ablations.append({"kept": list(subset), "passed": result["passed"], "verdict": result["verdict"]})
            if result["verdict"] != "REJECT" and result["passed"] == best["passed"]:
                minimal, found = result, True
                break
        if found:
            break
    return {"best": minimal, "ablation": ablations, "evaluated_candidates": len(visited),
            "baseline_passed": sum(r["passed"] for r in baseline),
            "evaluations_used": budget.used}


def observation_window(events, size=20):
    """Pure batch gate. Caller retains cursor; synthetic/unknown identity is held."""
    if type(size) is not int or not 1 <= size <= 1000:
        raise Refused("WINDOW_CONFIG")
    if not isinstance(events, list) or len(events) > 1000:
        raise Refused("WINDOW_SCHEMA")
    seen = set()
    for event in events:
        if (not isinstance(event, dict) or set(event) != {"id", "failed", "source"}
                or type(event["id"]) is not str or not re_safe_id(event["id"])
                or type(event["failed"]) is not bool
                or event["source"] not in {"operator_export", "fixture"}
                or event["id"] in seen):
            raise Refused("WINDOW_SCHEMA")
        seen.add(event["id"])
    if len(events) < size:
        return {"trigger": False, "reason": "INCOMPLETE_WINDOW", "consumed": 0}
    window = events[:size]
    count = sum(e["failed"] for e in window)
    return {"trigger": bool(count), "reason": "FAILURES" if count else "QUIET",
            "consumed": size, "failures": count, "window_sha256": digest(window),
            "production_verified": False}


def re_safe_id(value):
    return 1 <= len(value) <= 80 and all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in value)


def run(out, trust, seeds=None, evaluations=MAX_EVALUATIONS):
    manifest = verify_seal(ROOT, trust)
    cases = read_json(ROOT / "cases.json")
    out = Path(out)
    # Reports are a fresh directory, never overwrite a predecessor.
    if out.exists() or any(p.is_symlink() for p in [out, *out.parents]):
        raise Refused("OUTPUT_EXISTS_OR_SYMLINK")
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    journal = Journal(out / "journal")
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = search(cases, seeds or [make_candidate()], Budget(evaluations), journal)
        verify_seal(ROOT, trust)
        report = {"status": "ACCEPT_FOR_HUMAN_REVIEW", "mode": "synthetic_fixture",
                  "gain_claim": False, "promoted": False, "production_effects": [],
                  "started_at": started, "release_manifest_sha256": trust,
                  "suite_sha256": manifest["cases.json"], **result}
    except (Refused, ValueError, TypeError, KeyError, OSError):
        journal.append({"kind": "refusal", "reason": "FAIL_CLOSED"})
        report = {"status": "REJECT", "reason": "FAIL_CLOSED", "gain_claim": False,
                  "promoted": False, "production_effects": [], "release_manifest_sha256": trust}
    journal.append({"kind": "decision", "report": report})
    report["journal_head"] = journal.head
    verify_journal(out / "journal", journal.head)
    with (out / "decision.json").open("xb") as stream:
        stream.write(canonical(report) + b"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--candidate")
    args = parser.parse_args()
    try:
        seeds = [candidate(read_json(args.candidate))] if args.candidate else None
        result = run(args.output, args.trust_sha256, seeds)
        print(json.dumps({"status": result["status"], "gain_claim": False,
                          "journal_head": result["journal_head"]}))
        return 0 if result["status"] == "ACCEPT_FOR_HUMAN_REVIEW" else 2
    except (Refused, OSError, ValueError, TypeError, KeyError):
        print('{"status":"REJECT","reason":"FAIL_CLOSED","gain_claim":false}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
