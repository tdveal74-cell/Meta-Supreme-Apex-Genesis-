# The TQO lane was reading the wrong table, quietly

2026-09-16. TQO FINAL V5 went red on the VPS at 01:00:00Z and again at
04:00:00Z. The first report called it intermittent. It was not. It was
deterministic from 23:38Z the night before, and the loud failure was hiding a
silent one that mattered more.

## What broke

At 23:38Z on 2026-09-15 a concurrent session created its Airtable mirror tables
in the VPS project `qbrcjkbIoorbwot6`. Two of them carry the name of an existing
table inside their own:

| mirror created 23:38Z | contains |
|---|---|
| `at_tqo_content` | `tqo_content` |
| `at_tqo_content_primitives` | `at_tqo_content`, `tqo_content` |

From that minute, n8n's Data Table resource locator in **name** mode stopped
reaching `tqo_content`. Measured rather than inferred, with a throwaway probe
carrying one node and no filter:

```
By Name "tqo_content"      ->  0 rows, no columns
By Id   2GtmrFcTNqVMbddh   -> 45 rows, status and video_title present
```

`at_tqo_content_primitives` has no `status` column, which is exactly the column
n8n reported missing, so that is where the name was landing.

## Why it looked intermittent and was not

The last green pass was 22:00:00Z on 2026-09-15, before the mirrors existed. The
next two, 01:00:00Z and 04:00:00Z, failed identically. One failure against one
older success is not enough to call anything, and calling it a flake was the
error. The 04:00Z repeat is what forced the next look.

## The silent half

`Render Lock: Other Brand` throws loudly because it filters on `status`, a
column the wrong table does not have. It is the only node in that lane that
does. Counted from the estate rather than guessed: **73 Data Table nodes across
106 workflows resolve a table by name**, 31 of them inside the active TQO FINAL
V5 and one more in the active DEVON Pipeline Watchdog. Every one of those that
lands on `tqo_content` at runtime was reading an empty table.

Without a filter, that is not an error. `Get Queued Videos`, `Get Idea Rows` and
`Get Ready to Publish` returned zero rows and the lane carried on. For four and
a half hours the TQO half of the content pipeline was not failing. It was
finding no work, and nothing said so.

`nco_content` was never shadowed by any name, so the NCO half kept working
throughout, which is part of why the shape was confusing.

## The fix, ruled by Tee 2026-09-16

Rename the two mirrors rather than edit the workflow. One rename each fixes all
73 nodes at once. Editing V5 instead would have meant 31 node changes inside 240
nodes, plus the `Show Context` code nodes that emit table names as strings.

```
at_tqo_content             ->  at_tqo_show_content
at_tqo_content_primitives  ->  at_tqo_primitives
```

Checked before renaming, not after: all 106 workflows were scanned for any
reference to either old name, in node parameters, code or notes. Zero. The other
session's mirrors keep their rows and their ids; only the labels moved.

The two new names are not substrings of each other either, which the obvious
first choice would have been.

## Reproduced, fixed, re-measured

A throwaway carried the failing node's parameters exactly, with the runtime
expression replaced by the literal it evaluates to. Read only, a row get, never
a write. Both throwaways are archived.

```
BEFORE the rename   Filter validation failed: Column(s) "status" do not exist
AFTER  the rename   success
```

Stopping at "it no longer throws" would have proved nothing about where the name
lands, so a second node counted rows with no filter at all:

```
Count by name "tqo_content"  ->  45 real rows, status and video_title present
```

45 matches what id mode returned before the rename. The lock check itself
returns zero rows, which is the correct answer because nothing is currently
Rendering.

The hazard set across all 51 tables is now empty: no table name contains another
table's name.

## The rule this leaves behind

A Data Table resolved by name is only as stable as every other table name in the
project. Anyone may add a table at any time, and a name that merely contains an
existing name is enough to redirect a node that has not been touched in weeks.
Two properties make it dangerous rather than annoying: the redirect is silent
unless a filter happens to name a missing column, and the blast radius is every
by-name node in the project rather than the one workflow being worked on.

Resolve by id where the table is fixed. Where an expression must choose at
runtime, have it choose between ids rather than names. Until that is done, a new
table in this project is a change to the content pipeline whether or not anyone
meant it that way.

## Open

TQO FINAL V5's next scheduled pass is 07:00Z and is the real confirmation; the
repro is strong evidence and not the lane itself. The 31 by-name nodes in V5 and
the Watchdog's `Scan TQO Content` still resolve by name, so the fix is the
absence of a colliding name rather than a property of the workflow.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-tqo-lane-was-resolving-the-wrong-table_v1_2026-09-16g.md
DATE: 2026-09-16
DECISIONS: Tee ruled rename the two mirror tables rather than edit TQO FINAL V5, on a recommendation that one rename each fixes all 73 by-name nodes while editing the workflow would mean 31 node changes inside 240 nodes. The mirrors were renamed to at_tqo_show_content and at_tqo_primitives, chosen so neither is a substring of the other. Nothing in the workflow was edited.
FINDINGS: TQO FINAL V5 was not intermittently red, it was deterministically red from 2026-09-15T23:38Z, when a concurrent session created Airtable mirror tables whose names contain tqo_content and n8n's Data Table name resolution stopped reaching the real table. Measured with a throwaway: name mode returned 0 rows where id mode returned 45. 73 Data Table nodes across 106 workflows resolve tables by name, 31 in the active V5 and one in the active Watchdog, and every one landing on tqo_content was reading an empty table. Only Render Lock: Other Brand failed loudly, because it alone filters on status, a column the wrong table lacks; the rest returned zero rows and the TQO lane silently found no work for four and a half hours. nco_content was shadowed by nothing and kept working. After the rename the repro went from the exact production error to success, an unfiltered count by name returned the same 45 rows id mode returns, and the hazard set across all 51 tables is empty.
OPEN: V5's next scheduled pass is 07:00Z and is the real confirmation rather than the repro. The 31 by-name nodes in V5 and the Watchdog's Scan TQO Content still resolve by name, so the estate is protected by the absence of a colliding name rather than by anything in the workflows. Resolving by id, or by an expression choosing between ids, is the durable fix and is unstarted.
STATUS: The TQO lane is unblocked and re-measured. The two mirror tables are renamed, nothing referenced their old names, and no table name in the project contains another table's name.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
