# Authenticated live status in the operator console

Status: locally validated candidate; GitHub CI and production readback pending.
Supersedes: no historical reference record. Adds explicitly current reads beside the dated reference decks.

The authenticated legacy console had no controls for the existing intelligence
status and owner-bound n8n inventory routes. Direct browser navigation cannot
supply the application's Bearer header. This candidate adds a manual read panel
using the existing operator session, without exporting a credential or widening
backend authorization.

One click issues only four fixed same-origin GETs: auth/me, intelligence/status,
n8n/workflows and n8n/executions?limit=1. Requests refuse redirects, omit cookies,
and never select a caller-provided URL. Missing authentication and the read-only
soul host refuse before transport; the panel is hidden on the soul host. There
is no automatic polling, retry, generation, effect, workflow execution or new
backend route. The same existing CurrentUser and inventory-owner gates apply.

Only account UUID, configured provider/model/simulated state, inventory state
and counts, and canonical n8n connection state are rendered as text. Refusal
bodies, transport exception text, token values, recalled records and execution
payloads are withheld. Partial/malformed inventories and unexpected hosts are
not reported as complete successes. Configuration is explicitly distinguished
from successful inference; active workflow counts are separate from health.

Eleven executed JavaScript cases cover the fixed wire contract, missing auth,
soul-host refusal, hostile route selection, upstream-secret redaction, partial
inventory, unexpected telemetry hosts and overlapping clicks. A fresh critic
reproduced a mixed-session provenance gap; three new cases failed before the
repair and pass after it. A read now captures one token, refuses a session
change before subsequent transport or final render, and discards all mixed
results. Sign-in and credential-save events clear stale observations.

Validation at source commit 84a761eba381c94562d7be66c0cb0e626d794dc2:
9,745 full-suite tests and 56 subtests passed; 5,836 standalone tests passed.
Engine, root lint, container import, fresh Alembic upgrade/downgrade/upgrade,
strict root and soul dependency audits and locked pnpm audit passed. The API
image built and served the repaired /console at 200 with network disabled.
Node 22 web typecheck, all web contract checks and production build passed.
Real Chromium passed 129 panel, 41 dock, 31 Command Center and 45 console
checks on a temporary local stack using mock providers and synthetic accounts.
A fresh independent critic passed 64 console pytest cases and all 11 Node
cases, plus an independent same-token session invalidation case. Removing the
session guards made both race tests fail. The critic checkout remained clean.

Production Gemini selection and public health were independently established
through browser reads and matching Railway HTTP logs. The affected VPS path
still times out. The published n8n audit found 73 active workflows, 138 Data
Table nodes and 29 remaining Airtable targets across eight workflows; none
were edited or executed here. This panel does not silently fix or approve that
cutover. The existing n8n inventory owner gate may still require configuration;
only its authenticated response can establish readiness.

Rollback: main 2bad8685483884a93f17750997d3cff00a920971. No provider, n8n,
credential, approval, network or canon setting was changed by this candidate.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_console-live-status_v1_2026-11-04-2110.md
DATE: 2026-11-04
DECISIONS: Add a fixed read-only status panel to complete owner-bound runtime verification.
FINDINGS: Existing operator UI lacks these authenticated read controls; candidate adds them without new backend access.
OPEN: GitHub CI, rollout and authenticated provider/n8n readback. Separate Airtable migration and provider inference acceptance remain open.
STATUS: candidate only; no model inference or workflow execution performed
