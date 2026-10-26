# Doctor rulings carried to the live doctor

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q. This arc ran
2026-10-25T22:13Z to 2026-10-26T10:40Z. It follows
`SYS_OPS_score-only-doctor-twenty-rows_v1_2026-10-25-0654.md` and works its
Open list. Every state fact below was read on the date it carries: the n8n
workflow and table facts from the instance's public REST API, the execution
facts from the saved execution JSON of each run.

## Result

The live script doctor in `TQO FINAL V5` (`qEkGOUsNyVaRAmm6`) now carries
what the score-only lane proved, in two publishes on Tee's cards, each read
back.

At 2026-10-26T09:04Z, `dcc44552-a7bc-4a4a-89b8-5b119e7d9470` changed four
nodes from `fd873714`: the doctor grounding with the voice ruling and the
measured learning objective line, the NCO sentence on the comments question
and the subscribe close, the checklist parse in Hydrate, and the checklist
block in the episode description.

At 2026-10-26T10:39Z, `fc75f7a6-7947-402c-9bf2-2396bd866b12` changed one node
from `dcc44552`: for NCO, the "No engagement bait" line and the "close 15" line
each end with a clause saying one specific question for the comments is
allowed. On NCO 30, measured on the score-only lane before the publish, the
reads that called its closing comments question bait went from two of three in
execution 4512 to none of three in execution 4531.

Rollback: publishing `dcc44552` undoes the second; publishing `fd873714` undoes
both.

No held row is released by any of this. Five rows were re-scored, seven times
in all, each after a change that bore on it, and each is still held. Every hold now names the
doctor's rubric, mostly a missing dramatic question or a flat middle, rather
than a missing input.

## Rulings, in order

Every ruling was answered on a card, except the 07:35Z "Ok", which Tee typed.

| UTC | Ruling |
|---|---|
| 2026-10-25 22:13 | NCO may end on a specific comments question; overrule the 2026-09-08 cold-open record; give the live doctor the voice ruling and the measured learning objective line for both shows; enter the ILO release as TQO 54's source and ATP 6-22.1 as NCO 32's |
| 2026-10-25 23:22 | Go on the three n8n writes; keep NCO's subscribe close; re-write the cold-open record as overruled; fill the TQO checklist column |
| 2026-10-26 05:00 | Fill the column with JSON arrays and parse them in Hydrate, both lanes; add the checklist to the description in Fill Run Fields; prove the carousel fix with one dispatched run after merge |
| 2026-10-26 07:35 | "Ok": carry out the approved writes |
| 2026-10-26 09:03 | Publish `dcc44552` now; move the NCO comments clause next to the two rubric lines that forbid it, both lanes, as a second draft with its own verifier and publish card, then re-score NCO 30 |
| 2026-10-26 09:54 | Keep the bait line's clause as "is allowed and is not bait" |
| 2026-10-26 10:38 | Publish `fc75f7a6` now |

## Table writes

Each write was a dry run first, then the real call by row id, then a read
back of both tables. No write touched a column it did not name.

| UTC | Table | Rows | Column | What |
|---|---|---|---|---|
| 2026-10-25 22:18 | `tqo_content`, `nco_content` | TQO 54, NCO 32 | `sources` | One approved source each, with the page's own quote and `approved_by` naming the card |
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
checklist parsed, no read in 4522 called a checklist missing; the holds moved
to the rubric, "no dramatic question" and "the middle goes flat". Two of those
three rows scored lower than before. The reads of one row disagree by up to 27
points, which is why three reads are taken and the strictest written.

NCO 30's reads in 4512 said "engagement bait and violates the close rule" and
"engagement bait and violates the NCO Forge rules", citing the rubric lines
rather than the NCO sentence. In 4531, with the clauses in those lines, reads 1
and 2 list the closing question under what they preserve, as allowed for NCO,
and read 3 does not mention it. The row is held at 83 on its middle section
and its opening question.

## Live changes to TQO FINAL V5

Each change is one directory under `n8n/tqo-v5/` holding the pinned live body
`before.js`, the change, `after.js`, a manifest with both hashes, the version
it went live in and the rollback, and a test. The score-only build imports the
same replacement file, so both lanes say the same words.

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

The score-only workflow moved `6cfffabd` to `9bf3e5cc` (grounding and NCO
sentence), `6821ca7c` (parse) and `1cebf726` (rubric clauses). Each PUT was
read back node for node against `n8n/tqo-v5/doctor-score-only/workflow.json`.
It is inactive and runs by hand.

## The carousel job

`Carousels for review` failed on main in six scheduled runs, 13 to 18, from
2026-10-20 to 2026-10-25: `ubuntu-latest` became Ubuntu 26.04, where Playwright
1.56.1 cannot install Chromium's dependencies. PR #420 pinned it to
`ubuntu-24.04`, the same pin `audio-ci.yml` and `panel-smoke-ci.yml` carry, and
merged as `edf8a65`. Run 19, dispatched on main at 05:03Z after the merge,
succeeded, printed "Drawn 1, refused 0. Nothing here has been posted." and
uploaded the slides as its artifact.

## Gaps found and not fixed

Graded low; none is on a path a row takes today.

- The Script Gate checks a row's checklist count but not the words of its
  steps, so a subscribe request or a link inside a step would pass it.
- The writer path never stores the checklist it writes into the column, so a
  row the writer drafts reaches a later re-score without one.
- The description block's edge cases need malformed old blocks: CRLF line
  ends, a whitespace-only line, two blocks. With two, the first is replaced
  and the second left, which the test pins. None of the 24 stored
  descriptions has any of these.
- The 2026-09-08 Sisinty rulings 4, 7 and 9 are still active in the soul
  index. Only ruling 2, the cold open, was overruled.
- The writer and packaging prompts carry their own "No engagement bait" lines.
  `Series Addendum` allows the closing comments question for TQO only, and
  `Build Packaging Prompt` and `Package: Build Prompt` allow it for neither
  show. That is writing text, not the doctor, and the card did not name it. If
  an NCO draft is held for its question at the writing stage, those are the
  lines.
- The rubric guard is `isNCO`. A guard of `show !== 'TQO'` survives every test,
  and differs only if a third show is added.
- `Script: Fill Run Fields` carries a stale `parameters.parameters.jsCode`, an
  older copy n8n does not run. Left as it is.
- `n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json` predates both publishes.

## Verification

Every change went through a refuting verifier in its own worktree, given the
claim and the evidence and never the build reasoning, before it reached the
instance. Findings were fixed and the fix verified again.

| Under test | Found | Fixed in |
|---|---|---|
| `db5fc1b`, grounding and NCO sentence, three verifiers | four gaps in the grounding test | `8d9d01a` |
| `f5f8826`, the subscribe close | a "so cut it" mutant passed both tests, and the rubric's "Never a solicitation" could still mark the subscribe line down | `5769ffa` |
| `5769ffa` | "and is never marked down" said more than the card ruled | `fb91bd2` |
| the checklist and carousel findings, two verifiers | confirmed all; measured that no workflow writes the column and that all 24 descriptions lack the steps | |
| `27f3d32`, parse, description and the NCO 30 finding, three verifiers | three parse mutants no test killed; the description block cut an earlier block on every pass | `65556e6` |
| `65556e6` | replacing the block deleted any text after it | `766d867` |
| `766d867` | a comment overclaimed, and which of two old blocks is replaced was not pinned | `0f6eef0` |
| `92f2c86`, rubric clauses | the close 15 clause said "counts as a real action", past the card's "allowed" | `4aea437` |
| `4aea437` | none; three mutants, including the old wording in one lane only, all killed | |

`fb91bd2` cut one phrase and `0f6eef0` carried two small fixes to the 766d867
findings; neither had a verifier of its own. The tests that pin both passed in
every later verifier's run.

At `b4ac60b`: `nco_rubric` 23, `score_only` 301, `grounding` 101,
`checklist_parse` 50, `description_checklist` 41, `hydrate_fix` 17 and
`checklist_fix` 12 checks pass, and `build.mjs --check` and ruff are clean.

## Open

- The held rows. Every hold now names the doctor's rubric. Revising scripts is
  a separate ruling.
- The gaps above.
- Filing this receipt to DEVON goes through Tee's thread log; the capture key
  is not in this environment.

## DEVON RECEIPT

AREA: TQO, NCO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_doctor-rulings-live_v1_2026-10-26-1040.md
DATE: 2026-10-26
DECISIONS: Tee ruled on cards: NCO may end on a specific comments question and keeps its subscribe close; the 2026-09-08 cold-open record is overruled and re-written as overruled; the voice ruling and measured learning objective line go to the live doctor for both shows; the ILO release and ATP 6-22.1 are entered as sources; the twelve TQO checklists are stored as JSON arrays and parsed in Hydrate, both lanes; Fill Run Fields adds the TQO steps to the description; the carousel fix is proven by one dispatched run; the NCO comments clause sits on the bait and close 15 lines; publish dcc44552 and fc75f7a6.
FINDINGS: TQO FINAL V5 is live on fc75f7a6, read back. NCO 30's bait reads went from 2 of 3 to 0 of 3. With the checklist parsed, no read calls a checklist missing. Five re-scored rows are all still held on the rubric, with reads up to 27 points apart. The cold-open record no longer reaches any request. The carousel job is green again on ubuntu-24.04.
OPEN: The held rows; Script Gate step words; writer-path checklists not stored; description edge cases; Sisinty rulings 4, 7 and 9; writer and packaging bait lines; the isNCO guard; the stale nested jsCode; the stale export; DEVON filing.
STATUS: Complete and read back. TQO FINAL V5 live on fc75f7a6, rollback dcc44552. Score-only workflow inactive on 1cebf726. PR #419 carries the build and this doc.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
