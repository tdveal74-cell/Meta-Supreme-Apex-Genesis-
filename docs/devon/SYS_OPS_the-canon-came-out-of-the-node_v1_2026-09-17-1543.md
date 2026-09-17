# The canon came out of the node

Dated 2026-09-17. Tee ruled on a card to migrate the TQO canon rather than close
the arc with two unwired doctrine modules. The canon is now in this repository
twice: mirrored verbatim as the node source that ships it, and expressed as
rules that know whether they bend. A test fails when the two disagree. The live
node is unchanged.

## What was actually in the node, measured

The teardown that started this arc described a `Write Script (Claude)` node
carrying roughly four thousand words. Read from the live public API on
2026-09-17, at workflow `updatedAt` 2026-09-16T14:02:48.875Z, three of those
details are wrong and the structural finding is right.

There is no `Write Script (Claude)` node. The prompt is built in
`Build Script Prompt` and posted by `Write Script (Cerebras)`, with
`Token Budget: Script` converting the Anthropic shaped body in between. The
workflow is 240 nodes, not 212.

The canon is 805 words for TQO and 550 for NCO, against the four thousand
claimed. The node source including the code around both blocks is 1,608 words.
Since the teardown is dated 14 August and the workflow has moved since, the
honest reading is that its figure went stale rather than that it was invented.
Either way the number was the whole cost argument in that section, and it is now
counted from the artifact by `test_the_measurements_match_the_mirror` rather
than quoted.

The canon is also not one undifferentiated block. It already branches on show,
and the taglines were already lifted into `Show Context: Script` as data, which
the node's own first comment calls the identity board. Part of the job the
teardown asked for had already been done by whoever wrote v5.

What the teardown got right is the part that matters. Every line in both blocks
reads as unconditional. Nothing separates the rules that may never bend from the
craft guidance. And until this commit, a change to the prompt that writes every
episode of both shows left no diff in any repository, which is the gap
`n8n/tqo-v5/README.md` was created to name and had closed for exactly one node.

## What landed

`n8n/tqo-v5/build_script_prompt.js` and `show_context_script.js` are the live
node sources, byte for byte as read. `n8n/tqo-v5/README.md` records the read,
the workflow revision and the measurements.

`services/devon/tqo_canon.py` carries the same canon as 19 rules: 7 compliance
and 12 craft. Compliance covers the banned dashes, the owned presenter, no
stolen valor, sourced claims, the crisis support resource, no named person in a
negative light, and archival only military b-roll. Four of those seven come from
the QC gate's hard blockers rather than from the script prompt, which is worth
noticing on its own: the rules that hold an episode were written into the gate
and never into the thing that writes it.

Ten of the twelve craft rules carry no exception yet. That is reported by
`RuleLedger.unqualified` rather than hidden, because the number is the honest
measure of how much of this canon is still absolute purely because nobody has
hit the case.

## The contradiction the split found on its first pass

The NCO branch instructs the model to emit `NCO Forge`, an em dash, and the
tagline, described in the prompt as "this exact line", in the description of
every episode. Hard rule 1 bans that mark studio wide with no exceptions, and
`Build QC Prompt` in the same workflow caps the voice dimension at 3 for any
occurrence and requires it in the findings. An NCO episode that follows its own
script prompt exactly is built to be marked down by its own quality gate.
Seventeen banned marks are in that node in total.

Whether any of this reached a published description is not established, and the
first check run at it was close to vacuous. The `nco_content` data table holds
25 rows and not one carries a description, and `tqo_content` holds 45 rows with
two descriptions between them, neither carrying a banned mark. So the clean
result came from absent data rather than from clean data, and it is recorded
that way. Latent in source, unproven in output.

## What was deliberately not done, and what Tee then ruled

The assembled rule set is not wired in front of the model call. Sending it in
place of the block that ships today changes what the audience receives, and the
teardown puts that behind a blind comparison of ten scripts scored against the
existing rubric. That stays unwired, and Tee ruled it the next arc.

The dash contradiction was put to him on a card in the same breath and he ruled
to fix all seventeen. That was done the same day and is recorded in
`SYS_OPS_the-dash-contradiction-was-fixed-in-the-live-node_v1_2026-09-17-1652.md`,
which supersedes this document on that one point.

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-canon-came-out-of-the-node_v1_2026-09-17-1543.md
DATE: 2026-09-17
DECISIONS: Tee ruled on a card to migrate the canon rather than close the arc with unwired doctrine, and to hold PR #268 open and stack the migration on the same branch so the doctrine and its first real use land together. Mine: mirror the node before expressing it, so the canon is checked against an artifact in the repository rather than against a live read nobody can reproduce; trace every rule to a distinctive phrase in that mirror and fail the build when one stops matching, rather than trusting a copy; leave the live node unchanged, because wiring the assembly changes what publishes and is a write to an active workflow; and test the dash finding as a working detector rather than by pinning the live count of 17, which would have failed the day the node is fixed.
FINDINGS: The teardown's node name, node count and word count are all wrong against a 2026-09-17 read: there is no Write Script (Claude) node, the workflow is 240 nodes not 212, and the canon is 805 words for TQO and 550 for NCO against roughly four thousand claimed. Its structural finding holds: no exception layer, no compliance split, no diff. The NCO branch mandates an em dash in every episode description while hard rule 1 bans it studio wide and the QC gate in the same workflow caps voice at 3 for any occurrence, so an NCO episode that obeys its own prompt is built to be marked down by its own gate; 17 banned marks are in that node. Four of the seven compliance grade rules exist only in the QC gate and were never written into the prompt that does the writing. Ten of twelve craft rules carry no exception yet. The v5 author had already lifted the taglines into a context node, so the identity board pattern the teardown recommends was already in place.
OPEN: The assembly guard is not in front of the model call, so nothing about how the prompt is built has moved. The dash contradiction was ruled and fixed the same day, which this document's own body records and the 1652 doc carries the receipts for. The assembly guard is not in front of the model call, and wiring it needs the blind ten script comparison the teardown specifies plus authorization to write to an active workflow. Whether the mandated dash ever reached a published description is unknown and cannot be settled from the n8n data tables, which hold no NCO descriptions at all; the Airtable store the teardown counted was not read in this session. The rest of the QC chain, Token Budget: QC, Run QC (Cerebras) and Parse QC + Set Verdict, is still live only and unmirrored, as are 237 of the 240 nodes. The two Vercel statuses on PR #268 are an account level block, established as reproducing on the base and clearable only by Tee.
STATUS: On branch claude/review-incorporate-feedback-ke22i8, PR #268, held open on Tee's ruling to merge after this migration. Measured on the final tree: 13 canon tests pass; two mutations of the mirror, an edited rule phrase and a removed dash, each produced named failures and were reverted; the standalone job reproduced with PYTHONPATH unset and the full api suite results are recorded on the pull request. Not shipped, not merged, awaiting Tee.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
