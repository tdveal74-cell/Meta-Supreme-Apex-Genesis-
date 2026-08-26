---
title: DEVON Unified Command Center Handover
type: SYS_OPS
version: 1
date: 2026-08-26
area: Systems
status: branch-built-pending-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-unified-flagship-command-center
purpose: consolidate the surviving DEVON dashboards, terminals, voice surface, estate telemetry, and heartbeat context into one canonical operational cockpit
---

# DEVON Unified Command Center Handover v1

## Ruling

Flagship is the baseline, not the ceiling. This build does not replace working DEVON runtime or governance layers. It consolidates their operator surfaces into one cockpit and keeps specialized routes only as fallback or diagnostic surfaces.

## Source inventory actually inspected

Current main:

- `apps/web/app/command-center/page.tsx`
- `apps/web/components/devon/DevonChat.tsx`
- `apps/web/components/terminal/OperatorTerminal.tsx`
- `apps/web/components/terminal/RealShell.tsx`
- `apps/web/lib/api-base.ts`
- `app/services/agent_tasks.py`
- `app/api/v1/agent_tasks.py`
- `app/api/v1/agent_expansion.py`
- `app/api/v1/soul.py`
- `app/api/v1/health.py`
- `app/core/config.py`
- `services/devon/persona.py`
- `services/devon/areas.py`
- `.claude/skills/devon-learning-lane/references/heartbeat.md`
- `docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md`

Earlier operator surfaces:

- `docs/devon/assets/SYS_OPS_devon-console_v8_2026-08-23.html`
- `deploy/soul/console.html`
- `deploy/soul/terminal.html`
- `docs/devon/SYS_OPS_devon-browser-terminal-handover_v1_2026-08-24.md`
- superseded console generations located under `docs/devon/assets/`
- `website/index.html` and its ecosystem presentation were identified during the dashboard inventory

The Grok share URL supplied by Tee could not be retrieved by the available public web fetch path in this session. No feature claim from that conversation is treated as verified content.

## What was consolidated

### 1. One canonical cockpit

`apps/web/components/command-center/UnifiedCommandCenter.tsx`

The new command center carries forward the strongest control language from Console v8 while using the current live Next.js surfaces underneath it:

- copper instrument HUD visual system
- live DEVON API probe
- authenticated mind/provider probe
- Operator Bridge probe
- current clock and estate header
- nine Area brain map
- estate continuity organs
- voice and natural language interaction through `DevonChat`
- Council entry point
- embedded governed Operator Terminal
- embedded real bash PTY as a separate human operator lane
- explicit authority boundary between DEVON execution and Tee's shell

### 2. One execution deck

The command center no longer makes Tee choose between disconnected pages before acting.

Two execution modes are embedded in the same surface:

- `DEVON gated`: read commands flow; effectful commands stop at the existing human approval path.
- `Real shell`: a real xterm.js PTY for Tee's own operator work. It remains protected by the stored login session plus the dedicated shell key.

The older Vercel Sandbox terminal remains historical evidence and a useful isolation design reference. It is not made the canonical terminal because the current main branch already contains the newer real PTY and persistent sign-in path.

### 3. Live capability mesh

`apps/web/components/command-center/CapabilityDock.tsx`

The floating mesh reads authenticated runtime truth from:

- `/agent-tasks/tools`
- `/soul/status`
- `/agent-expansion/schedules`

It surfaces:

- Operator adapter readiness
- GitHub adapter readiness and repository scope count
- Browser capability
- Council agent count
- Scheduler status and visible scheduled goals
- effect receipts
- shared execution leases
- soul recall status
- next visible unmaterialized scheduled goal

The dock does not invent readiness. Failed telemetry reads show a degraded state.

### 4. DEVON personality is no longer optional by default

`app/core/config.py`

The synthesis voice now defaults from the canonical `services.devon.persona` register and boundary constants. Deployments can still override `SYNTHESIS_PERSONA`, but an omitted environment variable no longer reduces DEVON to generic synthesis prose.

The canonical source remains `services.devon.persona.py`. The config imports the register and anti-caricature boundary instead of creating a second independent persona.

### 5. Heartbeat stays separate from thought

The existing Build 13 heartbeat remains authoritative:

- deterministic pulse every six hours
- daily reflection
- daily Ledger Janitor at 02:30 UTC
- weekly learning-lane backup

The new cockpit shows the schedule but does not claim a live last-beat timestamp because the current API does not expose `devon_heartbeat_log` directly. The capability dock separately shows durable DEVON scheduled goals through the API.

## Login and operator convenience

The current main implementation already stores the DEVON login session on the trusted device and stores the Operator key and shell key in their existing browser slots. The unified cockpit reuses those paths rather than creating a fourth credential system.

This satisfies the intended use pattern of opening the command center repeatedly on the same trusted device without filling out a fresh login form every visit, subject to the API token's configured lifetime.

Security is not weakened into face-only authentication. The real shell retains two independent factors: a valid DEVON session and the dedicated shell key.

## Governance preserved

- DEVON core remains effect free.
- Agent tool adapters execute outside DEVON core.
- writes and high impact steps remain human gated.
- the real shell is Tee's operator door, not DEVON's bypass.
- effect receipts, leases, idempotency, and orphan-effect refusal remain untouched.
- no secret value was added to the repository.

## Files created

- `apps/web/components/command-center/UnifiedCommandCenter.tsx`
- `apps/web/components/command-center/CapabilityDock.tsx`
- `docs/devon/SYS_OPS_devon-unified-command-center-handover_v1_2026-08-26.md`

## Files modified

- `apps/web/app/command-center/page.tsx`
- `app/core/config.py`

## Verification state

At the time this handover file was created, code is present on the feature branch and CI has not yet been read on the final head. Do not call this shipped or merged until the final branch head passes the repository's actual CI gates and the deployed command center is opened against the live API.

Production smoke checks still required after merge:

1. `/command-center` loads on desktop and mobile widths.
2. DEVON API status reads online.
3. one stored session survives a close and reopen on the same trusted device.
4. one Council question returns in DEVON's canonical register.
5. one read-only agent directive completes.
6. one effectful directive stops on an approval card and continues only after Tee approves.
7. the governed terminal runs a read.
8. the real shell opens only with both factors and executes a harmless piped command.
9. the capability mesh reads tools, soul, and schedules without exposing credentials.
10. a heartbeat continues independently of the browser being open.

## DEVON RECEIPT

TOKEN: dcp_chatgpt_38d2db6f727f636407b7efddae5a00e57da8e8ec
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: Unified DEVON Command Center consolidation branch
STATE: built on feature branch, pending final CI and deployment smoke test
SOURCE OF TRUTH: Meta repo files listed above were actually opened in this session
SECURITY: existing approval gates and two-factor shell boundary preserved
NEXT GATE: final-head CI, then merge/deploy and live smoke verification
