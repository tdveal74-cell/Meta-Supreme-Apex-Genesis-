---
title: DEVON Control Plane Workspace
type: SYS_SPEC
version: 1
date: 2026-09-08
area: Systems
status: current
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
canonical_ref: claude/dreamy-wright-pv1f3l until merged, then main
owner: DEVON
supersedes_note: complements SYS_SPEC_devon-ecosystem_v1_2026-08-26 and SYS_SPEC_devon-ecosystem-control-map_v1_2026-08-26
---

# DEVON Control Plane Workspace v1

## What this document is

Tee's brief of 2026-09-08 asks for a unified three tier workspace over the
DEVON ecosystem: a Sovereign Admin Panel, an Interactive Cognitive 3D Hub, and
an Execution and Pipeline Monitor, with five modules and four operational
safeguards, and names four foundational files to start with. This document is
that brief mapped onto the estate as it actually stands.

Every row below is one of three things, and says which:

| Word | Meaning |
|---|---|
| **lives** | already in the repository before this arc; the path was opened and read, not remembered |
| **built** | added in this arc, with the check that proved it named in the receipts section |
| **not built** | absent; the row names where it goes and what gate it waits on, and claims nothing |

A claim that everything is live would be exactly the failure the ecosystem
spec exists to stop, so the honest split is kept rather than smoothed over.

## The four foundational files, and what each one turned out to be

| Asked for | What exists | What this arc did |
|---|---|---|
| Project structure | the estate below | this document, with every path verified |
| Production Docker Compose | `infrastructure/docker/docker-compose.yml` (development: mounts, reload, `pnpm dev`) | `infrastructure/docker/docker-compose.prod.yml`: postgres, redis, api, presence, web, and n8n under a profile; loopback binds; secrets required |
| Core React 3D canvas | nothing; the web workspace had no three.js | `apps/web/components/presence/` and `/presence` |
| Postgres `schema.sql` for the Live State Ledger | `database/schemas/012_live_state_ledger.sql` with `014_artifact_body.sql` and `018_schema_convergence.sql`; ten tables plus `universal_receipts`, writer, API and tests all live since 2026-08-26 | `019_event_hash_chain.sql`: the missing half, a hash chain over the Event Bus and a signed receipt |

There is deliberately no second `schema.sql`. A file that restated the ledger
beside 012 would be the second registry that drifts, which the estate's own
precedence doctrine forbids. The schema is the ordered set of scripts under
`database/schemas/`, applied by `conftest.py` for tests and by the Alembic
chain for deploys, and CI proves the two builds produce the same database.

## The map

```
Meta-Supreme-Apex-Genesis-/
  app/                                 lives   FastAPI control plane (/api/v1)
    api/v1/ledger.py                   lives   Live State Ledger routes
    api/v1/ledger.py  GET .../provenance   built   the signed verification payload
    api/v1/operator_shell.py           lives   xterm.js real shell, two factors
    api/v1/operator.py                 lives   governed operator commands
    services/live_state_ledger.py      lives   the only thing that writes the ledger
    services/live_state_ledger.py      built   hashes every event, signs every receipt
    services/provider_usage.py         lives   per account daily token ledger
    models/live_state_ledger.py        lives   storage shapes (019 columns added)
  services/
    devon/ecosystem.py                 lives   the organism: hierarchy, events, receipt law
    devon/provenance.py                built   hash chain and signature, pure
    devon/approval.py                  lives   the approval authority
    devon/vault.py                     lives   the estate registry (n8n ids, tables, indexes)
    intelligence/providers/            lives   cerebras, anthropic, openai, mock
    agent_runtime/                     lives   turns, tools, leases, effects, presence authority
    operator/bridge.py                 lives   governed command bridge
  apps/
    api/                               lives   secondary tree (see REPOSITORY_STATUS.md)
    presence/                          built   streaming middleware, Python
      main.py                          built   /health, /livekit/token, WS /ws/presence
      protocol.py                      built   wire protocol v1, ARKit names, priorities
      buffer.py                        built   safeguard 1, server half
      breaker.py                       built   safeguard 2, breaker and router
      inference.py                     built   token streamers (mock, provider adapter)
      speech.py                        built   viseme frames (mock); Cartesia is a stub
      livekit_token.py                 built   LiveKit JWT minting with PyJWT
      session.py                       built   one conversation: states, turns, interrupt
      settings.py                      built   env, refuses a default key in production
    web/                               lives   Next.js 15, React 19
      app/command-center/              lives   tier 1 cockpit (see below)
      app/terminal/  app/shell/        lives   governed terminal, real shell
      app/presence/page.tsx            built   tier 2 avatar surface
      components/presence/             built   canvas, socket, LiveKit, barge-in, stage
      lib/presence/                    built   protocol types, FrameBuffer, VAD, pure
      scripts/presence-check.ts        built   proves the pure modules with node
  database/
    schemas/001 .. 018                 lives   the schema, in order
    schemas/019_event_hash_chain.sql   built   hash columns, signature columns, triggers
    migrations/versions/019_*.py       built   the same script through Alembic
  infrastructure/docker/
    docker-compose.yml                 lives   development stack
    docker-compose.prod.yml            built   production stack
    Dockerfile.api                     lives   Railway image
    Dockerfile.presence                built   presence image, same hashed closure
    Dockerfile.web.prod                built   next build, next start
    initdb/010-n8n-database.sh         built   n8n database on first init
    .env.prod.example                  built   every variable, secrets blank
  n8n/devon/                           lives   Code node sources read by CI
  docs/devon/                          lives   the dated record; this file
```

## Tier 1: Sovereign Admin Panel

| Piece | Status | Where |
|---|---|---|
| Cockpit with live probes, nine Area map, advisor, capability dock | lives | `apps/web/components/command-center/UnifiedCommandCenter.tsx`, `MissionAdvisor.tsx`, `CapabilityDock.tsx` |
| Approvals: raise, list, rule, single use tokens, owner scoping | lives | `services/devon/approval.py`, `app/services/devon_approval_store.py`, `/api/v1/devon/approvals` |
| Emergency stop, engage from any level, release by Tee only | lives | `/api/v1/ledger/emergency-stop` |
| Passkey sign in | lives | `PasskeyAccess.tsx`, `app/api/v1/auth.py` |
| Ledger read and provenance verdict in the cockpit | not built | a card under the command center reading `GET /api/v1/ledger/intents/{id}/provenance`; the route is built and tested, the card is not |

## Tier 2: Interactive Cognitive 3D Hub

| Piece | Status | Where |
|---|---|---|
| WebGL avatar viewport, `@react-three/fiber`, morph targets driven by frames | built | `apps/web/components/presence/DevonAvatarCanvas.tsx` |
| Rigged likeness with ARKit blendshapes | not built | an owned asset gate. The canvas loads a GLB from `NEXT_PUBLIC_DEVON_AVATAR_URL` when one exists and otherwise renders a procedural placeholder head so the frame pipeline can be watched end to end. No stock humanoid ships here: DEVON's face is Tee's call, and "voice and identity owned, never rented" applies to the face as much as the voice |
| WebSocket frame listener with sliding window | built | `usePresenceSocket.ts`, `lib/presence/frame-buffer.ts` |
| WebRTC audio via LiveKit | built, unverified live | `useLiveKitAudio.ts` types against `livekit-client` 2.22.3 and the token route mints the documented claim layout; no LiveKit server was reachable in this build, so the join path has not been exercised |
| Barge in: client VAD, instant local flush, interrupt over the wire | built | `useBargeIn.ts`, `lib/presence/vad.ts`. The HUD shows the measured local reaction time; the 50 ms target is a target until a human measures it in a browser with a microphone |
| Cerebras text at 450 tok/s streamed to speech | not built as streaming | the provider base class has no streaming API; `ProviderTokenStreamer` completes then yields word tokens. SSE against `api.cerebras.ai` is the next gate |
| Cartesia or Hume EVI phoneme to viseme | not built | `speech.py` carries the adapter seam and a mock that produces ARKit frames from text; the vendor response shapes were not verified here and nothing pretends they were |
| Agent readiness matrix (IDLE, THINKING, EXECUTING, BLOCKED, FAILED per agent) | not built | `apps/web/components/readiness/`; reads would come from `/api/v1/agent-tasks` and the `agent_task_runs` lease rows, which already exist |
| Dynamic load balancing across agents | not built | needs the matrix and a latency ledger first; nothing in the estate balances today and this document does not say otherwise |
| 2nd Brain knowledge graph across Drive, Notion, Pinecone namespaces | not built | `apps/web/components/mind/`; the three indexes and their deletion protection are recorded in `services/devon/ecosystem.py`, and no route yet exposes vector activations |

## Tier 3: Execution and Pipeline Monitor

| Piece | Status | Where |
|---|---|---|
| Executor registry and routing (n8n internal, Zapier external, UNROUTED parked) | lives | `services/devon/ecosystem.py`, `executors` table |
| n8n workflow registry with ids, states, and proofs | lives | `services/devon/vault.py` |
| n8n Code node sources parsed in CI | lives | `n8n/devon/`, the standalone job |
| Execution telemetry card, retry and queue viewer, version sync against GitHub | not built | `apps/web/components/execution/`; the VPS instance at `n8n.editforge.online` is the executor of record and `scripts/n8n_migrate.py` is the existing bridge to it |
| Observability and cost | lives in part | `provider_usage` table, `PROVIDER_DAILY_TOKEN_CAP` refusal at 429, `/api/v1/health`; a widget over them is not built |

## Module 5: security shell and secrets

| Piece | Status | Where |
|---|---|---|
| Embedded xterm.js terminal | lives | `apps/web/components/terminal/RealShell.tsx`, `app/api/v1/operator_shell.py` |
| Signed requests before a terminal operation | lives, differently | the shell requires a valid DEVON JWT (HMAC-SHA256 under `SECRET_KEY`) and a separate shell key compared in constant time. That is two factors, not a per request HMAC over the command body. A per request signature is not built and this document does not call the existing gate one |
| Ephemeral password and secret vault, zero knowledge generator, injection into executors | not built | nothing in the repository generates or stores secrets, on purpose: every key lives in the environment, and `app/core/config.py` refuses to start in production on the public default. A vault is a design decision for Tee, not a file to add quietly |

## The four safeguards

| Safeguard | Status | Where and how proved |
|---|---|---|
| 1. Adaptive sliding window, audio real time, frames compressed by priority | built | server `apps/presence/buffer.py`, client `apps/web/lib/presence/frame-buffer.ts`. Priority 2 (idle motion) drops first, then 1 (brows, eyes), then 0 (mouth) is thinned; audio never enters the buffer. Proved by `test_presence_buffer.py` and `scripts/presence-check.ts`. Not yet measured against a real 60 fps renderer under real audio |
| 2. Circuit breaker on TTFT above 500 ms or a rate limit, fallback on the same connection | built | `apps/presence/breaker.py`. The router waits for the primary's first token, cancels it on breach, and continues the same turn from the fallback; the WebSocket stays up. Proved by `test_presence_breaker.py` and `test_presence_service.py` with an injected clock. Not exercised against live Cerebras |
| 3. SHA-256 chain over every state transition, signed Universal Receipt | built | `services/devon/provenance.py`, migration 019, writer, `GET /api/v1/ledger/intents/{id}/provenance`. Proved by `test_devon_provenance.py` (pure) and `test_live_state_ledger_provenance.py` (database, with negative controls that disable the trigger, alter a row, and watch the verifier name it) |
| 4. Token budget and cost guardrails with warning thresholds and hard caps | lives in part | the hard cap and the per account ledger exist (`017_provider_usage`); warning thresholds and the widget are not built |

## Safeguard 3 in detail: the cryptographic ledger

Each event carries `prev_hash` and `hash`. The hash is SHA-256 over canonical
JSON of the chain version, the previous hash, the intent id, the sequence
number, the event name, the action id, the payload and the occurrence time to
the microsecond. The first event of an intent links to the empty string.

The receipt carries `head_hash`, `chain_length`, `signature` and
`signature_key_id`. The signature is HMAC-SHA256 under `SECRET_KEY` over a
digest of the intent id, the head hash, the chain length, the six receipt
fields and the issue time. Rotating the key changes the key id on new receipts;
old receipts still verify their chain and report that they were signed under
another key, rather than reading as forged.

The database refuses an UPDATE on `events` and on `universal_receipts` with a
BEFORE UPDATE trigger. DELETE is left to the cascade from `intents` and `users`
because an owner's right to be removed outranks the audit trail; a removed row
still shows, because the verifier reports the gap. Rows written before 019
carry an empty hash and are counted as unhashed, never backfilled: a backfilled
hash would claim a provenance those rows never had.

The writer refuses to issue a receipt over a chain that does not verify. The
verdict names every break by sequence number.

## Wire protocol v1

JSON text over `WS /ws/presence` on the presence service. The first client
message is `hello` with the DEVON access JWT; anything else, or nothing within
fifteen seconds, closes the socket (4400 malformed, 4401 unauthenticated). The
token never appears in the URL.

| Direction | `t` | Fields |
|---|---|---|
| client | `hello` | `token`, `client`, `protocol` |
| client | `say` | `turn_id`, `text` |
| client | `interrupt` | `turn_id`, `at_ms` |
| client | `render` | `turn_id`, `behind_ms`, `fps` |
| client | `ping` | `at_ms` |
| server | `ready` | `session_id`, `protocol`, `speech`, `inference`, `fallback`, `livekit{configured,url}` |
| server | `state` | `state` in idle, listening, thinking, speaking; `turn_id`, `at_ms` |
| server | `token` | `turn_id`, `text` |
| server | `frame` | `turn_id`, `seq`, `at_ms`, `priority` 0 to 2, `weights` (ARKit names, 0 to 1) |
| server | `audio` | only without LiveKit: `seq`, `at_ms`, `codec` pcm_s16le, `rate` 16000, `b64` |
| server | `interrupt_ack` | `turn_id`, `flushed_frames`, `server_latency_ms` (measured) |
| server | `metrics` | `provider`, `fell_back`, `ttft_ms`, `breaker`, `frames_sent`, `frames_dropped`, `tokens` |
| server | `pong`, `error` | `at_ms`, `server_ms`; `code`, `message` |

Speech to text is not on this wire yet: the foundation takes `say` with text.
Speech in is the same gate as speech out and lands with it.

## Running it

Development, unchanged: `make up` uses `infrastructure/docker/docker-compose.yml`.

Production:

```bash
cp infrastructure/docker/.env.prod.example infrastructure/docker/.env.prod
# fill in every REQUIRED line
docker compose --env-file infrastructure/docker/.env.prod \
  -f infrastructure/docker/docker-compose.prod.yml config       # validate
docker compose --env-file infrastructure/docker/.env.prod \
  -f infrastructure/docker/docker-compose.prod.yml up -d --build
# only for a self contained stack, never beside the VPS executor:
docker compose --env-file infrastructure/docker/.env.prod \
  -f infrastructure/docker/docker-compose.prod.yml --profile executor up -d
```

Every port binds to 127.0.0.1; a TLS terminator fronts the stack. Redis is
provisioned for the real time relay and nothing opens it yet; the compose file
says so in its own header rather than letting a running container imply a
wired one.

## Receipts for this arc

Every line is a command that was run in this session on the branch head, with
the exit code captured directly rather than through a pipe.

| Check | Command | Result |
|---|---|---|
| Pure provenance, integrity, ecosystem | `python3 -m pytest -q test_devon_provenance.py test_devon_integrity.py test_devon_ecosystem.py` | 225 passed, exit 0 |
| Ledger against PostgreSQL 16, with negative controls | `python3 -m pytest -q test_live_state_ledger_provenance.py test_live_state_ledger.py test_devon_knowledge_loop_binding.py` | 39 passed, exit 0 |
| Alembic round trip | `alembic upgrade head`, `alembic downgrade 018_schema_convergence`, `alembic upgrade head` on a fresh database | all three exit 0, head reads `019_event_hash_chain` |
| The two schema builds agree | `scripts/schema_shape.py` on the Alembic build and on the SQL build, diffed | identical, both triggers present |
| Standalone job, exactly as CI runs it | `env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q` over the ten offline files | 137 passed, exit 0 |
| Container contract import | `env -u PYTHONPATH DEFAULT_AI_PROVIDER=mock python3 -c "from app.main import app; ..."` | exit 0 |
| Engine job | `python3 -m pytest -q test_council.py test_phase4_council.py test_security.py` with the two deselects | 25 passed, exit 0 |
| Soul host vendoring | `python3 -m pytest -q test_deploy_soul.py test_deploy_soul_operator.py test_deploy_soul_conflict_policy.py` | 112 passed, exit 0 (`provenance.py` vendored byte for byte) |
| Production compose | `docker compose --env-file <filled example> -f infrastructure/docker/docker-compose.prod.yml --profile executor config -q` | exit 0; six services with the profile, five without; a missing `SECRET_KEY` refuses with its own message |
| Web typecheck and build | `npx tsc --noEmit`; `npx next build` | both exit 0; route `/presence` 1.44 kB first load 107 kB |
| Pure presence modules | `node --experimental-strip-types scripts/presence-check.ts` | 12 checks passed, exit 0 |
| Workspace audit | `pnpm audit --audit-level=moderate` | no known vulnerabilities, exit 0 |
| Headless render, no presence server | Playwright against `next start`, Chromium on SwiftShader (`ANGLE Vulkan SwiftShader`) | canvas 800 by 499, rig `procedural head`, socket `locked`, state `idle`, 28 fps on the software renderer |
| Presence service, offline, as the standalone job would run it | `env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q test_presence_buffer.py test_presence_breaker.py test_presence_livekit_token.py test_presence_service.py` | 51 passed, exit 0 |
| Presence service, live | `uvicorn apps.presence.main:app --port 8010`, then `GET /health` | `status ok`, `inference mock`, `speech mock`, `livekit_configured false`, `audio_over_websocket true`, breaker `closed`; `POST /livekit/token` without a bearer answers 401 |
| Headless browser through the live presence service | Playwright against `next start` and the mock presence service, with a DEVON JWT minted under the service's key placed in the shared storage slot | socket `ready`; `say` reached `speaking` after 251 ms; 55 frames received, the freshest shown and 33 skipped by the software renderer at 19 fps; face age 10 ms, behind 94 ms; the HUD Interrupt button acked by the server in 0.3 ms with 823 frames flushed server side and 12 client side; state back to `listening`; server metrics reconcile at 70 sent plus 823 dropped |
| Headless browser with a fake microphone | the same run with Chromium's fake media device | the microphone opened (`live`) but the fake device delivered silence (rms 0.000), so the voice trigger never fired; the mic reaction figure stays unmeasured and only the manual path is proved |
| Dash ban | `grep -rn` for the two banned marks over every file this arc wrote | clean |
| Full API suite, presence tests included | `python3 -m pytest -q --tb=short` | 1497 passed, exit 0, 179 s |
| Lint | `python3 -m ruff check .` | All checks passed, exit 0 |

The 28 fps figure is the software renderer in a container and says nothing
about a GPU. The browser run proves the page mounts and the placeholder rig
receives the driver; it does not prove a 60 fps face.

## What is still not live, stated plainly

- No LiveKit server, Cartesia key, or Cerebras key was reachable in this build.
  Every adapter that touches one is typed, tested against a mock, and marked.
- The avatar is a procedural placeholder until Tee supplies an owned likeness
  with ARKit blendshapes. The pipeline is demonstrable; the face is a ruling.
- The 50 ms barge in figure is a target. The HUD measures the local reaction
  and a human with a microphone reads it; nothing here reports it as met.
- Redis is provisioned and unwired. Speech to text is not on the wire.
- The agent readiness matrix, the knowledge graph, the n8n execution hub, the
  cost widget, the ledger card in the cockpit, and the secret vault are not
  built, and each row above names where it goes.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_SPEC
ARTIFACT: DEVON Control Plane Workspace v1
BUILT: migration 019 hash chain and signed receipt with provenance route; presence streaming service with buffer, breaker, LiveKit token, WebSocket protocol; web presence surface with react-three-fiber canvas, frame buffer, VAD barge in; production compose with pinned images and loopback binds
PRESERVED: one ledger schema (012 plus increments, no second schema file); approvals never granted by the ledger; DEVON core effect free; no secret in the repository; no stock likeness
UNVERIFIED: LiveKit join, Cartesia, live Cerebras streaming, the 50 ms barge in figure, the compose stack under a real docker daemon
NEXT GATE: Tee reviews the draft PR; the rigged owned likeness; a LiveKit and Cartesia lane proved end to end by a human listening
