# DEVON's own memory, carried across the cutover

2026-09-16. The switch moved every organ to the VPS and the lane was proven end
to end the same night. This closes a gap that a clean switch left behind: the
tables DEVON reads about himself were a snapshot from thirteen days earlier.

## How it was found

By checking why the Heartbeat had not beaten instead of saying wall clock a
fourth time. The workflow was armed and correct, but the check turned up
something else.

`devon_heartbeat_log` on the VPS held 23 rows whose newest beat was
2026-09-03T04:00:24Z, and every one of those rows carried `createdAt`
2026-09-03T09:01Z: the earlier migration copied the table once and nothing ever
re-copied it. Cloud's own copy held 88 rows and kept beating on its six hour
cadence right up to 2026-09-15T22:00:24Z, which is when the switch unpublished
it. The same shape in `devon_build12_feed_log`: 2 rows on the VPS, 11 on Cloud.

This is not a cutover defect. Step three of the plan moved the state ledger, and
it moved nothing because all 21 Cloud ledger rows were terminal and terminal
rows stay. These logs were never in that step at all, which is why the gap
survived a switch that otherwise measured clean.

## What it would have cost

The pulse is where DEVON's continuity lives. Each beat reads the previous beat,
notices its own missed beats, and notices when the reflection has stopped
writing. Left alone, the first VPS beat would have read its own log, seen its
last pulse thirteen days back, and emailed a missed beat of about 310 hours.
That alarm clears itself after one beat. The lasting cost was the memory: twelve
days of DEVON's account of himself absent from the host he now runs on, and
vitals reporting 2 fed where the truth was 11.

Ruled by Tee 2026-09-16, two words: copy it.

## What was done

`scripts/vps_backfill_devon_logs.py`, insert only. It reads both sides, diffs on
a natural key per table, and inserts only rows whose key is absent, so a second
run is a no-op rather than a duplicate. It never updates a row and never deletes
one. `approval_queue` is not in its table list and must never be added: its rows
carry plaintext decision tokens, and the standing rule is that the queue does
not move and that column is not read.

Measured, not assumed:

| table | cloud | vps before | copied | vps after |
|---|---|---|---|---|
| `devon_heartbeat_log` | 88 | 23 | 65 | 88 |
| `devon_build12_feed_log` | 11 | 2 | 9 | 11 |
| `devon_soul_commit_log` | 1 | 1 | 0 | 1 |

The copied set is contiguous with what was already there. The VPS snapshot ended
at 2026-09-03T04:00:24Z and the first owed beat is 2026-09-03T10:00:25Z, the
next tick of the same six hour cadence, through to 2026-09-15T22:00:24Z. No
overlap and no missing middle.

Three checks were run rather than one. The script re-read the destination after
inserting and reported 0 still owed. A second dry run reported 0 owed on every
table, which is the idempotency claim actually exercised. Then an independent
read through a different client confirmed the last Cloud beat is now row 88 on
the VPS with its fields intact, `emailed` yes and the vitals JSON whole.

## What the first VPS beat will now say, and why that is right

It will read its previous pulse as 2026-09-15T22:00:24Z rather than thirteen
days ago. The threshold for a missed beat is 7.5 hours, so a beat landing near
05:30Z will report missing roughly one beat. That is true: DEVON did miss the
04:00Z beat, because he was being moved. A seven hour gap he really had beats a
three hundred hour gap he did not.

Its last email was 2026-09-14T22:00:24Z, past the 22 hour clock, so it will
write home on the first beat either way.

It will also flag the proof job `01M2KT8WM4RPZ90BCTZPVXH6HK` as a COMPLETED job
the feeder has not fed. That one is true as well: the row reads
`learning_state: not_captured`, and the learning lane has not picked it up.

## Open

The Heartbeat still has 0 executions on the VPS at 03:25Z. Cloud's beats landed
at 04:00, 10:00, 16:00 and 22:00 UTC, so the recurrence anchors to activation
rather than to midnight, and the first VPS beat is due near 05:30Z. If nothing
has fired by 06:00Z it is a fault rather than a wait.

`TQO FINAL V5` is red on the VPS from an intermittent Data Table failure at
01:00:00Z, recorded in `SYS_OPS_the-vps-cutover-proven_v1_2026-09-16a.md`. Its
next pass is 04:00Z and a second failure makes it real.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-devon-log-backfill_v1_2026-09-16d.md
DATE: 2026-09-16
DECISIONS: Tee ruled copy it, on a recommendation that named the cost of leaving it. The backfill inserts only, never updates and never deletes, and the approval queue is excluded by design rather than by care. Rows were copied one call at a time rather than in a batch, because a rejected batch would leave a partial copy that reads as a complete one.
FINDINGS: The VPS copies of DEVON's own memory tables were a snapshot taken 2026-09-03T09:01Z while Cloud kept writing to its own copies until 2026-09-15T22:00:24Z, a twelve day divergence that a clean cutover left behind because the plan's ledger step never covered these tables. 65 heartbeat rows and 9 feed rows were owed and are now copied, verified three ways: a read back after insert, a second dry run reporting 0 owed on every table, and an independent read confirming the last Cloud beat is row 88 on the VPS with its fields intact. The copied range is contiguous with the snapshot, 2026-09-03T10:00:25Z through 2026-09-15T22:00:24Z, with no overlap and no missing middle. The soul commit log was already in sync at 1 row. The rows API takes limit only, caps it at 250, rejects skip and offset and returns no total, so the reader refuses a full page rather than copying a prefix that would look complete.
OPEN: The Heartbeat has 0 executions on the VPS at 03:25Z; its beats anchor to activation rather than to midnight, so the first is due near 05:30Z and anything after 06:00Z is a fault. TQO FINAL V5 is red from an intermittent Data Table failure with its next pass at 04:00Z. The proof job is COMPLETED but learning_state not_captured, so the learning lane has not yet run on the VPS.
STATUS: DEVON's continuity survived the move. The heartbeat log and the learning feed log on the VPS now match Cloud exactly, and his first beat on the new host will read true history rather than a thirteen day hole.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
