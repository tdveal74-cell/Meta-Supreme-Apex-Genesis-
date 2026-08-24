---
title: DEVON Durable Shared Approval Authority Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: merge-authorized
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-durable-shared-approvals
pr: 28
pre_handover_verified_head: 87e9564949d5b008672304387d59597712852f34
pre_handover_ci_run: 32771790648
---

# DEVON Durable Shared Approval Authority Handover

## 1. Executive state

Tee explicitly authorized merge of PR #28 on 2026-08-24.

This handover is the final artifact added before merge. The merge gate remains evidence-based: the exact handover-inclusive branch head must pass the repository CI after this file is committed. Only that verified head may be merged.

PR #28 closes the process-local approval-state reliability gap by moving the API approval authority to PostgreSQL by default while keeping DEVON core framework-free and effect-free.

## 2. Canonical source inspected

The implementation and verification work was grounded against the current branch versions of:

- `services/devon/approval.py`
- `app/api/v1/devon.py`
- `app/services/devon_approval_store.py`
- `database/schemas/006_devon_approval_store.sql`
- `database/migrations/sql_script.py`
- `database/migrations/versions/001_baseline.py`
- `database/migrations/versions/004_federated_knowledge_waist.py`
- `database/migrations/versions/005_agent_runtime_persistence.py`
- `database/migrations/versions/006_devon_approval_store.py`
- `.github/workflows/ci.yml`
- `conftest.py`
- `test_devon_shared_approvals.py`
- `test_migration_sql_script.py`
- `deploy/soul/services/devon/approval.py`

## 3. Durable shared approval authority

The framework-free approval gate remains in `services/devon/approval.py`. Application database capability lives outside DEVON core in `app/services/devon_approval_store.py`.

Production/API behavior now uses PostgreSQL by default. `DEVON_APPROVAL_STORE=memory` is an explicit local/offline choice only. A PostgreSQL connection or operation failure raises a closed failure and does not silently fall back to process-local memory.

The PostgreSQL store persists the approval record, terminal ruling state, timestamps, consequence description, actor metadata, blast-radius metadata, expiry, and only the SHA-256 hash of the one-time approval token.

The plaintext token is returned only to the caller that creates the request. It is not persisted and is not recoverable from the database. Durable approval state therefore does not mean durable plaintext-token recovery.

Decision transitions are compare-and-set. A terminal ruling updates only a row still in `state='pending'`. When multiple workers race to rule on the same request, at most one can successfully perform the pending-to-terminal transition. Losing workers read the authoritative final state and refuse replay.

Overdue pending requests are durably moved to `expired` state.

## 4. Configuration contract

- `DEVON_APPROVAL_STORE=postgres` is the default behavior.
- `DEVON_APPROVAL_STORE=memory` selects the process-local store explicitly.
- `DEVON_APPROVAL_DATABASE_URL` optionally overrides the application database URL for approval storage.
- `DEVON_APPROVAL_CONNECT_TIMEOUT_SECONDS` controls the bounded connection timeout.
- Invalid backend names fail configuration rather than selecting a weaker backend.
- PostgreSQL errors do not trigger an automatic memory fallback.

## 5. Database and deployment chain

### Revision 005

PR #25 had already shipped Agent Runtime raw SQL persistence used by tests, but the production Alembic chain still ended at revision 004. PR #28 adds `005_agent_runtime_persistence.py` so a fresh Alembic deployment installs the same Agent Runtime tables that the application already depends on.

### Revision 006

`006_devon_approval_store.py` installs `database/schemas/006_devon_approval_store.sql`, including:

- `devon_approvals`
- allowed-state constraint
- 64-character lowercase hexadecimal token-hash constraint
- expiry-after-creation constraint
- terminal decision-shape constraint
- state/expiry and created-time indexes

### PostgreSQL raw-SQL migration executor

The repository's baseline migration previously passed an entire multi-command SQL file to SQLAlchemy's asyncpg dialect as one prepared statement. asyncpg rejects that pattern.

`database/migrations/sql_script.py` now scans PostgreSQL SQL and executes one top-level statement at a time on Alembic's existing transactional connection. It preserves:

- single-quoted strings
- double-quoted identifiers
- dollar-quoted PostgreSQL bodies
- line comments
- nested block comments
- semicolons inside quoted/function bodies

Malformed unterminated quoting/body/comment state fails rather than guessing.

Baseline revision 001 and raw-schema revisions 005 and 006 use this executor.

### Revision 004 ownership repair

Fresh-deploy verification exposed a historical migration conflict: baseline 001 already creates `embeddings.updated_at`, while revision 004 attempted to add the same column again.

Revision 004 now ensures that column exists with `ADD COLUMN IF NOT EXISTS` for historical databases that may predate the baseline field, but no longer claims ownership of it. Its downgrade no longer removes the baseline-owned column.

## 6. Security and governance boundary

- DEVON core still performs no approved external effect.
- The approval store records requests and human rulings only.
- The caller remains responsible for performing an approved effect after a successful approval result.
- Plaintext approval tokens are never persisted by the PostgreSQL adapter.
- Database unavailability fails closed.
- Human ruling authority remains Tee's. No model is granted authority to approve its own high-impact action.
- The hosted Soul vendored approval module remains byte-for-byte synchronized with the canonical approval core so the deployment-integrity guard remains meaningful.

### Multi-worker boundary

PR #28 makes approval-state decisions shared and race-safe across workers. It does not make the entire Agent Task execution system multi-worker-safe.

Two workers can no longer both win the same approval ruling. However, concurrent task resumes could still race an external effect unless task execution itself has leasing/idempotency protection. A task-execution lease/idempotency layer remains the next load-bearing reliability step before the whole runtime may be described as multi-worker-safe.

## 7. Verification defects caught and repaired

### Hosted Soul vendored module drift

An early PostgreSQL suite failed because `deploy/soul/services/devon/approval.py` had drifted from `services/devon/approval.py` after the approval-core change. The deployed copy was synchronized byte-for-byte. The deployment-integrity test was preserved rather than weakened.

### Baseline Alembic multi-command failure

Fresh Alembic deployment failed because asyncpg would not prepare the complete baseline SQL file as one statement. The PostgreSQL-aware script executor described above repaired the deployment path.

### Parser regression-test false positive

A parser test originally selected every statement containing `FUNCTION update_updated_at_column`, which also matched trigger statements that call that function. The test was corrected to target only the `CREATE OR REPLACE FUNCTION update_updated_at_column()` definition. The parser itself was not weakened.

### Revision 004 duplicate baseline column

Fresh Alembic deployment then exposed the duplicate `embeddings.updated_at` ownership between baseline 001 and revision 004. Revision 004 was repaired to preserve baseline ownership and remain compatible with historical databases.

## 8. Artifacts in PR #28

1. `.github/workflows/ci.yml`
2. `app/api/v1/devon.py`
3. `app/services/devon_approval_store.py`
4. `conftest.py`
5. `database/migrations/sql_script.py`
6. `database/migrations/versions/001_baseline.py`
7. `database/migrations/versions/004_federated_knowledge_waist.py`
8. `database/migrations/versions/005_agent_runtime_persistence.py`
9. `database/migrations/versions/006_devon_approval_store.py`
10. `database/schemas/006_devon_approval_store.sql`
11. `deploy/soul/services/devon/approval.py`
12. `requirements.txt`
13. `services/devon/approval.py`
14. `test_devon_shared_approvals.py`
15. `test_migration_sql_script.py`
16. `docs/devon/SYS_OPS_devon-durable-shared-approval-authority-handover_v1_2026-08-24.md`

## 9. Pre-handover verification evidence

Verified feature head before this handover:

`87e9564949d5b008672304387d59597712852f34`

GitHub Actions run:

`32771790648`

Results:

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- API suite, PostgreSQL 16 + pgvector: PASS
- Full repository suite: `660 passed, 4 warnings in 66.62s`
- Fresh `alembic upgrade head`: PASS through revisions 001 to 006
- `alembic downgrade 004_federated_knowledge_waist`: PASS
- Re-upgrade from 004 through 006: PASS
- Final database table/revision verification: PASS
- Ruff: `All checks passed!`

The four warnings are existing Starlette/FastAPI deprecation warnings and are not approval-store test failures.

## 10. Final merge gate

This handover changes the branch head. Therefore the pre-handover green run is not sufficient to merge by itself.

Required final sequence:

1. Let CI run against the exact handover-inclusive branch SHA.
2. Require all repository lanes, including PostgreSQL, fresh Alembic round trip, and Ruff, to pass.
3. Merge PR #28 using that exact expected head SHA under Tee's explicit merge authorization.
4. Verify GitHub reports the PR merged and closed.

## 11. Next load-bearing layer

After PR #28, the next reliability layer is task-execution leasing/idempotency for concurrent resumes and external effects. That layer is separate from shared approval-state authority and should be completed before browser automation, subagents, and scheduled workers are described as fully multi-worker-safe.
