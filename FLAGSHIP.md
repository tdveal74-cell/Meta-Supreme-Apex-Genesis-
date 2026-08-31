# Meta Supreme Apex Genesis - Flagship Standard

**Version:** 1.0.0-flagship · 2026-08-10

## What flagship means here

| Pillar | Standard |
|--------|----------|
| Identity | Intelligence OS, not a chatbot |
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

1. Not a chatbot; multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated

## Honesty (2026-08-31)

- This is not a closed 2nd-brain loop. Knowledge still needs a second tool open.
- Vault folder ids in the console STATE blob are a 2026-08-22 ID snapshot, not a live Drive read.
- Filing plans only: `executed: false`. DEVON plans; humans decide.
- Soul recall is off by default (needs `PINECONE_API_KEY`). Do not invent live soul connectivity.
- Hermes stack status is CI-proven / not operator-live. Do not wear a Live badge for undeployed operator verification.
- In-estate remember/approve/commit writes the Live State Ledger after a consumed approval. That is not Notion live, not Drive live, and not a claim that devon-soul.vercel.app moved (production SHA is still d2aff6d).
- `services/memory` is an empty stub. Hermes expansion defaults are in-memory / not durable.

## Beyond standalone

Full monorepo (`app.*` / `services.*`) + Postgres unlocks providers, persistence, and the full test suite. See `HOW_TO_TEST.md` and `HANDOVER_FOR_CLAUDE.md`. Label mock vs live providers honestly when those paths are exercised.
