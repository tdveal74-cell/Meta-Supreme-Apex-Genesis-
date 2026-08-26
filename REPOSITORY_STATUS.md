# REPOSITORY_STATUS — Meta Supreme Apex Genesis

**Updated:** 2026-08-26

| Field | Value |
|-------|--------|
| Product | Meta Supreme Apex Genesis — Intelligence Operating System |
| Canonical runtime (supported now) | **`standalone_api.py`** zero-key offline surface |
| Secondary tree | `apps/api/` monorepo-style FastAPI + Postgres path |
| Layout note | GitHub copy is a **flattened snapshot**; production imports may expect `app.*` / `services.*` |
| Completion vocabulary | **offline-flagship** for standalone · not persistent-production-ready without Postgres + live providers |
| Required checks | `.github/workflows/ci.yml` (must pass on main SHA) |
| Entry points | `pytest test_billing.py test_definition.py -q` · `uvicorn standalone_api:app --port 8000` |
| Known blockers | Canonical path ambiguity (flatten vs apps/api); current-head CI proof must be visible; requirements not fully pin-locked |
| Deployment | No production URL required for offline flagship |
| Governance | Agents recommend · humans decide · simulated output labeled |
| EditForge execution | `services/devon/editforge_execution.py` + `/api/v1/devon/editforge/*` — exact-intent approval, execute, poll, receipt validation, retry, cancel |
| Self-hosted media | DEVON URL/token are environment-configurable; development compose reaches host-published EditForge through `host.docker.internal` |

## Status badges (explicit)

| Badge | State |
|-------|--------|
| offline-flagship | **yes** (standalone) |
| live-provider-ready | no (keys + wiring) |
| persistent-production-ready | no (Postgres + migrations + RLS proof) |
