# TQO Research

TQO Research (`0zLNB34UOOTq6mck` on the VPS n8n) puts real sources on a locked
row, TQO or NCO Forge, before the writer touches it. Tee ruled it on 2026-10-07 after row 46,
whose script invented conversations, unnamed firms and figures: a research
step, the script doctor approves, a mechanical quote check under the doctor,
and Firecrawl for the search. NCO Forge was ruled to the same standard later
the same day.

`workflow.json` is the active version as read back after the publish. The six
`.js` files are its Code node bodies, named after the nodes in snake case.
`test_tqo_research_export.py` fails when a body drifts from the record, and
`research.test.mjs` drives the bodies over the real pages and replies of
executions 2349 and 2350. n8n is the running system and these are copies, so a
change made in the editor and not copied here is drift.

## What one run does

It runs daily at 09:40Z, in UTC so the November clock change does not move it,
40 minutes before the 10:20Z writer in TQO FINAL V5. A failure runs the shared
`OS - Error Handler (all pipelines)`.

1. `Firecrawl Balance` reads the account and `Credit Floor` refuses the whole
   run under 100 credits, or when it cannot read the balance at all.
2. `Get TQO Idea Rows` and `Get NCO Idea Rows` read both tables, and `Rows
   Needing Sources` takes Idea rows with `package_locked` set and no usable
   source, oldest first, two per show. A row whose last note says no source was
   written is left alone for seven days, read from the date the note opens
   with, so two rows that cannot be sourced do not starve the queue. These are
   exactly the rows `Package: Plan Batch` in V5 leaves out.
3. `Firecrawl Search` asks for eight results with each page's own text,
   excluding LinkedIn, Instagram, Facebook, TikTok, X and YouTube.
4. `Extract Quotes (Cerebras)` is asked to copy up to six passages word for
   word, each naming the organisation that produced the figure.
5. `Quote Check` keeps a quote only if it is found in the fetched page text
   after whitespace, punctuation and markdown link normalising and nothing
   else, if it names its origin in its own words unless the publisher produced
   the figure, and if that origin is on the page. A changed digit fails. A page
   naming itself as the origin of a figure it credits to unnamed studies or
   research fails too. A blog stating a number as its own still passes this
   step, and only the doctor stands between it and the row.
6. `Script Doctor Approves (Cerebras)` votes approve or reject on each checked
   source, briefed for the channel the row belongs to. It cannot edit one: `Compose Approved Sources` keeps the checked text
   and only reads the vote.
7. `Write Research to Row` writes `sources`, a JSON array, and `research_note`,
   dated, to the table the row came from. It never writes `status`. A row with no approved source stays Idea, its note
   saying why, and V5 keeps skipping it.

## What it cost and found on its first runs

Execution 2349 used 6 credits and approved five sources that were blogs and a
training vendor repeating figures without naming who produced them. Those were
cleared from row 46 by hand and the origin rule above was added. Execution 2350
used 10 credits, measured from the balance the next run read, and approved four: Bloomberg with Live Data Technologies, Korn
Ferry and Gallup as reported by Ramp, and Gartner's projection. The balance was
1,279 credits against a 1,000 credit monthly plan on 2026-10-07.

What it does not do: it does not re-fetch a page a second time, because the
search already fetched each page fresh and the check reads that text; and the
doctor's judgement of a publisher is still a model's judgement. All four row 46
figures are relayed rather than read at their origin: three through Ramp's page,
and Gartner's through a YouTube video page, which is why YouTube is now excluded
from the search.

Execution 2355, a test copy of the two table version run once and archived,
took NCO row 26 alone and wrote to `nco_content`. The doctor rejected Novoresume
twice and iHire as vendors, the quote check dropped two quotes that were not on
their pages, and one World Economic Forum source was approved. The live
workflow was then updated to that graph and read back as `964214fc`.
