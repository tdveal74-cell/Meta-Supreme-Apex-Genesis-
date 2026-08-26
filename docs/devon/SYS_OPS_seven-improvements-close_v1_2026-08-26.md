# Seven improvements close-out (v1, 2026-08-26)

Status doc for the 2026-08-26 session that continued and substantially
closed the seven estate improvements. Supersedes nothing; it is the
companion receipt to `SYS_OPS_devon-improvements-handoff_v1_2026-08-26.md`,
which was updated in place as each item landed and remains the per-item map.
Tee authorized merging and delegated in-arc decisions this session
("you have my permission to merge and make any decisions per your
recommendations").

## Scoreboard

| Item | State | Receipt |
|---|---|---|
| 1. Soul recall at the planning seam | DONE | PR #54, merged 59474e6; tests in `test_devon_agent_runtime.py`, `test_devon_soul_recall_seam.py` |
| 2. Council for gated jobs | DONE | `council.consult` + approval-card note; `test_devon_council_tool.py` |
| 3. First genuine PROMOTE | WAITS ON REAL WORK, by ruling | assessment in the handoff doc; no synthetic jobs, ever |
| 4. Upstream webhook auth flip | DONE | webhook `devon-build12-upstream` carries x-devon-key since 2026-08-26T01:56Z; vault + skill docs updated |
| 5. Ledger Janitor | PUBLISHED | workflow `HKNEDVy7PUKPtsrN`, active daily 02:30 UTC; registered in vault + skill |
| 6. Weekly table backup | PUBLISHED | workflow `qCfGZ1CwmpK9vOta`, active Sundays 03:10 UTC; dry run execution 3589 |
| 7. Build 14 reflection-to-intent | DEFERRED BY DESIGN | heartbeat needs a track record; revisit after a week or two of reflections |

Bonus, by direct request mid-session: the DEVON Command Center
(`apps/web/app/command-center/page.tsx`) now embeds the Operator Terminal
(extracted to `apps/web/components/terminal/OperatorTerminal.tsx`);
`/terminal` remains the full-screen variant and the home page routes to the
Command Center.

## What to watch next

- The eight stale Aug-24 E2E jobs are CLEARED. The janitor's on-demand run
  at 02:21Z (execution 3592) correctly swept nothing (jobs 42-49h old,
  under the 96h TTL); Tee then directed an immediate clear, so a one-time
  version-documented TTL override (96h to 24h) ran as execution 3593 at
  02:27Z and cancelled all eight through the guarded ledger webhook (every
  POST accepted, zero refusals, digest email sent), after which the 96h
  TTL was restored and republished. The heartbeat's stuck_jobs finding
  should be absent from the ~07:14 UTC pulse; a check-in at 07:35Z
  confirms the drain.
- The first weekly backup email lands Sunday 03:10 UTC with four CSV
  attachments. approval_queue is excluded on purpose; never add it.
- Item 3 completes itself the first time two real same-theme jobs run to
  COMPLETED through the ledger. Nothing further to build.
- Build 14 waits for reflection track record by its own design rule.

## Verification discipline used

Every repo change was validated to CI parity before push (per the steward
skill): full pytest suite against PostgreSQL 16 + pgvector (763 passing at
close), ruff clean, alembic upgrade / downgrade / upgrade round-trip. The
web change passed typecheck and production build, and both pages were
screenshot-verified in a headless browser. Both n8n workflows were
dry-tested before publish (janitor execution 3581 pre-session, backup
execution 3589 with Gmail pinned).
