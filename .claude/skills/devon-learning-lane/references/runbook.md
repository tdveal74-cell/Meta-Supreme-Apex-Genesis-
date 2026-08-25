# Learning lane runbook

## Where the truth lives

Each stage keeps its own receipt. Read them in this order when something looks
wrong:

1. `devon_state_ledger` — did the job actually reach COMPLETED? (terminal
   states: COMPLETED, CANCELLED; only COMPLETED feeds.)
2. `devon_build12_feed_log` — one row per fed job. `webhook_status` is the
   HTTP code read back; `gate_decision` is what the gate answered. A missing
   row means the feeder has not fed it yet (or its POST failed and is
   retrying — a failure emailed a digest).
3. `devon_soul_commit_log` — one row per PROMOTE proposal.
   PROPOSED = awaiting Tee (an APPROVAL NEEDED email exists);
   COMMITTED = written, `record_id` names the devon-soul record;
   REJECTED / EXPIRED = closed forever.
4. `approval_queue` — the decision record itself (status/decided_at).
5. Pinecone console — the only proof a committed record really exists.
   Digest emails say so explicitly: verify before trusting.

## Email vocabulary (all from Gmail, senderName tells you the organ)

- "APPROVAL NEEDED: Soul commit: …" — the queue asking Tee to rule. Links
  expire after 72h; no decision is a rejection.
- "Build 12 feeder: N job(s) fed…" — feed digest; FAILED lines retry next poll.
- "Soul Committer: N record(s) committed…" — commits landed (verify in console).
- "Soul Committer: … FAILED" / "closed without commit" — failures and closures.
- Silence = nothing happened. Every poll with zero work sends nothing.

## Failure semantics (what retries vs what stops)

| Failure | Behavior |
|---|---|
| Feeder POST to webhook fails | not logged as fed; retried next poll; digest alerts |
| Approval request POST fails | no commit-log row; retried next poll; digest alerts |
| Soul upsert fails after approval | row stays PROPOSED with a note; approval stands; retried under the SAME record id (no duplicate possible) |
| Workflow crashes between commit and log update | next poll re-upserts same id, then updates the log — self-healing |
| Proposal rejected or expired | terminal; never re-raised |
| Same job re-reported COMPLETED to the ledger | feeder feeds once per intent (feed log is the dedupe, not the ledger's learning_state) |

## Rules for touching things

- Conflict policy: edit `deploy/soul/main.py` in the repo, run
  `test_deploy_soul_conflict_policy.py` + `test_deploy_soul.py`, ship by PR.
  The deployed service updates on Vercel deploy of main.
- Live n8n workflows: prefer creating a new additive workflow over editing a
  live organ; if editing, export/read the JSON first and keep the sticky-note
  documentation truthful. The Build 12 Upstream workflow is not editable via
  MCP by design.
- Any new webhook or workflow: register it in `services/devon/vault.py`
  (WEBHOOKS / WORKFLOWS, mirrored byte-identically in
  `deploy/soul/services/devon/vault.py`) in the same change — the map's own
  rule: one path, one job, listed before a collision can route silently.
- Nothing in this lane updates Drive, Notion, or canon unless Tee explicitly
  instructs in the current session.

## Trust ladder for the gate

The gate is young. Confidence grows from receipts: feed digests accumulate
gate decisions; PROMOTE stays rare (needs >= 2 independent sources + a clear
receipt); every soul commit is individually human-approved. If the gate
misbehaves, the conservative rollback is unpublishing the feeder or committer
workflow (each is additive and stops cleanly) — never loosening the approval
gate.
