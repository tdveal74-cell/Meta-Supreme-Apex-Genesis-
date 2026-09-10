# SYS_OPS: the n8n Cloud to VPS migration, verified

2026-09-10. Tee asked whether the migration from n8n Cloud to the VPS at
`n8n.editforge.online` actually carried everything across. It did, as of the
dates it was taken, and the webhook hardening came across with it.

This document was first written around a security finding that turned out to be
false. It is withdrawn below, along with the method that produced it, because
the method is the part worth keeping: a summary field was read for something it
does not report, and its silence was taken as evidence.

## The two instances

| | Cloud | VPS |
|---|---|---|
| host | `thequietoperator.app.n8n.cloud` | `n8n.editforge.online` |
| project | `rM0TNTE2fNXErglU` | `qbrcjkbIoorbwot6` |
| workflows | 49 | 58 |
| active | 42 | 0 at 06:30, 1 by 11:25 (see below) |
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

## WITHDRAWN: the claim that the VPS TQO pipeline predates Cloud's hardening

This section originally carried the headline finding of this document: that
`TQO FINAL V5` on the VPS had lost the webhook hardening Cloud received between
2026-08-31 and 2026-09-08, leaving seven endpoints unauthenticated on bare
paths. **It is false.** Withdrawn 2026-09-10, recorded rather than deleted,
because the way it was reached is the useful part.

Read from V5's actual node graph on the VPS, the configuration is identical to
Cloud's:

| node | method | path | authentication |
|---|---|---|---|
| Run All (Webhook) | POST | `run-tqo-pipeline` | `headerAuth`, Devon Capture Key |
| SYSTEM PAUSE | GET | `system-pause` | `headerAuth`, Devon Capture Key |
| SYSTEM RESUME | GET | `system-resume` | `headerAuth`, Devon Capture Key |
| Run All (Webhook NCO) | POST | `run-nco-pipeline` | `headerAuth`, Devon Capture Key |
| Gumroad Ping (Sale) | POST | `gumroad-sale-<16 hex>` | none, suffix is the guard |
| Run TQO (Link) | GET | `run-tqo-<16 hex>` | none, suffix is the guard |
| Run NCO (Link) | GET | `run-nco-<16 hex>` | none, suffix is the guard |

Four header authenticated, three on unguessable paths, the same suffixes as
Cloud. The hex values are deliberately not written into this document. They are
the guard on those three endpoints, and a git repository is not where a guard
belongs.

### How the false finding was reached

The measurement came from the `triggerInfo` summary returned by
`get_workflow_details`, which reported "No credentials required for this
webhook" for all seven, and reported the three suffixed paths as bare
`/webhook/gumroad-sale`, `/webhook/run-tqo` and `/webhook/run-nco`.

On this VPS, `triggerInfo` does not report a webhook's authentication or its
full path for a workflow with no published version. Every VPS workflow carries
`activeVersionId: null`; every Cloud workflow carries a populated one. The
summary was read as authoritative on both.

A positive control was claimed and it was not a control. Cloud printed
`Credentials: - This webhook requires a header with name "x-devon-key"`, and
that was taken as proof the field reports reliably. Cloud is published and the
VPS is not, so the two were never comparable. The `activeVersionId` difference
was observed earlier the same day and not connected to it.

The instrument was proved wrong by accident. Header auth was written onto a VPS
webhook node to "fix" it, the write reported two operations applied, and
`triggerInfo` still said no credentials were required. Reading the node graph
then showed the parameter had been set correctly, and had already been set
before the write. The version history confirmed it: the write created no new
version, because it changed nothing.

The lesson is narrower than "verify", which was done. An instrument was used
without first establishing that it could report a positive on the same class of
object being measured. A negative from an instrument that cannot report a
positive is not evidence of absence.

Two claims made downstream of this one are withdrawn with it:

- That the eight rebuilt DEVON workflows dropped `x-devon-key` on their four
  webhooks. They did not. `authentication: headerAuth` and the Devon Capture
  Key are present on all four, set at build time.
- That the agent which built them reported a security control as verified when
  it was absent. It did not. Its claim was accurate, and the accusation is
  withdrawn in full. The further inference, that its other verification claims
  should be treated as unreliable, collapses with its premise and is withdrawn
  too.

### One thing this pass did establish

`OS - Error Handler (all pipelines)` (`GbeNilHQzjmoWDz3`) is **active and
published on the VPS**. It read `active: false` at 06:30 and `active: true` at
11:25, with `updatedAt` unmoved from 2026-08-31, so activation does not bump
that field. It was activated during the 08:22 to 08:53 build window and not
reported. The statement elsewhere in this document that the VPS runs zero
active workflows was true when written and is no longer true.

`DEVON - Error Alarm` (`bqcnIS0Qv4RkTCU1`) has no published version, so n8n
refuses to accept it as an error workflow until it is published. That is why
the six Build 14 to 17 workflows still point at OS Error Handler rather than
the DEVON Error Alarm their Cloud originals use.

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

Nothing was activated by this pass. The VPS was at 0 active workflows when this
was written at 06:30. By 11:25 `OS - Error Handler (all pipelines)` read active,
having been activated during the 08:22 to 08:53 build window by the agent that
rebuilt the eight DEVON workflows, and not reported. Everything else on the box
remains inactive and unpublished.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_n8n-cloud-to-vps-migration-verified_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ruled that TQO FINAL V8 was created in error by an agent and that TQO FINAL V5 is the real TQO pipeline, reversing a same day recommendation that had favoured V8 on credential wiring; Tee ruled TQO ORCHESTRATOR could be deleted, and it was archived rather than hard deleted under the estate's existing never hard delete doctrine; Tee confirmed the 2026-09-10 06:14 bulk edit was him enabling availableInMCP and not development work; no ruling yet taken on which instance owns the schedules, on the four orphaned sub-workflows, or on rebinding V5's credentials
FINDINGS: the headline finding of the first version of this document, that the VPS copy of TQO FINAL V5 had lost Cloud's webhook hardening, is FALSE and is withdrawn in place rather than deleted; read from the node graph the VPS carries the identical configuration, four webhooks on headerAuth with the Devon Capture Key and three on the same unguessable path suffixes, and two downstream claims are withdrawn with it, that the eight rebuilt DEVON workflows dropped x-devon-key and that the agent which built them falsely reported a security control as verified, neither of which is true; the cause was reading the triggerInfo summary, which on this VPS reports neither a webhook's authentication nor its full path for a workflow with no published version, and treating a published Cloud workflow as a positive control for an unpublished VPS one; OS Error Handler was activated on the VPS during the 08:22 to 08:53 build window without being reported, so the zero active claim in this document was true at 06:30 and false by 11:25; DEVON Error Alarm has no published version, so n8n refuses it as an error workflow, which is why six workflows still point at OS Error Handler rather than the handler their Cloud originals use; the migration itself is complete as of its snapshot dates, 41 of 49 workflows and 9 of 11 data tables with 0 column mismatches across 206 columns and rows intact, every absentee having been created on Cloud after the snapshot that produced the export; the import carried Cloud workflow IDs into errorWorkflow settings on at least two workflows and those IDs resolve to nothing on the VPS, so error routing is silently broken; two errors were made and corrected inside the session, reading a bulk availableInMCP flip as live development and archiving TQO FINAL V8 before checking that archiving makes a workflow unreadable
OPEN: copy rows into the two newly created data tables and import the 8 workflows Cloud has that the VPS does not, both of which need a Cloud read; rebind TQO FINAL V5's credentials on the VPS using the recovered map, which means rewriting a 220 node workflow; decide which instance owns the schedules before anything on the VPS is activated; decide whether the four orphaned sub-workflows are retired, which first needs checking whether V5 calls them; bring Cloud's webhook hardening across before TQO FINAL V5 is ever activated on the VPS
STATUS: migration verified and found complete as of its snapshot dates; two missing data tables created and schema verified, both empty; two workflows archived on Tee's rulings; one security finding raised with both instances measured and its blast radius graded as zero while inactive; two same session errors recorded rather than quietly fixed; five items remain open, three of them rulings only Tee can make
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
