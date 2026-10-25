# Score-only doctor: the twenty hand-loaded rows scored

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q, 2026-10-24 to
2026-10-25. Every state fact below was read on the date it carries. The n8n
workflow and table facts come from the instance's public REST API, and the
execution facts from the saved execution JSON of each run.

Ruled by Tee 2026-10-24: "Score only, never rewrite." Twenty rows sat at
Scripted with a script and no doctor line, TQO 49 to 60 in `tqo_content`
(`2GtmrFcTNqVMbddh`) and NCO 30 to 37 in `nco_content` (`DSH1tn4TZjzAEKxp`).
The QC Doctor Gate held all twenty, because it clears a row only on a doctor
line. Each row now carries one.

## Result

All 20 rows are scored and written. Three clear the gate: TQO 50, 51 and 59,
each PASS 100 on all three reads. The other 17 are held, at scores from 45 to
91. Nothing else in either table changed.

The workflow is `TQO Doctor: Score Only (hand run)`, `wwjYsar6zRS6ZeD0`, manual
trigger only. Read back at 2026-10-25T06:52Z: inactive, `versionId`
`6cfffabd-b4f4-46cc-9f3a-ab6dcc4b66ca`, 26 nodes, every node's parameters
equal to `n8n/tqo-v5/doctor-score-only/workflow.json` at `d2183ec`. A further
run finds no eligible row and stops with "No row to score".

## Rulings, in order

Every ruling was answered on a card.

| UTC | Ruling |
|---|---|
| 2026-10-24 10:16 | Create the workflow inactive; run TQO 49 first; fix the live `Script: Hydrate from Row`, draft and publish; record the Sources Gate finding only |
| 2026-10-24 11:22 | Fix the prompt's checklist line and re-score 49; give the live Build Doctor Prompt the same wording, draft and publish |
| 2026-10-24 11:59 | Ground the doctor with measured facts, then measure; clear row 49's wrong 58 line; audit the live doctor's past repairs, reads only |
| 2026-10-25 00:26 | Go, run the three measurement runs |
| 2026-10-25 00:36 | Three reads per row, the strictest one holds; first person that only addresses the viewer stands, both shows |
| 2026-10-25 02:48 | Measure 49, then score all 20 |
| 2026-10-25 02:57 | Sharpen the voice ruling and re-measure 49; quote the doctor's dashes as written and say how many |
| 2026-10-25 06:44 | Measure 49; if no read marks the viewer line down, write 49 alone, then the other 19 |

## Executions

All on `wwjYsar6zRS6ZeD0`, mode manual, status success.

| Execution | Started | Body | What it did |
|---|---|---|---|
| 4292 | 2026-10-24T10:17Z | first build, one read | Wrote row 49 NEEDS_REVISION 75. The prompt said "CHECKLIST: (none returned)" because no TQO row stores a checklist, and the top diagnosis asked for a checklist the script speaks |
| 4300 | 2026-10-24T11:30Z | checklist wording fixed | Wrote row 49 NEEDS_REVISION 58. The doctor guessed the learning objective sat past 30 seconds when it starts at word 31, and took the LEARNING OBJECTIVE field line for a second copy in the script |
| 4354, 4355, 4356 | 2026-10-25T00:27Z | grounded, measurement, one read | Row 49 scored 85, 100 and 90 on the same request. Nothing written |
| 4364 | 2026-10-25T02:49Z | three reads, voice ruling | Row 49 read PASS 96, PASS 100, NEEDS_REVISION 85. The 85 read took "the person who has spent years" for Terrance. Nothing written |
| 4381 | 2026-10-25T06:45Z | sharpened ruling, measurement | Row 49 read NEEDS_REVISION 72, PASS 92, PASS 100. No read marked the viewer line down. Nothing written |
| 4382 | 2026-10-25T06:45Z | real body | Wrote row 49 |
| 4383 | 2026-10-25T06:46Z | real body | Wrote the other 19 |

The two wrong lines on row 49, from 4292 and 4300, were cleared by row id at
11:27Z and 12:00Z on 2026-10-24, each after a dry run. Each clear set row
49's `score_history` and `last_feedback` back to null, and the snapshots
either side show no other cell in the 60 TQO rows changed.

In 4381 and 4382 every read that names the viewer line lists it under
PRESERVED. The lowest read in both runs held row 49 for its spoken steps
reading as a list rather than for the voice.

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
  The person in that line is the viewer, not Terrance.
- Each row is read three times. The lowest score is written, and the verdict
  is PASS only when all three reads pass at 90 or above. A failed read writes
  nothing for that row.
- The doctor's words are quoted as written. When they carry em or en dashes,
  the note ends by saying how many.

## Per row

Scores are the three reads in order. Under the strictest-of-three rule a
single PASS under 90 holds the row, as on TQO 55, TQO 60 and NCO 36.

| Row | Title | Reads | Written | Gate |
|---|---|---|---|---|
| TQO 49 | Your Experience Needs Evidence | NR 81, PASS 100, PASS 100 | NR 81 | held |
| TQO 50 | Before You Learn Code, Map the Work | PASS 100, 100, 100 | PASS 100 | clears |
| TQO 51 | Which Parts of Your Boss's Job Can AI Actually Do? | PASS 100, 100, 100 | PASS 100 | clears |
| TQO 52 | Automate One Task. Measure the Whole Cost. | NR 81, PASS 96, PASS 95 | NR 81 | held |
| TQO 53 | Two Responses to the Same AI Change | NR 78, NR 76, PASS 92 | NR 76 | held |
| TQO 54 | Audit Your Tasks Before You Judge Your Career | NR 45, NR 63, NR 85 | NR 45 | held |
| TQO 55 | Write the Brief Before You Build the Agent | PASS 100, PASS 96, PASS 87 | NR 87 | held |
| TQO 56 | Rewrite Your Resume Around Evidence | PASS 100, PASS 100, NR 91 | NR 91 | held |
| TQO 57 | Who Decides What Happens to Your AI Savings? | PASS 100, PASS 90, NR 88 | NR 88 | held |
| TQO 58 | An AI Audit Cannot Tell You Your Salary Is Safe | NR 86, PASS 100, PASS 93 | NR 86 | held |
| TQO 59 | Learn Enough Code to Check the Work | PASS 100, 100, 100 | PASS 100 | clears |
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
changed vs pre-run snapshot: 20 | anything else changed: []".

TQO 54 is the one hold with a source question in it. The script says the
International Labour Organization and NASK published a global index of
occupational exposure to generative AI in May 2025. The row's brief reads
"APPROVED SOURCES: none. No figure, percentage, dollar amount or named study
may stand." So the hold is right under the brief. The doctor's word for it,
"invented", is not: the ILO lists the paper as Working Paper 140, "Generative
AI and Jobs: A Refined Global Index of Occupational Exposure", at
ilo.org/publications, read 2026-10-25. Whether to approve that source or cut
the sentence is a content call.

## Live changes to TQO FINAL V5

Two one-line node changes, each published on Tee's card and read back:
`activeVersionId` equal to `versionId`, every active node equal to the draft,
only the one node different from the version before.

| Node | Before | After | Rollback |
|---|---|---|---|
| `Script: Hydrate from Row` | `9f80c967` | `bdb59b09` | publish `9f80c967` |
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
candidate re-measured each one at `7d57ca6`: 30 confirmed, none refuted,
none unsettled.

The repair kept all three promises. The learning objective is spoken word for
word, once, ending at word 58. All five checklist steps are spoken in the same
words and order. The closing comment question is unchanged and last.

It removed what the brief forbids. The invented first person claim is cut,
and the named five part framework "Operator Test" is gone from the script.

It also cut more than any rule asked. The five defining questions and the
roadmap sentence of the test paragraph are deleted, which leaves a dangling
"each question" and no explanation of the five parts. The b-roll it returned
still names "Operator test checklist".

It missed four things. "What I call the quiet move" stayed, against its own
note that no first person would remain. Three em dashes in the draft went
unflagged and two survived its repair, until a later step fixed them. It
passed a GMAC attribution that the approved quote does not contain. It left
"fifteen minutes", and the Sources Gate then failed the row on that word. The
row went to Error.

## The Sources Gate, offline

Recorded only, on Tee's ruling. The live Sources Gate, run offline on the
twenty rows as they stood before any doctor line, fails eight:

| Row | Flag | Script context |
|---|---|---|
| TQO 49 | figure "A third" | "Another leaves out the delivery date. A third asks the team" |
| TQO 50 | figure "A third" | "Another is a request for more information. A third is an escalation." |
| TQO 54 | figure "2025" | "In May 2025 the International Labour Organization and NASK published" |
| TQO 59 | figure "twice" | "What happens if the request arrives twice?" |
| NCO 30 | attributed to "Soldier" | "A newer Soldier may not know which materials" |
| NCO 31 | figure "sixty" | "We are using sixty seconds as a rehearsal exercise." |
| NCO 33 | figures "A third", "A fourth"; attributed to "Soldier" | "ask whether the Soldier with a problem knows how to report it" |
| NCO 37 | attributed to "Someone", "Somebody" | "Someone says it is probably complete." |

TQO 54 is the one real flag, the named study with no approved source. The
other seven are an ordinal, a count, a frequency or a character in the story.
The gate was not changed. Which of these rows will pass through it in TQO FINAL
V5 is not measured here.

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
  test reads only its Script Gate window and normaliser, which match.

## Verification

Each build behind these runs went through independent verifiers before it ran
on the instance: `7d57ca6` (grounding), `31e0f73` and `6305cda` (three reads
and the voice ruling), `e0351e1` and `d2183ec` (the sharpened ruling and the
dash count). Their findings are fixed in the commits that follow each one.

Two refuting verifiers were started at 2026-10-25T06:48Z on the run itself:
one on run integrity (the 20 appends, the lines against Compose Write, the
minimum and the strict verdict recomputed from the raw replies, the gate
clearing exactly TQO 50, 51 and 59, the dash counts) and one on three content
patterns in the replies. When this doc was first committed neither had
reported, so everything above rests on the saved execution files and the
table diff read in this session. Their verdicts are added to this section
when they report.

## Open

- Give the live doctor in TQO FINAL V5 the voice ruling and the measured
  learning objective line. Both are proven only on the score-only lane.
- The seventeen held rows. The scores say what the doctor sees; revising the
  scripts is a separate ruling.
- TQO 54's source: approve ILO Working Paper 140 for that row, or cut the
  sentence.
- The live doctor over-cut on TQO 5, and its two other repairs left no data to
  read.
- The seven Sources Gate false positives.
- The three parser gaps and the stale export above.

## DEVON RECEIPT

AREA: TQO, NCO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_score-only-doctor-twenty-rows_v1_2026-10-25-0654.md
DATE: 2026-10-25
DECISIONS: Tee ruled on cards: score only, never rewrite; create the score-only workflow inactive and run it by hand; ground the doctor with the learning objective's measured position and the brief's lines; three reads per row, the strictest holds; first person that only addresses the viewer stands, both shows; quote the doctor's dashes as written and count them; publish the Hydrate and checklist one-line fixes to TQO FINAL V5; record the Sources Gate finding only.
FINDINGS: All 20 rows written, appends only, nothing else changed; TQO 50, 51 and 59 clear at PASS 100, 17 held from 45 to 91. One read of the same request moved from 85 to 100 to 90, which is why three reads hold. The live doctor's TQO 5 repair kept the three promises and cut more than any rule asked. The Sources Gate fails 8 of 20 offline, one real. TQO 54's named study exists and is unapproved for the row.
OPEN: Voice ruling and grounding for the live doctor; the 17 held rows; TQO 54's source; the live doctor's over-cutting; seven Sources Gate false positives; three parser gaps; the stale export.
STATUS: Scoring complete and read back. TQO FINAL V5 live on fd873714. PR #416 open at d2183ec.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
