# The dash contradiction was fixed in the live node

Dated 2026-09-17. Tee ruled on a card to fix all seventeen banned marks in
`Build Script Prompt` rather than only the one that reaches an audience. The
live node was edited the same day, read back byte identical, and the mirror and
its tests moved with it. This is the first live write this arc made to the
workflow that publishes both shows.

## What was wrong

The NCO branch of `Build Script Prompt` instructed the model to emit
`NCO Forge`, an em dash, and the tagline, described in the prompt as "this exact
line", in the description of every episode. Tee's first hard rule bans that mark
studio wide with no exceptions. `Build QC Prompt`, a node in the same workflow,
caps the voice dimension at 3 for any occurrence and requires it in the
findings. An NCO episode that followed its own script prompt exactly was built
to be marked down by its own quality gate.

Seventeen marks were in the node in total, across sixteen lines. One of them
reached an audience. The other sixteen sat in the prompt's own instructional
text, telling a model in prose punctuated one way to write output punctuated
another.

## What was done

Every one restructured into sentences, never given a substitute mark, which is
what hard rule 1 asks for. `THE FIVE PILLARS, pick the one` became
`THE FIVE PILLARS. Pick the one`. The receipt clause in the NCO beat structure
became `every claim gets a receipt, and a receipt is a number, a documented
case, or a step the viewer can verify`. The mandated description line became
`NCO Forge. ${ctx.tagline}`, which renders as "NCO Forge. Leaders aren't born.
They're forged." The NCO opener now matches the shape the TQO branch already
used, a period rather than a dash, so the two branches read the same way.

Nothing else changed. The diff is sixteen lines, all of them string content.

## How it was checked before it went anywhere near production

The edited node was run as JavaScript with the n8n helpers stubbed and the real
`Show Context: Script` output fed in, for both shows. Both prompts rendered with
zero banned marks. The same harness was run against the pre-fix source as a
negative control and rendered fourteen dirty lines in the NCO prompt, so the
check can fail. `node --check` passes.

The write itself refused to proceed unless the live workflow still carried
`updatedAt` 2026-09-16T14:02:48.875Z, the revision the mirror was taken from,
and unless the live node body was byte identical to the file that was edited.
Both held. A full copy of the workflow was saved before the write.

## The read-back

This estate has a logged instance of `update_workflow` reporting a patch applied
that never persisted, and it is one of the seven stale artifact shapes carried
in `services/devon/flagship.py`. So the write was read back rather than
believed.

| check | result |
|---|---|
| `updatedAt` after write | 2026-09-17T16:40:13.408Z |
| live node body against the mirror | byte identical, sha256 6403b3c1f204e3b5 |
| banned marks in the live node | 0 |
| nodes | 240 before, 240 after |
| nodes whose definition changed | exactly one, `Build Script Prompt` |
| connections | identical to the pre-write copy |
| workflow active | true, unchanged |

## What this does not prove

No episode has been written since the edit. The next scheduled script run is the
first real exercise of the changed prompt, and nobody has read a script produced
by it. The fix is proven at the level of the prompt text and the node that holds
it, not at the level of an episode.

Whether the mandated mark ever reached a published description was never
established and cannot be from the n8n data tables: `nco_content` holds 25 rows
and not one carries a description. The clean result there came from absent data
rather than clean data.

## DEVON RECEIPT

```
AREA: NCO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-dash-contradiction-was-fixed-in-the-live-node_v1_2026-09-17-1652.md
DATE: 2026-09-17
DECISIONS: Tee ruled on a card to fix all seventeen marks rather than only the description line that reaches an audience, and separately ruled the next arc to be wiring the assembly behind the blind comparison. Mine: restructure every line into sentences rather than substituting another mark, because hard rule 1 asks for restructuring; make the NCO opener match the period the TQO branch already used rather than inventing a third shape; refuse the write unless the live workflow still carried the revision the mirror was taken from and the live node body was byte identical to the file edited; save a full copy of the workflow first; and read the write back rather than trusting the API response, because this estate has a logged instance of a patch reported applied that never persisted.
FINDINGS: Seventeen banned marks across sixteen lines in Build Script Prompt, one of which mandated the mark in every NCO episode description while the QC gate in the same workflow caps voice at 3 for any occurrence. Restructuring changed the NCO block from 550 words and 3,543 characters to 543 and 3,558, and the TQO block from 805 and 4,822 to 805 and 4,831. The pre-fix NCO prompt rendered fourteen dirty lines under a stub harness, which is what makes the post-fix zero meaningful rather than vacuous.
OPEN: No episode has been written since the edit, so the changed prompt is unexercised and no human has read a script produced by it. Whether the mandated mark ever reached a published description is unestablished and cannot be settled from the n8n data tables, which hold no NCO descriptions at all. The assembly guard is still not in front of the model call, which Tee ruled as the next arc behind a blind ten script comparison. 237 of 240 nodes remain unmirrored.
STATUS: The live node is fixed and read back byte identical at 2026-09-17T16:40:13.408Z. The repository side is on branch claude/review-incorporate-feedback-ke22i8, PR #268, not merged. Locally 14 canon tests pass, two mutations of the new guards each produced named failures and were reverted, and the standalone and full api suite results are recorded on the pull request. Not merged, awaiting Tee.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
