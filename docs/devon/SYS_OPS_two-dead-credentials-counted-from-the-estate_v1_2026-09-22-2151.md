# Two dead credentials, counted from the estate

Ruled by Tee on 2026-09-22: "Find what else depends on it first." This is the
answer. Every active workflow on n8n.editforge.online was read and the
credential id on every node was checked. Not the workflows a session could name.
All 45.

## What was counted, and how

`search_workflows` returns 65 workflows, 45 of them active. Each of the 45 was
opened and every node's `credentials` block read. The read list was diffed
against the active list programmatically rather than tallied by hand, because a
hand tally is the failure this file exists to stop. Zero gap in both directions.

The 28 that had been read earlier in the same session, before a context
compaction, were read again rather than carried forward. That paid for itself
twice, recorded under "What the re-read corrected" below.

## Google Drive, credential `NW3vR6nNcMoUkJyJ`

Dead between 2026-09-20T14:00:57Z and 2026-09-21T11:00:55Z, bracketed by the
last clean `_To Delete Auto-Purge` read. EIGHTEEN nodes across SIX workflows.

| workflow | nodes | on failure |
|---|---|---|
| `TQO FINAL V5` | 9 | 3 throw, 6 swallow |
| `DEVON - Drive Draft Writer (Build 16)` | 3 | swallow, then refuse with a named reason |
| `DEVON - iPhone Inbox Capture` | 2 | both throw |
| `DEVON - _To Delete Auto-Purge (30d)` | 2 | the read throws, so nothing is purged |
| `DEVON Precedence Guard` | 1 | swallows, composes an honest BLIND alarm |
| `DEVON - Duplicate Sweep` | 1 | swallows, then writes a false record |

A node that throws is the safe case: the run dies and nothing is claimed. The
expensive cases are the two that swallow and then write.

`DEVON - Duplicate Sweep`. `Move to _To Delete` carries
`onError: continueRegularOutput`. `Mark Superseded` then writes into Airtable a
Notes string that `Find Duplicates` composed BEFORE the move was attempted,
ending "Moved to _To Delete on <date>", and sets `Triaged: true`. Every
duplicate it touched since the credential died reads as filed and closed. None
of them moved.

`TQO FINAL V5`. `Repurpose: Drop Caption File` and `Repurpose: Drop Video` both
swallow. `Repurpose: Mark Handed Off` then PATCHes the Airtable slot to
`Status: Ready`, stamps `Posted At`, and writes a note saying the file was
dropped in the Repurpose folder and that "if nothing appears, the workflow on
their side is not pointed at this folder". It records a handoff that did not
happen and points at a downstream lane for it.

Graded honestly, because over-calling a finding is its own error. Those nine
`TQO FINAL V5` nodes have NOT fired since the credential died. Every failed
execution from 2026-09-19 onward is the Cerebras 402 at `Write Script` or
`Write Brief`; execution 614 was read back with `includeData` to confirm it,
and the runs that succeed exit in under a second, which is a schedule trigger
finding no work. The provider outage stopped the pipeline upstream of every
Drive node in it. That damage is armed, not done, and it lands the day a model
provider answers again.

`DEVON - iPhone Inbox Capture` is narrower than it first reads. `File into
Drive` and `Write Note to Drive` sit on separate branches: a capture carrying a
file throws, an iPhone Notes capture throws, and a plain typed note or shared
link with no file bypasses both and still reaches Airtable.

The whole TSWS block, all six workflows, carries no Drive credential at all. It
works through the render worker on the VPS filesystem.

Second order: the Action Router allowlist routes `drive.draft` to the Drive
Draft Writer, and the Face's system prompt names that executor as the one chosen
when a job "reads like a draft, outline, script, memo, brief or checklist". It
refuses cleanly, and `saveDataSuccessExecution: none` means those refusals leave
no execution to read.

## SMTP, credential `AgSGuaA2pnZsrZcJ`

SIXTEEN workflows, TWENTY `emailSend` nodes, every one of them on this
credential. Not one `emailSend` in the estate sits on a different credential, so
one dead password takes the whole alerting channel.

Heartbeat `Send Pulse`; `DEVON - Error Alarm` `Alert Tee`; `DEVON Pipeline
Watchdog` `Send Watchdog Alert`; `OS - Error Handler` `Send Email Alert`;
`DEVON Capture Nudge` `Send Capture Nudge`; `DEVON Precedence Guard` `Send
Precedence Alert`; `Monthly Credential Review` `Email the Review`;
`_To Delete Auto-Purge` `Email the Summary`; `Weekly Table Backup` `Send Backup
Email`; `Ledger Janitor` `Send Janitor Digest`; `Approval Queue` `Email Tee`;
`Soul Layer Write-Back` `Notify`; `Ledger Feeder` `Notify` and `Notify Marks`;
`Driver Poll` `Send Digest`; `Soul Committer` `Notify Propose Failures`,
`Notify Commits` and `Notify Closed`; `OS 29 - Platform Policy Sensor`
`Notify: Change` and `Notify: Silencing`.

Three of those cost more than a missed digest.

`OS 29 - Platform Policy Sensor` scans platform policy pages daily. Platform
policy is a compliance item with no exception path under Tee's standing rules,
and email is its only channel.

`DEVON - Weekly Table Backup` has no sink but email. It reads four tables,
builds four CSVs, and attaches them to a message that cannot leave. There has
been no backup since 2026-09-20.

`DEVON Approval Queue` is the 2026-09-01 failure repeating. Its own sticky note
records that when the Gmail credential died, `Store Pending` ran before `Email
Tee` and for nine days every card was written pending with links that never
arrived; REQ-20260905-f5kEZj expired undecided and its job cancelled. Checked
this time: the queue holds three rows, newest 2026-09-16, all approved. Nothing
has raised a card since the credential died, so nothing has been lost yet.

One channel survives. `Log to Maintenance` on `OS - Error Handler` writes every
fault into Airtable and swallows its own errors, so the Maintenance Logs table
has recorded faults through the whole outage.

`DEVON - Monthly Credential Review` would not have caught either death. It reads
an Airtable registry of rotation dates a human typed, not the live n8n
credential store, so a credential that dies between rotations is invisible to
it.

## What the re-read corrected

Two entries in the pre-compaction record were wrong, and only re-reading the
live workflow found them.

`DEVON Precedence Guard` was recorded as failing loud at a node called `Find
Duplicates`. The Drive call is `List Devon Core`, an `httpRequest` node using
the `googleDriveOAuth2Api` predefined credential type, and it carries
`onError: continueRegularOutput`. `Find Duplicates` is the Code node downstream
that reads the failure and composes the BLIND alarm. The guard degrades by
design and writes an honest message; the message is what dies.

That also means a grep for node type `googleDrive` misses this workflow
entirely. The credential id is the only reliable key.

`DEVON - iPhone Inbox Capture` was recorded as "every phone capture fails
outright". Two of three branches fail; the plain text branch does not.

## Counts that were wrong in writing, now corrected

`CLAUDE.md` said FOUR alerting lanes, then AT LEAST SIX. The sticky note added
to `OS - Error Handler` this morning said FOUR. Both were read from the lane
rather than the estate, which is the exact miss the first law tabulates. Both
are corrected to SIXTEEN workflows across TWENTY nodes, with the enumeration
method named so the next session re-runs it rather than adjusting it from an
error list.

The sticky note edit was applied and published; `activeVersionId` reads
`9189415a-2c14-4834-9858-eb1983849f0e` and equals `versionId`.

## Open

Both credentials are still dead. Tee holds both actions: a new Gmail app
password into `AgSGuaA2pnZsrZcJ`, and a reconnect of the Google Drive account
`NW3vR6nNcMoUkJyJ`. This session never handles either secret.

Unresolved and not attempted here: whether the false Airtable records the
Duplicate Sweep and the TQO repurpose lane have already written should be
reverted, and how. That is a data question with a blast radius, so it is Tee's
ruling rather than a cleanup to run.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_two-dead-credentials-counted-from-the-estate_v1_2026-09-22-2151.md
DATE: 2026-09-22
DECISIONS: Tee ruled "Find what else depends on it first" for the dead Google Drive credential, and "Leave it as a floor" for the SMTP count. The sweep required opening every node anyway, so the real SMTP count was produced and both written numbers were corrected rather than left wrong.
FINDINGS: Google Drive NW3vR6nNcMoUkJyJ feeds 18 nodes across 6 workflows; two of them swallow the failure and then write a false record into Airtable. SMTP AgSGuaA2pnZsrZcJ carries every emailSend in the estate, 20 nodes across 16 workflows, including the compliance lane and the only backup. The TQO Drive damage is armed but not yet realised because the Cerebras outage stopped the pipeline upstream. The pre-compaction record was wrong about the Precedence Guard's node name and error mode, and overstated the iPhone capture blast radius.
OPEN: Both credentials remain dead and both fixes are Tee's. Whether to revert the false Airtable records is an unruled data question.
STATUS: Sweep complete, 45 of 45 active workflows read and verified. Corrections landed in CLAUDE.md and in the live sticky note.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
