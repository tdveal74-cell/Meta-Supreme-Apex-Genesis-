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
   Just above the script, the doctor is also told where the learning objective
   is spoken, measured by the Script Gate's own rule in TQO FINAL V5: word for
   word, ignoring case and punctuation, inside the first 70 words. It is told
   which lines are the brief and which are the script. Both were added after
   execution 4300, in which the doctor guessed the objective's position wrong
   and took the LEARNING OBJECTIVE field line for a second copy of it. So the
   message the doctor reads is no longer exactly the live doctor's. NCO rows
   get the second line only, because their brief has no learning objective.
   The system message also carries Tee's ruling of 2026-10-24: first person
   that only addresses the viewer and claims no deed, sight, hearing or
   advice, as in "I am talking to the person who...", is his voice and stands.
   The rule against invented experience still covers everything else. Both
   shows get it. Tee sharpened it on 2026-10-25, after one read of three in
   execution 4364 took the person in that line for Terrance: it now says the
   person who has spent years is the viewer being addressed. On 2026-10-25 Tee
   ruled it covers both shows and goes to the live doctor too, which
   `../live-doctor-grounding/` carries.
   NCO rows are also told that a specific question for the comments is not
   engagement bait, and that an NCO episode may end on one or on a quiet
   action. Tee ruled this on 2026-10-25, after all three reads held NCO 30's
   closing question as bait. The same day he ruled "Keep NCO's subscribe
   close": the one line the NCO writer ends on, asking the viewer to
   subscribe, is NCO's call to action and stands, so the NCO sentence carries
   none of TQO's instruction to remove a subscribe request. The sentence is
   the one replacement in
   `../live-doctor-grounding/replacement.json`, so this lane and the live
   doctor carry the same words in the same place.
   The request is sent `READS` times (3). Tee ruled this on 2026-10-24, after
   the same request scored 85, 100 and 90 in three runs. The score written is
   the lowest of the reads. The verdict is PASS only when every read is PASS
   at 90 or above. If any read fails, nothing is written for the row.
5. It reads the row again. If any column the doctor was shown changed during
   the run (script, title, topic, description, learning objective, b-roll,
   checklist, show, season, episode, idea or sources), or a doctor line landed
   on it, nothing is written.
6. It appends one line to `score_history` and one note to `last_feedback`, then
   reads the row back to confirm both. Those two columns are the only writes.

The line reads `<time> | doctor 85/100 NEEDS_REVISION | score only, no rewrite, 3 reads (85, 100, 90), <model>`.
The note lists every read, shows the lowest read's diagnosis, preserved list
and notes in full, and gives the diagnosis of each other read. The doctor's
words are quoted as it wrote them. When they carry an em or en dash, which the
doctor is told not to write, the note ends by saying how many, as Tee ruled on
2026-10-25. Only the doctor's words are counted, never the TEE'S RECORD line
from the recall, and nothing this workflow writes adds a dash. A field the
doctor sends as something other than text is quoted as JSON. The one edit the
note makes is trimming whitespace at its very end.
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

`Run Config` holds five values: `FIRST_RUN_LIMIT` (1), `ROW_LIMIT` (20),
`ONLY_ROWS`, which limits a run to named rows such as `TQO:49`, `WRITE`
(true) and `READS` (3, from 1 to 5). Changing one is an edit to the workflow
on the instance.

`WRITE` false makes a measurement run. Every step runs and the doctor is paid,
but nothing is written to either table, and the run report lists each row's
score and diagnosis as MEASURED, NOT WRITTEN. A row that cannot be scored still
ends the run in error. `workflow.measure.json` is the measurement body: the
same workflow with `ONLY_ROWS` set to TQO 49 and `WRITE` false. Tee ruled on
2026-10-24 to score row 49 three times this way before the other 19, to see how
far one script's score moves between runs. Those three runs, executions 4354 to
4356, read one request at 85, 100 and 90, which is why `READS` exists.

## Files

`live/` holds the doctor lane bodies of TQO FINAL V5 at the version
`live/manifest.json` names, read back from the instance. `nodes/` holds the
code of the Code nodes this workflow adds; the other added nodes are defined in
`build.mjs`. `build.mjs` builds `workflow.json` and `workflow.measure.json`
from those, makes three replacements in live bodies and puts a comment header
on Build Doctor Prompt. `score_only.test.mjs` proves the build and runs in CI.

Since 2026-10-24 the live Build Doctor Prompt carries the same checklist
wording as this copy, published as fd873714. The pin in `live/` is still the
earlier body. Re-pinning from the instance would make the checklist replacement
fail to match, so a re-pin has to drop that replacement as well.
