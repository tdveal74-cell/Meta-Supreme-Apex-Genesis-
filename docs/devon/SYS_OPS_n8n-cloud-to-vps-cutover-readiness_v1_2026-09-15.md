# n8n Cloud to VPS cutover readiness, measured 2026-09-15

This is the readiness audit Tee asked for on 2026-09-15, read against the
2026-09-06 cutover plan (`SYS_OPS_n8n-cloud-to-vps-cutover_v2_2026-09-06.md`,
called the v2 record below) and the 2026-09-10 verification
(`SYS_OPS_n8n-cloud-to-vps-migration-verified_v1_2026-09-10.md`). Readiness
here means cutover readiness: could the DEVON lane be switched from
`thequietoperator.app.n8n.cloud` to `n8n.editforge.online` today without
losing a job, a card or an alarm. Nothing on either instance was activated,
published, executed or edited by this audit.

## Verdict in one paragraph

Not ready, and the one group that already runs on the VPS runs there in a
broken state. Of the 41 DEVON lane entries the vault registers, 39 exist on
the VPS and 38 of them are inactive with `activeVersionId` null, the Error
Alarm being the one published, while 33 of the 41 are active on Cloud and
Cloud keeps filing and finishing jobs. The VPS state ledger is the 2026-09-03 snapshot, eight
CANCELLED rows from August plus one decided approval card whose token field
reads the literal text `undefined`, against 21 rows on Cloud, so runbook
steps 3 (wipe) and 6.2 (copy) are both unstarted. The Google Drive OAuth
credential on the VPS is disconnected, proven by execution 23 dying at Upload
MP3 on 2026-09-13, which blocks TQO FINAL V5 and the Drive Draft Writer
there. The active OS Error Handler on the VPS binds two Cloud credential ids
that do not exist on the VPS, proven by execution 24, and sixteen VPS copies
name a Cloud id as their error workflow, eleven the Cloud OS Error Handler
and five the Cloud Error Alarm, five of the sixteen active, so the first
real failure on the VPS is silent. The VPS holds two vintages: eight DEVON
copies rebuilt on 2026-09-10 read clean, and 33 copies exported on
2026-08-31 predate Cloud fixes that landed since. TQO FINAL V5 and the TSWS
render chain are active on both instances, against the runbook's never both,
and three of V5's seven webhook doors on the VPS answer with no
authentication on a public host. Nothing outside n8n has moved: `vault.py`
still names the Cloud host and Cloud ids, and no section 6 proof has run.

## What was read, and how

Two instances through their MCP connectors, read only. Cloud project
`rM0TNTE2fNXErglU`: `search_workflows` with limit 200, `search_data_tables`,
`get_data_table_rows`, `search_workflow_executions`, and full
`get_workflow_details` on the workflows named below. VPS project
`qbrcjkbIoorbwot6`: the same calls plus `list_credentials`, and full node
graph reads of TQO FINAL V5 (222 nodes parsed for type, disabled,
authentication, credential ids, settings and host literals), TSWS 00 to 05,
both error handlers, and nine DEVON lane copies (Job Driver, Action Router,
Approval Queue, Drive Draft Writer, Airtable Row Writer, Face, Event Bus,
Intake Former, Driver Poll), six of which are among the eight copies created
on 2026-09-10; the other two of the eight are the Gumroad Sale Check and the
Gumroad Landing Page Helper, and the three others read (Action Router,
Approval Queue, Event Bus) are 08-31 vintage saved 2026-09-03.
`scripts/estate_reconcile.py check` ran against a Cloud observation file
built from those reads; its output is quoted where it applies. The
`approval_queue` table on Cloud was read by count only, with `limit 1` and
`skip 100000`, so no row and no token column reached this session; the VPS
`approval_queue` row was read because it is a stale snapshot copy the runbook
already orders wiped.

## The two instances today

| | Cloud | VPS |
|---|---|---|
| workflows | 49 (41 active) | 61 (9 active) |
| DEVON lane entries in the vault, 41 | 33 active, 6 inactive, 2 archived | 39 exist; the Error Alarm active, the other 38 `activeVersionId` null |
| active on the VPS | | DEVON Error Alarm `bqcnIS0Qv4RkTCU1`, OS Error Handler `GbeNilHQzjmoWDz3`, TQO FINAL V5 `qEkGOUsNyVaRAmm6`, TSWS 00 to 05 |
| executions since 2026-09-15T00:00Z | 13, all success: 12 timers and one manual run of the Learning Lane Table Reader at 05:54Z (7121), actor not read | 0 |
| executions since 2026-09-08 | production timers hourly and daily; 5 manual V5 errors on 09-08 and 09-10 | 24, all manual or test: 19 on TSWS 00 (ids 1 and 3 to 20), 4 on the V5 ADAPTER TEST copy (2 error), 1 on the OS Error Handler in error mode |
| data tables | 11 | 11, same names |
| state ledger rows | 21, every one read, all terminal (12 CANCELLED, 9 COMPLETED), newest 2026-09-13T06:00:39Z | 8, all from the 2026-09-03 snapshot, all CANCELLED, created 2026-08-24 |
| approval_queue rows | 13 by count (2 pending past expiry, 10 approved, 1 rejected) | 1, decided 2026-08-25, expired 2026-08-28, token field carries the literal `undefined` nine times |
| devon_driver_log, devon_chat_log | not read today; the v2 record counted 92 driver log rows on 2026-09-06 | 0 rows each |
| credentials | 29; Google Drive `WMz320icjnur7rDL`, Gmail `vsTKuAilHmpYCc5L`, Devon Capture Key `FYRvkRTOcROEYZ9P` | 31, all owned by Tee's personal project, no id in common with Cloud, so every rebinding is by id |

## The runbook, step by step

Section 5 of the v2 record, in its order. "Done" is what a read proves,
not what a record says.

| step | status | what the read shows |
|---|---|---|
| 0.1 read the Cloud usage page | not done | the v2 status block still carries 1,212 executions spent by 13:00Z on 2026-09-06; the usage page is not reachable through the connector |
| 0.2 note the VPS n8n version | unverified | no connector field carries it and the egress policy refuses a direct read; execution 24's stack trace shows data tables and the chat trigger working, which is an inference about the feature floor, and the number is unread |
| 0.3 list VPS tables, create the two missing ones | partial | `devon_driver_log EHrmGJfmOKNJJcc4` and `devon_chat_log DKCusDJfIF8CPxyb` exist, created 2026-09-10T07:30Z, both empty; the 09-03 rows are still in the ledger and the queue; `tables-map.json` lives outside the repository by design and is unverified |
| 0.4 API keys on both instances | partial | the Railway api carries `N8N_API_URL`, `N8N_API_KEY`, `N8N_SECONDARY_API_URL`, `N8N_SECONDARY_API_KEY`; which host the secondary names and its scopes are unverified, values redacted |
| 0.5 register the VPS OAuth redirect URI in Google Cloud | not done | VPS execution 23 at 2026-09-13T11:48Z failed at Upload MP3: the Google Drive account `NW3vR6nNcMoUkJyJ` needs to be reconnected; V5 binds it on 9 nodes, the Drive Draft Writer on 3 |
| 0.6 WEBHOOK_URL, N8N_EDITOR_BASE_URL, GENERIC_TIMEZONE | partial | every VPS `triggerInfo` prints `https://n8n.editforge.online/webhook/...` and execution 24 carries a VPS editor URL, so the two URLs resolve; `GENERIC_TIMEZONE` is unverified, the copies read pin no timezone except V5 and six DEVON copies on America/New_York |
| 0.7 Tee has a login on the VPS | unverified | every VPS credential's home project reads Terrance Veal, personal, which proves who owned the project when they were created; the login itself was not exercised |
| 0.8 snapshot the VPS before the wipe | unverified | the Hostinger panel is not reachable from here and no record names a snapshot |
| 1 export from Cloud and compare `inspect.txt` | partial | 41 copies carry `createdAt` 2026-08-31T13:23Z, an export that predates the tool; 8 carry 2026-09-10, rebuilt by hand per their sticky notes; no `inspect.txt` comparison is recorded anywhere |
| 2 create credentials on the VPS, write `creds-map.json` | partial | 31 credentials on the VPS; the verified record's five map targets exist, three of them renamed since (`EdFztvzdUL9PSycJ` is now `anthropic`, `KtgOCINafn32E0h4` `json2video`, `XbLg8FnNraeTbEfJ` `mailerlite`), so a name keyed map would miss them; `creds-map.json` unverified |
| 3 wipe the 09-03 rows | not done | ledger 8 rows and queue 1 row, all stamped 2026-09-03T09:01:37Z |
| 4 `import --rewrite-host` then `repoint` | partial | the tool never ran against these copies; by hand the nine lane copies read node by node carry the VPS host in Job Driver HOST, Action Router URLs, Approval Queue HOST, the two writers' bus URLs, the Face intake URL and the Event Bus ledger URL, and four more 08-31 copies read by the verifier do too; the remaining 26 copies dated 08-31 were not opened and are unverified for host literals; repoint is not done for error workflows or for the OS Error Handler's credentials |
| 5 hand edits the map lacks | not done | the Action Router VPS copy's allowlist still names `Oi7o1sTEqhxhOaJL`, the Cloud Spine id, and lists `spine.echo` only; 16 VPS workflows name a Cloud error workflow; the VPS Face chat trigger carries `webhookId bf371d93`, a different door from Cloud's `71510ab0` |
| 6.1 drain Cloud | not done | Cloud filed and completed jobs on 2026-09-12; all 21 ledger rows are terminal today, newest created 2026-09-12T21:22:36Z, so there is nothing to drain at this minute and the next job will land on Cloud |
| 6.2 copy terminal rows | not done | VPS ledger 8 rows against Cloud 21; the two new tables hold 0 |
| 6.3 switch one group per sitting, never both | not done, and reversed for one group | every DEVON copy inactive on the VPS while active on Cloud; group (e), the TSWS chain and the OS Error Handler, is active on both, and so is TQO FINAL V5 |
| 6.4 repoint `vault.py`, the soul copy, the skills, the n8n bodies, then `check --strict` | not done | `services/devon/vault.py` `N8N_HOST` is the Cloud host and all 51 `WORKFLOWS` and 13 `WEBHOOKS` ids are Cloud ids, counted from the file; `deploy/soul/services/devon/vault.py` is byte identical to it; the n8n bodies in the repository still carry the Cloud host at `n8n/devon/job-driver/decide.js:5` and `n8n/devon/action-router/authorise_and_resolve_target.js:52`, `:58`, `:64`; the skills reference is `.claude/skills/devon-learning-lane/references/ids-and-contracts.md:7`; `test_estate_reconcile.py` carries three hits; and the presence service watches `services/**`, so the vault edit deploys presence; whether the api service also redeploys on that edit is unverified, its watch patterns unread |
| 6.5 keep Cloud reachable and inactive 72 hours | not done | Cloud ran 12 timer executions and one manual run between 00:00Z and 06:30Z today |
| section 6 proofs 1 to 7 | none run | no VPS execution since 2026-09-08 touched a DEVON lane workflow; proof 4, the Cloud negative test, would return 200 today because the Cloud intake door is live |

## The nine hazards of the v2 record, re-read

1. The stale ledger copy: still there, 8 rows plus the decided queue row.
   A VPS Driver Poll or Janitor activated over it would act on jobs Cloud
   finished in August.
2. The two missing tables: created on 2026-09-10, both still empty.
3. The Cloud host inside nodes: closed on the nine lane copies read and on
   four more 08-31 copies opened by the second reader (Capture Webhook,
   Soul Committer, Ledger Feeder, Heartbeat), every URL and table id a VPS
   one, those four saved 2026-09-03T10:22Z in one batch rewrite; unverified
   on the remaining 26 copies dated 08-31. The repository's own copies of
   the bodies are a different matter: `n8n/devon/job-driver/decide.js:5`
   and `n8n/devon/action-router/authorise_and_resolve_target.js` lines 52,
   58 and 64 still carry the Cloud host, so the source is a three executor
   allowlist on Cloud, the live VPS copy is a one executor allowlist on the
   VPS, and no artifact anywhere is the target state.
4. Workflow ids inside Code nodes: open. The Action Router VPS copy is the
   08-31 shape, `spine.echo` only with the Cloud workflow id beside a VPS
   URL, so `drive.draft` and `airtable.row` would be refused on the VPS.
5. Error workflow settings: open on 16 VPS copies, eleven naming the Cloud
   OS Error Handler and five the Cloud Error Alarm, five of the sixteen
   active (the list is below).
6. Credentials by id: open. The active OS Error Handler binds `smtp
   mu7nJRSpkAfkzLdF` and `airtableTokenApi OyuQtrelq7zP2mTy`, neither on the
   VPS, so it fires and then fails at both its outputs (execution 24, mode
   error, 2026-09-13T11:48Z, parent 23). The Google Drive account exists and
   is disconnected (execution 23). Three Header Auth accounts were renamed,
   which breaks name based re-linking.
7. External posters: nothing in the DEVON lane has moved. Cloud receives
   every timer and the vault names the Cloud host, so the iPhone Shortcuts,
   the platform custom instructions, the MCP connectors and every sent
   approval email still point at Cloud; the posters themselves are
   unverified and the target is inferred from the vault. One poster class
   is already aimed at the VPS side and no record names it: the DEVON ops
   gateway at `ops.editforge.online`, hard coded at
   `apps/web/app/api/devon-ops/[action]/route.ts:10` and
   `deploy/soul/ops_gateway.py:14`, which the readiness audit covers.
8. The repository's record: `vault.py` is Cloud throughout, and it also says
   TSWS 00 Render Job `o4ctniOsIq2VSfgm` is active on Cloud while the Cloud
   census reads it inactive since 2026-09-13T08:19:29Z.
9. Double execution: no timer fires twice today, because all six V5
   schedules are disabled on both hosts and the TSWS 01 schedule is disabled
   on both, but V5's seven webhook doors answer on both hosts, the TSWS 00
   to 05 chain and both error handlers are active on both, and the two V5
   copies have diverged: Cloud has Run TQO (Link) and Run NCO (Link) on
   header auth and the VPS copy, last saved 2026-09-10T11:34Z, has them on
   none. The divergence is measured; its date is not, because Cloud's only
   saved version (`0c1f7068`, 2026-09-11T22:15:43Z) describes a narration
   provenance change and says nothing about webhook authentication. The v2 record's 4.7 warning is
   now the case on a public host: Gumroad Ping, Run TQO (Link) and Run NCO
   (Link) accept an unauthenticated request on the VPS. That same saved
   Cloud version records that the 11 September ElevenLabs rotation went to
   the VPS credential while Cloud runs against its own, so the credential
   split cuts both ways.

A tenth hazard the v2 record could not have named: the two vintages. The
eight DEVON copies rebuilt on 2026-09-10 read clean. The 33 copies dated
2026-08-31 predate the Soul Committer's move to an hourly poll (the VPS copy
polls every 15 minutes, `minutesInterval 15`, while the live Cloud trigger
reads Every Hour, `hoursInterval 1`, both read today), the Action Router's
third executor (measured: the VPS allowlist has one key), and by date the
OS 29 Firecrawl rebuild of 2026-09-08 (the two bodies were not compared).
Activating an 08-31 copy would regress a Cloud fix.

## Dangling references

- TSWS 01 `UoJS8WDZfkVD9AVH`, 02 `vqfgphaJUi1OWx5x`, 03 `s3TE4io4Qzl4DI1Q`,
  04 `khY3wwZt79FQgjAW`, 05 `klTNudFrz5hXBVy2`, all active: `errorWorkflow`
  `rqYmaQh91iCce8DJ`, the Cloud OS Error Handler, which resolves to nothing
  on the VPS.
- iPhone Inbox Capture `CEy7WAl4QAzHfG46`, Capture Webhook
  `Me7DDHBDX28ppvHA`, Duplicate Sweep `3tY1sJF3brpvdkgi`, Monthly Credential
  Review `ZKyaYzv7DAGhJSLi`, Notion Buffer Drain `ptAmD28msYTvobgq`, To
  Delete Auto-Purge `2M8CIPebpl1nSLVx`, all inactive: the same Cloud id.
- Ledger Feeder `GEbNoDMBdGqDfZJ2`, Soul Committer `drP96ernQvbrvzIZ`,
  Heartbeat `EEDrp2jLlw2Ssd5b`, Ledger Janitor `V0i8zTw1keMMJmhF`, Weekly
  Table Backup `rVXA5wH5AXW4tCjp`, all inactive: `errorWorkflow`
  `XDQXwgFkUhYxoEjG`, the Cloud Error Alarm; the VPS Error Alarm is
  `bqcnIS0Qv4RkTCU1`.
- OS Error Handler `GbeNilHQzjmoWDz3`, active: the two Cloud credential ids
  above, proven failing.
- Action Router `NYcEp03Oqlvq86Mb`: `workflow_id Oi7o1sTEqhxhOaJL` in the
  TARGETS Code node, the Cloud Spine id.
- Closed since the 09-10 record: TQO FINAL V5 `qEkGOUsNyVaRAmm6` now names
  `GbeNilHQzjmoWDz3`. Correctly pointed for contrast: TSWS 00, the Gumroad
  Sale Check, the Gumroad Landing Page Helper, and the eight 09-10 rebuilds
  which name `bqcnIS0Qv4RkTCU1`.
- Unresolvable from here: TQO Rendering Sub-workflow (Detailed) and its three
  sibling sub-workflows are absent from the VPS census of 61, so their
  `errorWorkflow IYDof2FtoIJbUqCB` could not be re-read; archived or removed,
  unverified which.

## The vault against both censuses

`scripts/estate_reconcile.py check` against the Cloud observation file:
101 claims, 4 drift, 21 unverified, 14 retired, 62 ok, verified score 71 of
100. Every one of the 13 `vault.WEBHOOKS` auth claims is OK. The Check Token
body gate on `devon-capture` is OK, enabled, wired as the door's only next
step, and its code fingerprint
`74fdf22a12cee9c8fede22e02061b82d8348b6cf48ae4ba115d7ae6cae7a38e9` equals the
2026-09-06 pin, the first keyed confirmation the vault comment asked for. The
four drift lines: the 2026-08-31 migration doc records 64 workflows against
49 live; Build 08 Credential Probe `pm5hoO4eFpGhlAb4` and Soul Index Setup
`vYr35jqNNaAztGhQ` are recorded inactive but are archived on Cloud
(`get_workflow_details` on each answers "archived and cannot be accessed",
and `search_workflows` omits archived), so the vault's inactive should read
archived or the entries should retire; and TSWS 00 Render Job is recorded
active but inactive on Cloud. The strict run's output is byte identical and
fails on the same four lines. The 21 unverified lines are the connector
claims the snapshot could not carry (fourteen lines: Drive, Airtable,
Notion, the skill vocabulary), four `dispatch.py` file checks against
`OPERATING.md` and `RUNBOOK.md`, the deployed Alembic head (the newest head
deployment is SKIPPED and the reconciler reads a SUCCESS build only), the
"deployed without hands" line of the ecosystem spec for the same reason, and
the vault host echo.

Against the VPS, 51 vault entries map to 49 VPS copies; the two absent are
the two archived Cloud workflows. Of the 49, nine are active on the VPS (the
two error handlers, V5 and TSWS 00 to 05) and 40 are inactive with no
published version; counting the DEVON lane alone, 39 of its 41 entries exist
on the VPS, one active and 38 unpublished.

## Cloud burn, an estimate

Not a measurement. Cloud execution ids 7041 to 7104 were consumed on
2026-09-14 (64 ids, 41 of them listed, because Soul Committer, Job Driver
and the executors persist no successful run) and 7106 to 7125 between
00:00Z and 06:30Z today (20 ids in 6.5 hours). That is roughly 60 to 75
executions a day, all timers: Driver Poll 24, Watchdog 6, Heartbeat 4, and
the dailies. At 64 a day a 30 day cycle is about 1,900 to 2,200 against the
2,500 cap Tee stated on 2026-09-06. The n8n Cloud usage page is the only real
number for both the count and the cycle reset date, and neither is readable
through the connector. Whatever the true figure, every execution in the
estimate is a group (a) to (d) timer, which is the group furthest from ready.

## What is ready, conditionally

The TSWS 00 to 05 render chain on the VPS: published with VPS ids throughout,
its sub-workflow targets all `CX07qa6O1hTSXlpj`, its render worker
credential `WpZNTg9qduOFC5NM` present, both HTTP nodes on
`http://172.16.2.1:8080`, and a passed smoke on 2026-09-12 (execution 11,
`ok:true` on an exists check). It is also the only render lane that is
wired at all: Cloud's TSWS 00 `o4ctniOsIq2VSfgm` is inactive with both URLs
still the `RENDER-WORKER-URL-HERE` placeholder, and its sticky note of
2026-09-13 says Cloud TSWS 05 calls it from four nodes and names TSWS 01 to
04 as likely callers, so Cloud TSWS 05 cannot render a byte and, if the note
is right about the other four, neither can they; their targets were not
read. It becomes ready when the five
`errorWorkflow` settings on TSWS 01 to 05 are repointed to `GbeNilHQzjmoWDz3`
and that handler's two credentials are rebound to `AgSGuaA2pnZsrZcJ` (smtp)
and `Avhx7u29TskBaR67` (Airtable). Even then it fires only by hand or by a
V5 pause signal, so activating it costs nothing on Cloud's cap and saves
nothing either.

## Blockers, in order

1. Wipe the 09-03 rows on the VPS (ledger 8, queue 1 with its token) and copy
   Cloud's terminal rows: ledger 21, plus the driver log and chat log, which
   are empty on the VPS. Runbook steps 3 and 6.2.
2. Reconnect the Google Drive account `NW3vR6nNcMoUkJyJ` on the VPS. Runbook
   step 0.5, and the first Drive upload fails until it is done.
3. Rebind the active OS Error Handler's two credentials, then repoint the 16
   `errorWorkflow` settings: `rqYmaQh91iCce8DJ` to `GbeNilHQzjmoWDz3` on
   TSWS 01 to 05 and six inactive DEVON copies, `XDQXwgFkUhYxoEjG` to
   `bqcnIS0Qv4RkTCU1` on the five learning lane copies.
4. Re-export or rebuild the 08-31 vintage where Cloud has moved on: Action
   Router (three executor allowlist, VPS Spine id), Soul Committer (hourly),
   OS 29 (Firecrawl body), and host-check the 26 not yet opened.
5. Close the three unauthenticated V5 doors on the VPS (Gumroad Ping, Run
   TQO Link, Run NCO Link) or deactivate V5 there. Cloud has two of the
   three on header auth and the VPS copy does not; when Cloud closed them is
   unmeasured.
6. Decide which instance owns TQO FINAL V5 and the TSWS chain. Both are
   active on both today.
7. Publish each DEVON copy only in the 6.3 order, Cloud off first per group.
8. Repoint `vault.py` (`N8N_HOST`, 13 webhooks, 51 workflows), the
   `deploy/soul` copy, the skills reference and the n8n bodies, then
   `estate_reconcile.py snapshot` and `check --strict`. Retire or re-mark the
   two archived entries and TSWS 00 on the way.
9. Run the seven section 6 proofs.
10. Read the n8n Cloud usage page for the real count and the cycle reset,
    and set the five `N8N_EXECUTION_CAP` anchor variables the telemetry
    route already reads, so the Execution Hub draws the burn instead of
    this audit estimating it.

## What could not be measured here

The VPS n8n version and `GENERIC_TIMEZONE`; whether a VPS snapshot exists;
whether `tables-map.json` and `creds-map.json` exist on Tee's machine; which
host and scopes the Railway secondary n8n key names; Cloud host literals
inside the 26 VPS copies dated 08-31 that nobody opened; the fate of the four TQO rendering
sub-workflows absent from the VPS census; which of Cloud's 29 credentials remain
unmatched on the VPS beyond the ids named above; where each external
poster points; the 18 older Cloud ledger rows; the real Cloud execution count
and cycle reset; any direct HTTP probe of a VPS surface, which the egress
policy refuses; and whether the VPS Face chat door opens for Tee.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_n8n-cloud-to-vps-cutover-readiness_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: none ruled; nothing on either instance was activated, published, executed or edited. Three calls are Tee's and are put to him here: which instance owns TQO FINAL V5 and the TSWS chain, since both are active on both; whether the three unauthenticated V5 doors on the VPS are closed or V5 is deactivated there; and whether the 08-31 vintage is re-exported from Cloud or rebuilt by hand.
FINDINGS: of the 41 DEVON lane entries in the vault, 39 exist on the VPS and 38 are unpublished with activeVersionId null, the Error Alarm being the one active, while 33 are active on Cloud; the VPS ledger is the 2026-09-03 snapshot, 8 CANCELLED rows and one decided approval card carrying the literal undefined in its token field, against 21 rows on Cloud; the Google Drive credential on the VPS is disconnected, execution 23; the active OS Error Handler on the VPS binds two Cloud credential ids and fails at both outputs, execution 24; 16 VPS copies name a Cloud error workflow id, eleven the Cloud OS Error Handler and five the Cloud Error Alarm, five of them the active TSWS pipelines; the VPS holds two vintages, 8 rebuilt 2026-09-10 and 33 exported 2026-08-31, and the older vintage predates the hourly Soul Committer and the third executor, both measured, and by date the OS 29 rebuild; TQO FINAL V5 and the TSWS chain are active on both instances, V5's copies have diverged so that three doors on the VPS accept unauthenticated requests, and Cloud's TSWS 05 calls a TSWS 00 that still carries the placeholder worker URL, with TSWS 01 to 04 named as likely callers by the same note, so only the VPS lane is known to be wired to a worker; the repository's own n8n bodies and the skills reference still carry the Cloud host; vault.py is Cloud throughout and mis-states TSWS 00 as active; the reconciler scores the vault 71 of 100 against Cloud with 4 drift lines, two of them archived workflows the vault calls inactive; Cloud burn is an ESTIMATE of 60 to 75 executions a day, all timers.
OPEN: the ten blockers above in order, the first two being the wipe and copy of the tables and the Drive reconnect; the seven section 6 proofs, none run; the usage page read and the cap anchor variables; the 26 unopened 08-31 copies; whether Cloud narration is falling back to Speechify since the 11 September credential split.
STATUS: not ready for cutover. The TSWS render chain is the one group that could be called ready, after its five error workflow settings and its handler's two credentials are repointed. Everything above was read today through the two connectors or counted from a named file; what could not be read is listed as unverified, with no rounding up.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
