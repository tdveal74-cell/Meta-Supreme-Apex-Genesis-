# Meta Supreme Apex Genesis

**Intelligence Operating System** — multi-agent Council, Knowledge, Memory,
Workflows with human approval gates, Phase 6 billing scaffold.

> Not a chatbot. Agents recommend. Humans decide.

## Layout note

This GitHub copy is a **flattened snapshot** of a monorepo. Production imports
expect `app.*` and `services.*`. Use the standalone API until the tree is restored.

## Quick start (offline)

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py test_definition.py -q
uvicorn standalone_api:app --reload --port 8000
```

- http://localhost:8000/health
- http://localhost:8000/billing/plans
- http://localhost:8000/docs

## Full product

See `HOW_TO_TEST.md` and `HANDOVER_FOR_CLAUDE.md` after monorepo restore.

## Non-negotiables

1. Not a chatbot — multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated
