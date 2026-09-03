# Changelog

All notable changes to Meta Supreme Apex Genesis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **DEVON and Hermes audit of 2026-09-02** (`docs/devon/SYS_OPS_devon-hermes-agent-audit_v1_2026-09-02.md`, PR #110) and the fix PRs that followed it, each merged after a fresh critic pass and green CI:
  - #111: the three `/devon` approval routes are authenticated and owner-scoped, `devon_approvals` carries an owner (migration 015), registration is closed behind `DEVON_REGISTRATION_KEY`, and migration 014 ships the artifact body column
  - #113: the knowledge-loop ruling is bound to its intent and a candidate hash at propose, commit verifies the approvals row, and the generic ledger route refuses forged approval events
  - #114: the three runtime expansion tools spend their approval and write the durable schedule, proposal and subagent tables
  - #115: the EditForge HTTP lane spends its approval once, mints command ids and gates retry and cancel on the spent approval; a deployed process refuses to boot on the public default `SECRET_KEY`
  - #116: the operator read lane judges every path argument after symlink resolution and `ps` left it; the browser fetcher refuses redirects and URL credentials
  - #117: the vendored unlazy skill is gone and the three community plugins are pinned by commit through a repository-local marketplace
  - #118: the agent task runtime takes its execution lease before the orphan check; effect fence refusals answer 409
  - #119: the FKR query route casts `project_id` at the bind and validates it as a uuid, 422 where it was 500 on every request
  - #120: the knowledge-loop ledger rows are durable before the approval is spent, everything after the spend runs inside a failure recorder that leaves ACTION_FAILED on the intent, and the refusal of a spent approval names the intent and its terminal event
  - #121: a paused workflow run seals a sha256 of its rendered pending payload; approval refuses when the live rendering no longer matches it, decisions are accepted only for the pending step, PATCH refuses a definition change at the gate, and a rejection always closes the run
  - #122: the 21 direct Python dependencies are pinned, a dependency-audit CI job runs pip-audit (root and soul-host requirements, Python 3.12) and pnpm audit on every push, and pnpm overrides move postcss, nanoid and sharp past their advisories
  - #123: the stale records are written back (production SHA, the retired web project name, the Alembic head, the cron entrypoint, the RUNBOOK paths) and each retired sentence is pinned in `scripts/estate_reconcile.py` as a tripwire that reports DRIFT if it returns
  - #124: the FKR ingest route types `project_id` as a uuid and runs the base route's owned-project check, so an unknown or unowned project answers 404 before anything is written instead of escaping as a 500 or filing knowledge under another account's project
  - #125: provider spend is capped per tenant per UTC day at the one chokepoint every lane passes through (`PROVIDER_DAILY_TOKEN_CAP`, migration 017), refused as a typed 429 before anything reaches the provider and recorded in `provider_usage` after every call
  - #126: the Alembic build and the SQL build are the same database again (migration 018 adds the `knowledge_items.content` column the deployed database was missing and every ingest path writes), the ledger's approval row now records consumed, refused and expired, and a CI step fails on any difference between the two builds

### Changed
- **Records written back** (audit item 14): production SHA 57fdddb in FLAGSHIP, COMPLETION and GAUNTLET, dated; `meta-supreme-apex-genesis-web` replaces the retired `meta-supreme-web` in DEPLOY.md, the deploy-readback skill and the ecosystem spec; Alembic head 015 in the Hermes v2 status; the cron entrypoint reads `python dispatch.py`; RUNBOOK paths follow the modules. `scripts/estate_reconcile.py` pins each retired sentence as a tripwire (DRIFT if it comes back) and checks the standing Alembic head and cron entrypoint against the repository on every run

## [0.5.1] — 2026-08-09 — Schedule dispatch and orphan recovery

Closes the two gaps 0.5.0 shipped documented rather than fixed: scheduled
workflows now actually fire, and runs stranded by a dead process no longer sit
at `running` forever.

### Added
- **Cadence parsing** (`services/workflows/schedule.py`): `hourly:MM`, `daily:HH:MM`, `weekly:DOW:HH:MM`, all UTC. Pure and clock-free — every function takes `now` explicitly, so slot arithmetic is testable without freezing time. Deliberately not cron: the expressiveness is a large surface to get right and nothing has asked for it
- **Schedule dispatcher** (`app/services/dispatcher.py`, invoked by cron via `python dispatch.py` at the repository root; amended 2026-09-02, the module path first written here never existed in the root package). Never a thread inside the API, which would fire N times on N replicas and tie dispatch to API uptime. Safe to run concurrently: a Postgres advisory lock prevents overlap, and every run carries an idempotency key of `schedule:{slot}` against the UNIQUE index from 002, so a race is refused by the database rather than double-firing
- **Catch-up policy — fire once, then move on.** An hourly workflow whose dispatcher was down six hours fires once, not six times; `next_run_at` is recomputed from now. Firing the backlog would mean a burst of provider calls for stale slots and, with effect steps, six approval gates queued behind one another
- **Orphan sweep** (`app/services/maintenance.py`) on API startup — a restart is both the likeliest cause of a stranded run and the moment it becomes visible. Threshold `WORKFLOW_ORPHAN_TIMEOUT_MINUTES` (default 30) must exceed the longest plausible run, or healthy in-flight runs get marked failed while they continue to execute
- **Migration 003**: `workflows.next_run_at` / `last_fired_at` plus a partial index covering only active scheduled workflows, so the dispatcher's query stays an indexed range scan
- `next_run_at` and `last_fired_at` on the workflow API response and the typed client
- Test suite expanded by **35** to 148: 20 cadence tests (boundary equality, month/year/leap rollovers, an explicit UTC-not-local-time assertion, successive slots never repeating) and 15 dispatcher/sweep integration tests (double-fire, six-hour outage, open-gate skip, one broken cadence not stopping the batch, and a sweep that leaves both in-flight runs and open gates alone)

### Changed
- `awaiting_dispatcher` now reports true only for `event` triggers; `schedule` is dispatched. Corrected at the API boundary rather than in `WorkflowTrigger`, which predates the dispatcher
- `dispatchable_triggers` in the step catalog gains `schedule`
- `next_run_at` is recomputed on every workflow save, so an edited cadence takes effect immediately rather than at the next fire of the old schedule

### Known limits
- Cadences are UTC. A workflow set to 07:00 fires at 07:00 UTC year-round and does not track a user's local wall clock across DST. Asserted in a test so the choice is deliberate rather than accidental
- Event triggers still have no dispatcher
- A scheduled workflow with an unresolved approval gate skips its slots until the gate is answered — correct, but worth telling owners

## [0.5.0] — 2026-08-04 — Phase 5: Workflows (automation with a human at every effect)

The last Phase 5 pillar. A workflow is a trigger plus an ordered list of steps;
steps that only read run unattended, and steps that change state or leave the
system stop the run until the owner approves them — every run, with no way to
switch that off through the API.

### Added
- **Workflow definitions** (`services/workflows/definition.py`): trigger + ordered steps stored as JSONB, validated at save time. Templates (`{{ input }}`, `{{ step_id }}`, `{{ step_id.text }}`) may only reference the trigger input or an *earlier* step — a forward or unknown reference is rejected when the workflow is saved rather than resolving to nothing when it runs. Per-type config validation (search limits, memory importance and type, council agent lists, option ceilings) and a step ceiling (`WORKFLOW_MAX_STEPS`, default 12) that bounds a single run's provider cost
- **Workflow engine** (`services/workflows/engine.py`): pure, stateless, framework-free. Takes a definition, the results recorded so far and the approvals granted so far, then runs as far as it honestly can — stopping at `awaiting_approval`, `halted` (a rejection), or `failed` (a handler raised). Resuming is the same call with more results, so a run can sit paused for days while the engine holds no state at all. Per-step latency and token accounting; a progress event stream (`run_started → step_started/step_completed → awaiting_approval → run_completed|run_halted|run_failed`)
- **Approval gates on effects**: `memory_write`, `decision_draft` and `export` pause every run; `knowledge_search` and `council` never do. The gate carries the **rendered** payload — what would actually be written, not the template that produced it — read back from the recorded event so the preview and the write cannot diverge. Approvals are stored with actor and timestamp; a rejection halts the run and is kept with everything up to it
- **Workflow persistence**: `Workflow` and `WorkflowRun` models. A run records its ordered step results, the approvals granted, the step it is paused in front of, its token usage, its error, and a trimmed event history — the audit trail for automation, recorded as it happened rather than reconstructed after
- **Workflows API**: `GET/POST /workflows`, `GET/PATCH/DELETE /workflows/{id}`, `POST /workflows/{id}/runs`, `GET /workflows/{id}/runs`, `GET /workflows/{id}/runs/{run_id}`, `POST /workflows/{id}/runs/{run_id}/approve`, and `GET /workflows/step-types` — the step catalog the builder reads so approval semantics are never hard-coded into the UI. Ownership enforced on every route
- **Invariants at the API boundary**: a workflow with an invalid or empty definition cannot be set `active`; an archived workflow refuses to run; a second run cannot start while one is still at a gate (concurrent paused runs would make the outcome depend on the order the user clicked); a workflow with a pending gate cannot be deleted
- **Idempotent run creation**: `POST /workflows/{id}/runs` accepts an `Idempotency-Key` header and returns the original run with `200` on a repeat, backed by a unique partial index on `(workflow_id, metadata->>'idempotency_key')` — so a race that slips past the application check is refused by the database rather than producing a second run. The awaiting-gate guard could never cover this case: a read-only workflow completes without stopping, leaving a double-submit nothing to collide with. The web client holds one key across retries and clears it only on success
- **Pagination** on `GET /workflows` and `GET /workflows/{id}/runs` (`limit`/`offset`), each with an id tiebreak on the sort — `updated_at` and `started_at` are not unique, and an unstable sort silently drops and duplicates rows across page boundaries
- **Alembic adoption**: `001_baseline` adopts the shipped `database/schemas/001_initial_schema.sql` by executing it, so the baseline and the file the tests apply cannot drift; `002_workflow_runs` adds the run table, the `workflows.metadata` column, and the indexes both need. Existing databases: `alembic stamp 001_baseline && alembic upgrade head`
- **Workflows UI** (`/workflows`): the automation list with per-workflow gate state, the step list with approval badges sourced from the API catalog, run-now with trigger input (shown only when the definition consumes one), the approval gate with the rendered payload and approve/reject, and run history where halted runs are kept with their reason. Two runnable starter templates for the empty state
- Test suite expanded by **49** to 113: 23 definition/engine unit tests (forward references, config bounds, gate previews, resume without re-running completed steps, rejection halting, handler failure, token accounting) and 26 API integration cases (the full approve and reject paths end to end, including proof that no memory row exists before approval and exactly one exists after; idempotent replay; page boundaries that neither drop nor repeat a row)

### Changed
- **Alembic is now the schema source of truth.** `database/schemas/001_initial_schema.sql` is frozen; further changes ship as migrations, with a re-runnable SQL twin only where the test fixture needs one
- `WORKFLOW_APPROVAL_REQUIRED`, `WORKFLOW_MAX_STEPS` and `WORKFLOW_RUN_HISTORY_LIMIT` added to settings. The first is deliberately absent from `.env.example`, the API and the UI — it exists so the engine can be tested without stubbing approvals, and as the switch a future per-workflow trusted-automation mode would flip
- Dashboard navigation gains Workflows

### Fixed
- `workflows` had no `metadata` column despite the model mapping one — inserting a `Workflow` raised `UndefinedColumn`. Added in `002_workflow_runs`
- `workflows` shipped with no indexes; owner and project lookups were sequential scans

### Known limits (documented, not hidden)
- Schedule and event triggers are stored and validated but nothing dispatches them. Both the API (`awaiting_dispatcher`, `dispatchable_triggers`) and the UI say so plainly; runs are started by a human until the scheduler lands
- `export` renders into the run record; no outbound channel (email, webhook) is wired, and the step result says `delivered: false` rather than implying otherwise
- A run executes inside the request that started it. Long council steps hold the connection — the same constraint the SSE endpoint carries, and the same fix (background jobs)

## [0.4.0] — 2026-07-28 — Phase 4: Council System (live deliberation)

### Added
- **SSE streaming**: `POST /conversations/{id}/messages/stream` emits the Council's live progress as Server-Sent Events (`run_started → context → intent → agents_selected → agent_started/agent_completed per round → synthesis_started → complete`), with full persistence committed before the `complete` event and terminal `error` events on failure
- **Deliberation rounds**: opt-in second round (`deliberate: true` per request, or `COUNCIL_DELIBERATION_ROUNDS=2` globally) where every agent sees its peers' round-1 contributions and revises — disagreements are named, not smoothed; a failed revision falls back to that agent's round-1 result so good contributions are never lost; token accounting covers both rounds
- **Model tiers**: `AI_MODEL_FAST` for intent classification and `AI_MODEL_SYNTHESIS` for the synthesis stage (None → provider default); agents keep the default tier
- **Progress events in the controller**: `ExecutiveController.run(context, on_event=…)` — the services layer emits, the app layer streams
- **Live Command Center**: the Council panel is driven by the event stream (per-agent Deliberating/Contributed/Failed, round indicator, stage line), a Deliberate toggle beside Full Council, a deliberation-rounds chip on responses, and graceful fallback to the non-streaming endpoint
- Test suite expanded to 64: event ordering, two-round deliberation with peer-context verification, round-2 failure fallback, model-tier routing, concurrency cap, SSE endpoint integration (event sequence + persistence + error events)

### Changed
- **Parallel execution is now the default** (`COUNCIL_PARALLEL_EXECUTION=true`) with a rate-limit-friendly concurrency cap (`COUNCIL_MAX_CONCURRENCY`, default 3)
- Executor repair attempts now carry deliberation-round context
- `agent_runs.input_payload` records the round that produced each contribution

## [0.3.0] — 2026-07-28 — MVP: Knowledge System + Memory + Decisions

All MVP acceptance criteria from the original blueprint are now met.

### Added
- **Embedding provider abstraction** (`services/intelligence/providers/embeddings.py`): `EmbeddingProvider` interface with retries and typed errors; OpenAI implementation (`text-embedding-3-small`, 1536-dim) and a deterministic offline `MockEmbeddingProvider` whose hashed bag-of-words vectors make retrieval behave lexically with zero keys (clearly labeled simulated)
- **Knowledge pipeline**: paragraph-aware chunking with overlap (`services/knowledge/chunking.py`); ingestion service (persist → chunk → embed → pgvector index, explicit `failed` status on embedding errors); cosine-distance semantic search scoped to the owner
- **Knowledge API**: `GET/POST /knowledge`, `POST /knowledge/search`, `GET/DELETE /knowledge/{id}` — ownership enforced everywhere
- **Retrieval wired into the Council**: every message run retrieves top-k knowledge into agent context; assistant messages carry `knowledge_sources` (title, chunk, distance) so responses cite their sources transparently
- **Memory engine** (Phase 5 slice): Council memory candidates persist as real memories after each exchange; lexical recall (keyword overlap × importance × recency) feeds `retrieved_memories` on future requests; `memories_recalled` reported per response. Full CRUD API — transparent, editable, pausable, hard-deletable
- **Decision tracking**: decisions CRUD; `POST /decisions/from-message` turns a Council exchange into a tracked decision (synthesis → recommendation, recommended actions → options); recording `chosen_option` is a human action that advances status to `decided`; outcome review supported
- **Frontend**: Knowledge Vault page (add/upload .txt/.md, semantic search, delete); Decisions page (recommendation vs. the human's recorded call, outcome review); Memory management in Settings (edit, pause, delete, teach-the-system); Command Center shows cited sources, memory-recall chip, and "Track as decision"
- Test suite expanded to 56 tests covering chunking, embeddings, knowledge API + Council citation, memory persistence/recall/CRUD, and decision lifecycle

### Changed
- `ContextPacket.retrieved_knowledge` / `retrieved_memories` now receive real data (previously always empty)
- Dashboard navigation gains Decisions; phase badge reads "MVP · Intelligence OS"

## [0.2.0] — 2026-07-28 — Phase 2: Intelligence Core

### Added
- **AI provider abstraction** (`services/intelligence/providers/`): model-agnostic `AIProvider` interface with token accounting, deterministic retry/backoff, and typed error taxonomy; implementations for Anthropic (Messages API), OpenAI (Chat Completions), and a deterministic offline `MockProvider` (zero keys, clearly labeled simulated output); config-driven factory
- **Agent execution framework** (`services/agents/executor.py`): registry definitions become executable agents — council ground rules, declared `output_format` enforced as a JSON contract, one corrective repair attempt, explicit failure (agents never fabricate)
- **Synthesizer** (`services/intelligence/synthesizer.py`): combines contributions under the fixed priority order (accuracy → strategic value → execution → risk → user objectives), surfaces points of agreement/tension, falls back to verbatim contribution assembly (flagged) if model synthesis fails
- **Executive Controller wired for real** — provider-backed intent analysis with heuristic fallback (source always reported), intent→agent routing, sequential execution (parallel opt-in via `COUNCIL_PARALLEL_EXECUTION`), full-council and explicit-agent overrides, memory-update candidates emitted transparently
- **Conversations + Messages persistence**: SQLAlchemy models (Conversation, Message, Agent, AgentRun), agents table seeded idempotently from the registry at startup, every council exchange recorded with one `agent_runs` row per contribution (input/output payloads, token usage, latency)
- **Conversations API**: create/list/get/rename/archive, `POST /conversations/{id}/messages` runs the full council flow and returns the synthesis with every agent's contribution, `GET /conversations/{id}/runs` exposes the audit trail
- **Intelligence API**: `POST /intelligence/ask` (one-shot, nothing persisted) and `GET /intelligence/status` (provider, model, simulated flag)
- **Frontend auth**: AuthProvider context, login/register wired to the real API, protected dashboard routes, user menu with sign-out
- **Command Center live**: real council conversations — synthesized responses with recommended actions, points of tension, intent/confidence/provider chips, expandable per-agent contributions, live agent status panel, provider status card with explicit simulated-mode notice
- Test suite expanded to 39 tests: provider unit tests (HTTP shaping via mock transports, retry semantics), executor/controller behavior, and full API integration tests against Postgres
- `ruff.toml` lint configuration; repo-wide encoding repair (stray control bytes from the Phase 1 archive)

### Changed
- `/api/v1/agents` now serves the canonical registry directly (Phase 1 static mirror removed)
- `DEFAULT_AI_PROVIDER` defaults to `mock` so the platform runs end-to-end with zero API keys
- Docker build context moved to the repo root so the API image includes `services/`
- `passlib` replaced with direct `bcrypt` (passlib is unmaintained and incompatible with bcrypt ≥ 4.1); hashes remain compatible

### Fixed
- `email-validator` missing from API requirements
- Corrupted multibyte characters (em-dashes, arrows, bullets) across repo files

## [0.1.0] — Phase 1: Foundation

### Added
- Handover package for Claude / continuing engineers (`docs/HANDOVER_FOR_CLAUDE.md` + `docs/CLAUDE_PROJECT_BRIEF.md`)
- Full AI Council agent registry (all 9 agents: Oracle, Analyst, Strategist, Architect, Engineer, Guardian, Creator, Librarian, Skeptic) with identity, mission, system instructions, capabilities, limitations, output format, and evaluation criteria
- Executive Controller skeleton with intent analysis, agent selection, and synthesis contract
- SQLAlchemy async models for User, Organization, OrganizationMember, Project
- Database session factory and dependency injection
- Complete authentication system: registration, login (JWT), current user endpoint
- Password hashing (bcrypt) and JWT utilities
- Security dependencies for protected routes
- Global exception handlers with consistent JSON error shape
- Projects API (list / create / get / update) with ownership checks
- Docker Compose stack (PostgreSQL + pgvector, API, Web)
- Design system tokens (Deep Navy, Amber Gold, Warm Off-White) in Tailwind
- Frontend shell: Landing, Login, Register, Dashboard layout, Overview, Command Center, Knowledge Vault, Settings
- Reusable Button + Card components
- Frontend API client utility (`lib/api.ts`)
- Shared packages scaffolding (`@meta-supreme/ui`, `@meta-supreme/types`, `@meta-supreme/shared`)
- Makefile with common developer commands
- Basic unit/integration tests (health, password hashing, JWT)
- Health and readiness endpoints
- Initial schema with all core tables (users, orgs, projects, conversations, messages, agents, agent_runs, knowledge_items, embeddings, memories, decisions, workflows, feedback, audit_logs)

### Changed
- Phase 1 foundation marked **ready** for iterative feature build

### Security
- Secrets loaded exclusively from environment variables
- JWT-based authentication with configurable expiry
- Password hashing with bcrypt
- CORS restricted to development origins by default
- Consistent error responses that avoid leaking internals

---

## [0.1.0] - 2026-07-27

### Added
- Project inception and master blueprint implementation start
- Repository scaffolding for the Intelligence Operating System
- Monorepo structure (`apps/`, `services/`, `packages/`, `database/`, `docs/`, `infrastructure/`)
- Core documentation: README, ARCHITECTURE, CONTRIBUTING, CHANGELOG, LICENSE

---

## Versioning Notes

- **Major**: Breaking changes to public APIs or core architecture
- **Minor**: New features (agents, knowledge capabilities, product modules) in a backward-compatible manner
- **Patch**: Bug fixes, documentation, performance, and security patches
