# TQO FINAL V5 does not need streamlining, it needs splitting, and the first locked row could not reach the writer

Tee asked one question on 2026-10-06: does TQO V5 need streamlining, or how
would the pipeline be built. The answer is measured rather than argued, and
the measuring found the defect that had kept every locked row away from the
writer, fixed it, proved the fix, and found the next gate behind it. Four of
the five claims the assessment started from were corrected by refuters before
anything was built on them, and the corrections are recorded here first.

## The five claims and what the refuters did to them

Twenty six agents ran over one pulled set of files: the workflow (draft and
published), its 167 executions from 2026-09-22, the two content tables, the
QC verdict table and the record. Four readers, three designers, three judges,
fifteen refuters, one critic.

1. Zero YouTube publishes since 2026-09-03: held. `published_url` is empty on
   all 48 tqo_content rows and all 28 nco_content rows, and the two upload
   nodes ran in none of the 167 executions. The channel itself was not read.
2. "Every scheduled run since 09-30 exited without writing anything": corrected.
   Twenty eight scheduled runs wrote no script, render or publish, but three
   Daily 6am passes (1722, 1793, 1917) wrote `package_options` onto six rows.
3. "The only SHIP script was written and judged outside V5": corrected. Two
   different scripts reached SHIP in two stores: tqo_content row 4, written in
   a Claude session on 2026-09-15 and judged SHIP 88 by V5's own `Run QC
   (Cerebras)` node, rendered, never published, with a description that
   discloses a likeness the file does not contain (45 stock clips, 0 presenter
   clips); and the s01e01 Google Doc, drafted through the bot lane and judged
   SHIP 81 in bot_qc_verdicts, present in no content table.
4. "290 nodes, 23 roots, grown from 240": corrected. The published version
   e04868cf was 265 nodes, 22 roots, 17 trigger type nodes; 290 was the
   unpublished draft 206299ba, which added the 24 node HeyGen Avatar lane and a
   TEST trigger. The README's 240 was a sentence, not a measurement.
5. "The 41 Idea rows are held at one gate": corrected to 40 of 41. Row 46 had
   been locked by Tee at 2026-10-05T22:25:48Z and was the first locked TQO row
   ever to reach a pass. And a second barrier sat behind the gate, which is the
   next section.

## The IF node, measured, fixed and proven

`Script: Already Written?` was an IF node at typeVersion 1 carrying a
typeVersion 2 condition shape. The engine copy in the executions read
`{"conditions": {}, "combineOperation": "all"}`, and IF v1 (upstream
`packages/nodes-base/nodes/If/V1/IfV1.node.ts`, the item loop) sends an item
with nothing to test to its TRUE output, wired to `Script: Hydrate from Row`,
which throws on an empty script. Predicted from source at 09:50Z and measured
at 10:20Z: scheduled execution 2257 took row 46 TRUE out of that node and died
at line 12 of the next one, no script written. Error handler execution 2258
sent the fault email at 10:20:06Z, the first handler send seen since the
2026-10-02 to 10-05 mail outage.

On Tee's rulings: the published version e04868cf was restored as the draft,
the node recreated at typeVersion 2 with identical parameters, id, position
and edges, read back as the only difference between draft and published
(265 nodes each, connections identical), and published as 3123aef0 at
12:22:18Z. One watched pass fired on the published version: execution 2269 at
12:23:19Z took row 46 out of the FALSE edge, wrote the script through `Write
Script (Cerebras)` and one expansion (828 to 1,465 words), ran the doctor (76,
repaired), dash repair (11 sentences restructured, 0 dashes left) and the
originality scan (95), saved it, and then the Script Gate held the row at
status Error on one rule, line 69 of `Script Gate: Quality`: the last 60 words
must carry a question mark and the word comments. The script ended on a
question that never said comments.

Tee ruled the close rule tightened rather than the draft accepted: the draft
also opened on an unsourced Layoffs.fyi figure and cited a company the doctor
flagged as invented. The CLOSE line of `Build Script Prompt` gained one 26 word
sentence, the canon rule `tqo.close.one-quiet-cta` carries the same sentence,
and the block was re-measured from the mirror at 999 words and 5,937
characters, under the 1,000 word guard the test keeps. The live node was
updated from the mirror through the public API and read back byte identical
(sha256 d14651cd17f4). Row 46 was set back to Idea with its `script` and
`script_machine` cleared, because the 10-01 Hydrate ruling reuses a script
that already sits on a locked row, so the gate note "set status to Idea to
write it again" has been stale since that ruling. The 2026-10-07 10:20Z pass
is the next measurement.

Two things learned about the instance on the way. A REST `PUT
/api/v1/workflows/{id}` on an active workflow publishes in place: versionId
and activeVersionId moved together to b99b38ab, with no draft step, so the
rule that an edit is a draft until published holds for the MCP tools and not
for the REST PUT. And the `rows/update` endpoint on data tables works with a
filter and a `dryRun` flag, which is how row 46 was flipped and cleared.

## The exports, the audit, the Gumroad path

PR #303 put both versions of the workflow into the repository under
`n8n/tqo-v5/exports/`, written by `scripts/tqo_v5_export.py` with the read
time inside each file, and `test_tqo_v5_exports.py` parses the README's
version table by role and carries the IF allowlist, which emptied the moment
the fix was published and the exports regenerated. Codex found three things
on that PR and all three were real: the README assertions were global
substrings a swapped pair would satisfy, `--from` derived the read time from
a file's mtime, and the exports carried the Gumroad sale ping's webhook path,
which has no authentication and whose random suffix is that door's only
barrier. The exporter now redacts every webhook path and id, the test proves
the Gumroad path is absent, `--from` requires `--read-at`, and on Tee's ruling
the live path was rotated to a fresh suffix and published as 22519c20, with
the new ping URL handed to him for the Gumroad side and kept out of the
repository. The old path sat in the branch history for about two hours.

PR #304 cleared the dependency audit, red on every push since two advisories
landed after main's last green run: source-map-js below 1.2.2 and
postcss-selector-parser below 7.1.6, both bumped through `pnpm.overrides`
with the lockfile regenerated by pnpm and the web build proven under the 7.x
parser. Both PRs merged on Tee's word.

## The verdict and the design

V5 does not need streamlining. Its lanes work: the gate code implements the
16 Sep ruling exactly, the render lane finished 39 of 41 worker jobs, and the
Script Gate and OS 28 gate held row 4 on their own rules twelve times. The
container fails: six entry doors that fan 209 to 214 nodes so a dead Brief
lane turned 28 finished renders into error executions, one `One Idea at a
Time` loop shared by both shows that drops the second show's rows when the
first had work, fifteen Code nodes carrying both shows' canon inline, and a
Gemini chat agent inside the content gate whose UPDATER tool can PUT any
workflow on the instance.

All three judges picked the same shape and Tee ruled it: one small workflow
per stage, each with one trigger, coupled only through the content ledger and
a show registry, every prompt and gate body mirrored in the repository with a
test that fails on drift, V5 kept active as the fallback until each stage is
proven on one row. The judges' corrections ride with it: export both versions
before any V5 edit (done), one Dispatch workflow holding every schedule, the
five `Show Context` node names kept as executeWorkflow calls, one YouTube
upload node per credential behind a router, the ten prompt builders that
branch on isNCO named as the limit on "a fourth show is a row", the human
gate on its own credential rather than the Face's key, the review request
raised only after a Drive read shows the owner opened the file. The full
assessment with scores and receipts is in the session scratchpad; the first
migration step, the show registry module and its test, is the next PR.

## Hostinger Reach

Tee ruled on 2026-10-06 that Hostinger Reach is the email platform of record
for the studio, and the MailerLite path is retired. The lane that uses Reach
is dead at its credential: every `Reach: Create Brief Template` call in the
pulled executions answered `Unauthenticated.`, the last at 2026-10-01T20:28Z
(execution 1872), on the n8n credential named `Hostinger` that three nodes
carry (`Reach: Create Brief Template`, `Reach: Create Brief Campaign`,
`Gumroad: Reach Buyer Sync`). The node never errors, so those runs read
success. Nothing has called Reach since, so its state today is unverified. Tee
ruled he replaces the API token on that credential; one read only call through
the `ZZ Reach Lane Test` node then proves it before anything sends.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tqo-v5-assessment-and-the-if-node_v1_2026-10-06-1240.md
DATE: 2026-10-06
DECISIONS: Tee ruled the pipeline split by stage on the ledger, the IF fix applied on a draft restored from the published version and proven by one watched pass, the close rule tightened and row 46 rewritten rather than accepted, the Gumroad webhook path rotated, Hostinger Reach as the email platform of record with the MailerLite path retired, the Reach token replaced by him and proven by one read only call, and this doc filed. He authorized the merges of #303 and #304 and the publish of the IF fix in chat.
FINDINGS: Published V5 was 265 nodes against a 290 node draft; zero YouTube publishes since 2026-09-03; the IF node defect measured on execution 2257 and the fix proven on 2269; the Script Gate's comments rule and the writer prompt disagreed; the Hydrate ruling makes "set status to Idea" insufficient for a rewrite; a REST PUT publishes in place; the Gumroad path was exposed in branch history for about two hours; the Reach credential answered Unauthenticated on every call on 2026-10-01; two scripts reached SHIP in two different stores and row 4's description discloses a likeness its file does not carry.
OPEN: The 2026-10-07 10:20Z pass on row 46 under the tightened rule. The Reach token, Tee's to replace, then the read only proof. Rows 4 and 5 and which writer feeds the table, unruled. The Avatar lane and TEST trigger in version history 206299ba awaiting their own publish after two landscape looks are approved. The first stage split PR, the show registry module. The chat agent lane with workflow PUT inside V5, to be removed in the split.
STATUS: IF fix published as 3123aef0 and proven on 2269; close rule published as b99b38ab and read back; Gumroad path rotated as 22519c20; #303 and #304 merged; #305 (the canon change) open with its CI not yet run at the time of writing; row 46 is a clean locked idea.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
