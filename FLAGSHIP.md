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

- This is not a closed 2nd-brain loop. Knowledge still needs a second tool open for Notion, Drive, and n8n.
- Vault folder ids in the console STATE blob are a 2026-08-22 ID snapshot, not a live Drive read or live vault sync.
- Filing plans only: `executed: false`. DEVON plans; humans decide.
- Soul recall is off by default. It needs `SOUL_RECALL_ENABLED` and `PINECONE_API_KEY`. Do not invent live soul connectivity.
- Hermes stack status is CI-proven / not operator-live. Do not wear a Live badge for undeployed operator verification.
- I serve the Loop HUD same-origin at app.main GET /console. Remember / file a ruling / add a task / start a project / log a thread propose on this host with the CurrentUser JWT. PLATFORM is not required there. CONSOLE_TOKEN is only for soul-host recall on devon-soul.vercel.app. That Vercel host has no Postgres, production SHA is still d2aff6d, and I do not pretend localStorage is memory.
- Tee rulings may enter the ledger (kind ruling) and outrank DEVON notes on find. Tasks, projects, threads, plate, and brief file the same receipted Postgres ledger. Layer 1 Tee Soul is still never written from this loop.
- Capture payload is stored on artifacts.body in PostgreSQL. estate:// is a path label. Find is still ILIKE on stated+body, Tee-first rank, not recall-at-plan-time.
- `services/memory` points reads at those receipted artifacts. It is not localStorage. Hermes expansion runtime tools are durable since 2026-09-02 (fix PR 3 of the DEVON and Hermes audit); the in-memory stores remain for offline tests only.
- Notion, Drive, and n8n are missing. I do not fake a write to them. `postgres.live` is proven by the engine this request, not by DATABASE_URL sitting in the env.

## Beyond standalone

Full monorepo (`app.*` / `services.*`) + Postgres unlocks providers, persistence, and the full test suite. See `HOW_TO_TEST.md` and `HANDOVER_FOR_CLAUDE.md`. Label mock vs live providers honestly when those paths are exercised.
