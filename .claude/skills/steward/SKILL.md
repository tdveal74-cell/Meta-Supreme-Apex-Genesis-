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

CI is FOUR jobs in `.github/workflows/ci.yml`, chained
`standalone -> {container, engine} -> api`: offline standalone, the Railway
container contract, engine (council/security), and the PostgreSQL API suite.
The api job also ends with `ruff check .`, so lint failures surface there rather
than as a job of their own.
Reproduce all four locally before any push; one validated push beats three
speculative ones. The full suite alone is not parity: the standalone job runs
with NO `PYTHONPATH` and no database, so an import that only resolves under the
test path passes locally and fails there.

**A FIFTH job exists and is easy to miss, because it usually does not run.**
`.github/workflows/web-ci.yml` runs `Next.js typecheck + build` and is path
filtered to `apps/web/**`, `packages/ui/**`, the root `package.json`, the
lockfile, the workspace file, and itself. Touch none of those and it never
appears, which is why a run of Python-only PRs makes CI look like exactly four
jobs. It is a real gate on any web change: `pnpm --filter @meta-supreme/web
typecheck` then `build`. Reproduce it with `npx tsc --noEmit` and `npx next
build` from `apps/web`, and note that `tsc` piped into `tail` reports the exit
code of `tail`, so capture `$?` directly or a type error reads as a pass.

ESLint is NOT configured in this repository. `next lint` drops into its
interactive setup prompt and exits non-zero, which looks like a lint failure and
is not one. There is no web lint step in CI to reproduce.

```
export DEFAULT_AI_PROVIDER=mock EMBEDDING_PROVIDER=mock ENVIRONMENT=test
export PYTHONPATH=$PWD:$PWD/apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme_test

# 1. standalone, exactly as CI runs it: no PYTHONPATH, no database
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python -c "import standalone_api"
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python -m pytest -q \
  test_billing.py test_definition.py test_providers.py test_schedule.py \
  test_workflow_engine.py test_devon_hermes_expansion.py \
  test_devon_hermes_durable_followon.py test_devon_learning_loop.py \
  test_devon_operating_layer.py

# 2. container contract (the import check, without building the image)
env -u PYTHONPATH DEFAULT_AI_PROVIDER=mock python -c "from app.main import app; \
  from app.api.v1.auth import passkey_login_options; \
  from services.intelligence.providers.cerebras_provider import CerebrasProvider"

# 3. engine
python -m pytest test_council.py test_phase4_council.py test_security.py -q \
  --deselect test_phase4_council.py::test_stream_endpoint_emits_events_and_persists \
  --deselect test_phase4_council.py::test_stream_endpoint_reports_errors_as_events

# 4. api suite + migrations (needs Postgres 16 + pgvector)
python -m pytest -q --tb=short
ruff check .
alembic upgrade head && alembic downgrade 004_federated_knowledge_waist && alembic upgrade head
```

Container quirks seen in practice: install `cffi` if `cryptography` panics on
import (Debian-packaged copy lacks `_cffi_backend`); `pip install --ignore-installed
cryptography webauthn` when the Debian copy shadows the wheel; apt provides
`postgresql-16-pgvector`; initdb under `/var/lib/postgresql` as the postgres
user, then create `meta_supreme` and `meta_supreme_test` with the `vector`
extension. Postgres does not survive container restarts; `pg_ctl start` again
on ConnectionRefused.

**An interrupted pytest poisons the next local run.** `_clean_tables` truncates
only AFTER each test, so killing pytest mid-test leaves
`council-tester@example.com` behind and the next session's first `auth_headers`
fails with a 409 about an email nobody in that session registered. Cure:
`psql -h 127.0.0.1 -U postgres -d meta_supreme_test -c "TRUNCATE users CASCADE"`,
or just run the suite again (its own post-wipe clears it). CI never hits this
because each run gets a fresh database. Truncating before the yield as well
LOOKS like the fix and is not: under pytest-asyncio the pre-wipe lands after
`auth_headers` has registered, and the run dies on "User not found or inactive"
instead. Tried on 2026-08-26, reverted.

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
mock in CI). Alembic head as of 2026-08-27: `013_approval_consumption` (the
skill said `010_agent_subagent_links`, then `012_live_state_ledger`; verify with
`alembic heads` rather than trusting this line).

**A new migration touches ci.yml in THREE places, not two.** The two `for f in
001... ; do test -s` loops check that the schema and migration files exist, and
they are the obvious ones. The third is an assertion inside the Python heredoc
of the "Fresh Alembic deploy" step: `assert revision == "<head>"`. On
2026-08-27 the first two were updated and the third was not, so the whole api
job went red on `AssertionError: 013_approval_consumption` after 1043 tests had
passed and the upgrade/downgrade/upgrade round trip had worked. The failure
names the new head, which reads like the migration broke rather than like a
pinned expectation went stale.
Live-environment verification (deployed DB, Cerebras key) cannot run from CI
or agent containers; it is always a manual item for Tee.
