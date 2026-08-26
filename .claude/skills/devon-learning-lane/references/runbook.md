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
   REJECTED / EXPIRED = closed forever;
   REVERTED = a commit that was manually undone after a mistaken approval —
   the devon-soul record was deleted by exact id and the row is terminal.
   No workflow writes REVERTED; it only ever comes from a hand-run,
   receipted reversal (first instance: the 2026-08-25 smoke card, approved
   by mistake, committed at 20:15Z, deleted and reverted at 20:23Z).
4. `approval_queue` — the decision record itself (status/decided_at).
5. `devon_heartbeat_log` — the Build 13 pulse writes vitals and keyed
   findings every 6h; a healthy estate shows fresh pulse rows even when the
   inbox is silent. Details: `references/heartbeat.md`.
6. Pinecone console — the only proof a committed record really exists.
   Digest emails say so explicitly: verify before trusting.

The committer persists NO execution data (deliberate: approval tokens must
never land in stored executions), so its n8n execution history is empty by
design. Inspect the feed log and commit log with the read-only Table Reader
workflow instead; never add an approval_queue read to it.

## Email vocabulary (all from Gmail, senderName tells you the organ)

- "APPROVAL NEEDED: Soul commit: …" — the queue asking Tee to rule. Links
  expire after 72h; no decision is a rejection.
- "Build 12 feeder: N job(s) fed…" — feed digest; FAILED lines retry next poll.
- "Soul Committer: N record(s) committed…" — commits landed (verify in console).
- "Soul Committer: … FAILED" / "closed without commit" — failures and closures.
- "DEVON Janitor: N stale job(s) cancelled…" — the daily 02:30 UTC sweep
  cancelled jobs non-terminal past 96h through the ledger. REFUSED lines mean
  the ledger said no or the POST failed (left as-is, swept again next day);
  SKIPPED lines (unreadable envelope or unknown state) need hand repair — the
  heartbeat's stuck_jobs finding keeps alerting on them until fixed.
- Silence = nothing happened. Every poll with zero work sends nothing.

## Failure semantics (what retries vs what stops)

| Failure | Behavior |
|---|---|
| Feeder POST to webhook fails | not logged as fed; retried next poll; digest alerts |
| Approval request POST fails or its response is lost | no commit-log row; next poll reconciles against approval_queue by evidence and ADOPTS the request if the queue stored it anyway — the card is never raised twice, and a decision Tee made on it is honored |
| Soul upsert fails after approval | row stays PROPOSED with an attempt counter in the note; approval stands; retried under the SAME record id (no duplicate possible); alerts damp to first failure + roughly every 4h |
| Workflow crashes between commit and log update | next poll re-upserts same id, then updates the log — self-healing |
| Committer crashes anywhere (node error) | the Error Alarm workflow emails Tee out-of-band — in-band digests cannot fire from a dead run. ONLY the committer names the Error Alarm in its settings today; a crashed FEEDER or QUEUE alerts nobody, so when the lane stalls, check those two in the n8n executions list before trusting silence |
| Feed-log row has webhook_status 200 but empty/garbled gate_decision | the gate answered 200 with a body the feeder could not parse a decision from; the intent is logged as fed (never re-fed) and invisible to the committer — terminal and near-silent (the feed digest line just lacks the ", gate ..." suffix). Repair: determine the gate's real decision (upstream execution history, or re-run the claim through the gate manually), then manually correct the feed-log row's gate_decision; a corrected PROMOTE enters committer intake on the next poll |
| Proposal rejected, refused, or expired | terminal; never re-raised |
| Queue row deleted / unknown status / bad expires_at | commit-log row closes EXPIRED 24h past the 72h TTL from proposed_at — nothing can stick silently forever |
| Same job re-reported COMPLETED to the ledger | feeder feeds once per intent (feed log is the dedupe, not the ledger's learning_state) |
| Job stuck non-terminal past 96h | the Ledger Janitor (daily 02:30 UTC) sweeps it to CANCELLED through the guarded ledger webhook, VERIFYING legally two-stepping FAILED then CANCELLED; a row with an unreadable envelope or unknown state is skipped and named in the digest — repair the envelope by hand, and the heartbeat's stuck_jobs finding keeps alerting until the row goes terminal |
| Tee approves a card by mistake | there is NO in-band undo: the queue records decisions immutably and the committer will write on its next tick. Unpublish the committer FIRST, then check the commit log. If it already committed, reverse by hand with receipts: delete the devon-soul record by its exact `record_id` (Pinecone `/vectors/delete`), verify with a fetch, and set the commit-log row to REVERTED with a note naming the ruling — then republish. The approve and reject links sit adjacent in the email; slow down on that tap |

## Rules for touching things

- Conflict policy: edit `deploy/soul/main.py` in the repo, run
  `test_deploy_soul_conflict_policy.py` + `test_deploy_soul.py`, ship by PR.
  The deployed service updates on Vercel deploy of main.
- Live n8n workflows: prefer creating a new additive workflow over editing a
  live organ; if editing, export/read the JSON first and keep the sticky-note
  documentation truthful. The Build 12 Upstream workflow became MCP-available
  on 2026-08-26 (it was blocked before); its webhook carries header auth from
  the same date.
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
