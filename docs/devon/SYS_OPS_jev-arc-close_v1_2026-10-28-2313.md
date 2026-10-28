# Jev arc: close

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q, 2026-10-23 to
2026-10-28. This doc covers the Jev work only: the three image lanes in TQO FINAL
V5, the thumbnail layout fix those lanes exposed, and the Jev router hook. The
doctor work of the same session closed in its own status docs of 2026-10-25 and
2026-10-26.
Every state fact below carries the time it was read. The n8n reads are from
2026-10-28 between 23:09Z and 23:13Z.

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

Tee funded the TypeSafe account and made the Header Auth credential "Jev"
(`AJM16uvmcW88bSL4`) on the instance. The key never went in a node, a file or a
chat. He then ruled three cards on 2026-10-27: "Standalone harness", "Draft now,
publish card next" and "Publish now". The lanes ran first in an inactive copy of
the workflow against the real API as execution 4737, then went into TQO FINAL V5
as version `3db61aef`, activated at 2026-10-27T21:58:51Z and read back equal to
the draft. Every `JEV_APPLY` is still false, so the lanes report what Jev would
pick and change nothing.

The harness frame showed two defects in the thumbnail that predate Jev. The navy
panel drew about 15 percent opaque, because GraphicsMagick reads the last pair of
an 8 digit colour as transparency and the code ended it in `D9`. Full headline
lines ran past the panel, because the wrap assumed 0.52 em a character: `DASHBOARD
FIRST` at 84 px reached x 866 against a panel edge at x 760. Tee ruled "Fix both,
prove first" and "Draft and publish now". Four proof runs, executions 4764 to
4767, drew every line inside the panel, and the fix went live as `de4ac645` at
2026-10-27T23:33:59Z. The test that holds the repo to the node took three rounds
of independent review, each of which found an edit the previous test let
through. Five layout edges were left as they are, each with its reason, under
"Proving it after wiring" in `n8n/tqo-v5/JEV_WIRING.md`.

## TQO FINAL V5 as it stands

Read at 23:09Z: `versionId` and `activeVersionId` both `51a807f7`, the workflow
active, 297 nodes, last saved 2026-10-28T20:52:44Z. A read only agent took the
full workflow and found the one `Thumb: Pick Still` node byte identical to
`n8n/tqo-v5/thumb_pick_still.js`, sha256
`a3e88bcc4d3d89cba7145c6906c87544973ab9811f3423bbd253a73af3f350e6`, which is
also the sha256 in `live-thumb-layout/manifest.json`. The live code reads `TEXT_BUDGET =
680`, `FLOOR_Y = 680`, `SIZES = [104, 84, 66, 54]` and `scrimColor: ink + '26'`.
The layout fix is what runs.

The workflow moved on after `de4ac645`. Its history shows five saved versions on
2026-10-28, all from another session, recorded in PR #434: `88b36040` (the NCO
Forge YouTube upload), `cd27ab26` (QC Doctor Gate), `efc24d94` (Preflight),
`e98e09b9` (OS 28 Publish Gate) and `51a807f7` (Jev: Thumb Verdict). #434
re-anchored the Jev thumbnail tests on the live export.

Five executions have started since the lanes went live, all in trigger mode at a
scheduled trigger's minute, and all successful. The longest, execution 4832 at 10:20Z, took 2.6 s. None was opened. A
run that short cannot have rendered a video, so as far as these reads show, no
real episode has gone through the lanes and Jev has not yet answered on one.

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

Four independent verifiers attacked every round, one each for leaks, time and
shape, spec and tests, and auth, with real bash 5.2 as the oracle. Four rounds
before the known commands ruling found 6, 4, 1 and 4 blockers. Four after it
found 3, 5, 3 and 1 issues. A final pass fixed the nits that kept recurring, and
its last round, on `1d4fa3f`, found no blocker and no should fix. The leaks
verifier re-ran all 90 reproductions from every earlier round and none sent a
value. CI on `1d4fa3f` passed all five `ci.yml` jobs.

## Also fixed here

The standalone list in `CLAUDE.md` missed `test_devon_rsi.py`,
`test_devon_rsi_ops.py` and `test_devon_rsi_experiments.py`, which the
standalone job in `ci.yml` runs. Counted from both files at `453af0b`: 51 in the
job, 48 in the list. The three are added, so a local run of the list matches the
job again.

## Lessons worth keeping

GraphicsMagick reads the last pair of an 8 digit colour as transparency, not
opacity. `D9` drew 0.15 opaque and `26` drew 0.855. Any colour handed to it with
an alpha pair needs the pair inverted from the CSS reading.

A wrap that assumes an average character width overflows on wide capitals. The
fix was to measure: Arial advance widths, checked against Liberation Sans read
from the font file, and the node's wrap compared line for line with the wrap
n8n's Compose node uses.

A mutation test proves nothing about a value pinned in several places unless
every pinned copy is moved together. Moving one copy only proves the copies
agree with each other.

A privacy filter cannot be made safe by modelling the shell more closely. Four
rounds each found a new construct the reader took for a command. The class
closed only from the other side, with an allowlist on what may leave, so a
reader mistake now drops a word instead of sending one.

An editor that commits inside a worktree can move a branch ref the main checkout
shares. The main checkout then reads as dirty while its index still equals the
older commit's tree. Check that before resetting, and never commit those
changes as if they were your own.

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
  and `JEV_WIRING.md` (publish `fc75f7a6`) both name versions older than the five
  saves listed above. Publishing either now would also undo the NCO upload wiring
  and the three compliance node changes. Undoing the thumbnail fix alone would
  now mean editing that one node.
- Twelve hook nits remain. One is worth knowing before `SEND`: a TLS failure, a
  refused CONNECT and a dead proxy all write the same `URLError` row.
- Unverified: which `PATH`, `HOME` and shell the live harness gives a hook, and
  what the harness does with the wrapper's `exit 1`.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_jev-arc-close_v1_2026-10-28-2313.md
DATE: 2026-10-28
DECISIONS: Tee ruled on cards: hold #368 and rebuild the hook as an allowlist (2026-10-17); prove the image lanes in a standalone harness, draft them, then publish (2026-10-27); fix the thumbnail panel and overflow, prove first, then draft and publish (2026-10-27); send a program name only when it is a known command, and send only top level MCP field names (2026-10-28). The container never holds the TypeSafe key.
FINDINGS: GraphicsMagick drew the navy thumbnail panel about 15 percent opaque because it reads the last colour pair as transparency, and full headline lines ran past the panel because the wrap assumed 0.52 em a character; both fixed live as de4ac645 and still live in 51a807f7, read back byte for byte. Every shell reader version of the hook leaked some value as a program name until the known commands gate closed the class. The CLAUDE.md standalone list missed three rsi tests the CI job runs. The rollback versions named in the thumbnail and lanes records now predate five later saves.
OPEN: SEND, ENFORCE and each JEV_APPLY are rulings; the first real render through the lanes is unread; the stale rollback lines; twelve hook nits; the PATH, HOME and shell the harness gives a hook are unverified.
STATUS: #423, #422 and #432 are merged and #368 is closed. TQO FINAL V5 is active at 51a807f7 with versionId equal to activeVersionId, read 2026-10-28T23:09Z. The hook ships switched off.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
