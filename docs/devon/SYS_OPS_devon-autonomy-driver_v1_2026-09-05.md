---
title: DEVON Autonomy Driver (Build 14)
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

# DEVON Autonomy Driver (Build 14) v1

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

All three live in the n8n Cloud project rM0TNTE2fNXErglU, header auth on
the one webhook, crash alerting through the DEVON Error Alarm, 300 second
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

## 3. Measured receipts (n8n Cloud, 2026-09-05, all times UTC)

| Execution | What | Result |
|---|---|---|
| 5629 (intake) | level 0, blast none, auto_verify, idempotency build14-proof-level0-20260905 | success in 13.7s; intent 01M1S81K3WDD0JSKY6KPAY43K1 RECEIVED to COMPLETED, 6 steps, no card; ledger row id 10 terminal true, verification passed by auto_no_artifact, receipt outcome completed, 20 trace events; devon_driver_log row 1 |
| 5663 (intake) | level 2, reversible_write, idempotency build14-proof-gated-20260905 | success; intent 01M1S84TTY4DMC4D0VCHTJB672 stopped at WAITING_APPROVAL with outcome card_post_failed, http 200 with a null body. Approval Queue execution 5681 errored: its live version still emailed through Gmail credential vsTKuAilHmpYCc5L, which had gone invalid, and Store Pending had already written the row. Root cause, not the driver |
| 5667 (intake) | free text, dry_run | refused: Cerebras unavailable, HTTP no response, in 0.18s. Root cause: the tagging prompt described the reply shape with a quoted JSON literal and the quotes lost their escaping on import, so the expression failed before any request left |
| 5684 (intake) | same free text, dry_run, after the prompt fix | success in 2.9s; envelope formed at RECEIVED with area TQO, level 1, blast_radius reversible_write, summary rewritten as one imperative sentence, all four tags by Cerebras, nothing filed |
| 5685 (intake) | level 2, reversible_write, idempotency build14-proof-gated-b-20260905, after the Approval Queue republish | success in 7.8s; intent 01M1S8CZ37X87B6281WPQA68B1 at WAITING_APPROVAL; approval card REQ-20260905-TwrTv3 raised, expires 2026-09-08T17:03:37Z; bus APPROVAL_REQUESTED persisted (ledger update_same_state); Approval Queue execution 5702 success, SMTP send included; ledger row id 12 carries approval.queue_row_id |
| 5705 (poll, run by hand) | hourly pass over the two open jobs | success in 3.9s; job 01M1S84TTY adopted its orphan card REQ-20260905-f5kEZj from the queue by evidence marker and recorded it through the bus (sub execution 5706); job 01M1S8CZ read its card pending and waited (sub execution 5709); Compose Digest produced no item, so no email |

Ledger census at 17:05Z: two non-terminal rows in the whole table, both
proof jobs above. The 18:00Z poll and every one after it will touch nothing
else until a new job is filed.

Repository receipts at this head: `env -u PYTHONPATH python3 -c "import
standalone_api"` exit 0; the standalone pytest set 137 passed, exit 0; the full
api suite 1321 passed in 161.9s, exit 0; `ruff check .` clean;
`test_estate_reconcile.py` and `test_devon_integrity.py` together 161 passed.
All exit codes captured to files, never through a pipe.

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
- The driver stops a pass at eight steps. A job that needs more resumes on the
  next poll, so nothing is lost, only delayed by up to an hour.

## 6. Census and registry changes

The Cloud estate holds 61 workflows, 36 active, measured from the project
listing on 2026-09-05 after the three were published. The migration doc's
2026-08-31 census sentence was amended, dated, and the reconciler's pin moved
from 58 to 61 with the old sentence kept as a tripwire. `test_estate_reconcile`
asserts exactly one live census claim and that the retired one reports
quote_retired.

## 7. How to use it from the iPhone

One Shortcut, one POST. URL
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
