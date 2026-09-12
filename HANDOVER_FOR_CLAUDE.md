# Handover Package — Meta Supreme Apex Genesis

**For Claude (or any continuing AI / engineer)**
**Date:** 2026-08-04
**Status:** Phases 1–5 complete (MVP + live Council System + Workflows). Remaining: SaaS layer (Phase 6), Enterprise layer (Phase 7).
**Repository root:** `meta-supreme-apex-genesis/`

This document is the single source of truth for continuing development. Read it fully before writing code.

---

## 1. What This Project Is

**Meta Supreme Apex Genesis** is **not a chatbot**.

It is a **scalable SaaS Intelligence Operating System** that amplifies human decision-making through:

- Multi-agent AI reasoning (AI Council)
- Knowledge management + semantic retrieval
- Long-term memory (transparent, editable, permissioned)
- Decision intelligence
- Workflow automation
- Enterprise governance

**Core philosophy**

| Humans provide          | AI provides              |
|-------------------------|--------------------------|
| Judgment                | Analysis                 |
| Values                  | Patterns                 |
| Responsibility          | Recommendations           |
| Final decisions         | Execution support        |

**Design principles (non-negotiable)**

- Secure by design
- Transparent by default
- Modular by architecture
- Simple by experience (Apple-level calm UI)
- Powerful beneath the surface

**Design system**

- Primary: Deep Navy `#0A1628`
- Accent: Amber Gold `#D4A017`
- Surface: Warm Off-White (`#F8F5F0` and related)

---

## 2. Current Status

| Phase | Focus                              | Status      |
|-------|------------------------------------|-------------|
| 1     | Foundation (Repo, Shell, Auth, DB) | Complete |
| 2     | Intelligence Core                  | Complete |
| 3     | Knowledge System                   | Complete |
| 4     | Council System (live multi-agent)  | Complete |
| 5     | Product Layer (Projects, Decisions, Memory, Workflows) | **Complete** |
| 6     | SaaS Layer (Billing, Plans)        | Pending — next |
| 7     | Enterprise Layer (Teams, Permissions, Compliance) | Pending |

**MVP acceptance criteria — all met:**

- [x] User registration works
- [x] Users can create projects
- [x] Users can upload knowledge (text/markdown ingestion → chunk → embed → pgvector)
- [x] Users can ask questions
- [x] Council activates
- [x] Agents collaborate
- [x] Responses are synthesized
- [x] Memory improves future interactions (persisted from exchanges, recalled into context, fully user-controlled)
- [x] Decisions can be tracked (from Council exchanges or manually; human records the final call)
- [x] Workflows automate the loop without ever acting unattended on an effect
- [x] System deploys reliably (Docker Compose)

**Verification state:**

- **2026-07-28 (Phase 4):** 64 backend tests green (`make test`), ruff clean, frontend `tsc --noEmit` and production build green, browser end-to-end verified twice.
- **2026-08-09 (Phase 5.1):** schedule dispatch and orphan recovery added, also **unexecuted**. Expect 148 tests.
- **2026-08-04 (Phase 5):** the Workflows slice was authored against this repository's source but **has not been executed** — no Python, Node or Postgres ran in the environment that produced it. Confirm with `make test` before treating Phase 5 as verified. See `phase5-workflows/README.md` for what is settled and what is still worth watching.

---

## 3. Technology Stack

| Layer        | Choice                                      |
|--------------|---------------------------------------------|
| Frontend     | Next.js 15, React 19, TypeScript, Tailwind, shadcn-style components, Framer Motion |
| Backend      | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| Database     | PostgreSQL 16 + pgvector, **Alembic migrations** |
| Auth         | Custom JWT + bcrypt (Supabase-compatible architecture planned) |
| AI Providers | Model-agnostic abstraction: Anthropic / OpenAI / offline Mock (httpx direct, no vendor SDKs) |
| Infrastructure | Docker Compose, GitHub Actions skeleton   |
| Monorepo     | pnpm workspaces                             |

---

## 4. Repository Map (Phase 5 additions marked ★)

```
meta-supreme-apex-genesis/
├── apps/
│   ├── api/                  # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/       # auth, projects, agents, health, conversations,
│   │   │   │                 # intelligence, knowledge, memory, decisions,
│   │   │   │                 # ★ workflows
│   │   │   ├── core/         # config (★ workflow settings), logging, exceptions
│   │   │   ├── db/           # async session + Base
│   │   │   ├── models/       # user, organization, project, conversation,
│   │   │   │                 # agent, knowledge, memory, decision,
│   │   │   │                 # ★ workflow (+WorkflowRun)
│   │   │   ├── security/     # password, JWT, deps
│   │   │   ├── services/     # intelligence, knowledge, memory,
│   │   │   │                 # ★ workflows.py (handlers + run persistence)
│   │   │   └── main.py
│   │   ├── tests/            # ★ test_workflow_engine, ★ test_workflows_api
│   │   └── requirements.txt
│   └── web/                  # Next.js frontend
│       ├── app/
│       │   ├── (auth)/
│       │   ├── (dashboard)/  # command-center, knowledge, decisions,
│       │   │                 # ★ workflows, settings
│       │   └── …
│       ├── components/
│       └── lib/              # api.ts (★ workflowsApi), auth-context.tsx
├── services/                 # framework-free intelligence layer
│   ├── agents/               # registry (source of truth), executor
│   ├── intelligence/         # providers/, synthesizer, executive_controller
│   ├── knowledge/            # chunking
│   ├── memory/
│   └── ★ workflows/          # definition.py (parse/validate), engine.py (execute)
├── database/
│   ├── ★ migrations/         # Alembic — now the schema source of truth
│   │   └── versions/         # 001_baseline, ★ 002_workflow_runs
│   └── schemas/              # 001_initial_schema.sql (FROZEN), ★ 002_workflow_runs.sql
├── infrastructure/docker/
├── alembic.ini · ruff.toml
├── ARCHITECTURE.md · CONTRIBUTING.md · CHANGELOG.md · Makefile · README.md
└── docs/HANDOVER_FOR_CLAUDE.md   # this file
```

---

## 5. What Is Already Implemented

### Intelligence Core (Phase 2)

**AI provider abstraction** — `services/intelligence/providers/`
- `AIProvider` interface: `complete(CompletionRequest) → CompletionResponse` with token usage, latency, finish reason
- Implementations: `AnthropicProvider` (Messages API), `OpenAIProvider` (Chat Completions), `MockProvider` (deterministic, offline, zero keys — output clearly labeled simulated)
- Deterministic retry/backoff on rate-limit/timeout/5xx; typed error taxonomy
- Config-driven via `create_provider()`; the app passes settings in (dependency direction app → services, never the reverse)

**Agent execution** — `services/agents/executor.py`
- Builds each agent's prompt from its registry definition + council ground rules + output contract
- Enforces the declared `output_format` as JSON; one corrective repair attempt; explicit failure otherwise — **agents never fabricate**

**Synthesis** — `services/intelligence/synthesizer.py`
- Fixed priority order: accuracy → strategic value → practical execution → risk awareness → user objectives
- Surfaces `points_of_agreement` and `points_of_tension` — disagreements are never averaged away
- Deterministic fallback (flagged `synthesis_mode="fallback"`) if model synthesis fails

**Executive Controller** — fully wired
- Intent analysis with heuristic fallback; `intent_source` always reported
- Routing per intent; `full_council` and `requested_agents` overrides
- Parallel by default (`COUNCIL_PARALLEL_EXECUTION`, capped by `COUNCIL_MAX_CONCURRENCY`)
- Raises `CouncilExecutionError` only if **no** agent contributes; partial failures synthesize transparently

### Knowledge System (Phase 3)

- Embedding providers: OpenAI (`text-embedding-3-small`, 1536-dim) and a deterministic offline mock
- Paragraph-aware chunking with overlap → pgvector → cosine-distance search scoped to the owner
- Every council run retrieves top-k chunks; assistant messages carry `knowledge_sources` — responses cite their sources
- Ingestion failures mark items `failed` with the error in metadata — never silent

### Council System (Phase 4)

- **SSE streaming** — `POST /conversations/{id}/messages/stream`, full event sequence, persistence committed before `complete`
- **Deliberation rounds** — agents see peers' round-1 contributions and revise; failed revisions fall back to round 1; both rounds token-accounted
- **Model tiers** — `AI_MODEL_FAST` (intent), `AI_MODEL_SYNTHESIS` (synthesis)
- **Live UI** — event-driven Command Center council panel

### Memory + Decisions (Phase 5)

- Council memory candidates persist as real `memories` rows; lexical recall (keyword overlap × importance × recency) feeds later requests
- Fully user-controlled: list, edit, pause, hard delete, and user-authored memories
- Decisions CRUD plus `POST /decisions/from-message`; the human records `chosen_option`. The Council never decides.

### Workflows (Phase 5 — new) ★

**The rule the whole feature is built on:** steps that only read run unattended;
steps that change state or leave the system stop the run until the owner
approves them, every run. `WORKFLOW_APPROVAL_REQUIRED` is not exposed through
the API, the UI, or `.env.example` — it exists so the engine can be tested
without stubbing approvals, and as the switch a future *per-workflow*
trusted-automation mode would flip. Do not surface it globally.

**Definitions** — `services/workflows/definition.py`
- Trigger + ordered steps as JSONB. Step types: `knowledge_search`, `council` (reads) and `memory_write`, `decision_draft`, `export` (effects, in `EFFECT_STEP_TYPES`)
- Templates `{{ input }}`, `{{ step_id }}`, `{{ step_id.text }}` may only reference the trigger input or an **earlier** step — a forward or unknown reference is rejected at save time rather than rendering as nothing at run time
- Per-type config validation and a step ceiling (`WORKFLOW_MAX_STEPS`, default 12)

**Engine** — `services/workflows/engine.py`
- Pure and stateless. Takes a definition, the results recorded so far, and the approvals granted so far; runs as far as it honestly can and returns `completed`, `awaiting_approval`, `halted`, or `failed`
- Resuming is the same call with more results — a run can sit paused for days while the engine holds nothing
- Emits progress events; the `awaiting_approval` event carries the **rendered** config, which is what the API reads back for the gate preview. The preview and the write cannot diverge, because they are the same object

**App layer** — `apps/api/app/services/workflows.py`
- Handlers bind each step type to a real operation: a Council run, a pgvector search, a `memories` row, a `decisions` row, a rendered export
- Every advance persists; approvals are stored with actor and timestamp
- Token usage accumulates on `workflow_runs.token_usage`, joining `agent_runs.token_usage` as the metering foundation for Phase 6

**Invariants enforced at the API boundary**
- A workflow with an invalid or empty definition cannot be set `active`
- An archived workflow refuses to run
- Only one run may sit at a gate per workflow — concurrent paused runs would make the outcome depend on the order the user clicked, since effect steps interpolate earlier results
- A workflow with a pending gate cannot be deleted
- `POST /runs` is idempotent under an `Idempotency-Key` header, enforced by a unique partial index rather than by the application check alone. This is the one guard the awaiting-gate rule cannot provide: a read-only workflow completes without stopping, so a double-submit has nothing to collide with
- List endpoints paginate with an id tiebreak on the sort; `updated_at`/`started_at` are not unique and an unstable sort loses rows across pages
- `GET /workflows/step-types` is the single source of approval semantics for the UI

**Frontend** — `/workflows`: automation list with gate state, step list with approval badges from the API catalog, run-now with trigger input (shown only when the definition consumes one), the approval gate with the rendered payload, and run history where halted runs are kept with their reason.

### API surface

| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Projects | `GET/POST /projects`, `GET/PATCH /projects/{id}` |
| Agents | `GET /agents`, `GET /agents/{slug}` |
| Conversations | `GET/POST /conversations`, `GET/PATCH /conversations/{id}`, `POST /conversations/{id}/messages`, `POST /conversations/{id}/messages/stream`, `GET /conversations/{id}/runs` |
| Intelligence | `POST /intelligence/ask`, `GET /intelligence/status` |
| Knowledge | `GET/POST /knowledge`, `POST /knowledge/search`, `GET/DELETE /knowledge/{id}` |
| Memory | `GET/POST /memory`, `PATCH/DELETE /memory/{id}` |
| Decisions | `GET/POST /decisions`, `POST /decisions/from-message`, `GET/PATCH /decisions/{id}` |
| Workflows ★ | `GET /workflows/step-types`, `GET/POST /workflows`, `GET/PATCH/DELETE /workflows/{id}`, `POST /workflows/{id}/runs`, `GET /workflows/{id}/runs`, `GET /workflows/{id}/runs/{run_id}`, `POST /workflows/{id}/runs/{run_id}/approve` |
| Health | `GET /health`, `GET /health/ready` |

### Persistence
- `agents` seeded idempotently from the registry at startup
- Every council exchange stores: user message → one `agent_runs` row per contribution → assistant message with full synthesis metadata
- Every workflow run stores its ordered step results, approvals (with actor and time), pending step, token usage, error, and a trimmed event history

---

## 6. How to Run Locally

```bash
cd meta-supreme-apex-genesis
make install          # pnpm + Python venv + requirements
alembic upgrade head  # schema (see below if the database already exists)
make up               # Docker Compose: Postgres + API + Web
```

- Frontend: http://localhost:3000
- API docs:  http://localhost:8000/api/docs
- Health:    http://localhost:8000/api/v1/health

**Migrations.** Alembic is the schema source of truth as of 0.5.0.
`database/schemas/001_initial_schema.sql` is frozen; `001_baseline` executes it
so the two cannot drift, and everything after is a hand-written revision.

```bash
alembic upgrade head                                  # fresh database
alembic stamp 001_baseline && alembic upgrade head    # database that predates Alembic
alembic revision -m "…" --autogenerate                # new change
```

Environment: copy `apps/api/.env.example` → `apps/api/.env`. Everything works with zero AI keys (mock mode).

Note for local (non-Docker) runs: the API needs the repo root on `PYTHONPATH` so `services.*` imports resolve — `make api` and `pytest.ini` already handle this.

---

## 7. Coding Standards & Conventions

Follow `CONTRIBUTING.md` strictly. Highlights:

**Backend** — type hints everywhere; Pydantic models for every request/response; SQLAlchemy 2.0 style; structured logging; never hard-code secrets; meaningful HTTP status codes. Lint: `ruff check .`.

**Services layer** — standard library + httpx only; **never imports `app.*`** (dependency direction is app → services). Framework-free and independently testable. `services/workflows` is the reference example: the engine has no idea Postgres exists.

**Frontend** — strict TypeScript; design tokens only (navy/amber/surface/border — never invent colors); accessible by default.

**Agents** — single source of truth is `services/agents/registry.py`; output must match declared `output_format`; never invent facts or silently fail.

**Database** — UUID PKs, timestamps, ownership columns. **Schema changes ship as Alembic revisions.** If a change needs a SQL twin for the test fixture, write it re-runnable (`IF NOT EXISTS`) and say in the file which one wins.

**Automation** — a new step type that touches anything outside the Council goes in `EFFECT_STEP_TYPES`. That is the only place the decision is made; the API catalog and the UI both read it.

---

## 8. Immediate Next Priorities

1. **Verify Phase 5** — `make test`, `ruff check .`, `tsc --noEmit`, `pnpm build`, then the browser loop: create from a template → run → approve → confirm the memory row → run again → reject → confirm the halt is kept
2. **Event trigger dispatch**: an internal event bus for `event` triggers (knowledge ingested, decision recorded), reusing the dispatcher's idempotency-key pattern. Schedule dispatch landed in 5.1; install the cron entry (`python dispatch.py` at the repository root, which the API image ships at /app; amended 2026-09-02, the module path first written here never existed in the root package; see the runbook §6) or scheduled workflows still will not fire
3. **Background execution** — runs currently execute inside the request that started them, as SSE council runs do. One background-job story fixes both
4. **The workflow builder** — the canvas: add/remove/reorder steps, per-step config, gate preview. `GET /workflows/step-types` exists to feed it
5. **Embedding-based memory recall** — add a vector column to `memories` via migration; replace the lexical scorer
6. **PDF/DOCX ingestion** — extend knowledge ingestion beyond text/markdown
7. **httpOnly cookie auth** — retire localStorage tokens alongside the Supabase-compatible auth work
8. **Rate limiting + usage metering** — `agent_runs.token_usage` and `workflow_runs.token_usage` are both populated; the aggregate endpoint does not exist yet (the Workflows screen deliberately shows per-run tokens rather than inventing a total)
9. **Phase 6 (SaaS)** — plans, billing, usage limits once metering exists

---

## 9. Important Constraints & Non-Negotiables

- **Do not turn this into a chatbot.** Keep the multi-agent council + synthesis model.
- Humans remain the final decision makers. Agents recommend; they do not decide.
- **Automation never commits an effect unattended.** Reads flow; writes wait. Do not add a global switch that turns approval off.
- Memory must stay transparent, editable, and deletable by the user.
- Never hard-code secrets or API keys.
- Keep the calm, premium aesthetic (Deep Navy + Amber Gold).
- Simulated output must always be labeled as simulated.
- Every new table/feature must respect ownership and multi-tenancy from day one.

---

## 10. Known Gaps / Technical Debt (intentional)

- **Phase 5 and 5.1 are unverified in the environment that wrote them** — see §2
- No event-trigger dispatch: `event` triggers validate and store, but nothing fires them. Reported as `awaiting_dispatcher` in the API and in words in the UI. Schedule triggers fire from cron as of 5.1
- Cadences are UTC — a scheduled workflow does not track a user's local wall clock across DST
- `export` renders into the run record and reports `delivered: false` — no email or webhook channel exists. Inbound webhooks additionally need an auth story
- Workflow runs execute inside the request that started them; long council steps hold the connection. Runs stranded by a process death are swept on the next API startup (5.1)
- The Workflows screen reads, runs and resolves gates; step editing is still definition-level rather than a canvas
- No aggregate usage endpoint, so no cross-workflow token total in the UI
- Memory recall is lexical, not embedding-based — needs a `memories` vector column
- Knowledge ingestion covers text/markdown/manual/url; PDF/DOCX not implemented
- JWT lives in localStorage on the frontend
- SSE runs hold a DB session for the duration of the council run
- No rate limiting; usage data is captured but not enforced against anything
- Packages (`@meta-supreme/*`) remain scaffolds
- Historic messages reload without per-agent contribution detail in the UI (data exists via `GET /conversations/{id}/runs`)

---

## 11. Key Files to Read First

| Priority | File |
|----------|------|
| 1 | `docs/HANDOVER_FOR_CLAUDE.md` (this file) |
| 2 | `ARCHITECTURE.md` |
| 3 | `services/agents/registry.py` — the 9 agents |
| 4 | `services/intelligence/executive_controller.py` — the wired core |
| 5 | `services/workflows/definition.py` — what a workflow may be, and why |
| 6 | `services/workflows/engine.py` — the approval gate, in ~350 lines |
| 7 | `apps/api/app/services/workflows.py` — handlers + run persistence |
| 8 | `apps/api/app/api/v1/workflows.py` — the HTTP surface and its invariants |
| 9 | `apps/web/app/(dashboard)/command-center/page.tsx` — the live Council UI |
| 10 | `apps/api/tests/` — behavior specification in test form |

---

## 12. Voice & Product Tone

- Clear, calm, precise. No hype.
- Honest about uncertainty; simulated output is labeled simulated.
- Actionable when possible. Never claim capabilities the system does not have.

---

## 13. Handover Checklist for Continuing Work

- [ ] `alembic upgrade head` (or `stamp` then `upgrade` on an existing database)
- [ ] `make up` → frontend + API docs reachable
- [ ] `make test` → 148 tests green
- [ ] `ruff check .` clean; `tsc --noEmit` and `pnpm build` green
- [ ] Browser: template → run → approve → memory row exists; run → reject → halt is kept
- [ ] Read the workflow definition + engine pair before changing anything about approval
- [ ] Decide the next slice (recommended: trigger dispatch, then background execution)
- [ ] Keep this handover document updated as major milestones land

---

**Meta Supreme Apex Genesis**
*The intelligence operating system.*
