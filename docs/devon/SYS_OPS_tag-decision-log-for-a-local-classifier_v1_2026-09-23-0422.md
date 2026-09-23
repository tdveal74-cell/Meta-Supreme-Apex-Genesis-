# Tag decision log for a local classifier

Ruled by Tee on 2026-09-23, after reading a cheat sheet for Jev, a vendor
classification model, and asking whether to build the model or buy it. The
answer was neither yet. Build the pattern (fixed answers, a confidence, a
threshold, a human below it) on one lane, and start with the data, because
the data does not exist. This doc covers step one: logging.

## Why this lane

`DEVON - iPhone Inbox Capture` (`CEy7WAl4QAzHfG46`) tags every capture with one
of nine Areas. It asks Cerebras, and when Cerebras refuses it falls back to
keyword hints. The fallback is recorded only as a sentence in Notes. A small
local classifier would take the provider out of this lane entirely.

The blocker is labels, not code. `Inbox Captures` held 13 rows on 2026-09-22.
A classifier needs a few hundred confirmed examples before its scores mean
anything.

## What changed

Three fields on `Inbox Captures` (`tbl4ziFRbl5mnUcKc`):

| field | id | written by | meaning |
|---|---|---|---|
| Tagged Area | `fldUOQIkF333gwofd` | the lane, once | the Area the machine chose |
| Tag Source | `fld2m30zLSF7O0iOm` | the lane, once | cerebras, keyword or none |
| Area Confirmed | `fldq7Mr38uyGFbnpG` | Tee | Area is correct, count this row |

`Area` stays the field Tee corrects. A row is a training label only once Area
Confirmed is ticked, so an unedited row is never mistaken for an approved one.
`Triaged` belongs to the Duplicate Sweep and was deliberately not reused.

`Index Capture` now maps `Tagged Area` from `$json.area` and `Tag Source` from
`$json.area_source`. `Apply Area` already computed `area_source` on every run
and nothing wrote it anywhere; the source of each tag was being thrown away.

The ids are recorded in `services/devon/vault.py` as `INBOX_TAG_LOG`, with the
vendored copy under `deploy/soul` synced by `cp`.

## Proof

Published and read back: `versionId` and `activeVersionId` both
`881a2a3c-c29f-46a1-8c58-5529823d7578`, `activeVersion.sameAsDraft` true.
The previous live version is `90ec4be9-b49e-4aa8-ba0e-c4e8312c5f7d`, the revert
target.

Manual execution 823 at 2026-09-23T04:22:18Z posted a text capture. The row
`recEMPR3rYsCE6jue` was read back from Airtable itself, not from the node
output: Tagged Area `Systems`, Tag Source `keyword`, Area `Systems`. The row was
then deleted. A production webhook request has not been sent; the manual run
executes the same published graph.

The same execution took HTTP 402 from Cerebras at 04:22:18Z, `payment_required`.
The provider outage is still live, so every capture logged today will read
`keyword` or `none`. That is the log telling the truth, and it is the case for
this work.

## What the estate holds to learn from

Measured the same day, on Tee's instruction to check the n8n data tables too.
All 55 tables on n8n.editforge.online were listed with their columns, and every
one that could hold a labelled decision was counted.

The 300 row threshold is not reachable at the current rate. Of the 13 rows in
`Inbox Captures`, one is a real capture (`SHORTCUTSBUILDGUIDE 2.md`, 2026-08-06).
Nine are shortcut tests: four titled `title`, three `Untitled capture`, one
`Provided Input` and one `2331756`. Three are executor proof rows for Builds 14
and 17 and the VPS cutover. Seven weeks of the lane produced one labelable row.

No other table is a shortcut:

| source | rows | what they are |
|---|---|---|
| `at_tqo_inbox_captures` `0tmm2baLwVWFdZAR` | 11 | one time copy at 2026-09-15T23:38:32Z, never updated, missing the two later rows |
| `devon_state_ledger` `QZvdxllOjWevb3Vo` | 9 | proof and test jobs |
| `devon_hearing_log` `Tht7qGrqF66E48EA` | 1 | a throwaway probe |
| `at_tqo_audience_intelligence` `Q8bQ41V0Oz7xHrCt` | 0 | |
| `devon_chat_log` `DKCusDJfIF8CPxyb` | 0 | |
| `script_exemplars` `k3A66wV0vUoeaElo` | 0 | |
| Airtable `Thread Receipts` `tblEhgEZoNr2ztbB3` | 4 | carries an Area, too few |

The mirror table was deliberately left alone. Nothing writes it, so adding the
three new columns to it would record nothing.

The logging stays: it costs nothing per capture and it is correct. What changed
is the premise of step two. Which way the plan goes from here is Tee's ruling.

## Next

1. Tee ticks Area Confirmed on captures as he reviews them, fixing Area first
   when it is wrong.
2. At about 300 confirmed rows, train a small classifier (ModernBERT or
   SetFit), calibrate it, and run it in shadow beside the live tagger.
3. Only after the shadow comparison does it decide anything, above a threshold,
   with the rest left for Tee.

Jev early access stays an option, to be tested against these same rows rather
than against its own published numbers.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tag-decision-log-for-a-local-classifier_v1_2026-09-23-0422.md
DATE: 2026-09-23
DECISIONS: Tee ruled "Go with your recommendations": do not build a general model, build the typed decision pattern on the iPhone capture tagger, log labels first, train at about 300 confirmed rows, shadow before deciding.
FINDINGS: Apply Area computed area_source on every capture and nothing persisted it. Cerebras still answered HTTP 402 at 2026-09-23T04:22:18Z. All 55 n8n data tables checked: no source in the estate holds labelled decisions in volume, and Inbox Captures holds one real capture in seven weeks, so the 300 row threshold is not reachable at the current rate. at_tqo_inbox_captures is a frozen one time copy.
OPEN: Whether to park the classifier, fix the Cerebras billing instead, or seed labels by hand is Tee's ruling. Cerebras billing remains unresolved.
STATUS: Three fields created, Index Capture published and read back, one probe proven from the store and deleted.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
