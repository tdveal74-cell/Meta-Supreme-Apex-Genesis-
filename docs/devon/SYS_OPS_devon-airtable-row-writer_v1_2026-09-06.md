---
title: DEVON Airtable Row Writer (Build 17), the close-out, and the handover
type: SYS_OPS
version: 1
date: 2026-09-06
area: Systems
status: live-on-cloud-proof-waits-on-card
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: b8fffb1
branch: claude/new-session-2f2yu2
supersedes: none
---

# DEVON Airtable Row Writer (Build 17) and the close-out handover v1

## Verdict in one paragraph

DEVON has a second real executor. On Tee's ruling of 2026-09-06 (build a of
the a, b, c order the operational report recommended) the Airtable Row Writer
went live on n8n Cloud as workflow `ps2S6dWcTIpq5bvr`, door
`devon-airtable-row` behind the same header key, and the Action Router now
carries `airtable.row` at ceiling `reversible_write` beside `drive.draft`. It
writes one row into a table its own allowlist permits (Inbox Captures today)
from an AUTHORIZED envelope that carries a structural
`intent.payload.airtable`, stamps the job's idempotency key and intent id on
the row in two fields created for it, finds an existing row under both before
writing, reads the created record back so the artifact says whether the stamp
persisted, and refuses as data. The Job Driver binds it only when the payload
is there, never from words in the summary, and the approval card names the
table, the title and the fields. Three things that would have made the
executor unreachable or unrecorded were found by reading rather than assumed
and closed in the same arc: the Intake Former dropped `payload.airtable`
before this build, the Face did not know either real executor existed, and
the live Absorb node had never received a guard the repository said it had.
Pinned runs 6171 to 6173 prove the write, the refusal and the reuse branches;
a live gated job (`01M1V6M3XG0RQR191QFF7W74WJ`) is parked at
WAITING_APPROVAL on card `REQ-20260906-8kt8Vj` with the executor bound and
named, and the first real row waits on Tee's tap. Nothing in this document
claims that row exists.

## 1. What was built

### The executor, `ps2S6dWcTIpq5bvr`

Sixteen nodes, created from validated SDK source and read back node by node.
Door `Row In (POST)` at path `devon-airtable-row`, header auth on credential
`FYRvkRTOcROEYZ9P` (Devon Capture Key, by id). `Validate and Plan` holds the
gates the Drive Draft Writer holds (schema 1.0.0, ULID, AUTHORIZED only,
blast radius no wider than `reversible_write`, a granted and unexpired
approval on every envelope whatever the label says, the ten minute single
flight lock, an idempotency key of 8 to 128 characters with no quotes, braces
or backslashes because it is quoted into an Airtable formula, no EditForge
payload) and then the allowlist: `TABLES` maps a table name to its id, the two
stamp fields and a rule per writable field (text with a length cap, date as
YYYY-MM-DD, select as one option name, multi select as a list of option
names). Anything outside it refuses with the writable tables or fields
named. The executor never sends `typecast`, so an option that does not exist
on a select field is Airtable's 422 and comes back as a refusal naming
Airtable's own error type. It never defaults a field the job did not name.

`Report Entry to Bus` posts INTENT_RECEIVED with `execution.state running`
under this workflow id, which is the lock. `Find Existing Row` is an HTTP
GET on the Airtable API with the predefined Airtable token credential
`OyuQtrelq7zP2mTy` (by id), `filterByFormula` on both stamp fields and
`maxRecords` 3, full response, never error. `Check Existing` refuses unless
the ledger persisted the entry report, refuses unless the search answered
200, and re-reads both stamp fields on every hit so a row carrying this key
under another job's id is ignored rather than adopted. `Write Row` is an
HTTP POST of `{ fields }` with the same credential. `Row Result` refuses on
anything but 200 with a record id and sets `key_verified` only when the
record Airtable returned carries this job's key and intent id. `Advance
Envelope` moves AUTHORIZED to EXECUTING with an artifact of kind
`airtable_record` (record url, id, table, the field names written, `by
airtable.row`, `reused`, `key_verified`) and an ACTION_STARTED trace entry;
`Report Exit to Bus` posts ACTION_COMPLETED; `Reconcile Exit Envelope`
carries both persistence flags and `ledger_clean`; `Return Envelope` answers
`[envelope]`, which is what the router's Report Dispatch parses; `Return
Refusal` answers HTTP 200 with the refusal as data. Settings: error workflow
`XDQXwgFkUhYxoEjG`, 120 second timeout, successful executions not saved.
Active version `d16f002c`.

The two stamp fields were created on Inbox Captures `tbl4ziFRbl5mnUcKc`
before the workflow: `DEVON key` (`fldvp5UiTnGhRunAs`) and `DEVON job`
(`fldM2r96swSZsxH8x`), both single line text, both described in place.
Adding a table to the allowlist means creating those two fields on it first.

### The router, the driver, the intake, the face

Action Router `ecLqrxALuLDdF2BN`: `airtable.row` in TARGETS at ceiling
`reversible_write`, with the ruling recorded in the comment above the table.
Active version `93f95447`.

Job Driver `TT4TfFXyH9O7lfdc`, Decide: `airtablePayload()` returns the
payload only when `intent.payload.airtable` is an object with a string table
and an object of fields; `selectAction()` tests it before the draft keyword
rule, so structure beats prose; `executorLine('airtable.row')` reads
"Airtable Row Writer (airtable.row): one row will be written into the
Inbox Captures table of the DEVON base, titled X, carrying the fields A, B,
C exactly as the job declares them plus DEVON key and DEVON job, reversible
by deleting the row. Nothing is published or sent". The binding into
`intent.payload.action` at card time and the mismatch park at AUTHORIZED are
unchanged. Active version `ea93e3ac`.

Intake Former `AEFgXee7IDJarNV7`: Form Job keeps a structural
`payload.airtable` (table name, a flat fields object of strings, lists of
strings, numbers or booleans, at most 12 fields, 20000 characters per value)
and Apply Tags floors any Airtable row job at `reversible_write` so a card is
always raised. Before this edit the intake kept only `editforge`,
`auto_verify` and `note` from a poster's payload, so the executor built an
hour earlier was unreachable from every door. Active version `0a6cf6c0`.

Face `LsmfRFMmI5feINs0`: the system prompt said "a Drive draft is next" a
day after the draft writer went live. It now names the three executors and
what selects each, and the reply format lets the model attach an `airtable`
object (table Inbox Captures, the seven permitted fields, substance in
Body). Parse Reply carries that object into the job payload untouched; the
intake bounds it and the executor holds the allowlist. Active version
`1ccd11b9`.

### The registry, the tests, the copies

`services/devon/vault.py` and its byte identical copy under `deploy/soul`:
`AIRTABLE_ROW_TABLES`, the `devon-airtable-row` door in WEBHOOKS with its
open ruling, the `Airtable Row Writer` entry in WORKFLOWS, the Action Router
state naming all three actions and ceilings, and KEY_ROTATION at sixteen
paths with ten carrying an auth field in the map.
`test_airtable_row_tables_match_the_executor_table_map` pins the executor's
`TABLES` (id, stamp fields, writable fields) to `vault.AIRTABLE_ROW_TABLES`
and its `BASE` to `vault.AIRTABLE["live_base"]`. The census pin moved from
63 to 64 with the old sentence kept as a tripwire, and the migration doc was
amended, dated. `n8n/devon/` gained `airtable-row-writer/`, `intake-former/`
and `face/`, and every live Code node of seven workflows was diffed against
its repo file after publishing: all identical.

## 2. Measured receipts (n8n Cloud, 2026-09-06, all times UTC)

| What | Receipt |
|---|---|
| Executor created | `ps2S6dWcTIpq5bvr` at 10:55:13Z, published 10:57Z, active version `d16f002c` |
| Pinned run, write path | execution 6171: Body `line one\r\nline two  ` became `line one\nline two`, both stamps set, formula `AND({DEVON key} = '...', {DEVON job} = '...')`, artifact `recPINTEST0000001` with `key_verified true`, `ledger_clean true`, answered by Return Envelope |
| Pinned run, allowlist refusal | execution 6172: table Credentials refused with "Writable tables: Inbox Captures", Return Refusal, Write Row never ran |
| Pinned run, reuse | execution 6173: two rows under the same key, the one carrying another job's id ignored, `recEXISTING000001` reused, `reused true`, attempts 2, Return Envelope |
| Router published | `ecLqrxALuLDdF2BN` active `93f95447` (a31cfe83 carried the allowlist; 93f95447 added one trailing newline so Report Dispatch equals its repo file) |
| Driver published | `TT4TfFXyH9O7lfdc` active `ea93e3ac` |
| Intake published | `AEFgXee7IDJarNV7` active `0a6cf6c0` |
| Face published | `LsmfRFMmI5feINs0` active `1ccd11b9` |
| Live gated job | intent `01M1V6M3XG0RQR191QFF7W74WJ`, filed through the intake at 11:10:57Z (driver pass 6175, origin intake, RECEIVED to WAITING_APPROVAL in five steps), card `REQ-20260906-8kt8Vj` expires 2026-09-09T11:11:04Z, `intent.payload.action` bound to `airtable.row`, `approval.card_executor` names the Inbox Captures table, the title and the seven fields, brief by Cerebras recommends proceed |
| Face dry run | execution 6194: asked to show what it would file, the model returned action `dry_run` with an `airtable` object (Title, Captured, Kind, Source, Area, Body), Parse Reply carried it into `payload.airtable`, the intake formed envelope `01M1V6VN93D9V3EVQRZ613ATJT` with the payload intact and filed nothing |
| Census | 64 workflows, 39 active, from the project listing at 11:07Z |
| Deploy read back of the previous merge | Railway `941318bb` SUCCESS on `b8fffb1` with the alembic context lines; devon-soul `dpl_44y1ogZqxPyVdw7mhVaCQmHdZTUa` READY production on `b8fffb1`; nothing owed to the web project |
| Repository | 199 tests pass, ruff clean; PR #151 draft |

## 3. Drifts found and closed

Every live Code node touched was read before it was edited, and the reads
found three disagreements the record did not know about.

- The live Absorb node of the Job Driver had never received the HTTP 200
  guard on refusals as data that the repository copy carried since the
  2026-09-05 rulings commit (`6dce5e5`). A 500 whose body happened to carry
  `refused: true` would have been read as a designed refusal. The repository
  copy was pasted into n8n in the same publish as the Decide change.
- The repository copy of the Drive Draft Writer's Advance Envelope lacked the
  "matched by" note the live node carried. The live text was copied into the
  repository.
- The Job Driver's Decide comment and the router's Reconcile Exit Envelope
  comment differed by a few lines in opposite directions. Both now equal.

None of the three changed a proven behaviour. All three are the failure
class the README under `n8n/devon/` names: copies drift, and no test can
compare them to n8n from CI. The check that found them is a transcript
extraction of every `get_workflow_details` read, diffed against the files,
and it is worth running at the start of any session that will edit a node.

## 4. What is not proven, stated plainly

- **The first real row.** No row has been written by the executor. The
  gated job waits on card `REQ-20260906-8kt8Vj`. After Tee approves, the
  next hourly poll (or a hand run of the Driver Poll `mbIKJk4UuB7V27rP`)
  carries it AUTHORIZED, through the router, into the executor, to
  VERIFYING and a verification card. The proof is the ledger row's artifact
  with `key_verified true`, the Airtable row under `DEVON key
  build17-proof-20260906-airtable-row`, and the executor execution id. Task
  28 in the session task list is that proof.
- **The refusal and reuse branches live.** Proven on pinned data only.
- **An Airtable 422.** Never observed. The refusal text for it is code read
  only.
- **A chat filed row job.** The Face path is proven as a dry run only.
- **Runtime of the executor under a slow Airtable.** The router's dispatch
  timeout is 75 seconds and the executor's timeout 120; the search and the
  write carry 15 and 20 second timeouts, so the executor answers inside the
  router's window on the happy path. Not measured under load.

## 5. The gap sweep: what stands between DEVON and fully operational

Tee's ask on 2026-09-06 was DEVON fully operational and every gap named.
This is the list, graded, with the owner. Numbers reference the operational
report of the same morning (`SYS_OPS_devon-operational-report_v1_2026-09-06`).

1. **The execution wall on n8n Cloud, Runbook C.** The report's id delta
   estimate puts the burn near 260 executions a day and the wall nearer
   2026-09-10 than 09-21 if the plan caps at 2,500 a month. Owner: Tee.
   First act: read the usage page; then the cutover steps in the autonomy
   doc, section 8 runbook C. Nothing in this session touched it. This is
   the one item that can stop everything else.
2. **Build b, learning capture on COMPLETED jobs** (task 27). Every
   driver run job still carries `learning.state not_captured`. The Ledger
   Feeder `6hQD8YhiYzR1FFda` polls COMPLETED rows and feeds each once; the
   Build 12 gate promotes only on a complete, clear receipt with two or more
   independent sources, so a single feed never promotes. What is missing is
   the write back: nothing marks the envelope captured after a feed, and
   the ledger treats COMPLETED as terminal, so a LEARNING event may need a
   same state update through the guarded webhook. Read the feeder and the
   ledger's guard table before designing it; do not widen the terminal rule.
3. **The keyed reconcile.** The body gate check merged in #146 has never
   run keyed against the live instance; this container has no egress to the
   n8n host and no `N8N_SOURCE_KEY`. Run `snapshot` and `check --strict`
   from a machine that has both. Owner: the next session with a key.
4. **The stale card.** `REQ-20260905-f5kEZj` on job
   `01M1S84TTY4DMC4D0VCHTJB672` self cancels on 2026-09-08. Decide it or
   let it decay; deciding it proves nothing new.
5. **The thread log skill** still says eight Areas and that n8n holds no
   Notion credential. Tee's synced file; Tee's edit. The drain workflow
   side was fixed on 2026-09-06 (nine Areas, Raw in the body, dedupe).
6. **Execution retention.** The Router saves neither successes nor
   failures now. The other fourteen doors still save failed executions with
   the header inside; redaction is Upgrade gated on this plan (Tee's
   screenshot, 2026-09-06). Rotate on schedule; the KEY_ROTATION checklist
   is current at sixteen paths.
7. **The soul is unfed.** `devon-subconscious` was verified empty on
   2026-08-26 and nothing has written it since. Follows from item 2.
8. **EditForge renders** wait on the host env file (autonomy doc, runbook
   A) and the Zapier lane was never built. Both Tee's hands.
9. **The Face's stale line about EditForge** ("wait on the host env") is
   true today and will go stale the day runbook A is done; the prompt is in
   `n8n/devon/face/compose_prompt.js`.

## 6. Handover prompt for the next chat

Paste the block below as the first message of a new Claude Code session on
this repository. It assumes CLAUDE.md and the repository skills load on
their own, which they do in a web session.

```
You are continuing the DEVON close-out arc for Tee. Read CLAUDE.md first, then
docs/devon/SYS_OPS_devon-airtable-row-writer_v1_2026-09-06.md (this handover)
and docs/devon/SYS_OPS_devon-operational-report_v1_2026-09-06.md. Load the
steward skill before touching CI or a PR, estate-reconcile before checking
records, devon-learning-lane before touching the Build 12 lane.

Where things stand on 2026-09-06 at about 11:20Z:
- Branch claude/new-session-2f2yu2 carries PR #151 (draft): Build 17, the
  Airtable Row Writer, plus the Face and Intake edits. Drive it green, merge
  it under Tee's standing operational merge permission when all six checks
  pass, then restart the branch from origin/main under the same name. Merge
  commits are titled "Merge PR #151: <title>". Read the head SHA with git
  rev-parse origin/<branch> before merging, never from a doc.
- Job 01M1V6M3XG0RQR191QFF7W74WJ waits at WAITING_APPROVAL on card
  REQ-20260906-8kt8Vj (expires 2026-09-09T11:11:04Z). Tee approves it from
  the email. Then hand run the Driver Poll mbIKJk4UuB7V27rP (execute_workflow,
  manual mode) or wait for the hourly poll, and read back: the ledger row in
  data table VYyno7pDWmY6uxBz (project rM0TNTE2fNXErglU) should carry an
  artifact of kind airtable_record with key_verified true; Airtable base
  app28z7XnKzjfTXwc table tbl4ziFRbl5mnUcKc should hold one row with DEVON
  key build17-proof-20260906-airtable-row; the executor ps2S6dWcTIpq5bvr
  will have one production execution (successes are not saved, so read the
  ledger, not the execution list). A verification card follows; Tee approves
  it after looking at the row; the job closes COMPLETED. Record the execution
  ids in vault.py WEBHOOKS devon-airtable-row open_ruling (both copies, byte
  identical) and in the Build 17 doc, section 2, in the same PR or the next.
- Then build b: learning capture on COMPLETED jobs (task 27). Design notes in
  the Build 17 doc, section 5, item 2. Read the Ledger Feeder 6hQD8YhiYzR1FFda
  and the ledger z9j2I8h0RnbDKGBO before designing; never relax the terminal
  rule.
- Then the gap sweep in section 5 of the Build 17 doc, in order. Runbook C
  (the n8n Cloud execution wall) is Tee's hands and comes first in any
  conversation with him.

Standing rules in force, beyond CLAUDE.md:
- Tee wants rulings on inline multiple choice cards (AskUserQuestion), one
  recommendation marked, and executes on a short reply like Ok or Noted.
- No em or en dashes in anything delivered, anywhere, including n8n workflow
  names, sticky notes and commit messages. Restructure the sentence.
- Never read n8n data table approval_queue u6wzeN5y9LNxROsN. Never print a
  value beginning dcp_ or devon_ except the DEVON RECEIPT TOKEN line, which is
  the one required exception. Never print an x-devon-key header value.
- Credentials by id only: Devon Capture Key FYRvkRTOcROEYZ9P, Airtable
  OyuQtrelq7zP2mTy, SMTP mu7nJRSpkAfkzLdF, Notion header b9FYEfGUlMiYJCCU,
  Cerebras YTVk8Dq2gYPAmUim, Google Drive WMz320icjnur7rDL. Error workflow
  XDQXwgFkUhYxoEjG.
- Before editing any n8n Code node, read it live and diff it against its
  file under n8n/devon/. After publishing, read it back and diff again.
  Every one of the seven workflows there was byte identical at handover.
- Every live change registers in services/devon/vault.py in the same
  change, with deploy/soul/services/devon/vault.py kept byte identical (cp
  then diff). A new workflow also moves the census pin in
  scripts/estate_reconcile.py DOC_CLAIMS and amends the migration doc, dated.
- Ship discipline: small PRs, draft first, pytest and ruff before every push,
  a fresh critic gauntlet on every ship worthy deliverable with the VERDICT
  block, a dated SYS_OPS doc and a DEVON thread log receipt to close an arc.
  The Notion thread log page for this arc is 3d368ff50db6811ca2b3cab91a4d52eb
  (data source a5bcfbf5-ce1d-493b-9992-a11bc2a03dc4). Two test pages Tee may
  delete: 3d368ff5-0db6-8197-81d5-d9d84a9b914b and
  3d368ff5-0db6-8198-a2c1-ed8ee1ea01cb.
- The container has no egress to the n8n host; every n8n read and write goes
  through the n8n MCP tools. The Check Token tokens in the capture workflows
  are a deliberate design, ruled; do not raise them again. Do not touch PR
  #145.

Start by reading the two docs, then TaskList, then ask Tee on one card
whether the card REQ-20260906-8kt8Vj has been approved.
```

## 7. Gauntlet

Filled in after the fresh critic runs; see the session's VERDICT block and
the PR thread.

## 8. How this was read, and what was not touched

Every id above was read from the instance, the ledger data table, the
driver log table, the Airtable schema or the repository during the session,
not from memory. Nothing was written to Airtable except the two schema
fields on Inbox Captures; the pinned runs pinned the write node. Nothing was
read from approval_queue. The proof job is a real ledger row and a real
card in Tee's inbox; that was the point.
