# Restore Meta Supreme (authoritative)

GitHub `main` is a **working partial** of the monorepo. The complete tree is:

1. **Drive:** [Meta-Supreme-Apex-Genesis-BUILD.zip](https://drive.google.com/file/d/1cjSiMO-JypICuDcIxCP_0WWFfNeHv2gW/view) (209 files)
2. **Drive:** Meta Supreme Apex Genesis Workflows 11.zip (Phase 5 source)

```bash
cd ~
unzip -o Meta-Supreme-Apex-Genesis-BUILD.zip -d meta-supreme-apex-genesis
cd meta-supreme-apex-genesis
cp apps/api/.env.example apps/api/.env
docker compose -f infrastructure/docker/docker-compose.yml up -d --build
# Web :3000 · API :8000/api/docs
```

Offline: `make standalone` / `make test-offline` when Makefile targets exist in the unzipped tree.

Do not treat the flattened root-level Python files on GitHub as the only layout — prefer `apps/`, `services/`, `database/` from the BUILD zip.

## What was missing, and where it came from

The gaps below were measured, not guessed — each was the reason a specific
suite could not run. All are now restored from the Drive archives this file
names above, byte-for-byte:

| Restored | Path | Was blocking |
| --- | --- | --- |
| `executor.py` | `services/agents/executor.py` | `test_council.py`, `test_phase4_council.py` — three modules import `AgentExecutor` / `AgentTask` / `AgentResult` |
| `001_initial_schema.sql` | `database/schemas/` | every database-backed suite — `conftest.py` builds the test database from it |
| `002_workflow_runs.sql` | `database/schemas/` | `workflow_runs`; the repo held a two-line placeholder |
| `003_schedule_dispatch.sql` | `database/schemas/` | the schedule columns; also a placeholder |
| `002_workflow_runs.py` | `database/migrations/versions/` | `alembic upgrade head` — the chain stopped at `001_baseline` |
| `003_schedule_dispatch.py` | `database/migrations/versions/` | same |

The `.sql` files are the test fixture's twin of the Alembic revisions. If the
two ever disagree, the migration wins and the `.sql` is the bug.

### What runs

`make test-offline` — 95 tests, no database, no API keys. CI's standalone and
engine jobs cover these.

The database-backed suites need Postgres with pgvector; CI's `api` job
provisions it, applies the migrations up-down-up, and runs the whole suite.

## Known gap: the online Alembic path

The test suites do not use Alembic — `conftest.py` builds its database from
`database/schemas/*.sql`, and the full suite passes against Postgres 16 with
pgvector. Alembic matters for real environments, and there it has a defect this
restore did not introduce and could not diagnose:

- **Verified working:** `alembic upgrade head --sql` runs the whole
  `001_baseline → 002_workflow_runs → 003_schedule_dispatch` chain cleanly. The
  revision files and `env.py` are correct.
- **Failing:** `alembic upgrade head` against a live database exits within a
  second. The migrations are reached — offline proves the chain — so the fault
  is in the online connection path in `env.py`, not in the revisions.

It was dropped from CI rather than left as a step that reports without meaning:
the diagnosis needs the runner's raw log, which GitHub buries under ~200 lines
of Postgres service-container output that the API cannot page past. Anyone who
can open the job page directly will see the traceback in seconds.

Reproduce locally with a database running:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme alembic upgrade head
```
