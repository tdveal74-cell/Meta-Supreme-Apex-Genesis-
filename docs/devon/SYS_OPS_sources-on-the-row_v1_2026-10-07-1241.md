# Real sources on the row, and a writer held to them

This follows `SYS_OPS_evidence-gate-after-row-46_v1_2026-10-07-1159.md`. That
fix stopped the writer putting experience in Tee's mouth and left it free to
invent a named source, which execution 2344 did. Tee ruled the root on cards
the same morning: sources on the row, a research step the script doctor
approves, a mechanical quote check under the doctor, Firecrawl for the search,
and unsourced rows back to Idea rather than Error. Then, on a second card,
publish the writer change, put row 46 back to Idea for the 10:20Z pass, and run
research daily at 09:40Z. PR #312 merged as `3bc665f` before any of this.

## The row and the skip

`tqo_content` gained a `sources` column and a `research_note` column. V5
`6d67e0a8` changed `Package: Plan Batch` so a locked TQO row with no source
carrying both a url and a quote gets no writer call and stays Idea. Row 46 was
reset to Idea under it.

## TQO Research

A new workflow, `0zLNB34UOOTq6mck`, recorded under `n8n/tqo-research/` with a
README that walks one run. It reads the Firecrawl balance and refuses under
100 credits, takes up to two locked Idea rows without sources, searches with
page text, has Cerebras copy quotes, checks every quote against the fetched
page, lets the doctor vote, and writes only `sources` and `research_note`.

The first run is the reason the check now demands provenance. Execution 2349
found every quote on its page and the doctor still approved five that were
blogs and a manager training vendor repeating figures without naming who
produced them. They were cleared from row 46 by hand within minutes, because
the writer did not read sources yet and the 10:20Z pass would have run on them.
The quote must now name the organisation that produced the figure, unless the
publisher produced it, and the doctor is told to reject vendors with a stake
and unnamed surveys. Execution 2350, 10 credits, approved four for row 46:
Bloomberg with Live Data Technologies on the 2023 middle manager share of
layoffs, Korn Ferry's 41 percent, Gallup's span of control from 10.9 to 12.1,
and Gartner's projection. It dropped a scraped JSON line and the doctor
rejected an off topic Silicon Valley figure. Those four were held in
`research_note` until the writer change was tested, then restored with a clean
`quote_text` beside each exact quote.

The doctor approved the vendor blogs on the first run against its own written
rule, so its vote is a model's judgement and the record says so. All four row
46 figures are relayed rather than read at their origin: three through Ramp's
page and Gartner's through a YouTube video page, which the search now excludes.

## The writer, the doctor and the gate

V5 `61d4aeeb` adds three Code nodes on existing edges and edits no existing
node, so the measured show blocks and the canon traced to them do not move.
`Sources Rule` appends the approved sources to the writer prompt with the rule
that every figure comes from them, named by origin. `Doctor Sources` hands the
doctor the same list. `Sources Gate` refuses any numeral missing from the
sources except counts of ten or under and a year the idea names, any
attribution to an unapproved name, and any unnamed person cited as a source.

Manual execution 2351 ran the draft on row 46. The writer cited all four
sources with the origin named and the year kept, and then invented a 150
person division, an interview with an unnamed HR director at a manufacturing
firm and a 300 person plant. The gate held the row as Error on six figures, and
the existing close rule flagged a close with no question. The evidence patterns
missed the interview because they need the first person, so the unnamed person
check was added to the Sources Gate, replayed on that script, and published
with the rest. The publish was read back: `versionId` equal to
`activeVersionId`, all three bodies byte for byte in the active version, the
chat lane still disabled. Row 46 was put back to Idea with its script cleared
and its sources kept, for the scheduled pass at 10:20Z on 2026-10-08.

## In the repository

The exports are regenerated at `61d4aeeb`, the registry names it, and its count
of Code nodes that branch on the show rose from 25 to 28 because the three new
nodes are TQO only. The three bodies are mirrored beside `build_script_prompt.js`
and a test pins each to its mirror and its edge. Two behaviour tests drive the
real bodies in the standalone job, `research.test.mjs` and
`sources_gate.test.mjs`, and every mutant tried against them failed them: the
provenance check removed, the figure check removed, a mirror byte changed, a
`status` column added to the research write.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_sources-on-the-row_v1_2026-10-07-1241.md
DATE: 2026-10-07
DECISIONS: Tee ruled on cards: merge PR #312 when green; real sources on the row; a research step the script doctor approves, with a mechanical quote check under it; Firecrawl for search; unsourced rows stay Idea, never Error; publish the V5 sources change; row 46 back to Idea for the 10:20Z pass; research daily at 09:40Z.
FINDINGS: PR #312 merged as 3bc665f. Research execution 2349 found every quote on its page and the doctor still approved five vendor and blog sources, so provenance was made mechanical; execution 2350 approved four named origins for row 46. V5 61d4aeeb execution 2351 cited all four correctly and invented three examples with six figures and an unnamed interview, which the Sources Gate held as Error. V5 and TQO Research were both published and read back equal.
OPEN: The 10:20Z pass on row 46 under the published rule, and whether the writer stops inventing examples or keeps landing Error. The first scheduled research run at 09:40Z on 2026-10-08, which should find no row to research. All four of row 46's figures are relayed, three by Ramp and one by a video page, not read at their origin. NCO has no sources rule because NCO was not ruled. The close rule still fails scripts that end without a question. Row 5's named claims and row 4's audit pointer are unchanged.
STATUS: V5 active and draft 61d4aeeb, read back; TQO Research active 3796e545, read back; row 46 Idea with 4 sources and no script; this doc's PR not yet opened at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
