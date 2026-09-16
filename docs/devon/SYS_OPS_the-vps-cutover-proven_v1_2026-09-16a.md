# The VPS cutover, proven end to end

2026-09-16. Closes the last open item from
`SYS_OPS_the-vps-cutover-executed_v1_2026-09-15.md`, which recorded that no real
job had been driven through the intake, a card, an executor and the verification
card since the switch. One now has. It also records a live failure found while
watching for it, in a workflow outside the cutover.

## The job

Filed at 00:36:07Z from a throwaway workflow, since archived, posting a well
formed envelope to `https://n8n.editforge.online/webhook/devon-intake` with the
Devon Capture Key. It carried an `airtable.row` payload for the Inbox Captures
table and the idempotency key `vps-cutover-proof-20260916`. The envelope was
built from the Intake Former's own contract and the Airtable Row Writer's
allowlist, both read off the live VPS first, because the 2026-09-15 door proof
used a probe body that threw in six organs and sent Tee seven fault emails at
23:39:32Z.

Everything below is read from the ledger row, `devon_state_ledger`
`QZvdxllOjWevb3Vo` row 9, not from a response body. 22 trace events.

| at | what happened |
|---|---|
| 00:36:08Z | spine adapter took it in RECEIVED |
| 00:36:09Z | RECEIVED to UNDERSTANDING on `VUXIyCaur9lejAhL` |
| 00:36:10Z | runtime recalled 8 prior Systems jobs, 0 open, and planned |
| 00:36:11Z | router raised the stated level 1 to level 2 on the blast radius floor, next state WAITING_APPROVAL |
| 00:36:14Z | card `REQ-20260916-37xZi6` raised, pending |
| 00:57:40Z | Tee approved, `decided_by` tee, grant decays 2026-09-17T00:57:40Z |
| 01:00:41Z | Driver Poll picked it up and the action router dispatched `airtable.row` to `glEO2xa4IZmHDbkg` |
| 01:00:43Z | row written, AUTHORIZED to EXECUTING, executor execution 188 |
| 01:00:44Z | EXECUTING to VERIFYING on the spine |
| 01:00:46Z | verification card `REQ-20260916-J1ApUy` raised, method human_watch |

The artifact is real and the ledger carries its coordinates:
`recoe6wzzAdkKpEnj` in `tbl4ziFRbl5mnUcKc` of base `app28z7XnKzjfTXwc`,
`reused: false`, `key_verified: true`.

The brief on the card came from cerebras gpt-oss-120b and recommended proceed.
The card named its executor, the table, the payload fingerprint 068eeb86 and the
first 182 characters of the body before Tee decided, which is the property that
was quarantined and rebuilt on 2026-09-05 and is the reason a human tap means
anything.

What is still not proven: the verification card is pending and its method is
`human_watch`, so the lane is proven as far as a human watching the artifact and
ruling. Nothing automatic closes it, and nothing should.

## The Driver Poll, twice

The first firing after the switch was execution 153 at 00:00:41Z, mode
`trigger`, 35 milliseconds. It read 8 ledger rows, found 0 open jobs and passed
quietly. A quiet pass sends nothing but still records an execution, which is why
it counts as proof.

The second, execution 181 at 01:00:41Z, ran 7.4 seconds and ended on Send
Digest. That is the one that carried the approved job to the executor. The
difference between 35 milliseconds and 7.4 seconds is the whole lane running.

## Still outstanding

The Heartbeat `EEDrp2jLlw2Ssd5b` reads 0 executions at 01:06Z. Its cadence is
six hours and it has not come round yet. Wall clock, not work.

## A live failure found while watching, outside the cutover

`TQO FINAL V5`, `qEkGOUsNyVaRAmm6`, failed on the VPS at 01:00:00Z, execution
178, and its error workflow (the OS Error Handler `GbeNilHQzjmoWDz3`) ran at the
same second, so Tee has an alert for it. It is not one of the 40 cutover organs
and nothing in this arc touched it.

The node is `Render Lock: Other Brand`, a Data Table row get. It resolves the
table by name through an expression,
`show === 'NCO' ? 'tqo_content' : 'nco_content'`, and filters `status` equals
`Rendering`. n8n refused with "Filter validation failed: Column(s) status do not
exist in the selected table".

What was measured rather than assumed:

- both `tqo_content` (`2GtmrFcTNqVMbddh`) and `nco_content`
  (`DSH1tn4TZjzAEKxp`) on the VPS carry a `status` column, type string. The
  column the error says is missing is present in both candidates.
- the same node on the same branch ran twice and succeeded at 22:00:00Z,
  execution 117, returning an empty object each time.
- the workflow's `updatedAt` is 2026-09-15T19:13:34.443Z, before that success,
  so nothing was edited between the pass and the failure. Same version, same
  node, same inputs, opposite outcomes.

So the failure is intermittent and sits in n8n's own Data Table schema
resolution, not in a wrong column name. That is as far as measurement goes from
here. It is a 240 node workflow carrying the TQO and NCO pipelines, its next
pass is at 04:00Z, and whether it is chased now or left to reproduce is Tee's
call rather than a thing to start editing at one in the morning.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-vps-cutover-proven_v1_2026-09-16a.md
DATE: 2026-09-16
DECISIONS: Tee approved card REQ-20260916-37xZi6 at 00:57:40Z, which is what let the airtable.row executor run and closed the last open item from the cutover close-out. The throwaway filer workflow was archived rather than left in the estate. TQO FINAL V5 was left alone rather than edited, because it is outside the cutover and the failure is intermittent.
FINDINGS: The DEVON lane runs end to end on the VPS. One real job went intake to spine to runtime to router to card to Driver Poll to the airtable.row executor to the spine again to a verification card, 22 trace events in the ledger, artifact recoe6wzzAdkKpEnj written into Inbox Captures with key_verified true and reused false. The Driver Poll fired unattended twice, a 35 millisecond quiet pass at 00:00:41Z and a 7.4 second working pass at 01:00:41Z. The approval card named its executor, table, payload fingerprint and body opening before Tee decided. TQO FINAL V5 (qEkGOUsNyVaRAmm6) failed at 01:00:00Z on a Data Table filter that names a column both candidate tables actually carry, after the same node on the same branch passed twice at 22:00:00Z with the workflow unedited since 19:13:34Z the previous evening, so it is intermittent rather than misconfigured.
OPEN: The verification card REQ-20260916-J1ApUy is pending and its method is human_watch, so the lane is proven only as far as a human ruling on the artifact. The Heartbeat EEDrp2jLlw2Ssd5b has still not fired, 0 executions at 01:06Z on a six hour cadence. TQO FINAL V5 is red on the VPS and unexplained; its next pass is 04:00Z. OS 29 Platform Policy Sensor is recorded active while its VPS copy is inactive, and the five TSWS workflows remain armed on both hosts; both were open before this arc and both are Tee's call.
STATUS: The cutover is proven. Every DEVON organ runs on the VPS, and the lane has now carried one real job from the front door to a verification card with a human grant in the middle.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
