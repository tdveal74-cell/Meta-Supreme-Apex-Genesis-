# DEVON thread receipts move from Airtable to an n8n data table

Status record for 2026-10-16. Tee ruled that DEVON thread receipts live in the
n8n data table `at_tqo_thread_receipts` (`JCwPJ37BmyUW21r1`, project
`qbrcjkbIoorbwot6`) on the self hosted n8n at n8n.editforge.online, not in
Airtable Thread Receipts (`tblEhgEZoNr2ztbB3`). Two live workflows changed and
both were published on his rulings, given on cards in the session.

## What was true before

The data table was made by the 2026-09-15 migration and held four rows, all
copied from Airtable that night. Nothing had written to it since. The capture
webhook still created an Airtable record, and the Notion Buffer Drain still read
Airtable, so the data table was a copy that nothing kept current.

The Airtable table held the same four receipts, all ticked synced to Notion,
read on 2026-10-16. No receipt existed in Airtable that the data table lacked,
so moving the drain stranded nothing.

## What changed

**Today's receipt, written directly.** Row 5, created 2026-10-16T20:58:22Z,
read back. The TOKEN line was stripped before filing, as the webhook does. The
earlier attempt to post it through the webhook was refused with HTTP 403
because the capture key, added today as an environment network secret, does not
reach a session that started before it existed.

**The capture webhook (`Me7DDHBDX28ppvHA`).** The last node, "File to Thread
Receipts", was an Airtable create. It is now a data table insert under the same
name, so the Confirm node and the reply a poster gets are unchanged. The same
twelve fields are mapped; the AREA list is joined into one string. Published as
version `78b22003-26b2-4770-84d2-9d6ab20849ea` and read back with
`activeVersionId` equal to `versionId`. The previous version,
`c9e85add-737d-4c02-9d6a-7f9de358f0c1`, cannot be restored: see Rollback.

**The Notion Buffer Drain (`ptAmD28msYTvobgq`).** A fresh critic found that
the webhook change alone cut receipts off from Notion, and a second agent
confirmed it: the drain read and ticked Airtable only, and two workflows read
the Notion Thread Log it fills, Soul Layer Write-Back (`rZdhFXcsOyBcEkgR`) and
Capture Nudge (`3B8pGfSklJMte3ut`). The drain now reads the data table, skips
rows whose `synced_to_notion` is true, and sets that column after the page is
made. The dedupe key written to the page's Source row is a migrated row's
Airtable record id, so it still matches pages the old drain filed, and
`dt:<row id>` otherwise. Sync failures still log to Airtable Conflicts
(`tblbenoy1QF9KAftn`). Published as version
`1d52d17d-0991-4eda-9269-8e3077791c89`. The previous version,
`6328edae-92d8-4635-8e94-0f8ebe521a68`, cannot be restored: see Rollback.

**The repository.** `services/devon/vault.py` and its deployed copy now name
the data table as the webhook's destination and as the drain's source. The
drain's live Shape for Notion code is at
`n8n/devon/notion-buffer-drain/shape_for_notion.js`.

## Rollback

This doc and both version descriptions first said the previous versions
restore the Airtable path. That was false, found by the closing critic on
2026-10-17 and confirmed by a verifier: `get_workflow_version` answers "was not
found for this workflow. It may have been pruned by workflow history retention"
for both ids, and the history of every workflow read on this instance (six of
them) holds one version only. A publish here leaves nothing behind to restore.

So the Airtable versions now live in the repository:

- `n8n/devon/notion-buffer-drain/rollback/ptAmD28msYTvobgq_6328edae_airtable.json`
  is the whole previous drain, from a public API listing read while 6328edae was
  live. It carries credential ids and no secret.
- `n8n/devon/notion-buffer-drain/rollback/Me7DDHBDX28ppvHA_c9e85add_airtable_node.json`
  is the one webhook node that changed, copied from a read of c9e85add. The rest
  of that workflow is unchanged and is not copied, because its Check Token node
  holds the capture tokens.

Rolling back means rebuilding from these files with `update_workflow`, then
publishing, which is Tee's call.

Before any later n8n publish here, export the live version first. The history
will not keep it.

## Proof

Drain execution 3300, manual, 2026-10-16T21:07:18Z, success. Read Thread
Receipts returned five rows. Shape for Notion passed one, row 5, keyed `dt:5`.
Find Existing Page returned no match, Create Notion Page made page
`3fb68ff5-0db6-81f2-8db5-f0da1b193aa4` with Area Podcast and Systems, and Tick
Synced to Notion set row 5's `synced_to_notion` to true at 21:07:19Z.

Soul Layer Write-Back execution 3301, 2026-10-16T21:15:43Z, read the new page
and its upsert to `tee-soul-layer` returned HTTP 201. The same run also took a
second page for the same session, `3fb68ff5-0db6-811d-a982-f59f294a9a2f`, filed
straight into Notion at 21:01Z by another Notion user with an empty Source row.
The Thread Log and the rulings namespace therefore hold two differently worded
records of the 2026-10-16 decisions. The drain cannot catch that: its dedupe
matches Source row, and a page filed by hand has none. The Airtable path had the
same gap. Tee ruled both kept.

The production devon-soul deployment after the merge is commit `6c5e674`,
READY, and `/api/v1/health` returned 200.

The changed shaping code was run locally against four sample rows before it was
saved, covering a synced row, an unsynced new row, a migrated row with an
unknown Area and a row with no title. The saved draft was read back and matched
the tested file before publishing.

Locally: `test_deploy_soul.py`, `test_devon_integrity.py`,
`test_estate_reconcile.py` and `test_devon_receipts.py` returned 569 passed;
the test files named in `ci.yml` returned 1661 passed; ruff clean.

## Not proven

- No receipt has yet travelled the published webhook. Its executions are not
  saved, and this session cannot send the capture key. The first receipt posted
  from a new session, read back as row 6 or later, is that proof.
- No scheduled run of drain version 1d52d17d had happened by the closing
  critic's read, and no run has yet handled an empty buffer or more than one
  row.
- The webhook's Confirm node reads Apply Token Identity through the paired item
  of the data table insert. The critic confirmed the insert keeps it from the
  upstream n8n source, not from the build on the VPS.

## Open

- Post one real receipt through the webhook from a new session and read the row
  back.
- Airtable Thread Receipts and the reconciler's Area vocabulary check on it are
  left in place. Retiring them is Tee's call.
- The closing critic's low findings, left as they are: the Find Existing Page
  note still says "Airtable row id"; Read Thread Receipts pulls every row daily
  with no filter; a failed tick and a failed Conflicts write are silent; and a
  malformed date that Airtable used to reject now reaches Notion and is retried
  daily. None loses a receipt.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_devon-receipts-to-data-table_v1_2026-10-16-2108.md
DATE: 2026-10-16
DECISIONS: Tee ruled receipts live in the n8n data table at_tqo_thread_receipts, not Airtable; ruled today's receipt written directly; ruled the capture webhook changed and published by the session; ruled the Notion drain repointed, published and run once.
FINDINGS: The webhook change alone stopped receipts reaching Notion, the soul layer write-back and the capture silence check, found by a critic and confirmed by a verifier. The drain now reads the data table; execution 3300 filed today's receipt to Notion and marked it synced, and soul layer execution 3301 upserted it. The previous n8n versions cannot be restored because the instance keeps one version per workflow, so the Airtable versions are saved in the repository.
OPEN: No receipt has yet travelled the published webhook; no scheduled drain run yet; Airtable Thread Receipts left in place pending Tee; four low critic findings left as they are.
STATUS: Live. Webhook 78b22003 and drain 1d52d17d published and read back.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
