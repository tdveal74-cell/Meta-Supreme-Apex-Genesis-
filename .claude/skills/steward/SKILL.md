---
name: steward
description: Repo-specific conventions for driving PRs and CI to green in Meta-Supreme-Apex-Genesis-. Load when taking over an arc from a handover, diagnosing red CI, shipping or merging PRs, or closing an arc. Compiled from the 2026-08-25 Hermes handover session that found the handover's "CI green" claim false and restored the pipeline.
---

# Steward: Meta-Supreme-Apex-Genesis-

How to drive this repo's PRs and CI without repeating the failures that made
CI silently red for five hours of merges.

## Rule zero: verify state claims before building on them

A handover doc's "operational-on-main, CI green" is a claim, not a fact. Check
the Actions history for the claimed head SHA before starting work. In the
Hermes arc the handover recorded green while every run since #206 had failed;
eight merges landed on a red main because nobody looked.

## Local verification parity with CI

CI is three jobs (`.github/workflows/ci.yml`): offline standalone, engine
(council/security), and the PostgreSQL API suite. Reproduce all three locally
before any push; one validated push beats three speculative ones.

```
export DEFAULT_AI_PROVIDER=mock EMBEDDING_PROVIDER=mock ENVIRONMENT=test
export PYTHONPATH=$PWD:$PWD/apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme_test
python -m pytest -q --tb=short        # full suite needs Postgres 16 + pgvector
ruff check .
alembic upgrade head && alembic downgrade 004_federated_knowledge_waist && alembic upgrade head
```

Container quirks seen in practice: install `cffi` if `cryptography` panics on
import (Debian-packaged copy lacks `_cffi_backend`); apt provides
`postgresql-16-pgvector`; initdb under `/var/lib/postgresql` as the postgres
user, then create `meta_supreme` and `meta_supreme_test` with the `vector`
extension. Postgres does not survive container restarts; `pg_ctl start` again
on ConnectionRefused.

## Failure patterns with known root causes

Check these before inventing new theories:

- **relation "agent_..." does not exist** in tests: `conftest.py` has two
  lists that must grow with every migration: `_INCREMENTAL_SCHEMAS` (SQL files
  applied to the test DB) and `_DATA_TABLES` (truncated between tests, FK
  order matters). A migration merged without updating both fails every test
  that touches the new tables.
- **Idempotent replay differs from the original response**: anything appended
  to a run payload must enter it BEFORE `complete_execution` persists it to
  the run ledger. Replay is byte-identical by contract.
- **"planner returned no steps" offline**: the mock provider special-cases
  `metadata.component == "devon-agent-planner"` and answers with a one-step
  plan using a read tool from the request's own catalog. Any new planner
  contract needs the same mock support or offline CI breaks.
- **Route introspection returns nothing**: `fastapi` is pinned only as
  `>=0.115.0` and 0.141 made `include_router` lazy. Tests inspect
  `app.openapi()["paths"]`, never `router.routes`. Expect the unpinned
  dependency to break something again on a future release.
- **Soul write-surface tests fail after adding a route**: the invariant is "no
  mutating routes", enforced as an explicit allowlist in `test_deploy_soul.py`
  and `test_deploy_soul_operator.py`. The only permitted non-GET route is
  `POST /api/v1/soul/conflict-search` (a read-only recall query). A new
  non-GET route must either be genuinely read-only and allowlisted with
  justification, or it does not belong in `deploy/soul/main.py`.
- **Banned dash in docs**: `test_devon_integrity.py` bans em and en dashes in
  `services/devon/*.py` and `docs/devon/*.md`. Restructure sentences; do not
  swap punctuation.
- **Vercel preview failed / CodeRabbit skipped**: cosmetic *for merging*. The
  gate is the CI workflow, not third-party commit statuses. A skipped Vercel
  build recorded as `CANCELED` with an "Ignored" bot comment is the per project
  `ignoreCommand` working, not a failure.
  Cosmetic for merging is not cosmetic for shipping: a green preview is not
  production. See the `deploy-readback` skill before claiming any surface is
  live. On 2026-08-26 preview statuses were reported as production while all
  three surfaces sat stale.

## Governance invariants (never relax to get green)

- `services/devon` stays effect-free
- WRITE / HIGH_IMPACT tools require human approval
- Orphan effect intents refuse automatic retry; the intent is committed
  durably BEFORE the adapter runs (its own transaction via the recorder's
  session factory) so the refusal survives a worker crash
- Receipts commit atomically with the lease-fenced result
- Skill promotion is human-gated; proposals dedupe by goal slug
- Materialize and spawn never auto-run effects

## Ship discipline

- Small PRs on the designated branch; draft first; full local validation
  before every push
- Merge only with Tee's explicit authorization; a standing "merge on my
  behalf" grant means merge each PR once its head run is green, using a merge
  commit titled `Merge PR #N: <title>`
- After a designated branch's PR merges, restart the branch from origin/main
  (same name, force-with-lease) for follow-up work
- Close every arc with a `docs/devon/SYS_OPS_*` status doc (versioned,
  supersedes noted) and a DEVON thread-log receipt
- When proving a concurrency or crash invariant, follow
  `references/crash-matrix.md`; a fix without a negative control is not
  proven

## Environment facts

Env flags: `DEVON_AUTO_SKILL_PROPOSE` (default on),
`DEVON_BROWSER_LIVE_FETCH` (default off), `DEVON_AGENT_TASK_LEASE_SECONDS`
(default 120), `DEFAULT_AI_PROVIDER`/`ENRICHMENT_PROVIDER` (cerebras live,
mock in CI). Alembic head as of 2026-08-25: `010_agent_subagent_links`.
Live-environment verification (deployed DB, Cerebras key) cannot run from CI
or agent containers; it is always a manual item for Tee.
