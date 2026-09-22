# The instance I was reading had been retired

2026-09-17. Systems. Closes the arc that began with a question about DEVON's
four open recommendations and ended with the discovery that the session asking
it had been reading a dead copy of the estate for a day.

## What was claimed, and what was true

On 2026-09-16 this session reported an outage:

> The Heartbeat was unpublished, not crashed. Last beat 2026-09-15T22:00:22Z;
> the 04:00 and 10:00 beats on 09-16 never ran. Root cause: an unpublished
> draft. Published, fired, row 90 proves it.

Every observation in that paragraph is accurate about the workflow it names. The
conclusion drawn from them is wrong, because the workflow it names is not the
one that beats.

Tee ruled on 2026-09-15, and the repository records the ruling verbatim in
`docs/devon/vps-cutover-maps_2026-09-15.json`:

> Every DEVON organ runs on the VPS, live and published. Open ledger jobs move,
> terminal ones stay, the approval queue never moves.

The same file maps `dRgTNLod2s8BAcPg` to `EEDrp2jLlw2Ssd5b`. The Cloud Heartbeat
was retired on purpose. The VPS Heartbeat beat at 04:00:15, 10:00:15, 16:00:15
and 22:00:15 on 2026-09-16, four successful executions, no `missed_beat` finding
on any of them. The Pulse never stopped. There was no outage.

The cutover is legible in the data if anybody looks. VPS `devon_heartbeat_log`
rows up to id 88 carry their original `beat_at` values and a `createdAt` of
2026-09-16T03:23:29 to 03:23:32Z: a backfill. The first natively written VPS
beat is 04:00:15Z that morning. Last Cloud beat 22:00:24Z the night before.
A clean cutover, in the window between the two.

## What the wrong diagnosis cost

Three things, and they are worth naming rather than summarising.

1. A workflow Tee had deliberately retired was **republished**, and made active
   again on a six hour schedule.
2. It emailed him a `missed_beat` alarm for a beat that was never missed.
3. It then beat again on its own at 2026-09-16T22:00:24Z, reading a frozen
   estate, so for about ten hours there were two Pulses writing two beat logs
   and mailing the same person contradictory reports.

All three were undone at the start of this session. `dRgTNLod2s8BAcPg` is back
to `active: false`, `activeVersionId: null`, which is exactly the state the
cutover left it in. That is a revert of this session's own change, not a ruling
on precedence: the precedence was ruled by Tee two days earlier and is committed
to this repository.

## The same error, four days apart

On 2026-09-13 DEVON's own reflection recorded this:

> I called TSWS 00 blocked all day against an id that was never the live
> workflow, and never re-read it. I do not know what else I carry that way.

That was the Cloud copy of TSWS 00, reported blocked about eight times while the
live VPS copy had been working since 2026-09-12. It cost nothing, because the
error was caught before anything was written to the wrong copy.

This is the same error with the safety off. Same shape: a Cloud id carried
forward, never re-read against the live instance, and this time **acted on**.
The reflection's closing sentence turned out to be a prediction.

The correction that generalises is not "check TSWS 00" and it is not "check the
Heartbeat". It is that after a cutover, an id is not an address. Both instances
answer. Both return plausible, well formed, internally consistent data. Nothing
in an n8n response says "this copy was retired two days ago", and the retired
copy will happily run a schedule if you publish it. The only thing that
distinguishes them is the ruling, and the ruling is in the repository.

**Read `docs/devon/vps-cutover-maps_2026-09-15.json` before touching any DEVON
workflow by id.** If the id appears in the `workflow_ids` map on the left hand
side, it is a Cloud id and the value beside it is where the work is.

## The four recommendations, re-graded against the live estate

Tee asked what the recommendations were and then said to do all of them. Graded
against the VPS rather than against the retired copy, they came apart:

**Something outside n8n should watch the Pulse.** Genuinely open, and the only
one that survived contact unchanged. `missed_beat` is computed by the Pulse, so
it reports a late beat and never a stopped one, and every organ that could watch
it dies with the instance. Answered by `.github/workflows/pulse-watchdog.yml`
and `scripts/pulse_watchdog.py`, a scheduled GitHub Actions job that reads the
beat log over the n8n public API every three hours and goes red when the newest
`pulse` row is older than the Pulse's own `MISSED_BEAT_H`. The alarm channel is
the job failing and GitHub mailing the owner; there is no SMTP in it on purpose,
because an alerting path with its own credential is one more thing that can rot
quietly, which this estate paid for when the Pulse's Gmail credential died on
1 September and nine days of alerts died at the send.

**Move the reflection to a standalone Routine.** Half done, and the half that
was blocked was blocked by something measurable rather than guessed. The
reflection was writing to the retired Cloud table, which is the whole reason the
live Pulse had been raising `reflection_missing` at 28h and 34h and mailing Tee
about a reflection that was in fact being written. Its Routine is now re-pointed
at the VPS tables and a reflection has been written there and read back. The
standalone half failed a real test: a Routine created through the MCP tool
stores no MCP connectors for this organisation, and the fired session came up
with tool set `Bash, Write, Edit, Read, Glob, Grep, Agent` and no n8n at all. It
went idle in twenty seconds having written nothing, which is what its own
instructions told it to do when the tools are missing. The Routine is left in
place and disabled, carrying the correct prompt, so attaching the connector in
the claude.ai Routines UI and enabling it is the whole remaining step.

**Match `feeder_silent` to the feeder's cadence.** Already done, on 2026-09-16
at 07:53Z, and done better than the fix proposed here. The proposal was to raise
the 40 minute threshold to about 26 hours. What actually shipped splits the one
finding into two that each mean one thing: `feeder_down` when the feeder has
missed its own daily slot by more than a two hour grace, and `feeder_skipped`
when the feeder ran after a COMPLETED job and still did not carry it. Neither
reads a wall clock guess; both read the feed log's own newest `fed_at`. The
threshold bump would have fixed the false positive and left the false negative
untouched, and the false negative is the one the finding was named for: the old
rule could only fire when a COMPLETED job happened to be waiting, so a feeder
that died on a quiet week was invisible to it.

**The lane has decided one PROMOTE and committed nothing.** True, and acting on
it is forbidden in writing. The sole PROMOTE is `SMOKE-COMMITTER-V2-20260825`,
whose own claim text reads "SMOKE TEST from the Build 12 close-out session.
REJECT this card. It proves the live propose path of the rebuilt Soul Committer
end to end; a devon-soul write must never result from it." The soul commit log
carries one row, state REVERTED, with the note "committed 2026-08-25T20:15:36Z
on a mistaken approval; Tee ruled the approval void in session 2026-08-25;
record deleted from devon-soul; terminal, never re-raised". So committing it
would not close a gap. It would repeat a mistake Tee has already had to undo
once. The open work is a genuine PROMOTE arising from real lane traffic, which
is repo task 15, and it cannot be manufactured by pushing this row through.

Two of four were not work. One was already done, better. One was a trap. That
ratio is the argument for grading a finding before acting on it, and it is the
second time in a week this estate has produced that argument.

## What was checked, and how

- The cutover ruling: read from `docs/devon/vps-cutover-maps_2026-09-15.json` on
  `origin/main`, not from memory.
- Both Heartbeats: read live. Cloud `active: false`, `activeVersionId: null`
  after the revert. VPS `active: true`, `activeVersionId`
  `738d6d58-d4db-431e-8cdb-72210faa9c7f`, four successful executions on 09-16.
- The live `Compose Pulse` node was read in full from version `738d6d58`. It
  emits `feeder_down` and `feeder_skipped` and no longer emits `feeder_silent`.
  It was then compared against the repository mirror at
  `n8n/devon/heartbeat/compose_pulse.js` on 21 distinctive markers: all ten
  constants including `MISSED_BEAT_H` at 7.5, all seven finding keys, the
  `feederDown` expression, the future-timestamp guard in `stampOf`, and the
  absence of the retired `feeder_silent` finding from both. Every marker
  matched. That is strong evidence the mirror is current and it is NOT a byte
  for byte comparison, which was not done; a difference outside those 21
  markers would not have been seen.
- The n8n rows API shape used by the watchdog was not guessed. It is taken from
  `scripts/vps_backfill_devon_logs.py`, which measured it against this estate on
  2026-09-16: `limit` and nothing else, capped at 250, no ordering promised, no
  total in the body, no way to page.
- `test_pulse_watchdog.py`: 13 passed, run with `PYTHONPATH`, `DATABASE_URL` and
  `TEST_DATABASE_URL` unset, which is stricter than CI.
- The full standalone job list reproduced locally: 887 passed, 1 skipped, exit
  code read from `$?` rather than through a pipe.
- `python3 -m ruff check .` clean repo wide.
- The reflection row was written to VPS `devon_heartbeat_log` and read back.

## What is NOT proved

True as written, at 0400Z. Two of the three paragraphs below moved later the
same day, and the amendment underneath them carries what changed with the
evidence. They are left standing rather than edited, because a status doc is a
record of a moment and quietly rewriting one destroys the thing it is for.

The watchdog has never reached the live instance. The repository secret
`N8N_VPS_KEY` does not exist, so every scheduled run will exit 2 and go red
until Tee sets it. That is the intended direction rather than a defect, because
a watchdog that skipped quietly when unconfigured would report green while
watching nothing, but it does mean the HTTP path, the key and the host are
unexercised. The unit tests prove the verdict function and say so in their own
text rather than implying more.

The standalone reflection is proved to be blocked, not proved to work. What was
measured is that a Routine created through this tool carries no connectors for
this organisation. Whether attaching one in the Routines UI fixes it is
untested, because only Tee can do that.

Nothing here audits what else in the estate still addresses the retired Cloud
instance. Two cases are now known, TSWS 00 and the Heartbeat, both found by
accident. A deliberate sweep has not been run.

## What changed after this was written

Written at 0400Z on 2026-09-17. By 2100Z the same day three of its open items
had moved, so they are recorded here rather than left to rot in an OPEN block
that reads as current.

**The watchdog now reaches the live instance, on its own schedule.** Tee added
the repository secret. Four runs exist and all four say what they should. Run 1
at 11:16:57Z was dispatched by hand before the secret existed and failed with
exit 2 saying so, which is the direction the design intended rather than a
defect. Run 2 at 11:40:09Z was dispatched after it and reported:

> OK: the Pulse last beat at 2026-09-17T10:00:15.107000Z, 1.7h ago, inside the
> 7.5h threshold. 77 pulse row(s) read.

Runs 3 and 4 at 16:21:01Z and 20:59:10Z were `schedule` events rather than
dispatches, and run 4 read:

> OK: the Pulse last beat at 2026-09-17T16:00:15.448000Z, 5.0h ago, inside the
> 7.5h threshold. 79 pulse row(s) read.

So the three hourly cadence is proven working and not only the manual path, and
the HTTP path, the key and the host are no longer unexercised.

The count moving 77 to 79 across those nine hours is worth one sentence,
because it looks like two scheduled beats and is not. One is the 16:00:15Z
beat. The other is row 97 at 12:30:49Z, the manual Heartbeat execution that
proved the feeder fix earlier the same day. It was checked rather than assumed,
which is the only reason this paragraph does not quietly report a cadence it
never measured.

**PR 261 is merged**, as `e647762` on `main`.

**The connector's name in the OPEN block was wrong.** It read `n8n_vps`. The
account carries an `n8n` connector and an `n8n vps` connector, and the one that
reaches the VPS is the second, with a space in its name. That name was written
from memory rather than read back, which is the first law's failure exactly, in
a doc whose whole subject is that failure. The instruction around it was right:
Tee attaches it in the claude.ai Routines UI, because `create_trigger` refuses
the `connectors` parameter for this organisation, measured twice, once before
the connector existed and once after.

**The standalone reflection is still not proved to work, and the block is now
confirmed rather than assumed.** The Routine is still `enabled: false` with
`mcp_connections: []`. It was fired once as a test with no connector attached
and behaved exactly as its own prompt instructs: the session came up with
`Bash, Write, Edit, Read, Glob, Grep, Agent` and no n8n at all, wrote nothing,
and went idle. Whether attaching the connector clears it remains untested,
because only Tee can attach it.

**That correction was itself wrong, in the other direction.** Read back from
the estate on 2026-09-22 at 2330Z, from the `mcp_connections` array on every one
of the account's seventeen Routines: the connector is stored as `n8n_vps`, with
an underscore, under uuid `b34c21d0-1fc6-40fe-9739-34739e8c469c`. The claim
above that `n8n_vps` is not the name of anything is false. Both spellings are
one connector. The claude.ai Routines form renders it `n8n vps`, with a space,
which is what Tee sees and what his 2026-09-22 screenshot showed; the API stores
the underscored form. The first correction read the UI and then asserted
something about the API it had not read, which is the same failure one layer
down, in the paragraph fixing it.

**The refusal is not a name problem, and that is now settled.** The `connectors`
parameter was passed `["n8n_vps"]`, the provably stored name, on 2026-09-22 at
2328Z, and answered `create_trigger: the connectors parameter is not available
for this organization. Omit the connectors parameter.` That is the fourth
measurement and the first one where a wrong name is excluded as the cause.

**A Routine on this account already carries `n8n_vps`, which the paragraph above
could not say.** `Money and access watch (daily 7:45 AM ET)`,
`trig_01PFGVyQTnAoSRR2GBmfvRbU`, created 2026-09-18T01:29:02Z, holds fifty eight
connectors including `n8n_vps`, `n8n_Knowledge` and `n8n`, and its last run
succeeded at 2026-09-22T11:45:17Z. It was made in the claude.ai Routines form,
whose New routine page attaches every connected connector by default. So the
instruction in the OPEN block is not a hope about a UI nobody had used: the path
is proven on this account, by a Routine that runs.

Two more things the same read settles. Every Routine created through
`create_trigger` carries `mcp_connections: []`, and so does every `send_later`
reminder; the ones that carry connectors were all made in the form. And
`created_via` reads `meta_mcp` on all seventeen, including the ones Tee made
himself, so it does not mean created by a tool call and must not be read that
way. `created_kind` is the field that separates them.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-instance-i-was-reading-had-been-retired_v1_2026-09-17-0400.md
DATE: 2026-09-17
DECISIONS: Reverted this session's republish of the retired Cloud Heartbeat
  dRgTNLod2s8BAcPg, restoring active false and activeVersionId null as the
  2026-09-15 cutover left it. Re-pointed the daily reflection Routine at the VPS
  tables. Built an external Pulse watchdog as a scheduled GitHub Actions job
  rather than as an n8n organ, because an organ on the watched instance dies
  with it. Did NOT commit the single PROMOTE: it is a smoke test marked REJECT
  whose approval Tee already ruled void.
FINDINGS: The 2026-09-16 outage report was wrong. The Pulse never stopped; the
  session was reading the Cloud instance retired by Tee's 2026-09-15 ruling. The
  cost was a retired workflow republished and running, a false missed_beat email
  to Tee, and about ten hours of two Pulses writing two logs. This is the same
  error as the TSWS 00 misread of 2026-09-13, four days later and acted on
  rather than only reported. Of the four open recommendations, one was real, one
  was already shipped better on 2026-09-16, one was half blocked by an
  organisation level limit on Routine connectors, and one would have repeated a
  mistake Tee had already reversed.
OPEN: Tee to build the standalone reflection Routine in the claude.ai Routines
  UI, from the New routine form, keeping the connector the form shows as
  "n8n vps" and the API stores as `n8n_vps`, and to delete the disabled
  `trig_017G3E46NB3VbL7i3swaxp2R` once the new one is proved. The Edit form
  carries no connector section, so an existing Routine cannot be repaired that
  way, and `create_trigger` refuses the parameter for this organisation. Until
  then the reflection still depends on one build session being awake. This line
  said n8n_vps until 2026-09-17 at 2110Z, then said that spelling was not the
  name of anything until 2026-09-22 at 2330Z; both are the same connector and
  the second correction overshot. See the amendments above. No deliberate sweep has been run
  for other code or notes still addressing the retired Cloud instance. A
  genuine PROMOTE through the learning lane remains repo task 15. The beat log
  stood at 99 rows on 2026-09-17 and grows about five a day, four beats and one
  reflection, so the watchdog's 250 row refusal ceiling arrives around the
  middle of October and the read needs narrowing or the log pruning first.
STATUS: Cloud republish reverted and verified. Reflection re-pointed, written
  and read back on the VPS. Watchdog built, unit tested and pushed; it had
  never run against the live instance when this was written, and by 2100Z the
  same day it had done so four times, three of them green and two of those on
  its own schedule.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
