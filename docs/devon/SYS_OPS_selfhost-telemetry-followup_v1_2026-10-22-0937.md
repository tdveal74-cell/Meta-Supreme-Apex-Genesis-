# Self-hosted n8n telemetry follow-up

Supersedes the execution-source uncertainty in SYS_OPS_workspace-source-audit_v1_2026-10-22-0813.md. This is source-validation evidence, not a production rollout receipt.

## Change

The authenticated execution route selects exactly one complete canonical self-hosted URL/key pair. It preserves that slot's execution cap, accepts the root or /api/v1 base form, removes the retired slot, and refuses missing, mismatched or ambiguous configuration without making a request. A refusal never falls back to Cloud. Transport does not follow redirects or environment proxies.

Existing generic offline telemetry readers remain available. This does not expand authentication or grant workflow execution.

## Independent verification

An independent isolated reviewer ran all 243 telemetry tests without a database. Negative controls failed when redirects were enabled, the route reverted to the multi-instance reader, or the wrong slot's key was selected. Reviewed candidate files remained unchanged.

A prior combined candidate passed 5,562 backend tests, with 3 skipped, plus standalone, Ruff and migrations. Validation against current main including PR398 is recorded in the delivery PR; the prior run alone does not establish compatibility with that later merge.

## Operational state

Railway API deployment 43a442e1-ea6a-4fa3-a74c-812a28ecdd81 still reports commit 9fbc37e35acc38880e6f0b5a5978a58a6fcb9418. Railway's October22 09:28UTC status update says Hobby builds remain unavailable. No stale-build redeploy was triggered.

PRs394 through398 are merged. This telemetry change still needs exact-head CI, merge and backend deployment, then an authenticated live execution read naming only n8n.editforge.online. The workflow inventory also needs explicit estate-owner configuration and its own live receipt. Notebook ingestion needs a working embedding account and backend rollout.

Graphify's repository is queryable through the connected app. PR372 explicitly remains draft pending provider-supported non-writing behavior and runtime activation. No Graphify runtime activation is claimed.

The isolated browser candidate's 13 real-Chromium tests passed after the close lifecycle correction. An independent negative control removing the awaited cleanup failed both close tests. Persistent-volume and crash recovery were exercised separately: a stale socket refuses automatic restart, historical receipts survive manual reconciliation, and the old crashed profile is not reused. Browser networking and a DEVON transport adapter remain separate work; no live browser is claimed.

## Hermes watch

The existing DEVON Hermes Updates automation remains enabled daily. Its recorded October22 run c8ff9bbd-82a8-8323-acc3-4e7d5d5a812a completed with no_update at07:55:18Z. That means output was suppressed, not proof of DEVON ingestion or delivery. No duplicate watch was created and no upstream package was auto-installed.

## Rollback

Revert the execution-route selection change if compatibility requires it. Disable the read capability while reconciling configuration; do not silently redirect it to the retired Cloud estate. No data migration or production variable change is part of this source change.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_selfhost-telemetry-followup_v1_2026-10-22-0937.md
DATE: 2026-10-22
DECISIONS: Read only the canonical self-hosted n8n pair; preserve existing approvals and independent delivery.
FINDINGS: Independent telemetry tests and negative controls passed; production API remains on the previously deployed commit.
OPEN: Exact-head delivery and live readback, workflow migrations, owner-bound inventory activation, notebook funding and ingestion, dedicated browser integration.
STATUS: independently verified source correction; production rollout incomplete
