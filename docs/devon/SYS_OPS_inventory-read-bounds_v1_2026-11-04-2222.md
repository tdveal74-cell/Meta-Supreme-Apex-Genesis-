# Bounded inventory reads for n8n 2.36.8

Status: locally validated candidate; GitHub CI and production readback pending.
Supersedes: the inventory-failure investigation state beside SYS_OPS_console-live-status_v1_2026-11-04-2110.md. Its delivered console and deployment receipts remain historical.

The owner binding was restored to the authenticated operator account and the
canonical execution telemetry returned upstream HTTP 200. Inventory then
returned failed with zero observed workflows. That is separate from an empty
estate. The precise current error is not yet visible in the shipped console.

An independent read-only inspection of the installed n8n 2.36.8 handler and
its database found a definite size incompatibility. List reads include editor
and published definitions even with excludePinnedData=true. The broad-owner
snapshot contained 283 workflows. Handler-matching JSON serialization measured
100/100/83-row pages at 2,109,225 / 5,205,944 / 6,285,786 decoded bytes, totaling
13,600,955. Its projected metadata was 53,155 bytes. Only aggregate sizes were
returned from the host; private definitions were not exported. This proves
that the old 2 MB page bound cannot cover this snapshot, rather than proving
it was the only cause of the current failed read.

This candidate permits 8 MB per decoded page and retains a 20 MB cumulative
allowance, the same ceiling as the original ten 2 MB pages. Each chunk is
checked before accumulation. A separate 2 MB projection limit includes an
envelope reserve. Only metadata is returned; full definitions are discarded
before the following fetch. A nonblocking lock permits one inventory read per
API process and releases on cancellation and failure. This is not a fleet-wide
lock or a guarantee of process RSS. The existing 100-row pages, ten-page cap,
30-second total timeout, fixed canonical host, paired credential selection,
GET-only transport, redirect/proxy refusal and exact owner binding remain.

The backend and console share a tested closed set of public failure reasons.
Authentication and permission refusals are distinguishable without reading
upstream refusal bodies. Unknown errors are reduced to a fixed generic reason;
no cursor, key, provider exception or private body is rendered. A failed or
partial result remains incomplete, and the client never retries or polls.

Before repair, five new Python regression cases and the new console reason
case failed. Focused checks now pass: 65 Python cases including the inventory,
console behavior and parsing checks; all twelve Node cases; targeted lint.
Full local validation passed at source 5a85cc60606d2092fb81e9e74e75ffea6010ce58:
9,760 tests and 56 subtests, 5,836 standalone tests, 25 engine cases, lint,
fresh Alembic upgrade/downgrade/upgrade and container imports. Strict root,
soul and locked pnpm dependency audits passed. Node 22 typecheck, all web
contracts, production build and 246 real Chromium checks passed. The API image
built and served the new console with networking disabled.

A fresh critic independently passed 49 inventory Python and twelve Node cases.
Deleting nine guards caused the corresponding tests to fail, including owner,
page/total/metadata bytes, singleflight, cancellation cleanup, backend/UI
redaction and session provenance. Separate probes covered chunked gzip decoded
bytes, six simultaneous thread/event-loop readers, escaped metadata overhead,
1,000-row/ten-page bounds and unexpected-exception cleanup. Synthetic 7.5 MB
JSON allocated 177.1 MB while parsing, confirming that the byte limits are not
RSS limits. The critic restored its source and its own checkout was clean.
No inference, production workflow execution or credential change is part of
this candidate. The previously applied owner UUID is a non-secret setting.

Rollback: revert this code candidate to main 9c21bd5fc586b0b07d5307cf72a486b09c7133a1.
Keep the explicitly restored operator owner binding unless separately ruled.
The existing API deployment d409cf23-6070-40a6-8b2f-9e231f407b43 is the runtime
baseline, with canonical telemetry working and inventory incomplete.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_inventory-read-bounds_v1_2026-11-04-2222.md
DATE: 2026-11-04
DECISIONS: Repair bounded canonical inventory transport and expose only fixed diagnostics.
FINDINGS: The measured n8n list pages exceed the existing per-page ceiling; exclusive runtime cause remains unverified.
OPEN: GitHub CI, rollout and authenticated inventory readback.
STATUS: candidate only; no model inference or workflow execution performed
