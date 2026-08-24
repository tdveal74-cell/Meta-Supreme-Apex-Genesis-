---
title: DEVON Agent Effect Receipts Design
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: design-approved
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-effect-receipts
---

# DEVON Agent Effect Receipts Design (Phase 1)

## Purpose

Close the remaining reliability window left after PR #29:

1. Capability adapter successfully performs an external effect
2. Process dies before the runtime can durably record the success

On restart the system must not silently re-execute and must not pretend the outcome is known.

## Non-negotiable rules

- `services/devon` remains effect-free
- Existing lease + fencing + `agent_task_runs` stay the arbitration authority
- Capability adapters remain the only place external effects occur
- No silent re-execution of an effect whose outcome is ambiguous
- Every durable effect receipt is inspectable and bound to the original task/run/idempotency key

## Core concepts

### EffectIntent
A pure, durable record written *before* the adapter is called:
`task_id + step_id + tool_name + arguments_hash + idempotency_key + intent_id`

### EffectReceipt
Written once the external system has acknowledged the effect (or the adapter has recorded that no provider-level idempotency was available):
`intent_id + provider_receipt_id + status (succeeded | failed | ambiguous) + sanitized raw response`

### AmbiguousOutcome
If an intent exists and no matching receipt is found after a crash, the runtime surfaces the task as FAILED with reason `ambiguous_external_effect` and refuses automatic retry.

## Adapter contract

New recommended path:

```text
def execute_with_receipt(
    self,
    *,
    intent: EffectIntent,
    arguments: dict,
) -> EffectReceipt
```

- Adapters with native idempotency propagate the key and return a real provider receipt.
- Adapters without it still return an explicit receipt that records the limitation.
- WRITE / HIGH_IMPACT tools use this path once the layer is active.

## Persistence

New tables (migration 008):

- `agent_effect_intents`
- `agent_effect_receipts`

Both bound to task/run/lease generation so a stale worker cannot write a receipt for a lease it no longer owns.

## Out of scope for Phase 1

- Browser automation
- Subagent pool
- Scheduler / cron
- Autonomous skill generation
- Changing the approval gate
- Claiming true distributed transactions

## Verification bar

Same standard as PR #29: unit + integration tests, crash-injection test, security test (no secrets in ledger), migration round-trip, full CI green, handover filed, explicit merge authorization required.
