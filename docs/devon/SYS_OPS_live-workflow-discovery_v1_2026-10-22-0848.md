# Owner-bound live workflow discovery

Supersedes the inventory limitation in SYS_OPS_workspace-source-audit_v1_2026-10-22-0813.md only after the new API is deployed and its account binding is verified. Code completion is not production activation.

## Evidence and correction

The independent self-hosted database read at2026-10-22T08:28:33Z counted209 workflows total,110 unarchived and68 active/unarchived. The static vault has54 distinct IDs and omits23 active IDs. Discovery is now a live read rather than an expansion of that stale static list.

The authenticated Control Plane read at2026-10-22T08:33:35.350Z showed the primary Cloud hostname answering404 and the secondary self-hosted hostname returning100 saved execution rows. The new reader selects exactly one canonical self-hosted URL and its PAIRED key. It never calls Cloud or forwards its key to the secondary. No production variable has been changed by this candidate.

The new GET /api/v1/n8n/workflows route and conversational n8n.workflow_inventory READ tool require an explicit estate-owner UUID matching the authenticated account. Missing binding disables the feature; another owner refuses before any provider request. Metadata is projected from bounded GET responses; no node parameters, credentials, pinned data or execution permission is exposed. Pagination has explicit complete, partial and failed states, including an explicit final cursor requirement.

Independent exact-source review passed59 focused tests. Removing the owner guard made5 cases fail, following redirects made1 fail, and using the Cloud primary key for the canonical secondary made1 fail. Mutations were restored. A separate worst-width pagination probe preserved10 unique workflow IDs and partial-state reporting under the turn budget. These are offline results, not a live inventory receipt.

## Presence wording

A second independent review confirmed the stage still claimed LiveKit had never published audio. Current server code starts a room publisher before ready when configured and selects room PCM instead of raw WebSocket PCM. The stage now describes both paths and refuses to equate connection or track state with audible playback. The19 publisher/configured-room checks passed with doubles; no production voice was generated. Client player comments were updated without changing transport logic.

## CI host compatibility

Audio CI run39750972507 stopped before playback/capture tests because its pinned Playwright1.56.1 refuses Chromium dependencies on the Ubuntu26.04 runner selected by ubuntu-latest. The audio job now pins Ubuntu24.04, matching the existing panel smoke job, without changing the browser version or skipping tests. Exact-head hosted checks must pass before merge.

## Activation and rollback

Verify the actual account UUID and set N8N_INVENTORY_OWNER_ID only for that account. Verify the self-hosted URL/key pairing and least-privilege list/read permission. After deployment, request inventory as the bound account and a second account: only the first may reach n8n. Compare IDs, observed time and completeness with the credential-visible upstream list. New workflows remain informational and cannot run because they were discovered.

Rollback unsets the inventory owner binding and reverts this reader and conversation registration. Existing workflow execution, canon, approvals and the pure services/devon package remain unchanged. No Data Table migration, notebook ingestion or browser provisioning is performed here.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_live-workflow-discovery_v1_2026-10-22-0848.md
DATE: 2026-10-22
DECISIONS: Current workflow discovery is owner-bound and read only; discovery never grants execution authority.
FINDINGS: Static catalog omits new active workflows; API still reads Cloud primary and self-hosted secondary; stage has stale LiveKit wording.
OPEN: Final full validation and CI, deployment, authenticated owner binding and live inventory readback, remaining Airtable migrations and funded notebook import.
STATUS: source candidate independently reviewed; production activation incomplete
