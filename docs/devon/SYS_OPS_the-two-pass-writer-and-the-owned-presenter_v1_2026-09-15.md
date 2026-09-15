---
title: The two pass writer and the owned presenter
type: SYS_OPS
version: 1
date: 2026-09-15
area: Systems
status: proven on the VPS, worker unchanged, presenter proof pending
owner: DEVON
---

# The two pass writer and the owned presenter

Six rulings, every one taken by Tee on an inline card, and what each one
became on the VPS on 2026-09-15. This document supersedes nothing; it sits
after `SYS_OPS_eight-rulings-and-v5-on-the-vps_v1_2026-09-15.md` and
`SYS_OPS_the-first-vps-watched-run_v1_2026-09-15.md` in the same day.

## The rulings

Tee asked for every ruling as an inline multiple choice card. These are the
cards and the answers, in the order they were put.

| card | answer |
|---|---|
| the Cerebras writer undershoots (894, 798, 1055, 1059, 848 words against a 1200 floor) | two pass expansion on Cerebras |
| captions | Shorts on, long form off, SRT uploaded as a YouTube caption track |
| row 5 of `tqo_content`, on Script Hold with season 1 episode 1 copied from S1E1 | back to Idea, episode 2 |
| the stacked Short caption | zone seam, MarginV 92 |
| an avatar that is free or close to it | lip sync over Tee's own footage; then, asked to choose the tool, "MuseTalk" |
| can DEVON be trained to write scripts | retrieval plus edit capture now, fine tune later |

Runway came up between the last two. The record was checked before answering:
EditForge's live store shows the Runway provider keyed and ready, the
2026-08-27 provider doc mapped lip sync to a "registry-locked Runway custom
avatar" and listed the avatar id as an input still to be supplied, the two live
Runway jobs in the store (2026-08-12) failed with "You do not have enough
credits to run this task", the VPS holds 32 credentials and none is Runway, and
no document names a Runway avatar id. Tee's answer to the Runway card was
"MuseTalk". Runway is out of the presenter path.

## What is live on the VPS

`TQO FINAL V5` (`qEkGOUsNyVaRAmm6`) went through five published versions in
this arc and the active one is `dc5f4f02`. Every version was read back after
publishing by fetching the workflow and diffing nodes and connections against
the previous fetch; the diffs matched the operation lists and nothing else
moved.

| version | what it carries |
|---|---|
| `129d692c` | the two pass writer; long form subtitles removed from Build Movie; the SRT saved on the row |
| `ec87180f` | the dash repair pass after the doctor |
| `4d36d942` | the dash repair prompt with worked examples and the fragment check |
| `3fe913c6` | the DEVON grounded writer: recall step, exemplar fetch, edit capture at Promote |
| `dc5f4f02` | the Script Writer schedule back to disabled (active) |

The script lane now runs: Get Idea Rows, One Idea at a Time, DEVON Recall:
Ask, Fetch Script Exemplars, DEVON Recall: Merge, Build Script Prompt, Series
Addendum, Token Budget: Script, Write Script (Cerebras), Parse Script JSON,
Script: Needs Expansion?, Expand? (IF), Expand Script (Cerebras), Parse
Expanded Script, Build Doctor Prompt, Token Budget: Doctor, Run Script Doctor
(Cerebras), Parse Doctor Output, Dash Repair: Needs?, Repair Dashes? (IF), Dash
Repair (Cerebras), Parse Doctor Verdict, Fetch Prior Episodes, DT Shim: Prior
REST, Originality Scan, Script Gate: Quality, Save Script to Airtable, Save
Doctor Verdict. Parse Doctor Verdict kept its name and became the dash repair
apply step, because Originality Scan and DT Shim: Prior REST read it by name;
the doctor's own parser is now Parse Doctor Output. Nothing downstream was
rewired.

The two pass writer: a draft under 1200 words goes back to the same model with
the same system prompt, the original brief and the draft, and is asked for 1800
to 2200 words with the hook kept verbatim. Parse Expanded Script keeps the
draft if the expansion is truncated, unparseable, or no longer than the draft.

The dash repair: sentences carrying an em or en dash after the doctor are sent
back for restructuring, and each rewrite is applied only if it carries no dash,
keeps the exact sequence of numbers the original carried, matches the source
verbatim, and leaves no sentence under five words. Anything refused is named in
`last_feedback` and the gate holds the script on the dashes that remain. No
dash is ever swapped for a comma by code: Tee's rule is restructure, never swap
the punctuation.

The DEVON grounding: DEVON Recall: Ask calls `GET /api/v1/soul/recall` on
`devon-soul.vercel.app` with the topic and the idea, continues on error, and
DEVON Recall: Merge folds the records and the newest three rows of the new
`script_exemplars` table onto the idea row. Build Script Prompt appends both to
the system prompt when present. Save Script now writes `script_machine`
beside `script`, and in the Promote lane Script Edits: Diff compares the two on
every promoted row and inserts a pair into `script_exemplars` when Tee changed
the text by hand. The gate report carries a `devon:` line naming what the recall
did.

Data changes: `tqo_content` gained `srt` and `script_machine`, `nco_content`
gained `script_machine`, and `script_exemplars` (`k3A66wV0vUoeaElo`) was
created with `source_row_id`, `show`, `topic`, `machine_script`, `tee_script`,
`machine_words`, `tee_words`, `captured_at` and `note`.

## The proof runs, measured

Row 5 was reset to Idea and episode 2 by a throwaway helper before each run.
Each run is a manual execution of the Script Writer trigger, which was enabled
for the run and disabled again in the next publish.

| run | draft | expansion | doctor | dash repair | gate |
|---|---|---|---|---|---|
| 83 | 833 | to 1509 | REPAIRED 82 | none yet | HOLD at 1377 words: 8 dashes, rhythm 45 |
| 85 | 1186 | to 1535 | REPAIRED 80 | 4 restructured, 0 remain | PASS at 1481 words, rhythm 100 |
| 88 | 1085 | to 1397 | REPAIRED 77 | 2 restructured, 0 remain | PASS at 1341 words, rhythm 88 |
| 90 | 1004 | to 1608 | REPAIRED 68 | 8 restructured, 1 remains | HOLD at 1556 words: 1 dash, doctor 68 |

Run 85 cleared the gate and its rewrites had split at the dash and left
fragments ("As a binary switch."), which is why `4d36d942` exists. Run 88's
rewrites read as sentences ("a single task called meeting facilitation",
"such as interpretation, storytelling, empathy"). Run 90 was the proof of the
grounded lane: the recall answered 401, the note landed in the gate report, the
script was still written, and the gate held it on the doctor's own 68, which is
the gate doing its job rather than a fault. Each full lane ran in about ten
seconds on Cerebras.

What the runs did not prove: the prose. Run 88's opening is "Recent analyses
show that a notable share of mid level roles", and run 90's is "a study from
McKinsey noted", and both are the doctor's repair of invented numbers into
vague attribution. Tee's own rule is name the source or cut the claim. The
doctor's prompt says it; the gate cannot measure it. Human Review is the check.

## The recall is switched off by a credential

Probe execution 86 on throwaway workflow `jsODGZCRmPeJDBlS` (archived) called
`/api/v1/soul/status` and `/api/v1/soul/recall` with the VPS credential
`Devon Soul Service Token` (`9meOVz4mM5q4f7BR`) and both answered 401, "That
token is not the one this service expects." The service is up and reports its
own key set; the stored credential is the wrong value or the wrong header. The
fix is Tee's: header name `Authorization`, value `Bearer` followed by the
service's `CONSOLE_TOKEN`. Until then every gate report will say so and the
writer runs without recall.

## The worker and the caption seam

The seam ruling needed no push. `252e4bb`, the head of PR #226, already carries
`MarginV=92` in `jobs.js` and the matching expectation in `jobs.test.js`; the
tree was clean and `git show 252e4bb:deploy/render-worker/jobs.js` says so.
The stacked acceptance render was re-run at that value and the frame at 1.0 s
(`sframe-1.0b.png` in the session scratchpad) shows the caption sitting on the
seam between the payload zone and the head zone, roughly y 1235 to 1305 of
1920, above the presenter's face and inside the spec's band. The PR body's
line saying the seam move was "not in this PR" was wrong and is corrected on
the next push. CI on `252e4bb` is green on all six jobs (GitHub shows seven
check runs; the seventh is the Vercel preview bot) and the PR is mergeable.

## MuseTalk: what was verified and what was not

Verified today, from the repositories: MuseTalk's code is MIT (Tencent Music
Entertainment Group, 2024) and its README says the trained models are
available for any purpose, including commercially; its smallest tested GPU is
an RTX 3050 Ti with 4 GB, fp16, about five minutes for eight seconds; it wants
a 256 by 256 face region and 25 fps. LatentSync's code is Apache 2.0 and its
weights licence on Hugging Face could not be read because the container's
egress policy blocks that host. This container has no GPU (no `nvidia-smi`, no
`/dev/nvidia*`), so nothing has been rendered. `deploy/lipsync/README.md`
carries the recording brief, the 30 second proof steps and the planned worker
job shape, and `deploy/lipsync/musetalk-proof.sh` is the script Tee runs on a
rented pod. The script is written from the README's commands and marked
unverified in its own header; its first run is the proof.

## Housekeeping

Throwaway workflows `fDzWYAL6bTTIfy72`, `D6hHzraGqSbsv2yd`, `6s7rHj5m2jEW1H0E`
and `jsODGZCRmPeJDBlS` are archived. All six V5 schedules are disabled on the
active version, checked by reading each trigger node back after the final
publish. Row 5 stands at Script Hold with the run 90 text and its
`script_machine` copy; the next Script Writer run needs it back on Idea or a
fresh idea row.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-two-pass-writer-and-the-owned-presenter_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: six rulings by Tee on inline cards on 2026-09-15: the writer becomes two pass on Cerebras instead of lowering the floor or moving to Sonnet; captions burn on Shorts and not on long form, with the SRT saved on the row for a caption track upload; row 5 goes back to Idea as episode 2; the stacked caption sits on the zone seam at MarginV 92; the presenter is MuseTalk lip sync over Tee's own footage on a rented GPU, Runway and HeyGen out; DEVON learns to write through retrieval from devon-soul plus capture of Tee's edits, with fine tuning deferred until a corpus exists.
FINDINGS: TQO FINAL V5 active at dc5f4f02 after five published versions, each read back and diffed; proof runs 83, 85, 88 and 90 measured drafts of 833, 1186, 1085 and 1004 words expanded to 1509, 1535, 1397 and 1608, doctor 82, 80, 77 and 68, with the gate passing 85 and 88 and holding 83 and 90 for the reasons its report names; the dash repair rewrote 4, 2 and 8 sentences under a number preserving check and left one dash on run 90; the VPS credential Devon Soul Service Token answers 401 at devon-soul on both status and recall (probe execution 86), so the recall step runs empty and says so; the worker head 252e4bb already carries MarginV 92 and the seam frame was viewed; MuseTalk is MIT with commercially usable weights by its README, LatentSync weights unverified (egress blocked), no GPU in this container; EditForge holds a keyed Runway provider with zero credits and no avatar id on record anywhere.
OPEN: Tee fixes the soul token on the VPS credential; Tee records the presenter takes on the iPhone and runs the 30 second MuseTalk proof on a rented pod, then watches it; Tee deploys the worker build after PR #226 merges; the SRT caption track upload in the publish lane is not built; the writer's vague attribution habit ("recent analyses show") is a Human Review item until a measurable rule exists; the Sisinty long form spec is being written by a background agent and is not yet filed; the TSWS 00 sticky note still says 18 job types; all six V5 schedules stay disabled until Tee's watched pass.
STATUS: proven on the VPS, worker unchanged since 252e4bb, presenter proof pending on Tee. Nothing published to YouTube, nothing merged, nothing deployed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
