# DEVON workspace and source audit

Observed 2026-10-22, approximately 03:48 to 04:12 America/New_York. This is a bounded operational audit, not a security certification or proof every branch ran. Supersedes no historical incident record.

## Current authority

Tee identified self-hosted n8n at https://n8n.editforge.online and n8n Data Tables as current. Cloud and Airtable history remains history. The audit does not rewrite historical receipts or infer successful migration from mirrored table presence.

## Independently verified findings

1. Published active n8n workflow graphs retain 8 enabled, structurally reachable Airtable I/O nodes across 5 DEVON workflows: Pipeline Watchdog (1), Duplicate Sweep (3), Monthly Credential Review (1), iPhone Inbox Capture (1), Airtable Row Writer (2). V5 additionally retains 15 and the shared Error Handler 1. This proves configuration, not that each branch executed or wrote data. No proxy, hosts-file or router interception was observed. Migration is incomplete for these configured paths.
2. Pure DEVON brief/triage replies and episode filing plans name old Airtable destinations. This candidate updates their wording to current self-hosted Data Tables and preserves an explicit missing-handler read/write caveat. It adds no network effect to services/devon. Both soul copies match.
3. The control plane Presence note says LiveKit is unconfigured. Live presence /health returns livekit_configured=true and audio_over_websocket=false. The candidate replaces the static deployment claim with a transport explanation. Current sound playback is not proven by health or token HTTP200.
4. Graphify has a ready code graph for main bb19f04736dcd72f309b68686cc30c483ce9de56, 14,151 nodes and 32,942 edges. That connector is usable here. DEVON runtime PR372 remains draft/unmerged at 5dd27223f34e9757dade80d5658984345e134ec6; its recorded authentication/non-writing blockers remain. Current main and deployed API lack its services/graphify runtime. Do not say DEVON itself retrieved Graphify code.
5. API deployment43a442e1-ea6a-4fa3-a74c-812a28ecdd81 remains SUCCESS on9fbc37e35acc38880e6f0b5a5978a58a6fcb9418. Main advanced to2fe0b604f410736ed5216cb7dacd95c7f5ad407a after PR395 merged. The web production deploymentdpl_J5DYoPFrjnNpzYFPnZHS9xaGS89M is READY on that commit; this is frontend evidence only. Original NotebookLM importer reuses existing backend routes; API age alone does not mean its backend is missing. OpenRouter provider PR395 is merged, but its backend still needs deployment and a funded working key.

## Availability and limits

API, presence, Soul and self-hosted n8n health all returned200. Scheduler logs show a real scheduled tick reading due goals and finding none. This is not proof a nonempty goal executed. Recent LiveKit token requests returned200. The24-hour n8n saved execution window had141 success and7 error rows, with the errors in TSWS micro integration/test lanes; unsaved successes and swallowed refusals are outside that count. The latest saved DEVON Error Alarm error is older, October12, and no new retry was launched.

The self-hosted database holds76 Data Tables; the read found no table-name containment collisions and no active name-mode Data Table locators. The Capture Webhook is active and same-as-published, with Data Table nodes. This does not certify every migration.

Railway variable names include primary and secondary n8n URL/key pairs. Connected-app reads do not expose values. The authenticated telemetry read could not be completed because the browser stopped responding. Which URL/key pair the live API uses remains unverified; no blind swap was made.

## New workflow inventory

An independent metadata-only database read at2026-10-22T08:28:33Z counted209 workflows total,110 unarchived and68 active/unarchived. The static vault contains54 distinct workflow IDs. Exactly23 currently active workflows are absent from that map, including six DEVON bot/desk workflows. Two mapped IDs are absent from the current database. Titles containing DRAFT or INACTIVE are not authority for activation state.

The corrective lane is a bounded metadata-only live inventory read, with explicit estate-owner binding and no execution grant. Updating the static map alone would recur. No new workflow was executed or authorized by discovery.

## Dedicated computer and browser

The existing Browser Desk on srv1936199 belongs to Tee and carries its own persistent profile. It has not been assigned to DEVON. DEVON's existing browser.navigate adapter only records an approved intent; visited=false means it opens no browser. The operator shell also is not a dedicated operating-system sandbox.

The new workspace needs its own container and profile volume, no Tee cookie/profile reuse, no Docker socket or host filesystem mount, bounded resources, private authenticated transport, explicit owner binding, and human approvals enforced before actions. Browser task prompts alone cannot enforce those approvals. Verification must cover cross-owner refusal, private-network refusal, approval replay/refusal, cancellation, restart persistence and an actual page-open receipt before claiming live browser ability. Rollback disables the bridge and stops only the new workspace while retaining its volume. No new computer or browser bridge is deployed by this candidate.

## Workspace and dispatch candidate

The existing Command Center, Control Plane and new Agent dispatch panel share /command-center with view selectors; legacy /control redirects there. Notebook Import stays available from its navigation. Existing panels are reused, with only the selected workspace mounted. No auth boundary is removed.

Dispatch uses existing owner-scoped task/subagent/run routes. Child creation does not run. Run is explicit, uses bounded steps and an idempotency key; no failed request is automatically retried. Effectful steps retain a separate human ruling. Approval tokens stay in component memory and are not recoverable after leaving/reloading the panel; keep it open until deciding. No provider-independent external agent fleet, load balancing or autonomous effect dispatch is claimed.

## Hermes updates

DEVON is a custom Hermes-inspired runtime, not a verified installed upstream package. The original runtime handover explicitly states no upstream source was copied. Official upstream latest checked asv0.22.4, published October21,2026. A daily DEVON Hermes Updates watch was created and confirmed enabled; it reports applicable changes and compatibility work, and does not auto-install, merge, deploy or bypass approvals.

## Open

- Initial source validation passed5433 tests with3 skipped; the independent component review and9 dispatch regressions passed, including a negative control. The combined main revision is undergoing final full validation. Finish candidate CI and deployment readback. This document is not production completion evidence.
- Migrate the counted live legacy workflow nodes through supported n8n publication, preserving filters, schema, identity, approval and receipts. No live workflow edits were made in this audit.
- Verify the API's authenticated n8n source host and key pairing.
- Complete Graphify provider-supported non-writing runtime activation separately; preserve PR372's explicit draft hold.
- Notebook import remains unperformed; usable embedding credit/key and provider deployment remain prerequisites.
- Agent dispatch has no successful live user-account run receipt yet.
- Self-hosted n8n administration currently opens a sign-in page in this browser; no authenticated publication channel is available here. The installed n8n skill exposes no administration tools in this session.
- The dedicated computer/browser remains a separate implementation lane; it has not replaced the notebook, workflow or audit work.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_workspace-source-audit_v1_2026-10-22-0813.md
DATE: 2026-10-22
DECISIONS: One workspace; self-hosted n8n and Data Tables are current; preserve human effect approvals.
FINDINGS: Published legacy Airtable paths, stale source and Presence wording, Graphify runtime hold, deployed API behind main.
OPEN: Workflow migration, authenticated host read, candidate delivery, Graphify activation, funded notebook import, live dispatch proof.
STATUS: audit verified; source candidate under validation; production remediation incomplete
