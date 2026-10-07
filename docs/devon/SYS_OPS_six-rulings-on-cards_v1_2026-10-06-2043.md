# Six open items ruled on cards, and two of them done the same hour

Tee asked for every open ruling on an inline card. The open list came from the
OPEN key of `SYS_OPS_show-registry-steps-one-and-two_v1_2026-10-06-1612.md`,
and it held six items. They went out on two cards of four and two, and rows 4
and 5 came back for a third card once they had been read live. This doc
records each ruling, what was done on it, and what was measured.

## The chat agent lane is disabled in V5

Ruling: disable it now rather than wait for the split.

The lane is seven nodes in `TQO FINAL V5` (`qEkGOUsNyVaRAmm6`): `When chat
message received`, `AI Agent`, `Google Gemini Chat Model`, `Simple Memory` and
three HTTP tools. `READER` GETs any workflow by id, `CREATOR` POSTs a new one
and `UPDATER` PUTs any workflow on the instance. Reading the live connections
showed nothing outside the lane wired into it, so disabling all seven touches
no other path.

The edit went in as a draft through `update_workflow`, seven `setNodeDisabled`
operations. Before publishing, the draft (`36013f35`) was diffed against the
live version (`3befd7a5`) node by node: 265 nodes on both sides, the same
names, the seven `disabled` flags the only difference, the connections
identical. `publish_workflow` moved `activeVersionId` to `36013f35`. The read
back shows `versionId` equal to `activeVersionId`, `active` true, and all
seven nodes disabled inside `activeVersion`. The nodes stay in the graph until
the split removes them.

The exports are regenerated from `36013f35`, and their diff is the seven flags
plus the version stamp. `SOURCE.version_id` in the show registry names it, in
both copies.

## The registry check runs daily

Ruling: a daily GitHub Action on the secret the watchdogs already use.

`.github/workflows/registry-check.yml` runs `scripts/show_registry_seed.py
--check` at 07:41Z every day and on `workflow_dispatch`. It reads and never
seeds. It goes red on drift and on a missing `N8N_VPS_KEY`. Measured here
before committing: the script ran CLEAN against both tables from a venv with
no packages installed, exit 0, and exited 1 with `N8N_VPS_KEY is required`
when the key was unset. It also ran under Python 3.11, the version the job
pins. A schedule only workflow does not fire until it is on `main`, and the
two watchdogs took five and six hours to fire their first scheduled run, so
the first proof after merge is a `workflow_dispatch` run. CLAUDE.md now counts
twelve jobs, read from the `jobs:` keys of the eight workflow files.

## The Avatar lane holds for the two looks

Ruling: nothing moves until Tee approves two landscape looks. Draft `206299ba`
stays in version history. HeyGen's 2026-10-31 removal of v1 and v2 does not
touch it, because the lane calls only v3.

## The Sunday Brief goes to Tee first

Ruling: wire the lane to Reach and send one Brief to Tee's address only, for
him to read end to end before any list receives it.

The lane was already wired to Reach. It never sends: it creates a template and
an unsent campaign, and the send happens by hand in the Reach dashboard. Its
two manual entry points also fan into Script, Promote, Render and Publish, so
on a second card Tee ruled a temporary trigger wired only to the TQO Brief.
It went into the draft alone and was never published: the draft was diffed
against live (`36013f35`) and differed by that one node and its one edge. It
was fired once in manual mode as execution 2295 and then removed. The draft
graph reads back identical to live, and production never left `36013f35`.

The test found a defect, and nothing it made should be sent. Execution 2295
succeeded and created template `355f83f8` and campaign `8d28dba8` in Reach,
subject "Brief cannot be generated", headline "No script provided". The lane
took row 5, but the script never reached the writer. `Build Brief Prompt`
reads `$('Get Latest Content')`, the raw data table row, whose keys are
lowercase, and then looks for `f.Script`. Only `DT Shim: Latest Content`
produces `Script`, and its output in the same run carries all 8,156
characters. So on the data table path the writer gets an empty script every
time. Nothing checks for that: both Reach check nodes test only for an HTTP
2xx and a uuid. The signature line in `Assemble Email HTML` also carries an
`&mdash;`, which Tee's voice rules forbid. Had the script reached the writer,
this Brief would have been about row 5, whose named claims are not sourced
yet.

## Rows 4 and 5, read live

Both rows were read from `tqo_content` (`2GtmrFcTNqVMbddh`) at about 20:39Z
and put on a card from what they say now.

Row 4 is TQO S1E1, "An AI Agent Did My Work for 7 Days: The Honest Log":
status Ready, human review ticked, QC SHIP 88, written in a Claude session on
2026-09-15. OS 30 held it at 2026-10-01T17:32:48Z on one check, asset native
fit: four en dashes in `platform_packaging`, and a packaging grade of 6.8
against a floor of 7.0. Its description says "Presented with a synthetic voice
and synthetic likeness of Terrance Veal", and the render telemetry reads 45
clips with no presenter.

Tee ruled that the seven days happened as the script tells them, and that the
row ships by re-rendering with the presenter through the Avatar lane, which
makes the likeness line true, with the packaging dashes fixed now. The four
dashes were rewritten as sentences and a colon, not swapped for a comma, by
one PATCH filtered on `id = 4`. A dry run first returned exactly one row,
before and after. The read back shows the new text byte for byte, zero
dashes, and no other column changed. The fix does not lift the 6.8 grade; the
gate grades that again when the row next passes through it.

Row 5 is The AI Shift S1E2, "AI job replacement is wrong: why jobs decompose,
not disappear": status Ready, rendered on 2026-09-16 with 45 stock clips, no
QC verdict, human review unticked. The script was written by the Cerebras two
pass writer. It names outcomes at "Bank of America's finance analyst team" and
at "Amazon's fulfillment centers", and a "regional bank" case study, with no
source anywhere on the row. Tee ruled: each named claim gets a source or comes
out, then the script goes through QC and the gate, then a fresh render. Open
at the time of writing.

## The writer of record and the first stage wait a day

Ruling on both: read the 2026-10-07 10:20Z pass on row 46 under the tightened
close rule first. The writer card comes back with that result in it, and the
Script stage is built after it as a workflow that does not run until Tee
publishes it.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_six-rulings-on-cards_v1_2026-10-06-2043.md
DATE: 2026-10-06
DECISIONS: Tee ruled on inline cards: disable the V5 chat agent lane now; run the registry check daily as a GitHub Action; hold the Avatar lane for two approved looks; send the Sunday Brief to him alone before any list; re-read rows 4 and 5 live before ruling; start the first stage after row 46's pass. On the rows card he ruled row 4's seven days true as told, row 4 to re-render with the presenter and its packaging dashes fixed now, row 5's named claims sourced or cut before QC, and the writer of record decided after row 46.
FINDINGS: The chat agent lane is seven nodes that nothing else connects to, and two of its tools can POST or PUT any workflow on the instance. V5 published as 36013f35 with only the seven disabled flags changed, read back. Row 4's description claims a likeness its 45 clip stock render lacks, and its OS 30 hold is four dashes plus a 6.8 packaging grade. Row 5 is rendered but never QC'd and names a bank and a retailer with no source. The Brief lane's prompt node reads the raw row instead of the shim, so the writer always gets an empty script, and execution 2295 put a draft titled "Brief cannot be generated" into Reach reporting success. The registry check runs on bare stdlib Python 3.11 and 3.13.
OPEN: The Brief lane fix (read the shim, refuse an empty script, take the dash out of the signature) and what happens to Reach drafts 355f83f8 and 8d28dba8, both Tee's to rule; the test send to Tee waits on the fix. Row 5's claims sourced or cut, then QC, then a re-render. Row 4's re-render once the Avatar looks are approved, and the 6.8 packaging grade regraded. The 2026-10-07 10:32Z read of row 46's pass, then the writer of record card and the Script stage build. The first workflow_dispatch run of registry-check.yml after merge.
STATUS: V5 active and draft both 36013f35, read back; tqo_content row 4 platform_packaging rewritten and read back; registry-check.yml committed in this doc's PR, which had not run CI at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
