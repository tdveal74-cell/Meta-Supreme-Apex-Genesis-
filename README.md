# Meta Supreme Apex Genesis

**Intelligence Operating System** — multi-agent Council, Knowledge, Memory,
Workflows with human approval gates, Phase 6 billing scaffold.

> Not a chatbot. Agents recommend. Humans decide.

**Flagship status:** offline surface complete — see `FLAGSHIP.md` and `REPOSITORY_STATUS.md`.

## Quick start (zero keys) — canonical runtime

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py test_definition.py -q
uvicorn standalone_api:app --reload --port 8000
```

| Route | Purpose |
|-------|---------|
| `GET /health` | Liveness |
| `GET /agents` | 9-seat Council |
| `POST /council/deliberate` | Mock deliberation (labeled simulated) |
| `GET /billing/plans` | Free / Professional / Enterprise |
| `POST /workflows/validate` | Workflow contract |
| `/docs` | OpenAPI |

## Non-negotiables

1. Not a chatbot — multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated

## Layout note

This GitHub copy is a **flattened snapshot**. The **supported zero-infra path is `standalone_api.py`**.
`apps/api/` is the secondary monorepo-style tree for persistent/live work (`HOW_TO_TEST.md`).
Canonical declaration: `REPOSITORY_STATUS.md`.
