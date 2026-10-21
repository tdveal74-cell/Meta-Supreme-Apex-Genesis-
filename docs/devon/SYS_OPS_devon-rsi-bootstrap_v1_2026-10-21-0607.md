# Devon RSI bootstrap, verified candidate deployment

Date: 2026-10-21. Scope: proposal-only bootstrap. No previous RSI status record is superseded.

## Verified implementation

The specification is SYS_SPEC_devon-rsi-boundaries_v1_2026-10-21.md.
A separate tools/devon_rsi runner provides 50 synthetic cases, a four-setting
allowlist, 16-candidate best-first search, exhaustive subset ablation, per-case
deltas, rejection gates, release fingerprints and a hash-linked journal.
Nothing was added to the effect-free services/devon core.

Tee explicitly authorized this work, including PRs, merging and deployment.
The authorization is for this implementation and installation. It is not a
standing promotion grant to future candidates.

## Evidence

- Independent reviewer checked commit 3bcc53a4990f20ae2122094e9cca96382c288f5e.
  All 96 RSI tests passed. A mutation removing the critical-failure guard made
  the negative-control test fail. Three hardening findings were reproduced,
  corrected and independently rechecked: numeric overflow, operator path
  traversal and stale bytecode execution.
- Local initial standalone run: 1,830 passed, one skipped. Updated RSI suite:
  96 passed. Engine plus doctrine/deployment/receipt checks: 1,000 passed,
  two deselected. These counts overlap and must not be summed.
- The 28 original JavaScript workflow steps passed. The additional current-main
  continuity transformer tests also passed. Ruff and API import checks passed.
- Both Python dependency audits passed. pnpm 10 audit passed under the existing
  repository policy, which already excludes GHSA-vfj7-8cjw-p6xm. No audit
  exception was added by this work. pnpm 11 ignores that repository config and
  failed; the test was corrected to CI's configured pnpm 10.
- The first full PostgreSQL run in a disposable test database returned 5,199
  passed, three failed and one skipped. All three failing fixtures invoked
  bare python, absent from the host PATH. A separate reviewer reproduced that
  missing-command condition. With the virtual environment on PATH, the three
  affected tests plus the current 96 RSI tests all passed: 99 passed in 5.57
  seconds. A fresh disposable database was used and removed afterward.

## Isolated host verification

Host: srv1936199. Installed candidate source commit:
f3fb7a8e1ea78a51d5bd8b25a996e3d121845bec. This candidate deployment precedes
its PR merge; do not infer a merged state from this document.

Release: /opt/devon/rsi/releases/f3fb7a8e1ea78a51d5bd8b25a996e3d121845bec

Pinned manifest: 0af7ba74e0ca7537099f2040fde69fb4ef206ceaffa61569138a841c13c036b3

Python image: sha256:2259debdc6af85626058a15a7bf44ad6a68b8c98c9ae82a02cf5cdb92f096d47

Actual Docker isolation probes returned UID 65534, zero effective capabilities,
NoNewPrivs=1, Seccomp=2, blocked network and code writes, absent Docker socket,
and absent host vault. The pinned runner completed 50/50 fixtures in 33
counted evaluations over 16 candidates. The baseline score was 33/50. Those
are synthetic adapter scores and are not real-world improvement evidence.

One existing local qwen3:1.7b request returned a valid candidate in 37.78
seconds with 62 generated tokens reported. No paid API was called. The model
received only a public schema. The candidate was evaluated in the same
network-disabled container and remained ACCEPT_FOR_HUMAN_REVIEW with
promoted=false and gain_claim=false.

Evidence paths:
- /opt/devon/rsi/deployment-candidate-20261021.json
- /opt/devon/rsi/isolation-proof-20261021.json
- /opt/devon/rsi/maker/local-qwen-20261021-a/receipt.json
- /opt/devon/rsi/runs/fixture-20261021-a/evaluation/decision.json
- /opt/devon/rsi/runs/local-maker-20261021-a/evaluation/decision.json

Fixture journal head:
ea366be4781032ea40039bb7142ee892aadacb508511797c3807ffb764a4110d

Local-maker evaluation journal head:
8fb09d19073db838a5563fbb04080ffad9c4a640bca10a4250c13b9f2278d480

## Open scope

This completes a deployable phase-one bootstrap and selected phase-two
mechanisms. Maximum-scale live RSI remains open: private independent holdouts,
live control comparisons, meta-operator experiments, an authenticated review
queue/Context Pill integration, durable observation ingestion, and monthly
human review evidence. The current Charter text and live Canon/Reflections
exports were not available from the bounded source search. No Canon entry or
standing lane was changed. There is no scheduler, publisher or promotion API.

## DEVON RECEIPT
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-rsi-bootstrap_v1_2026-10-21-0607.md
DATE: 2026-10-21
DECISIONS: Tee authorized this build, PR, merge and deployment; candidate authority remains unchanged.
FINDINGS: Bootstrap and isolated host execution verified; fixture scores are not live gains.
OPEN: PR checks and merge pending at this record; full live RSI phases remain open.
STATUS: VERIFIED_BOOTSTRAP_CANDIDATE
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
