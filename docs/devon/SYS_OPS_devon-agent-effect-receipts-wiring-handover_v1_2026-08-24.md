---
title: DEVON Agent Effect Receipts Wiring Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: repository-ready-pending-runtime-path
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-effect-receipts-wiring
---

# DEVON Agent Effect Receipts Wiring Handover

## Delivered in this PR

- `app/services/agent_effect_receipts.py`
  - `arguments_hash`
  - `new_intent_id`
  - `EffectReceiptRepository.record_intent` (lease + generation fenced)
  - `EffectReceiptRepository.record_receipt` (lease + generation fenced, approval_token stripped)
  - `EffectReceiptRepository.find_orphan_intents` (surfaces AmbiguousOutcome)
- Offline helper tests

## Still required before the layer is complete

1. Runtime path: before every WRITE / HIGH_IMPACT adapter call, write an intent; after the call, write a receipt; on resume, surface orphan intents as AmbiguousOutcome and refuse automatic retry.
2. Adapter path updates for Operator and GitHub to return structured receipt metadata where available.
3. Crash-injection / orphan-intent regression against PostgreSQL.
4. Full CI green on the final head, then explicit merge authorization.

## Governance

- `services/devon` untouched
- Fencing uses the existing task lease token and execution generation
- No silent re-execution of ambiguous effects
