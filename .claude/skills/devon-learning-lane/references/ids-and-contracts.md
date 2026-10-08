# Learning lane: live ids and payload contracts

Snapshot 2026-08-25, ids repointed to the VPS 2026-09-15. Ids are endpoints,
not secrets (the API key is the secret). Verify against
`services/devon/vault.py` and the live n8n instance before trusting in a much
later session.

Ruled by Tee 2026-09-15: every DEVON organ runs on the VPS, live and published.
Every workflow and data table id below is the VPS copy's. The Cloud instance
(thequietoperator.app.n8n.cloud) held these organs from the first build until
that evening; a Cloud id in an older doc or an execution number in a note is
history, and the two instances share no ids.

## n8n (n8n.editforge.online)

| Thing | Id | Notes |
|---|---|---|
| Live State Ledger workflow (Build 02) | `hDmTRI5VAZ3a8sTn` | webhook `devon-ledger`, header `x-devon-key`; states RECEIVED→…→COMPLETED/CANCELLED (terminal); legal transitions enforced |
| devon_state_ledger data table | `QZvdxllOjWevb3Vo` | one row per intent; `learning_state` belongs to the envelope and is rewritten on every upsert — never use it as a foreign marker |
| Ledger Feeder workflow | `GEbNoDMBdGqDfZJ2` | daily poll at 02:00 instance time (15-min until 2026-09-05); feeds COMPLETED jobs once each; since Build 18 (2026-09-06) a second branch off Fetch Feed Log posts one `LEARNING_CAPTURED` per fed, unmarked job to `devon-event` with `learning` set to `{state: captured, captured_at, by: ledger-feeder, gate_decision, feed_status}`, a COMPLETED to COMPLETED same state update; the feed log stays the only dedupe key, a mark the bus did not persist emails Tee and is retried next run; source in `n8n/devon/ledger-feeder/` |
| devon_build12_feed_log table | `U0PqQWiq4nadKFlm` | intent_id, fed_at, webhook_status, gate_decision, claim, area (area may be empty; parse `. Area: X.` from claim as fallback) |
| Build 12 Upstream Test workflow (the gate) | `VzJsSlDswkIJ9wok` | webhook `devon-build12-upstream`; header auth `x-devon-key` ON since 2026-08-26 (credential Devon Capture Key); MCP-available since 2026-08-26; active version `dc307024` since 2026-10-08 (the critic's fixes to `e4da9aed`, which was grouping Phase 1; before that `17f51ee2`, then `a8b070c5`): grouping Phase 1, a preflight refuses before any search and a single job HOLDs, see the payload section below; repo copy of every Code node in `n8n/devon/learning-gate/`; saves no successful executions, errors go to the OS Error Handler `GbeNilHQzjmoWDz3` |
| Approval Queue workflow | `Ia28EHrxtiI8cjeA` | webhooks `devon-approve-request` (POST, x-devon-key) and `devon-approve-decide` (GET, token in link) |
| approval_queue table | `AomDw2Oa9XCUluRX` | status pending/approved/rejected; 72h expiry; contains a plaintext token column — never read it |
| Soul Committer workflow | `drP96ernQvbrvzIZ` | hourly poll since 2026-09-06 (15-min before; Tee's ruling on the execution burn, version `49007534`); propose + resolve branches; first draft `Wo7zPxpGH8kiBRy8` archived unpublished after adversarial review |
| devon_soul_commit_log table | `x8U4QqvXTVgINg3h` | intent_id, state (PROPOSED/COMMITTED/REJECTED/EXPIRED/REVERTED), request_id, record_id, claim, area, proposed_at, resolved_at, note |
| Error Alarm workflow | `bqcnIS0Qv4RkTCU1` | shared error workflow; emails Tee when a workflow that names it crashes out-of-band |
| Learning Lane Table Reader | `VGwrZPdZ5se2pr03` | manual, read-only view of feed log, commit log, state ledger, heartbeat log; deliberately never reads approval_queue (token column) |
| Heartbeat workflow (Build 13) | `EEDrp2jLlw2Ssd5b` | 6h pulse: vitals, keyed findings, roughly daily email; see `references/heartbeat.md` |
| devon_heartbeat_log table | `RuPMZKXkqcbuHRKa` | beat_at, kind (pulse/reflection), vitals, findings, reflection, emailed |
| Daily Reflection Routine | `trig_01XCKFGEbojhkPRnNbMd8yCP` | claude.ai Routine, 11:30 UTC, writes one reflection row; see `references/heartbeat.md` |
| Ledger Janitor workflow | `V0i8zTw1keMMJmhF` | daily 02:30 America/New_York (timezone pinned 2026-09-07; it was implicit and this table said UTC, which was wrong by four hours, measured from executions 5202 through 6330 all firing 06:30 UTC); sweeps jobs non-terminal past 96h to CANCELLED through the guarded `devon-ledger` webhook (legal transitions enforced; VERIFYING two-steps FAILED then CANCELLED); envelope history preserved plus a janitor trace note; digest email only when it acted |
| Weekly Table Backup workflow | `rVXA5wH5AXW4tCjp` | Sundays 03:10 America/New_York (timezone pinned 2026-09-07; it was implicit and this table said UTC, which was wrong by four hours, measured from execution 6126 firing 07:10 UTC on Sunday 2026-09-06); read-only export of the four learning-lane tables to CSV, one email with four attachments; approval_queue EXCLUDED on purpose (plaintext decision tokens — mailing them would let inbox access approve soul writes) |
| Intake Former workflow (Build 14) | `TciVQhWJA0y92x9P` | webhook `devon-intake` (POST, x-devon-key); forms one v1 envelope at RECEIVED from `{text}` (Cerebras tags, vocabulary validated, no Area means refused) or a structured job, then calls the Job Driver synchronously and answers with where the job stopped; `dry_run: true` returns the envelope without driving it |
| Job Driver workflow (Build 14) | `MfJCYeJqVjBLFrCu` | sub-workflow, no trigger of its own; one pass advances one job through the organs as far as it legally can and stops at every human gate; reads approval_queue only by evidence marker `intent <id>; card approval` or `card verify` and copies only request_id, status, timestamps (never the token column); execution data persistence OFF; chooses the executor once when the approval card is raised, names it on the card and binds it into `intent.payload.action`, then dispatches that action and nothing else; posts a router refusal into the ledger as ACTION_FAILED at the same state, once per distinct reason; source in `n8n/devon/job-driver/` |
| devon_driver_log table | `EHrmGJfmOKNJJcc4` | one row per driver pass: intent_id, pass_at, execution_id, origin (intake or poll), entry_state, exit_state, outcome, steps, detail, approval_card, verify_card |
| Driver Poll workflow (Build 14) | `6b4dJasBKcOPQ6oX` | hourly; reads the ledger, hands every open non-terminal job (RECEIVED through VERIFYING; never FAILED or BLOCKED) to the Job Driver one at a time, skips rows written in the last 3 minutes; digest email only when a job moved or an organ refused, and a refusal whose reason repeats the previous pass is listed as still waiting rather than mailed again; source in `n8n/devon/driver-poll/` |
| Face workflow (Build 15) | `sPv6Cq7elbjoi5Nw` | n8n hosted chat, n8n user auth; Cerebras gpt-oss-120b answers as DEVON with the ledger, driver log and heartbeat in context; files or dry-runs jobs through `devon-intake`; never reads approval_queue |
| Action Router workflow (Build 05) | `NYcEp03Oqlvq86Mb` | webhook `devon-action` (POST, x-devon-key); dispatches an AUTHORIZED envelope to an allowlisted executor (spine.echo at ceiling read, drive.draft at ceiling reversible_write); since 2026-09-05 a refusal answers as data: refused true, reason, intent_id, state, action, known_actions, HTTP 200, and an executor's own refusal is carried through with the reason posted into the ledger (receipt says marked true); successful executions are not saved |
| Drive Draft Writer workflow (Build 16) | `FdQgiX2Thgk38CSa` | webhook `devon-drive-draft` (POST, x-devon-key), called only by the Action Router as action `drive.draft` at ceiling reversible_write; requires a granted, unexpired approval on every envelope whatever the blast radius label says; the entry report carries a single flight lock (execution running under this workflow, ten minute age out) and nothing is written unless the ledger took it; finds an existing draft by idempotency key and intent id, Cerebras writes the draft, one Google Doc in the DRAFT_FOLDERS folder for the Area, the file is read back under its key so the artifact records properties_verified, advances AUTHORIZED to EXECUTING with the artifact; refusals answer as data; source in `n8n/devon/drive-draft-writer/`; successful executions are not saved |
| devon_chat_log table | `DKCusDJfIF8CPxyb` | Face memory, one row per turn: session_id, role (user or assistant), content, at, action (none, file_job, dry_run), intent_id; no tokens, no secrets |

### Soul Committer v2 semantics (why it is shaped this way)

- One new approval POST per poll and one devon-soul commit per poll (oldest
  first): HTTP-response pairing stays 1:1, and a run cannot outlast the poll
  schedule (executionTimeout 300s backs this).
- Before POSTing, the propose lane reconciles against approval_queue itself:
  an existing `requested_by: soul-committer` row whose `evidence` starts with
  `intent <intent_id>;` is ADOPTED under its existing request_id (approved
  status preferred, else newest). A lost POST response therefore heals instead
  of double-raising the card, and a decision Tee made on the "lost" card is
  honored.
- `what_happens` carries the FULL claim — what Tee approves is byte-for-byte
  what gets committed.
- EXECUTION DATA PERSISTENCE IS OFF (success, error, manual). The resolve lane
  reads full approval_queue rows and the live queue stores plaintext decision
  tokens; persisted executions would let an execution-reader self-approve a
  soul write. Truth lives in the data tables and digest emails; use the Table
  Reader workflow to inspect. Do not turn saving back on.
- Stuck-state guards: queue statuses `refused`/`denied` close as REJECTED and
  `expired` as EXPIRED; a PROPOSED row whose queue row is missing, unparseable,
  or in an unknown state closes EXPIRED 24h past the 72h TTL (measured from
  proposed_at). EXPIRED notes say "no recorded decision" because the queue
  answers the browser before writing the decision and swallows a failed write.
- Commit failures keep the row PROPOSED with an attempt counter in the note;
  failure alerts are damped to the first attempt and roughly every 4 hours.

## Pinecone (integrated embedding llama-text-embed-v2, cosine, field map text)

| Index | Host | Writes |
|---|---|---|
| tee-soul-layer | `https://tee-soul-layer-jw37oa2.svc.aped-4627-b74a.pinecone.io`, namespace `rulings` | Soul Layer Write-Back only; READ-ONLY from the learning lane |
| devon-soul | `https://devon-soul-jw37oa2.svc.aped-4627-b74a.pinecone.io`, namespace `experience` | Soul Committer only, approval-gated |
| devon-subconscious | `https://devon-subconscious-jw37oa2.svc.aped-4627-b74a.pinecone.io`, namespace `experience` | upstream workflow on PROMOTE |

Wire format: NDJSON upserts to `{host}/records/namespaces/{ns}/upsert`,
header `X-Pinecone-API-Version: 2025-04`.

devon-subconscious was verified EMPTY on 2026-08-26: its only record
(`4YZ5HG555ZFRY69RPNH0SP3B7B`, a Build 12 upstream test write from
2026-08-25 with placeholder source_intent_ids
`01ABCDEFGHJKLMNPQRSTUVWX01/02`) was purged at Tee's direction, with
fetch-before and fetch-after receipts in n8n execution 3625. The first
record ever written there must come from real completed work. The
committer smoke (`SMOKE-COMMITTER-V2-20260825`, feed row
`webhook_status 0`) never wrote the subconscious; it was injected at
the committer propose path only, and its devon-soul record was already
deleted under the REVERTED ruling.

## devon-soul service (deploy/soul on Vercel, devon-soul.vercel.app)

Auth: `CONSOLE_TOKEN` Bearer. Read-only by invariant; the ONE non-GET route is
`POST /api/v1/soul/conflict-search` (a recall query, writes nothing —
`test_deploy_soul.py` pins this).

### Conflict-search receipt (policy b12.1)

Request: `{claim (>=8 chars after strip), sources?, top_k?, context?}`.
Response keys (contract pinned by `test_deploy_soul_conflict_policy.py`):
`receipt_id, complete, sources, conflict_status, matched_records, notes,
policy, issued_at, issued_by`. Each matched record carries
`id, text, score, band, source, kind, heading, area, dated`.

Bands by cosine score: `<=0` unknown (requires_human), `<0.35` weak (may
clear), `0.35–0.60` adjacent (requires_human), `>=0.60` strong
(requires_human; with prohibition language in the text → `conflict`).
`clear` is withheld unless the recall was complete, both souls were read with
no partial errors, AND no retrieval window came back full with its score floor
at or above 0.35 (a saturated window can hide a live ruling below the cutoff).
Timeout is a hard 12s. Thresholds live as constants in `deploy/soul/main.py`
(`CONFLICT_WEAK_BELOW`, `CONFLICT_STRONG_AT`); change them there, run the
tests, ship through a PR — never by editing the deployed service.

## Webhook payload: feeder → devon-build12-upstream

AUTH: header `x-devon-key` (flipped on 2026-08-26, closing the open ruling
that was recorded in `services/devon/vault.py` WEBHOOKS). The feeder was
already sending the key, so the automatic feed never noticed the flip; an
anonymous POST now gets 403 instead of reaching the Candidate Former. The
gate remains the second line of defense: PROMOTE alone writes, and only to
devon-subconscious, never devon-soul.

```json
{"claim": "...", "source_intent_ids": ["<ULID>"], "proposed_scope": "<area>",
 "confidence": 0.6-0.8, "source": "ledger-feeder", "ledger": {...provenance}}
```
That is the `kind: "job"` shape; `kind` is absent on every feeder POST and
defaults to job. From Phase 3 a second shape exists, `kind: "lesson"`:
`{"kind": "lesson", "lesson_key": "<slug>", "learning_intent_id": "<ULID>",
"source_intent_ids": ["<ULID>", ...2 to 5]}`, with NO claim (the gate reads
the claim from the registry). The response body carries the decision at
`gate.decision`; the feeder records it as `gate_decision`.
Gate promotes only on complete + clear + >= 2 independent sources, so a
single-job feed can never PROMOTE by itself. Measured 2026-10-07: the feeder
sends exactly one id, so HOLD_SUBCONSCIOUS is the best any fed job can get,
and the subconscious write, the Soul Committer and the Approval Queue are
unreachable from real work. Ruled the same day: group related jobs so they
can clear the two-source bar, spec first.

Gate behaviour since version `e4da9aed` (grouping Phase 1, ruled by Tee
2026-10-08; tested on a throwaway stub copy, executions 2412 to 2423, then
published, read back, and probed live through the real door with the real
header, execution 2424), and as amended by `dc307024` the same day after the
critic (draft run in manual mode, executions 2430 and 2431, then published
and read back byte for byte). The code is `n8n/devon/learning-gate/` in the
repo and `node n8n/devon/learning-gate/gate.test.mjs` drives it:

- Candidate Former is a PREFLIGHT, and every refusal is DATA, never a
  throw: the webhook answers 200 with `gate.decision` set, `receipt: null`
  and `gate.search_spent: false`, from the node Refuse Before Search. In
  order: `REJECT_MALFORMED` (body not an object, unknown kind, ids not a
  list of strings, any id not a ULID after trim and upper case, a repeat
  once case is ignored, a job with other than exactly one id, a lesson
  carrying a claim, a bad `learning_intent_id` or `lesson_key`, fewer than
  2 or more than 5 lesson ids, and from `dc307024` a body too large or too
  deep to scan whole: more than 8 levels, 2000 strings or 16384 characters,
  bounded before any pattern runs, so hostile input cannot throw or hold the
  runner); `REJECT_SECRET` (a field NAMED like a
  credential with any value, the reference gate's rule, or any string
  shaped like a credential this estate holds, the list in
  `services/devon/lesson_registry.py` SECRET_SHAPES, pinned equal by
  `test_devon_lesson_registry.py`); `REJECT_WEAK_EVIDENCE` (a job claim
  missing or under 12 characters).
- A single job answers `HOLD_SUBCONSCIOUS` with NO conflict search spent.
  So REQUIRES_HUMAN and REJECT_CONFLICT no longer appear on the job path,
  and the 2026-10-07 poison job (a claim over the service's 2000 character
  limit retrying a 422 forever) cannot happen for a job any more, because
  a job never reaches the issuer.
- Every lesson answers `REJECT_UNREGISTERED` ("the lesson path is not
  enabled yet") until Phase 3 creates the registry and group log tables
  and sets `LESSON_PATH_ENABLED`. So NOTHING can reach the search branch or
  PROMOTE in Phase 1.
- The search branch is made correct for Phase 3, unreachable today:
  Assemble Result reads the candidate from Search Needed; the Learning Gate
  promotes only `kind: "lesson"` with a `verified_count` that equals the
  length of `verified_ids`, every member a distinct ULID once case is
  ignored (from `dc307024`), and meets `min_sources` (never the caller's id
  count); Build Record keys the subconscious record on
  `learning_intent_id` (a retry rewrites the same record), adds `kind`,
  `status: active`, `lesson_key`, `conflict_check_receipt_id` and the top
  match, and throws without a valid id or a list of distinct members;
  Write Result THROWS
  on a non-2xx upsert instead of answering 200 PROMOTE with `ok: false`.
- Every consumer of the decision was read on 2026-10-08 and treats it as
  an opaque string: the feeder logs any 200 as fed and terminal, the Pulse
  only flags an EMPTY decision, the Soul Committer filters `eq PROMOTE`.
  The feeder's email footer still says the gate rules "PROMOTE or
  REQUIRES_HUMAN"; it is incomplete rather than false and was left alone.

History, superseded in part by `e4da9aed` above: refusals are now data rather than
thrown `REFUSED:` messages, and a job no longer reaches the issuer.

Gate behaviour since version `17f51ee2` (ruled by Tee 2026-10-07; drafted,
tested by hand on executions 2384 to 2387, reviewed by two read-only critics
with no blockers, then published and read back):

- No test fallbacks. A claim that is missing, not text, or under 12
  characters, or a body with no `source_intent_ids`, throws `REFUSED: ...`.
  Before, the first was replaced with a canned claim and the second with two
  fabricated ids, exactly the PROMOTE threshold. Ids are trimmed and upper
  cased before duplicates are dropped, so one job cannot count twice.
- The issuer body is built with `JSON.stringify`, so a quote, backslash or
  newline in a job summary can no longer break it. Proved on 2384 to 2387
  with all three in the claim.
- The issuer runs with `fullResponse` and a 25s timeout (under the feeder's
  30s). Assemble Result throws on a non-2xx answer, on a 2xx that is not a
  receipt, and on `complete: false` (timeout, provider error, or both souls
  unread). The webhook then answers 500, so the feeder logs FAILED, emails,
  and re-feeds the job on its next run instead of logging REQUIRES_HUMAN as
  fed forever. A partial read (`complete: true`, `conflict_status`
  requires_human) is still a legitimate REQUIRES_HUMAN and is still fed.
  The 500 path itself is reasoned from n8n and the feeder code, not yet
  executed: manual runs do not answer an HTTP caller or fire the error
  workflow.
- Every failure message names the first source id, and carries no colon or
  line break of its own, because n8n's Code node keeps only the text after
  the LAST colon of a thrown message, and only its first line. Measured on
  2385: `REFUSED: no source_intent_ids` arrived as description `REFUSED`
  and message `no source_intent_ids ...`.
- RESOLVED for jobs by `e4da9aed`, since a job never reaches the issuer.
  Was open, ruled to Tee rather than built: a job that can never pass (for
  example a claim over the service's 2000 character limit, which answers
  422) has no exit. It fails, emails and retries every day until someone
  intervenes, and the only manual exit is a hand-written feed log row.

## Approval queue contract

Request (POST devon-approve-request, x-devon-key): `title` and `what_happens`
REQUIRED (refused otherwise); optional `action_type` (vocabulary includes
identity_voice_rights, canon_change, deploy, …), `project`, `requested_by`,
`blast_radius`, `reversible`, `evidence`, `callback_url`.
Response: `{queued: true, request_id, expires_at}` — no token.
Decision: Tee taps the emailed approve/reject link; the row's `status`
becomes `approved`/`rejected` with `decided_at`. Rows never auto-expire in
the table; consumers must treat pending past `expires_at` as rejected.

Queue defects found 2026-08-25. Status re-read from the live workflow
definition (version `c85c41ee`) on 2026-10-07; the table and the run data were
not read:

1. FIXED. Build Request's `rand()` used signed shifts (`>>`), so random words
   >= 2^31 indexed `SET[negative]` and put the literal text `undefined` into
   request ids and tokens (seen live: `REQ-20260825-Jundef`). It now uses
   unsigned shifts (`>>>`) over `crypto.getRandomValues`, and the canvas note
   says not to change them back. Ids minted before the fix can still carry
   `undefined`; treat request ids as opaque.
2. OPEN. Find Request still reads only the 200 newest rows, unfiltered, and
   matches in Check Decision; a still-valid approval link for an older
   request denies with "No request found" once 200+ newer requests exist
   inside its TTL.
3. PARTLY FIXED. The order is now Check Decision, then Record Decision, then
   Respond Decided, so the browser is no longer answered first. But Record
   Decision still sets onError continueRegularOutput, so a failed table write
   still reaches Respond Decided and the page can still say "Recorded" for a
   decision that never landed. This is why committer EXPIRED notes say "no
   recorded decision".

## Soul record shape (committer → devon-soul)

Mirrors `SoulWriteCandidate.to_record()` in `services/intelligence/soul.py`:
```json
{"_id": "devon-<YYYY-MM-DD>-<FULL request_id>", "text": "<claim>", "kind": "lesson",
 "area": "...", "observed_on": "YYYY-MM-DD",
 "source_note": "Build 12 learning gate PROMOTE; source intent ...; approval ...",
 "author": "devon", "approved": true}
```
`kind` must be one of lesson/correction/pattern/preference (ALLOWED_KINDS).
The `_id` embeds the FULL request id with its case intact (example:
`devon-2026-08-25-REQ-20260825-Ab12Cd`), so it derives deterministically from
the approval — retries upsert the same record and two distinct approvals can
never fold to one id (Pinecone `_id`s are case-sensitive; never lowercase).
