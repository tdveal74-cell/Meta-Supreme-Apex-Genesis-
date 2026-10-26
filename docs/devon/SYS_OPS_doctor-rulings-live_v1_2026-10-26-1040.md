# Doctor rulings carried to the live doctor

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q. This arc ran
2026-10-25T22:13Z to 2026-10-26T10:40Z. It follows
`SYS_OPS_score-only-doctor-twenty-rows_v1_2026-10-25-0654.md` and works its
Open list. Every state fact below was read on the date it carries: the n8n
workflow and table facts from the instance's public REST API, the execution
facts from the saved execution JSON of each run.

## Result

The live script doctor in `TQO FINAL V5` (`qEkGOUsNyVaRAmm6`) now carries
the wording and the checklist parse that the score-only lane measured: the
grounding, the NCO sentence, the NCO rubric clauses and the parse. It also
carries a TQO description change in `Script: Fill Run Fields`, which the
score-only lane has no node to test and which rests on fixture checks. Both
went out in two publishes on Tee's cards, each read back. No live run has
reached any of the changed nodes since: executions 4539 at 10:20Z and 4541 at
11:00Z ran 7 and 4 nodes, none of them changed, and found no work.

At 2026-10-26T09:04Z, `dcc44552-a7bc-4a4a-89b8-5b119e7d9470` changed three
nodes and added a fourth, `Doctor: Ground the Request`, relative to
`fd873714`. `Token Budget: Doctor` now feeds the new node, which feeds
`Run Script Doctor (Cerebras)`. The changes are the doctor grounding with the voice ruling and the
measured learning objective line, the NCO sentence on the comments question
and the subscribe close, the checklist parse in Hydrate, and the checklist
block in the episode description.

At 2026-10-26T10:39Z, `fc75f7a6-7947-402c-9bf2-2396bd866b12` changed one node
from `dcc44552`: for NCO, the "No engagement bait" line and the "close 15" line
each end with a clause saying one specific question for the comments is
allowed. On NCO 30, measured on the score-only lane before the publish, the
reads that called its closing comments question bait went from two of three in
execution 4512 to none of three in execution 4531. That is one row, three
reads each, with the two clauses the only difference between the two requests.
It has not been measured on the live doctor.

Rollback: publishing `dcc44552` undoes the second; publishing `fd873714` undoes
both.

No held row is released by any of this. Five rows were re-scored, seven times
in all, each after a change that bore on it, and each is still held. Each of
those five holds names the doctor's rubric, mostly a missing dramatic question
or a flat middle, and not a missing input. Two of the 17 held rows were not
re-scored and are held only because one PASS read scored under 90: TQO 60
(PASS 100, 88, 96, no breach named by any read) and NCO 36 (PASS 83, 94, 95,
an empty diagnosis for the 83 read).

## Rulings, in order

Every ruling was answered on a card, except the 07:35Z "Ok", which Tee typed.

| UTC | Ruling |
|---|---|
| 2026-10-25 22:13 | NCO may end on a specific comments question; overrule the 2026-09-08 cold-open record; give the live doctor the voice ruling for both shows, the measured learning objective line for TQO, the only show with a learning objective, and for both shows the line saying which lines are the brief and which are the script; enter the ILO release as TQO 54's source and ATP 6-22.1 as NCO 32's |
| 2026-10-25 23:22 | Go on the three n8n writes; keep NCO's subscribe close; re-write the cold-open record as overruled; fill the TQO checklist column |
| 2026-10-26 05:00 | Fill the column with JSON arrays and parse them in Hydrate, both lanes; add the checklist to the description in Fill Run Fields; prove the carousel fix with one dispatched run after merge |
| 2026-10-26 07:35 | "Ok", typed in answer to a message saying the writes his cards had approved waited on his next answer |
| 2026-10-26 09:03 | Publish `dcc44552` now; move the NCO comments clause next to the two rubric lines that forbid it, both lanes, as a second draft with its own verifier and publish card, then re-score NCO 30 |
| 2026-10-26 09:54 | Keep the bait line's clause as "is allowed and is not bait" |
| 2026-10-26 10:38 | Publish `fc75f7a6` now |

## Table writes

Each write was a dry run first, then the real call by row id. The 22:18,
05:01, 07:37 and 09:20 writes were each followed by a read of both tables. The
22:19 clear was followed by a read of `tqo_content` only. The 05:06 checklist
write was checked against each row's own write response, and the table was
next read at 07:36, where all twelve checklists were equal. No write touched a
column it did not name.

| UTC | Table | Rows | Column | What |
|---|---|---|---|---|
| 2026-10-25 22:18 | `tqo_content`, `nco_content` | TQO 54, NCO 32 | `sources` | One approved source each, with verbatim quotes from the source (three excerpts joined by " / " for TQO 54, one sentence for NCO 32) and `approved_by` naming the card |
| 2026-10-25 22:19 | `tqo_content` | TQO 54 | `score_history`, `last_feedback` | Cleared to null before re-scoring |
| 2026-10-26 05:01 | `nco_content` | NCO 30, NCO 31 | `score_history`, `last_feedback` | Cleared to null before re-scoring |
| 2026-10-26 05:06 | `tqo_content` | TQO 49 to 60 | `checklist` | The four steps each script speaks after "Use four steps.", as a JSON array stored as text; all twelve read back equal |
| 2026-10-26 07:37 | `tqo_content` | TQO 49, 54, 58 | `score_history`, `last_feedback` | Cleared to null before re-scoring |
| 2026-10-26 09:20 | `nco_content` | NCO 30 | `score_history`, `last_feedback` | Cleared to null before re-scoring |

TQO 54's source is the ILO news release of 20 May 2025 on "Generative AI and
Jobs: A Refined Global Index of Occupational Exposure". NCO 32's is ATP
6-22.1, February 2024, read from the Army Publishing Directorate PDF. With its
source entered, the live Sources Gate passes TQO 54, which it failed on "2025"
before.

## The cold-open record

The 2026-09-08 record that the doctor applied to NCO 31 alone is
`3d568ff5-0db6-81ac-b2e4-f817cc57a833-d2` in the `tee-soul-layer` Pinecone
index. Recall serves any record with no status, so a new ruling filed beside it
would not have stopped it. A one-off n8n workflow,
`Ops: overrule soul record 3d568ff5 d2 (one-off 2026-10-25)`
(`5Z7HqAiFxfXf3yHG`), re-wrote it in execution 4472 at 2026-10-25T23:31Z with
`status: overruled`, the text unchanged and every original field kept. The
upsert answered 201, the read back confirmed it, and the workflow was archived.
`n8n/soul-overrule/README.md` has the method. In execution 4512 the overruled
ruling no longer reached NCO 31's request.

## Executions

All on `TQO Doctor: Score Only (hand run)`, `wwjYsar6zRS6ZeD0`, mode manual,
status success. Reads are in order; the lowest is written.

| Execution | Started | Version | Row, what changed | Reads | Written |
|---|---|---|---|---|---|
| 4468 | 2026-10-25T22:19Z | `6cfffabd` | TQO 54, source entered | 94, 95, 95 | NR 94, was 45 |
| 4512 | 2026-10-26T05:01Z | `9bf3e5cc` | NCO 30, NCO sentence | 85, 75, 88 | NR 75, was 70 |
| 4512 | | | NCO 31, record overruled | 72, 83, 90 | NR 72, was 45 |
| 4522 | 2026-10-26T07:37Z | `6821ca7c` | TQO 49, checklist parsed | 93, 68, 95 | NR 68, was 81 |
| 4522 | | | TQO 54, checklist parsed | 88, 100, 100 | NR 88, was 94 |
| 4522 | | | TQO 58, checklist parsed | 85, 100, 77 | NR 77, was 86 |
| 4531 | 2026-10-26T09:20Z | `1cebf726` | NCO 30, rubric clauses | 92, 83, 100 | NR 83, was 75 |

Each run did what it was built to do, and none released a row.

TQO 54's reads went from calling the ILO citation invented to scoring in the
nineties, and then one read held it for a missing checklist. With the
checklist parsed, no read in 4522 called a checklist missing. The written
holds moved to the rubric: in the lowest read of each row, TQO 49 and TQO 54
lacked a dramatic question and TQO 58's middle became flat exposition. One
other read of TQO 49 (93) still marked down the checklist's lead-in, "Use four
steps.", as wording outside the required list; it is not the written read.
All three of those rows scored lower than before: TQO 49 from 81 to 68, TQO 54
from 94 to 88 and TQO 58 from 86 to 77. In these runs the reads of one row
disagree by up to 27 points (TQO 49 in 4522, 68 to 95). Three reads are taken
and the lowest written because the same request scored 85, 100 and 90 in
executions 4354 to 4356 on 2026-10-25.

NCO 30's reads in 4512 said "engagement bait and violates the close rule" and
"engagement bait and violates the NCO Forge rules", citing the rubric lines
rather than the NCO sentence. In 4531, with the clauses in those lines, reads 1
and 2 list the closing question under what they preserve, as allowed for NCO.
Read 3's preserved list does not name it and its diagnosis is empty, but its
reasoning also calls it allowed. The row is held at 83 on its middle section
and its opening question.

## Live changes to TQO FINAL V5

Each change is one directory under `n8n/tqo-v5/` holding the pinned live body
`before.js`, the change, `after.js`, a manifest with both hashes, the version
it went live in and the rollback, and a test. For the NCO sentence, the
checklist parse and the NCO rubric clauses, the score-only build imports the
same replacement file, so both lanes say the same words. The voice ruling and
the learning objective measurement are separate copies in
`ground_request.js` and the score-only `Final Word`; `grounding.test.mjs`
holds them equal, apart from the score-only clause. The description block is
in the live lane only, because the score-only pass never writes a
description.

| Directory | Node | Live in | What |
|---|---|---|---|
| `live-doctor-grounding` | `Build Doctor Prompt`, new `Doctor: Ground the Request` | `dcc44552` | The voice ruling, the measured learning objective line, and the NCO sentence: a specific comments question is not bait, and the writer's one subscribe line is NCO's call to action and stands |
| `live-checklist-parse` | `Script: Hydrate from Row` | `dcc44552` | An array, or text that parses to one, is the checklist; any other value reads as none, as before |
| `live-description-checklist` | `Script: Fill Run Fields` | `dcc44552` | A TQO description gains "The checklist from this episode:" and the numbered steps; an old block is replaced in place; NCO and a run with no steps are untouched |
| `live-nco-close-rubric` | `Build Doctor Prompt` | `fc75f7a6` | For NCO, the bait line ends "For NCO, one specific question for the comments is allowed and is not bait." and the close 15 line ends "For NCO, one specific question for the comments is allowed." |

Draft history: `5edf7d64` carried the grounding, `1b7293dd` added the parse,
`dcc44552` added the description block, and `fc75f7a6` the rubric clauses.
Each draft was read back node for node against the repo before its publish
card, and each publish was read back: `activeVersionId` equal to `versionId`,
the published nodes equal to the read-back draft, and only the named nodes
different from the version before.

The score-only workflow moved `6cfffabd` to `9bf3e5cc` (the NCO sentence in
`Build Doctor Prompt`; the voice ruling and the measured line were already in
`Score Only: Final Word` in `6cfffabd`), `6821ca7c` (parse) and `1cebf726`
(rubric clauses). Each PUT was
read back node for node against `n8n/tqo-v5/doctor-score-only/workflow.json`.
It is inactive and runs by hand.

## The carousel job

`Carousels for review` failed on main in six scheduled runs, 13 to 18, from
2026-10-20 to 2026-10-25: `ubuntu-latest` became Ubuntu 26.04, where Playwright
1.56.1 cannot install Chromium's dependencies. PR #420 pinned it to
`ubuntu-24.04`, the same pin `audio-ci.yml` and `panel-smoke-ci.yml` carry, and
merged as `edf8a65`. Run 19, dispatched on main at 05:03Z after the merge,
succeeded, printed "Drawn 1, refused 0. Nothing here has been posted." and
uploaded the slides as its artifact. No scheduled run has fired since, so the
schedule itself is not yet proven on the new runner. This branch does not carry
`edf8a65`, so its own copy of the workflow file still reads `ubuntu-latest`
until it meets main.

## Gaps found and not fixed

Graded low; no gap here has been shown to change a row's result. Most are not
on a path a row takes today. The Sisinty rulings are: the soul recall served
them into the doctor request on the score-only lane, and the live doctor reads
the same recall.

- The Script Gate checks a row's checklist count, em and en dashes in the
  steps, and the retired free audit's names and addresses in the steps. It
  does not check the steps for a like and subscribe phrase, which it tests on
  the script only, or for any other link, so those would pass it. It checks
  nothing for NCO.
- The writer path never stores the checklist it writes into the column, so a
  row the writer drafts reaches a later re-score without one.
- The description block's edge cases need malformed old blocks: CRLF line
  ends, a whitespace-only line, two blocks. With two, the first is replaced
  and the second left, which the test pins. None of the 24 stored
  descriptions has any of these.
- Rulings 4, 7 and 9 of the 2026-09-08 Sisinty filing were served by the soul
  recall in execution 4512, and ruling 7 again in 4531, because their records
  carry no status and the recall treats a missing status as active. Rulings 5,
  11, 13 and 14 of the same filing were served in 4522. Ruling 13 says ruling 9
  is superseded, but record d9 still has no status, so in 4512 it was served
  without the correction. No read marked a row down on any of them. Only ruling
  2, the cold open, was overruled. The index was not re-read after 09:20Z.
- The writer and packaging prompts carry their own "No engagement bait" lines.
  `Series Addendum` allows the closing comments question for TQO only.
  `Build Packaging Prompt` and `Package: Build Prompt` each carry a "No
  engagement bait" line with no clause for a comments question, for either
  show. Separately, `Build Packaging Prompt` tells the writer that each
  LinkedIn post ends on a question that drives comments and asks for a pinned
  comment inviting discussion, for both shows. That is writing text, not the
  doctor, and the card did not name it. If an NCO draft is held for its
  question at the writing stage, `Series Addendum` is the line.
- The rubric guard is `isNCO`. A guard of `show !== 'TQO'` survives every test,
  and differs only if a third show is added.
- `Script: Fill Run Fields` carries a stale `parameters.parameters.jsCode`, an
  older copy n8n does not run. Left as it is.
- `n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json` predates both publishes.

## Verification

Every commit that changed a live node body, the score-only build or a test
went through a refuting verifier in its own worktree at that commit, except
`8d9d01a`, `fb91bd2` and `0f6eef0`, which had none at their own commits.
`8d9d01a` is test pins only and never reached the instance. `fb91bd2` and
`0f6eef0` are in the bodies published as `dcc44552`. `b461e5d` and `b4ac60b`
only record version ids. The table writes and the Pinecone re-write each had a
dry run or a read back, and no refuting verifier before they were made.

| Under test | Found | Fixed in |
|---|---|---|
| `db5fc1b`, grounding and NCO sentence, three verifiers | four gaps in the grounding test; one verifier also measured the conflict, which the author had flagged, between the NCO writer's subscribe line and the sentence's "remove it" | `8d9d01a`; the conflict in `f5f8826`, on Tee's card |
| `f5f8826`, the subscribe close | a "so cut it" mutant passed both tests, and the rubric's "Never a solicitation" could still mark the subscribe line down | `5769ffa` |
| `5769ffa` | "and is never marked down" said more than the card ruled | `fb91bd2` |
| the checklist and carousel findings, two verifiers | confirmed all; measured that no workflow writes the column and that all 24 descriptions lack the steps | |
| `27f3d32`, parse, description and the NCO 30 finding, three verifiers | three parse mutants no test killed; the description block cut an earlier block on every pass | `65556e6` |
| `65556e6` | replacing the block deleted any text after it | `766d867` |
| `766d867` | a comment overclaimed, and which of two old blocks is replaced was not pinned | `0f6eef0` |
| `92f2c86`, rubric clauses | the close 15 clause said "counts as a real action", past the card's "allowed" | `4aea437` |
| `4aea437` | one wording note, that the bait clause's "is not bait" goes past the card's "allowed"; three mutants, including the old wording in one lane only, all killed | none, kept by Tee's ruling at 09:54Z |

`fb91bd2` cut one phrase and `0f6eef0` carried two small fixes to the 766d867
findings. Each test that pins them passed on the unmodified tree in every
verifier run that included it, but not every later verifier ran them. Only the
`4aea437` verifier ran `description_checklist`, which pins `0f6eef0`. Only the
`65556e6`, `92f2c86` and `4aea437` verifiers ran both `score_only` and
`grounding`, which pin `fb91bd2`.

At `b4ac60b`: `nco_rubric` 23, `score_only` 301, `grounding` 101,
`checklist_parse` 50, `description_checklist` 41, `hydrate_fix` 17 and
`checklist_fix` 12 checks pass, and `build.mjs --check` and ruff are clean.

## Open

- The held rows. The five re-scored in this arc (TQO 49, 54, 58, NCO 30 and
  31) are each held on a rubric defect. The other twelve were last scored on
  2026-10-25. Ten of those name a defect. TQO 60 is held at 88 although all
  three reads said PASS, and NCO 36 at 83 by a PASS read with an empty
  diagnosis. Revising scripts is a separate ruling.
- The cold-open record's status in Pinecone, and what lanes other than the
  score-only recall receive, were not re-read after 23:31Z; no key for the
  index is in this environment.
- The gaps above.
- Filing this receipt to DEVON goes through Tee's thread log; the capture key
  is not in this environment.

## DEVON RECEIPT

AREA: TQO, NCO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_doctor-rulings-live_v1_2026-10-26-1040.md
DATE: 2026-10-26
DECISIONS: Tee ruled on cards: NCO may end on a specific comments question and keeps its subscribe close; the 2026-09-08 cold-open record is overruled and re-written as overruled; the voice ruling goes to the live doctor for both shows and the measured learning objective line for TQO; the ILO release and ATP 6-22.1 are entered as sources; the twelve TQO checklists are stored as JSON arrays and parsed in Hydrate, both lanes; Fill Run Fields adds the TQO steps to the description; the carousel fix is proven by one dispatched run; the NCO comments clause sits on the bait and close 15 lines; publish dcc44552 and fc75f7a6.
FINDINGS: TQO FINAL V5 is live on fc75f7a6, read back; no live run has reached the changed nodes yet. On the score-only lane, NCO 30's bait reads went from 2 of 3 (execution 4512) to 0 of 3 (execution 4531), one row, three reads each. With the checklist parsed, no read in 4522 calls a checklist missing; one read still marks down the "Use four steps." lead-in. Five re-scored rows are all still held on the rubric, with reads up to 27 points apart. TQO 60 and NCO 36 are held by a PASS read under 90. The overruled cold-open record reached no request in executions 4512, 4522 and 4531. Carousel run 19 passed on ubuntu-24.04; no scheduled run has fired since.
OPEN: The held rows; the cold-open record's live status, not re-read; Script Gate step words; writer-path checklists not stored; description edge cases; Sisinty rulings 4, 7 and 9; writer and packaging bait lines; the isNCO guard; the stale nested jsCode; the stale export; DEVON filing.
STATUS: Complete and read back. TQO FINAL V5 live on fc75f7a6, rollback dcc44552. Score-only workflow inactive on 1cebf726. PR #419 carries the build and this doc.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
