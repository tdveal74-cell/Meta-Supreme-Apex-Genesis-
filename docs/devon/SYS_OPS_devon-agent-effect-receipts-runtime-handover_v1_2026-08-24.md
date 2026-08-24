---
title: DEVON Agent Effect Receipts Runtime Wiring Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: wiring-ready-pending-final-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-effect-receipts-runtime
---

# DEVON Agent Effect Receipts Runtime Wiring Handover

## Delivered

- Optional `EffectRecorder` protocol in the portable runtime
- Runtime writes intent before WRITE/HIGH_IMPACT execution and receipt after, only when a recorder is injected
- `LeasedEffectRecorder` application adapter (lease + generation fenced)
- `DurableAgentTaskService` injects the recorder under a live lease
- Orphan-intent check before run: refuses automatic retry with `ambiguous_external_effect`
- Offline test covering intent + receipt path after approval

## Governance

- `services/devon` untouched
- Runtime remains framework-free without a recorder
- No silent re-execution of ambiguous effects

## Remaining evidence before review-ready

- Full CI green on this branch head
- Explicit merge authorization from Tee

## Explicitly still limited

- Adapter-native provider idempotency propagation beyond metadata `id` / `provider_receipt_id`
- Full PostgreSQL crash-injection suite (orphan path is implemented; broader DB race tests remain next)
