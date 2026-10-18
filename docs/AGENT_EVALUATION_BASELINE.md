# Agent evaluation baseline (draft)

This first slice is offline and opt-in. It changes no runtime completion state,
approval policy, database schema, tool execution, or active skill.

`services/agent_evaluation.py` separates required deterministic checks
from evaluator votes. `outcome_verdict` reports FAILED for a failed required
check and UNVERIFIED for missing or explicitly inconclusive checks. It rejects
empty requirements, duplicate checks, and checks for undeclared requirements.
A conclusive check requires an evidence reference. References are not verified
by this module: only a trusted test runner may construct these inputs. Do not
accept a model-authored receipt as proof of execution or artifact properties.

`evaluator_agreement` reports paired tasks, agreements, missing pairs,
disagreement IDs, raw agreement, and nominal Cohen's kappa. Missing votes do
not count as agreement. Empty overlap and degenerate kappa return None.
`all_evaluator_pairs` requires at least two evaluators and reports each pair.
Agreement does not prove correctness or independence. Calibrate against
known-answer cases and human-reviewed examples separately.

Run the focused tests:

```bash
python3 -m pytest -q test_agent_evaluation.py
```

## Remaining implementation

1. Record route/model/prompt/skill versions, task family, stopping reason,
   evidence IDs, latency, cost, and unresolved requirements. Classify observed
   behavior per task, then aggregate with denominators. Do not equate a proper
   approval pause or an unavailable tool with premature stopping. Mixed and
   insufficient-evidence outcomes must remain possible.
2. Store intermediate tool outputs outside chat with owner/project access,
   immutable IDs, hashes and retention rules. Prove retrieval after restart
   and context compaction, and refusal for another owner. Reuse the existing
   durable coordinator where suitable. Do not duplicate external effects.
3. Add trusted schema, execution and artifact validators. A successful tool
   response and a content hash alone do not prove a claim. Bind each result
   to the exact requirement, artifact, checker version and run.
4. Benchmark baseline versus orchestration or compaction on the same frozen
   tasks and budgets. Report correctness, evidence coverage, cost and stopping
   behavior, not a judge score alone.
5. Preserve immutable skill instructions and parent revisions; isolate tuning
   tasks from held-out tasks by task lineage. Record every attempted revision,
   evaluation suite version and evidence. Keep promotion human gated and test
   rollback of the active revision pointer. Repeatedly inspecting a held-out
   suite turns it into tuning data; use a fresh final set for promotion.

No deployed verification, route profiling, durable storage implementation,
known-answer evaluator calibration, or skill promotion is claimed by this slice.

## Local validation, 2026-10-18

At implementation commit `07174679f1d9fecc3d8b71ead19fc686c7ce9f89`:

- Installed the exact hashed Python closure from `requirements.txt` into an
  isolated virtual environment, without changing repository dependencies.
- Canonical standalone list extracted from `.github/workflows/ci.yml`:
  41 test files, 1,656 passed, 1 skipped, 1 warning. This run covered Python
  tests only, not the workflow's separate Node commands.
- New evaluator plus runtime, effect-runtime, receipt-hardening and integrity
  suites: 417 passed.
- Repository-wide pinned Ruff: all checks passed.
- Earlier independent critic checked 7,380 kappa cases against exact fraction
  arithmetic and 256 required-check combinations. Removing failure precedence
  caused the existing negative test to fail, then the mutation was reverted.

Full API validation is blocked locally. The first attempt had missing Python
packages. After restoring them, the next full run collected and started tests,
then was interrupted after database-dependent errors appeared. It is not a
completed full-suite result. PostgreSQL package configuration failed while
switching system users (`setpriv: setresuid failed: Invalid argument`);
`initdb` refused root, and `su postgres` reported no usable postgres user.
No production connection was attempted. Migration, container, web, engine and
security audit parity have not been established by these checks.

This remains a local draft commit. No push, PR, merge or deployment is claimed.
The next validation environment needs PostgreSQL 16 with pgvector and a usable
unprivileged database service account before the full suite can run.

## Isolated VPS validation, 2026-10-18

This section supersedes the local database setup blocker as the latest attempt,
but does not claim a green full-suite result.

Used a separate checkout on srv1936199 at base `747df79` with the exact first
slice patch applied. A disposable PostgreSQL 16 + pgvector container used
`--network none`, no port bindings, a private Unix socket, a 512 MiB memory
limit and one CPU. No running DEVON service or production database was changed.

Confirmed results:

- Full patched Python suite with initial test environment: 4,868 passed,
  4 failed, 1 skipped in 378.20 seconds.
- An independent verifier reproduced all four failures on unchanged `747df79`.
  The three effect tests invoke literal `python`; the original VPS shell did
  not have that command on PATH. Prepending the test virtual environment made
  those three base tests pass. The presence ordering test passed alone on base.
  This separates these failures from the new evaluator, but is not a substitute
  for a completed green patched-tree full run.
- Migration upgrade/downgrade/upgrade reached `028_support_articles`; separate
  Alembic and SQL schema builds matched across 822 shape lines.
- Updated canonical offline CI list: 42 files, 1,675 passed, 1 skipped.
- Web typecheck, production build, and all check commands selected from the
  web CI workflow passed using pnpm 10, matching CI's major version.
- Standalone CI Node syntax and behavior commands passed.
- Container entry-point imports and repository-wide pinned Ruff passed.
- Evaluator, receipt-shape and estate-reconciliation checks: 594 passed.
- Root and soul Python dependency audits reported no known vulnerabilities.
  pnpm audit exited zero under the existing ignored-advisory policy; it still
  reported one high advisory covered by that policy.
- Independent review confirmed the CI change only adds evaluator tests and
  removes no existing selection or flag.

The patched full-suite rerun with corrected PATH last reached 98% with no
failures visible in its progress output. The remote status request then timed
out; Desktop Commander's last-seen timestamp stopped advancing. Its final
exit status is UNVERIFIED. The final ledger/knowledge subset against the
Alembic-built database was not started. No push, PR, merge or deployment was
made. Reconnect Desktop Commander, retrieve the existing run's final receipt,
and clean up the dedicated test container before closing this validation.

Remote evidence remains under `/tmp/meta-route-eval-20261018/`:
`full-suite-socket.log`, `full-suite-corrected-path.log`, `migration-check.log`,
`base-four-failures.log`, `base-effects-venv-path.log` and
`base-presence-alone.log`. The corrected full-run process ID was `1919480`;
the dedicated container is `meta-route-eval-db-20261018`. These names identify
only this isolated test run. Do not restart the suite or change production to
recover a missing final read.

## Recovered final receipts, 2026-10-18

Supersedes the missing-final-result status above. After Desktop Commander
reconnected, the complete corrected full-suite log was retrieved and independently
read by a verifier. It reached 100% and ended with **4,872 passed, 1 skipped,
50 warnings in 389.81 seconds**. The old process session was no longer present
after the reconnect, so its original shell exit record could not be recovered;
the full pytest summary is the available evidence.

The remaining ledger/knowledge subset against the Alembic-built database then
completed with **49 passed**, shell exit zero. This was a separate run using
`TEST_SCHEMA_PREBUILT=1`, not another SQL-mirror fixture build.

The isolated test container was removed after these checks; evidence logs and
the separate checkout were retained. No production service or database was
changed. The evaluator remains an offline primitive; route profiling, durable
result storage, trusted validator integration and immutable skill revisions
remain open. Passing this slice does not establish those capabilities.
