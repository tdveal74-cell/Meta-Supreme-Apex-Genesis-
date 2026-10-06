# The show registry is in the repository and on the instance, and the four Show Context nodes that carry a tagline finally agree

Step one and step two of splitting `TQO FINAL V5` by stage, both on
2026-10-06, both on Tee's rulings from cards. Step one is PR #307, merged as
`08708f8`: `services/devon/show_registry.py` carries one record per show
lifted from the five `Show Context` nodes and `Series Addendum`, and
`test_devon_show_registry.py` traces every value back into the branch of the
node that carries it. Step two is on the instance: the two stale tagline nodes
repaired and published as `3befd7a5`, and the `show_registry` and
`show_series` data tables created and seeded from the module, read back
clean. This doc also closes the Reach item the morning's doc left open.

The test counts, the critic counts, the publish read back and the table read
backs below are this session's own measurements. Their receipts are the
commit messages and PR bodies on #307, #308 and #309 and the n8n version and
execution ids named in the text; the repository holds the commits, not the
runs.

## Step one: what the critics did to the first trace

The first commit traced each registry value by substring over the whole node
body. Four critics ran over it in their own worktrees (50 agents in all, 22
findings survived two refuters each, one refuted) and the test-strength and
trace-fidelity lenses found the same hole from two sides: an integer limit
traced against any digit in a table id, a value from the other show's branch
passed, and the voice settings matched comment text. Eight mutations of the
export or the registry stayed green under it. The second commit keyed the
trace on the node's own field name and scoped it to the branch that builds
the show's object, compared the voice settings numerically inside
`VOICE_SETTINGS`, and matched series and aliases as whole entries inside
their own table. All eight mutations now fail, each reverted, and the PR body
carries the table.

The other findings that changed the diff: the two candidate narrator strings
(`providerEleven`, `providerSpeechify`) lifted into the voice lane because
`Mark Ready + Save URL` writes one of them as narration provenance; `row()`
emits JSON strings for the lists and the voice settings because an n8n data
table column is string, number, boolean or date; the drift map's keys pinned
in the test so the map can only shrink; `SOURCE.version_id` asserted against
the export's own `versionId`; the docstring counts counted from the export by
a test (25 Code nodes branch on the show in four spellings, 16 carry
`isNCO`); and `n8n/tqo-v5/show_context_script.js` retired, because the README
called it the identity board, no test read it, and it already lacked the
`packageLimit` the live node carries.

Measured before the merge: full api suite 3299 passed on `81f72fa`; the
standalone list exactly as `ci.yml` runs it with no `PYTHONPATH`, 1076 passed;
CI green on `407cfe7` across all five `ci.yml` jobs and web-ci. Tee ruled
merge on a card and the PR merged as `08708f8`.

## Step two: the two nodes, then the two tables

The lift found the four Show Context nodes that carry a tagline disagreeing
on it (`Show Context: Brief` carries none): `Show Context:
Promote` and `Show Context: Publish` still carried "Military Mindset.
Civilian Impact." for NCO Forge while Script and Render carried the Aug 2026
audit line. Blast radius read from the export was zero, because the only
consumer of `tagline` downstream is `Build Script Prompt` and it reads
`Show Context: Script`. Tee ruled both fixed. The edit went in as a draft
through the MCP `update_workflow` (two `updateNodeParameters`, one line
each), the draft was compared to the active version node by node before
publishing (265 nodes, only those two differed, only in `parameters`, each
by the one line, connections identical), then `publish_workflow` moved
`activeVersionId` to `3befd7a5` and the read back shows `versionId` equal to
it, `active` true, both nodes carrying the audited line and the old line
gone. The exports were regenerated from that version at 16:10Z, both files
`3befd7a5`, 265 nodes, every webhook path and id `redacted`, and
`KNOWN_NODE_DRIFT` is now empty with the test still pinning its keys.

The tables are new on the instance, in project `qbrcjkbIoorbwot6`:
`show_registry` is `xmNWLUm49QyZ4ysO` with 34 columns and `show_series` is
`s1IxySUuphOVrOqU` with 9, created through the n8n MCP `create_data_table`
call with column types taken from the module's row shapes
(number for the three limits, the stale claim hours and the series position,
boolean for the two readiness flags, string for the rest);
`scripts/show_registry_seed.py --spec` prints that same create payload from
the module, so a lost table or a third show is recreated from the module
rather than from memory. Neither existed
before: the 61 tables on the instance were listed and none matched.
`scripts/show_registry_seed.py` wrote 2 and 16 rows and read both tables back
against the module, CLEAN, and a second run inserted nothing and read CLEAN
again. The module now carries the two ids in `REGISTRY_TABLES`, and
`test_show_registry_seed.py` proves the script's diff on fixture rows without
a network: a missing row, a drifted value, a duplicate, a stranger and an
extra column are each named, and a faithful copy reads clean.

Two things learned about the public API on the way, both from the instance's
own `/api/v1/openapi.yml` rather than from a guess: the rows endpoint pages
by `nextCursor` and rejects `skip`, and the insert is a plain `POST` on
`/data-tables/{id}/rows` with `{"data": [...], "returnType": "count"}`;
`/rows/insert` answers 404.

## Hostinger Reach, closed

The morning's doc left the Reach token open. Tee replaced it on the n8n
credential `Hostinger` and execution 2276 of the proof workflow returned HTTP
200 on all three read only calls, after 2270, 2271 and 2273 had returned 401
on the credential as first stored. The proof workflow was archived
afterwards. Reach is live; nothing sends through it yet, and enabling the
Sunday Brief lane is a ruling still to ask for.

## HeyGen v1 and v2 deprecation, read against the estate

Tee forwarded HeyGen's notice the same afternoon: API v1 and v2 are removed
on 2026-10-31, migrate to v3. The estate was counted rather than assumed, all
152 workflows on the instance (51 active) and the repository. No active
workflow calls api.heygen.com. The only v2 calls on the instance sit in two
archived, inactive September probes (`remaining_quota` and avatar details)
that never run. The Avatar lane draft 206299ba, the one place a HeyGen render
is wired, calls only `/v3/users/me`, `/v3/videos` and `/v3/videos/{id}` across
its 290 nodes, and the one inactive TEMP engine test is v3 as well. The
repository holds no HeyGen API call: the render worker consumes the finished
file, and `deploy/lipsync/README.md` recorded on 2026-09-16 that HeyGen's own
v2 response named the 2026-10-31 removal and ruled the render call built on
v3. There is no migration to do.

The comparison page was read in full once Tee allowed developers.heygen.com
in the environment's network list (the first attempt was blocked at the
egress proxy, and the permission policy declined a read only fetch workflow
on the instance). Its table: v1 and v2 stay operational through 2026-10-31
and are retired from 2026-11-01; every legacy response carries
`Deprecation: true`, a `Sunset` header and a `warning.v3_endpoint` naming the
replacement; `POST /v2/video/generate` becomes `POST /v3/videos` with a
discriminated body (`type: "avatar"`, `"image"`, `"cinematic_avatar"` or
`"studio"`); `GET /v2/videos/{video_id}` becomes `GET /v3/videos/{video_id}`;
`GET /v2/user/remaining_quota` becomes `GET /v3/users/me`; `GET /v2/avatars`
becomes `GET /v3/avatars`; pagination is cursor based on every v3 list. The
lane's three calls are exactly the three v3 replacements, with `type:
'avatar'` in the body, and they were answered by the live API on manual
execution 2221 (2026-10-06T01:07Z): `/v3/users/me` 200 with the wallet at
13.58, `POST /v3/videos` 200 with video id `8622143d` from a body of `type:
'avatar'`, `avatar_id`, `audio_url` and `title`, and `GET /v3/videos/{id}`
polled eight times to `completed` with a 62.6 second mp4. The two archived
probes' v2 calls map to `/v3/users/me` and `/v3/avatars` and stay archived.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_show-registry-steps-one-and-two_v1_2026-10-06-1612.md
DATE: 2026-10-06
DECISIONS: Tee ruled on cards to merge PR #307, to fix the two stale NCO tagline nodes now with a read back, to create and seed the show_registry and show_series data tables now, and to file the HeyGen deprecation reading here. Earlier the same day he ruled the show registry module and its test as step one of the stage split.
FINDINGS: The first trace was a whole node substring match and eight mutations passed it green; the keyed, branch scoped trace fails all eight. Promote and Publish carried the pre audit NCO tagline with zero blast radius. The rows endpoint pages by nextCursor and the insert is POST on the rows route. The stale show_context_script.js mirror lacked packageLimit and nothing tested it. Reach execution 2276 returned 200 after three 401s. HeyGen's v1 and v2 removal on 2026-10-31 touches nothing live: zero active calls, two archived v2 probes, the Avatar lane draft on v3 only.
OPEN: The 2026-10-07 10:20Z pass on row 46 under the tightened close rule, to be read at 10:32Z that day. Nothing schedules `scripts/show_registry_seed.py --check` yet, so a change to the module drifts from the two tables with no alarm until someone runs it; a scheduled read back is a ruling for Tee. Rows 4 and 5 and which writer feeds the table, unruled. The Avatar lane and TEST trigger in version 206299ba awaiting their own publish. Enabling the Sunday Brief lane now that Reach is live. The first stage workflow that reads show_registry instead of a Show Context node. The chat agent lane with workflow PUT inside V5, to be removed in the split.
STATUS: PR #307 merged as 08708f8; V5 published as 3befd7a5 and read back; both tables seeded and read back clean twice; this doc's PR not yet opened at the time of writing, so its CI has not run.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
