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

## What this partial restore is actually missing

Measured, not guessed — each item below is the reason a specific suite cannot
run. Everything else has been put back in the package its own imports name.

| Missing | Blocks | Why it cannot be reconstructed here |
| --- | --- | --- |
| `services/agents/executor.py` | `test_council.py`, `test_phase4_council.py` | `AgentExecutor` / `AgentTask` / `AgentResult` are imported by `services/intelligence/executive_controller.py` and `services/intelligence/synthesizer.py`. No copy exists anywhere in the repository — writing one would be inventing the Council's execution semantics, not restoring them. |
| `database/schemas/001_initial_schema.sql` | every database-backed suite | `conftest.py` applies it to build the test database. Only the `002` and `003` increments are present, and an increment cannot create the tables it alters. |

Both are in the Drive archives named at the top of this file. Drop them in and
the blocked suites should run without further changes.

### What does run

`python -m pytest test_billing.py test_definition.py test_providers.py test_schedule.py test_workflow_engine.py`
— 74 tests, no database, no API keys. This is what CI's standalone job runs.

The database-backed suites need Postgres plus `asyncpg`, `sqlalchemy`, and the
baseline schema above; CI's `api` job provisions the first two.
