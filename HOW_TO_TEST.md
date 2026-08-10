# How to Test — Meta Supreme Apex Genesis

## Offline smoke (this flattened mirror)

Works with **zero AI keys** and **no Postgres**:

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py -q          # Phase 6 plan limits
uvicorn standalone_api:app --port 8000
```

| Route | Purpose |
|-------|---------|
| `GET /` | Identity + phase |
| `GET /health` | Liveness |
| `GET /billing/plans` | Free / Professional / Enterprise |
| `POST /billing/check` | Pure limit evaluation |

## Full verification (monorepo layout required)

Imports expect `app.*` and `services.*`. Restore the monorepo tree from the
HANDOVER archive, then:

```bash
make install
alembic upgrade head
make up          # Postgres + API + Web
make test        # target: 148 tests green
ruff check .
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/v1/health

### Phase 5 browser loop

1. Create workflow from template
2. Run → hits approval gate on effect steps
3. Approve → memory/decision row exists
4. Run again → reject → halt is kept

## Completed in repo

- `knowledge.py` — search, retrieve_for_context, ingest_text
- `memory.py` — recall_memories, persist_memory_candidates
- `billing.py` — plan catalog + limit checks
- `standalone_api.py` — offline smoke server
- `test_billing.py` — offline unit tests

## Not live yet

- Payment provider
- Restored monorepo package paths in this GitHub mirror
- Verified 148-test green run against this flattened tree alone
