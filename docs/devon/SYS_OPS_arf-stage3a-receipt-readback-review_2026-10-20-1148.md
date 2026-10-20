# ARF Stage 3a Receipt Readback Review
AREA: Systems
TYPE: SYS_OPS
DATE: 2026-10-20
STATUS: draft PR review, not deployed

## Scope
ARF adds an opt-in authenticated GET endpoint for DEVON build-stage
shadow diagnostics. The endpoint is disabled unless the operator sets
ARF_SHADOW_READ_ENABLED, and it has no task, approval or effect mutations.

The new declared-check reader uses owner-scoped immutable tool-result
and verification records. It recomputes checks and may attest only
requirement_evidence, never human acceptance, creative canon, source
truth, spending approval or production publication.

Approval readback is restricted to the current task's exact bound markers.
The API endpoint intentionally supplies no approval database reader, so
it cannot authorize or attest any effectful tool.

## Verification
The isolated package passed 110 offline unit cases with explicit test
shims. These are not hosted CI or real database tests.

The initial draft PR #381 standalone workflow had 1,743 tests pass,
1 skipped, and 2 route-manifest accounting failures. It exposed the new
GET route in code but left the governed route count at 32. This follow-up
records 33 routes in the generated manifest and status counts without
weakening tests. Rerun CI on this exact correction before promotion.

## Remaining gates
Verify the exact PR-head hosted CI, real PostgreSQL integration, real
authentication and cross-tenant refusal, and output redaction. Obtain
operator permission before changing the feature flag or deploying the
candidate. This PR does not activate the shadow endpoint or enforce
domain acceptance across TSWS, TQO, NCO Forge, EditForge or WhatBroke.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_arf-stage3a-receipt-readback-review_2026-10-20-1148.md
DATE: 2026-10-20
DECISIONS: Keep Stage 3a as a default-disabled, authenticated, read-only build-stage diagnostic; do not bypass CI or operator authorization for activation.
FINDINGS: Stage 3a candidate passed standalone, dependency, engine, container and Chromium smoke checks; the initial PostgreSQL suite failed five status-document receipt and timestamp governance assertions, repaired in this revision.
OPEN: Fresh exact-head PostgreSQL and Ruff CI; deployment readback; authenticated cross-tenant denial before enabling ARF_SHADOW_READ_ENABLED.
STATUS: Corrected draft, not merged or activated at document creation.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
