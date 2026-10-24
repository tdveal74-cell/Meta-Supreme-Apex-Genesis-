# TQO Doctor: Score Only (hand run)

Ruled by Tee on 2026-10-24: "Score only, never rewrite."

The script doctor in TQO FINAL V5 runs only for rows at status Idea. Twenty
rows were loaded by hand straight to Scripted, TQO 49 to 60 and NCO 30 to 37,
so none of them carries a doctor line, and the QC Doctor Gate and Preflight
hold all twenty. This workflow gives each of those rows one doctor line and
one note, and changes nothing else on it.

## What a run does

A person starts it by hand. It has no schedule and no webhook.

1. It reads the Scripted rows of both tables and takes those with a script and
   no doctor line, TQO first, each in row order.
2. The first run takes one row. Once a score-only line exists on a Scripted row
   in either table, a run takes up to 20.
3. For each row it asks the DEVON recall for Tee's record. If the recall does
   not answer, or answers without Tee's own index, the run stops there and
   writes nothing for that row.
4. It runs the live doctor prompt with the output contract replaced. The doctor
   returns a score and PASS or NEEDS_REVISION, and never a rewritten script.
   When a row stores no checklist, the doctor is told to judge the spoken steps
   in the script itself rather than told none was returned.
5. It reads the row again. If any column the doctor was shown changed during
   the run (script, title, topic, description, learning objective, b-roll,
   checklist, show, season, episode, idea or sources), or a doctor line landed
   on it, nothing is written.
6. It appends one line to `score_history` and one note to `last_feedback`, then
   reads the row back to confirm both. Those two columns are the only writes.

The line reads `<time> | doctor 92/100 PASS | score only, no rewrite, <model>`.
This workflow never writes REPAIRED, so of its lines the QC Doctor Gate and
Preflight clear only PASS at 90 or above. A score is rounded down, so 89.95 is
written as 89.9 and held.

Any reply other than PASS or NEEDS_REVISION with a score from 0 to 100 writes
nothing. That covers REPAIRED, a refused or truncated call and unreadable
JSON. A run in which any row was not written ends in error. When it reaches
Run Report, the error lists every row, including one whose write did not read
back. A run that stops at Recall Required names the row it stopped on. If a
data table step itself fails, n8n's own error stops the run without naming the
row. Either way, the rows written before it stay written.

## Undoing a line, or scoring a row again

A row with a doctor line is never scored again by this workflow, and the live
doctor does not reach Scripted rows. To undo a line, or to score a row again
after its script is revised, open the row in the n8n data table and delete the
line this workflow appended to `score_history` and the note it appended to
`last_feedback`. Both cells were empty on all twenty rows when they were read
on 2026-10-24, before any run, so on those rows the appended text is all there
is unless another lane has written there since. QC appends to `score_history`
too, so read the cell before clearing it. The next run then picks the row up.

## Settings

`Run Config` holds three values: `FIRST_RUN_LIMIT` (1), `ROW_LIMIT` (20) and
`ONLY_ROWS`, which limits a run to named rows such as `TQO:49`. Changing one is
an edit to the workflow on the instance.

## Files

`live/` holds the doctor lane bodies of TQO FINAL V5 at the version
`live/manifest.json` names, read back from the instance. `nodes/` holds the
code of the Code nodes this workflow adds; the other added nodes are defined in
`build.mjs`. `build.mjs` builds `workflow.json` from those, makes three
replacements in live bodies and puts a comment header on Build Doctor Prompt.
`score_only.test.mjs` proves the build and runs in CI.
