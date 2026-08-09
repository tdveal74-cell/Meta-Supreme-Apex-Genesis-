# Audit package — Meta Supreme Apex Genesis, Workflows (Phase 5 / 5.1)

For an external reviewer. Read this before the code.

**Date:** 2026-08-09 · **Scope:** the Workflows feature and the platform
guarantees it rests on · **Status:** unverified by the authoring environment —
see §6.

---

## 1. The claim being audited

> Automation in this platform reads, reasons and drafts on its own. It never
> commits an effect — writing memory, opening a decision, preparing an export —
> without a human explicitly approving that specific action, on every run.

Everything below exists to let you test that sentence and try to break it.

The claim is narrow on purpose. It is not "the AI is safe" or "the AI is
correct." It is a statement about *control*: which operations can happen
without a person, and which cannot.

---

## 2. Where the claim is enforced

Four places, in dependency order. A defect in any one of them breaks the claim.

| # | Layer | File | What it must guarantee |
|---|---|---|---|
| 1 | Classification | `services/workflows/definition.py` | `EFFECT_STEP_TYPES` is the *only* place a step is declared an effect. Nothing else decides. |
| 2 | Execution | `services/workflows/engine.py` | An effect step with no approval decision returns `awaiting_approval` and executes nothing further. Pure, stateless, no database. |
| 3 | Persistence | `apps/api/app/services/workflows.py` | The approval and the effect commit in the same transaction. An approval records actor and timestamp. |
| 4 | Transport | `apps/api/app/api/v1/workflows.py` | Ownership on every route; the approve endpoint refuses decisions for steps the run is not waiting on. |

**The highest-value thing to attack is layer 2**, because it is where the rule
actually lives, and because it is pure — you can drive it directly with no
database, no HTTP, and no AI provider.

---

## 3. Attempt these specifically

Ordered by what would be most damaging if it worked.

1. **Execute an effect with no approval.** Construct a definition where an
   effect step's approval could be inferred, defaulted, or skipped. Resume a
   run with a forged `prior_results` claiming the effect already ran.
2. **Approve a different step than the one shown.** The gate preview is read
   back from the recorded event; make the preview and the eventual write
   diverge.
3. **Escalate across tenants.** Every workflow route is scoped by `owner_id`.
   Find one that is not. Try a run id belonging to another owner against your
   own workflow id, and vice versa.
4. **Template injection.** `{{ }}` references may only look backwards. Try a
   forward reference, a self-reference, a cycle, `{{ input.__class__ }}`, or a
   reference that resolves to something outside the run.
5. **Approval replay.** Re-POST an approval for a completed run. Approve a run
   twice concurrently. Approve while a dispatcher fires the same workflow.
6. **Double-fire the scheduler.** Run two dispatchers against one database and
   make the same slot produce two runs. (The defence is a UNIQUE partial index,
   not application logic — see `002_workflow_runs.py`.)
7. **Denial of service by definition.** `WORKFLOW_MAX_STEPS` bounds one run's
   cost. Nothing bounds how often a workflow may be run manually.

---

## 4. Known gaps — declared, not discovered

Stated up front so your time goes to what we do not already know.

| Gap | Consequence | Status |
|---|---|---|
| Runs execute inside the HTTP request | A long provider call holds a connection; process death strands the run | Swept on API startup (5.1); background execution not built |
| No event-trigger dispatch | `event` triggers store but never fire | Reported as `awaiting_dispatcher` in API and UI |
| `export` has no outbound channel | Renders into the run record only; reports `delivered: false` | Deliberate — no outbound integration, and inbound webhooks have no auth story |
| No rate limiting | A user may start manual runs without bound | Metering data captured (`token_usage`), nothing enforces |
| JWT in `localStorage` | XSS yields a token | Known; httpOnly cookie migration planned |
| Cadences are UTC only | A schedule does not follow local time across DST | Deliberate; asserted in `test_schedule.py` |
| Memory recall is lexical | Not embedding-based; recall quality is weaker than retrieval | Planned |
| No per-tenant resource isolation | One tenant's provider spend affects shared rate limits | Not addressed |

`WORKFLOW_APPROVAL_REQUIRED` deserves its own note. It exists so the engine can
be tested without stubbing approvals, and is deliberately absent from the API,
the UI, and `.env.example`. **If you find any path that sets it false at
runtime, that is a finding.**

---

## 5. What is out of scope

- The AI providers themselves (Anthropic, OpenAI) and the quality of model output.
- Phase 1–4 surfaces except where Workflows depends on them (auth, ownership, the council executor).
- Infrastructure hardening — TLS, secrets management, network policy — none of which ships in this repo.
- The frontend beyond the Workflows screen.

---

## 6. Verification status — read this before trusting any test count

**Partially executed, as of 2026-08-09.**

| | Status |
|---|---|
| Engine + cadence suites (no database) | **49 passed** — `VERIFICATION_REPORT_OFFLINE.md` |
| API integration, dispatcher, orphan sweep | Not run — needs PostgreSQL |
| Migrations, lint, typecheck, frontend build | Not run |

The passing subset is the one that bears most directly on §1:
`test_workflow_engine.py` is the approval rule as executable specification, and
it is pure precisely so it can be run anywhere. **The rule holds in isolation.**

That is not the same as the system holding. Layers 3 and 4 of §2 — where the
approval and the effect must commit in one transaction, and where ownership is
enforced on every route — are exactly the parts still unexecuted. An attack on
the claim is most likely to succeed there, not in the engine.

A static pass resolved every imported symbol against real source and fixed
three import-level defects. That is not a substitute for running the suite.

**On counts.** Figures in `CHANGELOG.md` were derived by counting test
functions before anything ran; pytest expands parametrised cases, so collected
totals run higher — the offline subset was estimated at 43 and collected 49.
Treat no count in this repository as measured unless a report generated by an
actual run says so.

Reproduce independently. Full run, Docker and nothing else:

```bash
docker compose -f docker-compose.verify.yml up --abort-on-container-exit
```

Offline subset, Python and nothing else:

```bash
bash scripts/verify-offline.sh
```

Each writes its own report: what ran, what passed, pinned versions. Postgres is
`tmpfs`-backed, so every full run starts from an empty database and a pass
cannot depend on leftover state. Provider mode is `mock` — deterministic,
offline, no external calls, no API keys.

**Do not accept a passing report that you did not generate yourself.**

---

## 7. Reading order

1. `docs/AUDIT.md` — this file
2. `services/workflows/definition.py` — what a workflow may be, and why
3. `services/workflows/engine.py` — the rule, in ~350 lines
4. `apps/api/tests/test_workflow_engine.py` — the rule as executable spec
5. `apps/api/app/services/workflows.py` — where effects meet the database
6. `apps/api/app/api/v1/workflows.py` — the HTTP surface and its invariants
7. `docs/RUNBOOK.md` — how it is operated, and what operators are told never to do

The tests are the specification. Where a test and this document disagree, the
test is what the system does — and the disagreement is itself a finding.

---

## 8. Reporting

Include the run id or workflow id, the exact request, and the observed versus
expected behaviour. For anything touching §3.1 or the `WORKFLOW_APPROVAL_REQUIRED`
note in §4, treat it as critical: those break the product's central claim, and
we would rather stop a release than ship past them.
