# The Airtable mirror on the VPS

2026-09-15, after the 6pm pass. Tee's standing ask was to pull the whole Airtable
estate into data tables on n8n.editforge.online and draft the result as a pull
request. That ran tonight. Thirty eight data tables now exist on the VPS under an
`at_` prefix, carrying 507 rows, and every cell has been read back and compared
against its Airtable source.

## What moved

Two bases. `app28z7XnKzjfTXwc` holds 37 tables and 36 of them were mirrored.
`appa7WL221K1DhYnX` holds 2 and both were mirrored. The one table left behind is
`Credentials`, and it was left behind on purpose: `airtable_mirror.py` names it in
`EXCLUDED_TABLE_NAMES`, because a data table is readable by every workflow on the
instance and a secret store cannot live somewhere with that reach.

That exclusion was checked rather than trusted. The live base list was read back
and diffed against the plan, and the only table in the base and not in the mirror
is `Credentials`. Field counts match on all 36 tables. Counting from the estate,
not from the plan, is what the first law asks for, and in this case the count came
out right.

The row data itself never enters this repository. The Leads, Customers, Coaching
Clients and Coaching Sessions rows live on Tee's VPS and nowhere else. What is
committed here is the map: which Airtable table became which data table id, the
column names and types, and the counts.

## The date column that moved a day

The plan typed every Airtable date field as an n8n `date` column. A probe table
settled whether that was safe, and it was not. A cell inserted as `2026-08-06`
read back as `2026-08-06T04:00:00.000Z`. The instance runs on America/New_York, so
n8n stamps a four hour offset onto a value Airtable stored as a bare date. Anyone
reading that column in UTC sees four in the morning on the sixth. Anyone reading
it further west sees the fifth. An archive that silently shifts a day is worse
than no archive.

So every Airtable date field is mirrored into a `string` column and the value
lands byte for byte. ISO 8601 still sorts and compares correctly, so nothing is
lost but the coercion. The rule was fixed in `airtable_mirror.column_type` rather
than patched in the loader, and `test_airtable_mirror.py` now carries the
measurement so the rule cannot be relaxed back without someone re-running the
probe.

This is the part worth reading twice. A count check would have called that load
clean. The rows were all there, the types were all accepted, every insert returned
200. The value was still wrong. Green is not correct.

## What was measured

| what | how | result |
|---|---|---|
| the date coercion | a throwaway probe table on the VPS, since deleted | `2026-08-06` came back `2026-08-06T04:00:00.000Z` |
| the plan against the live base | the base table list read back and diffed | 37 tables live, 36 mirrored, the miss is `Credentials` by design |
| field counts | per table, base fields plus two against plan columns | 36 of 36 match |
| the load | 38 creates and the row inserts over the n8n REST API | 507 rows, every table count equal to plan |
| the load, independently | every row read back and compared cell by cell | 22,941 cells, 0 mismatches |
| the load, repeated | the same loader run a second time | 0 rows inserted, verifier clean again |

The second run is the idempotency proof. A table already carrying its rows is
topped up from the plan offset, so an interrupted pull is finished rather than
copied twice.

## What is in the repository

`scripts/airtable_mirror.py` already held the transform, and the only change to it
is the date typing above. Two scripts join it. `airtable_mirror_load.py` applies a
plan to the VPS over the public REST API, resume safe, reading its host and key
from the environment and never logging either. `airtable_mirror_verify.py` reads
the live tables back and diffs every cell, and exits non-zero on any difference,
so it can gate a step rather than decorate one.

The map is `docs/devon/airtable-vps-table-map_2026-09-15.json`. It carries the
Airtable base and table ids, the VPS data table ids, the columns with their types,
and the row counts. It carries no record ids and no cell values.

The loader talks to the REST API instead of a connector for a reason worth
recording. The rows run to about two megabytes, several of them are script bodies,
and moving executable text through a tool call is both slow and a chance to change
a character that nobody would notice.

## What this is not

This is an archive, not a cutover. Nothing on the VPS reads an `at_` table yet,
and the live pipeline tables such as `tqo_content` are untouched. The mirror is a
faithful copy of Airtable as of tonight, and a second pull will update the same
table names rather than create a second set.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-airtable-mirror-on-the-vps_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: Tee ruled the whole Airtable estate is mirrored into n8n data tables on the VPS under an at_ prefix, as a faithful archive that no lane reads, with the Credentials table excluded because a data table is readable by every workflow on the instance. Ruled in this session on the measurement: every Airtable date field is mirrored into a string column rather than an n8n date column, because n8n stamps the instance timezone onto a date only value. The row data stays on Tee's VPS and never enters the repository; only the schema map is committed.
FINDINGS: 38 data tables were created on n8n.editforge.online in project qbrcjkbIoorbwot6 carrying 507 rows, and an independent read back compared 22,941 cells against the Airtable source with 0 mismatches. A second run of the same loader inserted 0 rows and verified clean, so the pull is idempotent. An n8n date column silently coerces a date only value: a probe inserted 2026-08-06 and read back 2026-08-06T04:00:00.000Z on this America/New_York instance, which is the previous day anywhere west of UTC-4, so airtable_mirror.column_type now returns string for every Airtable date type and test_airtable_mirror.py pins the measurement. The live base carries 37 tables and 36 were mirrored; the single omission is Credentials and it is excluded by name in airtable_mirror.EXCLUDED_TABLE_NAMES. Field counts match on all 36 tables. The second base carries 2 tables and both were mirrored.
OPEN: Nothing on the VPS reads an at_ table yet, so the mirror is an archive and not a cutover; which lanes should read it instead of Airtable is Tee's ruling. Whether the mirror should run on a schedule rather than on demand is unsettled. The 13 empty tables were created with their schema and no rows, so a later pull fills them without a migration.
STATUS: The pull ran, was verified cell by cell, and was proven idempotent on a second run. The repository carries the loader, the verifier, the corrected date rule with its test, and the schema map.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
