# NCO Forge held to the sources standard, and the real source of row 46's inventions

This follows `SYS_OPS_sources-on-the-row_v1_2026-10-07-1241.md`, which PR #313
merged as `2351e38` on Tee's word. Two things changed after it: Tee asked whether
NCO Forge had the same rules and whether the scripts were presenter led, and a
fresh critic graded the merged work PASS-WITH-CONDITIONS with nine findings.
Every change below was ruled on a card.

## What the earlier record got wrong

That doc said the writer cited row 46's four sources and then invented a 150
person division, an HR director interview and a 300 person plant. The critic
traced execution 2351 node by node and the writer did not. Its first pass was
769 words carrying only sourced numbers. The expansion step that lengthens
short drafts added every one of the inventions, because both expansion prompts
and the length line asked it to lengthen each section with "a concrete example
... or a number". Most drafts go through expansion, so most scripts would have
kept failing.

The same doc said the year was kept. In 2351 the 2023 Bloomberg figure was
narrowed to tech and moved to "last year". It also called 2350's spend 10
credits without a reading to prove it; execution 2355 read 1,263 against 2350's
1,273, so the figure was right and is now measured.

## The fixes, published as V5 `d7f4d56f`

- The expansion prompts and the length line now ask for a mechanism, a step or
  a closer reading of a figure already in the draft, and forbid a new number,
  company, person, study, interview or case.
- The Sources Gate reads numbers from each source's clean quote and claim. A raw
  quote's link URL had lent it 30, 03, 15 and 2024, and "30 minutes" passed in
  2351. It now also refuses spelled out figures, an unnamed firm or study that
  reported something, an unapproved name followed by found or predicts, and a
  mismatched unit.
- `Save Doctor Verdict` reads the Sources Gate, so the feedback no longer says
  Cleared for Promote on a row the gate held.
- The writer is told to end TQO scripts on one question for the comments.
- NCO Forge: the three sources nodes and `Package: Plan Batch` hold NCO rows to
  the same rule, `nco_content` has the two columns, and the new `NCO Presenter
  Rule` tells the NCO writer that Terrance presents on camera in his own
  likeness and cloned voice. The NCO prompt block had described a single
  narrator, which is the retired faceless framing.
- The two Save nodes are renamed for the data tables they write to. Fifteen
  nodes still call the Airtable API; Tee ruled they move in the stage split.

TQO Research, now `964214fc`, reads both tables, two rows per show, briefs the
doctor for the right channel, writes back to the row's own table, dates every
note and leaves a row that found nothing alone for seven days. A page naming
itself as the origin of a figure it credits to unnamed research is refused.
Test copy execution 2355 researched NCO row 26 and the doctor rejected three
vendor sources; the copy was archived after the live workflow took its graph.

## What the two test runs showed

Execution 2356 expanded 936 words to 1,656 with no new figure and passed the
Sources Gate with nothing unsourced, failing only the close. Execution 2357
passed the close and the gate, then failed the 1,200 word floor at 1,124: the
expansion reached 1,292 and the doctor trimmed it afterwards. The second
expansion is decided before the doctor runs, which is an older gap and is open.

Tee ruled row 46 keeps the 2356 script with the close made a question. The
hand edits are logged in `last_feedback`. Cut as unsupported by the four
sources: the Korn Ferry respondents' industries, a "common thread" behind the
cuts, a quote put in the mouth of unnamed senior leaders, two sentences giving
a cause for Gartner's projection, and "the evidence shows". Bloomberg's "bore
the brunt" was restated as one in three. The result passes the Sources Gate and the close rule at 1,510
words and reads Scripted, waiting for his review; `script_machine` keeps the
machine text.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_nco-sources-and-the-expansion-fix_v1_2026-10-07-1316.md
DATE: 2026-10-07
DECISIONS: Tee ruled on cards: merge PR #313; NCO Forge held to the same sources standard as TQO; NCO presenter led like TQO; Airtable moves out stage by stage in the split, with the two Save nodes renamed now; fix the expansion prompts before 10:20Z; point Save Doctor Verdict at the Sources Gate; row 46 keeps the 2356 script with the close fixed; tell the writer to close on a question rather than loosen the gate.
FINDINGS: The expansion step, not the writer, invented row 46's figures. The gate read numbers from link URLs. The earlier record's year kept claim was false. V5 d7f4d56f and Research 964214fc are published and read back. Test 2356 added no figure across 720 expanded words; test 2357 fixed the close and fell under the floor after the doctor's trim. NCO row 26 has one approved WEF source and its package lock still does not resolve.
OPEN: The second expansion runs before the doctor trims, so a script can land under 1,200 words. Fifteen V5 nodes still call Airtable. The NCO presenter rule and NCO sources path are proven offline and by the research copy, not yet by an NCO script, because no NCO row resolves a lock. A blog stating a number as its own is still left to the doctor. Row 46 awaits Tee's review tick. Carousels for each show, asked by Tee after this work.
STATUS: V5 active and draft d7f4d56f, read back; Research active 964214fc, read back; row 46 Scripted with sources; this doc's PR not yet opened at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
