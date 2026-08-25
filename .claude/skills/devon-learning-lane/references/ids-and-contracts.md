# Learning lane: live ids and payload contracts

Snapshot 2026-08-25. Ids are endpoints, not secrets (the API key is the
secret). Verify against `services/devon/vault.py` and the live n8n instance
before trusting in a much later session.

## n8n (thequietoperator.app.n8n.cloud)

| Thing | Id | Notes |
|---|---|---|
| Live State Ledger workflow (Build 02) | `z9j2I8h0RnbDKGBO` | webhook `devon-ledger`, header `x-devon-key`; states RECEIVED→…→COMPLETED/CANCELLED (terminal); legal transitions enforced |
| devon_state_ledger data table | `VYyno7pDWmY6uxBz` | one row per intent; `learning_state` belongs to the envelope and is rewritten on every upsert — never use it as a foreign marker |
| Ledger Feeder workflow | `6hQD8YhiYzR1FFda` | 15-min poll; feeds COMPLETED jobs once each |
| devon_build12_feed_log table | `QeoV4V4dYXXN8dBR` | intent_id, fed_at, webhook_status, gate_decision, claim, area (area may be empty; parse `. Area: X.` from claim as fallback) |
| Build 12 Upstream Test workflow | `VznESplSFCs8ldph` | webhook `devon-build12-upstream`; NO header auth (deliberate — see below); NOT editable via MCP |
| Approval Queue workflow | `syRVj0G47mA1b0Xn` | webhooks `devon-approve-request` (POST, x-devon-key) and `devon-approve-decide` (GET, token in link) |
| approval_queue table | `u6wzeN5y9LNxROsN` | status pending/approved/rejected; 72h expiry; contains a plaintext token column — never read it |
| Soul Committer workflow | `lANs6wopaK0PkNhN` | 15-min poll; propose + resolve branches; first draft `Wo7zPxpGH8kiBRy8` archived unpublished after adversarial review |
| devon_soul_commit_log table | `U9fnVy19Vc8kvQAw` | intent_id, state (PROPOSED/COMMITTED/REJECTED/EXPIRED/REVERTED), request_id, record_id, claim, area, proposed_at, resolved_at, note |
| Error Alarm workflow | `XDQXwgFkUhYxoEjG` | shared error workflow; emails Tee when a workflow that names it crashes out-of-band |
| Learning Lane Table Reader | `we45pHkQHRmSRnZx` | manual, read-only view of feed log + commit log; deliberately never reads approval_queue (token column) |

### Soul Committer v2 semantics (why it is shaped this way)

- One new approval POST per poll and one devon-soul commit per poll (oldest
  first): HTTP-response pairing stays 1:1, and a run cannot outlast the 15-min
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
| devon-subconscious | namespace `experience` | upstream workflow on PROMOTE |

Wire format: NDJSON upserts to `{host}/records/namespaces/{ns}/upsert`,
header `X-Pinecone-API-Version: 2025-04`.

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

AUTH: none — the webhook is deliberately unauthenticated (open ruling recorded
in `services/devon/vault.py` WEBHOOKS). The feeder sends `x-devon-key` anyway,
so header auth can be enabled later without breaking the automatic feed. Until
then anyone with the URL can POST candidate claims (and a caller-supplied
`source_intent_ids` list) into the gate; the stated safety is the gate itself —
PROMOTE alone writes, and only to devon-subconscious, never devon-soul. Weigh
this in any security review of the lane.

```json
{"claim": "...", "source_intent_ids": ["<ULID>"], "proposed_scope": "<area>",
 "confidence": 0.6-0.8, "source": "ledger-feeder", "ledger": {...provenance}}
```
Response body carries the gate decision (`decision`, e.g. PROMOTE /
REQUIRES_HUMAN / REJECT / HOLD); the feeder records it as `gate_decision`.
Gate promotes only on complete + clear + >= 2 independent sources, so a
single-job feed can never PROMOTE by itself.

## Approval queue contract

Request (POST devon-approve-request, x-devon-key): `title` and `what_happens`
REQUIRED (refused otherwise); optional `action_type` (vocabulary includes
identity_voice_rights, canon_change, deploy, …), `project`, `requested_by`,
`blast_radius`, `reversible`, `evidence`, `callback_url`.
Response: `{queued: true, request_id, expires_at}` — no token.
Decision: Tee taps the emailed approve/reject link; the row's `status`
becomes `approved`/`rejected` with `decided_at`. Rows never auto-expire in
the table; consumers must treat pending past `expires_at` as rejected.

Known queue defects (found 2026-08-25, reported to Tee, unpatched — live
workflow edits are permission-blocked from sessions):

1. Build Request's `rand()` uses signed shifts (`>>`); random words >= 2^31
   index `SET[negative]` and concatenate the literal text `undefined` into
   request ids and tokens (seen live: `REQ-20260825-Jundef`). Half of all id
   suffixes collapse to one of 62 strings, so same-day id collisions are
   realistic, and token entropy is far below design. Fix: `>>>` for the three
   shifted indexes in Build Request. Consumers must treat request ids as
   opaque and possibly colliding until patched.
2. Find Request scans only the 200 newest rows; a still-valid approval link
   for an older request denies with "No request found" once 200+ newer
   requests exist inside its TTL.
3. Record Decision runs AFTER Respond Decided with onError continue: the
   browser can show "Recorded" while the table write failed, silently losing
   a decision. This is why committer EXPIRED notes say "no recorded decision".

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
