---
title: DEVON Airtable Row Writer (Build 17), the close-out, and the handover
type: SYS_OPS
version: 1
date: 2026-09-06
area: Systems
status: live-on-cloud-first-job-completed
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
Pinned runs 6171 to 6173 prove the write, the refusal and the reuse branches.
The live gated job (`01M1V6M3XG0RQR191QFF7W74WJ`) was parked at
WAITING_APPROVAL on card `REQ-20260906-8kt8Vj` with the executor bound and
named when this document was first written, and it said so: nothing in it
claimed the row existed. Amended the same day at 11:36Z: Tee approved the
card at 11:32:16Z, a hand run of the Driver Poll (execution 6200, driver
pass 6202) carried the job to AUTHORIZED, through the router, into the
executor (execution 6208), and to VERIFYING. The row exists:
`recKhlOqdAG0Zju30` in Inbox Captures, both stamp fields read back directly
from Airtable, artifact `key_verified true`, `ledger_clean true`. Tee
approved the verification card `REQ-20260906-vED3ik` at 12:04:12Z, and
driver pass 6238 (Driver Poll run 6236, 12:08:11Z) closed the job COMPLETED
with `verification.state passed`, `method human_watch`, `human_watched
true` and a completed receipt. That is the whole lane, end to end, on a
real job: intake, spine, runtime, route, card, grant, router, executor,
row, verification card, human watch, terminal state. A fresh critic read
the whole diff in between and its findings were closed the same hour
(section 7).

## 1. What was built

### The executor, `ps2S6dWcTIpq5bvr`

Sixteen functional nodes plus one sticky note, created from validated SDK
source and read back node by node (fifteen functional nodes until 11:41Z,
when the `Write?` guard below was added on the critic's finding).
Door `Row In (POST)` at path `devon-airtable-row`, header auth on credential
`FYRvkRTOcROEYZ9P` (Devon Capture Key, by id). `Validate and Plan` holds the
gates the Drive Draft Writer holds (schema 1.0.0, ULID, AUTHORIZED only,
blast radius no wider than `reversible_write`, a granted and unexpired
approval on every envelope whatever the label says, the single flight mark
described below, an idempotency key of 8 to 128 characters with no
whitespace, quotes, braces or backslashes because it is quoted into an
Airtable formula and stamped on the row verbatim (whitespace added 11:41Z; a
key was collapsed before, so the stamp could differ from the ledger key), no
EditForge payload) and then the allowlist: `TABLES` maps a table name to its id, the two
stamp fields and a rule per writable field (text with a length cap, date as
YYYY-MM-DD, select as one option name, multi select as a list of option
names; a date must also be a calendar date that exists, since V8 reads
2026-02-30 as March 2 and Airtable would refuse it). Anything outside it
refuses with the writable tables or fields named. The executor never sends
`typecast`, so an option that does not exist on a select field is Airtable's
422 and comes back as a refusal naming Airtable's own error type. It never
defaults a field the job did not name.

`Report Entry to Bus` posts INTENT_RECEIVED with `execution.state running`
under this workflow id. That mark is the single flight rule, and this
document first called it a ten minute lock, which overclaims (critic,
2026-09-06): the mark lives only in the ledger row, and the router's failure
exit rewrites that row from its pre dispatch envelope, so it does not
survive a failed pass. What actually stops a second row is the Driver Poll
skipping any job touched inside three minutes and the search by both stamp
fields before every write. The residual window is two passes loading the
row before either entry report lands, which the hourly poll plus a hand run
inside the same seconds could produce. `Find Existing Row` is an HTTP
GET on the Airtable API with the predefined Airtable token credential
`OyuQtrelq7zP2mTy` (by id), `filterByFormula` on both stamp fields and
`maxRecords` 3, full response, never error. `Check Existing` refuses unless
the ledger persisted the entry report, refuses unless the search answered
200, and re-reads both stamp fields on every hit so a row carrying this key
under another job's id is ignored rather than adopted. `Write?` (added
11:41Z) sits between `Existing?` and the write: a Check Existing refusal
used to flow straight into `Write Row`, which had no url to call and threw,
so a designed refusal became an execution error and the reason was lost.
It now reaches `Return Refusal` as data; pinned runs 6224 (search answers
429) and 6225 (ledger refuses the entry report) prove it, and 6226 proves
the write path still passes through the guard. `Write Row` is an HTTP POST
of `{ fields }` with the same credential. `Row Result` refuses on
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
Active version `d16f002c` at first publish, `486c243d` since 11:41Z.

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
Inbox Captures table of the DEVON base (payload fingerprint 65a13f8e),
titled X, carrying the fields A, B, C as the job declares them plus DEVON
key and DEVON job. Body begins: ... Reversible by deleting the row. Nothing
is published or sent". The fingerprint (FNV-1a over the canonical payload,
eight hex characters, not a secret) and the Body excerpt were added at
11:49Z on the critic's finding that a list of field names is not consent to
a value nobody saw; the same line is kept in `approval.card_executor`, and
at AUTHORIZED the driver recomputes the fingerprint and parks the job
(`bound_payload_mismatch`) when the payload no longer produces the one the
card carried. The binding into `intent.payload.action` at card time and the
action mismatch park are unchanged. Active version `ea93e3ac` at first
publish, `f33c65ed` since 11:49Z.

Intake Former `AEFgXee7IDJarNV7`: Form Job keeps a structural
`payload.airtable` (table name, a flat fields object of strings, lists of
strings, numbers or booleans, at most 12 fields, 20000 characters per value,
20 items per list) and Apply Tags floors any Airtable row job at
`reversible_write` so a card is always raised. Before this edit the intake
kept only `editforge`, `auto_verify` and `note` from a poster's payload, so
the executor built an hour earlier was unreachable from every door. Active
version `0a6cf6c0`. Amended at 11:50Z on the critic's findings (`207ae1cc`):
a value over a bound is refused with the bound named rather than cut to fit
(the first version sliced a 20001 character Body to 20000 and dropped a
thirteenth field silently, a transformation the first law says to refuse);
an idempotency key carrying whitespace, quotes, braces or backslashes is
refused at the door, the union of what both executors refuse, so a bad key
cannot pass the intake, raise a card, and burn the grant at the executor;
and an Airtable row job labelled wider than `reversible_write` is refused,
because the driver binds `airtable.row` at exactly that radius and a wider
label would card the job as a spine echo and park it with the grant spent.

Face `LsmfRFMmI5feINs0`: the system prompt said "a Drive draft is next" a
day after the draft writer went live. It now names the three executors and
what selects each, and the reply format lets the model attach an `airtable`
object (table Inbox Captures, the seven permitted fields, substance in
Body). Parse Reply carries that object into the job payload untouched; the
intake bounds it and the executor holds the allowlist. Active version
`1ccd11b9`; `1c9e6662` since 11:48Z, when Attach Receipt was taught to show
the table, the Title, the field names and how the Body begins on a dry run,
so what Tee says "file it" to is what the card will carry.

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
| The first real row | Tee approved `REQ-20260906-8kt8Vj` at 11:32:16Z (decided_by tee, grant decays 2026-09-07T11:32:16Z). Driver Poll hand run 6200 at 11:36:18Z; driver pass 6202 (origin poll, six steps, WAITING_APPROVAL to VERIFYING, `ledger_clean true`): APPROVAL_GRANTED, router dispatched `airtable.row` to `ps2S6dWcTIpq5bvr` execution 6208, row written, Spine EXECUTING to VERIFYING, verification card `REQ-20260906-vED3ik` raised (expires 2026-09-09T11:36:28Z). Ledger artifact: kind `airtable_record`, `recKhlOqdAG0Zju30`, seven fields, `reused false`, `key_verified true`, created 11:36:25Z. Direct Airtable read of the record: Title, Captured 2026-09-06, Kind Note, Source Other, Area Systems, Body, Notes as declared, `DEVON key build17-proof-20260906-airtable-row`, `DEVON job 01M1V6M3XG0RQR191QFF7W74WJ`. The same pass found the other open job's card `REQ-20260905-f5kEZj` still pending (pass 6201) |
| The close | Tee approved verification card `REQ-20260906-vED3ik` at 12:04:12Z. Driver Poll hand run 6236 at 12:08:11Z; driver pass 6238 (origin poll, two steps, VERIFYING to COMPLETED): queue read approved, bus VERIFICATION_PASSED, ledger update accepted. Ledger row: `state COMPLETED`, `terminal true`, `verification passed / human_watch / human_watched true / verified_at 12:08:11Z`, `execution succeeded` on `ps2S6dWcTIpq5bvr` execution 6208 (kept, per Tee's ruling 3), `receipt.outcome completed`, `artifact_count 1`, `trace_count 23`, `learning.state not_captured` (build b's target). The same pass found card `REQ-20260905-f5kEZj` still pending (pass 6237) |
| ACX on the Area field | Tee added the option in the Airtable UI after ruling on it at about 12:05Z; read back at 12:08Z: `fldpbMPz2xBcEo0Ia` now carries nine choices, ACX as `selu5krZ25DLbIMi4` |
| Pinned runs, the Write? guard | execution 6224: Find Existing Row pinned to HTTP 429, Check Existing refused, `Existing?` false, `Write?` false, Return Refusal answered the reason, Write Row never ran. Execution 6225: entry report pinned `persisted false`, same path, Write Row never ran. Execution 6226: happy path through `Write?` true, Row Result `key_verified true`, Return Envelope, `ledger_clean true` |
| Republished after the critic | executor `486c243d` (11:41Z), Face `1c9e6662` (11:48Z), Job Driver `f33c65ed` (11:49Z), Intake Former `207ae1cc` (11:50Z); all 23 live Code nodes of the four workflows diffed against `n8n/devon/` after publishing: identical |
| Face dry run | execution 6194: asked to show what it would file, the model returned action `dry_run` with an `airtable` object (Title, Captured, Kind, Source, Area, Body), Parse Reply carried it into `payload.airtable`, the intake formed envelope `01M1V6VN93D9V3EVQRZ613ATJT` with the payload intact and filed nothing |
| Census | 64 workflows, 39 active, from the project listing at 11:07Z |
| Deploy read back of the previous merge | Railway `941318bb` SUCCESS on `b8fffb1` with the alembic context lines; devon-soul `dpl_44y1ogZqxPyVdw7mhVaCQmHdZTUa` READY production on `b8fffb1`; nothing owed to the web project |
| Repository | This row first read "199 tests pass, ruff clean" against commit 4c14e3f and again against 5c94df5. That was false, and the critic re-measured it: at 4c14e3f, dac7859 and 5c94df5 the same selection was 1 failed, 198 passed, the failure being the census pin test that still said 63 while the pin and this doc said 64. The commit that moved the pin did not run the test that guards it. Fixed in aac9d5e; CI green on all six checks from that commit. Amended 2026-09-06 rather than rewritten, because the first law says a wrong claim gets dated, not deleted |

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

- **The first real row.** Proven at 11:36Z (section 2, "The first real
  row"); this bullet said "no row has been written" until then, and until
  12:08Z it said the close was not proven. It is: Tee approved the
  verification card at 12:04:12Z and pass 6238 closed the job COMPLETED
  (section 2, "The close"). Nothing about the proof job is unproven now.
- **The refusal and reuse branches live.** Proven on pinned data only (6172,
  6173, 6224, 6225). The live path has run once, on the happy branch.
- **The payload fingerprint on a live card.** The driver change at 11:49Z is
  proven in a Node harness (card carries the fingerprint and the Body
  excerpt, same payload dispatches, a changed Body parks with
  `bound_payload_mismatch`, key order does not matter, a card without a
  fingerprint dispatches as before) and by the live node reading back
  identical; no job has been carded through it live yet. The proof job's
  card predates it and carries no fingerprint, which is the legacy path.
- **The intake refusals live.** Same: harnessed on the exact node bodies
  (20001 characters refused, 13 fields refused, 21 items refused, a key with
  a quote or a space refused, an irreversible airtable job refused) and read
  back identical; not yet exercised through the door.
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
10. **ACX is missing from the Inbox Captures Area field.** Read live by the
    critic: the field (`fldpbMPz2xBcEo0Ia`) has eight options, TQO, Podcast,
    NCO, Health, Money, Family, Learning, Systems, and no ACX. The Face and
    the intake accept nine Areas, so a chat filed ACX capture would raise a
    card, be approved, and park at AUTHORIZED on Airtable's 422 with the
    grant spent. RULED 2026-09-06 by Tee, on a card: add ACX to the field in
    Airtable. The Airtable connector cannot add a select option (its field
    update takes a name, a description or a formula only), so it was Tee's
    click in the Airtable UI, done and read back at 12:08Z: nine choices,
    ACX as `selu5krZ25DLbIMi4`. CLOSED. The Kind, Source and Area
    vocabularies of Inbox Captures
    are recorded nowhere in the vault; adding them is a record without a
    check until a keyed reconcile can read the Airtable schema, so it waits
    on item 3.
11. **Small ones the critic named and this session left.** The Face key
    hashes the summary only, so two captures with the same wording in one
    session collide at Dedupe (reported, not silent). The chat log stores
    the dry run job cut at 4000 characters, so a very long Body makes the
    stored proposal unparseable and "file it" files the model's
    re-derivation. `card_executor` is kept at 500 characters, so a long
    Title plus the Body excerpt loses the tail in the ledger (the card
    itself is whole). `Area` allows nine items against eight options.

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

Where things stand on 2026-09-06 at about 12:00Z:
- Branch claude/new-session-2f2yu2 carries PR #151 (draft): Build 17, the
  Airtable Row Writer, plus the Face and Intake edits. Drive it green, merge
  it under Tee's standing operational merge permission when all six checks
  pass, then restart the branch from origin/main under the same name. Merge
  commits are titled "Merge PR #151: <title>". Read the head SHA with git
  rev-parse origin/<branch> before merging, never from a doc.
- Job 01M1V6M3XG0RQR191QFF7W74WJ is COMPLETED (12:08:11Z, driver pass 6238,
  human_watched true). The row recKhlOqdAG0Zju30 exists in Inbox Captures
  (base app28z7XnKzjfTXwc, table tbl4ziFRbl5mnUcKc), artifact key_verified
  true, executor execution 6208. The whole lane has run end to end on a real
  job once. It carries learning.state not_captured, which is exactly what
  build b (task 27) exists to change; use it as the first fed job.
- The critic's findings on Build 17 were closed live at 11:41Z to 11:50Z
  (executor 486c243d, Face 1c9e6662, driver f33c65ed, intake 207ae1cc) and
  every live Code node of those four workflows reads back identical to
  n8n/devon/. Tee ruled on 2026-09-06 that ACX goes onto the Inbox Captures
  Area field and added it himself; read back at 12:08Z as selu5krZ25DLbIMi4
  (Build 17 doc, section 5, item 10, closed).
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

Start by reading the two docs, then TaskList. Nothing on the proof job is
open; the first question for Tee is whether PR #151 merges now (six checks
green on the head, read them yourself) and whether build b starts.
```

## 7. Gauntlet

A fresh critic (a subagent given the diff b8fffb1..aac9d5e, the ask and the
touched surfaces, none of the build rationale) read every node body under
`n8n/devon/`, both vault copies, the test, this doc and the reconciler,
read the four live workflows and the Inbox Captures schema read only, ran
the pinned tests at each commit in a scratch clone, and drove a Node
harness against the actual `validate_and_plan.js` and `decide.js`. It
wrote nothing. Verdict as returned: **PASS-WITH-CONDITIONS**, scores scope
fidelity 4, correctness 3, unverified claims 2, security 4, reversibility
5, silent failure 3, idempotency 4, traceability 3, observability 4,
completeness 4, maintainability 4, Flagship Bar 3.

What it found and what was done, all on 2026-09-06:

| # | Finding | Disposition |
|---|---|---|
| 1 | Merge condition. `Existing?` false wired straight into `Write Row`, so a Check Existing refusal (non 200 search, entry report not persisted) reached the HTTP node with no url and threw: the designed refusal became an execution error, the Error Alarm mailed, and the reason was lost. Inferred from the graph, and confirmed here by reading the live connections. | Fixed live 11:41Z: `Write?` If node routes a refused item to `Return Refusal`. Pinned 6224 (429 search), 6225 (entry report refused), 6226 (happy path). Executor `486c243d`. |
| 2 | Merge condition. "199 tests pass, ruff clean" was false at 4c14e3f, dac7859 and 5c94df5 (1 failed, 198 passed, the census pin test). | Amended in section 2, dated, with the re-measurement. |
| 3 | The intake truncated silently (Body to 20000, a 13th field dropped, a 21st list item dropped). | Fixed live 11:50Z: every bound refuses with the bound named. Harnessed. Intake `207ae1cc`. |
| 4 | Idempotency key charset checked at the wrong door: a key with a quote or a brace passed the intake, raised a card, and was refused by the executor with the grant burned. | Fixed live 11:50Z: the intake refuses whitespace, quotes, braces and backslashes, the union of both executors. The executor also refuses whitespace instead of collapsing it (the stamp must equal the ledger key). |
| 5 | Inbox Captures `Area` has eight options and no ACX; the Face offers nine. | Ruling for Tee, section 5 item 10. Not changed. |
| 6 | The card named fields, never values; Body written unseen; the dispatch check compared the action name only. | Fixed live 11:49Z: fingerprint and Body excerpt on the card and in `card_executor`; dispatch parks on a changed payload. Face dry run receipt shows the values (11:48Z). Harnessed. Driver `f33c65ed`, Face `1c9e6662`. |
| 7 | A Face filed airtable job labelled `irreversible_write` was carded as a spine echo and would park at the router with the grant spent. | Fixed live 11:50Z: Apply Tags refuses an airtable job wider than `reversible_write`. Harnessed. |
| 8 | "Ten minute single flight lock" overclaimed. | Reworded in the executor comment, section 1 and the vault ruling: what the mark covers and what actually prevents a second row. |
| 9 | Nits: 4000 character chat log cut, Face key collision, `2026-02-30` accepted, whitespace collapsed in the key, nine Area items against eight options, "sixteen nodes". | Date and key fixed live; the rest recorded in section 5 item 11 and section 1. |
| 10 | Verified as claimed: KEY_ROTATION counts, byte identical vault copies, the test regex, the File Job forward, pinned run 6171, zero dashes, blast radius one row, the header key holder's reach as KEY_ROTATION states it. | No action. |

Re-verification after the fixes: harnesses on the exact node bodies for
the executor gates, Decide, Form Job, Apply Tags and Attach Receipt; pinned
runs 6224 to 6226 on the published executor; every live Code node of the
four republished workflows diffed against `n8n/devon/`, identical; the
199 test selection and ruff on the amended tree (receipt in the commit).
The VERDICT block for the whole deliverable is in the session's final
message and repeated in the PR thread.

## 8. How this was read, and what was not touched

Every id above was read from the instance, the ledger data table, the
driver log table, the Airtable schema or the repository during the session,
not from memory. Nothing was written to Airtable by hand except the two
schema fields on Inbox Captures; the one row that exists was written by the
executor through the approved job, and the pinned runs pinned the write
node. Nothing was read from approval_queue. The proof job is a real ledger
row, a real card Tee approved, and a real record; that was the point.
