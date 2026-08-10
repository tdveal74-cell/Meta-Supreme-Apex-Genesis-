# Meta Supreme Apex Genesis

**Intelligence Operating System** — multi-agent Council, Knowledge, Memory,
Workflows with human approval gates, and a Phase 6 billing scaffold.

> Not a chatbot. Agents recommend. Humans decide.

## Honest layout note

This GitHub copy is a **flattened snapshot** of a monorepo. Production imports
expect `app.*` and `services.*` package paths. Until the tree is restored,
use the **standalone smoke API** to exercise root-level modules offline.

## Quick smoke test (no monorepo restore)

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py -q
uvicorn standalone_api:app --reload --port 8000
```

- Identity: http://localhost:8000/
- Health: http://localhost:8000/health
- Plans: http://localhost:8000/billing/plans
- Docs: http://localhost:8000/docs

```bash
curl -s http://localhost:8000/billing/plans | head
curl -s -X POST http://localhost:8000/billing/check \
  -H 'content-type: application/json' \
  -d '{"plan_id":"free","action":"council_run","usage":{"council_runs":50}}'
```

## Full product (after monorepo restore)

```bash
make install && alembic upgrade head && make up && make test
```

See `HOW_TO_TEST.md`, `HANDOVER_FOR_CLAUDE.md`, `IMPLEMENTATION_STATUS.md`.

## What is implemented in this mirror

| Area | Status |
|------|--------|
| Council / Intelligence / Workflows / Memory / Knowledge modules | Authored (flat files) |
| `knowledge.py` / `memory.py` service surfaces | Filled |
| `billing.py` plan catalog + limit checks | Filled |
| `standalone_api.py` smoke server | Runnable offline |
| `test_billing.py` | Runnable offline |
| Package path restore (`app/`, `services/`) | Still required for full API |
| Stripe / payments | Not wired |

## Non-negotiables

1. Not a chatbot — multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated
