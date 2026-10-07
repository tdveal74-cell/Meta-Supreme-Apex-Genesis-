# Carousels for every episode, and what a second critic found

This follows `SYS_OPS_nco-sources-and-the-expansion-fix_v1_2026-10-07-1316.md`.
Tee asked for a carousel for each, once NCO Forge was done, and ruled the shape
on a card: one per episode, automatic, from our own HTML templates, delivered
as files for review only. A fresh critic graded the NCO work on `e334db6` as
PASS-WITH-CONDITIONS, and Tee ruled all four of its live fixes applied.

## Carousels

V5 already writes each episode's carousel as text: the packaging step returns
7 to 9 one line slides and stores them in the row's `platform_packaging` as a
`CAROUSEL` block. Nothing drew them. `tools/carousel` now does, and
`carousel-render.yml` runs it daily at 12:13Z, reads both content tables, and
uploads the slides as the run's artifact. It posts nothing and writes nothing
to the instance. A carousel is refused, with its reasons on the run page, when
it breaks the packaging rules, carries a dash, or states a figure the row's own
script does not.

TQO follows `sites/tqohq/DESIGN.md`. NCO Forge first got a manila draft of my
own; Tee said the brand lives in a document on his Drive, and the v1 package
there sets Deep Navy, Gold and Olive with a bold sans serif, so the template was
rebuilt to it in Inter. The v2 packages for both shows are zips too large for
the Drive connector and are unread; Tee ruled v1 for now and will supply v2's
style guide in a readable size. On the first run only TQO row 4 had a packaged
carousel; its contact sheet and the NCO sample were sent to Tee.

## The second critic

It confirmed every live version and mirror byte for byte and every execution
figure in the record, and found these, graded by blast radius.

- Row 46, waiting on Tee's review, still carried an invented testimonial that
  both gates passed: "Managers who have applied this three-step plan report
  that...". Cut by hand under the existing ruling and logged on the row, which
  now reads 1,482 words.
- The Sources Gate read attributions across sentence breaks, so an approved
  name ending one sentence let an unapproved one through in the next.
- Research refused primary sources speaking for themselves, such as "Gallup
  research finds" on Gallup's own page.
- An empty table would have stopped Research for both shows without an error.

All four were fixed and published: V5 `c2d51b46` changes only the Sources Gate,
replayed on the critic's inputs and on row 46 before and after the cut; Research
`641bcc0c` was proven on a test copy, execution 2358, then promoted and the copy
archived. The two test mutants that had survived now fail the tests.

Graded and left open: the gate cannot see an unattributed projection stated as
fact, and NCO prose will raise false alarms on things like 0600, the 101st or a
DD-214, all failing closed to Error for Tee to clear. The measured show blocks
in `Build Script Prompt` still ask for "a concrete example or number"; only the
expansion passes and the length line were changed.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_carousels-and-the-second-critic_v1_2026-10-07-1344.md
DATE: 2026-10-07
DECISIONS: Tee ruled on cards: one carousel per episode, automatic, our own HTML templates, files for review only; the NCO look comes from his brand package, v1 now and v2 when he supplies it; apply all four of the second critic's live fixes; merge PR #314 when green.
FINDINGS: Every episode's carousel text already existed in platform_packaging and nothing drew it. Only TQO row 4 had one on the first run. Row 46 carried an invented testimonial past both gates. The gate read across sentence breaks; Research refused primary sources and could stall on an empty table. V5 c2d51b46 and Research 641bcc0c are published and read back.
OPEN: The v2 brand packages for NCO Forge and TQO, unread. The first scheduled carousel run, which needs the workflow on main. NCO false alarms on military numbers. Unattributed projections. The measured show blocks still ask for an example or a number. Row 46 awaits Tee's review tick.
STATUS: V5 active c2d51b46, Research active 641bcc0c, both read back; carousel stage committed on PR #314, not yet merged at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
