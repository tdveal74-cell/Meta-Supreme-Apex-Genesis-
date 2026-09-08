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
| Production Docker Compose | `infrastructure/docker/docker-compose.yml` (development: mounts, reload, `pnpm dev`) | `infrastructure/docker/docker-compose.prod.yml`: postgres, redis, migrate, api, presence, web, and n8n under a profile; loopback binds; secrets required; the API on a least privilege role |
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
    initdb/020-api-role.sh             built   the devon_api runtime role on first init
    initdb/sql/api-role.sql            built   the role, CONNECT and USAGE, TEMP and CREATE revoked
  database/grants/
    devon_api.sql                      built   what the role may do to the tables, applied after every migration
    apply_devon_api.py                 built   applies it as the owner from the migrate service
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
| WebRTC audio via LiveKit | built, unverified live | `useLiveKitAudio.ts` types against `livekit-client` 2.22.3 and the token route mints the documented claim layout for the caller's own presence session only, with the identity fixed to the verified user; no LiveKit server was reachable in this build, so the join path has not been exercised |
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
| One HS256 key verifying sessions in two services | open ruling for Tee | the presence service verifies DEVON JWTs under the same `SECRET_KEY` as the API, and with HS256 a verifier can also sign. Receipts are no longer signed under it. Closing the rest means asymmetric tokens or the presence service asking the API to verify; the recommendation is asymmetric tokens, and the call is Tee's |
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

The payload is hashed as the database stores it, not as Python first rendered
it. The first cut hashed Python's rendering, and a gauntlet fed it `1e16` and
`-0.0`: JSONB renders those `10000000000000000` and `0.0`, so every such
event read as altered and the intent could never be receipted. The writer now
asks PostgreSQL to render the payload through `jsonb` before hashing and
decodes that rendering the way the ORM decodes the stored column, so the
writer and the verifier hash the same bytes by construction. NaN, infinity
and text UTF-8 cannot encode are refused at the door with a reason, never a
500 at the insert.

The receipt carries `head_hash`, `chain_length`, `signature` and
`signature_key_id`. The signature is HMAC-SHA256 over a digest of the intent
id, the head hash, the chain length, the six receipt fields and the issue
time. The signing key is `RECEIPT_SIGNING_KEY`, or a key derived from
`SECRET_KEY` when none is set; it is never `SECRET_KEY` itself, and the
compose stack passes it to the API only. `RECEIPT_SIGNING_KEYS_PREVIOUS` is
the rotation ring: a receipt signed under an earlier key still verifies and
reports which key signed it, and one signed under a key no longer in the ring
is named as such rather than reading as forged.

The database refuses UPDATE on `events` and on `universal_receipts`, and on
`intents` admits a change to `state` and `updated_at` only: the opening event
hashes the owner and the statement, so a row handed to another account or
reworded no longer matches its own first hash and the verifier says so. A
DELETE on `events` or `universal_receipts` is admitted only once the intent
is gone, and on `intents` only once the owner is gone: that is what a
cascade is, the parent has already left the transaction when the referential
action reaches the child, and a statement aimed at the child while the
parent stands is refused from any trigger depth. The third gauntlet pass
showed why depth was the wrong test: a temporary table's trigger deletes at
depth 2. Every trigger is `ENABLE ALWAYS`, so replica mode does not silence
it. Rows written before 019 carry an empty hash and are counted as unhashed,
never backfilled, and only as a prefix: an unhashed row standing after
hashed rows was written around the writer and is named as a break.

The writer refuses to append to a chain that does not verify and refuses to
issue a receipt over one. The verdict names every break by sequence number.
`verified` on the provenance payload means a complete chain (every row
hashed, every link sound) and a receipt that certifies exactly that chain. An
intent without a receipt reports `receipted: false`; an intent whose prefix
predates the chain reports `chain.complete: false` and is receipted on trust,
not on proof, because the verifier cannot tell pre 019 history from rows
planted to look like it.

What the database cannot own is stated rather than pretended away. A role
that can disable or drop the triggers, TRUNCATE the tables, or delete users
can rewrite or erase history. The production compose therefore runs the API
as `devon_api`, a role that reads and writes every table, deletes only where
the application deletes (workflows, memories, knowledge items, agent tasks
and what hangs off them), never deletes users, intents, events or receipts,
and holds no CREATE, no TEMP, no TRUNCATE, no ownership and no superuser.
The role is created on first init by `infrastructure/docker/initdb/sql/api-role.sql`
and granted after every migration by `database/grants/devon_api.sql` through
`database/grants/apply_devon_api.py`, run by the one shot `migrate` service,
which is the only container that holds the owner credential; the presence
container holds no database credential at all and n8n has its own role and
database. The test suite runs both SQL files against the test database, takes
the role, appends through the writer, and proves each refusal, including the
temporary table and the temporary function. Proving history to a reader who
does not trust the database at all needs the chain heads anchored outside it,
which is a later gate.

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

Migrations run as the owner in the one shot `migrate` service, which then
applies `database/grants/devon_api.sql` so every table a migration creates is
granted as it appears; the API runs as `devon_api`, created by
`initdb/020-api-role.sh` on the first start of the postgres volume, which is
the image's documented behaviour. A stack whose volume predates this
revision creates the role by hand from `initdb/sql/api-role.sql`.
`API_DB_PASSWORD` is required beside `POSTGRES_PASSWORD`; `N8N_DB_PASSWORD`
must be set before the first start when the executor profile will be used,
because the n8n role and database are created at that moment only.

Providers default to `mock` in the example env and in the compose file, so the
stack starts with the keys still blank and `/health` says simulated out loud.
The first cut shipped `cerebras` with a blank key, which refused to start the
presence service and, because the web container waits on its health, the web
surface with it. A provider named without its key still refuses, and the
refusal now names `PRESENCE_INFERENCE` rather than the API's variable.

## The gauntlet, and what it changed

A fresh critic with no build context attacked the branch on 2026-09-08 and
returned QUARANTINE. Every check the branch had was green at the time; none of
them fed the chain a float, a DELETE, or the example env. The confirmed
findings and their fixes, all re-measured:

| Finding | Was | Now |
|---|---|---|
| The hash did not survive its own storage: `1e16`, `-0.0`, `1.5e300` written by the writer read as altered on verification | hashed Python's rendering | hashed as PostgreSQL renders the jsonb; nine numeric cases in `test_live_state_ledger_provenance.py` |
| History was rewritable through DELETE: drop the tail and the receipt, append, re-issue, `verified true` | DELETE open | BEFORE DELETE trigger refusing a direct statement and admitting the cascade; direct delete and cascade both proved |
| The pre 019 grace laundered a planted unhashed row and the next append linked to genesis behind it | any empty hash reset the chain | unhashed rows only as a prefix; the writer refuses to append to a chain that does not verify |
| The example env named `cerebras` with a blank key, so the stack did not start | `cerebras` default | `mock` default, and the refusal names `PRESENCE_INFERENCE` |
| One HS256 key signed sessions and receipts in two services | receipts under `SECRET_KEY` | receipts under a derived or dedicated key the presence service never receives, with a rotation ring; the shared session key is an open ruling |
| A signed in user could mint a LiveKit token for any room under any identity | caller named both | room must be the caller's own open session; identity is the verified user |
| A synthesiser frame at `at_ms` infinity held the drain loop open forever and NaN reached the wire | weights validated only | timeline validated, NaN refused on the wire, the turn fails by name and lands on listening |
| `verified: true` on an intent with no receipt | chain alone | receipt required; `receipted` says which half is missing |
| NaN in an HTTP payload was a 500 at the insert | unhandled | refused at the door with a reason, 409 |

The critic's scores before the fixes: correctness 2, security 3, flagship 2,
mean 3.5.

A second fresh critic attacked the fix commit and returned QUARANTINE again,
with security 3 and a mean of 3.8. It confirmed every first pass fix and
found the doors the fixes had left open. Each was closed and re-measured:

| Finding | Was | Now |
|---|---|---|
| Delete the intent (the cascade admitted it), re-insert its id, replay a different history, `verified true` | the guard sat on the leaf tables only | BEFORE DELETE on `intents` admitting only the cascade from `users`; proved directly |
| The shipped stack connected the API as the database superuser, so TRUNCATE, DISABLE TRIGGER, replica mode and a scratch table with a deleting trigger were all available to it | one owner credential for migrations and runtime | a `devon_api` role with DML only, a one shot `migrate` service as the owner, every trigger `ENABLE ALWAYS`; the role script runs in the test suite and each refusal is proved |
| Switching from the derived receipt key to a dedicated one, or rotating `SECRET_KEY`, orphaned every earlier receipt | the ring held only the configured keys | the derived key of the current secret is always in the ring, and `secret:<old>` entries derive an earlier one; both proved |
| A NUL in a payload string passed the door and failed at the cast, mid transaction, as a 500 | NaN and infinity refused, NUL not | NUL refused at the door, 409 over HTTP |
| An all unhashed intent read `verified true`; the verifier cannot tell a forged post 019 prefix from pre 019 history | `verified` required intact | `verified` requires complete; a pre 019 prefix is receipted on trust and says so |
| A NaN ping killed the socket on the way out, an infinite `behind_ms` poisoned every later turn | numbers checked for type only | non finite numbers refused by name, the socket stays up |

One design residual is recorded, not fixed: the writer accepts a lawful late
event after a receipt (`ACTION_FAILED` after `ACTION_COMPLETED`), and the
verifier then reports growth past the receipt the same way it reports
tampering. Distinguishing the two needs a second receipt law and is a ruling
for Tee.

A third fresh critic attacked the second fix commit and returned QUARANTINE a
third time, with security 2 and a mean of 3.4. It confirmed every second
pass fix and then rewrote a receipted history as the very role the stack
ships. Each door was closed at the root and re-measured:

| Finding | Was | Now |
|---|---|---|
| The runtime role could create a temporary table with a trigger that deleted events and the receipt at trigger depth 2, which the guard admitted, then re-receipt to `verified true` | the delete guard asked how deep the call stack was; TEMP is granted to PUBLIC by default | the guard asks whether the parent row is already gone, which is what a cascade means, from any depth; TEMP is revoked from PUBLIC on the database; both proved, the depth 2 attack itself is a negative control in the suite |
| The runtime role held DELETE on every table, including `users`, so the owner cascade was plain DML: delete the user, re-insert, replay | one broad grant | DELETE granted only where the application deletes; `users`, `intents`, `events` and `receipts` never; a new delete path fails loudly with permission denied |
| The owner credential still shipped to the presence container through the shared env, and n8n connected as the owner | one env anchor for every Python container | the shared anchor carries no database URL; only `migrate` holds the owner credential, `api` holds `devon_api`, presence holds none, n8n has its own role and database |
| The intent row was unbound: `owner_id` and `stated` could be rewritten and the thief's read of the chain was `verified true` | the opening event hashed the channel only | the opening event hashes the owner and the statement; a BEFORE UPDATE trigger on `intents` admits `state` and `updated_at` only; a handed over or reworded row is named by the verifier |
| The runtime role could rewrite `alembic_version` and wedge the next migration | default privileges | the role reads `alembic_version` and nothing else |
| A 400 digit integer in a wire number overflowed `float()` and killed the socket | finite check after the cast | the overflow is caught and refused by name, the socket stays up |
| The six ordinary characters of a written out NUL escape were refused as a NUL | the check read the rendered text | the check walks the values themselves |

The fourth pass is recorded in the receipts below.

## Receipts for this arc

Every line is a command that was run in this session on the branch head, with
the exit code captured directly rather than through a pipe.

| Check | Command | Result |
|---|---|---|
| Pure provenance, integrity, ecosystem | `python3 -m pytest -q test_devon_provenance.py test_devon_integrity.py test_devon_ecosystem.py` | 232 passed, exit 0 |
| Ledger against PostgreSQL 16, with negative controls | `python3 -m pytest -q test_live_state_ledger_provenance.py test_live_state_ledger.py test_devon_knowledge_loop_binding.py` | 71 passed, exit 0, on a test database rebuilt from the schema files; includes the `devon_api` role built from its two SQL files and refused on create, temporary table, temporary function, truncate, disable trigger, replica mode, `alembic_version`, deleting users and every direct ledger delete, while a workflow delete succeeds; and the depth 2 trigger attack itself, run as the owner, refused by the parent-gone rule |
| Alembic round trip | `alembic upgrade head`, `alembic downgrade 018_schema_convergence`, `alembic upgrade head` on a fresh database | all three exit 0, head reads `019_event_hash_chain`, the downgrade removes all six triggers and all three functions, the upgrade restores all six as `ENABLE ALWAYS` |
| The two schema builds agree | `scripts/schema_shape.py` on the Alembic build and on the SQL build, diffed | identical; `019_event_hash_chain.sql` applied twice in a row without error; all six triggers present |
| The role and grants scripts as shipped | `psql -v api_password=... -f initdb/sql/api-role.sql` (real psql interpolation, through `set_config`), then `python3 database/grants/apply_devon_api.py` as the owner, on the SQL built test database and on an Alembic built one | both exit 0, seven grant statements; as `devon_api`: DELETE on `workflows` true, on `events` and `users` false, `alembic_version` SELECT true and UPDATE false, TEMP false, CREATE on the schema false |
| Standalone job, exactly as CI runs it | `env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q` over the ten offline files | 137 passed, exit 0 |
| Container contract import | `env -u PYTHONPATH DEFAULT_AI_PROVIDER=mock python3 -c "from app.main import app; ..."` | exit 0 |
| Engine job | `python3 -m pytest -q test_council.py test_phase4_council.py test_security.py` with the two deselects | 25 passed, exit 0 |
| Soul host vendoring | `python3 -m pytest -q test_deploy_soul.py test_deploy_soul_operator.py test_deploy_soul_conflict_policy.py` | 112 passed, exit 0 (`provenance.py` vendored byte for byte) |
| Production compose | `docker compose --env-file <filled example> -f infrastructure/docker/docker-compose.prod.yml --profile executor config -q` | exit 0; seven services with the profile, six without (`migrate` added); a missing `SECRET_KEY` refuses with its own message; read back from the resolved file: only `migrate` holds the owner URL, `api` holds `devon_api` and the receipt keys, `presence` holds no database URL, `n8n` connects as `n8n` |
| The example env starts the presence service | `PresenceSettings.from_env()` under the filled example with `ENVIRONMENT=production`, then `create_app` | starts, inference `mock`, no fallback; the same with `PRESENCE_INFERENCE=cerebras` and no key refuses and names `PRESENCE_INFERENCE` |
| Web typecheck and build | `npx tsc --noEmit`; `npx next build` | both exit 0; route `/presence` 1.44 kB first load 107 kB |
| Pure presence modules | `node --experimental-strip-types scripts/presence-check.ts` | 12 checks passed, exit 0 |
| Workspace audit | `pnpm audit --audit-level=moderate` | no known vulnerabilities, exit 0 |
| Headless render, no presence server | Playwright against `next start`, Chromium on SwiftShader (`ANGLE Vulkan SwiftShader`) | canvas 800 by 499, rig `procedural head`, socket `locked`, state `idle`, 28 fps on the software renderer |
| Presence service, offline, as the standalone job would run it | `env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q test_presence_buffer.py test_presence_breaker.py test_presence_livekit_token.py test_presence_service.py` | 57 passed, exit 0 |
| Presence service, live | `uvicorn apps.presence.main:app --port 8010`, then `GET /health` | `status ok`, `inference mock`, `speech mock`, `livekit_configured false`, `audio_over_websocket true`, breaker `closed`; `POST /livekit/token` without a bearer answers 401 |
| Headless browser through the live presence service, on the post gauntlet code | Playwright against `next start` and the mock presence service, with a DEVON JWT minted under the service's key placed in the shared storage slot | socket `ready`; `say` reached `speaking` after 262 ms; 62 frames received, the freshest shown and 37 skipped by the software renderer at 17 fps; face age 1 ms, behind 68 ms; the HUD Interrupt button acked by the server in 0.7 ms with 823 frames flushed server side and 13 client side; state back to `listening`; server metrics reconcile at 70 sent plus 823 dropped; a LiveKit token asked for a foreign room answers 503 while LiveKit is unset, and 403 once it is configured (proved in `test_presence_service.py`) |
| Headless browser with a fake microphone | the same run with Chromium's fake media device | the microphone opened (`live`) but the fake device delivered silence (rms 0.000), so the voice trigger never fired; the mic reaction figure stays unmeasured and only the manual path is proved |
| Dash ban | `grep -rn` for the two banned marks over every file this arc wrote | clean |
| Full API suite, presence tests included | `python3 -m pytest -q --tb=short` | 1541 passed, exit 0, 174 s |
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
