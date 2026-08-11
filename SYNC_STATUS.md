# GitHub Sync Status — Meta Supreme

**Date:** 2026-08-11  
**Source of truth for full tree:** Drive `Meta-Supreme-Apex-Genesis-BUILD.zip` (209 files) and original Workflows 11 zip.

## On GitHub `main`
- Operator / FLAGSHIP / BUILD docs
- `apps/web` flagship landing + tokens + button/card
- `apps/api` core: main, config, session, router, health
- `infrastructure/docker` compose + Dockerfiles
- Root-level Phase 5 modules (definition, engine, tests, providers) — historical flat layout
- Monorepo path starts: `apps/`, `services/`, `database/`

## Full restore (recommended)
```bash
unzip Meta-Supreme-Apex-Genesis-BUILD.zip -d meta-supreme-apex-genesis
cd meta-supreme-apex-genesis
docker compose -f infrastructure/docker/docker-compose.yml up -d --build
```

## Honest gap
GitHub is **not** a 1:1 of the 209-file BUILD zip. Prefer BUILD zip for `make up` / full API routes / dashboard pages / alembic until a bulk sync completes.

## This session
Authorized full sync; progressive monorepo path pushes ongoing. Drive remains the complete archive.
