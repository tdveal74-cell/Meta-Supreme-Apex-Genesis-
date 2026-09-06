# SYS_OPS: DEVON operational report, what he can do today and what he cannot

Date: 2026-09-06. A standing read of the live estate taken between 08:35Z and
08:55Z, written the same hour.
Status: FINAL for this read. The next report supersedes it.
Supersedes: nothing in this repository. The nearest prior is the Notion Thread
Log page "DEVON operational assessment, two framing corrections, and the Avatar
Content Run recovery" (3d268ff50db681758c4fdcc1844ff274, 2026-09-05).
Related: PR #146 (merged a719ecd), SYS_OPS_devon-autonomy-driver_v1_2026-09-05.md,
SYS_OPS_devon-draft-parser_v1_2026-09-06.md,
SYS_OPS_alert-lane-blackout-and-estate-map_v1_2026-09-05.md, Notion Thread Log
page 3d368ff50db6811ca2b3cab91a4d52eb (this session's log).

Every claim below is labelled. VERIFIED means read from a live system this
morning with the id shown. RULED means Tee decided it. UNVERIFIED means believed
from a record and not measured today. ESTIMATE means arithmetic on a reading.
Ids are the join key throughout; names are shown for a human and were unescaped
from the API.

---

## 1. Verdict in one paragraph

DEVON is operational and human gated. He takes a job from a phone capture, a
chat message or a webhook post, understands it against the ledger, plans it
with a Cerebras brief, raises an approval card to Tee by email, executes
through an allowlisted executor once the card is granted, raises a verification
card, and closes the job with a receipt in the ledger. Two executors exist: a
certification echo (ceiling read) and a Google Doc draft in a show's script
folder (ceiling reversible_write). Every write passes Tee twice, once to
authorise and once to verify. At read time the hourly poll had run clean on
every pass since 03:00Z, the six hourly pulse was arriving on SMTP, and the
estate had produced zero error executions in the fourteen hours before the
read. The gaps are equally plain: two executors and no more, a registry that
misses four active organs so the reconciler does not watch them, a cloud to
VPS cutover on a clock with an estimated wall of 2026-09-21, and one stale
approval card that will cancel itself on 2026-09-08.

## 2. What DEVON is made of

### The census, VERIFIED

Project `rM0TNTE2fNXErglU` on `thequietoperator.app.n8n.cloud`, read in one page
of 63 with `count` 63, aggregated by script from a TSV rather than by eye.

| Count | What |
|---|---|
| 63 | workflows in the project, 38 active, 25 inactive |
| 39 | with DEVON in the name, 31 active, 8 inactive |
| 31 | registered in `services/devon/vault.py` WORKFLOWS, every one present on the instance, every state matching |
| 10 | DEVON named on the instance and absent from the vault, 4 active and 6 inactive (section 6, finding 1) |
| 10 | doors in `vault.WEBHOOKS`, one of them now carrying a body gate fingerprint |
| 5 | open rulings in the vault, listed by every reconciler run |
| 24 | workflows with no DEVON in the name: the TQO and TSWS pipelines, seeds, one shots, and the shared OS Error Handler |

### The organs, by function

Names are given without the instance's em dash separator; the id is the
identity.

**Spine and ledger.** Live State Ledger `z9j2I8h0RnbDKGBO` (door `devon-ledger`),
Event Bus and Universal Receipts `Bvy0grTSIyEmPwFA` (door `devon-event`), Spine
Conformance Executor `Oi7o1sTEqhxhOaJL` (door `devon-spine-n8n`, advances one
legal state), Conscious and Subconscious Runtime `5Nc9yh6WSqBJ41ok` (door
`devon-runtime`, UNDERSTANDING to PLANNING with area recall), Intelligence
Router `xh3EkLmgTDJFhzGH` (door `devon-route`, PLANNING to the next gate).

**Autonomy, Builds 14 to 16.** Intake Former `AEFgXee7IDJarNV7` (door
`devon-intake`, Cerebras tagging), Job Driver `TT4TfFXyH9O7lfdc` (one pass
state machine, called per open job), Driver Poll `mbIKJk4UuB7V27rP` (schedule
trigger every 1 hour, no cron string, executionTimeout 300, error workflow
`XDQXwgFkUhYxoEjG`, resumes RECEIVED, UNDERSTANDING, PLANNING,
WAITING_APPROVAL, ESCALATED, AUTHORIZED, EXECUTING and VERIFYING, skips rows
written in the last three minutes), Action Router `ecLqrxALuLDdF2BN` (door
`devon-action`, the allowlist in section 3), Drive Draft Writer
`J7Ly7riwXEd95D9a` (door `devon-drive-draft`, the refuse on dash parser is its
active version `fac97950-0f49-4f23-a169-58a33d9d887d`), EditForge Handoff
`OFIhA7zdFv9UoyCv` (door `devon-editforge`, a second stage organ that acts on an
EXECUTING envelope and is deliberately not on the router, RULED 2026-08-24).

**Human interface.** Approval Queue `syRVj0G47mA1b0Xn` (door
`devon-approve-request` behind the header key, `devon-approve-decide` behind a
single use token in the emailed link with a 72 hour expiry), Face
`LsmfRFMmI5feINs0` (hosted chat behind n8n login, files jobs at level 2 or
higher, RULED), iPhone Inbox Capture `5s6CwWWelffqszQe` (door `devon-inbox`),
Capture Webhook `pPIt2cELH2RVZktS` (door `devon-capture`, header key plus the
Check Token body gate, receipts from ChatGPT, Grok, Gemini and Claude into
Airtable), Capture Nudge `YHueoBK7TSLdTlfF` (daily 08:00).

**Memory and learning.** Soul Committer `lANs6wopaK0PkNhN`, Soul Layer
Write-Back `edIJx7Q3FXTawg9J` and Build 12 Ledger Feeder `6hQD8YhiYzR1FFda`
(each a 15 minute poll), Build 12 Upstream Test `VznESplSFCs8ldph` (door
`devon-build12-upstream`), Learning Lane Table Reader `we45pHkQHRmSRnZx`
(manual, read only, inactive on purpose), Notion Buffer Drain
`X3sKmPj6yHJu4xWu` (daily at 07:00 America/New_York, Airtable Thread Receipts
to the Notion Thread Log over the public REST API with credential
`b9FYEfGUlMiYJCCU`; not in the vault).

**Housekeeping and alarms.** Heartbeat `dRgTNLod2s8BAcPg` (6 hour pulse on
SMTP), Error Alarm `XDQXwgFkUhYxoEjG`, OS Error Handler `rqYmaQh91iCce8DJ`
(shared with the TQO pipeline), Pipeline Watchdog `wndFo6uJCqVuINaV`,
Precedence Guard `W5rlpAt6hsJAExU6` (daily 07:00), Duplicate Sweep
`X7OGXWHBx57CIG42`, Ledger Janitor `HKNEDVy7PUKPtsrN` (daily 02:30), Weekly
Table Backup `qCfGZ1CwmpK9vOta` (Sunday 03:10), Health and Observability
Console `M3H2mVPZJpDyIzrl` (GET `devon-health`, mentioned in a vault comment,
not registered), Monthly Credential Review `yro0wBRGghMjkZhj` (not registered),
To Delete Auto-Purge 30d `0soYvqnSKYlFn3gr` (not registered).

**Retired or parked.** Capture Hook `Cbd24ptTPWch3aZO` (retired 2026-08-22),
TQO FINAL V5 `gsGJQan7a6ZufhYt` (inactive by ruling), and six inactive DEVON
named workflows the vault does not carry: Soul Index Setup one shot
`vYr35jqNNaAztGhQ`, Build 08 Credential Probe `pm5hoO4eFpGhlAb4`, End to End
Watch Harness `ktZ0fnrgxvCNY9xH`, Master Index `ocU2Zep8WyRmbsIk`, Purge List
`Epcmuep1JnBaSrrr`, Vault Comparison `mhI1YAoqrITtuB1M`.

### The data he keeps, VERIFIED

| Store | Id | Read today |
|---|---|---|
| State ledger | n8n data table `VYyno7pDWmY6uxBz`, 37 columns | yes, all 17 rows aggregated |
| Approval queue | n8n data table `u6wzeN5y9LNxROsN` | no, on purpose; it carries the single use decide tokens in plaintext |
| Driver log | n8n data table `9VbICTCa4x4yhWZm` | no |
| Chat log | n8n data table `nwnHN8o2dgHjtk7f` | no |
| Capture buffer | Airtable Thread Receipts `tblEhgEZoNr2ztbB3` in base `app28z7XnKzjfTXwc` | yes, drained to empty |
| Memory | Notion Thread Log, data source `a5bcfbf5-ce1d-493b-9992-a11bc2a03dc4` | yes, two pages written |
| Shared key | n8n credential Devon Capture Key `FYRvkRTOcROEYZ9P`, header `x-devon-key` | rotated 2026-09-06, three proofs in hand (RULED and VERIFIED, PR #143) |

### Off n8n

Railway project `devon-api` `3bf31602-1e72-4fac-ade7-4c89106d8896` serves the
FastAPI app, the ledger schema and the Alembic migrations. Vercel project
`devon-soul` `prj_RTiwmhndbWFWf1KH7go43rs2Acxn` serves the phone lane from
`deploy/soul`. Vercel project `meta-supreme-apex-genesis-web`
`prj_tlXnTP7pZ2qzdDBdU0hNID7ystaw` serves the Command Center from `apps/web`.
Two VPSs are recorded, `srv1936193` (self hosted n8n, installed and empty) and
`srv1936199` (EditForge); both were VERIFIED up on 2026-09-05 by direct read
and are UNVERIFIED today, the container has no egress to either.

## 3. What he can do today

Each line is a ledger row or an execution, not a description of intent.

- **A level 0 job, end to end, unattended.** Job `01M1S81K3WDD0JSKY6KPAY43K1`
  ran RECEIVED to COMPLETED in 14 seconds on 2026-09-05 (execution 5629,
  VERIFIED from the receipt logged that day; not re-read this morning).
- **A gated job with a real artifact.** Job `01M1SAK59GF0511GR7B78Y06A9`
  (TQO, level 2, reversible_write): card `REQ-20260905-12yaAZ` raised at
  17:41:59Z, approved by Tee at 18:33:39Z, dispatched as `drive.draft` at
  19:34:48Z, Google Doc of 491 words written to `TQO/01_SCRIPTS` at 19:34:53Z
  (`1xKry9iQc2hzK3ewk2szlWn02_Y0uJsDn7MkEUk89ocs`), verification card
  `REQ-20260905-0Mq1q1` raised at 19:34:58Z, approved by Tee at 19:37:29Z,
  COMPLETED with `human_watched` true. VERIFIED from the ledger row this
  morning. A second draft job, `01M1SN5X4ETKEPPCC4JT61TE5V`, COMPLETED at
  02:30:19Z today with one artifact, human watched.
- **A rejection lands as a cancelled row with the reason.** Tee rejected card
  `REQ-20260905-TwrTv3` at 07:12:48Z today; the 08:00Z poll (execution 6132)
  wrote job `01M1S8CZ37X87B6281WPQA68B1` to CANCELLED, `receipt_outcome`
  cancelled, `state_reason` naming the card and the time. Forty eight minutes
  from tap to ledger is the hourly cadence, not a fault. VERIFIED.
- **An out of scope action is refused, not widened.** The Action Router's
  allowlist and ceilings, VERIFIED from the live node "Authorise and Resolve
  Target":

  | action | dispatches to | ceiling |
  |---|---|---|
  | `spine.echo` | `Oi7o1sTEqhxhOaJL` | read |
  | `drive.draft` | `J7Ly7riwXEd95D9a` | reversible_write |

  Execution 5810 (2026-09-05T18:35:45Z) is the last error execution in the
  estate and it is this rule working: the driver asked `spine.echo` to carry a
  reversible_write job an hour before `drive.draft` existed, and the router
  threw REFUSED rather than widen. The router now answers refusals as data
  (RULED 2026-09-05), so the same case today parks the job at AUTHORIZED with
  the reason in the ledger row and one digest email per distinct reason.
- **The shared key was rotated without dropping a job.** Job
  `01M1TB5RAJHF0FJEN91QMKYYK7` ran RECEIVED to COMPLETED at 03:11:25Z today on
  the new key; the old key returned 401 to Tee and is deleted. VERIFIED and
  RULED.
- **Receipts from other platforms reach memory.** A Claude receipt posted to
  `devon-capture` on 2026-09-05 at 18:24Z sat in Airtable until this session
  drained it into Notion page `3d368ff50db681e8a09ff0ea4c93ff62` and ticked
  the row. The Notion Buffer Drain workflow would have done the same at 11:00Z
  with a lossier mapping (section 6, finding 2). VERIFIED.
- **He talks.** The Face files jobs from chat at level 2 or higher behind n8n
  login. RULED and proven on 2026-09-05 (executions 5733, 5734, 5754 in that
  day's receipt); not exercised today, so UNVERIFIED for today.
- **He writes home.** Heartbeat executions 5623, 5969 and 6092 succeeded at
  16:00Z and 22:00Z on 2026-09-05 and 04:00Z today on the SMTP credential.
  VERIFIED.

## 4. Health at read time, VERIFIED

| Signal | Reading |
|---|---|
| Driver Poll `mbIKJk4UuB7V27rP` | 29 executions in history; 03:00Z through 08:00Z today (6045, 6088, 6097, 6104, 6119, 6132) all success, 3 to 5 seconds each |
| Heartbeat `dRgTNLod2s8BAcPg` | last three success; the errors at 10:00Z and 12:04Z on 2026-09-05 (5583, 5598) are the blackout arc, closed that day |
| Error executions since 2026-09-05T08:00Z | six, all on 2026-09-05, the last at 18:35:45Z (5810, explained above); none in the fourteen hours to the read |
| Ledger `VYyno7pDWmY6uxBz` | 17 rows: 9 CANCELLED, 7 COMPLETED, 1 WAITING_APPROVAL; 16 terminal; 15 Systems, 2 TQO; 2 human watched; 2 with an artifact; first row 2026-08-24T01:01:51Z, latest update 2026-09-06T08:00:03Z |
| The one open row | `01M1S84TTY4DMC4D0VCHTJB672`, card `REQ-20260905-f5kEZj`, raised 2026-09-05T16:59:10Z before the SMTP fix so it never emailed; expires 2026-09-08T16:59:10Z; `decide.js` cancels an undecided expired card |
| Notion Buffer Drain `X3sKmPj6yHJu4xWu` | daily success 2026-09-01 to 2026-09-05 (5106 to 5589); errors on 08-30 and 08-31 (4873, 4990) are the quota outage |
| Railway `devon-api` | LIVE on `a719ecd`: deployment `c5f389cd` SUCCESS at 08:50:40Z; the deploy log carries the alembic context lines from the pre deploy hook at 08:50:18Z and `Application startup complete` at 08:50:37Z. The database was not touched by #146, so the hook found nothing pending and there is no `Running upgrade` line, which is expected |
| Vercel `devon-soul` | LIVE on `a719ecd`: `dpl_2hUqKkdKti2YBHEoNapGeGtGVvFm`, READY, `target: "production"`, created 08:44:18Z; `deploy/soul/services/devon/vault.py` changed in #146, so this build was owed and it ran |
| Vercel `meta-supreme-apex-genesis-web` | current on its own terms: `dpl_8jWAx3yHecZDeQUZF949o6YfoUMY` on `a719ecd` is CANCELED with `target: "production"`, which is the `ignoreCommand` skipping; verified by hand below rather than trusted |

The web surface is current on its own terms: `git diff --stat cb01b7a a719ecd`
over `apps/web`, `packages/ui`, `pnpm-lock.yaml` and `pnpm-workspace.yaml` is
empty, and `cb01b7a` is the last commit that actually built that project.

## 5. What he cannot do yet, stated plainly

- **Two executors.** A job above reversible_write, or a reversible write the
  driver does not read as draft like, has no executor. It parks at AUTHORIZED
  with the reason, is re-dispatched hourly, and cancels with a receipt when
  its grant decays at decided_at plus 24 hours. An Airtable row, a render, a
  publish: none of these can be executed today. `editforge.render` is
  deliberately off the router because Build 07 accepts EXECUTING and the
  router hands off AUTHORIZED (RULED 2026-08-24).
- **No Zapier lane.** Build 05 is half shipped and says so in its own code.
- **Hourly latency.** A tap on a card waits for the next poll, up to an hour.
  Ten minute polling waits for the VPS, where executions are free.
- **No silent capture.** Nothing watches a chat on any platform. Capture is a
  receipt at the end of a thread, posted or pasted (thread log skill).
- **Learning is not captured.** `learning_state` was `not_captured` on every
  ledger row read in full this morning (3 of 17) and on every row in the
  2026-09-05 receipts. UNVERIFIED for the other 14 rows; the census did not
  aggregate that column.
- **Four active organs are unwatched.** The reconciler checks workflow state
  for the 31 registered ids only, so the Health Console, the Credential
  Review, the Buffer Drain and the Auto-Purge can go inactive without a DRIFT.
- **The clock.** Cloud execution burn was ESTIMATED on 2026-09-05 at about 120
  a day, wall about 2026-09-21 if the plan caps at 2,500. Read the real cap on
  n8n's usage page; this report did not.

## 6. Findings from this read, graded before raising

1. **Registry gap, record side, DRIFT.** Ten DEVON named workflows on the
   instance are absent from `vault.WORKFLOWS`: active `M3H2mVPZJpDyIzrl`,
   `yro0wBRGghMjkZhj`, `X3sKmPj6yHJu4xWu`, `0soYvqnSKYlFn3gr`; inactive
   `vYr35jqNNaAztGhQ`, `pm5hoO4eFpGhlAb4`, `ktZ0fnrgxvCNY9xH`,
   `ocU2Zep8WyRmbsIk`, `Epcmuep1JnBaSrrr`, `mhI1YAoqrITtuB1M`. Consequence:
   no state claim, so no DRIFT when one of the four active ones stops. Fix:
   register them in both vault copies, or archive the six inactive ones (an
   estate effect, Tee's call). Owner: the next session, after Tee rules which
   are in scope.
2. **The thread log skill is stale in two places, and the drain workflow
   inherits one of them.** The skill says eight Areas and never invent a ninth;
   ACX is live as the ninth in Notion, Airtable and the Capture Webhook (RULED
   2026-08-20). The skill also says n8n holds no Notion credential; the Notion
   Buffer Drain posts to `api.notion.com` daily with credential
   `b9FYEfGUlMiYJCCU`. Its `AREAS` constant is the eight, so an ACX receipt is
   filed to Notion with no Area, silently. It also truncates every field at
   1900 characters and does not carry `Raw` into the page body, which the skill
   requires. Consequence: a lossy automatic drain and a hand drain that
   disagree. Owner: Tee, the skill is his synced file; the workflow edit is an
   effect behind the gate.
3. **Execution history keeps the key.** n8n stores the inbound request headers
   of every webhook execution, `x-devon-key` included, in plaintext, readable
   by anyone with workflow read on the instance. Graded low: an n8n login
   already confers workflow edit, which is a larger power than the key, and
   the value seen this morning was the retired one. Not a finding to act on
   alone; it is a reason to prefer per execution data retention settings on
   the Router and the Capture Webhook if the instance ever gains a second
   user. Owner: Tee's ruling.
4. **One stale card.** `REQ-20260905-f5kEZj` self cancels on 2026-09-08. No
   action unless Tee wants to decide it, which would prove nothing new.
5. **Dead Gmail carriers, UNVERIFIED today.** The blackout doc lists the Weekly
   Table Backup as still carrying the invalid Gmail credential. Its next run is
   Sunday 03:10Z; this report did not read its credential.
6. **A mislabelled failure row.** The Buffer Drain's `Log Sync Failure` node
   hard codes `Type: Ambiguous date` on every sync failure it files. Cosmetic,
   but a reader triaging that table would be misled. Owner: the workflow edit
   above.

## 7. Recommended next builds, in order

A recommendation. Tee rules.

1. Close the registry gap (finding 1). Record side, cheap, and it puts the
   whole estate under the reconciler.
2. Runbook C before the wall: mint the VPS API key, `n8n_migrate.py` export and
   import from a machine with egress to both hosts, repoint the MCP connector,
   re-run the reconcile and both lane proofs on the VPS, then tighten the poll
   to ten minutes.
3. A third executor at reversible_write, an Airtable row write, through the
   same allowlist and ceiling. It is the smallest executor that is not a
   document.
4. Learning capture on COMPLETED rows, so `learning_state` stops reading
   `not_captured` on every job.
5. Fix the drain's Area list and failure label in the same workflow edit
   (findings 2 and 6), after Tee rules on the nine Areas in the skill.

## 8. Receipts

- Ledger rows read in full: `01M1S84TTY4DMC4D0VCHTJB672`,
  `01M1S8CZ37X87B6281WPQA68B1`, `01M1SAK59GF0511GR7B78Y06A9`; all 17 rows
  aggregated by the census subagent, page 2 at skip 100 empty, count 17.
- Executions read: 5810 (router refusal, full data), 5583, 5598, 5591, 5585,
  5681 (error list), 6045 to 6132 (poll), 5623, 5969, 6092 (pulse), 4873 to
  5589 (drain).
- Workflow details read: `X3sKmPj6yHJu4xWu` full, `mbIKJk4UuB7V27rP` full,
  `ecLqrxALuLDdF2BN` full, `pPIt2cELH2RVZktS` (the pin, PR #146).
- GitHub: PR #146 merged as `a719ecd` at about 08:44Z with all six checks
  green on `1b59b56`; designated branch restarted from main.
- Railway deployment `c5f389cd-b8c9-439b-a65a-9311227c0655` SUCCESS on `a719ecd`; Vercel devon-soul `dpl_2hUqKkdKti2YBHEoNapGeGtGVvFm` READY production on `a719ecd`; web `dpl_8jWAx3yHecZDeQUZF949o6YfoUMY` CANCELED production on `a719ecd` (skip verified).
- Notion pages: `3d368ff50db681e8a09ff0ea4c93ff62` (drained receipt),
  `3d368ff50db6811ca2b3cab91a4d52eb` (this session's log).
- Airtable: `recHjlkQBRWcwnHbQ` ticked Synced to Notion.

## 9. How this was read, and what was not touched

n8n was read only; `approval_queue` `u6wzeN5y9LNxROsN` was not read. The
census subagent passed every printed value through a mask for `dcp_` and
`devon_` prefixes and the mask fired zero times. Writes made in the whole
session: two Notion pages, one Airtable checkbox, the merge of PR #146 and the
branch restart. No workflow was published, activated, deactivated or edited by
this report.
