# DEVON readiness, audited 2026-09-15

Tee asked on 2026-09-15 for an audit of DEVON for readiness. Readiness here
means two things: can DEVON take a job from Tee's phone today, gate it, run
it and tell the truth about what happened; and can each surface it runs on
be trusted for what it claims. The audit read the live estate through the
Railway, Vercel and n8n connectors, the repository at `40355ae` on the
designated branch and `79a09cb` on `origin/main`, and the dated `SYS_OPS`
record, then put every claim through a second pass that tried to refute it.
Nothing on any surface was changed, activated or executed. The companion
audit of the n8n cutover is
`SYS_OPS_n8n-cloud-to-vps-cutover-readiness_v1_2026-09-15.md`.

## Verdict in one paragraph

The core job lane is operational and human gated, and its own ledger proves
it: on 2026-09-12 a job went from RECEIVED to COMPLETED through intake, the
Cloud state ledger, two approval cards Tee approved, the action router, the
`airtable.row` executor and a receipt, with the Airtable record confirmed
outside the envelope. Today every scheduled organ on Cloud fired on cadence
with zero errors, the ledger holds 21 rows all terminal, and the production
API, the presence service and the phone lane each owe nothing to `main` on
their own paths. Four edges are not ready. Soul recall on the platform is off
because the Railway api carries none of its variables, and the dock fix that
stops a failed read from reading as recall off is unmerged on PR #219. The
EditForge lane is a token only surface with no human sign in and no artifact
store, and its render worker has answered one exists check and never moved a
sample. The VPS runs no DEVON organ and carries a second, diverged copy of
TQO FINAL V5 that one record says is inactive. The learning lane has never
carried a genuine PROMOTE. Two things on the platform answer in the
reassuring direction with no check behind them: `GET /health/ready` says
ready without touching the database, and the VPS action gate proxy on
`origin/main` logs the raw request body and the first three characters of
`DEVON_OPS_SECRET` on every call, against its own header comment, and the
Vercel log store already holds twenty such lines from this morning. The record disagrees with itself in thirteen places, most of them
same date docs the filenames cannot order.

## The surfaces, read back

| surface | serving | read from | owes main |
|---|---|---|---|
| Railway api `api-production-5644.up.railway.app` | `84ad6a1c` SUCCESS 2026-09-14T00:46:51Z, commit `95fbdd5` | `list-deployments`, `describe-service` | nothing on its paths: `git diff 95fbdd5..origin/main` over `app`, `services`, `database`, `requirements.txt`, `alembic.ini`, `dispatch.py` is empty |
| Railway api, the gate | five deployments SKIPPED between 03:48Z and 04:33Z today on `31abeff`, `a9189b7`, `40f092a`, `3fd8ae7`, `79a09cb`; `checkSuites` true | same | Railway waits on GitHub checks and `main`'s api job has been red since run #735; harmless today, armed against the next change under `app/` or `services/` |
| Railway api, the traffic | 1,304 requests in 48 hours, 0 with a 5xx, 2 with a 4xx; the deploy log of `84ad6a1c` carries zero error lines since 2026-09-14T00:00Z; health check path `/api/v1/health`, pre deploy `alembic upgrade head` | `http-error-rate`, `get-logs`, `get-service-config` | serving clean |
| Railway presence `presence-production-d272.up.railway.app` | `6eea80f9` SUCCESS 2026-09-10T16:58:08Z, commit `7da04d4` | `list-deployments` | nothing: the diff over `apps/presence`, `services`, `requirements.txt` is empty; `GET /health` is refused by the egress policy, so speech, inference and breaker state are unverified from here |
| Railway scheduler-cron | `4b262e07` SUCCESS 2026-09-15T04:33:13Z on `79a09cb`; `*/5 * * * *`, `python dispatch.py`, `checkSuites` false | `describe-service` | current; deployed a commit the api skipped, so the two services do not share the gate |
| Vercel web `meta-supreme-apex-genesis-web` | `dpl_CjGxG52cLXhYB5YjqYjdFMvrWEbS` READY production on `79a09cb` at 04:33:52Z; Vercel Authentication on for every `vercel.app` URL (`ssoProtection` enabled, `all_except_custom_domains`) | `get_deployment`, `get_project_deployment_protection` | current, and ahead of CI: it went READY on a commit whose `ci.yml` run failed, so no check suite gate is in effect there, and it serves the dash `main` rejects and the proxy debug logging below |
| Vercel `devon-soul` | `dpl_GCU6imhA8oBsn26g1aFEquxMNGyn` READY production, a redeploy of `95fbdd5`, 04:52:30Z; `/api/v1/health` healthy, `console_token_set` true, `soul_key_set` true at 05:32Z; no deployment protection, which is what an n8n called API needs | `get_deployment`, `web_fetch_vercel_url`, `get_project_deployment_protection` | nothing: the diff over `deploy/soul` is empty |

`main` head at read time `79a09cb`. CI from the workflow files: nine jobs
in five files, and `ci.yml` is the only file that runs on a push to `main`,
so the five direct commits pushed on 2026-09-14 and 15 got the Python suite
and nothing else. The api job has been red for eight consecutive runs, #735
on `400fded` (the PR #216 merge, 2026-09-14T22:33:08Z) through #744, the api
job failing at Full suite on the en dash at `VpsActionGate.tsx:272` while the
other four jobs stay green; the last green run is #733 on `95fbdd5`, the
commit the api serves. Fixed on PR #219 as `c2daa8a`, and that PR's head
`2ef5a8e` passed 8 of 8 check runs at 06:42Z to 06:49Z.

## The body today

Cloud, read at about 07:10Z. Every workflow in the vault's active set that
persists executions fired on cadence in the last three days with zero
errors; the instance wide search for error, crashed, canceled, waiting and
running executions since 2026-09-12 returned zero.

| organ | id | last success | runs, 3 days | reading |
|---|---|---|---|---|
| Driver Poll | `mbIKJk4UuB7V27rP` | 07:00Z today, execution 7126 | 82, 82 success by filter | hourly on the hour, each 2 to 4 seconds |
| Heartbeat | `dRgTNLod2s8BAcPg` | 04:00Z today, 7117 | 13 | six hour pulse on cadence |
| Build 12 Ledger Feeder | `6hQD8YhiYzR1FFda` | 06:00Z today, 7123 | 4 | daily; last row it fed is 2026-09-13 |
| Ledger Janitor | `HKNEDVy7PUKPtsrN` | 06:30Z today, 7125 | 4 | daily, nothing to cancel |
| Pipeline Watchdog | `wndFo6uJCqVuINaV` | 04:00Z today, 7116 | 20 | every four hours |
| Notion Buffer Drain | `X3sKmPj6yHJu4xWu` | 2026-09-14T11:00Z, 7073 | 3 | daily, today's not yet due at read time |
| Platform Policy Sensor | `7WyIarNoJa2irx2r` | 2026-09-14T10:00Z, 7069 | 3 | daily, 2.5 to 3.5 minutes each |
| Weekly Table Backup | `qCfGZ1CwmpK9vOta` | 2026-09-13T07:10Z, 6994 | 1 | weekly Sunday |
| Soul Layer Write-Back | `edIJx7Q3FXTawg9J` | 2026-09-13T08:00Z, 6998 | 2 | polling trigger, fires only on a new Thread Log entry |
| Intake Former | `AEFgXee7IDJarNV7` | 2026-09-12T20:50Z, 6888, manual | 1 | nothing filed by webhook since |
| Soul Committer | `lANs6wopaK0PkNhN` | none observable | 0 | persists no executions by design; the heartbeat vitals carry soul REVERTED 1 |
| Capture Webhook | `pPIt2cELH2RVZktS` | none observable | 0 | persists neither success nor error, by the 2026-09-12 ruling |
| Approval Queue | `syRVj0G47mA1b0Xn` | none observable | 0 | same; the table is the witness |
| Event Bus | `Bvy0grTSIyEmPwFA` | none observable | 0 | successes not saved, errors would be, none were |
| Live State Ledger | `z9j2I8h0RnbDKGBO` | none observable | 0 | same; newest row 2026-09-13T06:00:39Z |
| Face | `LsmfRFMmI5feINs0` | none since 2026-09-12 | 0 | no chat turn in three days, if the instance default saves successes |
| Error Alarm | `XDQXwgFkUhYxoEjG` | none | 0 | nothing to alarm |
| TQO FINAL V5 | `gsGJQan7a6ZufhYt` | none since 2026-09-12 | 0 | all six schedules disabled, seven webhooks live, none hit; live version `0c1f7068` of 2026-09-11T22:15Z while `vault.py` records `bde7ddec` |

The tables. `devon_state_ledger` on Cloud: 21 rows, 9 COMPLETED, 12
CANCELLED, every one terminal, 4 with `human_watched` true, newest updated
2026-09-13T06:00:39Z. `devon_heartbeat_log`: 84 rows; beat 84 at 05:56Z
today is a reflection saying nothing in the estate moved and asking Tee to
move the reflection to a standalone Routine; beats 82 and 83 carried
`reflection_missing` at 34 and 40 hours, the 34 hour one emailed. The
reflection half of Build 13 was therefore silent from about 2026-09-13T14Z
to 2026-09-15T05:56Z, and the body reported it correctly. The email arrived:
Gmail thread `1a0a1ef8a73d6fd1` at 2026-09-14T22:00:25Z carries the 34 hour
finding in its WATCHING section, unread, under the subject "DEVON Pulse: all
quiet", because the subject logic does not count `reflection_missing` as
something that needs Tee. The Sunday backup mail of 2026-09-13T07:10Z
carries the full ledger and feed log as CSV attachments, which no record
lists as a data surface.
`approval_queue`: 13 rows by count, 10 approved, 1 rejected, 2 pending, and
both pending rows are past their 72 hour expiry, so nothing will act on
them; the Soul Committer's Resolve Closed node treats no decision as a
rejection, and what the queue's own decide door does with an expired token
was not read. No row and no token reached this session.
`devon_build12_feed_log`: 11 rows, 6 HOLD_SUBCONSCIOUS, 4 REQUIRES_HUMAN, 1
PROMOTE, and that one is the 2026-08-25 smoke card. No genuine PROMOTE has
ever entered the lane.

## The capability matrix

Readiness by capability, with the last thing that proved it. "Ready with
conditions" means the capability works and carries an open item a person
should know before leaning on it.

| capability | lane | last proved | readiness |
|---|---|---|---|
| State ledger, Build 02 | n8n Cloud | 21 rows, zero open; row 20 a job COMPLETED 2026-09-12 with a human watching | ready |
| Live State Ledger on Postgres, migrations 012 and 019, provenance card | Railway api, `/control` | Alembic head `019_event_hash_chain` deployed; provenance card reads it (2026-09-09) | ready with conditions: chain heads not anchored outside the database |
| Driver Poll, hourly | n8n Cloud | 82 of 82 success in three days | ready; hourly latency stands |
| Intake: Intake Former, Face, iPhone Inbox Capture, chat parser | n8n Cloud, web | a job filed 2026-09-12T20:51:53Z ran the whole lane | ready with conditions: seven trigger sweep routes gate on prose, ruling owed |
| Approval Queue, request and decide doors | n8n Cloud, SMTP | two cards approved 2026-09-12 | ready; two pending cards sit past expiry |
| Action Router and the three executors | n8n Cloud | `airtable.row` end to end 2026-09-12, `drive.draft` 2026-09-05 and 06, `spine.echo` 2026-09-05 | ready with conditions: ceiling table duplicated in two nodes; nothing above `reversible_write` has an executor |
| Event Bus and receipts | n8n Cloud | 23 trace entries and a receipt on the 2026-09-12 job | ready with conditions: the bus itself unread since 2026-09-06 |
| Heartbeat, six hour pulse | n8n Cloud | 13 of 13 in three days | ready; the reflection Routine is the weak half |
| Learning lane: Feeder, Upstream gate, Soul Committer | n8n Cloud, devon-soul | feeder 4 of 4; issuer healthy with `soul_key_set` true | ready with conditions: no genuine PROMOTE ever |
| Soul recall on the platform | Railway api | OFF: none of the four SOUL variables on the service | not ready until Tee sets `SOUL_RECALL_ENABLED` and `PINECONE_API_KEY` |
| Phone lane, `deploy/soul` on Vercel | Vercel | READY on `95fbdd5`, health healthy | ready with conditions: `SOUL_DEVON_HOST` has no default there, so DEVON's own soul on that lane is unverified |
| Capture lanes: Capture Webhook, keep, Notion Buffer Drain | n8n Cloud, Railway api | Check Token fingerprint equals the pin; drain 3 of 3 | ready with conditions: four per poster tokens inside the code node await Tee's decision |
| Presence voice | Railway presence | heard by Tee on 2026-09-10 | ready with conditions: chat voice on `/devon` through `POST /tts` unheard |
| Control plane panels, six routes | Vercel web reading Railway api | 129 checks in real Chromium, re-run today | ready with conditions: no record says a person has looked at `/control` |
| Scheduler cron, `dispatch.py` | Railway | two ticks read back 2026-09-10; `SCHEDULER_TICK_INSTALLED` is among the api service's variable names today, value unreadable; the handover reported the tile lit, not read here | ready with conditions: proven to run, never proven to have work |
| EditForge lane | Vercel, VPS render worker | `/api/health` 503 degraded 2026-09-12; one exists check through TSWS 00 | not ready |
| Workflow engine, ten routes | Railway api, cron, web | merged 2026-09-10; the smoke creates and reads one in CI only | ready with conditions: no production workflow created by a person |
| n8n telemetry panel | Railway api reading both instances | merged 2026-09-10 | unverified: the live response never read from production, and the panel's fetch is outside the smoke filter |
| Mesh dock | Vercel web | four reads answered 200 from an iPhone at 04:48Z and 04:54Z today | ready with conditions: PR #219 unmerged; on `main` a failed read still renders as recall off |
| VPS action gate and `ops.editforge.online` proxy | Vercel web | on `main` through PRs #216 to #218 and five direct pushes; the gateway answers: Vercel runtime logs show 22 requests answered 202 and one reject answered 200 between 03:59Z and 04:35Z today | unverified as a lane: no record, no critic, no receipt, the debug logging below, and the disposition of about twenty accepted requests on the gateway unread |
| Skill gate and learning store | Railway api, `/control` | opened 2026-09-10 | ready with conditions: unwatched by human eyes |
| n8n Cloud, executor of record | n8n Cloud | 49 workflows, 41 active, 13 timer runs today | ready; the vault mis-states three entries |
| n8n VPS | n8n VPS | 61 workflows, 9 active, 0 executions since 2026-09-14 | not ready, see the cutover audit |
| Railway api surface | Railway | `95fbdd5`, owes nothing | ready; `/health/ready` finding below |
| Vercel web surface | Vercel | `79a09cb` READY | ready with conditions: serves code `main` CI rejects |

## Findings that are not organs

1. The VPS action gate proxy logs a secret prefix. On `origin/main`,
   `apps/web/app/api/devon-ops/[action]/route.ts` lines 78 to 82 read, after
   `rawBody = await request.text()`, a comment "INSERT THE DEBUG LOGS EXACTLY
   HERE" and four `console.log` calls: a banner, a timestamp, `RAW BODY:`
   with the whole body, and `SECRET (first 3):` with
   `process.env.DEVON_OPS_SECRET?.substring(0, 3)`. No `NODE_ENV` guard.
   The file's own header at lines 5 to 8 says the secret must never appear
   in logs. The lines entered in `31abeff`, a direct push, and are live in
   production on `79a09cb`. This is an exposure, not a potential one: the
   Vercel runtime log for the web project holds 20 `DEVON GATEWAY DEBUG`
   entries between 03:59:24Z and 04:35:24Z today across four deployments,
   each printing the raw body and the first three characters of the
   secret, which are readable by anyone with the Vercel account and are
   not repeated here. The bodies are about fifteen `run` `tqo` requests
   with a smoke test reason, five `system` `pause` requests, all answered
   202, and one reject at 04:35:24Z answered 200 with `rejected_by` Tee.
   Blast radius: three characters of a secret of sixteen or more, plus
   every request body, in a log store the account can read. Graded low
   and real, read by byte from `origin/main` and from the log store in
   this session. Recommendation: delete lines 78 to 82 in a commit of
   their own and treat the secret as partially disclosed; not done here
   because PR #219 is the Soul arc and the lines look like a debugging
   session someone may still be in.
2. `GET /health/ready` answers ready without checking anything.
   `app/api/v1/health.py` lines 25 to 37 return HTTP 200 with
   `{"status": "ready", "checks": {"database": "pending", "ai_providers":
   "pending"}}` unconditionally; line 30 is a TODO. `app/main.py:27` says
   the route reports database availability, which is false against the
   route, and startup does not block on the database either (`main.py`
   lines 37 to 40 log a seeding failure and continue). A platform health
   check keyed on the status code would be told the service is ready
   whenever the process is up. Railway's health check path for the api
   service is `/api/v1/health`, the liveness route, read from the service
   config today, and the compose stack checks the same, so no platform
   probe keys on the lie; it also means nothing on Railway checks database
   readiness at all.
   A second copy sits at `apps/api/app/api/v1/health.py` lines 22 to 30.
3. TQO FINAL V5 is active on both instances, with seven live webhook
   doors on each, while `SYS_OPS_the-voice-lane-and-the-registration-gate_v1_2026-09-10.md`
   line 111 says the VPS copy is inactive with zero triggers and the
   2026-09-10 migration record's OPEN says the owner is to be decided before
   anything on the VPS is activated. The copies have diverged; when is
   unmeasured. Detail in the cutover audit.
4. The CI count is stated three ways: the steward skill says five jobs plus
   a sixth, `CLAUDE.md` said eight until `f3bb58a` on this branch, and the
   files hold nine. Only `ci.yml` runs on a push to `main`, so a direct push
   gets the Python suite and nothing else; `test_devon_integrity.py` inside
   the api job is what caught the web dash.
5. The vault against the Cloud census: `estate_reconcile.py check` scores 71
   of 100 with four drift lines. Two `vault.WORKFLOWS` entries, Build 08
   Credential Probe and Soul Index Setup, are archived on Cloud and recorded
   inactive; TSWS 00 Render Job is recorded active and is inactive since
   2026-09-13; the 2026-08-31 migration doc records 64 workflows against 49
   live. The 13 webhook auth claims and the Check Token fingerprint are OK.
6. The execution cap the Execution Hub is built to show is unconfigured.
   `app/services/n8n_telemetry.py` lines 296 to 299 read
   `N8N_EXECUTION_CAP`, `N8N_EXECUTION_CAP_ANCHOR_ID`, `_ANCHOR_SPENT`,
   `_ANCHOR_AT` and `_RESETS_AT` (and the `N8N_SECONDARY_` set at line 304),
   and lines 1108 to 1114 compute a spent estimate from the anchor and the
   newest execution id. The Railway api carries none of the five names for
   either prefix, so the panel draws no cap and no burn for either
   instance, and the only burn figure anywhere is the hand estimate in the
   cutover audit. Setting the anchor from the usage page is a one time
   read Tee can do.
7. The only saved version of TQO FINAL V5 on Cloud, `0c1f7068` of
   2026-09-11T22:15:43Z, records that the 11 September ElevenLabs rotation
   went to the VPS credential while the live lane runs on Cloud against
   its own, turning a rare narration error into a likely one with a
   Speechify fallback behind it. Whether Cloud narration is falling back
   today is not measured; the lane has not run since 2026-09-12.
8. The record disagrees with itself in thirteen places. The ones that
   change a reading: the learning lane cadences (the 2026-09-06 report says
   15 minute polls, the skill says daily and hourly, and today's executions
   agree with the skill); the n8n telemetry panel (one 2026-09-10 doc says
   DO NOT SHIP, another of the same date says merged, and the tree carries
   the route); TSWS 00 (one 2026-09-12 doc says it still carries a
   placeholder URL, another says the VPS copy is repointed and passed a
   smoke, and both may be true of different copies); the unified control
   plane doc whose receipt says nothing is deployed while its own
   correction section says it is; the executor count (two in the 2026-09-06
   report, three by the same day's Build 17 doc); and the vault's 51
   registered ids against 49 live. The "newest doc on a topic supersedes"
   rule cannot order two docs carrying the same date, and there are three
   dated 2026-09-10 that supersede each other.

## Open items by date

The items still open on the record, oldest first, condensed to the ones a
reader would act on. 2026-09-06: register or archive the ten DEVON named
workflows absent from the vault; fix the Notion Buffer Drain's eight Area
list and its 1900 character truncation; read the real n8n execution cap.
2026-09-08: anchor chain heads outside the database. 2026-09-09: the chat
voice on `/devon` unheard; nobody has filed a capture through keep; the
console mute button toggles over a refusing Voice; the receipt canon
backlog of forty five exempt docs awaits a ruling. 2026-09-10: Tee opens
`/control` on a phone and looks; the stray Railway service
`Meta-Supreme-Apex-Genesis-` `6fb2feb3` with a 57 change staged patch, not
among the four services of project `devon-api` today and possibly in another
project, unverified; seven
trigger sweep routes gate on prose; decide which instance owns the
schedules; rotate the ElevenLabs key found as a literal in an archived
sub-workflow; the two unauthenticated GET link triggers on V5. 2026-09-11:
no V5 lane has run end to end on Gateway credits because every schedule is
disabled; the four step render worker acceptance suite on real media.
2026-09-12: where EditForge runs; no human can sign in to
`editforge.vercel.app`; the ceiling table duplicated between Job Driver and
Action Router; four per poster capture tokens inside the Check Token node;
no genuine PROMOTE; the reflection to intent loop not built; the connector
snapshot has no scheduled run. 2026-09-15, new: Tee sets the two soul
variables on Railway api and runs the four read back steps; merge PR #219
so `main` goes green and the dock stops rendering a failed read as recall
off; remove the proxy debug logging; write a record for the VPS action gate;
reconcile the CI count in the steward skill; move the reflection to a
standalone Routine as beat 84 asks.

## What could not be measured here

Direct reads of `railway.app`, `vercel.app` and `ops.editforge.online`, all
refused by the egress policy, so the presence health payload, the Railway
health check path and whether the ops gateway answers are unverified. The
`devon-soul` project's variable names. Soul Committer, Capture Webhook and
Approval Queue execution health, because those three persist no executions
by design; their tables were read instead. The Face's instance default for
saving successes. `devon_soul_commit_log` and `devon_driver_log`, not read;
soul REVERTED 1 comes from the heartbeat vitals. Whether the 34 hour
reflection email reached the inbox. Whether either expired pending card
carries a decision that never landed. The diff behind V5's version drift,
`bde7ddec` in the vault against `0c1f7068` live. The twelve name gap between
the 29 variable names the service config lists on the api and the 41 an
earlier variable read counted. And every external poster's target, which
is inferred from the vault and was not read.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-readiness-audit_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: none ruled; nothing on any surface was changed. Five calls are put to Tee: set SOUL_RECALL_ENABLED and PINECONE_API_KEY on the Railway api service; delete the four debug lines at apps/web/app/api/devon-ops/[action]/route.ts:78-82 in their own commit; give /health/ready a real database check or rename what it returns; decide which instance owns TQO FINAL V5; and move the Build 13 reflection to a standalone Routine as beat 84 asks.
FINDINGS: the core job lane is operational and human gated, proved by ledger row 20 on 2026-09-12 and by 82 of 82 Driver Poll successes, 13 heartbeats, 4 feeder and 4 janitor runs with zero errors in three days; the ledger holds 21 terminal rows and nothing has moved since 2026-09-13T06:00:39Z; the api, presence and phone lane surfaces owe nothing to main on their own paths, and main's red since run #735 is one en dash fixed on PR #219, green on 8 of 8 checks there; soul recall on the platform is off on configuration alone; the EditForge studio has no human sign in and no artifact store; the VPS runs no DEVON organ and carries a diverged active copy of TQO FINAL V5; the learning lane has never carried a genuine PROMOTE; the devon-ops proxy on origin/main logs the raw body and three characters of DEVON_OPS_SECRET on every call, and the Vercel log store holds twenty such lines from this morning, so the prefix is disclosed; the gateway at ops.editforge.online is live and accepted about twenty requests today whose disposition is unread; /health/ready returns ready with no check behind it and main.py:27 claims otherwise, while Railway probes /api/v1/health and so checks no database readiness at all; two approval cards sit pending past expiry; the reflection Routine was silent about 40 hours and the body reported it, in an email whose subject read all quiet; the vault scores 71 of 100 against Cloud with four drift lines; the record disagrees with itself in thirteen places.
OPEN: the five calls above; the 2026-09-15 items in the open list; the thirteen record disagreements, which need a dating rule for same day docs before they can be closed; the eleven things listed as not measurable from this container.
STATUS: DEVON is operational at the core and not ready on four edges, and two of its readiness signals answer in the reassuring direction without a check. Every ready label rests on an execution id, a ledger row, a deployment id or a byte read named beside it; every organ that could not be measured is labelled unverified, with no rounding up. Filed with the cutover audit on the designated branch; nothing merged.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
