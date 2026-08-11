# How to Test — Meta Supreme Apex Genesis

## Flagship offline (recommended)

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py test_definition.py -q
uvicorn standalone_api:app --port 8000
```

Smoke:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/agents | head
curl -s -X POST http://localhost:8000/council/deliberate \
  -H 'content-type: application/json' \
  -d '{"prompt":"Should we ship the flagship offline surface?"}'
```

Every council response includes `"simulated": true`.

## Full product

Requires monorepo layout + Postgres. See `HANDOVER_FOR_CLAUDE.md`.

```bash
make install && alembic upgrade head && make up && make test
```
