# Data Tables resolve by id, on every workflow that is running

2026-09-16. Tee ruled three things on inline cards this session. This is the
first of them, and it is the one that closes a hole that was open the whole
time: every locator in an active workflow now names a table by id.

The count that matters is one line. **No active workflow in this estate
resolves a Data Table by name.** Before: 33 that did, 31 of them inside the
pipeline that earns the money.

## Why a name was the fault

A Data Table resolved in NAME mode is only as stable as every OTHER table name
in the project. A new name that merely CONTAINS an existing one captures it. On
2026-09-15 at 23:38Z a concurrent session created `at_tqo_content` and
`at_tqo_content_primitives`, both carrying `tqo_content` inside them, and from
that minute name resolution stopped reaching the real table.

Almost nothing failed. Of 73 by-name nodes, exactly one threw, because it alone
filtered on a column the wrong table lacked. The other 72 returned zero rows and
carried on, so the TQO lane was not failing for four and a half hours, it was
finding no work and saying nothing.

Tee ruled the instance fix that morning, rename the longer table. He ruled the
durable fix on the card this session: resolve by id. An id is unique and
immutable and cannot be captured.

## The card I put the ruling on was wrong about the cost

The option read like 31 find-and-replaces. It was not. Only four of V5's thirty
one locators carry a literal table name. The other twenty seven compute one at
run time from a field called `tableId` that holds a NAME, minted by five
`Show Context: *` nodes, carried on by five `DT Unpack: *` nodes as `__table`,
and passed along by six more. Converting the locators alone would have pointed
id mode at a name and all twenty seven would have refused.

That was said out loud before continuing rather than after, because a ruling
made on a wrong cost is not the ruling that was given.

## The shape of the fix: additive, so a miss survives

`tableId` and `__table` keep their values and their meaning everywhere. A new
`tableRef` and `__tableRef` carry the id beside them, and only the locators
moved. Two consequences, both deliberate:

A node the transform missed keeps working on the old path rather than breaking.
And a locator pointed at a ref nobody set fails loudly instead of returning zero
rows, which is the exact silence that made the original incident expensive.

## What was measured before anything was touched

| claim | how it was checked |
|---|---|
| id mode evaluates an expression | probe `2RQX9mrwJTvqGATQ` execution 268 read `tqo_content` three ways, id via expression, id literal, name via expression. All three returned the same 40 rows. |
| id mode cannot fall back to name resolution | n8n REFUSES at save time to accept a locator with mode id and value `tqo_content`: "data table with id 'tqo_content' not found". |
| the real Show Context bodies emit a correct ref | all ten branches, five nodes by TQO and NCO, executed in Node against the converted bodies. Ten of ten correct. |
| the composition resolves end to end | execution 278. The real Show Context body feeding V5's real converted locator returned rows 6 and 7 at status Idea, honouring `scriptLimit: 2`, no errors. |

The second row is the one that makes this a fix rather than a repaint. If id
mode quietly fell back to names, converting would have changed nothing and
looked like everything.

## Applied offline first, then staged, then published

The conversion ran against the exported workflow before a byte reached n8n: 240
nodes before and after, connections byte identical, 48 nodes changed and every
change confined to `parameters`.

It went in as a DRAFT in six stages, which cost nothing because a draft does not
touch the active version. That removed the schedule pressure entirely: V5 runs
`0 */3 * * *` in `America/New_York`, so the next pass was 10:00Z, and a 48 node
edit does not go in front of a scheduled run.

Seventeen of those nodes are live production code bodies, 32 kB of them, and
they had to be reproduced exactly. So the whole draft was read back and diffed
against the offline version before publishing: 102 code nodes compared, zero
mismatches, 31 of 31 locators on id mode. Then published.

| workflow | locators | active version | revert to |
|---|---|---|---|
| TQO FINAL V5 `qEkGOUsNyVaRAmm6` | 31 | `39874380` | `23735e68` |
| DEVON Pipeline Watchdog `IZBVlXQ8Y5dsGTRS` | 2 | `9b4d682f` | `9e937aaf` |
| TQO FINAL V5 - ADAPTER TEST `a11aa1a50e871723` | 29 | inactive, saved not published | n8n version history |

The adapter copy was handed back on the first card and Tee ruled on a second
card to convert it as well. It is inactive, so it was saved and deliberately
NOT published: publishing an inactive workflow in n8n activates it, and nobody
asked for that. Verified the same way, 222 nodes, connections identical, 46
changed, zero mismatches, 29 of 29 locators on id.

Its `Show Context: Render` was the one body that differs from V5's, and only
the table reference was converted in it. That copy still carries the retired
clone id `LLhnFOCTr3y3wrH59DtJ` and the fixed `provider: 'elevenlabs'` literal
that V5 replaced on 2026-09-10 because it credited the clone while Speechify
spoke. That is a second reason not to activate this workflow as it stands, and
fixing it is a separate ruling rather than something to fold in here.

## The miss, and the guard that now catches it

`Winner: Build Re-expansion` minted the ref at the top and then rebuilt its
items in a closing `rows.map` that forwarded `tableId` alone, dropping the ref
before the unpacker saw it. The conversion report did not show it, because a
report says what CHANGED and not what survives to the edge. It was caught by
reading the converted body.

`audit()` now walks every emitter and fails when a `tableId` has no `tableRef`
beside it, and it is tested against that exact mutation rather than only against
the fixed body:

```
audit on the real converted workflow: clean
audit on the mutated workflow: ['Winner: Build Re-expansion line 43: emits tableId with no tableRef beside it']
```

## The check the arc was required to carry

Tee's ruling 4 on the vision card, recorded in the `_2026-09-16l` doc, said this
arc must carry a check that counts name mode nodes from the estate, so the count
cannot drift the way it did and so a new one cannot be added quietly. That is
`scripts/n8n_name_mode_check.py`, over the pure `name_mode_locators` in
`services/devon/data_tables.py`.

It fails on an ACTIVE name mode locator, reports inactive ones without failing,
because a permanently red guard is a guard nobody reads, and exits 2 rather than
0 when it cannot read the estate. That third answer is the whole lesson of the
original incident. Its own count was wrong on the first run, reading 224
workflows from 112 files because the export writes an index as well as a file
per workflow, which a check written to stop a count drifting had no business
getting wrong. Deduplicated by id, and there is a test for it.

## What I got wrong this session

I reported no open pull requests and built on it. The call used a lowercased
repository name and came back empty; with the correct casing PR #249 was open,
and PR #248 had already landed the presence read-back work I then duplicated.
The branch was reset onto `45837de` and the duplicate is gone from it. The
lesson is narrow and worth keeping: an empty list from an API is not evidence of
an empty set until the query is known good.

One thing that landed in that PR is worth correcting. It says
`livekit_configured: false` is "pinned false by test_presence_service.py:106".
That test builds the app from the TEST environment, where the LiveKit variables
are unset, so it pins the local value and says nothing about production.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_data-tables-resolve-by-id_v1_2026-09-16m.md
DATE: 2026-09-16
DECISIONS: Tee ruled on an inline card to convert Data Table resolution from name to id, and on a second card to convert the inactive ADAPTER TEST copy as well after it was handed back. The conversion is additive rather than a rename: tableId and __table keep their values and their meaning, a tableRef and __tableRef carry the id beside them, and only the locators move, so a missed node keeps working on the old path and a locator pointed at an unset ref fails loudly instead of returning zero rows. DEVON Pipeline Watchdog was converted alongside V5 without a separate ruling, because it is the only other ACTIVE workflow with by-name locators and two literal ids close the active surface completely. TQO FINAL V5 - ADAPTER TEST was handed back on the first card and converted on the second; it was saved and deliberately NOT published, because publishing an inactive workflow in n8n activates it and nobody asked for that. Everything went in as a draft first, in six stages, because a draft does not touch the active version and that removes the schedule entirely.
FINDINGS: The card understated the work: only four of V5's thirty one locators carry a literal name and twenty seven compute one at run time, so converting the locators alone would have pointed id mode at a name and all twenty seven would have refused. Two facts were measured rather than assumed: id mode evaluates an expression, proven by execution 268 returning the same 40 rows three ways, and id mode does not fall back to name resolution, proven by n8n refusing at save time to accept tqo_content as an id. That refusal is what makes this a real fix. Execution 278 then proved the composition with the real Show Context body feeding V5's real converted locator, returning rows 6 and 7. One real miss: Winner: Build Re-expansion minted the ref and then dropped it in a closing rows.map that forwarded tableId alone, invisible in the conversion report because a report says what changed and not what survives to the edge; audit() now catches it and is tested against that mutation. The offline pass held 240 nodes before and after with connections byte identical and all 48 changes confined to parameters, and the published draft was read back and diffed: 102 code nodes compared, zero mismatches. The estate now reads 96 id mode locators against 58 before, 44 still on name and every one of them inactive. The new guard's own count was wrong on its first run, 224 workflows from 112 files, because the export writes an index beside the per workflow files. And I reported no open pull requests from a query that used a lowercased repository name and returned empty, then duplicated work that PR #248 had already landed; an empty list is not evidence of an empty set until the query is known good.
OPEN: 15 name mode locators remain and all of them are inactive and defensible: 7 in DT Bootstrap Tables, which creates and drops tables by name as its actual job, 3 in S5 Seed, and 5 in throwaways. Throwaway 8dsCOEDaG7Tnu5Sb cannot be archived from here because MCP access is off on that workflow, so it needs archiving in the n8n UI. TQO FINAL V5 - ADAPTER TEST is converted but still carries a retired voice clone id and the fixed provider literal V5 replaced, so it is still not safe to activate for reasons that have nothing to do with table ids. The conversion has not yet been observed in a real scheduled V5 pass; the next is 13:00Z and it has not run. The two other rulings from this session, building the LiveKit room publisher and making an empty balance 400 surface its real body, are not started. PR #248 states that test_presence_service.py:106 pins livekit_configured false for production; it pins the test environment's value and that correction is not yet filed anywhere but here.
STATUS: Done and published on both active workflows, and saved on the inactive adapter copy, proven four ways before publishing and read back byte for byte after. The durable fix Tee ruled is live on every workflow that runs. The remaining 15 name mode locators are all inactive and all defensible.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
