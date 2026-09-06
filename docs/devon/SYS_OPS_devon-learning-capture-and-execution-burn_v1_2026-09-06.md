---
title: DEVON learning capture (Build 18) and the n8n Cloud execution burn, measured
type: SYS_OPS
version: 1
date: 2026-09-06
area: Systems
status: build-18-live-and-proven-wall-measured-levers-await-ruling
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: b1fe283
branch: claude/new-session-2f2yu2
supersedes: none
---

# DEVON learning capture (Build 18) and the execution burn v1

## Verdict in one paragraph

Build b of Tee's 2026-09-06 order is live: the Build 12 Ledger Feeder
(`6hQD8YhiYzR1FFda`) now writes the fact of a feed back onto the job
envelope. Every COMPLETED job the feeder has fed to the learning gate, and
whose envelope still read `learning.state not_captured`, carries one
`LEARNING_CAPTURED` event and a learning block that says when it was fed,
by whom, with what gate decision and what HTTP status. Seven jobs were
marked live at 12:40Z, one each, including the Build 17 proof job; the
feed log stays the feeder's only idempotency key, the mark is a mirror of
it, and the ledger's terminal rule was not touched, because COMPLETED to
COMPLETED is a same state update the Build 02 guard already allows. The
first proof run also found two defects in the build (a crash where a
refusal should have been data, and a mark branch that did not run on a
quiet day); both are closed and proven, one pinned, one live. The second
half of this document is the execution burn, measured from the instance
rather than estimated: 314 saved executions in the last 24 hours, about
264 an hour by hour steady state from the quiet window, and the levers
that would cut it, which are Tee's ruling.

## 1. What was built

The feeder had three Code nodes and fed each COMPLETED job to
`devon-build12-upstream` once, recording the feed in
`devon_build12_feed_log` (`QeoV4V4dYXXN8dBR`). Its sticky note said, and
still says, why the feed log and not the ledger's `learning_state` column
is the dedupe key: Build 02 rewrites whole rows from the envelope, so a
marker kept there can be wiped. That rule stands. What was missing is the
other direction: nothing ever told the envelope it had been fed, so every
driver run job read `not_captured` forever, and the Face, the Heartbeat
and the operational report all repeated it.

Build 18 adds a second branch, hung off `Fetch Feed Log` so it runs whether
or not there was anything new to feed:

- `Select Unmarked Jobs` (Code): for every COMPLETED row whose feed log
  entry answered 2xx (this run's fresh feeds included, taken from the
  digest because the table write is still in flight on the other branch)
  and whose `learning_state` is not `captured`, parse the envelope, refuse
  to touch it unless its `intent_id` matches and its state is COMPLETED,
  set `learning` to `{state: captured, captured_at, by: ledger-feeder,
  gate_decision, feed_status}`, and emit one item. At most 25 a run.
- `Report Learning to Bus` (HTTP): POST to `devon-event` with
  `event_type LEARNING_CAPTURED`, actor `devon`, the note naming the feed
  time, the status and the gate decision. One item at a time with a short
  interval, 30 second wait, `neverError` and continue on error, so a
  transport failure is an item with an error and not a crash.
- `Mark Receipts` (Code): reads every bus receipt back. `persisted true`
  is a mark; anything else is NOT RECORDED with what the bus said.
- `Marks Failed?` (If) and `Notify Marks` (SMTP, `mu7nJRSpkAfkzLdF`): one
  email only when a mark did not persist. A failed mark is retried on the
  next daily run because the row still reads `not_captured`.

The feeding branch is unchanged. Feeding is not approval and neither is
the mark: PROMOTE alone writes `devon-subconscious`, and `devon-soul` is
written only by the Soul Committer behind a card. The bus already carried
`LEARNING_CAPTURED` in its fourteen types and the repository's
`services/devon/ecosystem.py` lists it with `INTENT_RECEIVED` as its only
prerequisite, so no vocabulary moved.

The five Code node bodies live under `n8n/devon/ledger-feeder/`, the three
that were already live copied verbatim and the two new ones. The sticky
note was corrected in the same edit: the trigger has been daily at 02:00
instance time since 2026-09-05, not every 15 minutes, and the vault, the
learning lane skill and its ids reference said 15 minutes until this
document (corrected, dated, in the same commit).

## 2. Measured receipts (n8n Cloud, 2026-09-06, all times UTC)

| What | Receipt |
|---|---|
| First publish | version `f6569263` at 12:40Z |
| Proof run, the marks | production execution 6243 at 12:40:32Z: fed the Build 17 proof job `01M1V6M3XG0RQR191QFF7W74WJ` (feed log row 10, HTTP 200, gate REQUIRES_HUMAN), then selected seven unmarked rows and posted seven `LEARNING_CAPTURED` events. All seven persisted: the ledger rows `01M1S81K...`, `01M1SAK5...`, `01M1SC1B...`, `01M1SEBX...`, `01M1SN5X...`, `01M1TB5R...` and `01M1V6M3...` read `learning_state captured` with the full learning block, updated 12:40:39Z and 12:41:01Z, and each envelope carries exactly one `LEARNING_CAPTURED` trace entry (read back in full at 12:43Z) |
| Defect 1, found by that run | the run itself ended in ERROR at `Report Learning to Bus` with ECONNABORTED at 12:40:58Z: the HTTP node fired all seven posts at once, the bus and the ledger queued behind each other on the instance, and the node's 20 second wait aborted before every receipt came back. The marks had landed; the receipts had not. The shared Error Alarm fired (execution 6256) and emailed Tee, which is the email he received at 12:41Z |
| Fix 1 | version `b84dafc9` at 12:44Z: one post at a time with a 750 ms interval, 30 second wait, continue on error so the receipt reader sees the failure as data |
| Defect 2, found by the re-run | production execution 6261 at 12:45Z, nothing left to feed: the run stopped at `Select Unfed Jobs` with zero items and the mark branch, wired off `Log Or Alert`, never ran. A mark that had failed once would have waited for the next new job |
| Fix 2 | version `7bef0e3b` at 12:46Z: `Select Unmarked Jobs` hangs off `Fetch Feed Log`, which always outputs, and reads `Log Or Alert` only when it ran |
| Pinned run, the receipt path | execution 6263 (manual, pinned data tables and HTTP nodes): two unmarked rows selected, a third already captured skipped; one bus receipt pinned `persisted true` and one `persisted false`; Mark Receipts reported one MARKED and one NOT RECORDED with the bus's own words; `Marks Failed?` true; `Notify Marks` reached (pinned) |
| Live run, the quiet day | production execution 6264 at 12:47Z: zero unfed, the mark branch ran and selected zero, no error, no email. Idempotent on the live tables |
| Cost | the proof and its two fixes spent about 20 executions: one feeder run per proof, one gate call, seven bus posts and seven ledger writes |

## 3. What is not proven, stated plainly

- The receipt reader has not seen a live bus refusal; it is proven on a
  pinned receipt only. The next real COMPLETED job exercises the whole
  branch live at the 02:00 run.
- `MAX_PER_RUN` of 25 has never been reached.
- The mark carries the gate decision as the feed log recorded it. The
  feed log's own reading of the gate's answer (`decision`, `gate_decision`
  or `gate.decision`) is unchanged from Build 12 and was not re-verified
  here.
- Nothing downstream reads the new learning block yet. The Face prompt and
  the Heartbeat still describe `learning_state` as a column; they will
  now see `captured` on fed jobs without any change of their own.

## 4. The execution burn, measured

The 2026-09-05 blackout doc estimated about 120 executions a day and a wall
near 2026-09-21; the 2026-09-06 operational report re-estimated about 260
a day from four quiet hours of execution ids. This is the first count
taken from the instance's own execution list.

**24 hours, 2026-09-05 12:35Z to 2026-09-06 12:35Z, saved executions:**
314 (the listing's own count, not an estimate). Of those, by workflow:

| Saved runs | Workflow | Note |
|---|---|---|
| 69 | Live State Ledger `z9j2I8h0RnbDKGBO` | every organ report lands here; successes unsaved since 20:44Z on 09-05 |
| 69 | Event Bus `Bvy0grTSIyEmPwFA` | same |
| 35 | Driver Poll `mbIKJk4UuB7V27rP` | hourly, plus hand runs during the proofs |
| 18 | Drive Draft Writer | 17 of them manual, the Build 16 critic cycle |
| 17 | Approval Queue | cards raised and decided |
| 13 each | Spine Conformance Executor, Action Router, Intake Former | job traffic |
| 8 | Soul Layer Write-Back `edIJx7Q3FXTawg9J` | the vault says 15 minute poll; eight saved runs suggest otherwise, unverified |
| 8 | Job Driver | manual only; its poll driven runs are unsaved |
| 6 each | Pipeline Watchdog (every 4 hours), Airtable Row Writer (pinned), Intelligence Router, Runtime | |
| 5 | Heartbeat | 6 hour pulse plus one hand run |
| 1 to 4 each | Face, Precedence Guard, Weekly Table Backup, Capture Nudge, Table Reader, Duplicate Sweep, Ledger Janitor, Ledger Feeder, Capture Webhook, Monthly Credential Review | |

**What the saved count misses.** Execution ids are global and monotonic.
The ids in that window run from 5602 to 6236, a span of 634 for 314 saved
executions, so about 320 executions in the window were never saved:
the Soul Committer (every 15 minutes, all persistence off), the Job
Driver's poll driven passes, and every bus and ledger success since
20:44Z. The saved count understates the burn by roughly half.

**Steady state, from the quiet window.** Between 04:00Z and 08:00Z on
2026-09-06, with no one working, the Driver Poll's passes sit at ids 6088,
6097, 6104, 6119 and 6132: 44 ids in four hours, 11 an hour, about 264 a
day, about 7,900 a month. That agrees with the operational report's
estimate and is now measured twice. Of those 44: the Soul Committer 16
(four an hour, polling a commit log that holds one row, the reverted smoke
test of 2026-08-25, and has proposed nothing since), the Driver Poll 4
plus the driver passes for the one open job 4, the Heartbeat 1, the
Watchdog 2, the feeder 1, the Janitor 1, the backup 1, the Duplicate
Sweep 1, and the remaining dozen or so are the bus and ledger writes those
passes made.

**The cap is unread.** No tool in this session reads the n8n Cloud usage
page, so whether the plan caps at 2,500 or 10,000 a month is not known
here. At 264 a day a 2,500 month is spent in nine to ten days and a 10,000
month in thirty eight. If the month reset on 2026-09-01 and the cap is
2,500, the wall is about 2026-09-10. Tee reads the usage page; this
document does not guess it.

## 5. The levers, for Tee's ruling

Each is one schedule edit on the instance, reversible, and none changes
what any organ does when it runs. Savings are per day at the steady state
above.

1. **Soul Committer from every 15 minutes to hourly.** Saves about 72 a
   day (27 percent of the steady burn). Cost: a soul proposal waits up to
   an hour instead of fifteen minutes to be raised as a card, and the
   commit log shows nothing has been proposed in twelve days, so the
   latency is theoretical today. Recommended.
2. **Decide the stale card `REQ-20260905-f5kEZj`** on job
   `01M1S84TTY4DMC4D0VCHTJB672` from the email (reject; it was a proof).
   Saves about 24 a day until it self cancels on 2026-09-08, and it is a
   card Tee owns anyway. Recommended.
3. **Driver Poll from hourly to every two hours.** Saves about 12 a day
   with no open jobs, more with jobs waiting. Cost: a job Tee approves
   waits up to two hours to run. Not recommended while the approval to
   execution latency is the lane's whole promise; the VPS cutover makes
   the poll cheaper in the other direction.
4. **Runbook C, the VPS cutover.** Removes the ceiling. Tee's hands: an API
   key on the VPS instance, `scripts/n8n_migrate.py export` and `import`
   from a machine with egress to both hosts, the MCP connector repointed,
   then the reconcile and the lane proofs re-run there before any external
   poster is switched. One thing to verify first: the autonomy doc of
   2026-09-05 says the VPS instance is installed and empty, while ledger
   job `01M1KAEBPXJZMZSWC6MM02E2HA` (COMPLETED 2026-09-03, executor
   claude-cowork-session) records nine data tables and 38 rows migrated
   to `n8n.editforge.online` on 09-03. Both cannot be whole; read the VPS
   before importing anything.

Levers 1 and 2 together take the steady state to about 168 a day, about
5,000 a month: under a 10,000 cap with room, still over a 2,500 cap by the
middle of the month. They buy days, not the month. Only the usage page says
which plan this is, and only Runbook C removes the ceiling.

## 6. Records moved with this build

- `n8n/devon/ledger-feeder/` (five bodies, new), README row and paragraph.
- `services/devon/vault.py` and the `deploy/soul` copy, byte identical:
  the feeder's state string now says daily poll and the mark, with the
  dated note that it read 15 minute poll until this change and that the
  live trigger had been daily since 2026-09-05.
- `.claude/skills/devon-learning-lane/SKILL.md` and
  `references/ids-and-contracts.md`: the lane diagram and the feeder row.
- This document.

## 7. How this was read

The feeder, the ledger, the bus and the committer were read live with
`get_workflow_details`; the ledger's COMPLETED rows and the feed log were
read in full before and after the proof; every mark was verified by
reading the envelopes back and counting `LEARNING_CAPTURED` entries; the
execution list was read for the last 24 hours in two pages and ranked by
workflow id joined to the vault's names. Nothing was read from
`approval_queue`. No schedule was changed; section 5 is a recommendation.
