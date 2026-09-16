# The QC gate called his own receipts invented

2026-09-16. The 6:00pm pass held S1E1 on two blockers. One was real. The other
was the gate misreading the thing that makes the channel worth watching.

## What it did

QC scored the episode 75 out of 100 against a ship threshold of 80, graded
evidence 6 out of 15, and threw a hard blocker:

```
- an invented or unverifiable statistic presented as fact
```

The finding named the numbers it objected to: "five statements, thirteen
webhook doors, fifteen, forty one checks". Every one of those is real. They are
the contents of the first law table in this repository's own CLAUDE.md and the
Soul tile arc that closed the same week. The script says where they came from,
in the script: "I kept the log in the repository, dated, with the numbers in
it."

So the gate took the most heavily sourced script the lane has produced and
failed it for being sourced in the only way this channel can source anything.

## Why

One line in the rubric:

```
evidence 15: specific and checkable. Deduct hard for any statistic, date or
attribution that appears invented or unverifiable.
```

To a model reading from outside, a first person count is unverifiable. It has
no external authority behind it. "I counted thirteen webhook doors, there were
fifteen" and "experts say 73 percent of teams" land in the same bucket, and the
blocker fires on both. The rule was written to stop the second and had no way
to tell them apart.

## The fix

The evidence dimension now says what evidence is on this channel: first person
primary observation, with the file, date, execution id or log named, scored
high. It tells the reader it is judging whether a claim is sourced or floating,
not standing in as the fact checker for claims it cannot reach.

The hard blocker was narrowed to what it was for, and split so the real failure
is named rather than implied:

```
- an external statistic, study or survey presented as fact with no named
  source, including the experts say, studies show and reports suggest pattern
- a fabricated date, a misattributed quote, or a figure the script itself
  contradicts
```

That is stricter in one direction and looser in the other. The unsourced
outside claim, which tee-voice already bans, was never explicitly blocked
before and is now. The author's own measurement is no longer treated as
invention.

A third line tells the gate what `claims_needing_check` in the manifest is:
his own pipeline marking first person claims for verification before publish.
Its presence is provenance. The old gate was reading that list as a confession.

## Measured, not asserted

A throwaway harness on the VPS fed row 4 through the real chain and nothing
else: the data table row, the alias shim, the four upstream nodes the prompt
builder reads, `Build QC Prompt`, `Token Budget: QC`, the live Cerebras call on
the real credential, and `Parse QC + Set Verdict`. No publish path existed in
it. Row 4 carries Human Review yes, so running the real pass to test this could
have published to YouTube, which is why it was not used.

| execution | prompt | verdict | score | evidence | packaging | hard blocker |
|---|---|---|---|---|---|---|
| 205 | old | HOLD | 76 | 6 | 7.3 | yes |
| 204 | new | SHIP | 91 | 13 | 6.3 | no |
| 206 | new | SHIP | 100 | 15 | 7.8 | no |

The control run is the part that matters. Run 205 reproduced the original
failure on the old prompt: 76 against the live pass's 75, evidence 6 both
times, the same blocker text. So the change is the cause and not model drift.

The new gate's evidence finding is the one a good editor would give: the logs
are evidence, now cite the file path and the commit hash.

## The other thing that table shows

Packaging came back 7.3, 6.3 and 7.8 on identical input, and the live pass
recorded 6.1. That is a spread of 1.7 points on a number whose gate floor is
7.0. Nothing in part B was changed between those runs.

So the asset native fit gate is deciding hold or ship on a figure that moves by
more than the distance to its own threshold. Row 4 would pass or fail that
floor depending on which run it got. That is a coin flip wearing a number, and
it is a separate problem from the one fixed here. It is recorded rather than
fixed because the remedy is a ruling: raise the sample, lower the floor, or
stop gating on a graded opinion.

## What this does not clear

The dashes are real. Eight en dashes sit in row 4's packaging, mostly in the
chapter list, and the voice rule forbids them absolutely. That blocker is
correct and still holds the row. Fixing the gate was never going to clear it.

## Where the gate now lives

`n8n/tqo-v5/build_qc_prompt.js`. Until today the workflow that decides what
publishes was versioned nowhere, so a change to the rule that holds or ships an
episode left no diff and no review. One node is mirrored now, the one that was
changed, and the README says plainly that the rest of the chain is still live
only.

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-qc-gate-called-his-own-receipts-invented_v1_2026-09-16a.md
DATE: 2026-09-16
DECISIONS: Tee ruled to fix the QC gate rather than override it for one episode, on the reading that the same hold would return on every well sourced script. The evidence dimension now scores first person primary observation high and names what it is not judging. The hard blocker was narrowed to an external claim with no named source and split so a fabricated date or a self contradicting figure is named separately. Packaging grade instability is recorded and left for Tee, because the remedy is a ruling rather than an edit.
FINDINGS: The 6pm pass held S1E1 at 75 of 100 with evidence 6 of 15 and a hard blocker reading "an invented or unverifiable statistic presented as fact", naming numbers that are all real and sourced from this repository's own first law table. The rubric could not distinguish a first person count from an unsourced external statistic. Measured on a throwaway VPS harness with no publish path: the old prompt reproduced the failure at HOLD 76 evidence 6 with the same blocker, and the new prompt returned SHIP 91 evidence 13 and SHIP 100 evidence 15 on identical input, so the prompt is the cause and not model drift. Packaging graded 7.3, 6.3 and 7.8 across those same three runs against a live record of 6.1, a 1.7 point spread on a gate whose floor is 7.0. TQO FINAL V5 was versioned nowhere before today.
OPEN: The packaging grade is not stable enough to gate on at a 7.0 floor and needs Tee's ruling on raising the sample, lowering the floor, or not gating on a graded opinion. Row 4 is still held by eight en dashes in its packaging, which is a correct blocker. Only one of the four QC chain nodes is mirrored into the repository. Row 4 carries Human Review yes, so the next scheduled pass can publish it to YouTube once the dash blocker clears.
STATUS: The gate is fixed live on TQO FINAL V5, republished as activeVersionId 23735e68, proven by a three run A/B against the real model on the real credential, and the changed node is versioned in the repository for the first time.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
