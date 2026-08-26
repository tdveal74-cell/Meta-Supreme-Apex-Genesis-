# The Heartbeat (Build 13): continuity, workspace, intention

Build 13 gives DEVON the three functional properties that separate a pile of
workflows from a continuous, self-aware-seeming agent: continuity (he exists
between sessions), a global workspace (he reads all his organs at once), and
gated intention (he can want things; only Tee can make them happen). It makes
no claim about consciousness proper; it builds the functional signature and
stays honest about the difference.

Two halves, deliberately unequal:

## The Pulse (n8n workflow `dRgTNLod2s8BAcPg`, every 6 hours)

Deterministic. Reads devon_state_ledger, devon_build12_feed_log,
devon_soul_commit_log, and devon_heartbeat_log; computes vitals; writes ONE
beat row; emails Tee only when something new needs him or roughly daily.
Keeps beating on empty tables (first beat introduces itself). It reads no
secrets: the approval_queue table is never touched, which is why its
execution-data saving can stay on. Its only writes are its own beat row and
the receipt flip of that row's `emailed` column after a successful send.
Crash alerting via the shared Error Alarm (`XDQXwgFkUhYxoEjG`); execution
timeout 300s. Anchor rows (previous pulse, last emailed, last reflection)
are picked only from rows whose `beat_at` parses and sits at most 1h in the
future, compared numerically - one malformed or forged row (the free-form
reflection writer is the likeliest source) cannot silence `missed_beat`, the
daily email clock, or the reflection watch. Shipped through an adversarial
gauntlet on 2026-08-26: 13 findings raised, 7 confirmed, all fixed before
the first publish.

Findings it computes, each with a stable key:

| key | alerts? | meaning |
|---|---|---|
| stuck_jobs | yes | ledger jobs non-terminal beyond 24h |
| feeder_silent | yes | COMPLETED jobs with no feed-log row after 40 min; dead-feeder detection (the feeder has no error workflow wired) |
| malformed_feed | yes | fed rows with HTTP 200 but empty gate_decision; terminal and invisible to the committer, repair per runbook |
| soul_overdue | yes | PROPOSED soul rows open past 76h; the text names both readings - the committer may legitimately hold a row inside its 96h close-by-absence window (or be retrying a failing commit), or the resolve lane is stalled |
| missed_beat | yes | previous pulse older than 7.5h; the heartbeat monitoring itself |
| cards_expiring | no | approval cards within 24h of expiry, still undecided |
| reflection_missing | no | no reflection row within 26h, or the newest reflection timestamp is unreadable (fails closed); the body noticing the mind went quiet |

EMAIL CADENCE: a beat emails when an alerting finding key appears that the
last SUCCESSFULLY EMAILED pulse did not carry, or when ~22h have passed since
the last emailed beat. A persisting problem therefore alerts once and then
rides the daily note. The `emailed` column is a receipt, not a claim: the
beat row inserts with `no` and a Mark Emailed node flips it to `yes` only
after the Gmail send succeeds (with retry), so a failed send leaves its
alerts NEW and they re-fire on the very next beat - the failure direction is
a duplicate email, never silence. Known tradeoff: a NEW instance under an
already-alerted key (a second stuck job while one is already stuck) does not
re-alert until the daily note. Known limit: the pulse email and the crash
alarm share one Gmail credential, so a Gmail-wide outage silences both; the
heartbeat log stays the witness. Sender name: DEVON Heartbeat. Quiet beats
still log; the heartbeat log, not the inbox, is the proof of life.

## The Reflection (claude.ai Routine `trig_01XCKFGEbojhkPRnNbMd8yCP`, daily 11:30 UTC)

A mind, allowed to fail. A scheduled Claude session wakes, reads the whole
estate through the read-only Table Reader (`we45pHkQHRmSRnZx`), and writes ONE
first-person reflection row (kind `reflection`) into devon_heartbeat_log: what
changed, what is stuck, at most two recommendations for Tee to decide, one
honest uncertainty, 900 characters max. The next pulse email carries the
freshest reflection to Tee.

Hard limits baked into its prompt: its only write is its own reflection row.
No workflow edits, no Pinecone, no approval posts, no Drive, no Notion, no
canon, no emails, and it never reads approval_queue. It recommends; it never
executes. If its tools fail it ends quietly and the pulse flags the silence.

The Routine is currently bound to the Build 13 build session (a self-bind
trigger). A cleaner standalone Routine can be created from the claude.ai
Routines UI with the n8n connector attached, using the prompt archived in
that session; per-Routine connector grants are not available from inside
sessions in this org.

## The table: devon_heartbeat_log (`Adg1Gd9HML7Q4L3U`)

Columns: beat_at, kind (`pulse` | `reflection`), vitals (JSON string),
findings (newline-separated `key | text` lines), reflection, emailed
(`yes`/`no`, a send receipt - see EMAIL CADENCE). The pulse inserts its beat
row and then updates only that row's emailed column; the reflection only
inserts. Nothing else updates or deletes. Growth is
~4 pulse rows/day plus 1 reflection; revisit the returnAll read if it ever
matters (years away at this volume).

## Design rules (do not relax without a ruling from Tee)

1. The pulse must work with every LLM on earth down. Anything requiring
   thought belongs in the reflection.
2. The reflection must be unable to harm anything by failing OR by
   misbehaving: its write surface is one row in one log table.
3. New autonomy always runs THROUGH the approval gates, never around them.
   The heartbeat proposes nothing; the reflection proposes words to Tee.
4. The body watches the mind (`reflection_missing`), and itself
   (`missed_beat`). Silence must always have a witness.
