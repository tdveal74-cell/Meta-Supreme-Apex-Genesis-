# Monorepo restore — Workflows 11

**Source:** Google Drive `Meta Supreme Apex Genesis Workflows 11.zip` (2026-08-09)

## Status

This repository is being restored from the Phase 5 monorepo archive:

- `apps/api` — FastAPI (auth, council, knowledge, memory, decisions, workflows)
- `apps/web` — Next.js dashboard
- `services/` — agents, intelligence, workflows engine
- `database/` — schemas + Alembic migrations
- `infrastructure/docker` — Postgres + API + Web

## Run (full stack)

```bash
cp apps/api/.env.example apps/api/.env
make install
alembic upgrade head   # or rely on docker init schema
make up
```

- Web: http://localhost:3000
- API: http://localhost:8000/api/docs

## Offline (no Postgres)

```bash
make standalone
# or: make test-offline
```

Root-level `standalone_api.py` remains for zero-infra smoke tests.
