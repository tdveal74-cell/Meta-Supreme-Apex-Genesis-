# Verify

Two paths. Start with whichever your machine supports.

## Offline — Python only, no Docker, no Postgres

```bash
bash scripts/verify-offline.sh
```

Installs two packages and runs every test that is pure by construction: the
workflow engine and the schedule arithmetic. Writes
`VERIFICATION_REPORT_OFFLINE.md`.

This is a real signal, not a consolation prize. The engine is where the
approval rule actually lives (`docs/AUDIT.md` §2, layer 2), and it is pure
precisely so it can be driven with no database, no HTTP, and no AI provider.
If this fails, nothing downstream is worth running.

It is still a minority of the suite. It does not verify the build.

## Full — Docker, nothing else

```bash
docker compose -f docker-compose.verify.yml up --abort-on-container-exit
```

Writes `VERIFICATION_REPORT.md` — every stage, its result, and the pinned
versions it ran against. That file is the artifact to hand an auditor.

Exit code is nonzero if any required stage failed.

## CI — nothing on your machine at all

`.github/workflows/ci.yml` runs all of it on every push: the pure suites first
as a fast gate, then the full suite against a real PostgreSQL 16 + pgvector
service container, then lint, then the frontend typecheck and build. It also
applies the migrations to an empty database, reverses them, and re-applies —
a downgrade path nobody exercises is a downgrade path that does not work.

Once this repository is on GitHub, the Actions tab is the verification report,
and it regenerates itself on every commit. That is the intended answer to
"is this build verified" — not a file somebody remembered to update.

---

## What it runs

| Stage | Notes |
|---|---|
| `alembic upgrade head` | Against an empty PostgreSQL 16 + pgvector |
| `pytest apps/api/tests` | Provider mode is `mock` — offline, deterministic, no API keys |
| `ruff check .` | |
| `tsc --noEmit`, `pnpm build` | Skipped in the container (no Node). Run `bash scripts/verify.sh` on a machine with pnpm to include them |

The database is `tmpfs`-backed, so every run starts empty. A pass cannot depend
on state a previous run left behind.

---

## Why the rest cannot run offline

The remaining tests need a real PostgreSQL with pgvector. Several exist
specifically to check unique-index and constraint behaviour — the idempotency
guarantee is enforced by a UNIQUE partial index, not by application code — so
mocking the database would delete the thing under test.

On a machine with Python 3.11 and a reachable Postgres, without Docker:

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme_test
export DEFAULT_AI_PROVIDER=mock EMBEDDING_PROVIDER=mock
export PYTHONPATH="$PWD:$PWD/apps/api"

pip install -r apps/api/requirements.txt
pip install ruff pytest pytest-asyncio httpx asyncpg alembic

bash scripts/verify.sh
```

One thing that trips people: **Alembic does not build the test database.**
`conftest` creates `meta_supreme_test` itself from `database/schemas/*.sql`.
That split is deliberate — see `docs/PHASE5_PATCH_NOTES.md`.

---

## Status

**The offline subset has executed and passed** (49 tests, 2026-08-09). That is
the first execution of any of this code, and it covers the approval rule
itself.

**Nothing requiring a database has executed.** No migration has been applied,
no API route exercised, no lint or frontend build run, in the environment that
produced this package.

A note on counts: figures quoted in `CHANGELOG.md` and elsewhere were derived
by counting test functions, before anything ran. pytest expands parametrised
cases, so collected totals are higher — the offline subset was estimated at 43
and collected 49. Treat every count in the docs as an estimate until the full
run reports its own.

Treat the build as unverified until you have generated a passing
`VERIFICATION_REPORT.md` yourself.

---

## Then

- `docs/AUDIT.md` — the entry document for an external reviewer
- `docs/RUNBOOK.md` — operating it, and what operators are told never to do
- `docs/PHASE5_PATCH_NOTES.md` — what changed in Phase 5 / 5.1 and why
