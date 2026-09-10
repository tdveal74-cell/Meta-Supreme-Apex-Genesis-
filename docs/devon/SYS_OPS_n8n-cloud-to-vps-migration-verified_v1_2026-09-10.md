# SYS_OPS: the n8n Cloud to VPS migration, verified

2026-09-10. Tee asked whether the migration from n8n Cloud to the VPS at
`n8n.editforge.online` actually carried everything across. It did, as of the
dates it was taken. The migration is not the problem. What the diff surfaced
instead is that the VPS copy of the TQO pipeline predates a security hardening
that Cloud already has, and that fact would have been invisible to anyone who
only counted workflows.

## The two instances

| | Cloud | VPS |
|---|---|---|
| host | `thequietoperator.app.n8n.cloud` | `n8n.editforge.online` |
| project | `rM0TNTE2fNXErglU` | `qbrcjkbIoorbwot6` |
| workflows | 49 | 58 |
| active | 42 | 0 |
| data tables | 11 | 9 |
| credentials | not counted | 28 |

Measured 2026-09-10 06:30 UTC through the two n8n MCP connectors. The VPS
connector is a second install of the same directory connector, not a custom
URL entry, and it is named `n8n vps` in the account so the two can be told
apart. Confirming it was genuinely a second instance and not Cloud under a
second name took four independent checks: every workflow ID differs, the
project ID differs, it carries 17 workflows Cloud does not have, and its tool
surface differs, exposing `create_folder` and `list_n8n_connect_services`
which the Cloud connector does not.

## The diff

41 of Cloud's 49 workflows are on the VPS. 8 are not. All 8 were created on
Cloud after 2026-08-31, which is the timestamp every VPS workflow carries from
the import. Nothing was dropped. The export is simply ten days behind:

`DEVON Airtable Row Writer (Build 17)`, `DEVON Gumroad Sale Check`,
`DEVON Drive Draft Writer (Build 16)`, `DEVON Driver Poll (Build 14)`,
`DEVON Face (Build 15)`, `DEVON Intake Former (Build 14)`,
`DEVON Job Driver (Build 14)`, `Gumroad Landing Page Helper (gxcyjr)`.

17 workflows exist on the VPS and not on Cloud. Most are TQO era rule patches
and the decomposed TQO experiment described below.

9 of Cloud's 11 data tables migrated. The two absent, `devon_driver_log` and
`devon_chat_log`, were both created on Cloud on 2026-09-05, after the table
snapshot of 2026-09-03. Two separate migration passes, then, workflows on
08-31 and tables on 09-03.

Column check across the 9 shared tables: **0 mismatches**, name, type and index
position. 206 columns in total, including the 34 on `devon_state_ledger` and 53
each on `tqo_content` and `nco_content`. Rows came too, not just schema:
`devon_state_ledger` carries 8 rows on the VPS, all bulk written at
2026-09-03T09:01:37.

## The finding: the VPS TQO pipeline predates Cloud's webhook hardening

`TQO FINAL V5` exists on both instances and carries 7 webhook triggers on each.
They are not the same 7.

On **Cloud** (active, 222 nodes, last updated 2026-09-08):

| method | path | guard |
|---|---|---|
| POST | `/webhook/run-tqo-pipeline` | header `x-devon-key` |
| GET | `/webhook/system-pause` | header `x-devon-key` |
| GET | `/webhook/system-resume` | header `x-devon-key` |
| POST | `/webhook/run-nco-pipeline` | header `x-devon-key` |
| POST | `/webhook/gumroad-sale-<16 hex>` | unguessable path only |
| GET | `/webhook/run-tqo-<16 hex>` | unguessable path only |
| GET | `/webhook/run-nco-<16 hex>` | unguessable path only |

On the **VPS** (inactive, 220 nodes, last updated 2026-09-03), the same seven
nodes report **no credentials required**, and the three that Cloud protects
with a random suffix sit on bare paths: `/webhook/gumroad-sale`,
`/webhook/run-tqo`, `/webhook/run-nco`.

The hex suffixes are deliberately not written into this document. They are the
guard on those three endpoints, and a document in a git repository is not where
a guard belongs.

So the hardening landed on Cloud between the 08-31 export and 09-08, and the
VPS never received it. Four of the seven VPS endpoints are GET requests with
side effects, two of them `system-pause` and `system-resume`. A GET with a side
effect fires from anything that merely fetches a URL: a link unfurler, a
crawler, browser prefetch, a preview card in a chat client.

**Current exposure is zero.** Nothing on the VPS is active, so none of those
paths are registered. The finding is a loaded gun, not a fired one. It becomes
real the moment anyone activates `TQO FINAL V5` on that box, and the obvious
move for someone finishing this migration is exactly that.

The fix is not to invent hardening. Cloud already solved it. Bring Cloud's V5
across rather than activating the VPS copy.

## Rulings taken 2026-09-10

**`TQO FINAL V8` was created in error by an agent. `TQO FINAL V5` is the real
TQO pipeline.** Ruled by Tee. V8 is archived on the VPS.

This reversed a recommendation made earlier the same day. A count of nodes had
put V5 ahead at 220 against V8's 80, and ahead again at 220 against 195 counting
V8 plus its six sub-workflows and orchestrator. Tee's own stated rule was that
the bigger of the two wins, which pointed at V5. Then a version diff showed V8
had received 13 credential rebindings at 07:27 that V5 had not, and on that
evidence V8 was recommended as the operationally ready one. The provenance
ruling settled it: V8 was never meant to exist. Node count and wiring effort
were both the wrong question.

**`TQO - ORCHESTRATOR` can be deleted.** Ruled by Tee. It was archived rather
than hard deleted, following the doctrine `DEVON Purge List (manual)` already
states for Drive: never hard delete, emptying stays a human act.

Archiving it orphans four workflows that have no triggers of any kind and could
only ever be called by a parent: `TQO Script Generation Sub-workflow` (7 nodes),
`TQO Packaging Sub-workflow` (7), `TQO Promote Sub-workflow` (3),
`TQO Rendering Sub-workflow (Detailed)` (14). 31 nodes now unreachable. They
were left alone because Tee named only the orchestrator, and because it is
**unverified** whether V5's 220 nodes also call them.

## Two corrections recorded

Both are errors made inside this session and caught the same day.

**The 06:14 batch was not development.** Eight VPS workflows share the timestamp
`2026-09-10T06:14:06.688` and were read as active TQO development, which was
written into a handover prompt and repeated to Tee twice. Tee corrected it: he
had enabled `availableInMCP` in bulk. The evidence was already visible and was
not looked at. Seven of the eight share that timestamp to the millisecond, and
none of them created a version entry. Hand editing cannot produce identical
milliseconds across seven files.

**Archiving a workflow makes it unreadable.** `TQO FINAL V8` was archived and
then could not be read back. Both `get_workflow_details` and
`get_workflow_history` return "archived and cannot be accessed". The archive
was performed before that was checked. Nothing was lost because the trigger
list and the full credential diff had been captured beforehand, but only by
luck. Check what a destructive operation costs you before running it, not after.

## Dangling references the import left behind

The migration carried Cloud workflow IDs into `errorWorkflow` settings, and
those IDs do not resolve on the VPS:

- `TQO FINAL V5` points at `rqYmaQh91iCce8DJ`, which is Cloud's
  `OS Error Handler (all pipelines)`. The VPS copy is `GbeNilHQzjmoWDz3`.
- `TQO Rendering Sub-workflow (Detailed)` points at `IYDof2FtoIJbUqCB`, which
  exists on neither instance.

Error routing on those workflows is silently broken. Zero impact while
everything is inactive, and no alert at all on the first failure after that.

## The credential map

Recovered from V8's 07:27 version diff before it was archived. It is the lookup
table for rebinding V5, and it is the one durable thing the V8 mistake produced:

```
TEJIJDPoEhid0aOE  ->  EdFztvzdUL9PSycJ   Header Auth account 3   Claude calls
WMz320icjnur7rDL  ->  NW3vR6nNcMoUkJyJ   Google Drive account    6 upload and share nodes
BT9qHSPFUV4L5hW6  ->  KtgOCINafn32E0h4   Header Auth account 8   render worker
eYTecIAkpa16GAQ6  ->  XbLg8FnNraeTbEfJ   Header Auth account 7   MailerLite
rqYmaQh91iCce8DJ  ->  GbeNilHQzjmoWDz3   errorWorkflow           OS Error Handler
```

Tee had said the credentials were not wired on the VPS. They largely are. The
box carries 28 credentials named to match Cloud, including `Header Auth
account 10`, which is what `TSWS 00 Render Job` wants. What is not done is
rebinding the workflow nodes, because the IDs differ between instances and an
imported workflow arrives carrying the Cloud ID.

## Work performed on the VPS

- Created `devon_driver_log` (`EHrmGJfmOKNJJcc4`, 11 columns) and
  `devon_chat_log` (`DKCusDJfIF8CPxyb`, 7 columns) from the Cloud schemas, read
  back and verified column for column including index order. Both are empty;
  the rows still need a Cloud read.
- Archived `TQO - ORCHESTRATOR` (`IBRMsfd5kGqRvfis`).
- Archived `TQO FINAL V8` (`DrK37dBm6n1idio8`).

Nothing was activated. The VPS remains at 0 active workflows, which is the safe
state while Cloud runs all 42.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_n8n-cloud-to-vps-migration-verified_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ruled that TQO FINAL V8 was created in error by an agent and that TQO FINAL V5 is the real TQO pipeline, reversing a same day recommendation that had favoured V8 on credential wiring; Tee ruled TQO ORCHESTRATOR could be deleted, and it was archived rather than hard deleted under the estate's existing never hard delete doctrine; Tee confirmed the 2026-09-10 06:14 bulk edit was him enabling availableInMCP and not development work; no ruling yet taken on which instance owns the schedules, on the four orphaned sub-workflows, or on rebinding V5's credentials
FINDINGS: the VPS copy of TQO FINAL V5 predates a webhook hardening that Cloud received between 2026-08-31 and 2026-09-08, so where Cloud requires an x-devon-key header on four endpoints and hides three more behind unguessable path suffixes, all seven VPS endpoints report no credentials and sit on bare paths, four of them GET requests with side effects including system pause and system resume; current exposure is zero because nothing on the VPS is active, and the finding becomes real only on activation; the migration itself is complete as of its snapshot dates, 41 of 49 workflows and 9 of 11 data tables with 0 column mismatches across 206 columns and rows intact, every absentee having been created on Cloud after the snapshot that produced the export; the import carried Cloud workflow IDs into errorWorkflow settings on at least two workflows and those IDs resolve to nothing on the VPS, so error routing is silently broken; two errors were made and corrected inside the session, reading a bulk availableInMCP flip as live development and archiving TQO FINAL V8 before checking that archiving makes a workflow unreadable
OPEN: copy rows into the two newly created data tables and import the 8 workflows Cloud has that the VPS does not, both of which need a Cloud read; rebind TQO FINAL V5's credentials on the VPS using the recovered map, which means rewriting a 220 node workflow; decide which instance owns the schedules before anything on the VPS is activated; decide whether the four orphaned sub-workflows are retired, which first needs checking whether V5 calls them; bring Cloud's webhook hardening across before TQO FINAL V5 is ever activated on the VPS
STATUS: migration verified and found complete as of its snapshot dates; two missing data tables created and schema verified, both empty; two workflows archived on Tee's rulings; one security finding raised with both instances measured and its blast radius graded as zero while inactive; two same session errors recorded rather than quietly fixed; five items remain open, three of them rulings only Tee can make
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
