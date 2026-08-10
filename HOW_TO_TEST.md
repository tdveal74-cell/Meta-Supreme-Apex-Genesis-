# How to Test — Meta Supreme Apex Genesis

## Offline (this flattened mirror)

Zero AI keys. Zero Postgres.

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py test_definition.py -q
uvicorn standalone_api:app --port 8000
```

| Route | Purpose |
|-------|---------|
| `GET /` | Identity + non-negotiables |
| `GET /health` | Liveness |
| `GET /system/charter` | Platform rules + effect step types |
| `GET /billing/plans` | Free / Professional / Enterprise |
| `POST /billing/check` | Limit evaluation |
| `POST /workflows/validate` | Workflow definition validation |
| `/docs` | OpenAPI |

Example validate:

```bash
curl -s -X POST http://localhost:8000/workflows/validate \
  -H 'content-type: application/json' \
  -d '{"definition":{"version":1,"trigger":{"type":"manual"},"steps":[{"id":"council","type":"council","config":{"prompt":"Assess: {{ input }}"}}]}}'
```

## Full product (monorepo layout required)

Imports expect `app.*` and `services.*`. Restore from the HANDOVER archive, then:

```bash
make install && alembic upgrade head && make up && make test
```

Target: 148 tests green. Frontend `:3000`, API docs `:8000/api/docs`.

## Completed offline

- `knowledge.py` / `memory.py` / `billing.py` service surfaces
- `definition.py` workflow contract + `test_definition.py`
- `standalone_api.py` (health, billing, validate, charter)
- `test_billing.py`

## Not live in this mirror alone

- Live Council / provider calls against DB
- Stripe
- Restored monorepo package tree
