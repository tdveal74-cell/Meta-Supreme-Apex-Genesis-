# Row 46 passed the gate, and the Brief lane now reads the script

This follows `SYS_OPS_six-rulings-on-cards_v1_2026-10-06-2043.md`. It covers
the morning of 2026-10-07: the scheduled pass on row 46 that two rulings were
waiting on, four rulings Tee made on one card once it had landed, and what was
done on each.

## Row 46 under the tightened close rule

Scheduled execution 2336 of `TQO FINAL V5` fired at 2026-10-07T10:20:00Z on
`Daily 6am - Script Writer` and finished at `Scripts Done` with status success
in 20 seconds. Row 46, "The Middle Is the Target", took the FALSE edge of
`Script: Already Written?`. The writer drafted 841 words, one expansion took
it to 1,370, the doctor scored it 78 and repaired it, dash repair rewrote 7
sentences, and the originality scan returned 100. The Script Gate passed with
no failures. The row now reads `Scripted` at 1,345 words, updated
10:20:20Z, with zero dashes.

The last spoken sentence is "Tell me in the comments, what concrete metric
are you using to demonstrate your impact this quarter?" It carries the word
comments and a question mark, so the close rule published as `b99b38ab` held
on its first unattended run.

One thing in the script is Tee's to judge before it moves on. The opening
sentence states a fact with no source: "middle managers are being laid off at
a noticeably higher rate than senior executives." The doctor's own diagnosis
says it removed invented figures from the draft ("42 planned cuts" and a "12
percent uplift"). This general claim stayed in. Promote runs Monday,
Wednesday and Friday at 7am. Nothing publishes without the human review tick.

## Four rulings on one card

The writer of record is the V5 two pass writer, and every script from any
source passes the same doctor and gate.

PR #310 merged as `2bd82f1`. Its first `workflow_dispatch` run of
`registry-check.yml`, run 37608572402 on that commit, went green, and its
log reads `show_registry (xmNWLUm49QyZ4ysO): 2 rows read back, 2 expected,
CLEAN` and the same for `show_series` at 16 rows. That proves the
`N8N_VPS_KEY` secret and the host from GitHub's side. Whether the schedule
fires is still untested; that needs a 07:41Z slot to pass.

The two Reach drafts from execution 2295 were ruled deleted by me, and that
could not be done. The Hostinger API lists create, get, list and performance
operations for Reach campaigns and templates, and no delete for either. Read
back through `reach_campaigns_get`: campaign `8d28dba8` is `status: draft`,
`total_sent: 0`, no segments, no schedule. It and template `355f83f8` have
to be removed in the Reach dashboard.

The Brief lane fix was ruled as a draft, one test, then a publish.

## The Brief lane fix

Two nodes changed and nothing else. `Build Brief Prompt` now reads
`$('DT Shim: Latest Content')` instead of the raw data table row, and throws
"Refusing to write a brief about nothing" when the script is empty. The
signature line in `Assemble Email HTML` read `&mdash; The Quiet Operator` and
now reads `The Quiet Operator`. Both were checked byte for byte against the
intended code after each `update_workflow`.

A temporary manual trigger wired only to the TQO Brief was added to the draft
and fired once as execution 2337. The prompt carried 8,291 characters, against
an empty script in 2295. The Brief came back with the subject "Map the tasks
AI can take", a real headline and body, and zero dashes. It created template
`f610bed6` and campaign `089bb4f4` in Reach as a draft. That draft is the one for Tee to
send to himself from the dashboard.

The trigger was then removed. The draft was diffed against `36013f35`: 265
nodes on both sides, only the two Brief nodes differ, connections identical.
Published as `99e32b37`. The read back shows `versionId` equal to
`activeVersionId`, both fixed nodes in `activeVersion`, all seven chat agent
nodes still disabled, and no test node. The exports are regenerated from it
and `SOURCE` in the registry names it.

## What the test Brief says, graded

The fix is proven. The content still needs Tee's eye before anyone else reads
it, for two reasons. The lane picked row 5 again, the newest Ready row, and
row 5's named claims are not yet sourced. The Brief turned the script's Bank
of America example into "finance analysts find the data entry time vanish
while the time spent on variance analysis rises", which carries the same
unsourced claim without the name. It also says "Companies that cut headcount
before understanding this split often lose institutional knowledge and see
performance dip", which nothing on the row supports.

One more finding, with a blast radius of zero today. `Assemble Email HTML`
hardcodes The Quiet Operator: header, footer, signature and the Gumroad link.
`Brief: Brand Overrides` does not rewrite the HTML. So an NCO Forge Brief
would go out wearing TQO branding. Nothing runs that path unattended while
the Sunday trigger stays disabled.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_row-46-pass-and-the-brief-fix_v1_2026-10-07-1040.md
DATE: 2026-10-07
DECISIONS: Tee ruled on one card: the V5 two pass writer is the writer of record with one gate for every script; fix the Brief lane in a draft, test once, publish; delete the two test drafts in Reach; merge PR #310.
FINDINGS: Scheduled execution 2336 took row 46 to Scripted at 1,345 words and the gate passed; the close carries the word comments and a question mark. The opening sentence of row 46 is an unsourced factual claim. Registry check run 37608572402 read both tables CLEAN from GitHub. The Reach API has no delete for campaigns or templates. The Brief fix took the prompt from an empty script to 8,291 characters (execution 2337). The test Brief carries row 5's unsourced claim in softened form. Assemble Email HTML hardcodes TQO branding for both shows.
OPEN: Reach drafts 8d28dba8 and template 355f83f8 to be deleted in the dashboard by Tee; draft 089bb4f4 for Tee to send to himself and read end to end. Row 46's opening claim to source or cut before it passes human review. Row 5's named claims to source or cut. NCO branding in Assemble Email HTML before the NCO Brief runs. The first scheduled registry-check run at 07:41Z. The Script stage build on the V5 writer.
STATUS: V5 active and draft both 99e32b37, read back; PR #310 merged as 2bd82f1; this doc's PR not yet opened at the time of writing, so its CI has not run.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
