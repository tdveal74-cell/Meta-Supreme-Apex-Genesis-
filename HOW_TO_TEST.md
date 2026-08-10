# How to Test — Meta Supreme Apex Genesis

## Honest status

Phases 1–5 are **authored** in this repository (Intelligence OS, Council, Knowledge, Memory, Workflows, schedule dispatch). Two critical empty modules (`knowledge.py`, `memory.py`) were filled in this pass, and a Phase 6 `billing.py` scaffold was added.

**Structural caveat:** this GitHub copy is a **flattened snapshot**. Imports expect a monorepo layout (`app.*`, `services.*`, `apps/api`, `apps/web`). Until the package tree is restored, `make test` / `make up` from the HANDOVER will not match a clean run from this root alone.

## Intended verification (when layout is restored)

```bash
# From the full monorepo root (not the flattened dump)
make install
alembic upgrade head
make up          # Postgres + API + Web
make test        # target: 148 tests green
ruff check .
cd apps/web && pnpm tsc --noEmit && pnpm build
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/v1/health

Works with **zero AI keys** (mock provider).

## Browser loop (Phase 5)

1. Create workflow from template
2. Run → hits approval gate on effect steps
3. Approve → memory/decision row exists
4. Run again → reject → halt is kept

## What this pass completed

- `knowledge.py` — search, retrieve_for_context, ingest_text
- `memory.py` — recall_memories, persist_memory_candidates
- `billing.py` — Free / Professional / Enterprise plan catalog + limit checks

## Not live yet

- Payment provider
- Restored monorepo package paths in this GitHub mirror
- Verified 148-test green run in this environment
