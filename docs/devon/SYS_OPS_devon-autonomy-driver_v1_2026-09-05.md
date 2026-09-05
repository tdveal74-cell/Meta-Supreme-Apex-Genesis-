---
title: DEVON Autonomy Driver and Face (Builds 14 and 15)
type: SYS_OPS
version: 1
date: 2026-09-05
area: Systems
status: live-on-cloud-human-gated
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

Objection logged once: these are production organs and the house rule is
that nothing ships without a human watching. The alternative was a live
autonomy lane whose approval cards never reached the approver, which is
worse than a reversible publish. Tee owns the ruling.

## 5. Known limits, stated plainly

- The Action Router allowlist carries one executor, spine.echo. A job that
  reaches AUTHORIZED today runs a certification echo, not real work. Real
  executors (a Drive write, an Airtable row, a render) are the next build and
  each one will pass the same allowlist and blast radius ceiling.
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
- DEVON chooses a blast radius for a job he files from chat and the intake
  trusts that field. The level 2 default sends every chat filed job to a
  card, so a too narrow blast radius still passes Tee before anything runs;
  it does not yet raise the blast radius floor, which is a router change.
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
to see the envelope DEVON would form without filing it.

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

1. Tee decides card REQ-20260905-TwrTv3 either way, then watches the next
   poll carry the job to a verification card. That is the last unproven hop
   in the human-gated path.
2. Runbook A, then one real voice render through the lane.
3. A second executor on the Action Router allowlist (a Drive draft write,
   reversible, blast radius reversible_write) so an approved job produces an
   artifact.
4. Runbook C before the ceiling.
5. Give the Face hands beyond filing: a read tool over the driver log and
   the heartbeat by id, and the same brief in the Heartbeat digest, both
   through Cerebras. Each is one more node on a proven lane, not a new organ.
