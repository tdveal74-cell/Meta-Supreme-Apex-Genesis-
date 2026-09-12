---
title: DEVON Hermes Stack Status
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: ci-proven-not-operator-live
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
---

# DEVON Hermes Stack Status

## On main

| Capability | Status |
|---|---|
| Agent runtime + leases + idempotency | CI-proven. Not operator-live. |
| Effect intents / receipts + orphan refusal | CI-proven. Not operator-live. |
| Cerebras voice / enrichment default | CI-proven (key required). Not operator-live. |
| Subagents (spawn durable child tasks) | CI-proven API. Not operator-live. |
| Scheduler (create / due / materialize) | CI-proven API + schema 009. Not operator-live. |
| Browser allowlisted fetch + approved navigate | CI-proven (fetch offline unless `DEVON_BROWSER_LIVE_FETCH`). Not operator-live. |
| Skill proposals + human promote | CI-proven API. Not operator-live. |
| Effect receipts provider_receipt_id (GitHub + Operator) | CI-proven. Not operator-live. |

Honest label: CI-proven / not operator-live. Superseded by v2.

## API surface

- `/api/v1/agent-tasks`: tasks, run, learning
- `/api/v1/agent-expansion/schedules`: create, list, due, materialize
- `/api/v1/agent-expansion/subagents`: spawn child task
- `/api/v1/agent-expansion/skill-proposals`: propose, list, decide+promote

## Governance invariants held

- DEVON core remains effect-free
- WRITE / HIGH_IMPACT tools still require human approval
- Orphan effect intents refuse automatic retry
- Skill promotion is human-gated
- Materialize and spawn never auto-run effects

## Remaining optional hardening

- Multi-worker concurrent lease-loss crash matrix under load
- Parent↔child join table beyond context fields
- Auto skill-propose after successful task completion (still requires Tee promote)
