---
title: DEVON Autonomy Driver and Face (Builds 14 and 15)
type: SYS_OPS
version: 1
date: 2026-09-05
area: Systems
status: live-on-cloud-human-gated-pass-with-conditions
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: 70a0a12
branch: claude/new-session-2f2yu2
supersedes: none
---

# DEVON Autonomy Driver and Face (Builds 14 and 15) v1

## Verdict in one paragraph

DEVON now runs a job on his own from capture to completion, and stops at
every gate a human owns. Before this build the organism had every organ it
needed (spine, ledger, runtime, router, action router, event bus, EditForge
handoff, approval queue) and nothing that walked a job between them: every
hop needed a hand. Build 14 adds the three workflows that close that gap and
proves them live on n8n Cloud. A level 0 job with blast radius none went
RECEIVED to COMPLETED in one pass of 14 seconds through six organ hops with
no human card (intent 01M1S81K3WDD0JSKY6KPAY43K1). A level 2 job with a
reversible write stopped at WAITING_APPROVAL with an approval card in Tee's
inbox (intent 01M1S8CZ37X87B6281WPQA68B1, card REQ-20260905-TwrTv3). Free
text is now tagged into a full envelope by Cerebras and validated against the
closed vocabularies. The hourly poll resumed both open jobs, adopted an orphan
card by its evidence marker, and sent nothing because nothing moved. Three
organs that had been failing silent on the dead Gmail credential (Approval
Queue, Heartbeat, Error Alarm) had SMTP fixes sitting in unpublished drafts;
those drafts are now live, and that is a ruling Tee can reverse. What DEVON
still cannot do on his own is real work beyond the spine echo: the Action
Router allowlist carries one executor, and EditForge voice and avatar renders
wait on a host env file only a human can edit. Those four human runbooks are
in section 8.

Later the same day, on Tee's two asks ("Devon needs a face" and "enrich him
as much as possible with Cerebras"), Build 15 added the Face: an n8n hosted
chat behind n8n login where DEVON answers from the live ledger and files jobs
through the same intake (workflow LsmfRFMmI5feINs0). Asked where things
stood, he listed the three waiting jobs by id and expiry in 3 seconds
(execution 5733). Asked what he would do without filing, he drafted the
outline and returned a dry run envelope with a plan and a recommendation,
then waited for a plain yes (execution 5734). Cerebras now also writes a
brief on every job at intake (plan, done when, risks, proceed or hold with a
reason), the brief rides in the envelope and in the approval card, and a hold
raises the level so the router sends the job to Tee.

Later still, Tee approved a card from the phone. The approval reached the
ledger and the next poll moved the job to AUTHORIZED, where the Action Router
refused it because no allowlisted executor may carry a reversible write. That
refusal surfaced a third silent defect, an empty reply where a reason
belonged, repaired the same day. The job now parks with its reason on record
until the grant decays. The approve hop is proven from the phone; the execute
hop waits on a real executor. Tee then ruled for that executor. It is built
and validated as a Drive draft writer; its creation on n8n Cloud was held by
the session's permission gate and waits on his word.

## 1. The gap this build closes

The organs existed and each one was proven in isolation on 2026-08-23 and
2026-08-24. Nothing formed a job from a capture. Nothing carried an envelope
from one organ to the next. Nothing bridged an approval card decision back
into the ledger as APPROVAL_GRANTED. Nothing observed an EditForge job to
completion. Nothing owned the VERIFYING to COMPLETED transition, so no job
could ever finish without a session driving it by hand. The Feeder, the
Committer, the Janitor and the Heartbeat all watched a ledger nothing wrote
to on its own.

## 2. What was built

All four live in the n8n Cloud project rM0TNTE2fNXErglU, header auth on
the one webhook, n8n login on the chat, crash alerting through the DEVON Error Alarm, 300 second
execution timeout. Registered in `services/devon/vault.py` (both copies) and
in `.claude/skills/devon-learning-lane/references/ids-and-contracts.md`.

| Thing | Id | Role |
|---|---|---|
| Intake Former workflow | `AEFgXee7IDJarNV7` | the mouth: POST `devon-intake` becomes one v1 envelope at RECEIVED and is driven at once |
| Job Driver workflow | `TT4TfFXyH9O7lfdc` | sub-workflow: one pass advances one job through the organs as far as it legally can |
| Driver Poll workflow | `mbIKJk4UuB7V27rP` | hourly: resumes every open job, digest only when something moved or refused |
| devon_driver_log table | `9VbICTCa4x4yhWZm` | one row per driver pass |

### The Intake Former

POST `https://thequietoperator.app.n8n.cloud/webhook/devon-intake` with the
`x-devon-key` header (credential Devon Capture Key FYRvkRTOcROEYZ9P). Two
body shapes.

Free text: `{"text": "Devon, draft the checklist for TQO episode 12"}`.
Cerebras (gpt-oss-120b, credential YTVk8Dq2gYPAmUim) proposes area, summary,
blast_radius and level. Every value is checked against the closed vocabulary
in the envelope schema and discarded if it does not match. No Area means the
job is refused with the reason, never filed with a guess. No blast radius
defaults to reversible_write, which routes the job to Tee. The model is a
proposer; the vocabularies are the authority.

Structured: `summary`, `area`, `blast_radius`, `level`, `actor` (type and
source), `payload` (an `editforge` block with kind, prompt, provider, or
`auto_verify: true`), `idempotency_key`, `dry_run`. A dry run returns the
formed envelope and drives nothing.

The response is a receipt naming where the job stopped: COMPLETED,
WAITING_APPROVAL with the card id, EXECUTING, or a refusal with its reason.
HTTP 400 on refusal, 200 otherwise.

### The Job Driver

A sub-workflow with no trigger of its own. It takes one envelope and loops
Decide, Call Organ, Absorb until the job stops at a gate or the pass reaches
eight steps. Every hop is a real HTTP call to a production organ webhook; the
driver never writes the ledger directly. State changes it owns (approval
granted, verification passed, cancelled, failed) go through the Event Bus as
typed events, so the ledger's transition guard applies to the driver exactly
as it applies to everything else.

| Envelope state | What the driver does |
|---|---|
| RECEIVED | spine, to UNDERSTANDING |
| UNDERSTANDING | runtime, to PLANNING |
| PLANNING | router, to AUTHORIZED or WAITING_APPROVAL or ESCALATED |
| WAITING_APPROVAL, ESCALATED | raise one approval card, record its id on the envelope, then stop and wait; approved means APPROVAL_GRANTED and AUTHORIZED with a 24 hour grant; rejected, expired, or absent past 96 hours means CANCELLED with a receipt |
| AUTHORIZED | action router with spine.echo, to EXECUTING |
| EXECUTING | EditForge handoff when the payload carries an editforge block, otherwise spine, to VERIFYING |
| VERIFYING | auto verify only when blast radius is none, no artifacts and no EditForge job: COMPLETED with human_watched false and method auto_no_artifact; otherwise raise a verification card and wait; Tee approving writes VERIFICATION_PASSED, COMPLETED and human_watched true; rejected or expired writes FAILED |
| terminal states | nothing |

Safety properties, each one enforced by data shape rather than by
instruction:

- A 200 is a claim. Absorb accepts an organ answer only when the body carries
  an envelope with this job's intent_id; anything else stops the pass and is
  logged as refused.
- The approval_queue table carries plaintext decision tokens. The driver reads
  it only by the evidence marker `intent <id>; card approval` or `card
  verify`, copies only request_id, status, requested_at, decided_at and
  expires_at into its memory, and its execution data persistence is off, the
  same rule the Soul Committer follows. A session must never read that table.
- Cards are adopted, never duplicated. If a card POST fails after the queue
  stored the row, the next pass finds the row by marker and records it. This
  path was exercised live (section 4, pass 5705).
- human_watched is never claimed by a machine. Only a verification card that
  Tee approved sets it true.
- One row per pass in devon_driver_log, so a job's history is readable without
  execution data.

### The Driver Poll

Every hour it reads the ledger, selects rows that are not terminal and sit in
RECEIVED through VERIFYING (never FAILED or BLOCKED, which wait for a human or
the Janitor), skips rows written in the last three minutes so an intake pass
in flight is never driven twice, and hands each job to the Job Driver one at
a time. It emails a digest only when a job moved or an organ refused. Hourly
because n8n Cloud counts every execution and the cutover to the VPS is on a
clock; intake drives new jobs eagerly, so the poll only exists to resume jobs
after Tee decides a card or a render finishes.

### The Cerebras brief (Build 15 enrichment)

After tagging, the Intake Former asks Cerebras gpt-oss-120b for a brief:
plan (3 to 5 imperative steps), done_when (2 to 4 statements a human can
check), risks (0 to 3), recommendation (proceed or hold) and reason. Every
value is validated (arrays of strings, capped, recommendation coerced to hold
unless it is exactly proceed) and attached as `intent.payload.brief`. The
Job Driver's approval card now carries the plan, the done-when checks, the
risks and the recommendation, and a verification card carries the done-when
checks, so Tee reads what DEVON intends before he taps. A hold
recommendation raises `intent.level` to at least 2, which the router turns
into WAITING_APPROVAL: DEVON's own doubt gates a job, never releases one. A
missing or unparseable brief is noted and the job proceeds without one; the
brief is advice, not a gate that can fail open or closed.

### The Face (Build 15)

Workflow `LsmfRFMmI5feINs0`, fifteen nodes, hosted chat trigger behind n8n
user auth (Tee is logged in on the phone; there is no open door and no new
credential). Each turn reads this session's last sixteen rows from
`devon_chat_log` (`nwnHN8o2dgHjtk7f`), the 25 most recently updated ledger
rows, the last eight driver passes and the last heartbeat, and builds one
Cerebras request with a system prompt that carries DEVON's voice rules (no
hype, no dashes, recommend then hand back, never claim a receipt the context
does not carry), the state machine, the vocabularies, and a context block of
ids he may cite. Cerebras answers as JSON: reply, action (none, file_job,
dry_run) and job. A malformed answer becomes a plain reply with action none,
so a formatting slip can never file a job. file_job and dry_run POST to
`devon-intake` with the capture key, actor type tee, source devon_face_chat,
so the same tags, brief, router, cards and ledger apply as for any poster;
the intake receipt (where the job stopped, the card id, the plan) is appended
to the reply. Both turns are written to the chat log before the reply node,
with continueRegularOutput on the insert so a failed write never eats a
reply. The Face never reads approval_queue and never decides a card. The
Cerebras credential is header auth, which the n8n chat model subnodes cannot
use, so the language lane is an HTTP Request rather than an Agent node; that
is a deliberate departure from the n8n chatbot guidance and the reason is in
the workflow's sticky note.

The Face has a visible face as well as a voice. `docs/devon/assets/devon-mark.svg`
is an original emblem, owned outright: charcoal ground, a quiet green lens
with a single pulse, a D in the centre. No stock, no rented persona, no
synthetic human. It is inlined into the chat page as a data URI through the
trigger's custom CSS with the house palette (charcoal header, light bot
bubbles, green user bubbles), published as Face version af7db714. The mark
was rendered at 192, 64 and 32 pixels and in a mock of the n8n chat layout
before publishing; the live page sits behind n8n login, so the last look is
Tee's on the phone. A human looking face for DEVON is a ruling for Tee under
the owned identity rule: the only likeness lane the studio owns is Tee's own
avatar and voice, and DEVON borrowing them would blur who is speaking. The
recommendation is to keep the mark.

## 3. Measured receipts (n8n Cloud, 2026-09-05, all times UTC)

| Execution | What | Result |
|---|---|---|
| 5629 (intake) | level 0, blast none, auto_verify, idempotency build14-proof-level0-20260905 | success in 13.7s; intent 01M1S81K3WDD0JSKY6KPAY43K1 RECEIVED to COMPLETED, 6 steps, no card; ledger row id 10 terminal true, verification passed by auto_no_artifact, receipt outcome completed, 20 trace events; devon_driver_log row 1 |
| 5663 (intake) | level 2, reversible_write, idempotency build14-proof-gated-20260905 | success; intent 01M1S84TTY4DMC4D0VCHTJB672 stopped at WAITING_APPROVAL with outcome card_post_failed, http 200 with a null body. Approval Queue execution 5681 errored: its live version still emailed through Gmail credential vsTKuAilHmpYCc5L, which had gone invalid, and Store Pending had already written the row. Root cause, not the driver |
| 5667 (intake) | free text, dry_run | refused: Cerebras unavailable, HTTP no response, in 0.18s. Root cause: the tagging prompt described the reply shape with a quoted JSON literal and the quotes lost their escaping on import, so the expression failed before any request left |
| 5684 (intake) | same free text, dry_run, after the prompt fix | success in 2.9s; envelope formed at RECEIVED with area TQO, level 1, blast_radius reversible_write, summary rewritten as one imperative sentence, all four tags by Cerebras, nothing filed |
| 5685 (intake) | level 2, reversible_write, idempotency build14-proof-gated-b-20260905, after the Approval Queue republish | success in 7.8s; intent 01M1S8CZ37X87B6281WPQA68B1 at WAITING_APPROVAL; approval card REQ-20260905-TwrTv3 raised, expires 2026-09-08T17:03:37Z; bus APPROVAL_REQUESTED persisted (ledger update_same_state); Approval Queue execution 5702 success, SMTP send included; ledger row id 12 carries approval.queue_row_id |
| 5705 (poll, run by hand) | hourly pass over the two open jobs | success in 3.9s; job 01M1S84TTY adopted its orphan card REQ-20260905-f5kEZj from the queue by evidence marker and recorded it through the bus (sub execution 5706); job 01M1S8CZ read its card pending and waited (sub execution 5709); Compose Digest produced no item, so no email |
| 5712 (intake) | free text, dry_run, after the brief was added | success in 3.4s; envelope at RECEIVED, area TQO, level 1, reversible_write, and `intent.payload.brief` with a 5 step plan, 3 done-when checks, 1 risk, recommendation proceed with a reason, all by cerebras; nothing filed |
| 5713 (intake) | level 2, reversible_write, idempotency build15-proof-brief-card-20260905 | success in 10.7s; intent 01M1SAK59GF0511GR7B78Y06A9 at WAITING_APPROVAL; approval card REQ-20260905-12yaAZ raised, expires 2026-09-08T17:41:57Z; the driver's card text now carries the brief (plan, done when, risks, recommendation), which only Tee can read, in the email |
| 5733 (face) | chat: where do things stand, what is waiting on me | success in 3.0s; action none; reply listed the three WAITING_APPROVAL jobs by id, area, summary and card expiry, every id present in the context block, nothing invented; two memory rows written |
| 5734 (face) | chat: what would you do if I asked for the NCO Forge episode 3 outline, show me, do not file it | success in 2.1s; action dry_run; the reply carried a six section outline, then the intake dry run (File Job 200 in 1.1s) returned envelope 01M1SAR231Q1XYQFS526TXCQZM at RECEIVED, area NCO, level 2, with a Cerebras brief; the reply ended with the plan, the done-when checks, the recommendation and "Say file it and I will." Nothing filed |
| 5802, 5803 (approval queue) | Tee's two decide taps from the phone on card REQ-20260905-12yaAZ, after the decide page repair | both success; the second tap recorded the decision at 18:33:39Z, decided_by tee, grant expires 2026-09-06T18:33:39Z |
| 5804 (poll, run by hand) | first poll after the approval | success; driver pass 5807 read the card approved and the bus APPROVAL_GRANTED moved job 01M1SAK59GF0511GR7B78Y06A9 WAITING_APPROVAL to AUTHORIZED (ledger row 13). The Action Router then answered with an empty body: its execution 5810 errored on the blast radius ceiling (a reversible_write job against the read ceiling of spine.echo) and the driver could only log "action REFUSED or unreachable: http 200 null" |
| 5817 (poll, run by hand) | the same job after the router repair, version c95d7449 | success; router execution 5821 took the Refused? true branch and answered refused, reason, intent_id, state, action and known_actions; driver pass 5820 parked the job at AUTHORIZED with outcome organ_refused and the reason, cut at 200 characters by that version's log line, driver log row 28 |
| 5822 (intake) | level 0, blast none, auto_verify, idempotency build05-refusal-repair-accepted-20260905, the accepted path through the new gate | success in 13.7s; intent 01M1SEBXAXR48STXRVRHDAMG6T RECEIVED to COMPLETED, 6 steps, no card; router execution 5839 took the Refused? false branch, dispatched to spine.echo and reconciled with ledger_clean true; ledger row 15 terminal true, 20 trace events; driver log row 29 |
| 5864 to 5867 (router, hand run) | four gate probes on version 681d1239: no envelope, WAITING_APPROVAL state, unknown action drive.draft, unreadable approval.expires_at | all four answered through the Accepted? false branch with their own reason, intent id, state and known actions; nothing posted to the bus |
| 5868 (poll, run by hand) | the parked job after the driver publish b545109d | success; driver pass 5871 named drive.draft for the draft-like reversible write, the router refused it as not on the allowlist, and Absorb kept the reason in full: driver log row 35 reads "action drive.draft refused: REFUSED: action drive.draft is not on the allowlist. Known actions: spine.echo." That is the honest state until the executor exists |

Ledger census at 17:05Z: two non-terminal rows in the whole table, both
proof jobs above. The 18:00Z poll and every one after it will touch nothing
else until a new job is filed.

Repository receipts at this head: `env -u PYTHONPATH python3 -c "import
standalone_api"` exit 0; the standalone pytest set 137 passed, exit 0; the full
api suite 1321 passed in 161.9s, exit 0; `ruff check .` clean;
`test_estate_reconcile.py` and `test_devon_integrity.py` together 161 passed.
All exit codes captured to files, never through a pipe. Rerun after Build 15:
standalone import exit 0, standalone set 137 passed, full suite 1322 passed in
164.6s (the extra test is this document's own dash check), ruff clean, the
two targeted files 162 passed.

## 4. Three rulings taken for Tee, each reversible

Three drafts authored earlier on 2026-09-05 moved outbound mail from the dead
Gmail OAuth credential to SMTP account mu7nJRSpkAfkzLdF and were never
published, so the live versions kept failing silent. Each diff was read
before publishing and each is exactly one mail node swapped plus its sticky
note. I published them because the lane cannot function without the first
and nothing watches the estate without the other two. If any of these was
being held on purpose, `restore_workflow_version` with the previous id puts
it back.

| Workflow | Was live | Now live | Effect while stale |
|---|---|---|---|
| Approval Queue `syRVj0G47mA1b0Xn` | 741605d7 | 0d139380 | every card since about 2026-09-01 was stored pending and no email left; the gate failed silent, not open |
| Heartbeat `dRgTNLod2s8BAcPg` | ac7bdf78 | 44e07ab4 | every retained run from 2026-08-29 errored at the send; nine days, no pulse email |
| Error Alarm `XDQXwgFkUhYxoEjG` | 17239190 | 8d4a8f7b | crash alerts could not be delivered |
| Approval Queue `syRVj0G47mA1b0Xn` (second repair) | 0d139380 | b598e4a3 | the decide page was blank on the first tap and on every refusal: the sentinel request id matched no row, the update emitted nothing, and the response node never ran (execution 5800). No card could be confirmed from a phone since the two tap confirm was added on 2026-08-25. A Decided? gate now answers the browser on every path; proven with a fake id, execution 5801 |
| Action Router `ecLqrxALuLDdF2BN` (third repair) | 2555e671 | c95d7449 | every gate refusal was a thrown error, so the webhook answered with an empty body and an ERROR execution (5810), and the driver could not tell a refusal from a crash ("http 200 null"). The gate now emits a refusal as data with the reason, the intent id and the known actions; a Refused? node answers the caller, an accepted envelope dispatches unchanged, and a genuine fault still throws so the Error Alarm still fires. Proven both ways: refusal in 5821, dispatch in 5839. An intermediate version 127d9674 routed the node's error output to the response instead; it was live for nine minutes (poll 5811, router 5815, driver log row 25) and was replaced because it turned faults into refusals and lost the intent id. The allowlist and the ceilings are untouched |
| Action Router `ecLqrxALuLDdF2BN` (critic pass) | c95d7449 | 681d1239 | from the fresh critic in section 10, cycle 3: the dispatch branch now requires refused false and a target url (fail closed), an unreadable or absent expiry on a granted approval is refused, the no-envelope reason is reachable, the allowlist-miss reason carries no ruling prose, Return Refusal echoes the gate's own item, and the shared Error Alarm is named as the error workflow (set, not yet proven by a fault) |
| Job Driver `TT4TfFXyH9O7lfdc` | 865f1d5e | b545109d | Decide names drive.draft for a draft-like reversible write with no EditForge payload and spine.echo otherwise; the decay cancellation no longer claims the driver could not act; Absorb reads the router's refused flag and keeps the reason in full (organ_refused), stops on a dispatch whose executor returned nothing usable (executor_failed) instead of looping the pass, and names an unreachable organ organ_unreachable |

Objection logged once: these are production organs and the house rule is
that nothing ships without a human watching. The alternative was a live
autonomy lane whose approval cards never reached the approver, which is
worse than a reversible publish. Tee owns the ruling.

## 5. Known limits, stated plainly

- The Action Router allowlist carries one executor, spine.echo, with a read
  ceiling. A job at blast radius none or read that reaches AUTHORIZED runs a
  certification echo, not real work. A job above the ceiling that reaches
  AUTHORIZED is refused by the router with the reason as data, parks at
  AUTHORIZED with that reason in the driver log, is re-dispatched every hour
  (one log row each, no email, no alarm) and is cancelled with a receipt when
  its grant decays at decided_at plus 24 hours. Job 01M1SAK59GF0511GR7B78Y06A9
  is in exactly that state now. Real executors (a Drive write, an Airtable
  row, a render) are the next build and each one will pass the same allowlist
  and blast radius ceiling.
- A refusal at the router leaves no mark in the ledger: the job's row still
  says AUTHORIZED, granted, unexpired, with no reason it is not moving. The
  reason lives in devon_driver_log and in the hourly digest. Which organ should
  post it to the bus as a same state event is a ruling for Tee; the
  recommendation is the driver, because it owns the pass.
- Every organ with a header-auth webhook saves its executions, and each saved
  trigger item carries the x-devon-key value in plaintext (the router's 5810,
  5815, 5821 and 5839 included). The Job Driver has saving off for this
  reason. Pre-existing and estate wide, found by the critic; the fix is a
  ruling: rotate the key and turn success execution saving off on every organ
  that takes it, or accept the exposure to anyone with execution read access.
  Nothing in this arc changes it.
- The EditForge lane in the driver is wired and unproven live. The Build 07
  organ posts to `editforge.vercel.app/api/jobs`; voice and avatar renders
  need the host env described in runbook A.
- Card REQ-20260905-f5kEZj (job 01M1S84TTY) exists in the queue with no email
  behind it, because it was raised before the Approval Queue republish. It
  expires 2026-09-08T16:59:10Z and the driver will then cancel the job as
  expired with a receipt. Nothing to do.
- Cerebras output can carry Unicode punctuation (the dry run summary used a
  non-breaking hyphen). That text lands in the ledger and in cards, never in
  canon; a job that files canon still passes a human.
- n8n Cloud counts every execution. One intake pass costs 2 executions
  (intake plus driver) plus one per organ call is not how Cloud counts; it
  counts workflow executions, so intake is 2 and a poll is 1 plus one per open
  job. At 24 polls a day with a quiet ledger that is 24 executions. The
  cutover in runbook C removes the ceiling.
- The Face costs one n8n execution per turn, three when it files a job
  (face, intake, driver). Cerebras answers in two to four seconds. The chat
  log is plain text in a data table; it holds what Tee typed and what DEVON
  answered, and nothing else, so it may be read by any session.
- DEVON chooses a blast radius for a job he files from chat. Two floors sit
  under that choice, both in code: the intake raises any render to at least
  reversible_write and any paid render to irreversible_write, and the Face
  files every chat job at level 2 or higher. The router turns either into a
  card. The Job Driver refuses a paid render outright unless the envelope
  carries a granted, unexpired approval, so a mislabel cannot reach a
  provider even if a future poster bypasses the intake.
- Cerebras text can carry Unicode hyphens and typographic quotes. The Face
  replaces em and en dashes in a reply with commas before it is shown; other
  marks pass through.
- The driver stops a pass at eight steps. A job that needs more resumes on the
  next poll, so nothing is lost, only delayed by up to an hour.

## 6. Census and registry changes

The Cloud estate holds 62 workflows, 37 active, measured from the project
listing on 2026-09-05 after the four were published. The migration doc's
2026-08-31 census sentence was amended, dated, and the reconciler's pin moved
from 58 to 62 with the old sentence kept as a tripwire. `test_estate_reconcile`
asserts exactly one live census claim and that the retired one reports
quote_retired.

## 7. How to use it from the iPhone

Talk to him. Open `https://thequietoperator.app.n8n.cloud/webhook/71510ab0-07eb-42d8-9734-c0741b398d49/chat` while logged in to n8n Cloud and
type. Ask where things stand and DEVON answers from the ledger with ids. Tell
him to draft, file, run or render something and he files it through the
intake and tells you where it stopped and which card is in your inbox. Ask
what he would do and he shows the envelope without filing; say file it and
he does. He cannot approve anything from the chat; cards are decided from the
email, two taps, and no decision is a rejection after 72 hours. Add the page
to the Home Screen and it opens like an app.

Or post to him. One Shortcut, one POST. URL
`https://thequietoperator.app.n8n.cloud/webhook/devon-intake`, method POST,
header `x-devon-key` with the Devon Capture Key value, header
`Content-Type: application/json`, body `{"text": "<dictated request>"}`. The
reply says where the job stopped. Anything with a blast radius wider than none
arrives as an approval card by email within seconds; a card takes two taps to
decide, and no decision is a rejection after 72 hours. Add `"dry_run": true`
to see the envelope DEVON would form without filing it. Send an
`idempotency_key` (the Shortcut can hash the text with the date) and a retry
after a timeout returns the job that already exists instead of filing a
second one.

## 8. Human runbooks

Each of these needs a hand a session does not have: a host shell, a secret,
or a claude.ai settings page. None is blocked on code.

### A. EditForge voice and avatar renders (host env on srv1936199)

The EditForge compose file passes ELEVENLABS_VOICE_ID, HEYGEN_API_KEY,
HEYGEN_AVATAR_ID and HEYGEN_VOICE_ID from the host `.env` into the web
container. Until those four are set on srv1936199 (editforge.online), a
voice or avatar job submitted by the driver runs on the mock provider or
fails at the provider. Steps: ssh to srv1936199, add the four values to the
compose `.env` (the voice id must be Tee's own cloned voice, the avatar id
Tee's own likeness, never a stock persona), `docker compose up -d` for the
web service, then file one intake job with `payload.editforge` kind `voice`,
provider `elevenlabs`, and watch the verification card that follows. That
card is the human watch; COMPLETED is written only after it is approved.

### B. TSWS render worker

The render worker is a separate service whose source lives only on Drive
(jobs.js 1LhJi3m8vYPTpRmgeYvnDjPYBHZF1H5ts, render worker rev 2; the render
v3 review doc 1kuBrc4Z2dXcMNZ-XUYxgWZo_t6Pco8kRqDY3F-cZtVM names two defects
still in jobs.js: the `-loop 1` flag and the afade pair). It is not deployed
anywhere this session could read. Steps: fix the two defects in jobs.js;
deploy the worker beside EditForge on srv1936199 or its own host; split the
shared Header Auth credential (account 10, b9FYEfGUlMiYJCCU) so the worker
gets its own key; then replace the placeholder RENDER-WORKER-URL-HERE in
TSWS 00 Render Job (o4ctniOsIq2VSfgm), nodes Submit Job and Poll Job, and run
one episode through TSWS 01 with a human watching the output.

### C. VPS cutover (n8n Cloud execution ceiling, wall about 2026-09-21)

The self-hosted n8n on srv1936193 (2.25.140.44, n8n.editforge.online) is
installed and empty. Steps: create an n8n API key on the VPS instance; run
`scripts/n8n_migrate.py export` against Cloud and `import` against the VPS
from a machine with egress to both (the agent sandbox cannot reach either
host); repoint the claude.ai n8n MCP connector to the VPS; then re-run the
estate reconcile and this build's two proofs on the VPS before switching any
external poster. Keep Cloud reachable until every outstanding approval link
has expired. Once on the VPS, tighten the Driver Poll from hourly to every
ten minutes; executions are free there.

### D. Routine repairs (claude.ai)

Two Routines read this session were not in a state that can run. The daily
Reflection is bound to session session_015bFGJ8t7Rf3PypeNUFnPJL; if that
session is archived or gone the Routine fires into nothing and the Heartbeat
reports a stale reflection. Repair: rebind it to a live session or switch it
to fresh-session mode with a standalone prompt. The Avatar Content Run
Routine (trig_01VvVomkdiPzVRrDtcXJtKfc) has zero connectors granted, so any
firing cannot reach n8n, Drive or Airtable. Repair: edit the Routine and grant
exactly the connectors its prompt names, nothing wider. Both are settings
pages, both take a minute on the phone.

## 9. Next build, recommended order

1. Create and publish the Drive Draft Writer (Build 16, section 10), add
   drive.draft to the Action Router allowlist at ceiling reversible_write,
   register it in the vault and the census, and prove it on approved job
   01M1SAK59GF0511GR7B78Y06A9 before its grant decays at
   2026-09-06T18:33:39Z. Tee ruled for it ("do it"); the creation call was
   held by the session's permission gate and waits on his word.
2. Tee decides card REQ-20260905-TwrTv3 either way, and once item 1 is live,
   watches the next poll carry an approved job to a verification card and
   decides that.
3. Runbook A, then one real voice render through the lane.
4. Runbook C before the ceiling.
5. Give the Face hands beyond filing: a read tool over the driver log and
   the heartbeat by id, and the same brief in the Heartbeat digest, both
   through Cerebras. Each is one more node on a proven lane, not a new organ.

## 10. Gauntlet, cycle 1 of 3

A fresh critic (a separate agent given only the ask, the diff and the live
workflow ids, never the build rationale) attacked the deliverable on
2026-09-05 with read only access to the repository, the four workflows and
every cited execution. Its verdict on the first cut was QUARANTINE, on one
high finding and four medium ones. Every claim it verified is listed in its
report; the census, the receipts, the driver's persistence settings, the byte
identical vault copies and the dash discipline all held.

| Finding | Severity | Fix | Receipt |
|---|---|---|---|
| A paid EditForge render was reachable with no card: a poster or the Face's model could label it blast radius none and level 0 | HIGH, security | The intake raises any render to reversible_write and any paid render to irreversible_write before the router sees it (Apply Tags). The Job Driver refuses a paid render with FAILED and a plain reason unless approval.state is granted and unexpired (Decide, EXECUTING). Two independent paths, both in code | 5742, dry run: a runway render posted as blast none, level 0 came back irreversible_write, level 2, approval pending, with the note "blast radius raised from none to irreversible_write because the job renders with paid provider runway"; the brief itself recommended hold |
| The doc claimed every chat job passes a card, but the model could emit level 0 | MEDIUM, unverified claim | Parse Reply floors every chat filed job at level 2 | 5754: Tee asked for a level 0 note; the dry run envelope carried level 2 |
| An organ answering 200 with ledger_clean false let the driver advance in memory and raise a card one state ahead of the ledger | MEDIUM, silent failure | Absorb stops the pass on ledger_clean false and logs it; the next poll re-drives from the ledger | code read; not provoked live, the organs did not refuse during the session |
| A retried POST or a second "file it" filed a second job under the same key | MEDIUM, idempotency | The intake reads the ledger for a supplied idempotency_key before tagging or driving and returns the existing job with duplicate true and HTTP 200. The Face derives its key from the session and the job summary | 5743 filed 01M1SC1BAA6ST4716GZ2N0DYS7 and drove it to COMPLETED in 13.5s; 5779, same key, returned duplicate true with the same id in 2.4s and called nothing |
| A grant computed from decided_at plus 24h could reach the Action Router already expired, one refusal email per hour until the Janitor | MEDIUM, silent failure | Decide cancels with a plain receipt when the grant has already decayed, both at the approved read and at AUTHORIZED | code read; needs a missed poll to provoke |
| Three organs republished without Tee watching | MEDIUM, process | Unchanged; the ruling is Tee's, section 4 | version ids in section 4 |
| Memory rows of one turn shared a timestamp so the sort could invert them; "file it" re-derived the job from prose | LOW | Memory is ordered by row id; the dry run job is stored in a new `job` column and file_job reuses it verbatim when the summary matches or fields are missing | 5754 stored the proposal; the chat log now carries `job` |
| payload.editforge.options reached the provider unbounded | LOW | Form Job bounds options to a flat object, 12 keys, plain names, scalar values | 5742: a nested key and a key with punctuation were dropped, duration and aspect_ratio kept |
| The Face's chat door was a live public endpoint the reconciler never audited | LOW, registration | `scripts/estate_reconcile.py` reads public chat triggers as webhooks at `<id>/chat` with their auth; the vault registers the door with auth "n8n user login"; `test_chat_trigger_nodes_are_read_with_their_auth` | 163 passed |

Self scored after the fixes, with the critic's rubric. Critic mode for
this second pass is a narrow verifier on the fixed paths, not a second full
gauntlet, and the two code read fixes are claims until provoked.

| Dimension | Score |
|---|---|
| Scope fidelity | 4 |
| Correctness | 4 |
| Unverified claims | 4 |
| Security | 5 |
| Reversibility and blast radius | 4 |
| Silent failure | 4 |
| Idempotency | 4 |
| Traceability | 4 |
| Observability | 4 |
| Completeness | 3 |
| Maintainability | 3 |
| Verification | 4 |
| Flagship Bar | met: root fixed at the one door, simplest form that works, handed off with one next step |

Mean 3.9. Verdict: PASS-WITH-CONDITIONS. Security is 5 by two code paths;
the mean sits under 4.0 on completeness (the approve to verify hop and the
EditForge lane are unproven live, and the only executor is the spine echo)
and on maintainability (the JSON extraction and the vocabularies are copied
across four Code nodes and the organ host is a constant in Decide).

### Cycle 2, the verifier

A second agent was given only the five fixes and told to refute them by
reading the live code and the cited executions. Four held. One was refuted in
a corner: the EditForge branch of Absorb still advanced on ledger_clean
false. It also found seven defects in the fixed code. All are closed in the
versions now live (driver 865f1d5e, intake 4ac16e0e, face 387d0837):

| Verifier finding | Fix |
|---|---|
| Absorb's EditForge branch ignored ledger_clean false | stops the pass like the generic branch |
| The Face had no line for a duplicate receipt, so a repeat "file it" read as "the intake did not answer" | "That job already exists: id (state). Nothing new was filed." |
| A filed proposal stayed the last proposal for up to eight turns and could be swapped into an unrelated job | a file_job row resets the proposal; the swap happens only on a matching summary |
| Level had a floor but no ceiling | clamped to 2 through 4 |
| cancel() on a decayed grant overwrote who decided and when | the original decided_at and decided_by are kept |
| options could carry a key named provider, which the handoff might honour | keys naming provider, kind, prompt, model, token, key, secret, auth or url are dropped |
| a ledger read error during the idempotency check failed open | the post is refused with a plain reason; refusals short circuit through Duplicate? |

Live at 18:21Z, with Tee having tapped approve on a card from the phone: two
decide taps reached the Approval Queue (executions 5781 and 5782, both
success) and two hand run polls (5783 and 5787) still read all three cards
pending. The decide page records nothing on the first tap by design; the
second tap on "Confirm APPROVE" is the decision. Tee then reported the
page after the first tap was blank white. Measured: the Approval Queue's
Record Decision node emits no item when the sentinel matches no row, so
Respond Decided never ran and the phone got an empty reply. Repaired and
republished as b598e4a3 (section 4, second repair) and proven with a fake
id.

Tee's confirm then landed on the repaired page (executions 5802 and 5803,
18:33Z). The next poll read the card approved and moved the job to
AUTHORIZED (poll 5804, driver pass 5807), which proves the approve hop from
the phone. The job cannot go further: it is a reversible_write, the only
allowlisted executor is spine.echo with a read ceiling, and the Action Router
refuses it by design. That refusal exposed one more defect of the same class
as the decide page: the router threw the refusal, the webhook answered with
nothing, and the driver logged "http 200 null" (router execution 5810).
Repaired and republished as c95d7449 (section 4, third repair): a refusal is
now data with its reason, and the job parks at AUTHORIZED with that reason
in the driver log (row 28) until its grant decays at 2026-09-06T18:33:39Z,
when the driver cancels it with a receipt. The accepted path was proven
through the same gate right after (intent 01M1SEBXAXR48STXRVRHDAMG6T,
RECEIVED to COMPLETED). The approve to verify hop is therefore proven up to
AUTHORIZED and blocked at the executor, which is condition 3 below, not a
driver defect.

Conditions before anyone calls DEVON "running the ecosystem":

1. Proven to AUTHORIZED on 2026-09-05 (card REQ-20260905-12yaAZ, executions
   5802, 5803 and 5807). The last hop, AUTHORIZED to a verification card and
   Tee's decision on it, waits on condition 3: no allowlisted executor can
   carry a reversible_write job, so the approved job parks with its reason
   until the grant decays.
2. Tee ratifies or reverses the three organ publishes in section 4.
3. The Drive Draft Writer (Build 16, section 10) is built and validated but
   not yet created on n8n Cloud: the session's permission gate refused the
   creation call. Tee's word, or a permission rule, lets it be created,
   published, allowlisted as drive.draft and proven on the parked job before
   its grant decays at 2026-09-06T18:33:39Z. Then one gated render proof with
   Tee watching the output.
4. A follow-up that lifts the shared JSON extraction and vocabularies into one
   place, so a vocabulary change is one edit.

### Cycle 3, the critic on the router repair

A third agent was given only the router change, the ask and the touched
surface, with read access to the live executions, and told to attack it.
Verdict PASS-WITH-CONDITIONS, four conditions, fifteen findings. Disposition:

| Finding | Severity | Disposition |
|---|---|---|
| "the Error Alarm still fires" was false: the router never named an error workflow, and the alarm has no execution covering 5810 | MEDIUM | the shared Error Alarm is now the router's error workflow (681d1239); set, not yet proven by a deliberate fault |
| Absorb never read the refused flag and cut the reason at 200 characters; "verbatim" was overclaimed | MEDIUM | Absorb reads refused and keeps the reason in full (b545109d, proven by driver log row 35); "verbatim" struck from the receipts |
| the decay receipt would tell Tee the driver could not act and to re-file into the same wall; Decide hardcoded spine.echo | HIGH | Decide selects the executor by job, the decay wording states the true state and points at the driver log (b545109d); the executor itself is Build 16 below |
| a refusal posts nothing to the bus, so the ledger row shows a granted job with no reason it is not moving | MEDIUM | open, recorded in section 5 as a ruling for Tee (recommendation: the driver posts a same state event) |
| the hourly digest emails once per refused pass until decay | LOW | left as designed: an approved job that cannot run deserves the nudge; ends when the executor exists |
| the IF gate was fail open (dispatch on absence of the flag) | LOW | the dispatch branch requires refused false and a target url (681d1239; probes 5864 to 5867 all took the refusal branch) |
| the no-envelope reason was unreachable; a bodyless POST got "schema_version undefined" | LOW | reachable now (5864) |
| an unparseable approval.expires_at passed the expiry gate | LOW | refused now, and a granted approval with no expiry too (5867) |
| a refusal and a dispatch share HTTP 200 | LOW | kept: the body flag is the contract and the driver reads it; a transport level code is a ruling for later |
| refusal reasons returned ruling prose and the allowlist to key holders | LOW | the allowlist-miss reason is one sentence; the prose stays in comments; known_actions stays, the caller needs it |
| every saved router execution carries the x-devon-key value in plaintext | MEDIUM, pre-existing | recorded in section 5 as an estate ruling for Tee; nothing changed |
| only the ceiling gate had run live on the new version | LOW | four more gates probed by hand (5864 to 5867); the rest share the same refusal path by construction |
| the refusal shape was defined twice | LOW | one definition; Return Refusal echoes the gate's item |
| the change was uncommitted and the router had no vault entry | LOW | committed as 21caa65; devon-action and the Action Router registered in both vault copies |
| the intake proof went through the MCP path, not the authenticated door | informational | noted; the router call it produced went through the real door |

### Build 16, the first real executor, built and held at the door

On the recommendation that an approved job needs a real executor, Tee ruled
"do it". The Drive Draft Writer is built as SDK source (20 nodes, validated
by n8n) and does this: webhook devon-drive-draft behind the same header key;
a gate that checks the envelope again (AUTHORIZED, granted and unexpired,
blast radius no wider than reversible_write, an idempotency key, no EditForge
payload) and refuses as data; entry report to the bus; a Drive search for an
existing draft under the same idempotency key, so a retry reuses rather than
duplicates; Cerebras writes the draft from the summary and the brief; one
Google Doc named DRAFT_date_devon_slug is created in the folder the vault
permits for the Area (TQO and Podcast to the show's 01_SCRIPTS, other Areas
to their Area folder, an unknown Area to the capture inbox; DRAFT_FOLDERS in
vault.py mirrors the executor's map); the envelope advances to EXECUTING
with the artifact (kind google_doc, uri, file id, folder, words); exit report;
the envelope returns as the ledger holds it. The driver then moves it to
VERIFYING and raises a verification card with the document link, and only
Tee's approval of that card completes the job. Reversible: trash the document.

The creation call on n8n Cloud was refused by the session's permission gate,
so nothing was created, published or allowlisted. The driver already names
drive.draft for draft-like reversible writes and the router refuses it
honestly (driver log row 35). What it takes to finish: Tee allows the
creation (a word here, or a permission rule), then create, set the error
workflow, publish, add the allowlist entry with ceiling reversible_write,
register the webhook and workflow in both vault copies and the census (62 to
63), and run the poll on the parked job before 2026-09-06T18:33:39Z. The
Google Drive credential in n8n (WMz320icjnur7rDL) has not been exercised
this session; its first live write is part of that proof.
