# Jev arc: close

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q, which began on
2026-10-16. This doc covers its Jev work of 2026-10-27 and 2026-10-28: the three
image lanes in TQO FINAL V5, the thumbnail layout fix those lanes exposed, and the
Jev router hook. The doctor work of the same session closed in its own status
docs of 2026-10-25 and 2026-10-26. The n8n reads are from 2026-10-28 between
23:09Z and 23:15Z. Everything else is quoted from the repo record named beside
it.

The status doc of 2026-10-23 left two Jev items open: TypeSafe funding and the
router hook rebuild. Both are closed here.

## What shipped

| PR | What | Merge |
|---|---|---|
| #423 | dnspython 2.9.0, clearing the pip audit | `a8db658` |
| #422 | The three Jev image lanes live in shadow, the thumbnail layout fixed, the model pinned | `9bc4b7a` |
| #432 | The Jev router hook rebuilt as an allowlist, switched off | `453af0b` |

#368, the first version of the hook, was closed unmerged with a pointer to
#432. Other PRs merged to main in the same window are outside this arc.

## The image lanes

Per `n8n/tqo-v5/JEV_WIRING.md`, Tee funded the TypeSafe account and made the
Header Auth credential "Jev" (`AJM16uvmcW88bSL4`) on the instance himself. A
fresh critic's read of the live Jev nodes on 2026-10-28 found no Bearer value in
any of them. Tee then ruled three cards on 2026-10-27: "Standalone harness",
"Draft now, publish card next" and "Publish now". The lanes ran first in an
inactive copy of the workflow against the real API as execution 4737, then went
into TQO FINAL V5 as version `3db61aef`, activated at 2026-10-27T21:58:51Z and
read back equal to the draft. All three `JEV_APPLY` constants read false in the
live nodes on 2026-10-28, so the lanes report what Jev would pick and change
nothing.

The harness frame showed two defects in the thumbnail that predate Jev. The navy
panel drew about 15 percent opaque in execution 4737, because GraphicsMagick
reads the last pair of an 8 digit colour as transparency and the code ended it
in `D9`. Full headline lines ran past the panel, because the wrap assumed 0.52 em
a character: `DASHBOARD FIRST` at 84 px reached x 866 against a panel edge at
x 760. Tee ruled "Fix both, prove first" and "Draft and publish now". Four proof
runs, executions 4764 to 4767, drew every line inside the panel, and the fix went
live as `de4ac645` at 2026-10-27T23:33:59Z. The test that holds the repo to the
node took three rounds of independent review, each of which found an edit the
previous test let through. Five layout edges were left as they are, each with
its reason, under "Proving it after wiring" in `JEV_WIRING.md`.

## TQO FINAL V5 as it stands

Read at 23:09Z: `versionId` and `activeVersionId` both `51a807f7`, the workflow
active, 297 nodes, last saved 2026-10-28T20:52:44Z. A read only agent took the
full workflow and found the one `Thumb: Pick Still` node byte identical to
`n8n/tqo-v5/thumb_pick_still.js`, sha256
`a3e88bcc4d3d89cba7145c6906c87544973ab9811f3423bbd253a73af3f350e6`, which is
also the sha256 in `live-thumb-layout/manifest.json`. The live code reads
`TEXT_BUDGET = 680`, `FLOOR_Y = 680`, `SIZES = [104, 84, 66, 54]` and
`scrimColor: ink + '26'`. The layout fix is what runs.

The workflow moved on after `de4ac645`. Its history, read through the n8n
connector, lists six versions and no older ones: `de4ac645`, then five saves on
2026-10-28, `88b36040` (Show Context: Publish and Upload to YouTube for NCO
Forge), `cd27ab26` (QC Doctor Gate), `efc24d94` (Preflight), `e98e09b9` (OS 28
Publish Gate) and `51a807f7` (Jev: Thumb Verdict). This session made none of
them. PR #434, from another session, records the export at `51a807f7`, names
`e98e09b9`, and re-anchors the Jev thumbnail tests on the live export. The repo
does not name `88b36040`, `cd27ab26` or `efc24d94` by id.

Five executions have started since the lanes went live, all in trigger mode at a
scheduled trigger's minute, and all successful. A fresh critic opened all five.
None ran a Jev, Build Movie, Thumb or render node. The longest, execution 4832 at
10:20Z, took 2.6 s, ran seven nodes and stopped at `Package: Plan Batch` with no
items. No real episode has gone through the lanes yet, so Jev has not answered on
one.

## The router hook

`.claude/hooks/jev_route.py` runs before every Bash, Edit, Write, NotebookEdit and
MCP call. Once switched on, it asks Jev whether a dedicated tool would do the
step better and whether the step changes something outside the repository or
something that cannot be undone. It ships with `SEND = False` and `ENFORCE =
False`, so today it makes no request, prints nothing and writes one `off` row per
call to `.claude/ledger/jev-route.jsonl`.

What would leave the machine is an outline built from allowed pieces, never a
cleaned copy of the call. Tee ruled three things on cards. On 2026-10-17, "Hold
it, rebuild as allowlist", after four findings against #368's scrubbing. On
2026-10-28, "Known commands only": a word leaves as a program name only when it
is a bash builtin or reserved word from a pinned list, a name `PATH` resolves to
an executable, or an existing executable path. The same day, "Top-level only":
an MCP call sends its top level field names and nothing below them. His earlier
ruling stands too: the container never holds the TypeSafe key, so the hook sends
no Authorization header and relies on the environment's proxy to add it.

The fix commits name each verify round. Before the known commands ruling there
were five reader findings against `42b0e2d`, three against `c65e5c7` and six
against `59ef1ed`. After it there were three redirect target findings against
`bc5b316`, five reader leaks in round 6 and the array literal leaks of round 7.
Per PR #432's description, each round had four independent verifiers, one each
for leaks, time and shape, spec and tests, and auth, with real bash 5.2 as the
oracle. The last round, on `1d4fa3f`, found no blocker and no should fix, and
its leaks verifier re-ran all 90 reproductions from every earlier round with
none sending a value. CI on `1d4fa3f` passed all five `ci.yml` jobs.

## Also fixed here

The standalone list in `CLAUDE.md` missed `test_devon_rsi.py`,
`test_devon_rsi_ops.py` and `test_devon_rsi_experiments.py`, which the
standalone job in `ci.yml` runs. Counted from both files at `453af0b`: 51 in the
job, 48 in the list. The three are added, so a local run of the list matches the
job again.

The Jev router section of `CLAUDE.md` said the third verify round before the
known commands ruling found more blockers than the second. The fix commits
record three findings for the third and five for the second. The sentence now
says what both the fix commits and PR #432's tally agree on: the last of the
four rounds found more than the one before it.

## Lessons worth keeping

GraphicsMagick reads the last pair of an 8 digit colour as transparency, not
opacity. `D9` drew about 0.15 opaque in execution 4737, and `26` drew 0.855 in a
GraphicsMagick 1.3.42 render. Any colour handed to it with an alpha pair needs
the pair inverted from the CSS reading.

A wrap that assumes an average character width overflows on wide capitals. The
fix was to measure: Arial advance widths, checked against Liberation Sans read
from the font file, and the node's wrap compared line for line with the wrap
n8n's Compose node uses.

A mutation test proves nothing about a value pinned in several places unless
every pinned copy is moved together. Moving one copy only proves the copies
agree with each other.

A privacy filter cannot be made safe by modelling the shell more closely. Four
rounds each found a new construct the reader took for a command. The known
commands gate closed that path from the other side, so a reader mistake about a
program name now drops a word instead of sending one. It does not cover redirect
targets, which are paths by syntax, and rounds 5 to 7 still found leaks there and
through flags, each closed in the reader. An allowlist narrows what a mistake can
cost; it does not end the need for adversarial rounds.

In this session the main checkout once read as dirty after an editor committed
inside its worktree: the branch ref had moved under the checkout while its index
still matched the older commit's tree. Check that before resetting, and never
commit those changes as if they were your own.

## Open

- `SEND` for the router hook is Tee's ruling. The first live call is what proves
  the proxy adds the header. If it does not, the API answers 401, the hook writes
  an `error` row and the call runs as it would without the hook.
- `ENFORCE` is a separate ruling, made from the ledger once real answers exist.
- Each `JEV_APPLY` flip is its own ruling, made from the shadow numbers of real
  runs.
- The first real render through the lanes is still to be read: whether the two
  Split In Batches loops hand the side branches the right row, the item counts
  after a failed still fetch, Jev's answers on real narration and photos, and how
  much the saved execution data grows.
- The rollback lines in `live-thumb-layout/manifest.json` (publish `3db61aef`)
  and `JEV_WIRING.md` (publish `fc75f7a6`) name versions the workflow's history
  no longer lists, and a fresh critic's GET of either id returned 404. They may
  already be unusable; no publish was tried. Even if one worked, publishing it
  would also undo the five saves above, the NCO upload wiring, the three
  compliance node changes and the `Jev: Thumb Verdict` change among them.
  Undoing the thumbnail fix alone would now mean editing that one node.
- PR #432's description lists twelve hook nits left as they are. One is worth
  knowing before `SEND`: a TLS failure, a refused CONNECT and a dead proxy all
  write the same `URLError` row.
- Unverified: which `PATH`, `HOME` and shell the live harness gives a hook, and
  what the harness does with the wrapper's `exit 1`.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_jev-arc-close_v1_2026-10-28-2313.md
DATE: 2026-10-28
DECISIONS: Tee ruled on cards: hold #368 and rebuild the hook as an allowlist (2026-10-17); prove the image lanes in a standalone harness, draft them, then publish (2026-10-27); fix the thumbnail panel and overflow, prove first, then draft and publish (2026-10-27); send a program name only when it is a known command, and send only top level MCP field names (2026-10-28). The container never holds the TypeSafe key.
FINDINGS: GraphicsMagick drew the navy thumbnail panel about 15 percent opaque because it reads the last colour pair as transparency, and full headline lines ran past the panel because the wrap assumed 0.52 em a character; both fixed live as de4ac645 and still live in 51a807f7, read back byte for byte. Each shell reader version of the hook leaked some value; the known commands gate closed the program name path, and later rounds closed redirect target and flag leaks in the reader. The CLAUDE.md standalone list missed three rsi tests the CI job runs, and a CLAUDE.md sentence misstated which verify round found more. The rollback versions named in the thumbnail and lanes records are no longer in the workflow's history.
OPEN: SEND, ENFORCE and each JEV_APPLY are rulings; the first real render through the lanes is unread; the rollback lines point at versions the history no longer lists; twelve hook nits; the PATH, HOME and shell the harness gives a hook are unverified.
STATUS: #423, #422 and #432 are merged and #368 is closed. TQO FINAL V5 is active at 51a807f7 with versionId equal to activeVersionId, read 2026-10-28T23:09Z. The hook ships switched off.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
