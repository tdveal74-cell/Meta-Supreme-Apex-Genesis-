# Score-only doctor: the twenty hand-loaded rows scored

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q. This arc ran
2026-10-24 to 2026-10-25. Every state fact below was read on the date it
carries. The n8n workflow and table facts come from the instance's public REST
API, and the execution facts from the saved execution JSON of each run.

Ruled by Tee 2026-10-24: "Score only, never rewrite." Twenty rows sat at
Scripted with a script and no doctor line, TQO 49 to 60 in `tqo_content`
(`2GtmrFcTNqVMbddh`) and NCO 30 to 37 in `nco_content` (`DSH1tn4TZjzAEKxp`).
By the QC Doctor Gate's code, a row with no doctor line reads `UNCHECKED` and
is held. Each row now carries one.

## Result

All 20 rows are scored and written. Three meet the gate's doctor line
condition, PASS at 90 or above: TQO 50, 51 and 59, each PASS 100 on all three
reads. That is one condition of the QC Doctor Gate, not the whole gate: the
gate also needs a signed AI review, a SHIP verdict and its release evidence,
and none of those were run here. The other 17 are held on the doctor line, at
scores from 45 to 91. Over the two writing runs nothing else in either table
changed, apart from the table's own `updatedAt` stamp on those same 20 rows.

Two of the twenty rows had been hand edited earlier on 2026-10-24, outside this
lane and before any scoring run. NCO 30 changed at 12:03Z: the row's note records a
hand edit "on Tee's card ruling 'Apply all repairs'" that added a three step
checklist and a closing question for the comments and restructured six
contrast lines, after an offline gate pass that applied the TQO closing
question and checklist rules to it. TQO 46, which is not one of the twenty,
changed at 11:44Z. Neither edit was made by this lane, and the card behind
them is not in this lane's record. Every score here was given to the script as it stood after
those edits.

The workflow is `TQO Doctor: Score Only (hand run)`, `wwjYsar6zRS6ZeD0`, manual
trigger only. Read back at 2026-10-25T06:52Z: inactive, `versionId`
`6cfffabd-b4f4-46cc-9f3a-ab6dcc4b66ca`, 26 nodes, every node's parameters
equal to `n8n/tqo-v5/doctor-score-only/workflow.json` at `d2183ec`. By the
Select Rows code and the snapshots taken after 4383, where every Scripted row
in both tables carries a doctor line, a further run would find no eligible row
and stop with "No row to score". That was not run.

## Rulings, in order

Every ruling in this arc was answered on a card. The first three rows set the
arc up; the rest are this lane.

| UTC | Ruling |
|---|---|
| 2026-10-24 00:56 | Keep the doctor line hold on the 20 hand-loaded rows and build a re-run for them |
| 2026-10-24 06:46 | Publish draft `9f80c967`, which restored the #367 laws on TQO FINAL V5 |
| 2026-10-24 08:37 | Score only, never rewrite |
| 2026-10-24 10:16 | Create the workflow inactive; run TQO 49 first; fix the live `Script: Hydrate from Row`, draft and publish; record the Sources Gate finding only |
| 2026-10-24 11:22 | Fix the prompt's checklist line and re-score 49; give the live Build Doctor Prompt the same wording, draft and publish |
| 2026-10-24 11:59 | Ground the doctor with measured facts, then measure; clear row 49's wrong 58 line; audit the live doctor's past repairs, reads only |
| 2026-10-25 00:26 | Go, run the three measurement runs |
| 2026-10-25 00:36 | Three reads per row, the strictest one holds; row 49's line "I am talking to the person who has spent years handling problems other people never even saw." is allowed, because it addresses the viewer, and "the score-only brief gains one line" saying so |
| 2026-10-25 02:48 | Measure 49, then score all 20 |
| 2026-10-25 02:57 | Sharpen the voice ruling and re-measure 49; quote the doctor's dashes as written and say how many |
| 2026-10-25 06:44 | Measure 49; if no read marks the viewer line down, write 49 alone, then the other 19 |

## Executions

All on `wwjYsar6zRS6ZeD0`, mode manual, status success.

| Execution | Started | Body | What it did |
|---|---|---|---|
| 4292 | 2026-10-24T10:17Z | first build, one read | Wrote row 49 NEEDS_REVISION 75. The prompt said "CHECKLIST (keep these steps as spoken, in order): (none returned)" because no TQO row stores a checklist, and the top diagnosis asked for a checklist the script speaks |
| 4300 | 2026-10-24T11:30Z | checklist wording fixed | Wrote row 49 NEEDS_REVISION 58. The doctor guessed the learning objective sat past 30 seconds when it starts at word 31, and took the LEARNING OBJECTIVE field line for a second copy in the script |
| 4354, 4355, 4356 | 2026-10-25T00:27Z to 00:28Z | grounded, measurement, one read | Row 49 scored 85, 100 and 90 on the same request. Nothing written |
| 4364 | 2026-10-25T02:49Z | three reads, voice ruling | Row 49 read PASS 96, PASS 100, NEEDS_REVISION 85. The 85 read took "the person who has spent years" for Terrance. Nothing written |
| 4381 | 2026-10-25T06:45Z | sharpened ruling, measurement | Row 49 read NEEDS_REVISION 72, PASS 92, PASS 100. No read marked the viewer line down. Nothing written |
| 4382 | 2026-10-25T06:45Z | real body | Wrote row 49 |
| 4383 | 2026-10-25T06:46Z | real body | Wrote the other 19 |

The two wrong lines on row 49, from 4292 and 4300, were cleared by row id at
11:27Z and 12:00Z on 2026-10-24, each after a dry run. Each clear set row
49's `score_history` and `last_feedback` back to null, its `updatedAt` stamp
moved, and the snapshots either side show no other row in the 60 TQO rows
changed.

In 4381 and 4382, reads 1 and 2 of each run list the viewer line under
PRESERVED, and read 3 of each names it only in its saved reasoning, as
allowed. No read marks it down. The lowest read in each run is not about the
voice: 4381 read 1, at 72, says "The script lacks a single clear argumentative
thesis; it reads as a list of instructions rather than an argument", and 4382
read 1, at 81, says "The script flattens in the middle where it lists steps
without presenting conflict or stakes". Both cite the spoken checklist as the
example.

## What the doctor is given

The score-only workflow runs the live doctor lane of `TQO FINAL V5` with these
differences, each built from the node code and pinned by
`score_only.test.mjs`, 280 checks at `d2183ec`:

- The output contract asks for a score and PASS or NEEDS_REVISION, never a
  rewritten field. Any other verdict, REPAIRED most of all, writes nothing.
- `Score Only: Final Word` adds two facts above `SCRIPT:`. For TQO, where the
  learning objective is spoken, measured by the Script Gate's own rule: word
  for word, ignoring case and punctuation, inside the first 70 words. For both
  shows, which lines are the brief and which are the script.
- The voice ruling goes into the system message: first person that only
  addresses the viewer, as in "I am talking to the person who has spent years
  handling problems other people never even saw.", is Tee's voice and stands.
  The person in that line is the viewer, not Terrance. The card ruled on row
  49's line and said "the score-only brief gains one line". That brief scores
  both tables, so the build put the line in the system message for NCO rows
  too, and the card did not name NCO. No NCO script carries a first person
  line that addresses the viewer; their first person sentences are quoted
  dialogue.
- Each row is read three times. The lowest score is written, and the verdict
  is PASS only when all three reads pass at 90 or above. A failed read writes
  nothing for that row.
- The doctor's words are quoted as written. When they carry em or en dashes,
  the note ends by saying how many.

## Per row

Scores are the three reads in order. Under the strictest-of-three rule a
single PASS under 90 holds the row, as on TQO 55, TQO 60 and NCO 36. The last
column is the doctor line condition only. Two stored titles, TQO 51 and NCO
35, use a typographic apostrophe, written straight here.

| Row | Title | Reads | Written | Doctor line |
|---|---|---|---|---|
| TQO 49 | Your Experience Needs Evidence | NR 81, PASS 100, PASS 100 | NR 81 | held |
| TQO 50 | Before You Learn Code, Map the Work | PASS 100, 100, 100 | PASS 100 | meets 90 |
| TQO 51 | Which Parts of Your Boss's Job Can AI Actually Do? | PASS 100, 100, 100 | PASS 100 | meets 90 |
| TQO 52 | Automate One Task. Measure the Whole Cost. | NR 81, PASS 96, PASS 95 | NR 81 | held |
| TQO 53 | Two Responses to the Same AI Change | NR 78, NR 76, PASS 92 | NR 76 | held |
| TQO 54 | Audit Your Tasks Before You Judge Your Career | NR 45, NR 63, NR 85 | NR 45 | held |
| TQO 55 | Write the Brief Before You Build the Agent | PASS 100, PASS 96, PASS 87 | NR 87 | held |
| TQO 56 | Rewrite Your Resume Around Evidence | PASS 100, PASS 100, NR 91 | NR 91 | held |
| TQO 57 | Who Decides What Happens to Your AI Savings? | PASS 100, PASS 90, NR 88 | NR 88 | held |
| TQO 58 | An AI Audit Cannot Tell You Your Salary Is Safe | NR 86, PASS 100, PASS 93 | NR 86 | held |
| TQO 59 | Learn Enough Code to Check the Work | PASS 100, 100, 100 | PASS 100 | meets 90 |
| TQO 60 | Before You Hand Over the Workflow, Test the Failure | PASS 100, PASS 88, PASS 96 | NR 88 | held |
| NCO 30 | Three Leadership Failures Every NCO Should Audit | NR 70, NR 85, NR 85 | NR 70 | held |
| NCO 31 | Your First 60 Seconds as the Leader | NR 66, NR 67, NR 45 | NR 45 | held |
| NCO 32 | Lead Without Screaming | NR 78, PASS 92, NR 80 | NR 78 | held |
| NCO 33 | The Habits That Make Accurate Reporting Harder | PASS 95, NR 91, PASS 91 | NR 91 | held |
| NCO 34 | Before You Call a Squad Broken, Diagnose the Work | NR 68, PASS 100, PASS 100 | NR 68 | held |
| NCO 35 | Leading When You're the Youngest NCO | NR 72, NR 73, PASS 98 | NR 72 | held |
| NCO 36 | When the Standard Changes Depending on Who You Are | PASS 83, PASS 94, PASS 95 | NR 83 | held |
| NCO 37 | Leadership Shortcuts That Can Put Soldiers at Risk | PASS 100, NR 68, PASS 100 | NR 68 | held |

The table diff of the snapshots taken before 4382 and after 4383 reads "rows
changed vs pre-run snapshot: 20 | anything else changed: []". That diff
skipped `updatedAt`; the verifier below compared every column and found the
stamp moved on the same 20 rows and nowhere else.

TQO 54 is the one hold with a source question in it. The script says the
International Labour Organization and NASK published a global index of
occupational exposure to generative AI in May 2025. The row's brief reads
"APPROVED SOURCES: none. No figure, percentage, dollar amount or named study
may stand." All three reads call the citation invented, and that is the
brief's own word: the live doctor prompt says a named study "that is not in
APPROVED SOURCES is invented". So the hold follows the rule as written. The
study itself exists: the ILO lists it as Working Paper 140, "Generative AI and
Jobs: A Refined Global Index of Occupational Exposure", at
ilo.org/publications, read on the web 2026-10-25. Whether to approve that
source for the row or cut the sentence is a content call.

## Live changes to TQO FINAL V5

Two single node changes, each published on Tee's card and read back:
`activeVersionId` equal to `versionId`, every active node equal to the draft,
only the one node different from the version before. The checklist change is
one line. The Hydrate change replaces one code line with one code line and
five comment lines.

| Node | Before | After | Rollback |
|---|---|---|---|
| `Script: Hydrate from Row` | `9f80c967` | `bdb59b09` | restore that node's `before.js` body on top of `fd873714`; publishing `9f80c967` would undo both changes |
| `Build Doctor Prompt` | `bdb59b09` | `fd873714` | publish `bdb59b09` |

Read back again at 2026-10-25T06:52Z: active, `versionId` and
`activeVersionId` both `fd873714-7acf-482b-8ab1-e101e1afb5ac`. The before and
after bodies and their hashes are in `n8n/tqo-v5/live-hydrate-fix/` and
`n8n/tqo-v5/live-doctor-checklist-fix/`.

## The live doctor's past repair, execution 2668

Reads only. Execution 2668 is the live doctor's REPAIRED run on TQO row 5,
2026-10-11T10:20Z, the only REPAIRED run whose data is still retained. TQO 46
and NCO 26 were also repaired, and their executions are gone. Three lenses
read the draft, the repair and the reply, and one refuting verifier per
candidate re-measured each one, 29 at `7d57ca6` and one at its ancestor
`6f8c55f`: 30 confirmed, none refuted, none unsettled.

The repair kept all three promises. The learning objective is spoken word for
word, once, ending at word 58. All five checklist steps are spoken in the same
words and order. The closing comment question is unchanged and last.

It removed what its absolute rules forbid. The invented first person claim is
cut, and the name "Operator Test", three times in the draft, is gone. The
same five parts stay as an unnamed "five-part test", which meets the letter
of the rule against a named five step framework and arguably not its intent.

It also cut more than any rule asked. The five defining questions and the
roadmap sentence of the test paragraph are deleted, which leaves a dangling
"each question" and no explanation of the five parts. The b-roll it returned
still names "Operator test checklist".

It missed things the audit confirms. "What I call the quiet move" stayed,
although its reasoning called the first coinage the only one. Three em dashes
in the draft went unflagged and two survived its repair, until a later step
fixed them. It reported banned words as absent, and "truly" stays twice. It
passed a GMAC attribution that the approved quote does not contain. Graded
low: unnamed firm claims left in place, and a 62 character title called
compliant against an under 60 rule.

"Fifteen minutes" stayed in the script, and the Sources Gate then failed the
row on that word, so the row went to Error. The audit does not count that as
the doctor's miss: the stricter numeral rule is in the writer prompt and not
in the doctor's request, so the doctor and the gate apply different numeral
rules.

## The Sources Gate, offline

Recorded only, on Tee's ruling. The live Sources Gate, run offline on the
twenty rows as they stood before any doctor line, fails eight:

| Row | Flag | Script context |
|---|---|---|
| TQO 49 | figure "A third" | "Another leaves out the delivery date. A third asks the team" |
| TQO 50 | figure "A third" | "Another is a request for more information. A third is an escalation." |
| TQO 54 | figure "2025" | "In May 2025 the International Labour Organization and NASK published" |
| TQO 59 | figure "twice" | "What happens if the request arrives twice?" |
| NCO 30 | attributed to "Soldier" | "A Soldier reports that a required item is unavailable." |
| NCO 31 | figure "sixty" | "We are using sixty seconds as a rehearsal exercise." |
| NCO 33 | figures "A third", "A fourth"; attributed to "Soldier" | "A third habit is reporting a concern upward", "A fourth habit is allowing a report to disappear", "A Soldier reports that a required resource is missing." |
| NCO 37 | attributed to "Someone", "Somebody" | "Someone says it is probably complete." |

NCO 30 was run as it stood before its 12:03Z hand edit; the same sentence
trips the gate on the edited script that was scored.

TQO 54's flag is the one with a real problem behind it, though the gate caught
the year "2025" rather than the attribution: the International Labour
Organization and NASK passed its attribution checks. Under the row's brief,
which approves no source, the named study cannot stand. The other seven are an
ordinal, a count, a frequency or a character in the story. The gate was not
changed. Which of these rows will pass through it in TQO FINAL V5 is not
measured here.

## Gaps found and not fixed

- `parse_score_only.js` drops a `notes` field sent as a bare string, and a
  `preserved` field sent as an object, because `list()` keeps only arrays.
  Read from the code.
- The note is trimmed at both ends, so trailing whitespace the doctor wrote at
  the end of its last field is lost.
- The blank-entry filter in `list()` is not pinned. Removing
  `.filter(s => s.trim())` and rebuilding left all 280 checks passing,
  measured in a throwaway worktree at `d2183ec`.
- `n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json` is stale on
  `DOCTOR_FLOOR`: it carries 70 where the live gate carries 90. The grounding
  test reads three lines of its Script Gate, the 70 word window, the
  normaliser and the in-window test, and all three match the live gate.

## Verification

Each build behind these runs went through independent verifiers before it ran
on the instance: `7d57ca6` (grounding), `31e0f73` and `6305cda` (three reads
and the voice ruling), `e0351e1` and `d2183ec` (the sharpened ruling and the
dash count). The findings on `7d57ca6`, `31e0f73` and `e0351e1` are fixed in
`c292c57`, `6305cda` and `d2183ec`; `6305cda`'s verifier raised none. The
verifier on `d2183ec` raised two that are not fixed: the blank-entry filter
mutant and the `list()` drops, the first and third items under Gaps above.

A fresh critic then checked every factual sentence of this doc against the
same files, in four sections. It found no wrong id, version or score. It
found two wrong quotes in the Sources Gate table, a checklist count that took
in an NCO reply, and a set of overclaims on the gate, the voice ruling's
scope and NCO 30's history. All of its corrections are applied here.

Two refuting verifiers checked the run itself, each in its own worktree at
`d2183ec`, from the saved execution files and table snapshots, with no network
and no database. Both reported CONFIRMED.

Run integrity:

- Exactly 20 rows differ between the snapshots, TQO 49 to 60 and NCO 30 to
  37. Each differs in `score_history`, `last_feedback` and `updatedAt` only,
  both written cells were null before, and both tables keep their row counts.
  The verifier noted that `updatedAt` is the one column the claim left out.
- Every written line and note is byte for byte what that row's Compose Write
  produced.
- Recomputed from the 60 raw Cerebras replies, all ending on `stop`: every
  written score is the lowest of three, and only TQO 50, 51 and 59 are PASS.
- The QC Doctor Gate's own regex, taken from `qc_doctor_gate.js`, passes the
  doctor line of exactly TQO 50, 51 and 59 on the post-run history. That tests
  the doctor line rule, not the whole gate.
- The 12 notes that end with a dash count are right, and the other 8 carry no
  em or en dash. The notes also carry 31 non-breaking hyphens, which are
  neither and are not counted.

Three patterns in the replies, each graded against the request the doctor was
actually sent:

- NCO 30. All three reads held its closing line, "In the comments, which of
  the three failures did you find in your own last week, and what is the one
  repair you will make?", as engagement bait. The TQO sentence saying a
  specific comments question is not a solicitation is in all 12 TQO requests
  and in none of the 8 NCO requests. Both shows' requests carry the same
  shared rubric line, "close 15: a clean implication or a real action. Never
  a solicitation.", and only TQO's add the comments clause. The other seven
  NCO scripts close that way, and NCO 30 is the only one that ends on a
  comments question. That question is new: it was added in the 12:03Z hand
  edit on 2026-10-24, after an offline gate pass that held NCO 30 for having
  no comments question, "the same rule V5 failed TQO 46 on". Before the edit
  the script ended "Then return to the work. Let the next action support what
  you said." So the doctor read the NCO request as written, and two lanes now
  disagree on how an NCO episode should close.
- NCO 31. Its lowest read, 45, cites "Tee's cold-open rule". The rule is in
  the request, in the TEE'S RECORD block from the DEVON recall: a ruling dated
  2026-09-08, "adopted 2026-09-08 from the Sisinty benchmark refresh (Claude
  derived, Tee to overrule)", that a long form cold open stacks three or four
  teased items each with a named entity and a number. Of the 19 requests in 4383 it reached
  only NCO 31's. The block is headed as the only first person material that
  may stand, and the read applied it as a script rule. So one row was judged
  on a rule the other nineteen were never shown.
- The checklist. This doc's draft expected many holds to blame the required
  checklist for reading as a list. Measured, 2 of the 23 NEEDS_REVISION
  replies name the required checklist passage as the problem: TQO 49 read 1
  (81) and TQO 58 read 1 (86), each the read that holds its row. All 12 TQO
  requests carry "REQUIRED BY THE BRIEF, NEVER CUT OR REWORD: ... the spoken
  checklist of 3 to 5 steps". Three NCO replies call a script a list of
  instructions or a checklist of separate items, NCO 37 read 2 (68), NCO 31
  read 1 and NCO 33 read 2 (91), where NCO has no checklist rule. Separately, a note on TQO 55 read
  3 asks to drop "Use four steps" because it "hints at a named framework",
  against the brief's "The checklist is not a named framework".

## Open

- Give the live doctor in TQO FINAL V5 the voice ruling and the measured
  learning objective line. Both are proven only on the score-only lane.
- The seventeen held rows. The scores say what the doctor sees; revising the
  scripts is a separate ruling.
- TQO 54's source: approve ILO Working Paper 140 for that row, or cut the
  sentence.
- The live doctor over-cut on TQO 5, and its two other repairs left no data to
  read.
- How an NCO episode closes: with a comments question, as the 2026-10-24 hand
  edit of NCO 30 assumed, or with "a clean implication or a real action", as
  the shared rubric line says when no comments clause is added. That decides
  NCO 30's ending.
- Whether the viewer address ruling covers NCO. The card named row 49's line
  and the score-only brief; the build applied it to both tables.
- Whether the 2026-09-08 cold-open record stands. If it does, every row's
  brief should carry it; if not, the recall should stop serving it.
- TQO 49 and TQO 58 are each held by one read that marks down the required
  checklist.
- The seven Sources Gate false positives.
- The three parser gaps and the stale export above.

## DEVON RECEIPT

AREA: TQO, NCO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_score-only-doctor-twenty-rows_v1_2026-10-25-0654.md
DATE: 2026-10-25
DECISIONS: Tee ruled on cards: score only, never rewrite; create the score-only workflow inactive and run it by hand; ground the doctor with the learning objective's measured position and the brief's lines; three reads per row, the strictest holds; row 49's viewer address line is allowed and the score-only brief gains a line saying so; quote the doctor's dashes as written and count them; publish the Hydrate and checklist single node fixes to TQO FINAL V5; record the Sources Gate finding only.
FINDINGS: All 20 rows written, appends only, nothing else changed but the table's own updatedAt stamp; two refuting verifiers and a fresh critic confirmed the run. TQO 50, 51 and 59 meet the gate's doctor line condition at PASS 100; the rest of the gate was not run. 17 are held from 45 to 91. NCO 30's comments question, added by a 2026-10-24 hand edit, is held under the shared close rule without TQO's comments clause. NCO 31 was judged on a 2026-09-08 cold-open record that the recall served to that row alone. The required checklist is marked down in 2 of 23 NEEDS_REVISION replies, holding TQO 49 and 58. One request scored 85, 100 and 90 on three single reads, which is why three reads hold. The live doctor's TQO 5 repair kept the three promises and cut more than any rule asked. The Sources Gate fails 8 of 20 offline, one with a real problem behind it. TQO 54's named study exists and is unapproved for the row.
OPEN: Voice ruling and grounding for the live doctor; the 17 held rows; TQO 54's source; the live doctor's over-cutting; how an NCO episode closes; whether the viewer address ruling covers NCO; the cold-open record; the checklist mark-downs on TQO 49 and 58; seven Sources Gate false positives; three parser gaps; the stale export.
STATUS: Scoring complete and read back. TQO FINAL V5 live on fd873714. The score-only workflow inactive on 6cfffabd. PR #416 carries the build and this doc.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
