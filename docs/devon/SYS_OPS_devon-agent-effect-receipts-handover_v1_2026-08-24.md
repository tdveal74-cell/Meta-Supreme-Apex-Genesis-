---
title: DEVON Agent Effect Receipts Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: foundation-ready-pending-final-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-effect-receipts
---

# DEVON Agent Effect Receipts Handover (Phase 1 Foundation)

## 1. Executive state

This PR lands the foundation for adapter-level durable effect receipts. It closes the data-model and schema gap required before the runtime can safely write an intent, call a capability adapter, and record a receipt.

It does **not** yet wire the runtime call path to write intents before every WRITE/HIGH_IMPACT adapter call. That wiring is the next implementation slice and must not be claimed as done by this PR.

## 2. What this PR delivers

- Framework-free contracts: `EffectStatus`, `EffectIntent`, `EffectReceipt`, `AmbiguousOutcome`
- SQLAlchemy models: `AgentEffectIntentRecord`, `AgentEffectReceiptRecord`
- Re-runnable SQL schema `008_agent_effect_receipts.sql`
- Alembic migration `008_agent_effect_receipts` (revises 007)
- CI gates updated to require schema + migration + tables + Alembic head `008_agent_effect_receipts`
- Offline contract/model registration tests

## 3. Governance preserved

- `services/devon` is untouched
- Existing lease + fencing + `agent_task_runs` remain the arbitration authority
- No silent re-execution logic is introduced in this PR
- Capability adapters remain the only effect boundary

## 4. What is deliberately not in this PR

- Runtime wiring that writes an intent before an adapter call
- Adapter `execute_with_receipt` path implementation for Operator / GitHub
- Crash-injection test that leaves an intent without a receipt
- Repository methods that fence receipt writes against stale workers
- Browser automation, subagents, scheduler, autonomous skill generation

## 5. Next required slice

1. Add repository methods that record intents and receipts under the live lease generation
2. Update the runtime to write an intent, call the adapter, then record the receipt
3. Update Operator and GitHub adapters to return structured receipts
4. Add the crash-injection regression that proves automatic retry is refused when an intent exists without a receipt
5. Full CI green, then explicit merge authorization

## 6. Merge state

PR remains open and unmerged. Do not merge without Tee's separate explicit authorization after final CI on the PR head is green.
