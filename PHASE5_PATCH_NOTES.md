# Phase 5 — Workflows

A patch set against `meta-supreme-apex-genesis`. Every path below is
repo-relative: copy the tree over the repository root and the files land where
they belong.

```
rsync -a phase5-workflows/ /path/to/meta-supreme-apex-genesis/
```

## What is here

**New**

| Path | What it is |
|---|---|
| `database/migrations/versions/001_baseline.py` | Adopts the existing raw-SQL schema as Alembic revision 001 |
| `database/migrations/versions/002_workflow_runs.py` | `workflow_runs`, `workflows.metadata`, indexes |
| `database/schemas/002_workflow_runs.sql` | Re-runnable SQL twin of 002 — the test fixture builds from schema files, not Alembic |
| `apps/api/app/api/v1/workflows.py` | The HTTP surface |
| `apps/api/tests/test_workflow_engine.py` | 23 unit tests, no database |
| `apps/api/tests/test_workflows_api.py` | 26 integration cases against Postgres |
| `apps/web/app/(dashboard)/workflows/page.tsx` | The Workflows screen |
| `docs/RUNBOOK.md` | On-call runbook — deploy, rollback, incident playbooks |
| `docs/AUDIT.md` | External-audit entry document — the claim, where it is enforced, what to attack |
| `docker-compose.verify.yml` + `scripts/verify.sh` | One-command reproducible verification (Docker only) |
| `services/workflows/schedule.py` | Cadence parsing + next-slot arithmetic (5.1) |
| `database/migrations/versions/003_schedule_dispatch.py` | `next_run_at` / `last_fired_at` + partial index |
| `database/schemas/003_schedule_dispatch.sql` | Re-runnable twin of 003 |
| `apps/api/app/services/dispatcher.py` | The scheduler (5.1) |
| `apps/api/app/services/maintenance.py` | Orphaned-run sweep (5.1) |
| `apps/api/app/cli/dispatch.py` | Cron entrypoint |
| `apps/api/tests/test_schedule.py` | 20 cadence tests |
| `apps/api/tests/test_dispatcher.py` | 15 dispatch + sweep tests |

**Replaced**

| Path | Change |
|---|---|
| `apps/api/app/core/config.py` | `WORKFLOW_APPROVAL_REQUIRED`, `WORKFLOW_MAX_STEPS`, `WORKFLOW_RUN_HISTORY_LIMIT`, sweep settings |
| `apps/api/app/main.py` | Startup orphan sweep in the lifespan |
| `apps/api/app/models/workflow.py` | `next_run_at` / `last_fired_at` mapped |
| `apps/api/app/api/v1/router.py` | Registers the workflows router |
| `apps/api/tests/conftest.py` | Applies incremental schema files; `workflow_runs` in the truncate list |
| `apps/web/lib/api.ts` | Workflow types + `workflowsApi` |
| `apps/web/app/(dashboard)/layout.tsx` | Workflows in the nav |
| `CHANGELOG.md` · `docs/HANDOVER_FOR_CLAUDE.md` | 0.5.0 |

Already present in the repo and **not** touched: `services/workflows/{definition,engine}.py`,
`apps/api/app/models/workflow.py`, `apps/api/app/services/workflows.py`,
`alembic.ini`, `database/migrations/env.py`.

## Two defects this fixes

1. `workflows` has no `metadata` column, but `app/models/workflow.py` maps one.
   Inserting a `Workflow` raises `UndefinedColumn`. Nothing had exercised that
   path yet.
2. `workflow_runs` does not exist in any schema file. The model, the service
   layer and `conftest`'s truncate list all refer to it.

Both are closed by `002`.

## Two guarantees added after an audit pass

**Idempotent run creation.** `POST /workflows/{id}/runs` accepts an
`Idempotency-Key` header; a repeat returns the original run with `200`. This is
the one case the awaiting-gate guard structurally cannot cover — that guard
fires only when a run *stopped*, and a read-only workflow completes without
stopping, so a double-submit had nothing to collide with and really did run
twice. A unique partial index on `(workflow_id, metadata->>'idempotency_key')`
means a race that beats the application check is still refused by the database.
The web client holds one key across retries and clears it only on success.

**Stable pagination.** `limit`/`offset` on both list endpoints, each with an id
tiebreak on the sort. `updated_at` and `started_at` are not unique — two rows
written in one transaction share a timestamp, and an unstable sort drops and
duplicates rows across page boundaries without erroring. Both are tested at a
page boundary, not just for shape.

## Applying it

```bash
# Existing database (has the Phase 4 schema already)
alembic stamp 001_baseline
alembic upgrade head

# Fresh database
alembic upgrade head
```

## Verifying it — one command, Docker only

```bash
docker compose -f docker-compose.verify.yml up --abort-on-container-exit
```

No local Python, Node or Postgres needed. Writes `VERIFICATION_REPORT.md`
(stages, results, pinned versions) — the artifact to hand an auditor. The
database is `tmpfs`-backed so every run starts empty, and provider mode is
`mock`: deterministic, offline, no API keys.

On a fully-provisioned machine, the same stages plus the frontend:

```bash
bash scripts/verify.sh              # detects pnpm and adds tsc + build
```

Then:

```bash
make test                       # expect 148 passing
ruff check .
cd apps/web && pnpm tsc --noEmit && pnpm build
```

The test database picks 002 up automatically — `conftest` applies the
incremental schema files on every session start, and they are written to be
re-runnable, so an existing `meta_supreme_test` gains the new table rather than
failing on a missing column.

## Verification status

**None of this has been executed.** No Python, Node or Postgres ran in the
environment that produced it. Treat the test counts as intent, not as a result,
until `make test` says otherwise.

What *was* done instead — a static pass resolving every symbol the new modules
import against the real repository source. It found three import-level defects,
each of which would have failed at startup before a single test ran:

1. `RunStatus.RUNNING` does not exist. The services-layer `RunStatus` carries
   only statuses the *engine* can return; it never observes a run mid-flight,
   and `"running"` is an app-layer string literal. `maintenance.py` used the
   attribute — `AttributeError` on import.
2. `parse_definition` is defined in `app.services.workflows`, not exported from
   `services.workflows`. `dispatcher.py` imported it from the latter —
   `ImportError`.
3. `start_run` takes no `trigger` argument; it derives the trigger from the
   definition. The dispatcher passed one — `TypeError` on every scheduled fire.

Also confirmed correct: `asyncio_mode = auto` (bare `async def` tests are
right), `get_db` commits on success (so `flush` + `refresh` in endpoints is the
right pattern), `AsyncSessionLocal` and `setup_logging` exist where the new
code expects them, and `describe_definition` returns a fresh dict per call — so
the API's `awaiting_dispatcher` correction mutates nothing shared.

Still worth watching, in order:

1. The `DISTINCT ON` in `list_workflows` — correct on Postgres, and this
   project is Postgres-only, but it is the one query that is not portable.
2. `db.delete(workflow)` relies on the database's `ON DELETE CASCADE` to clear
   `workflow_runs`; there is no ORM relationship. Correct, but invisible from
   the Python side.
3. `metadata ? 'idempotency_key'` in migration 002 — `?` is a parameter marker
   in some drivers. It is inside a raw `op.execute`, so it should pass through
   untouched, but it is the line to check first if 002 fails.
4. Run duration. A council step inside the request that started it is the only
   place a real provider's latency becomes a request timeout.

## What is deliberately not here

- **Event trigger dispatch.** `event` triggers validate and store; nothing
  fires them. The API reports `awaiting_dispatcher` and the UI says so in
  words. (`schedule` triggers *do* fire as of 5.1 — cron, `python -m
  app.cli.dispatch`, see the runbook §6.)
- **Outbound delivery.** `export` renders into the run record and reports
  `delivered: false`. Email and webhooks need an outbound integration and, for
  inbound webhooks, an auth story that does not exist yet.
- **A visual builder.** The screen reads and runs workflows and resolves their
  gates; step editing is still definition-level. The canvas is the next slice,
  and `GET /workflows/step-types` exists to feed it.
- **Background execution.** A run executes inside the request that started it —
  the same constraint the SSE council endpoint carries, with the same fix.
