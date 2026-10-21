"""Bounded seed-strategy experiments using the unchanged v1 evaluator.

Sixteen data-only proposal strategies are compared. The recommendation cannot
change a scorer, suite, budget, promotion gate or standing authorization.
"""

import itertools
import time
from pathlib import Path

from tools.devon_rsi.kernel import ALLOWED, Refused, digest, make_candidate, verify_seal
from tools.devon_rsi.runner import ROOT, run


def compare(out, trust):
    verify_seal(ROOT, trust)
    out = Path(out)
    if out.exists() or out.resolve() != out:
        raise Refused("OUTPUT_EXISTS_OR_SYMLINK")
    out.mkdir(mode=0o700, parents=True)
    started, rows = time.monotonic(), []
    for values in itertools.product(*ALLOWED.values()):
        if time.monotonic() - started > 60:
            raise Refused("META_TIME_BUDGET")
        seed = make_candidate(dict(zip(ALLOWED, values, strict=True)))
        report = run(out / digest(seed), trust, seeds=[seed])
        if report["status"] != "ACCEPT_FOR_HUMAN_REVIEW":
            raise Refused("META_SUBRUN_REFUSED")
        rows.append({"seed": seed, "evaluations": report["evaluations_used"],
                     "passed": report["best"]["passed"],
                     "minimal_candidate_sha256": report["best"]["fingerprint"],
                     "journal_head": report["journal_head"]})
    verify_seal(ROOT, trust)
    best = sorted(rows, key=lambda r: (-r["passed"], r["evaluations"], digest(r["seed"])))[0]
    result = {"status": "ACCEPT_FOR_HUMAN_REVIEW", "mode": "synthetic_meta_fixture",
              "strategies": rows, "recommended_seed": best["seed"],
              "operator_unchanged": True, "promoted": False, "gain_claim": False,
              "production_effects": [], "paid_model_calls": 0,
              "release_manifest_sha256": trust}
    from tools.devon_rsi.kernel import canonical
    with (out / "decision.json").open("xb") as stream:
        stream.write(canonical(result) + b"\n")
    return result
