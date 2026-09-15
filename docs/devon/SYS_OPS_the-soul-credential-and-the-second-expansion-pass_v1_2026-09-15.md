---
title: The soul credential and the second expansion pass
type: SYS_OPS
version: 1
date: 2026-09-15
area: Systems
status: recall live on V5, second pass published and not yet exercised
owner: DEVON
---

# The soul credential and the second expansion pass

Two things happened on the VPS after
`SYS_OPS_the-two-pass-writer-and-the-owned-presenter_v1_2026-09-15.md` was
filed: the 401 between TQO FINAL V5 and devon-soul was found and closed, and
the writer gained a second expansion pass on a ruling by Tee. This document
sits after that one in the same day.

## The 401, measured instead of guessed

Every probe of devon-soul from the VPS since execution 86 had answered 401 on
`/api/v1/soul/status` and `/api/v1/soul/recall`. The suspects were the Vercel
variable, the Vercel deploy, the n8n credential and the token characters. The
deploy was ruled out first: `deploy/soul/REDEPLOY.md` merged in PR #227, the
production build on bd34b23 recorded READY, and a dashboard redeploy of it at
17:06Z (dpl_A5vKKS7v2rJgrAT44YHaczJhPjRz) also recorded READY. Probe execution
94 against that deployment still answered 401 on both routes.

The credential side cannot be read through the MCP tools, so it was measured
with an echo: a throwaway workflow on the same n8n instance with a webhook
door and a manual branch that calls the door using the credential under test.
The door's Code node reports only the shape of the `Authorization` header,
the length, whether it begins with `Bearer `, whitespace, and the character
classes present, never the value or any prefix. Its production executions were
set not to be stored. Three readings:

| credential | reading | devon-soul |
|---|---|---|
| Devon Soul Service Token (9meOVz4mM5q4f7BR), execution 95 | 74 characters, no Bearer prefix, characters `_ = : / - .` present | 401 |
| the same, execution 98, after Tee reported the credential updated | identical to execution 95 | 401 (execution 97) |
| Devon Console Token (JSBvIdHJ9UUQRXwH), execution 100 | `Bearer ` plus 32 characters, letters and digits only | 200 on status and recall (execution 102) |

`deploy/soul/main.py` strips the first seven characters of a header that
starts with `bearer ` and compares the rest against `CONSOLE_TOKEN` on bytes,
so a value with no prefix can never match. The Cloud n8n also carries a
credential named Devon Soul Service Token (SFou54MzuKGj3MwV), which is where
an edit made on the wrong instance would land; that was not verified and does
not need to be, because the VPS credential that answers 200 exists.

The fix was one change to V5: the `DEVON Recall: Ask` node now uses the Devon
Console Token credential. Published as version 5b688ce8; the version diff
against dc5f4f02 shows that node's credential id and name and nothing else.
The echo workflows and the probe are archived, and an archived workflow's
executions cannot be read through the MCP tools, so the three readings above
and the probe results are this session's testimony until Tee unarchives
q8bds72Sw4zv8Jwg in the n8n UI and reads executions 94, 97 and 102 himself.
The stale credential is Tee's to delete, since no MCP tool here deletes a
credential.

## Proof run 104: recall live, gate holds on length

Row 5 of `tqo_content` was set from Script Hold back to Idea and the writer
schedule was enabled, fired once by hand, and disabled again, published as
b3054314. Execution 104, 27 seconds:

| step | result |
|---|---|
| DEVON Recall: Merge | 4 records, 4 from Tee, 0 from DEVON |
| Build Script Prompt | the FROM DEVON block is in the system prompt, carrying the four records the recall returned for this topic: the 2026-09-05 ruling that DEVON is deliberately unfed, the 2026-08-22 security thread close, the 2026-09-05 identity ruling, and the 2026-08-24 build freeze lift. Not the 2026-09-08 Sisinty rulings; those came back to the probe's different query and the first draft of this document said they were here |
| Fetch Script Exemplars | 0 rows, `script_exemplars` is empty until Tee edits a script by hand |
| first draft | 859 words |
| expansion | 859 to 1184 words |
| doctor | REPAIRED 90 of 100, trimmed to 1144 words |
| dash repair | 4 sentences restructured, 0 dashes remain |
| originality | rhythm 88, similarity 100 |
| gate | HOLD, 1144 words under the floor of 1200 |

The recall line in the gate report changed from the 401 note to the count,
which is the sentence this arc existed to produce. The hold was a real hold:
the expansion under-delivered against its 1800 to 2200 target and the doctor
took forty words off the top of that.

## The ruling and the build

Tee ruled on an inline card: a second expansion pass when the expanded draft
is still under the floor, capped at two passes, before the doctor. Four nodes
were added to V5 in version af87dc83. Six versions were published in this
window, and a restore or a diff should name the right one: 5b688ce8 (the
credential), 5660045e and b3054314 (the writer schedule on and off around run
104), af87dc83 (the four nodes), 1598bf9e and 09cfde8d (the schedule on and off
around run 106). 09cfde8d is the live head:

```
Parse Expanded Script -> Script: Still Short? -> Expand Again?
  true  -> Expand Script 2 (Cerebras) -> Parse Expanded Script 2 -> Build Doctor Prompt
  false -> Build Doctor Prompt
```

`Script: Still Short?` reuses the first pass system prompt and brief from
`Token Budget: Script`, tells the model this is the last expansion, and asks
for at least the larger of 400 words or the gap to 1800. `Parse Expanded
Script 2` has the same contract as the first parser: a truncated, empty,
unparseable or no-longer result keeps the text that entered the pass and
appends the reason to the expansion note, so a failed pass never costs the
draft. The version diff from b3054314 to 09cfde8d shows the four nodes, one
connection removed and six added, nothing modified, and every schedule
disabled; the two schedule toggles between them net to zero, and run 106
started under 1598bf9e with the writer schedule enabled for those eleven
seconds.

## Proof run 106: gate passes, second pass not exercised

Row 5 back to Idea, schedule enabled, fired once, disabled, published.
Execution 106, 11 seconds:

| step | result |
|---|---|
| DEVON Recall: Merge | 4 records, 4 from Tee, 0 from DEVON |
| first draft | 999 words |
| expansion | 999 to 1304 words |
| Script: Still Short? | 1304 is at or over the floor, so `needsExpansion2` is false and the second call was skipped |
| doctor | REPAIRED 80 of 100, 1261 words |
| dashes | 0 |
| originality | rhythm 100, similarity 100 |
| gate | PASS, cleared for Promote, status Scripted |

So the skip branch of the new lane is proven and the call branch is not:
`Expand Script 2 (Cerebras)` and `Parse Expanded Script 2` have run zero
times. The next row whose first expansion lands under 1200 words is the live
proof, and its gate report will read "then a second pass to N words".

## What this window did not do

- No test of the second pass call branch. It has the same shape as the first
  pass and the same keep-the-draft rule, and that is a claim until a run
  shows it.
- Row 5 is Scripted at 1261 words and doctor 80, unread by a human. The
  doctor's notes on run 104 removed the audit link from the close as a
  solicitation, which is the brand's one primary ask; whether the doctor's
  rule is too wide is a call for Tee.
- The stale VPS credential and the Cloud copy still exist.
- The workflow was edited on the live instance and read back through version
  diffs, not through a critic mutating the source; the code of the four nodes
  is in this repository only as the description above.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-soul-credential-and-the-second-expansion-pass_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: Tee ruled on an inline card on 2026-09-15 that the writer runs a second expansion pass when the expanded draft is still under the 1200 word floor, capped at two passes, before the doctor; the V5 recall node was pointed at the Devon Console Token credential because it is the one that answers 200, and the stale Devon Soul Service Token credential is Tee's to delete.
FINDINGS: the 401 was the n8n credential and not Vercel, on this session's readings of executions that are now behind archived workflows and unreadable through the MCP: three echo readings showed the Devon Soul Service Token credential sending a 74 character value with no Bearer prefix, unchanged after Tee's edit, while Devon Console Token sends Bearer plus 32 characters and answered 200 on status and recall in probe execution 102; V5 versions 5b688ce8 (credential) and af87dc83 (second pass) carry the changes, six versions were published in the window and 09cfde8d is the live head, each read back by version diff; run 104 wrote with 4 recalled records in the prompt (2026-09-05 unfed, 2026-08-22, 2026-09-05 identity, 2026-08-24; not the Sisinty rulings) and held at 1144 words after an 859 to 1184 expansion and a doctor trim; run 106 wrote with the same 4 records, expanded 999 to 1304, skipped the second pass, and passed the gate at 1261 words with doctor 80, zero dashes and rhythm 100; the second pass call branch has run zero times.
OPEN: a row whose first expansion lands under 1200 words to exercise Expand Script 2; Tee reads the row 5 script before Promote and rules on the doctor treating the audit link as solicitation; Tee deletes the stale VPS credential; script_exemplars stays empty until a hand edited script reaches Promote; all six V5 schedules stay disabled until Tee's watched pass.
STATUS: recall live on V5 at version 09cfde8d, second pass published and not yet exercised. Nothing published to YouTube, nothing merged, nothing deployed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
