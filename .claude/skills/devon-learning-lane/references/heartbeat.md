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
execution-data saving can stay on. Its only write is its own beat row.
Crash alerting via the shared Error Alarm (`XDQXwgFkUhYxoEjG`); execution
timeout 300s.

Findings it computes, each with a stable key:

| key | alerts? | meaning |
|---|---|---|
| stuck_jobs | yes | ledger jobs non-terminal beyond 24h |
| feeder_silent | yes | COMPLETED jobs with no feed-log row after 40 min; dead-feeder detection (the feeder has no error workflow wired) |
| malformed_feed | yes | fed rows with HTTP 200 but empty gate_decision; terminal and invisible to the committer, repair per runbook |
| committer_stalled | yes | PROPOSED soul rows past 72h expiry plus 4h grace |
| missed_beat | yes | previous pulse older than 7.5h; the heartbeat monitoring itself |
| cards_expiring | no | approval cards within 24h of expiry, still undecided |
| reflection_missing | no | no reflection row within 26h; the body noticing the mind went quiet |

EMAIL CADENCE: a beat emails when an alerting finding key appears that the
previous beat did not carry, or when ~22h have passed since the last emailed
beat. A persisting problem therefore alerts once and then rides the daily
note. Known tradeoff: a NEW instance under an already-alerted key (a second
stuck job while one is already stuck) does not re-alert until the daily note.
Sender name: DEVON Heartbeat. Quiet beats still log; the heartbeat log, not
the inbox, is the proof of life.

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
(`yes`/`no`). Both writers only insert; nothing updates or deletes. Growth is
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
