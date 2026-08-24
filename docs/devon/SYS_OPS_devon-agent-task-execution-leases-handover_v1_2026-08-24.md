---
title: DEVON Agent Task Execution Leases Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: handover-filed-pending-final-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-task-execution-leases
pr: 29
base_main: bdf8ac23873cd86d998f3db49a33776604dbcc3d
pre_handover_verified_head: 0f370ad6a9e2ae54ebea6cdc99fb269faec7897b
pre_handover_ci_run: 32775321659
---

# DEVON Agent Task Execution Leases Handover

## 1. Executive state

This layer closes the multi-worker task overwrite race that remained after PR #28 made DEVON approvals durable and shared.

Before this branch, `DurableAgentTaskService.run_until_blocked()` restored a durable task into an in-process runtime, executed it, and then saved the resulting snapshot. Two API workers could therefore restore the same pre-run task state, execute it concurrently, and race to overwrite the same durable task row.

PR #29 introduces one database execution lease per task, fencing tokens, heartbeat renewal, a durable run/replay ledger, and request idempotency semantics at the API boundary. The layer remains outside `services/devon`; DEVON core continues to perform no effect execution.

Pre-handover code head `0f370ad6a9e2ae54ebea6cdc99fb269faec7897b` passed all repository CI lanes in run `32775321659`, including 667 PostgreSQL-backed tests, migration 007 upgrade/downgrade/re-upgrade, and Ruff. This handover commit intentionally moves the branch head, so the handover-inclusive head must pass the same CI gate before the PR is review-ready.

## 2. Load-bearing boundary

The changed-file accounting before this handover contained no file under `services/devon/`.

Execution control remains split as follows:

- `services/devon/`: judgment and approval contracts only; unchanged by this PR.
- `app/services/agent_tasks.py`: application coordinator that acquires the durable task lease before invoking runtime capability adapters.
- `app/services/agent_runtime_persistence.py`: PostgreSQL claim, fencing, run-ledger, completion, failure, and mutation exclusion logic.
- capability adapters: remain the effect boundary.
- PostgreSQL: shared arbitration authority for task execution ownership and replay records.

This PR does not move shell, GitHub, network, or other effect capability into DEVON core.

## 3. Database contract

Migration head becomes `007_agent_task_execution_leases`.

### `agent_tasks` additions

- `lease_token VARCHAR(64)`
- `lease_owner VARCHAR(200)`
- `lease_expires_at TIMESTAMPTZ`
- `execution_generation BIGINT NOT NULL DEFAULT 0`

`execution_generation` increases on every successful lease acquisition. A random lease token is the fencing credential used by heartbeat, completion, and failure writes.

### `agent_task_runs`

A durable execution-request ledger records:

- task and owner
- caller `Idempotency-Key`
- request hash bound to `max_steps`
- state: `running`, `completed`, or `failed`
- lease token and worker identity while active
- attempt count
- sanitized replay result
- error, timestamps, and completion time

Unique constraint: `(owner_id, task_id, idempotency_key)`.

## 4. Atomic lease claim

`AgentTaskRepository.acquire_execution()` performs an atomic PostgreSQL `UPDATE ... WHERE` against the task row.

A claim succeeds only when:

- the task belongs to the caller, and
- there is no lease token, or
- lease expiry is absent, or
- the lease has expired.

A successful claim writes a fresh random token, worker identity, expiry, and increments `execution_generation` in the same statement. The task snapshot and new generation are returned from that atomic write.

If another live worker owns the row, the second claim receives `TaskExecutionBusy` and the API returns HTTP 409.

## 5. Fencing and stale-worker rejection

A worker may persist the execution result only when its lease token still matches the task row and its run-ledger row.

`complete_execution()` refuses stale results if either fence no longer matches. This prevents a worker whose lease expired from overwriting a newer worker's task state after takeover.

The heartbeat renews the lease using a separate database session while the capability runtime is active. A failed renewal marks the local lease as lost; the worker will not commit its task result afterward.

When an expired lease is taken over under a different idempotency key, any abandoned `running` ledger row for that task is closed as `failed` with:

`superseded after execution lease expired`

The old lease credential is removed from that row and the stale worker remains fenced from task completion.

## 6. Idempotency semantics

`POST /api/v1/agent-tasks/{task_id}/run` accepts the standard `Idempotency-Key` header.

The response includes:

- `Idempotency-Key`
- `Idempotent-Replay: true|false`

A completed request with the same task, owner, idempotency key, and `max_steps` returns the durable result without running capability adapters again.

Reusing the same key with different `max_steps` fails with HTTP 409.

A run previously recorded as failed does not silently execute again under the same key. The caller must make an explicit new execution request.

Important limit: this layer provides concurrency fencing and replay safety after a result is durably committed. It does not claim crash-atomic exactly-once external effects. If an adapter effect succeeds and the process dies before the result is durably committed, the outcome is ambiguous. Adapter-native idempotency keys and durable effect receipts are the next hardening layer.

## 7. Approval-token security rule

The first runtime call that reaches an approval boundary still returns the one-time approval token to the authenticated caller so Tee can decide the request.

That plaintext token is never persisted in `agent_task_runs.result`.

Before a run result enters the replay ledger, the application copies the response and replaces top-level `approval_token` with `null`. Therefore:

- the token is delivered once to the caller,
- the PostgreSQL replay ledger does not contain it,
- replaying the same idempotency key does not reissue it,
- the original credential remains usable until the approval gate consumes or expires it.

This preserves the hash-only approval-token discipline established in PR #28.

## 8. Mutation exclusion

While a task has a live execution lease, these competing mutations fail closed with HTTP 409:

- cancel
- rollback
- delete
- a second run claim

Read-only task inspection remains available.

Expired lease metadata may be cleared when a mutation obtains the task row lock; a live lease is never cleared by those mutation paths.

## 9. Real concurrency regression

`test_devon_agent_task_lease_concurrency.py` creates two independent SQLAlchemy sessions and races them simultaneously for the same task with `asyncio.gather()`.

Acceptance assertions require:

- exactly one `won`
- exactly one `busy`
- task `execution_generation == 1`
- task lease token equals the winning claim token
- exactly one `agent_task_runs` row remains `running`

This is a real PostgreSQL row-contention test, not only a sequential simulation.

## 10. Security regression

`test_devon_agent_task_lease_security.py` drives an approval-gated `operator.command` through the real API.

It proves:

1. the first caller receives a non-empty approval token,
2. the durable `agent_task_runs.result` stores `approval_token: null`,
3. the plaintext token is absent from the persisted result representation,
4. same-key replay returns `Idempotent-Replay: true` with no token reissue,
5. the original one-time token still successfully decides the approval afterward.

## 11. Lease and takeover regressions

`test_devon_agent_task_leases.py` covers:

- completed approved effect replay does not execute the effect a second time,
- same idempotency key cannot substitute different run parameters,
- a live lease blocks a second worker, cancel, and delete,
- an expired lease can be taken over,
- execution generation increases on takeover,
- the abandoned run is durably closed as superseded,
- the old worker cannot commit or renew with its stale token.

## 12. CI and migration gate

`.github/workflows/ci.yml` now requires:

- schema file `007_agent_task_execution_leases.sql`,
- migration file `007_agent_task_execution_leases.py`,
- `agent_task_runs` after migration,
- all four task lease columns,
- Alembic head exactly `007_agent_task_execution_leases`.

The database lane performs:

1. full repository pytest against PostgreSQL 16 + pgvector,
2. `alembic upgrade head`,
3. downgrade to `004_federated_knowledge_waist`,
4. upgrade back to head,
5. table/column/revision verification,
6. Ruff.

## 13. Verification history and defects caught

### Initial candidate

Initial PR head: `df676d9505c716f6dcf558d8dd00ee355aebbf6b`

CI run: `32774431897`

Evidence:

- standalone lane: passed,
- engine/security lane: passed,
- PostgreSQL test suite: 665 passed, 4 warnings,
- migration 007 round trip: passed,
- Ruff: failed with one `I001` import-format error in `app/models/agent_runtime.py`.

The Ruff error was repaired rather than waived.

### Audit defect: abandoned running ledger row

Manual review found that a different-key takeover after lease expiry would fence the old worker but could leave its run-ledger row marked `running` forever.

Repair: successful takeover now closes abandoned running rows as `failed / superseded after execution lease expired`. The stale-worker regression directly verifies that row state.

### Audit defect: plaintext approval token replay persistence

Manual review found that persisting `RuntimeResult.to_dict()` unchanged would store a one-time approval token in `agent_task_runs.result` when execution stopped at an approval boundary.

Repair: replay persistence sanitizes `approval_token` to `null`. A dedicated security regression proves non-persistence and no token reissue.

### Stronger concurrency evidence

The first regression set proved post-commit exclusion but did not exercise a true simultaneous database race. A two-session `asyncio.gather()` race was added before acceptance.

### Pre-handover accepted code head

Head: `0f370ad6a9e2ae54ebea6cdc99fb269faec7897b`

CI run: `32775321659`

Evidence:

- standalone lane: passed,
- engine/security lane: passed,
- PostgreSQL lane: passed,
- full suite: 667 passed, 4 warnings in 69.57s,
- migration 007 upgrade/downgrade/re-upgrade: passed,
- Ruff: all checks passed.

This is pre-handover evidence only. The handover-inclusive head must be verified again.

## 14. Artifacts in PR #29

Modified:

- `.github/workflows/ci.yml`
- `app/api/v1/agent_tasks.py`
- `app/models/__init__.py`
- `app/models/agent_runtime.py`
- `app/services/agent_runtime_persistence.py`
- `app/services/agent_tasks.py`
- `conftest.py`

Created:

- `database/migrations/versions/007_agent_task_execution_leases.py`
- `database/schemas/007_agent_task_execution_leases.sql`
- `test_devon_agent_task_lease_concurrency.py`
- `test_devon_agent_task_lease_security.py`
- `test_devon_agent_task_leases.py`
- `docs/devon/SYS_OPS_devon-agent-task-execution-leases-handover_v1_2026-08-24.md`

No `services/devon/` file is modified by this PR.

## 15. Operational configuration

Optional environment variable:

`DEVON_AGENT_TASK_LEASE_SECONDS`

Default: `120` seconds.

Application validation clamps the value to 15 through 3600 seconds. Heartbeat interval is approximately one third of the lease duration with a five-second floor.

The database remains the shared authority. Do not replace this with process-local locks for multi-worker deployments.

## 16. What this layer does not claim

This PR does not claim:

- exactly-once external side effects across process death,
- distributed transactions between PostgreSQL and GitHub/shell/network providers,
- browser automation,
- autonomous subagent scheduling,
- unattended approval authority,
- execution inside DEVON core.

Those claims would exceed the evidence.

## 17. Next layer

The next reliability layer should be adapter-level durable effect receipts and provider-native idempotency propagation.

The goal is to close the remaining ambiguity window between:

1. an external effect succeeding, and
2. DEVON Agent Runtime durably recording that success.

For providers with native idempotency support, the task/run idempotency key should be propagated into the adapter request. For providers without it, the application needs a durable effect-intent/receipt ledger with explicit ambiguous-outcome handling rather than automatic re-execution.

Only after that boundary is hardened should browser automation, subagents, and scheduling be allowed to increase unattended execution volume.

## 18. Merge state

PR #29 remains open and unmerged at handover creation.

Do not merge without Tee's separate explicit authorization after the handover-inclusive head passes the full repository gate.
