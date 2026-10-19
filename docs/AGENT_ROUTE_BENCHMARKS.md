# Route profiling and evaluator calibration

`services.agent_benchmarks` performs deterministic analysis over trusted runner
records. It makes no provider calls, executes no tools, promotes no skill and
changes no approval requirement.

Run the executable synthetic calibration example from the repository root:

```bash
python -m services.agent_benchmarks
```

The example deliberately gives two synthetic judges the same wrong approval.
It demonstrates perfect agreement alongside 50% correctness and a shared error.
These numbers describe invented fixture votes, never a real LLM or route.

## Record contract

Construct one frozen `RouteTrace` per task per configuration and treatment.
Persist its full serialized value and `content_hash` as an append-only record in
the durable runner store. A trace ID must never be reused for a changed record.
The pure module does not authenticate receipts, enforce storage immutability or
look up referenced evidence. The caller must do those things. Do not feed model
self-assessments into the behavior flags or counters.

Record versioned route, model, prompt, skill and suite identifiers. `task_hash`
is the SHA256 of the complete frozen task fixture, including requirements and
inputs. `config_fingerprint` hashes canonical strict JSON containing **all**
non-treatment settings (seed, sampling, tool allowlist, budgets, etc.). Explicit
`treatment` is baseline, orchestration or compaction; leave treatment out of the
configuration fingerprint so it is the only permitted experimental difference.
Keep external tool state frozen or the causal comparison is unverified.

`receipt_refs` names trusted runner evidence. `required`, `unresolved` and
`evidenced` are requirement counts. Evidence coverage reports evidence presence,
not correctness. An investigator label means investigation was observed, never
that the resulting answer passed. Multiple observed behaviors yield `mixed`;
no evidence, no requirements, no positive behavior or a boundary pause yields
`insufficient`. Approval pauses, unavailable tools, exhausted budgets and errors
are never called early stopping. Voluntary stops count only with unresolved
requirements and an available next step established by the runner.

Latency is milliseconds and cost is USD. Use `None` when unmeasured. Zero means
measured zero. Reports retain route and task-family strata, all version/config
strata, explicit task/requirement denominators and missing-metric counts.

`compare_paired` rejects unpaired or changed frozen tasks, versions or settings.
Metric deltas include only pairs with both measurements, with their own count.
A partial latency sample cannot stand in for the whole suite.

## Calibration

Use `KnownAnswer` fixtures from deterministic or independently reviewed sources
with evidence references. Pass at least two named judges and a complete declared
answer universe to `calibrate`. Missing votes remain missing; report correctness
on votes and its denominator. False approvals are VERIFIED votes against either
FAILED or UNVERIFIED known answers. Pairwise agreement uses the existing
`services.agent_evaluation` implementation; kappa remains undefined for degenerate
marginals. Shared identical wrong votes are listed separately.

Held-out task IDs and content hashes must be unique. Supply the complete training
and revision-tuning content-hash inventory as `training_hashes`; overlap rejects
the calibration. An empty inventory means no declared overlap, not independently
proved absence of contamination. Fixture provenance and evaluator independence
must be established outside this arithmetic module.
