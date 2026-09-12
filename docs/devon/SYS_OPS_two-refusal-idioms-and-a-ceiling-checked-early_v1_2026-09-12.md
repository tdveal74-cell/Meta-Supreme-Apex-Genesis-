# Two refusal idioms, and a ceiling checked early

Closes the 2026-09-12 evening arc. Four things happened, and only the first was
planned: a credential audit that came back clean, an alarm coverage fix that
would have been wrong if applied the obvious way, the Build 14 approval to
action path proved end to end on its third attempt, and a guard added so the
second attempt's failure cannot recur silently.

## The audit that came back clean

The Gmail OAuth credential `vsTKuAilHmpYCc5L` went invalid on its own around
2026-09-05 and took every lane that emails down with it for nine days. The
records said the conversion to SMTP `mu7nJRSpkAfkzLdF` had been done for the
Heartbeat and the Error Alarm, and warned that other workflows still carried
the dead credential and were each a silent failure until moved.

All 49 workflows on the instance were read in full, not sampled. The dead
credential is referenced by ZERO nodes. All thirteen mail nodes across the
eleven workflows that email run on SMTP. The credential is orphaned in the
store, along with ten others.

Proved from the destination rather than from the wiring, which is the only
honest direction: the Pulse mailed successfully on 8, 9, 10 and 11 September,
and a Build 14 approval card landed in the inbox at 20:52:00Z on the 12th. The
last production error anywhere on the instance since 05 September was execution
6243, the feeder, on 06 September at 12:40Z.

## The fix that would have been wrong

The runbook claimed only the committer named an error workflow, and that a
crashed feeder or queue alerted nobody. The obvious repair was to point the
unalarmed organs at the shared DEVON Error Alarm `XDQXwgFkUhYxoEjG`.

That would have been a mistake, and it was caught before it was made. The
organs split into two kinds by how they refuse:

- Build 14 to 17 organs return a refusal as DATA, `{refused: true, reason}`,
  and never throw for one. Any crash they report is a real crash, so they can
  safely name the plain alarm.
- Build 01 to 07 organs refuse by THROWING a message that begins with the
  literal prefix `REFUSED:`. Bad schema version, non-ULID id, illegal
  transition, wrong state, blast radius over an executor's ceiling, event type
  outside the fourteen. Every one of those is designed behaviour.

Pointing a throw-to-refuse organ at the plain alarm would email on every legal
refusal, which is precisely how the alert that matters gets buried. So the OS
Error Handler `rqYmaQh91iCce8DJ` was taught the prefix first, as a generic rule
matching only on a trimmed message starting with `REFUSED:`, so a genuine fault
that merely mentions the word is still a fault. Then thirteen workflows were
wired to it.

The two handlers are not interchangeable and the runbook now says so.

## A draft of my own, unpublished for three days

While auditing something else, the DEVON Approval Queue `syRVj0G47mA1b0Xn` was
found carrying an unpublished draft. The retry hardening on its Email Tee node,
approved on 09 September, had never been published and had sat as a draft for
three days. The diff was verified as exactly two modifications, the retry
settings and two sticky note paragraphs, and then published.

It was found by accident. That is the finding, not the fix.

## Build 14, proved on the third attempt

Job `01M2BP853KS5PN4D2CK7PQ8234`, ledger row 20. Filed 20:51:53Z, COMPLETED
21:13:10Z, `human_watched` true, one artifact, 23 trace entries.

The two earlier attempts failed differently. The 05 September card never reached
Tee, because the Approval Queue was still on the dead Gmail credential. The 09
September card he did approve, and the job then refused at the router: it
carried no payload, so the driver bound `spine.echo`, whose ceiling is read,
while the job itself declared `reversible_write`. The grant decayed unspent 24
hours later.

The third attempt carried a structural Airtable payload so the driver would bind
`airtable.row` at exactly the declared radius. `airtable.row` was chosen over
`drive.draft` deliberately: the draft writer runs through Cerebras with a word
floor and a hard long-dash refusal that has already quarantined two versions,
and for a proof the executor should be the only variable.

Airtable record `recQeZBU2TxKy0OPM` was confirmed to exist independently of the
envelope's claim, carrying both executor-owned stamps.

## The guard that makes the second failure loud

The driver already re-derived the bound action at action time and refused a
mismatch. Nothing caught a job that could never have run at all.

A pre-card ceiling guard now sits at WAITING_APPROVAL in the Job Driver's
`Decide` node. Before any card is raised it compares the executor it would bind
against the declared blast radius, and cancels the job with a receipt rather
than asking for a grant the router would refuse. `spine.echo` reads;
`drive.draft` and `airtable.row` write reversibly.

Two decisions inside it are worth naming, because both could have been got
wrong quietly.

`irreversible_write` is EXEMPT. No executor carries that radius, so a plain rank
comparison would have cancelled every such job before Tee ever saw it, silently
repealing the 2026-08-24 interim routing ruling that sends them to the approval
queue for a human decision. A job above every ceiling is Tee's call.

The ceiling table is DUPLICATED from the Action Router, which stays the
authority and still refuses at dispatch. The alternative was duplicating
`selectAction()` into a separate node, a worse copy of a more volatile rule.
This is a standing drift hazard: change a ceiling in the router and it must
change in the driver in the same edit. The code comment and the canvas sticky
note both say so.

## What was checked, and how

The guard was run against the real patched node code in a harness before it went
near the estate. Seven binding cases: the 09 September shape cancels, the
Airtable proof job still gets its card, `none`, `read`, draft-word and unknown
radius jobs all pass through untouched. Three further cases proved it can never
fire on a job that already has a card out, which would have been the destructive
bug.

After applying, the node was read back off the instance and compared by SHA-256
against the tested file: `c340de3e6677f5f23e868610c64d404339700ec4e2e9c489338f24dbc8968a16`,
27,981 characters, byte identical. A 28KB hand transcription into a live organ is
not something to check by eye.

Then published, and `versionId` confirmed equal to `activeVersionId`. Twice,
because leaving an unpublished draft was already this session's own mistake.

Proved live on ledger row 21, filed 21:22:36Z and cancelled 21:22:42Z. The
evidence is what is ABSENT from its twelve trace entries: no APPROVAL_REQUESTED.
No card, no email, no grant.

## A contradiction introduced and corrected

The commit that rewrote the runbook's coverage row to say the whole lane is
alarmed did not notice that `heartbeat.md` still carried the opposite claim
about the feeder in a parenthetical. Two files in the same skill then told a
reader different things about the same workflow, and the stale one was the more
specific, so it would have won.

Checked against the live instance rather than from memory: workflow
`6hQD8YhiYzR1FFda` carries `errorWorkflow: XDQXwgFkUhYxoEjG` and has since its
07 September update. Corrected without dropping why the finding exists, since a
crash alarm and `feeder_silent` see different failures and neither covers the
other.

Like the unpublished draft, this was found by a second look rather than by any
process. Both are the same shape of miss.

## What is proved and what is not

Proved: the credential count, from all 49 workflows. The SMTP lane, from the
destination. Build 14 end to end, from the ledger and from Airtable
independently. The guard, from ten harness cases, a hash comparison, and one
live cancellation. The Vercel account block cleared, from deployment records
created, previews reaching READY, and commit statuses going green, three
independent signals rather than one.

Not proved: nothing has exercised the guard against `drive.draft` or
`airtable.row` at a radius above their ceiling, because only `irreversible_write`
sits above them and that case is exempt by design; the guard's behaviour there
is reasoned, not measured. The ceiling table's agreement with the Action
Router's was read once and is not enforced by anything. The learning lane has
still never carried a genuine PROMOTE.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_two-refusal-idioms-and-a-ceiling-checked-early_v1_2026-09-12
DATE: 2026-09-12
DECISIONS: Tee ordered the credential audit, then approved the four remediation items and the Build 14 proof together; he approved the Build 14 execution card REQ-20260912-JrCSGb at 20:55:39Z and the verification card REQ-20260912-bf6nrD at 21:11:18Z; he authorised the pre-card ceiling guard on the Job Driver after being told it was a live edit to a load bearing organ, and authorised the merge of PR 211. Inside that authority the session ruled: teach the OS Error Handler the generic REFUSED: prefix BEFORE wiring any throw-to-refuse organ to it, rather than pointing the unalarmed organs at the plain alarm; exempt irreversible_write from the ceiling guard so the 2026-08-24 interim routing ruling still reaches a human; duplicate the ceiling table from the Action Router rather than duplicate selectAction(), accepting a named drift hazard over a worse copy of a more volatile rule; cancel rather than park a job whose executor cannot carry its radius, since the end state is identical and cancelling reaches it without spending Tee's attention; choose airtable.row over drive.draft for the proof so the executor was the only variable; verify the 28KB node transcription by SHA-256 read-back rather than by eye.
FINDINGS: the Gmail OAuth credential vsTKuAilHmpYCc5L is referenced by ZERO nodes across all 49 workflows, read in full rather than sampled, so the 2026-09-05 SMTP conversion was complete and the earlier warning that other workflows still carried it was false; eleven credentials are orphaned in total. The DEVON organs use two incompatible refusal idioms, Build 14 to 17 returning refusals as data and Build 01 to 07 throwing a message prefixed REFUSED:, and wiring the second kind to the plain DEVON Error Alarm would have emailed Tee on every legal refusal; the OS Error Handler rqYmaQh91iCce8DJ was taught the prefix first and thirteen workflows were then wired to it. The DEVON Approval Queue syRVj0G47mA1b0Xn was carrying an unpublished draft of a retry fix Tee approved on 2026-09-09, which had sat unapplied for three days and was found only incidentally while auditing something else. The DEVON Capture Webhook pPIt2cELH2RVZktS stored the raw request body, including a poster's plaintext capture token line, on any FAILED run, because success persistence was off and error persistence defaulted to all; closed. Build 14 completed end to end for the first time, job 01M2BP853KS5PN4D2CK7PQ8234, ledger row 20, Airtable record recQeZBU2TxKy0OPM confirmed present independently of the envelope. A doc correction in this same session introduced a contradiction between runbook.md and heartbeat.md about whether the Build 12 Ledger Feeder is alarmed; the live workflow 6hQD8YhiYzR1FFda has carried errorWorkflow XDQXwgFkUhYxoEjG since 2026-09-07, so heartbeat.md was the stale one, corrected. A diagnosis is withdrawn: when the verification card read pending to the driver at 21:11:01Z the session ranked "only one tap of two was made" as the likeliest cause, and the decision in fact recorded at 21:11:18.351Z, seventeen seconds later; the poll was early, the card and queue were correct throughout. The Vercel account block cleared at some point between 08:34:32Z and 21:04:05Z, established by deployment records being created again rather than by any status turning green. CodeRabbit declines to review on two INDEPENDENT gates, not one, and the session first recorded only the second: on a draft it reports that draft PRs are not auto-reviewed by default (PR 214), and once a PR is marked ready it reports that this repository receives no automatic reviews because it has fewer than ten stars (PR 211). So the "Review skipped: draft pull request" commit status is the first gate rather than the whole story, and on the evidence of those two PRs no automated reviewer reads these diffs even after a PR leaves draft. A manual trigger is offered on each PR and was not used. Two observations are not a rule, so treat this as the current behaviour rather than a settled fact.
OPEN: TSWS 00 o4ctniOsIq2VSfgm still carries the literal RENDER-WORKER-URL-HERE in Submit Job and Poll Job and all five TSWS pipelines route through it, blocked on Tee for the worker host; the ceiling table in the Job Driver Decide node mirrors the Action Router's and nothing enforces their agreement, so a ceiling changed in one and not the other is a silent wrong refusal; the guard's behaviour against drive.draft and airtable.row above their ceiling is reasoned rather than measured, since only irreversible_write sits above them and it is exempt; the four per-poster capture tokens remain in the Capture Webhook's Check Token code node and cannot be moved to credentials by id, because n8n code nodes cannot read credentials, so per-poster header auth credentials or a lookup table is a design decision for Tee; the learning lane has never carried a genuine PROMOTE, repo task 15; the reflection to intent loop, repo task 19, is not built; the DEVON thread log receipt that normally accompanies a close-out doc is NOT filed for this arc.
STATUS: PR 211 merged as d7619164489f22a426d89bcd3b461188c38ff8f1, six checks green, verified on main by reading the corrected line back off origin/main rather than from the merge API. The Job Driver TT4TfFXyH9O7lfdc is published at activeVersionId d4c96f1f-71d4-456f-89eb-0458cf5b2136 with the pre-card ceiling guard live and its canvas sticky note updated to match. The OS Error Handler rqYmaQh91iCce8DJ is published at ac9c58c9-4838-4f3a-ac4e-73cf01617181 carrying the generic REFUSED: rule, with thirteen workflows naming it. The whole lane is alarmed. The state ledger holds zero non-terminal jobs. Both Vercel production surfaces are correct at a commit behind main, confirmed by running each project's own ignoreCommand comparison by hand over its own paths after main advanced through PRs 211, 212 and 213; both empty, nothing owed. The designated branch has been restarted from the merged main.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
