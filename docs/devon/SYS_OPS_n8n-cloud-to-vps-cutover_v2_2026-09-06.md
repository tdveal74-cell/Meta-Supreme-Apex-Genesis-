# n8n Cloud to VPS cutover, runbook v2

    status: runbook, cutover not started; Cloud estate census read live 2026-09-06
    source: thequietoperator.app.n8n.cloud, 64 workflows, 39 active, 11 data tables
    target: n8n.editforge.online on Hostinger VPS srv1936193 (2.25.140.44).
            Tee stated 2026-09-06 that nine data tables are there. This sandbox
            has no egress to the VPS, so nothing about the VPS is verified here.
    cap: 2,500 executions a month, stated by Tee 2026-09-06; 1,212 spent by
         13:00Z on 2026-09-06; the wall is 2026-09-17 to 2026-09-25 by section 2,
         the later date at the quiet burn and the earlier with two more build days
    supersedes: docs/devon/SYS_OPS_n8n-cloud-to-vps-migration_v1_2026-08-31.md
            for the cutover itself. v1 stays the reference for the 28 credentials,
            the Google OAuth redirect URI and the drain ruling, and is amended
            in place where this pass moved it.
    tool: scripts/n8n_migrate.py (export, inspect, import --rewrite-host, repoint),
          extended in this pass, tests in test_n8n_migrate.py

## Verdict in one paragraph

The cutover is ready to run from Tee's machine and nothing in this pass ran
it. What this pass added is the part v1 named as a class of problem and left
unenumerated: a node level census of all 64 Cloud workflows, taken by two
independent readers per workflow with every disagreement re-read singly
(section 4), and a tool that acts on that census instead of asking a human to
walk 39 workflows by hand. `inspect` now lists every host written inside a
node, every sub-workflow target and every error workflow setting and says
which ones the export never saw; `import --rewrite-host` replaces the Cloud
host literal and prints each node it touched; `repoint` rewrites workflow,
credential and data table ids on the target from maps and exits non-zero
while anything still points at Cloud. Two facts change the plan since v1:
the VPS is not empty of tables, it holds a 2026-09-03 copy that is stale and
must be wiped before the real copy (section 3, hazard 1), and there are
eleven tables now, not nine, so the VPS is missing the two the autonomy lane
writes to every hour (hazard 2). The wall is the reason to move at all:
1,212 of 2,500 executions were spent by 13:00Z on 2026-09-06 and the quiet
burn spends the rest in about a week.

## 1. What changed since the 2026-08-31 worklist

| Then (2026-08-31) | Now (2026-09-06, read live unless marked) |
|---|---|
| 58 workflows, 32 active | 64 workflows, 39 active (`search_workflows`, count 64) |
| 9 data tables | 11: `devon_driver_log` (11 columns) and `devon_chat_log` (7) were created 2026-09-05; the nine of 08-31 are identical column for column; `docs/devon/n8n-datatable-schemas.json` re-read and regenerated |
| VPS "currently empty of workflows" | Tee, 2026-09-06: nine data tables are on the VPS. Ledger job `01M1KAEBPXJZMZSWC6MM02E2HA` (COMPLETED 2026-09-03, executor claude-cowork-session) records nine tables and 38 rows migrated. Workflows on the VPS: unknown here |
| cap unread | 2,500 executions a month (Tee, 2026-09-06). Cycle reset date: unread, see section 2 |
| Approval Queue mails through Gmail OAuth | SMTP `mu7nJRSpkAfkzLdF` since 2026-09-05 (version b598e4a3 created 18:31Z that day, the workflow last updated 20:43Z; read 2026-09-06). The Gmail credential `vsTKuAilHmpYCc5L` died around 2026-09-01; the queue stored pending rows it could not announce for about nine days, which is how card `REQ-20260905-f5kEZj` came to exist without an email |
| host references "named as a class" | enumerated per node, section 4 |
| repointing by hand | `repoint` from `_id_map.json` plus credential and table maps |
| Soul Committer every 15 minutes | hourly since 2026-09-06 13:11Z (PR #154 merged 73e1851) |

## 2. The wall, measured

Execution ids on the Cloud instance are global and monotonic, so the delta
between two ids is the number of executions between them, saved or not.
This is an upper bound on what the plan counts only if n8n counts every
execution and the cycle is the calendar month; neither could be verified
here (docs.n8n.io is blocked by the sandbox egress policy), so the usage
page in the Cloud dashboard is the truth and this table is the estimate.

| Moment (UTC) | Execution id | Note |
|---|---|---|
| 2026-09-01 00:00:13 | 5053 | first execution of the month (Pipeline Watchdog) |
| 2026-09-05 12:35 | 5602 | start of the 24 hour window in the Build 18 doc |
| 2026-09-06 00:00:00 | 5982 | Driver Poll |
| 2026-09-06 13:00:00 | 6265 | Driver Poll; 6266 its driver pass |

Month to date at 13:00Z on 2026-09-06: 1,212. Remaining under 2,500: 1,288.

Burn: 929 over the five days to 2026-09-06 00:00Z, about 186 a day, with
the committer at four an hour and two build days inside it; 283 in the
thirteen hours after that, a build day. The Build 18 doc's 264 a day was an
extrapolation from a four hour window that happened to hold the daily
crowd (the feeder, the janitor, the sweep, the Sunday backup), and it
overstated the quiet day.

**First post change hour, measured.** The 13:00Z Driver Poll was id 6265
and the 14:00Z poll id 6268: three executions in the hour, the poll, its
driver pass for the one open job, and the hourly committer. That is one
hour and one point. The day's quiet burn is that base plus what the
schedules in 4.8 add:

| Source | A day |
|---|---|
| Driver Poll, hourly | 24 |
| driver pass for the open job, hourly until it cancels | 24 |
| Soul Committer, hourly | 24 |
| Heartbeat every 6 hours | 4 |
| Pipeline Watchdog every 4 hours | 6 |
| six dailies (feeder, janitor, sweep, nudge, precedence, drain) | 6 |
| weekly backup, weekly purge, monthly review | under 1 |
| Soul Layer Write-Back | only when the Thread Log gains a page |
| quiet total | about 88, about 64 once the open job cancels |

Projection from that alone: 1,288 remaining at 13:00Z on 2026-09-06, 88 a
day to 2026-09-08 17:00Z, then 64 a day, spends the last execution about
2026-09-25, which is the wall if the cycle resets on the 1st. Every build
or proof session moves it earlier: 2026-09-05 and 2026-09-06 each cost
roughly 280 beyond the quiet rate, about four days of margin apiece. Two
more such days put the wall around 2026-09-17. The number in the status
block is therefore a range, 2026-09-17 to 2026-09-25, and the usage page
is the truth on both the count and the reset date.

Levers left on Cloud, all small next to the cutover: pausing the Soul
Committer until cutover saves 24 a day (it has proposed nothing in twelve
days and the commit log holds one row); the Driver Poll at two hours saves
12 a day with no open jobs; the Watchdog at twelve hours saves 4. The
cutover removes the ceiling.

The stale card `REQ-20260905-f5kEZj` on job `01M1S84TTY4DMC4D0VCHTJB672`
cannot be decided: Approval Queue execution 5681 at 2026-09-05T16:59:10Z
stored the row and errored at Email Tee on the dead Gmail credential, so
the approve and reject links never left the instance, and the queue has no
resend path. It costs one driver pass per hourly poll (35 passes in the
driver log by 13:00Z on 2026-09-06, all `awaiting approval decision`) until
the card expires at 2026-09-08T16:59:10Z, when the driver cancels the job
on its next poll. That expiry path has never run live; letting it run is a
free proof of it, at a cost of about 50 executions. Recommended over a hand
cancellation through the ledger webhook.

## 3. Hazards this pass found, each with its fix

1. **The VPS holds a stale copy of the ledger.** The 2026-09-03 job copied
   38 rows across nine tables. The Cloud ledger has moved since: 18 rows
   now, 17 terminal, one open. A VPS Driver Poll activated over a 09-03 copy
   would resume whatever was non-terminal on 09-03 and the VPS Janitor
   would cancel the rest through the VPS ledger webhook, both against jobs
   that Cloud has already finished, and any `approval_queue` row that came
   across carries a live decision token for a card that was decided on
   Cloud. Fix: delete every row of every DEVON table on the VPS before the
   real copy in step 6.2, never activate a timer workflow on the VPS while
   its tables hold the 09-03 rows, and keep `approval_queue` empty on the
   VPS for good (v1 ruling, unchanged).
2. **Two tables are missing on the VPS.** `devon_driver_log` and
   `devon_chat_log` did not exist on 2026-09-03. The Driver Poll and the
   Job Driver write the first on every pass and the Face writes the second
   on every message. Fix: create both from the regenerated schema file
   before import; `repoint --table-map` needs their VPS ids.
3. **The Cloud host is written inside nodes**, not only in webhook URLs.
   26 occurrences in 14 active workflows (4.2); the Job Driver builds every organ URL
   from one `HOST` constant, the Action Router's allowlist carries three
   absolute executor URLs, the Approval Queue builds its decision links from
   a `HOST` constant, and HTTP Request nodes across the lane carry the host
   verbatim. Fix: `import --rewrite-host thequietoperator.app.n8n.cloud=n8n.editforge.online`,
   dry run first, and compare its plan against section 4.
4. **Workflow ids are written inside Code nodes too**, and `repoint` does
   not rewrite those. The Action Router's allowlist carries the executors'
   Cloud workflow ids as `workflow_id`; the router passes it through as
   `target_workflow` and the Job Driver only prints it in its log line
   (`absorb.js`), so a stale value is cosmetic there. Section 4 lists every
   Code node the census found carrying a workflow id; check each against the
   `_id_map.json` and edit by hand where the id is load bearing.
5. **Sub-workflow targets and error workflow settings** address Cloud ids.
   33 Execute Workflow nodes in active workflows and two error workflows named
   by 24 active workflows (4.3, 4.4); `repoint` rewrites every one that is
   in the id map and names every one that is not.
6. **Credentials by id.** v1 lists the 28. 11 are bound by an active
   workflow (4.5), so Tee can create only those first. Of v1's three OAuth
   blockers only Google Drive is bound by an active workflow; Gmail and
   YouTube are bound by inactive ones only, so the redirect URI work in v1
   serves one consent flow, not three.
7. **External posters.** Everything that POSTs to a Cloud webhook keeps
   posting there until told otherwise. Known from the vault's rotation
   checklist and from this pass: the iPhone Shortcut(s) posting to
   `devon-capture` and `devon-inbox`; any Apple automation posting to
   `devon-intake`; the custom instructions on ChatGPT, Grok, Gemini and
   Claude that carry the `devon-capture` URL and a body token; any saved
   curl; the claude.ai n8n MCP connector, which is how every Claude session
   including this one reaches the instance; Tee's bookmark for the Face's
   chat page; and every approval email already sent, whose links are
   absolute and Cloud only. Not posters, verified this pass: the Railway
   `api` service carries no `N8N_*` variable (read 2026-09-06, names only),
   and nothing under `deploy/soul` or `apps/web` references either host.
8. **The repository's own record of the estate.** `services/devon/vault.py`
   carries `N8N_HOST`, a workflow id on every `WEBHOOKS` entry and on all
   48 `WORKFLOWS` entries, and `scripts/estate_reconcile.py` checks them
   against the live instance, so after cutover every one of those claims
   reads DRIFT until the vault is re-registered from `_id_map.json`. The
   same ids live in `.claude/skills/devon-learning-lane/references/ids-and-contracts.md`
   and in the `n8n/devon/*` bodies. Fix: step 6.4.
9. **Double execution** (v1 section 5, unchanged): fourteen workflows run on
   a timer. Never leave one active on both instances; `import` lands
   everything inactive and the switch is per group in one sitting.
10. **The 2,500 cap counts VPS proofs too if they run on Cloud.** Every
    proof in section 6 runs on the VPS by construction; the one Cloud call
    is the negative test, which is a refused request.

## 4. The census, node level

### 4.1 How it was read

Every one of the 64 workflows was read with `get_workflow_details` by two
independent agents with different instructions: one walked every node and
reported each reference by node and field, the other treated the workflow
as text and counted literals. For each workflow the two passes had to agree
on the Cloud host count outside sticky notes, the sub-workflow node count,
the error workflow setting, the credential id set, the data table id set
and the webhook path set; the 4 that disagreed were re-read singly by a
third agent with both answers in hand, and all four turned out to be one
pass packing prose into an id field (the Face's chat trigger has no path
literal; an Airtable table id is not an n8n data table; two table
references by name were annotated). Sixteen readers, four resolvers,
204 tool calls, no writes. 6 workflows could not be read (4.11). The
structured result is `docs/devon/n8n-cloud-census_2026-09-06.json`, names
normalised to drop the estate's em dash separator, ids the join key.

### 4.2 The Cloud host written inside nodes

34 occurrences in 15 workflows outside sticky notes, 26 of them in
14 active workflows. No sticky note carries the host (0 found)
and no workflow anywhere carries `n8n.editforge.online` (0 found).
Every one of these is rewritten by `import --rewrite-host`; the dry run
must print exactly this list for the files being imported.

| Workflow | Id | State | Occurrences | Where (node, field, count) |
|---|---|---|---|---|
| DEVON Action Router, n8n lane (Build 05, half) | `ecLqrxALuLDdF2BN` | active | 5 | Authorise and Resolve Target (code, jsCode) x3; Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON Airtable Row Writer (Build 17) | `ps2S6dWcTIpq5bvr` | active | 2 | Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON Approval Queue | `syRVj0G47mA1b0Xn` | active | 2 | Build Request (code, jsCode) x1; Check Decision (code, jsCode) x1 |
| DEVON Build 12 Ledger Feeder | `6hQD8YhiYzR1FFda` | active | 2 | Feed Learning Webhook (httpRequest, url) x1; Report Learning to Bus (httpRequest, url) x1 |
| DEVON Conscious and Subconscious Runtime (Build 03) | `5Nc9yh6WSqBJ41ok` | active | 2 | Report Exit to Bus (httpRequest, url) x1; Report Entry to Bus (httpRequest, url) x1 |
| DEVON Drive Draft Writer (Build 16) | `J7Ly7riwXEd95D9a` | active | 2 | Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON EditForge Handoff (Build 07) | `OFIhA7zdFv9UoyCv` | active | 2 | Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON Event Bus and Universal Receipts (Build 06) | `Bvy0grTSIyEmPwFA` | active | 1 | Persist to Ledger (httpRequest, url) x1 |
| DEVON Face (Build 15) | `LsmfRFMmI5feINs0` | active | 1 | File Job (httpRequest, url) x1 |
| DEVON Intelligence Router (Build 04) | `xh3EkLmgTDJFhzGH` | active | 2 | Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON Job Driver (Build 14) | `TT4TfFXyH9O7lfdc` | active | 1 | Decide (code, jsCode) x1 |
| DEVON Ledger Janitor | `HKNEDVy7PUKPtsrN` | active | 1 | Cancel via Ledger (httpRequest, url) x1 |
| DEVON Soul Committer (Build 12) | `lANs6wopaK0PkNhN` | active | 1 | Raise Approval Request (httpRequest, url) x1 |
| DEVON Spine Conformance Executor (n8n) | `Oi7o1sTEqhxhOaJL` | active | 2 | Report Entry to Bus (httpRequest, url) x1; Report Exit to Bus (httpRequest, url) x1 |
| DEVON End to End Watch Harness | `ktZ0fnrgxvCNY9xH` | inactive | 8 | A1 Spine (httpRequest, url) x1; A2 Runtime (httpRequest, url) x1; A3 Route (httpRequest, url) x1; A4 Action (httpRequest, url) x1; B1 Spine (httpRequest, url) x1; B2 Runtime (httpRequest, url) x1; B3 Route (httpRequest, url) x1; A5 EditForge (httpRequest, url) x1 |

The three shapes: HTTP Request nodes calling the Event Bus or the ledger
by absolute URL (most rows); a `HOST` constant at the top of a Code node
from which every organ URL is built (the Job Driver's Decide, one line that
rewires eight call targets; the Approval Queue's Build Request and Check
Decision, which build every emailed approve, reject and confirm link); and
the Action Router's allowlist, three absolute executor URLs beside the
executors' workflow ids.

### 4.3 Sub-workflow targets

35 Execute Workflow nodes across 8 workflows, 33 of them in active
workflows. Every one references its target by the `workflowId` parameter
(workflowId parameter), and every target is in the export
(none missing),
so `repoint` rewrites all of them from `_id_map.json`.

| Caller | State | Targets (count of calling nodes) |
|---|---|---|
| DEVON Driver Poll (Build 14) | active | DEVON Job Driver (Build 14) `TT4TfFXyH9O7lfdc` x1 |
| DEVON Intake Former (Build 14) | active | DEVON Job Driver (Build 14) `TT4TfFXyH9O7lfdc` x1 |
| TQO FINAL V5 | inactive | TSWS 01 Post-Production Master `Zbq6gS77PRauqb1I` x2 |
| TSWS 01 Post-Production Master | active | TSWS 00 Render Job (sub-workflow) `o4ctniOsIq2VSfgm` x6; TSWS 04 Detail Recovery (EditForge) `wl6XAUp84fiq50sj` x1; TSWS 03 Visual Assembly `TL6ssgJjJLdvxrUp` x1; TSWS 02 Narration & Sound Bed `v6E12rr1fg1azVHi` x1; TSWS 05 Conform & Grain `QaXpPiVFubsOkDD1` x1 |
| TSWS 02 Narration & Sound Bed | active | TSWS 00 Render Job (sub-workflow) `o4ctniOsIq2VSfgm` x9 |
| TSWS 03 Visual Assembly | active | TSWS 00 Render Job (sub-workflow) `o4ctniOsIq2VSfgm` x3 |
| TSWS 04 Detail Recovery (EditForge) | active | TSWS 00 Render Job (sub-workflow) `o4ctniOsIq2VSfgm` x5 |
| TSWS 05 Conform & Grain | active | TSWS 00 Render Job (sub-workflow) `o4ctniOsIq2VSfgm` x4 |

TSWS 01 carries a draft that differs from its published version in one
node (Build Packaging's Code adds a sixth OS 28 gate in the draft); an
export takes the draft, so decide which one migrates. Its five minute scan
schedule is disabled in both versions and must not be re-enabled by
accident on the VPS.

### 4.4 Error workflow settings

| Error workflow | Named by | Workflows |
|---|---|---|
| OS Error Handler (all pipelines) `rqYmaQh91iCce8DJ` | 13 | DEVON Capture Webhook, DEVON Duplicate Sweep, DEVON Monthly Credential Review, DEVON Notion Buffer Drain, DEVON _To Delete Auto-Purge (30d), DEVON iPhone Inbox Capture, TQO FINAL V5 (inactive), TSWS 00 Render Job (sub-workflow), TSWS 01 Post-Production Master, TSWS 02 Narration & Sound Bed, TSWS 03 Visual Assembly, TSWS 04 Detail Recovery (EditForge), TSWS 05 Conform & Grain |
| DEVON Error Alarm `XDQXwgFkUhYxoEjG` | 12 | DEVON Action Router, n8n lane (Build 05, half), DEVON Airtable Row Writer (Build 17), DEVON Build 12 Ledger Feeder, DEVON Drive Draft Writer (Build 16), DEVON Driver Poll (Build 14), DEVON Face (Build 15), DEVON Heartbeat (Build 13), DEVON Intake Former (Build 14), DEVON Job Driver (Build 14), DEVON Ledger Janitor, DEVON Soul Committer (Build 12), DEVON Weekly Table Backup |

Active workflows with no error workflow set (15): DEVON Approval Queue, DEVON Build 12 Upstream Test, DEVON Capture Nudge, DEVON Conscious and Subconscious Runtime (Build 03), DEVON EditForge Handoff (Build 07), DEVON Error Alarm, DEVON Event Bus and Universal Receipts (Build 06), DEVON Health and Observability Console (Build 10), DEVON Intelligence Router (Build 04), DEVON Live State Ledger (Build 02), DEVON Pipeline Watchdog, DEVON Precedence Guard, DEVON Soul Layer Write-Back, DEVON Spine Conformance Executor (n8n), OS Error Handler (all pipelines).
The two error workflows themselves are in that list by construction; the
rest route a crash nowhere today and did so on Cloud too, so this is a
standing gap rather than a cutover regression. The Error Alarm's mail body
uses `$json.execution.url`, which n8n fills from the instance's own base
URL, so it is expected to name the VPS once that instance's editor base
URL is set; not verified here.

### 4.5 Credentials bound by the active set

11 of the 20 credentials the readable workflows bind are bound by an
active workflow. Create these first, in this order of reach, and write
`creds-map.json` from them. v1 counted 28 credentials on the instance; the
other 17 are bound only by inactive workflows or by nothing.

| Credential | Cloud id | Type | Active workflows | Which |
|---|---|---|---|---|
| Devon Capture Key | `FYRvkRTOcROEYZ9P` | httpHeaderAuth | 20 | DEVON Action Router, n8n lane (Build 05, half), DEVON Airtable Row Writer (Build 17), DEVON Approval Queue, DEVON Build 12 Ledger Feeder, DEVON Build 12 Upstream Test, DEVON Capture Webhook, DEVON Conscious and Subconscious Runtime (Build 03), DEVON Drive Draft Writer (Build 16), DEVON EditForge Handoff (Build 07), DEVON Event Bus and Universal Receipts (Build 06), DEVON Face (Build 15), DEVON Health and Observability Console (Build 10), DEVON Intake Former (Build 14), DEVON Intelligence Router (Build 04), DEVON Job Driver (Build 14), DEVON Ledger Janitor, DEVON Live State Ledger (Build 02), DEVON Soul Committer (Build 12), DEVON Spine Conformance Executor (n8n), DEVON iPhone Inbox Capture |
| SMTP account | `mu7nJRSpkAfkzLdF` | smtp | 15 | DEVON Approval Queue, DEVON Build 12 Ledger Feeder, DEVON Capture Nudge, DEVON Driver Poll (Build 14), DEVON Error Alarm, DEVON Heartbeat (Build 13), DEVON Ledger Janitor, DEVON Monthly Credential Review, DEVON Pipeline Watchdog, DEVON Precedence Guard, DEVON Soul Committer (Build 12), DEVON Soul Layer Write-Back, DEVON Weekly Table Backup, DEVON _To Delete Auto-Purge (30d), OS Error Handler (all pipelines) |
| Airtable Personal Access Token account | `OyuQtrelq7zP2mTy` | airtableTokenApi | 8 | DEVON Airtable Row Writer (Build 17), DEVON Capture Webhook, DEVON Duplicate Sweep, DEVON Monthly Credential Review, DEVON Notion Buffer Drain, DEVON Pipeline Watchdog, DEVON iPhone Inbox Capture, OS Error Handler (all pipelines) |
| Cerebras Cloud | `YTVk8Dq2gYPAmUim` | httpHeaderAuth | 5 | DEVON Drive Draft Writer (Build 16), DEVON Face (Build 15), DEVON Intake Former (Build 14), DEVON Intelligence Router (Build 04), DEVON iPhone Inbox Capture |
| Google Drive account | `WMz320icjnur7rDL` | googleDriveOAuth2Api | 5 | DEVON Drive Draft Writer (Build 16), DEVON Duplicate Sweep, DEVON Precedence Guard, DEVON _To Delete Auto-Purge (30d), DEVON iPhone Inbox Capture |
| Header Auth account 10 | `b9FYEfGUlMiYJCCU` | httpHeaderAuth | 2 | DEVON Notion Buffer Drain, TSWS 00 Render Job (sub-workflow) |
| Notion account | `69GcWnTi2TDh1FAN` | notionApi | 2 | DEVON Capture Nudge, DEVON Soul Layer Write-Back |
| Pinecone account | `3XjKfxbS7zFWEa48` | pineconeApi | 2 | DEVON Soul Committer (Build 12), DEVON Soul Layer Write-Back |
| Devon Soul Service Token | `SFou54MzuKGj3MwV` | httpHeaderAuth | 1 | DEVON Build 12 Upstream Test |
| EditForge MCP Token | `THqWeT7Fd0kiiGSv` | httpHeaderAuth | 1 | DEVON EditForge Handoff (Build 07) |
| Pinecone Api-Key | `FcxUsEaxn5OfXeiO` | httpTemplatedCustomAuth | 1 | DEVON Build 12 Upstream Test |

Of v1's three OAuth blockers only Google Drive is bound by an active
workflow. Gmail and YouTube are bound by inactive workflows only:
- Eleven Labs `4bVgNOG53Ibog4eK` (httpHeaderAuth; S5 Seed: TQO Idea Row, TQO FINAL V5)
- GitHub `WCF2WR8TnuJ9F6QF` (httpHeaderAuth; DEVON Build 08 Credential Probe (throwaway))
- Gmail account `vsTKuAilHmpYCc5L` (gmailOAuth2; DEVON Soul Index Setup (one-shot))
- Header Auth account 3 `TEJIJDPoEhid0aOE` (httpHeaderAuth; TQO FINAL V5)
- Header Auth account 7 `eYTecIAkpa16GAQ6` (httpHeaderAuth; TQO FINAL V5)
- Header Auth account 8 `BT9qHSPFUV4L5hW6` (httpHeaderAuth; TQO FINAL V5)
- Pexel Header Auth `nRIc1n1L6nvZ2jYB` (httpHeaderAuth; S5 Seed: TQO Idea Row, TQO FINAL V5)
- Speechify API `o1Y2okfhRPngvhOl` (httpHeaderAuth; S5 Seed: TQO Idea Row, TQO FINAL V5)
- YouTube account 2 `GA3sbYnmJAAo0AVC` (youTubeOAuth2Api; TQO FINAL V5)

### 4.6 Data tables

Seven table ids are bound by active workflows and need entries in
`tables-map.json`. The two content tables are referenced by name only, by
inactive workflows, so they travel by name. `devon_github_checkpoints` and
`devon_soul_setup` are referenced by no readable workflow.

| Table | Cloud id | Bound by |
|---|---|---|
| devon_state_ledger | `VYyno7pDWmY6uxBz` | 11 node(s) in 10 active workflow(s): DEVON Build 12 Ledger Feeder, DEVON Conscious and Subconscious Runtime (Build 03), DEVON Driver Poll (Build 14), DEVON Face (Build 15), DEVON Health and Observability Console (Build 10), DEVON Heartbeat (Build 13), DEVON Intake Former (Build 14), DEVON Ledger Janitor, DEVON Live State Ledger (Build 02), DEVON Weekly Table Backup |
| approval_queue | `u6wzeN5y9LNxROsN` | 6 node(s) in 3 active workflow(s): DEVON Approval Queue, DEVON Job Driver (Build 14), DEVON Soul Committer (Build 12) |
| devon_build12_feed_log | `QeoV4V4dYXXN8dBR` | 5 node(s) in 4 active workflow(s): DEVON Build 12 Ledger Feeder, DEVON Heartbeat (Build 13), DEVON Soul Committer (Build 12), DEVON Weekly Table Backup |
| devon_soul_commit_log | `U9fnVy19Vc8kvQAw` | 7 node(s) in 3 active workflow(s): DEVON Heartbeat (Build 13), DEVON Soul Committer (Build 12), DEVON Weekly Table Backup |
| devon_heartbeat_log | `Adg1Gd9HML7Q4L3U` | 5 node(s) in 3 active workflow(s): DEVON Face (Build 15), DEVON Heartbeat (Build 13), DEVON Weekly Table Backup |
| devon_driver_log | `9VbICTCa4x4yhWZm` | 3 node(s) in 2 active workflow(s): DEVON Face (Build 15), DEVON Job Driver (Build 14) |
| devon_chat_log | `nwnHN8o2dgHjtk7f` | 2 node(s) in 1 active workflow(s): DEVON Face (Build 15) |
| tqo_content, nco_content | by name | 14 nodes, all in inactive workflows (DT Bootstrap Tables, S5 Seed, TQO FINAL V5) |

TQO FINAL V5 (inactive) addresses tables through 27 expression references
that resolve at run time; nothing to repoint, everything to re-test if it
is ever activated on the VPS.

Row counts on Cloud at 13:55Z on 2026-09-06, for checking the copy in step
6.2: devon_state_ledger 18 (17 terminal, 1 open), devon_driver_log 92,
devon_heartbeat_log 41, devon_build12_feed_log 10, devon_chat_log 8,
tqo_content 2, devon_soul_commit_log 1, devon_soul_setup 1,
devon_github_checkpoints 0, nco_content 0. approval_queue was not read.

### 4.7 Webhook doors

| Path | Method | Auth | Credential | Workflow | State |
|---|---|---|---|---|---|
| devon-action | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Action Router, n8n lane (Build 05, half) | active |
| devon-airtable-row | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Airtable Row Writer (Build 17) | active |
| devon-approve-request | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Approval Queue | active |
| devon-approve-decide | GET | none |  | DEVON Approval Queue | active |
| devon-build12-upstream | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Build 12 Upstream Test | active |
| devon-capture | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Capture Webhook | active |
| devon-runtime | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Conscious and Subconscious Runtime (Build 03) | active |
| devon-drive-draft | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Drive Draft Writer (Build 16) | active |
| devon-editforge | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON EditForge Handoff (Build 07) | active |
| devon-event | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Event Bus and Universal Receipts (Build 06) | active |
| (chat trigger, URL from webhookId 71510ab0-07eb-42d8-9734-c0741b398d49) | POST | n8nUserAuth |  | DEVON Face (Build 15) | active |
| devon-health | GET | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Health and Observability Console (Build 10) | active |
| devon-intake | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Intake Former (Build 14) | active |
| devon-route | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Intelligence Router (Build 04) | active |
| devon-ledger | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Live State Ledger (Build 02) | active |
| devon-spine-n8n | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Spine Conformance Executor (n8n) | active |
| devon-inbox | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON iPhone Inbox Capture | active |
| devon-capture-file | POST | headerAuth | `FYRvkRTOcROEYZ9P` | DEVON Capture Hook | inactive |
| devon-soul-setup-<16 character suffix, elided> | POST | none |  | DEVON Soul Index Setup (one-shot) | inactive |
| run-tqo-pipeline | POST | none |  | TQO FINAL V5 | inactive |
| system-pause | GET | none |  | TQO FINAL V5 | inactive |
| system-resume | GET | none |  | TQO FINAL V5 | inactive |
| gumroad-sale | POST | none |  | TQO FINAL V5 | inactive |
| run-nco-pipeline | POST | none |  | TQO FINAL V5 | inactive |
| run-tqo | GET | none |  | TQO FINAL V5 | inactive |
| run-nco | GET | none |  | TQO FINAL V5 | inactive |

The seven TQO FINAL V5 paths and the Soul Index Setup path take no auth.
They are inactive on Cloud; importing them to the VPS and activating them
there would open unauthenticated doors on the new host, so leave them out
of the first import or leave them inactive.

### 4.8 What starts each active workflow, and what it saves

`saveDataSuccessExecution` is sent in the workflow settings, and the import
read back compares every settings key it sent against what the target
stored, so a dropped `none` shows up as a `READ BACK DIFFERS` line rather
than as saved headers discovered later. Anything on `default` saves
successful runs, headers included.

| Workflow | Id | Saves success | Trigger |
|---|---|---|---|
| DEVON Action Router, n8n lane (Build 05, half) | `ecLqrxALuLDdF2BN` | none | Webhook: POST /webhook/devon-action with header auth (x-devon-key), responds via Respond to Webhook nodes |
| DEVON Airtable Row Writer (Build 17) | `ps2S6dWcTIpq5bvr` | none | Webhook: POST /webhook/devon-airtable-row with header auth (x-devon-key), responds via Respond to Webhook nodes |
| DEVON Approval Queue | `syRVj0G47mA1b0Xn` | none | Two webhooks: POST /webhook/devon-approve-request (header auth x-devon-key) queues a request and emails Tee; GET /webhook/devon-approve-d... |
| DEVON Build 12 Ledger Feeder | `6hQD8YhiYzR1FFda` | default | Schedule trigger 'Daily 02:00': every 1 day at 02:00 instance time (rule days interval 1, triggerAtHour 2, triggerAtMinute 0; no workflow... |
| DEVON Build 12 Upstream Test | `VznESplSFCs8ldph` | none | Webhook: POST /webhook/devon-build12-upstream with header auth (x-devon-key), responds with the first entry JSON of the last node |
| DEVON Capture Nudge | `YHueoBK7TSLdTlfF` | default | Schedule: daily at 08:00 (Schedule Trigger 1.3, interval entry triggerAtHour 8 with no field, node named 'Daily 08:00'); no workflow time... |
| DEVON Capture Webhook | `pPIt2cELH2RVZktS` | none | Webhook: POST /webhook/devon-capture with header auth (x-devon-key), plus a per-poster capture token checked in the body by the Check Tok... |
| DEVON Conscious and Subconscious Runtime (Build 03) | `5Nc9yh6WSqBJ41ok` | none | Webhook: POST /webhook/devon-runtime with header auth (x-devon-key), responds via Respond to Webhook node |
| DEVON Drive Draft Writer (Build 16) | `J7Ly7riwXEd95D9a` | none | Webhook: POST /webhook/devon-drive-draft with header auth (x-devon-key), responds via Respond to Webhook nodes |
| DEVON Driver Poll (Build 14) | `mbIKJk4UuB7V27rP` | default | Schedule trigger node 'Every Hour': rule interval field hours, hoursInterval 1 (every hour). |
| DEVON Duplicate Sweep | `X7OGXWHBx57CIG42` | default | Schedule: daily at 03:00 America/New_York (Schedule Trigger 1.3, field days, triggerAtHour 3, node 'Daily 3am'; workflow timezone America... |
| DEVON EditForge Handoff (Build 07) | `OFIhA7zdFv9UoyCv` | none | Webhook trigger node 'EditForge In (POST)': POST /webhook/devon-editforge, headerAuth, responseMode responseNode. |
| DEVON Error Alarm | `XDQXwgFkUhYxoEjG` | default | Error Trigger node 'On Workflow Failure' (n8n-nodes-base.errorTrigger): runs only when another workflow that names this id in settings.er... |
| DEVON Event Bus and Universal Receipts (Build 06) | `Bvy0grTSIyEmPwFA` | none | Webhook trigger node 'Event In (POST)': POST /webhook/devon-event, headerAuth, responseMode responseNode. |
| DEVON Face (Build 15) | `LsmfRFMmI5feINs0` | default | Chat trigger node 'Chat In' (@n8n/n8n-nodes-langchain.chatTrigger v1.4): public true, mode hostedChat, authentication n8nUserAuth, respon... |
| DEVON Health and Observability Console (Build 10) | `M3H2mVPZJpDyIzrl` | default | Webhook trigger node 'Health In (GET)': GET /webhook/devon-health, headerAuth, responseMode responseNode. |
| DEVON Heartbeat (Build 13) | `dRgTNLod2s8BAcPg` | default | Schedule trigger node 'Every 6 Hours': rule interval field hours, hoursInterval 6 (every 6 hours). |
| DEVON Intake Former (Build 14) | `AEFgXee7IDJarNV7` | none | Webhook trigger node 'Intake In (POST)': POST /webhook/devon-intake, headerAuth, responseMode responseNode. |
| DEVON Intelligence Router (Build 04) | `xh3EkLmgTDJFhzGH` | none | Webhook: POST /webhook/devon-route (node Route In (POST)), header auth, responds via Respond to Webhook node |
| DEVON Job Driver (Build 14) | `TT4TfFXyH9O7lfdc` | none | Execute Workflow Trigger (node When Called, inputSource passthrough); executed by another workflow only, never on its own (sticky note na... |
| DEVON Ledger Janitor | `HKNEDVy7PUKPtsrN` | default | Schedule: daily at 02:30 (node Daily Sweep, daysInterval 1, triggerAtHour 2, triggerAtMinute 30; the workflow sets no timezone, the descr... |
| DEVON Live State Ledger (Build 02) | `z9j2I8h0RnbDKGBO` | none | Webhook: POST /webhook/devon-ledger (node Ledger In (POST)), header auth, responds via Respond to Webhook node |
| DEVON Monthly Credential Review | `yro0wBRGghMjkZhj` | default | Schedule: monthly on the 1st at 08:00 America/New_York (Schedule Trigger 1.3, field months, triggerAtDayOfMonth 1, triggerAtHour 8, node... |
| DEVON Notion Buffer Drain | `X3sKmPj6yHJu4xWu` | default | Schedule: daily at 07:00 America/New_York (Schedule Trigger 1.3, field days, triggerAtHour 7, node 'Daily 7am'; workflow timezone America... |
| DEVON Pipeline Watchdog | `wndFo6uJCqVuINaV` | default | Schedule: every 4 hours (Schedule Trigger 1.3, field hours, hoursInterval 4, node named 'Every 4 Hours'); no workflow timezone set. |
| DEVON Precedence Guard | `W5rlpAt6hsJAExU6` | default | Schedule: daily at 07:00 (Schedule Trigger 1.3, interval entry triggerAtHour 7 with no field, node named 'Daily 07:00'); no workflow time... |
| DEVON Soul Committer (Build 12) | `lANs6wopaK0PkNhN` | none | Schedule: every hour (node Every Hour, hoursInterval 1; changed from every 15 minutes on 2026-09-06 per sticky note) |
| DEVON Soul Layer Write-Back | `edIJx7Q3FXTawg9J` | default | Notion Trigger (n8n-nodes-base.notionTrigger 1.1) polling every 15 minutes on dataSourceId a5bcfbf5-ce1d-493b-9992-a11bc2a03dc4; the even... |
| DEVON Spine Conformance Executor (n8n) | `Oi7o1sTEqhxhOaJL` | none | Webhook: POST /webhook/devon-spine-n8n (node Envelope In (POST)), header auth, responds via Respond to Webhook node |
| DEVON Weekly Table Backup | `qCfGZ1CwmpK9vOta` | default | Schedule: weekly on Sunday at 03:10 (node Weekly Backup, weeksInterval 1, triggerAtDay [0], triggerAtHour 3, triggerAtMinute 10; the work... |
| DEVON _To Delete Auto-Purge (30d) | `0soYvqnSKYlFn3gr` | default | Schedule: weekly on Sunday at 10:00 America/New_York (Schedule Trigger 1.3, field weeks, triggerAtDay [0], triggerAtHour 10, node 'Sunday... |
| DEVON iPhone Inbox Capture | `5s6CwWWelffqszQe` | none | Webhook: POST /webhook/devon-inbox (node Capture In (POST), n8n-nodes-base.webhook v2.1), authentication headerAuth via credential FYRvkR... |
| OS Error Handler (all pipelines) | `rqYmaQh91iCce8DJ` | default | Error Trigger only (node 'Error Trigger', n8n-nodes-base.errorTrigger): fires when a workflow whose settings.errorWorkflow names this id... |
| TSWS 00 Render Job (sub-workflow) | `o4ctniOsIq2VSfgm` | default | Executed by another workflow only: Execute Workflow Trigger 'When Called' (n8n-nodes-base.executeWorkflowTrigger v1, no declared inputs,... |
| TSWS 01 Post-Production Master | `Zbq6gS77PRauqb1I` | default | Three trigger nodes: Schedule Trigger 'Scan Every 5 Minutes' (rule: every 5 minutes) which is disabled=true in both the draft and the pub... |
| TSWS 02 Narration & Sound Bed | `v6E12rr1fg1azVHi` | default | Executed by another workflow only: Execute Workflow Trigger 'Receive Audio Job' (v1, no declared inputs), called by TSWS 01 node 'Narrati... |
| TSWS 03 Visual Assembly | `TL6ssgJjJLdvxrUp` | default | Executed by another workflow only: Execute Workflow Trigger 'Receive Assembly Job' (v1, no declared inputs), called by TSWS 01 node 'Visu... |
| TSWS 04 Detail Recovery (EditForge) | `wl6XAUp84fiq50sj` | default | Executed by another workflow only: Execute Workflow Trigger 'Receive Recovery Job' (v1, no declared inputs), called by TSWS 01 node 'Deta... |
| TSWS 05 Conform & Grain | `QaXpPiVFubsOkDD1` | default | Executed by another workflow only: Execute Workflow Trigger 'Receive Conform Job' (v1, no declared inputs), called by TSWS 01 node 'Confo... |

Three things in that table matter for the burn and for the cutover. The
Soul Layer Write-Back is a Notion polling trigger every 15 minutes; a
polling trigger only starts an execution when it finds new items, and its
last-seen state lives in workflow static data, which an export does not
carry, so its first poll on the VPS may re-ship or skip entries and must be
watched. The TSWS 00 Wait node resumes through a webhook, so the VPS needs
a correct `WEBHOOK_URL`. The Job Driver, TSWS 00 and TSWS 02 to 05 have
no trigger of their own and only run when called.

### 4.9 Ids and hosts written inside Code nodes, which the tool does not rewrite

- Action Router, `Authorise and Resolve Target`: the allowlist carries
  the three executors' Cloud workflow ids beside their URLs. The URL is
  rewritten by `--rewrite-host`; the id passes through as
  `target_workflow` and the Job Driver only prints it in its log line, so
  it is cosmetic. Update it by hand from `_id_map.json` anyway, because a
  log that names a Cloud id on the VPS will mislead the next reader.
- Airtable Row Writer, Drive Draft Writer and Spine use `$workflow.id` at
  run time for the single flight mark and to stamp `execution.workflow_id`.
  That is the runtime's own id on either instance, so it stays consistent
  after cutover provided no non-terminal row carries a Cloud id, which the
  drain in step 6.1 guarantees.
- Job Driver `Decide`, Approval Queue `Build Request` and `Check Decision`:
  the `HOST` constants, rewritten by `--rewrite-host` (4.2).
- Error Alarm: a name map from workflow ids to names in its Code, cosmetic
  for the email subject; Health Console: a workflow id in prose only.
- TSWS 00: both HTTP Request nodes still carry the placeholder
  `RENDER-WORKER-URL-HERE`, and its own sticky note says the smoke test
  has never succeeded. The TSWS chain cannot run as exported on either
  host; on the VPS the worker URL can move into an environment variable,
  which the Cloud plan denied.

### 4.10 External hosts, unchanged by the move

| Host | Active workflows | Which |
|---|---|---|
| RENDER-WORKER-URL-HERE | 1 | TSWS 00 Render Job (sub-workflow) |
| airtable.com | 1 | DEVON Airtable Row Writer (Build 17) |
| api.airtable.com | 6 | DEVON Airtable Row Writer (Build 17), DEVON Duplicate Sweep, DEVON Monthly Credential Review, DEVON Notion Buffer Drain, DEVON Pipeline Watchdog, OS Error Handler (all pipelines) |
| api.cerebras.ai | 5 | DEVON Drive Draft Writer (Build 16), DEVON Face (Build 15), DEVON Intake Former (Build 14), DEVON Intelligence Router (Build 04), DEVON iPhone Inbox Capture |
| api.notion.com | 3 | DEVON Capture Nudge, DEVON Notion Buffer Drain, DEVON Soul Layer Write-Back |
| devon-soul-jw37oa2.svc.aped-4627-b74a.pinecone.io | 1 | DEVON Soul Committer (Build 12) |
| devon-soul.vercel.app | 2 | DEVON Build 12 Upstream Test, DEVON Intelligence Router (Build 04) |
| devon-subconscious-jw37oa2.svc.aped-4627-b74a.pinecone.io | 1 | DEVON Build 12 Upstream Test |
| docs.google.com | 1 | DEVON Drive Draft Writer (Build 16) |
| drive.google.com | 1 | DEVON iPhone Inbox Capture |
| editforge.vercel.app | 1 | DEVON EditForge Handoff (Build 07) |
| render.example.com | 1 | TSWS 00 Render Job (sub-workflow) |
| tee-soul-layer-jw37oa2.svc.aped-4627-b74a.pinecone.io | 1 | DEVON Soul Layer Write-Back |
| www.googleapis.com | 3 | DEVON Duplicate Sweep, DEVON Precedence Guard, DEVON _To Delete Auto-Purge (30d) |

None of these change. The Pinecone index hosts, devon-soul and editforge
on Vercel, Cerebras, Notion, Airtable and Google keep answering the same
credentials from the new instance.

### 4.11 Not read

MCP access is off on these six, all inactive, all old TQO versions; the
public API export in step 1 may still read them, and either way they are
not in the recommended import set:
- TQO - ORCHESTRATOR `ljrWDpRVgK8gxQwH`
- TQO FINAL V1 (80Um) `80Um0VPtbVQIO47n`
- TQO FINAL V1 (o09u) `o09uEM6O2JedxpF5`
- TQO FINAL V1 FIXED 2 `hnVhgvRJOLVPfXHI`
- TQO FINAL V2 `k5B5dcewspDpNSHO`
- TQO FINAL V4 `WDFEnVIziUmGA3Pj`

The four disagreements the resolver settled, for the record:
- DEVON Face (Build 15): webhook paths: reader [webhookId 71510ab0-07eb-42d8-9734-c0741b398d49 (chat trigger carries no path parameter)], counter []
- DEVON iPhone Inbox Capture: data table ids: reader [tbl4ziFRbl5mnUcKc], counter []
- DT Bootstrap Tables (TQO Migration S1a): data table ids: reader [nco_content,nco_content (dataTableId mode name),tqo_content,tqo_content (dataTableId mode name)], counter [nco_content,tqo_content]
- S5 Seed: TQO Idea Row: data table ids: reader [tqo_content (dataTableId mode name)], counter [tqo_content]

## 5. The runbook, in order, for Tee's hands

Everything below runs from a machine with egress to both hosts, which this
sandbox is not. Keys stay in the shell environment and are never written
anywhere. Nothing before step 6 changes what Cloud does.

**Step 0, before anything moves.**

1. Read the n8n Cloud usage page: executions used this cycle and the date
   the cycle resets. Write both into the status block of this document.
2. On the VPS, open n8n and note the version (Settings, then the version at
   the foot of the page). Data tables and the Chat Trigger are recent
   features; a VPS version older than Cloud's may lack a node the export
   uses, and the import will accept the workflow and fail at run time.
   Cloud's version is not readable through the MCP connector; read it in the
   Cloud UI the same way and compare.
3. On the VPS, list the data tables. Expect the nine named in v1 section 2
   with the 09-03 rows still in them. Create `devon_driver_log` and
   `devon_chat_log` from `docs/devon/n8n-datatable-schemas.json`, column
   order and types exactly. Then write `tables-map.json`:
   `{"<Cloud table id>": {"id": "<VPS table id>", "name": "<name>"}}` for all
   eleven, Cloud ids from the schema file, VPS ids from the VPS table pages.
4. On the VPS, create an API key (Settings, n8n API) with workflow create,
   read and update. On Cloud, create one with workflow list and read. Export
   both into the shell only.
5. Register the VPS OAuth redirect URI in Google Cloud per v1 (the callback
   section). 4.5 shows Google Drive is the only OAuth credential an active
   workflow binds, so one consent flow, not three.
6. Set the VPS instance's environment before anything is imported, because
   three things in 4.8 and 4.4 depend on it and none of them fails loudly:
   `WEBHOOK_URL` and `N8N_EDITOR_BASE_URL` to `https://n8n.editforge.online`
   (the TSWS 00 Wait node resumes through a webhook, the Error Alarm's mail
   links use the execution URL, every webhook URL is built from it), and
   `GENERIC_TIMEZONE` to the zone Cloud runs on, read from the Cloud
   instance settings page, because several schedules in 4.8 set no
   workflow timezone and run on the instance's. Restart n8n after setting
   them and confirm on any credential page that the OAuth redirect URL n8n
   prints carries the VPS host.
7. Make sure Tee has a login on the VPS instance. The Face's chat door is
   `n8nUserAuth` (4.7): without a VPS user it does not open.
8. Take a snapshot of the VPS before step 3, the one destructive step:
   a Hostinger VPS snapshot from the panel, or `docker exec` into the n8n
   container and export its database, whichever Tee can restore from
   without help. Name it in this document with the time.

**Step 1, export and inspect.**

    export N8N_SOURCE_URL=https://thequietoperator.app.n8n.cloud
    export N8N_SOURCE_KEY=...        # workflow:list, workflow:read
    python3 scripts/n8n_migrate.py export ./n8n-export
    python3 scripts/n8n_migrate.py inspect ./n8n-export > inspect.txt

Read `inspect.txt` against section 4. The counts must agree: hosts marked
MOVES by workflow and node, sub-workflow targets, error workflow settings,
credentials with types, data tables, webhook paths. A line in `inspect.txt`
that section 4 does not carry is a change since 2026-09-06; a line in
section 4 that `inspect.txt` lacks is a workflow the export missed. Six of
the inactive TQO workflows were unreadable through the MCP connector in
this pass (section 4 lists them); the public API export may read them, and
either way they are inactive and old.

Decide what to import. `import` creates every `*.json` in the directory, so
move the files you do not want into a subfolder first. Recommended set: the
39 active workflows plus nothing else on the first pass; every one-shot
utility and every retired TQO version can be imported later if wanted.

**Step 2, credentials on the VPS.** Create the ones section 4 lists for the
active set, same names, and write `creds-map.json`:
`{"<Cloud credential id>": {"id": "<VPS credential id>", "name": "<name>"}}`.
The VPS credential id is in the URL of the credential's page. Header
credentials take the same secret values; the Devon Capture Key value is the
one rotated on 2026-09-06 and known only to Tee.

**Step 3, wipe the stale rows.** On the VPS, delete every row in every one
of the nine copied tables. `approval_queue` stays empty from here on. This
is hazard 1 and it is the one step in this runbook that destroys data; the
data it destroys is a 2026-09-03 snapshot that Cloud has superseded.

**Step 4, import with the host rewritten, then repoint.**

    export N8N_TARGET_URL=https://n8n.editforge.online
    export N8N_TARGET_KEY=...        # workflow:create, read, update
    python3 scripts/n8n_migrate.py import ./n8n-export \
        --rewrite-host thequietoperator.app.n8n.cloud=n8n.editforge.online

That is the dry run. It prints the rewrite plan per node and creates
nothing; its "in nodes" count must equal the 4.2 total for the files being
imported (26 for the active set) and its sticky note count must be 0,
because inspect and import now count with the same matcher. Then the same
command with `--confirm`, which creates everything INACTIVE, reads each
workflow back and compares node names, webhook ids, the settings it sent
and the absence of the Cloud host (a `READ BACK DIFFERS` line and exit 2
if anything was silently dropped), and writes `./n8n-export/_id_map.json`
after every creation, so a run that dies half way leaves a map and a re-run
skips what exists. If the VPS already holds workflows, the tool checks them
first: a webhook path or a workflow name that this run would duplicate is
a refusal with the list, whatever flags are set; an unrelated population
is a refusal that says so and asks for `--allow-existing`. A 400 naming a
`settings.` key is the target's API refusing a key Cloud exports carry
(`callerPolicy` and `availableInMCP` are the likely two, unverified here);
the tool drops that key, retries, prints it and records it in the map, and
a dropped `callerPolicy` has to be set again by hand in the editor because
it governs who may call a sub-workflow.

    python3 scripts/n8n_migrate.py repoint ./n8n-export \
        --credential-map creds-map.json --table-map tables-map.json

Dry run again. Read every `STILL AT THE SOURCE` line: with both maps
complete the expected remainder is empty, because everything the tool
rewrites (Execute Workflow targets, error workflow settings, credential
ids, data table ids) is in those maps; any line printed is a map entry to
add or a reference to fix by hand. The ids inside Code nodes (4.9) are not
in this tool's reach and never appear here. Then `--confirm`, which writes
each workflow back, reads it again and reports any rewrite that did not
stick. The tool exits 2 while anything still points at Cloud and 0 when
nothing does, and a second run is 0 on a correct estate: a reference that
already carries a target id is reported as already done, not as dangling.

**Step 5, the hand edits the tool cannot make.** The Code node workflow ids
in 4.9, each against `_id_map.json`. The Face's chat trigger URL is derived
from its `webhookId`; whether the public API keeps that id on create is one
of the things the import read back checks (a `READ BACK DIFFERS` line names
it), and if it was reissued the new URL is on the Chat In node. The error
workflow setting on any workflow that named a Cloud id the map lacks.
Workflow tags are not carried by the create call (`CREATE_FIELDS`); the
census shows no tags on the estate, so nothing is lost today.

**Step 6, drain, copy, switch.**

1. Drain. One Cloud job is open (`01M1S84TTY4DMC4D0VCHTJB672`, section 2);
   it cancels itself on the first poll after 2026-09-08T16:59Z. From then
   the Cloud ledger is all terminal. Do not file new Cloud jobs after that
   point.
2. Copy rows, terminal only, after the drain and after step 3: the ledger,
   the feed log, the commit log, the heartbeat log, the checkpoints, the
   soul setup, the driver log, the chat log, and the two content tables.
   `approval_queue` never. The counts on Cloud at 13:55Z on 2026-09-06 are
   in 4.6 so the copy can be checked by count. There is no tool for this
   step in the repository and n8n's public API has no data table endpoint
   this pass could verify. The 2026-09-03 job did it through a Claude
   session holding an n8n MCP connector for each host, reading rows from
   Cloud with `get_data_table_rows` and writing them to the VPS with
   `add_data_table_rows`; whether the VPS instance exposes MCP access is
   unverified (section 7), and if it does not, the Weekly Table Backup's
   CSV email covers four of the ten tables and the other six are a hand
   copy from the Cloud table pages, small at today's counts (the driver
   log at 92 rows is the largest).
3. Switch, one group per sitting, Cloud off first then VPS on, never both:
   (a) the DEVON job lane: Live State Ledger, Event Bus, Spine, Runtime,
   Intelligence Router, Action Router, the three executors, EditForge
   Handoff, Intake Former, Job Driver, Driver Poll, Approval Queue, Error
   Alarm, Face, Health Console; (b) the learning lane: Ledger Feeder, Build
   12 Upstream, Soul Committer, Ledger Janitor, Weekly Table Backup,
   Heartbeat; (c) capture: Capture Webhook, iPhone Inbox Capture, Notion
   Buffer Drain, Capture Nudge; (d) the sweeps: Precedence Guard, Duplicate
   Sweep, To Delete Auto-Purge, Monthly Credential Review, Pipeline
   Watchdog, Soul Layer Write-Back; (e) the TSWS chain and the OS Error
   Handler. Group (a) goes first because it is the one that burns. Rolling
   a group back is the same sitting in reverse: VPS copies off, Cloud twins
   on, and nothing else, because the tables are copies and the posters have
   not moved yet.
4. Repoint the repository and the outside holders. `services/devon/vault.py`
   and the `deploy/soul` copy byte identical: `N8N_HOST`, every `WEBHOOKS`
   workflow id, every `WORKFLOWS` id, from `_id_map.json`, each with the
   dated note the write-back doctrine asks for. The skills' ids reference.
   The bodies under `n8n/devon/` where a host or id is a literal. Then
   `python3 scripts/estate_reconcile.py snapshot` against the VPS and
   `check --strict`. Then the posters in hazard 7, one at a time, each
   proven by a 200 from the VPS.
5. Keep Cloud reachable, with every workflow inactive, until 72 hours after
   the last approval card it sent, then one more weekly backup cycle, then
   downgrade or close the Cloud plan. The wall goes with it.

## 6. Proofs, before any external poster moves

All on the VPS unless marked. Each is a receipt, not a claim.

1. A capture from the phone to `/webhook/devon-capture` on the VPS returns
   200 and the row lands in Airtable Thread Receipts.
2. A level 0 job with blast radius none and `auto_verify` posted to
   `/webhook/devon-intake` on the VPS runs RECEIVED to COMPLETED in one
   pass, and the VPS ledger row and driver log row read back.
3. A gated job raises a card, the email arrives through SMTP, the approve
   link opens on the phone at the VPS host, the confirm tap lands, and the
   next VPS Driver Poll carries the job to a verification card. This is the
   one proof that exercises the `HOST` constant in the Approval Queue.
4. Negative, on Cloud: the same intake POST to the Cloud host with the lane
   inactive is refused (a webhook on an inactive workflow answers 404). A
   200 there means a Cloud twin is still live and hazard 9 is open.
5. `estate_reconcile.py check --strict` against the VPS snapshot reports no
   DRIFT and no UNVERIFIED.
6. The Heartbeat's next beat row on the VPS names the VPS host in its
   vitals, and the Ledger Feeder's next daily run feeds nothing new and
   errors nothing.

## 7. What is unverified in this document

- Everything about the VPS: which tables and rows it holds, its n8n version,
  whether Data Tables and the Chat Trigger exist there, whether the MCP
  access used on Cloud is available on it. Tee's statement and the 09-03
  ledger job are the sources, and they disagreed with the 08-31 record.
- What n8n Cloud counts toward the 2,500 and when the cycle resets. The
  usage page settles both.
- The six TQO workflows the MCP connector could not read (section 4).
- The tool's three network paths (`export`, `import`, `repoint`) have not
  run against a real instance from this sandbox, because it has no egress
  to either host. They are covered by tests against a fake target that
  answers the same four API routes; the first real run is Tee's, the dry
  runs exist so that run can be read before anything is written, and both
  write paths read back what they wrote and say when the target kept less
  than it was sent. What the public API keeps (webhook ids, every settings
  key) is therefore measured on the first run rather than asserted here.

## 8. Records moved with this pass

A fresh critic graded the first version of this pass PASS-WITH-CONDITIONS
(idempotency 2, correctness 3): repoint red on a second run, blank map
values written as empty ids, no map after a partial import, three sentences
in this runbook describing the tool wrongly, and no read back after a
write. All of those are closed above and in the tool; the second pass is
recorded in the PR.


- `scripts/n8n_migrate.py`: host census in `inspect`, `--rewrite-host` on
  `import`, the new `repoint` subcommand; after the first critic pass, one
  matcher for inspect and import, an id map written after every creation
  and honoured on re-run, collisions by path and by name checked before the
  populated target refusal, a same-host guard from `_export_meta.json`,
  settings keys the target refuses dropped one at a time and named, blank
  map values refused, `repoint` idempotent with a read back after every
  PUT, and a read back after every create. `test_n8n_migrate.py`: thirty
  three tests.
- `docs/devon/n8n-datatable-schemas.json`: re-read live, eleven tables.
- `docs/devon/SYS_OPS_n8n-cloud-to-vps-migration_v1_2026-08-31.md`: amended
  in place, dated (status block, the table count, section 2).
- This document.
