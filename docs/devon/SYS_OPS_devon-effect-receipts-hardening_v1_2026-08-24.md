---
title: DEVON Effect Receipts Hardening
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: hardening-ready-pending-final-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-effect-receipts-hardening
---

# DEVON Effect Receipts Hardening

## Delivered

- GitHub adapter surfaces `provider_receipt_id` from sha / commit sha / html_url / url / number
- Offline hardening tests:
  - receipt id extraction from GitHub result metadata
  - runtime passes provider_receipt_id into the durable receipt
  - approval_token does not appear in receipt raw_response
  - AmbiguousOutcome refuses automatic retry framing

## Already on main from prior PRs

- Contracts, models, migration 008
- Fenced EffectReceiptRepository
- Runtime intent → call → receipt path
- Orphan-intent refusal before run

## Still limited

- Full multi-worker PostgreSQL crash-injection under concurrent lease loss remains optional further hardening
- Operator shell path still has no provider-native receipt id (by design: no external object id)
