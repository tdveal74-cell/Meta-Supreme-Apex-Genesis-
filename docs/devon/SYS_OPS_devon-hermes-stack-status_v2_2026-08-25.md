---
title: DEVON Hermes Stack Status
type: SYS_OPS
version: 2
date: 2026-08-25
area: Systems
status: operational-on-main
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
| Agent runtime + leases + idempotency | Live, crash matrix proven |
| Effect intents / receipts + orphan refusal | Live, intent durable before effect |
| Cerebras voice / enrichment default | Live (key required) |
| Subagents (durable parent-child links, schema 010) | Live |
| Scheduler (create / due / materialize) | Live |
| Browser allowlisted fetch + approved navigate | Live (live fetch opt-in) |
| Skill proposals + human promote | Live, deduped by goal slug |
| Soul conflict-search (Build 12 banded policy) | Live |

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

- Live verification in Tee's deployed environment (deployed DB at Alembic
  head 010, one Cerebras voice turn, one materialize-run-complete path, one
  propose-approve-promote path). Not reachable from CI or agent containers.
