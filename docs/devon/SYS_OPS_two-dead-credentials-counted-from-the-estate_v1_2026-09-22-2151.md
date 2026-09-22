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
`onError: continueRegularOutput`. `Mark Superseded` then wrote into Airtable a
Notes string that `Find Duplicates` composed BEFORE the move was attempted,
ending "Moved to _To Delete on <date>", and set `Triaged: true` whatever came
back.

`TQO FINAL V5`. `Repurpose: Drop Caption File` and `Repurpose: Drop Video` both
swallow. `Repurpose: Mark Handed Off` then PATCHed the Airtable slot to
`Status: Ready`, stamped `Posted At`, and wrote a note saying the file was
dropped in the Repurpose folder and that "if nothing appears, the workflow on
their side is not pointed at this folder". It recorded a handoff that did not
happen and pointed at a downstream lane for it.

## The blast radius was zero, and the first version of this doc said otherwise

The paragraphs above first read "every duplicate it touched since the credential
died reads as filed and closed". That was taken from the code and never from the
data, which is the first law's own failure mode inside the doc whose subject is
that failure.

Measured the same evening. `Inbox Captures` (tbl4ziFRbl5mnUcKc) holds 13 rows,
all of them read: none carries a "Moved to _To Delete" note, none is Triaged,
and exactly one has a `Filename` populated at all, so `Find Duplicates` cannot
form a pair. `Publishing Slots` (tblQgQ3JdpoKOANXh) holds zero rows. Neither
lane has ever written a false record.

The defect is real and would have landed on the first matching row. It had not
landed. Over-calling a finding spends Tee's attention and is its own error, so
the correction is recorded here rather than quietly edited out.

## The repair, and why the two lanes recover differently

Ruled by Tee 2026-09-22 from a card: fix the code first, leave the records.

`Confirm Move` on the Duplicate Sweep and `Confirm Drop` on the TQO repurpose
lane both read the Drive file id back and compose the note honestly in both
directions. A failure is named, the file is named, and nothing claims a move
that did not happen. On the repurpose lane the failure PATCH carries the `Notes`
field ONLY: `Status` and `Posted At` are left exactly as they were, and no new
`Status` option is invented, because `typecast` is on in that request and an
unknown option name would silently add one to Tee's base. An error path does not
get to make a schema change.

Nineteen fixture cases run in node against both bodies before either was
published: the success shape, a dead credential, a 200 carrying no file id, and
an error object with no message. Both published and read back;
`activeVersionId` equals `versionId` on each.

They recover differently and that is worth knowing before trusting either.
`Find Duplicates` reads every capture row with no `Triaged` filter, so the sweep
re-detects the same duplicate and rewrites its own note on the next run.
`Repurpose: Due Slots` selects on `{Status}='Pending'`, so a slot flipped to
`Ready` is never selected again and would have been stranded permanently.

## Another session was editing TQO FINAL V5 at the same time

Two versions landed on `qEkGOUsNyVaRAmm6` between the read at 21:45Z and the
write at 22:04Z, both authored via MCP: `0bd1a2f5` at 21:55:23Z rebuilding the
packaging lane so the model ranks and Tee picks, and `f78ebf25` at 21:56:16Z, a
comment. The node count moved 250 to 251 under the read, which is how it was
noticed.

Nothing was published on that basis alone. The diff `27e53292..f78ebf25` was
read first and touches only the Idea and Packaging lane: `Package: Plan Batch`,
`Package: Write Options`, `Package: Context` and neighbours. Not one of the
three Repurpose nodes appears in it. The draft was then published by explicit
`versionId` and the diff `f78ebf25..9d00e60f` read back to confirm it adds one
node, modifies one `jsonBody`, rewires three connections and touches nothing
else.

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
DECISIONS: Tee ruled "Find what else depends on it first" for the dead Google Drive credential, "Leave it as a floor" for the SMTP count, and on a second card "Fix the code first, leave the records" for the two false-write paths. The sweep required opening every node anyway, so the real SMTP count was produced and both written numbers were corrected rather than left wrong.
FINDINGS: Google Drive NW3vR6nNcMoUkJyJ feeds 18 nodes across 6 workflows; two of them swallowed the failure and would then have written a false record into Airtable, though measurement of both tables shows neither ever did. SMTP AgSGuaA2pnZsrZcJ carries every emailSend in the estate, 20 nodes across 16 workflows, including the compliance lane and the only backup. The TQO Drive damage is armed but not yet realised because the Cerebras outage stopped the pipeline upstream. The pre-compaction record was wrong about the Precedence Guard's node name and error mode, and overstated the iPhone capture blast radius.
OPEN: Both credentials remain dead and both fixes are Tee's. Another session is editing TQO FINAL V5 concurrently; its packaging-lane work and this repurpose-lane fix do not overlap, but a third change should read the version history first.
STATUS: Sweep complete, 45 of 45 active workflows read and verified. Both false-write paths repaired, published and read back. Corrections landed in CLAUDE.md, in the live sticky note, and in this doc's own over-called blast radius.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
