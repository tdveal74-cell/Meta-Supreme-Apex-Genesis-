---
title: DEVON Hermes Stack Status
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: operational-on-main
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
---

# DEVON Hermes Stack Status

## On main

| Capability | Status |
|---|---|
| Agent runtime + leases + idempotency | Live |
| Effect intents / receipts + orphan refusal | Live |
| Cerebras voice / enrichment default | Live (key required) |
| Subagents (spawn durable child tasks) | Live API |
| Scheduler (create / due / materialize) | Live API + schema 009 |
| Browser allowlisted fetch + approved navigate | Live (fetch offline unless `DEVON_BROWSER_LIVE_FETCH`) |
| Skill proposals + human promote | Live API |
| Effect receipts provider_receipt_id (GitHub + Operator) | Live |

## API surface

- `/api/v1/agent-tasks` — tasks, run, learning
- `/api/v1/agent-expansion/schedules` — create, list, due, materialize
- `/api/v1/agent-expansion/subagents` — spawn child task
- `/api/v1/agent-expansion/skill-proposals` — propose, list, decide+promote

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
