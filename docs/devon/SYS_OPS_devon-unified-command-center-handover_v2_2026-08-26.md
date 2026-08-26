---
title: DEVON Unified Command Center Handover
type: SYS_OPS
version: 2
date: 2026-08-26
area: Systems
status: final-head-pending-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-unified-flagship-command-center
supersedes: SYS_OPS_devon-unified-command-center-handover_v1_2026-08-26.md
purpose: final inventory and consolidation record for DEVON command centers, dashboards, terminals, voice, advisor, capability telemetry, and continuity surfaces
---

# DEVON Unified Command Center Handover v2

## Ruling

Flagship is the baseline, not the ceiling. One canonical cockpit now owns the operator experience. Older surfaces remain evidence, fallback, or diagnostic artifacts. Their stale state is not promoted into live truth.

## Surfaces actually inspected

### Current Meta main

- `apps/web/app/command-center/page.tsx`
- `apps/web/components/devon/DevonChat.tsx`
- `apps/web/components/terminal/OperatorTerminal.tsx`
- `apps/web/components/terminal/RealShell.tsx`
- `apps/web/lib/api-base.ts`
- `app/services/agent_tasks.py`
- `app/api/v1/agent_tasks.py`
- `app/api/v1/agent_expansion.py`
- `app/api/v1/devon.py`
- `app/api/v1/soul.py`
- `app/api/v1/health.py`
- `app/core/config.py`
- `services/devon/persona.py`
- `services/devon/areas.py`
- `.claude/skills/devon-learning-lane/references/heartbeat.md`
- `docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md`
- `website/index.html` was identified as the operations and ecosystem presentation surface

### Historical and parallel DEVON control surfaces

- `docs/devon/assets/SYS_OPS_devon-console_v8_2026-08-23.html`
- `deploy/soul/console.html`
- `deploy/soul/terminal.html`
- `docs/devon/SYS_OPS_devon-browser-terminal-handover_v1_2026-08-24.md`
- superseded Console v1 through v7 files under `docs/devon/assets/`
- old `devon-browser-terminal`, `devon-operator-terminal`, and Claude Jarvis branches, all verified fully behind main with no unmerged commits

### Separate Vercel Mission Control HUD

Vercel project: `devon-mission-control-hud`

Production surface inspected: `https://devon-mission-control-hud.vercel.app`

Useful pattern found:

- JARVIS-class cockpit framing
- central reactor presentation
- an Advisor rail that names the three items demanding attention

Confirmed defect in that snapshot:

- it is a static brief from 14 August
- it contains obsolete operating state
- it displays `Areas 8 fixed`, which conflicts with the current canonical nine Areas

Decision: preserve the Advisor interaction pattern, reject the stale snapshot data.

### Grok share

The Grok share URL supplied by Tee could not be retrieved through the available public web path in this session. No content from that conversation is represented as verified or merged by assumption.

## Canonical cockpit built

### `UnifiedCommandCenter.tsx`

One page now combines:

- copper instrument HUD language from Console v8
- live DEVON API probe
- authenticated intelligence provider probe
- live Operator Bridge probe
- hydration-safe local clock
- nine-Area brain map
- continuity schedule panel
- DEVON natural-language and voice interface
- Council entry
- embedded governed Operator Terminal
- embedded real xterm.js bash PTY
- explicit separation between DEVON's governed effects and Tee's human shell

Heartbeat telemetry is deliberately honest. The card says `6H SCHEDULE`, not `ONLINE`, because the Build 13 heartbeat schedule is verified in canon but the current API does not expose the last heartbeat row to this page.

### `MissionAdvisor.tsx`

The useful Mission Control HUD advisor pattern is now live rather than static.

It reads:

- pending DEVON approval records
- authenticated DEVON Agent Tasks

It surfaces at most three items, prioritizing required human rulings and blocking task states. It explicitly says the ranking is operational, not invented business-value scoring.

### `CapabilityDock.tsx`

The capability mesh reads live authenticated status from:

- `/agent-tasks/tools`
- `/soul/status`
- `/agent-expansion/schedules`

It reports Operator, GitHub, Browser, Council, Scheduler, Effect Receipts, Soul, execution leases, and the next visible scheduled goal. Partial read failure produces `degraded`, never an invented green state.

## DEVON personality and spoken voice

`app/core/config.py` now derives the default synthesis persona from canonical `services.devon.persona` register and boundary constants. DEVON's personality therefore survives when `SYNTHESIS_PERSONA` is not explicitly set by the host.

This closes the text/personality seam. It does not turn browser speech synthesis into premium cloned TTS.

Current spoken transport remains the browser Web Speech API in `DevonChat.tsx`. That is functional and local, but the repo does not currently contain a verified ElevenLabs, Speechify, or equivalent premium TTS path for DEVON. Do not call the voice timbre final JARVIS quality until a dedicated TTS lane is connected and listened to end to end.

## Persistent access without weakening the shell

Current main already persists:

- DEVON login token per trusted browser device
- Operator key per device
- dedicated shell key per device

The unified cockpit reuses those stores. It does not introduce a fourth credential path.

The real shell still requires both:

1. a valid DEVON login session
2. the dedicated shell key

This meets the repeat-open use case within the configured access-token lifetime without replacing the stronger execution boundary with face-only authentication.

## Continuity and heartbeat

Build 13 remains authoritative:

- deterministic n8n pulse every six hours
- daily reflection
- Ledger Janitor at 02:30 UTC
- weekly learning-lane backup

DEVON's durable scheduler also exists separately through Agent Expansion create, due, and materialize routes. Scheduled goals do not silently auto-run effects.

## Governance preserved

- DEVON core remains effect free.
- external capability adapters own effects.
- WRITE and HIGH_IMPACT actions remain human gated.
- the real shell is Tee's human operator door, not an agent bypass.
- effect receipts, shared leases, idempotency, and ambiguous-effect refusal remain in place.
- no secret value was added to the repository.
- stale dashboard numbers were not copied into the new cockpit.

## Artifacts created by this consolidation

- `apps/web/components/command-center/UnifiedCommandCenter.tsx`
- `apps/web/components/command-center/CapabilityDock.tsx`
- `apps/web/components/command-center/MissionAdvisor.tsx`
- `docs/devon/SYS_OPS_devon-unified-command-center-handover_v1_2026-08-26.md`
- `docs/devon/SYS_OPS_devon-unified-command-center-handover_v2_2026-08-26.md`

## Artifacts modified

- `apps/web/app/command-center/page.tsx`
- `app/core/config.py`

## Acceptance gates

Do not call this merged, deployed, or final until all applicable evidence exists:

1. final-head repository CI passes
2. final-head Web CI typecheck passes
3. final-head production Next.js build passes
4. Vercel preview reaches READY
5. `/command-center` resolves on the preview
6. after authorized merge, production `/command-center` resolves
7. one stored session survives close and reopen on the trusted device
8. one Council answer returns in DEVON's canonical register
9. one read-only directive completes
10. one effectful directive stops for human approval and resumes only after approval
11. governed terminal executes a read
12. real shell refuses missing factors and executes a harmless command with both factors
13. capability mesh reads without exposing credentials
14. heartbeat continues independently of the browser
15. premium voice quality remains a separate audio acceptance gate until a dedicated TTS lane exists

## DEVON RECEIPT

TOKEN: dcp_chatgpt_38d2db6f727f636407b7efddae5a00e57da8e8ec
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: DEVON Unified Command Center v2 handover
BUILT: canonical cockpit, live advisor, live capability mesh, governed terminal selector, real PTY selector, canonical persona default
PRESERVED: approvals, effect receipts, leases, idempotency, shell two-factor boundary, Build 13 heartbeat
REJECTED AS LIVE TRUTH: stale Mission Control HUD values including obsolete eight-Area state
UNVERIFIED: Grok share body, final premium TTS timbre, final live production smoke until executed
NEXT GATE: final-head CI and Vercel preview verification
