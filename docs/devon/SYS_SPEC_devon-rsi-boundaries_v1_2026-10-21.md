# Devon RSI trust boundary, version 1

Date: 2026-10-21. Status: implementation specification, not Canon.
Authority: Tee's Maximum-Scale Safe Devon RSI Proposal and explicit instruction
to build, create PRs, merge, and deploy in this session. That authorization
covers this installation. It does not grant future candidates authority.

## What is implemented

The deployable component is a bounded, proposal-only bootstrap. It exercises
50 public synthetic cases, generates and validates four enum settings,
searches all 16 combinations best-first, and exhaustively ablates the selected
candidate to the smallest changed-key subset that retains its fixture score.
It writes per-case deltas, fingerprints and a hash-linked event journal.
It has no promotion API, no mutable production skill, and no vault adapter.

This is not yet the maximum-scale live RSI system described in the proposal.
The fixture adapter is not Devon's production reasoning model. A perfect
fixture result proves only behavior against these fixtures. Neither the
runner nor a live maker result is allowed to claim demonstrated real-world gain.

## Trust zones

| Zone | Inputs | Capabilities | Cannot access |
| --- | --- | --- | --- |
| Operator | Approved release and explicit task authorization | Install a version; retain predecessor; invoke one run | No grant transfers to candidates |
| Local maker | Public enum schema and task description | One bounded local-model request returning data | Cases, expectations, traces, vault, secrets, tools |
| Candidate | Four enum values in one exact JSON schema | Influence reference-adapter output | Code import, arbitrary files, gates, scorer, permissions |
| Evaluator | Sealed cases, kernel, baseline and candidate | Deterministic scoring and rejection | Network, live vault, production API, Docker socket |
| Report store | Validated outputs and stable error codes | New run directories and exclusive event creation | Overwrite or delete predecessors via the runner |
| Human review | Decision, deltas, ablations, source proof | Review and authorize a concrete external change | A score is never approval |

The actual isolation boundary is Docker with network disabled, read-only code,
an unprivileged UID, no capabilities, no-new-privileges, memory/CPU/PID limits,
and a single writable new report directory. A temporary directory on its own
is not a security boundary. Host administrators remain trusted.

The operator pins the SHA-256 of release.json outside the candidate. Every
packaged Python source and case file is hash checked before and after a run.
The launchers redirect bytecode lookup to a fresh output/tmpfs prefix with
bytecode writes disabled; Python's write-disable flag alone still reads old
caches. Release construction uses tracked files only. There is no
seal-generation command in the runner. Updating a seal is a reviewed release
operation, not a candidate operation. The hash is an integrity anchor, not a
digital signature and not a claim against malicious host administrators.

## Resolving the apparent scorer conflict

The proposal calls evaluation machinery an open meta-surface and also calls
the scorer and suite immutable. For this implementation, the deciding scorer,
holdout, acceptance thresholds and authorization boundaries remain trusted and
fixed per reviewed release. Alternative scoring ideas may be written as
recommendations for separate review. They cannot grade their own promotion.
An advisory scorer's output is never input to the binding acceptance decision.
Changing a binding gate is outside the mutable candidate surface.

## Source register and standing lanes

Sources read: the user's proposal; repository AGENTS.md, CLAUDE.md and
docs/devon/DEVON.md; Steward and deployment read-back skills; Drive's
SYS_SPEC_devon-standing-authorizations_v1_2026-09-03.md, read on 2026-10-21.
That source labels itself OPERATING and not Canon. A current Charter v2 text
and full Canon/Reflections export were not located in the bounded search.
No private facts or raw transcripts were copied into the public case suite.

| Lane | Source-defined scope | Harness behavior |
| --- | --- | --- |
| S1 | Emit a truthful thread receipt | Classify a plan; operator emits |
| S2 | File that receipt into _Devon Core | Classify a plan; no uploader |
| S3 | File continuity SYS_SPEC/SYS_LOG after state changes; retain predecessors | Classify a plan; no Charter/Canon/Area edits |
| S4 | EditForge workflow dispatch with dry_run=true | False or missing dry_run is held; no dispatcher |
| S5 | Airtable records/schema reads | Classify a read plan; no connector |

All source-specific execution remains outside this harness. Unknown fields,
identity claims and attempts to move a gated action into a lane are refused.
Charter, Canon, contradictions, secrets, Archive, protected markers, new Areas,
the Devon skill and live n8n activation remain closed to candidates. Two
reviews in this build are software review, not two independent Canon sessions.

## Budgets, audit and statistics

Ceilings: 32 unique candidates, 256 evaluations, 60 seconds of evaluator time,
64 KiB input, 75 seconds external process timeout. Local maker: one request,
512 generated-token target, 2,048 context, 45 seconds HTTP timeout, no retries,
no paid API. Provider limits are corroborated by the recorded response where
available, not accepted from candidate-supplied cost claims.

The runner fails closed on malformed data, duplicate keys, nonfinite numbers,
missing cases, critical failure (even if baseline also fails), any regression,
altered release, exhausted budget, and unknown candidate properties. It never
imports candidate code. Records contain output hashes and synthetic results,
not raw model/provider errors or secrets.

Journal events are exclusive-create, fsynced files with previous-hash links.
The decision records the final head. Retain that head separately to detect
tail truncation. This is application-level append-only behavior, not WORM.
No rollback deletes history; rollback selects a retained prior release.

The paired sign-test helper accepts independent run blocks, rejects constant
deltas, and applies a predeclared comparison correction. It never grants a
gain claim: authenticated independent provenance and a blind holdout remain
external requirements. Repeated cases are not independent samples. Freeze the
holdout before search; evaluate a selected winner once; do not tune on it.

## Phase acceptance and remaining work

| Proposal phase | Delivered here | Still required for the full live system |
| --- | --- | --- |
| 1 | 50 fixtures, seal, validator, deterministic scoring, negative controls | Independent private cases grounded in current Charter/Canon |
| 2 | Bounded search, full subset ablation, local maker transport | Live reference/control trials with admissible provenance |
| 3 | Trust-boundary specification for meta proposals | Independently evaluated non-gate operator candidates; no self-updating gate |
| 4 | S1-S5 plan classifier and review artifact | Authenticated existing review queue and Context Pill handoff |
| 5 | Adversarial cases, health fixtures, complete-window observation function | Durable deduplicated observation ingestion, monthly human review evidence |

The observation function consumes a full 20-event batch and returns a content
fingerprint. An operator must retain the cursor and fingerprint; this version
does not claim a persistent continuous observation service. No cron is installed
and no monthly review is represented as completed. Health fixture flags concern
Reflections, Canon growth, disagreement and blind-test equivalence. They do not
establish any of those conditions in Tee's live vault.

## Operating and rollback

Run tests: `python -m pytest -q test_devon_rsi.py`.
Local fixture run (substitute the report path and operator-pinned hash):

```sh
(
  RSI_CACHE="$(mktemp -d)" || exit 1
  trap 'rmdir "$RSI_CACHE"' EXIT
  python -B -X "pycache_prefix=$RSI_CACHE" -m tools.devon_rsi.runner \
    --output <new-directory> \
    --trust-sha256 <operator-pinned-manifest-hash>
)
```

The fresh bytecode prefix is required for local runs too: source hashes cannot
authenticate a stale cache loaded before the evaluator starts. This local
command is a fixture convenience; use the isolated launcher on a host.
Production-host isolation uses deploy/devon-rsi/run-isolated.sh with a pinned
local Python image ID, a versioned release directory and a fresh run directory.
The local maker helper lives beside it and cannot launch an evaluator or merge.

Revoke by ceasing operator invocations. There is no always-on service to stop.
Restore by selecting an earlier retained release and its original trust hash.
Do not rewrite prior reports to make a rollback look like a successful run.
