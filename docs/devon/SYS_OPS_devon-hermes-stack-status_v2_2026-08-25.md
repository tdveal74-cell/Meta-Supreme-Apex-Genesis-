---
title: DEVON Hermes Stack Status
type: SYS_OPS
version: 2
date: 2026-08-25
area: Systems
status: ci-proven-not-operator-live
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
supersedes: SYS_OPS_devon-hermes-stack-status_v1_2026-08-24.md
---

# DEVON Hermes Stack Status v2

## This arc (PRs 43, 44, 45, all merged)

CI had been red on main since the effect-receipts runtime wiring (run 206).
PR 43 restored it to green and closed a real governance hole; PR 44 landed
the Build 12 banded conflict policy; PR 45 finished the ops polish.

| Change | PR | Status |
|---|---|---|
| CI restored: test DB schemas 008-010, replay parity, typed orphan refusal, offline planner, FastAPI 0.141 compat, soul route allowlist, doc hygiene | 43 | Merged |
| Durable effect intents: intent commits before the adapter runs, so orphan refusal survives a real worker crash | 43 | Merged |
| Multi-worker lease-loss crash matrix (test_devon_lease_loss_crash_matrix.py) under real concurrency | 43 | Merged |
| Build 12 banded conflict policy for soul conflict-search | 44 | Merged |
| Auto skill-propose dedupe by goal slug | 45 | Merged |

## On main

| Capability | Status |
|---|---|
| Agent runtime + leases + idempotency | CI-proven, crash matrix proven. Not operator-live. |
| Effect intents / receipts + orphan refusal | CI-proven, intent durable before effect. Not operator-live. |
| Cerebras voice / enrichment default | CI-proven (key required). Not operator-live. |
| Subagents (durable parent-child links, schema 010) | CI-proven. Not operator-live. |
| Scheduler (create / due / materialize) | CI-proven. Not operator-live. |
| Browser allowlisted fetch + approved navigate | CI-proven (live fetch opt-in). Not operator-live. |
| Skill proposals + human promote | CI-proven, deduped by goal slug. Not operator-live. |
| Soul conflict-search (Build 12 banded policy) | CI-proven. Not operator-live. |

Honest label: schema and CI green are not the same as a person running Hermes as the live operator. This stack is CI-proven / not operator-live.

Update 2026-09-02 (fix PR 3 of the DEVON and Hermes audit): the three runtime tools, runtime.spawn_subagent, runtime.schedule_goal and runtime.propose_skill, now spend their approval binding and write the same tables the HTTP routes read. Before that date the subagent, scheduler and skill-proposal rows above were true for the HTTP routes only; the runtime tool path was process-local (audit finding H6).

Update 2026-09-09: the Hermes agent surface is machine checked against this
record. `docs/devon/hermes-surface.json` pins it, and
`test_devon_hermes_surface.py` re-derives it from the code on every run,
failing when the two disagree and naming exactly what moved.

Tools come from `build_tool_registry()`, the registry the running service
builds, each with its risk class, reversibility and blast radius. Routes are
read from every v1 router whose prefix begins `/agent`, discovered by walking
the package rather than from a list, and read from the routers themselves
rather than from the OpenAPI schema, because the schema omits a route declared
`include_in_schema=False` and such a route still answers. Columns cover every
agent table declared anywhere under `app/models`, not one module. Migrations
cover those that touch one of those tables, and a migration file that declares
no readable revision fails the run rather than being skipped, which is how the
repository's own `alembic revision` template slipped past the first cut.

These counts are the gate. Regenerating the manifest does not clear a failure
on its own, because the test reads this block and checks it against the code,
so a surface change has to move this document too:

```hermes-surface-counts
tools 20
routes 24
columns 126
states 9
migrations 7
```

What it does not cover, stated plainly so nobody reads more into a green run.
The Status column of the table above is a human judgement and stays one. The
behaviour behind a tool is unpinned, so a rewritten implementation under an
unchanged name, risk class and blast radius still passes. A column added by
raw SQL under `database/schemas/` that no model declares is not seen, and
neither is a rewritten migration body under an unchanged revision. The
migration list is read from the source tree, which says what the next deploy
will apply and not what production runs; the deployed estate stays the job of
`scripts/estate_reconcile.py` and stays UNVERIFIED without a Railway read.

## Governance invariants held

- DEVON core remains effect-free
- WRITE / HIGH_IMPACT tools require human approval
- Orphan effect intents refuse automatic retry, and the intent now survives
  a worker crash so the refusal actually fires
- Skill promotion is human-gated; duplicate drafts for one goal suppressed
- Materialize and spawn never auto-run effects
- Soul service answers exactly one non-GET route, the read-only
  conflict-search POST, pinned by invariant tests

## Remaining manual item

- Operator-live verification in Tee's deployed environment (deployed DB at
  Alembic head 018 as of 2026-09-03, amended from 015 on that date, one Cerebras voice turn, one materialize-run-complete
  path, one propose-approve-promote path). Not reachable from CI or agent
  containers. Until that lands, do not call this stack Live.
