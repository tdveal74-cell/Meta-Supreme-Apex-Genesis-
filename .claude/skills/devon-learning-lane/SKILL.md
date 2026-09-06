---
name: devon-learning-lane
description: >
  Operate, debug, or extend the DEVON Build 12 learning lane: the path from a
  completed job in the Build 02 state ledger, through the Ledger Feeder and the
  devon-build12-upstream webhook, the conflict-search receipt issuer on the
  devon-soul service, the Learning Gate, the subconscious writer, and the
  approval-gated Soul Committer. Use when a session touches the learning gate,
  conflict policy, PROMOTE decisions, devon-subconscious or devon-soul writes,
  the feeder or committer workflows, or their data tables; when asking why
  something did or did not PROMOTE or commit; when tuning conflict thresholds;
  or when building or modifying ANY DEVON n8n workflow (the house conventions
  reference applies estate-wide).
---

# DEVON Learning Lane (Build 12)

How DEVON learns from completed work without ever quietly rewriting his own
past. Every stage below is live and was proven end to end on 2026-08-25.

## The lane

```
Build 02 state ledger (n8n data table, jobs one row per intent)
  → Ledger Feeder (daily poll since 2026-09-05: COMPLETED jobs, fed once each;
     since 2026-09-06 it also marks each fed job's envelope learning.state
     captured through the Event Bus, one LEARNING_CAPTURED per job)
    → devon-build12-upstream webhook
      → Candidate Former → Conflict-Search Issuer → Learning Gate
        (issuer = POST /api/v1/soul/conflict-search on devon-soul.vercel.app,
         the ONLY trusted receipt source; gate PROMOTEs only on
         receipt.complete && conflict_status "clear" && >= 2 independent sources)
        → PROMOTE writes devon-subconscious/experience (automatic)
        → PROMOTE also enters the Soul Committer intake:
           proposal → DEVON Approval Queue email → Tee decides
           → approved: ONE record into devon-soul/experience
           → rejected or expired: closed forever
```

Weak conflict matches (score < 0.35) clear; adjacent and strong matches stop at
a human; a strong match carrying prohibition language is a conflict. Full
policy semantics, every live id, and every payload contract:
`references/ids-and-contracts.md`.

## Posture — do not relax without a ruling from Tee

1. The candidate NEVER supplies its own conflict receipt; the issuer on the
   devon-soul service is the only receipt source, and status:active filtering
   is the service's job, not the caller's.
2. devon-soul is written by the Soul Committer ONLY, and the committer never
   writes alone: every record is individually approved through the DEVON
   Approval Queue first. No smoke or test writes to devon-soul, ever.
3. tee-soul-layer is read-only from this entire lane. The committer workflow
   deliberately contains no tee host string, so a misfire cannot reach it.
4. Feeding is not approval; PROMOTE is not a soul write. Each escalation has
   its own gate.
5. One proposal per intent, ever. Rejected and expired proposals stay closed;
   no decision is the same as a rejection.
6. Status codes are read back, never assumed. A failure alerts by email and
   retries; it is never silently logged as success.
7. Secrets live in host environment settings only (CONSOLE_TOKEN,
   PINECONE_API_KEY). Never in Drive, never in a skill, never in a workflow
   note. The approval queue's token column is never read by any lane code.

## Components at a glance

| Component | Where | Detail |
|---|---|---|
| Conflict policy b12.1 | repo `deploy/soul/main.py` (tests: `test_deploy_soul_conflict_policy.py`) | code + tests are canonical |
| Ledger Feeder | n8n workflow, daily poll (15-min until 2026-09-05) | feeds once each, then mirrors the feed log onto the envelope as LEARNING_CAPTURED (Build 18, 2026-09-06); ids in reference |
| Upstream gate | n8n workflow (webhook, x-devon-key since 2026-08-26) | receipt contract in reference |
| Soul Committer | n8n workflow, hourly poll (15-min until 2026-09-06, Tee's ruling on the execution burn) | state machine in reference |
| Vault map | repo `services/devon/vault.py` WEBHOOKS/WORKFLOWS | keep truthful on every change |
| Heartbeat (Build 13) | n8n pulse + claude.ai reflection Routine | continuity and self-monitoring, `references/heartbeat.md` |
| Ledger Janitor | n8n workflow, daily 02:30 UTC | sweeps jobs non-terminal past 96h to CANCELLED through the guarded ledger webhook; ids in reference |
| Weekly Table Backup | n8n workflow, Sundays 03:10 UTC | mails the four learning-lane tables as CSVs; approval_queue excluded on purpose (token column); ids in reference |

## Which reference to read

- Changing thresholds, payloads, or debugging a decision →
  `references/ids-and-contracts.md`
- Something looks stuck, failed, or silent → `references/runbook.md`
- Building or modifying any DEVON n8n workflow →
  `references/n8n-conventions.md` (applies estate-wide, not just this lane)
- The Heartbeat: the 6h pulse, the daily reflection, or the
  devon_heartbeat_log → `references/heartbeat.md`

## Provenance

Compiled 2026-08-25 from the Build 12 close-out session that shipped the
banded conflict policy (PR #44), the Ledger Feeder, and the Soul Committer,
each proven live with receipts (merged PRs, live executions, digest emails).
The repo's code and tests outrank this skill wherever they disagree; the live
n8n workflow JSON outranks the reference's description of it. Verify ids
against `services/devon/vault.py` before trusting them in a new session.
