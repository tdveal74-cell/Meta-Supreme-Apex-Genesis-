# The daily reflection writes through the outward gate

Status record, 2026-10-23. PR #407, merged as b9cfcc9 on top of main 76e1358.

## What was wrong

The daily reflection routine, `trig_01XCKFGEbojhkPRnNbMd8yCP`, wakes once a day
in the Build 13 session, reads four VPS tables and writes one row of kind
`reflection` into `devon_heartbeat_log` (`RuPMZKXkqcbuHRKa`). It always fires
with nobody in the session. The outward gate refuses an n8n write unless Tee
spoke or answered a card in the 30 minutes before it, so the routine's one
write was refused on 2026-10-16 and 2026-10-17, as it would be on any scheduled
run. Both refusals sit in this session's transcript with `is_error: true`.

From 2026-10-18 to 2026-10-22 the routine also found the VPS n8n connector
signed out, so it could not read the tables either. That is a separate cause.
Tee re-authorized the connectors on 2026-10-22, and nothing in this change
touches it.

The Pulse raised `reflection_missing` on every beat from 233 to 258, read back
row by row, and the newest of them read 178 hours. Its email carried the
finding daily from beat 233 on.

## Rulings

Tee ruled on 2026-10-22:

1. On a card, "Write it now". Row 259 was written while he was present and read
   back: `beat_at 2026-10-22T22:08:37.000Z`, 819 characters.
2. On the same card, "Exempt that one row", as the standing fix rather than
   standing the routine down or leaving both as they were.
3. On a second card, after the first critic round, "One per 12 hours".
4. In chat, "All rulings on inline cards multiple choice". Recorded in CLAUDE.md
   under the 2026-09-16 rulings paragraph: a ruling is a multiple choice card,
   never a sentence in a report, and a scheduled wake holds the decision for the
   next time he is present.

## What shipped

In `.claude/hooks/gate_ledger.py`, `add_data_table_rows` is ledger only, so it
passes with nobody present, only when every one of these holds:

- the server name contains n8n;
- the table is `RuPMZKXkqcbuHRKa` in project `qbrcjkbIoorbwot6`;
- the call has exactly its three keys and one row of exactly the six row keys,
  every value a string;
- kind is `reflection`, `vitals` and `findings` are empty and `emailed` is "no";
- the text is non-empty and at most 900 characters;
- `beat_at` is UTC in ASCII digits with a `Z` or `+00:00` suffix and at most six
  fractional digits, and lies within 10 minutes of the hook's clock.

The freshness bound exists because the Pulse anchors its reflection watch on any
reflection whose `beat_at` is up to 1h ahead, so a forward dated row could
silence `reflection_missing`.

The cap allows at most one such row per 12 hours in a session. Before the row
passes, the hook reads the session's transcripts, the main file and every
subagent file under it, for a completed write to the table. A write inside 12
hours sends the call to the ordinary gate, and so does a transcript that cannot
be read or one that restarts at a compact boundary inside the window. A refused
or failed write carries `is_error` and does not count. Across the 16 completed
writes the transcript still holds, from 2026-09-23, the shortest gap is 14.9
hours, so the cap would have refused none of them. The scan skips files
untouched since the window opened and parses only lines that name the tool or
carry a tracked id; on the real session, about 176 MB across 113 files, it takes
0.21 s against the hook's 15 s timeout.

PostToolUse and PostToolUseFailure record the call by its shape alone, and the
exception path in `main()` fails closed on a reflection row. Any other table,
row shape or n8n write goes through the gate exactly as before.

Records changed with it:

- CLAUDE.md names the shape, the form and the cap.
- The heartbeat reference describes the routine's reads and the exemption, and
  now says `reflection_missing` alerts, which the live and mirrored Compose
  Pulse confirm (`finding('reflection_missing', true, ...)`).
- `scripts/ledger_receipt.py` no longer lists a fixed set of ungated classes.
  The old list had left out pushes and `test_workflow`.

## Critics

Two rounds ran in isolated worktrees, and an independent skeptic re-ran each
finding before it counted.

Round 1 sent four critics against 96b36e4, with lenses for bypass, harm through
the Pulse, regression and records. None of them found a bypass. Nine findings
were confirmed, all low. The missing daily limit went to Tee as the second
card; the other eight were fixed in 724f0c5.

Round 2 sent two critics after the cap on 935d643. Neither found an unbounded
bypass. Four findings were confirmed and fixed in ee8816c:

- a transcript rebuilt on a fresh disk restarts at its newest boundary;
- a quadratic id prefilter, where 3,000 refused attempts took 20.6 s;
- surviving mutants of the newest write rule;
- surviving mutants of the window edge, the stale file floor and the id match.

Two more went unverified past the three per lens limit. The `os.walk` gap was
fixed anyway. The ee8816c commit message lists it among the four confirmed and
folds the two mutant findings into one bullet; this record follows the
workflow's verdicts, which an independent verifier re-read. The other is left as known: a capped row that Tee then allows is
recorded at PostToolUse by its shape, because the post event cannot see the
pre decision, while the pre row still shows the gated allow.

## Measured

- The scheduled reflection test is denied on main's hook and passes on the
  branch.
- Forty two single check mutations each turn a test red: 30 in round 1, 3 on
  the speed fix and 9 in round 2.
- On ee8816c, merged with main 76e1358:
  - `test_gate_ledger.py` with `test_ledger_receipt.py` gave 766 passed.
  - The standalone list from `ci.yml`, with no PYTHONPATH and no database, gave
    2219 passed.
  - The full API suite gave 5870 passed and 2 skipped.
  - `ruff` was clean.
- CI passed all six checks on ee8816c.

## Deploy read back

Read back after the merge, by deployment id, state and commit:

- Railway `api`: `e2261b03`, SUCCESS at 2026-10-23T00:18:05Z on b9cfcc9,
  after main's CI on b9cfcc9 passed.
- Railway `scheduler-cron`: `8d52dd0e`, SUCCESS on b9cfcc9. Railway's GitHub
  status for it posted success at 00:05:54Z; the record's own last update read
  00:15:06Z, which is not the moment it went live.
- Railway `presence`: `1bf3304d`, SKIPPED on b9cfcc9.
- Vercel `meta-supreme-apex-genesis-web`: `dpl_Dw2H6sWBW7RqLE22vvd8AgiSChYY`,
  target production, CANCELED.
- Vercel `devon-soul`: `dpl_8DofbJbEaJ4McbNEeuoyR5mvQE6N`, target production,
  CANCELED.

The two Vercel records are the ignore step skipping, and the skip was correct.
`git diff 76e1358 b9cfcc9` names five files, the hook, its tests, CLAUDE.md, the
heartbeat reference and the receipt script, and none of them is under
`apps/web`, `packages/ui`, the pnpm files or `deploy/soul`. No production surface
serves anything this change altered. The change acts in the session hook, which
runs from each session's own checkout, so a session picks it up from its working
tree. This session's hook file is byte identical to the merged one.

## Open

- The first unattended proof is the next scheduled reflection, due about
  11:35Z on 2026-10-23. It falls 13.4 hours after row 259, so the cap should let
  it through. Whether it wrote is read from `devon_heartbeat_log` afterwards,
  not predicted here.
- Tee's recall test from `/console` is still to run. The console and recall
  close out waits on it.
- What the harness does when this hook times out is still unverified. The scan
  is held far below the limit rather than relying on the answer.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_reflection-row-through-the-gate_v1_2026-10-23-0004
DATE: 2026-10-23
DECISIONS: Tee ruled on 2026-10-22 on cards to write the missed reflection now, to exempt only the reflection row from the outward gate, and to cap it at one per 12 hours in a session; and in chat that every ruling goes on an inline multiple choice card.
FINDINGS: the gate refused the unattended reflection on 2026-10-16 and 2026-10-17 and the Pulse raised reflection_missing on beats 233 to 258; two critic rounds with independent skeptics found no bypass, thirteen confirmed findings were fixed or ruled, and forty two mutations each turn a test red.
OPEN: the first unattended reflection under the exemption is due about 2026-10-23T11:35Z and must be read back from the heartbeat log; Tee's console recall test is still to run; hook timeout behaviour stays unverified.
STATUS: PR #407 merged as b9cfcc9 under the standing approval with all six checks green on ee8816c; Railway api e2261b03 and scheduler-cron 8d52dd0e SUCCESS on b9cfcc9, presence skipped, both Vercel projects correctly ignored.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
