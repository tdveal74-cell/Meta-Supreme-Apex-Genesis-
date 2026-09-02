# Meta Supreme Apex Genesis - Completion

## AAA flagship (visual + spec)

- `docs/FLAGSHIP_SPEC.md` - product + visual standard
- `apps/web/app/globals.css` - tokens, motion, MS utility classes
- `apps/web/app/page.tsx` - flagship marketing surface
- `apps/web/components/ui/button.tsx` · `card.tsx` - premium primitives
- `packages/ui/src/index.ts` - shared design tokens
- `apps/web/tailwind.config.ts` - navy / amber / surface scale

## Run paths

| Mode | Command |
|------|---------|
| Offline API | `make standalone` |
| Offline tests | `make test-offline` |
| Full monorepo | Restore **Workflows 11** zip → `make up` |

## Principles

1. Not a chatbot
2. Humans decide
3. Reads flow · writes wait
4. Simulated always labeled
5. Navy · Amber · Surface only

## Honesty (2026-08-31)

- Not a closed 2nd-brain claim. I still would not put Notion away.
- Vault: 2026-08-22 ID snapshot in the console STATE blob. Not live vault sync.
- Filing: `executed: false`. Plans only; humans decide.
- Soul recall: off by default until `SOUL_RECALL_ENABLED` and `PINECONE_API_KEY` are set.
- Hermes: CI-proven / not operator-live. No Live badge for schema-only verification.
- I serve the wired Loop HUD from app.main GET /console, same origin, CurrentUser JWT. CONSOLE_TOKEN stays on the Vercel soul host only. Public gate is production SHA 57fdddb as of 2026-09-02, the PR #111 merge (no Postgres on that host). Remember fail-closes there rather than storing localStorage as memory.
- Tasks, projects, thread log, plate, and brief file the receipted Postgres ledger after consume-once. Notion/Drive/n8n are still missing. Find is ILIKE, Tee rulings first, not recall-at-plan-time. Layer 1 Tee Soul stays 403.
- Ledger find ranks Tee rulings above operator files and notes. Artifact body lives on PostgreSQL artifacts.body.
- `services/memory` points at those receipted artifacts. Not localStorage. No Live badge.

## DEVON-operated EditForge execution (2026-08-26)

- [x] Shared-approval authorization bound to exact edit intent hash
- [x] Long-form, short-form, and full-motion micro-drama command contracts
- [x] Clone, voice, identity version, and consent lock
- [x] Canon separation for TSWS and Ascension Caudex
- [x] Authenticated execute, status, receipt validation, retry, and cancel API
- [x] Environment-configurable self-hosted EditForge URL and bearer token
- [x] Canonical service vendored byte-identically into `deploy/soul`
- [ ] Provider smoke render after consented IDs and deployment credentials are installed (not claimed live here)
