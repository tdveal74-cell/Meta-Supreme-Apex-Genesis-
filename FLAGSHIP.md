# Meta Supreme Apex Genesis — Flagship Standard

**Version:** 1.0.0-flagship · 2026-08-10

## What flagship means here

| Pillar | Standard |
|--------|----------|
| Identity | Intelligence OS — not a chatbot |
| Council | 9 named agents; dissent preserved |
| Human gate | Effects never commit unattended |
| Simulation | Always labeled `simulated: true` when offline |
| Billing | Explicit limits; Free is fully usable offline |
| Testability | Zero-key smoke path on any machine |

## Offline flagship surface

```bash
pip install fastapi uvicorn pydantic pytest
pytest test_billing.py test_definition.py -q
uvicorn standalone_api:app --port 8000
```

| Route | Flagship behavior |
|-------|-------------------|
| `GET /agents` | Full 9-seat registry |
| `POST /council/deliberate` | Mock multi-agent run, labeled simulated |
| `GET /system/charter` | Non-negotiables + effect step types |
| `GET /billing/plans` | Free / Professional / Enterprise |
| `POST /workflows/validate` | Effect-gate enforcement at save time |

## Non-negotiables (locked)

1. Not a chatbot — multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated

## Beyond standalone

Full monorepo (`app.*` / `services.*`) + Postgres unlocks live providers, persistence, and the 148-test suite. See `HOW_TO_TEST.md` and `HANDOVER_FOR_CLAUDE.md`.
