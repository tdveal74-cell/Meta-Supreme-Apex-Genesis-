# The writer was inventing Tee's experience, and nothing in the lane could see it

This follows `SYS_OPS_row-46-pass-and-the-brief-fix_v1_2026-10-07-1040.md`. Tee
ruled that row 46's unsourced opening line be sourced or cut. Reading the whole
script before touching one line showed the line was the smallest problem in it.

## What row 46 said in his voice

The script that execution 2336 wrote and passed at 10:20Z carried eight lines
that nothing on the row supports. Some put experience in his mouth: "In
recent conversations with senior HR leaders across software, finance, and
manufacturing sectors, they reported", "In my own experience, a product line
manager I consulted for", "I once advised a logistics coordinator", "the same
manager I mentioned earlier". Others cite sources that cannot be checked: "A
finance firm reported", "A recent case study from a logistics firm", a quoted
phrase put in the mouth of "several large technology firms", and the opener
"The data we have right now shows". The opening claim could not be sourced
from here either: the network policy blocks CNBC, Wikipedia and Ramp, and a
search summary is not a primary source.

Promote's 11:00Z run, execution 2339, stopped at `Get Oldest Released Script`
and never touched the row.

## Why every check passed it

Tee asked whether the script had been audited in the workflow. It had, four
times, and none of the four looks for this. The Script Doctor scored it 78 and
removed two invented figures, because its prompt bans invented "statistics,
metrics, studies or quotes" and says nothing about invented experience. The
originality scan measures rhythm and overlap and says in its own report that
it is not a fact check. The Script Gate measures structure only. The QC prompt,
which had not yet run on this row, tells the grader that first person claims
are "the strongest evidence on this channel" and never to treat one as
invented, so it would have trusted the model's inventions as his.

The pressure comes from the brief. `Build Script Prompt` demands that "every
claim carries a receipt. A number, a named tool, a documented before-and-after"
and asks for mini stories, with no research supplied. With no real receipt the
model makes one.

## The fix, published as 54fbda3d

Tee ruled the writer fixed and the row rewritten. Three nodes changed and
nothing else, diffed against `99e32b37` before publishing, read back after.

`Build Script Prompt` gains an EVIDENCE block for both shows, placed after the
two measured show blocks so the 999 word TQO count the canon test pins does not
move. It allows first person material only from his DEVON record, forbids
unnamed firms, studies, reports and case studies, defines a receipt as a named
public source, a named tool or a step the viewer can do, and allows a plainly
labelled picture with no name, employer or number. The mirror
`n8n/tqo-v5/build_script_prompt.js` carries it, and the canon gains
`compliance.no-invented-experience`, traced to "EVIDENCE: NOTHING INVENTED"
and proven by mutation: removing the phrase fails the test.

`Build Doctor Prompt` gains the same rule and now receives the DEVON recall,
2,527 characters on execution 2336, as TEE'S RECORD, so his real material can
stand and nothing else can.

`Script Gate: Quality` refuses ten patterns of invented first person experience
and unnamed sources. Measured on the gate code in a harness before it went
anywhere: row 46's old script moved from Scripted to Error on 8 hits, row 4,
his real seven day log, scored 0, and row 5 scored 2, its "the data shows"
opener and its regional bank case study. The same harness surfaced two older
holds that are not this change's: row 4's script still points to the retired
free audit, and row 5's close asks no question for the comments.

## The rewrite, and what no pattern can catch

Row 46 was reset the way it was reset on 2026-10-06, status Idea with `script`
and `script_machine` cleared after a dry run on one row, and manual execution
2344 rewrote it on the draft. The invented first person lines went from 8 to
0 and the doctor scored it 92. The writer then invented in a new place: "Public
data from the 2026 Layoffs Tracker compiled by Challenger, Gray & Christmas"
showing a growing middle management share of AI cuts, a salary band of
$110,000 to $150,000, a $199 certification, and a product called Microsoft
Project Planner. Challenger is real and publishes monthly job cut reports; the
search summaries of its March and May 2026 reports name no middle management
breakdown, so the attribution is unverified and likely invented. The PDFs
themselves were not read. The gate held the row as Error on length, 1,074
words against the 1,200 floor, on a close with no question mark, and on one
evidence hit.

So the lane now refuses invented experience, and still cannot tell a real
named source from an invented one. Tee ruled the root: real sources on the
row, which the writer may cite and nothing else.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_evidence-gate-after-row-46_v1_2026-10-07-1159.md
DATE: 2026-10-07
DECISIONS: Tee ruled on cards: fix the writer and rewrite row 46 rather than cut one line; publish the evidence fix to live V5; put real sources on the row so the writer cites only those and the gate refuses anything else; hold row 46 as Error until sources exist.
FINDINGS: Row 46's passed script carried eight unsupported lines in Tee's voice, four of them invented first person experience. The doctor, the originality scan and the gate all passed it, and the QC prompt is written to trust first person claims. The writer brief demands receipts with no research supplied. The new gate scored rows 46, 4 and 5 at 8, 0 and 2 hits. The rewrite on the fixed draft carried 0 invented first person lines but invented a named Challenger attribution and unsourced figures. V5 published as 54fbda3d and read back.
OPEN: The sources column on tqo_content, the writer reading it, and a gate check that every figure and named organisation in a script appears in it. Row 46 held as Error until then. Row 4's retired audit pointer and row 5's missing comments question. The QC prompt's trust in first person claims, to revisit once the record is the only first person source.
STATUS: V5 active and draft both 54fbda3d, read back; row 46 status Error; this doc's PR not yet opened at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
