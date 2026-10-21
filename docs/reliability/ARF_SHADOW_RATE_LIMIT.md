# ARF shadow diagnostic request protection

## Approved scope

Only `GET /api/v1/agent-tasks/{task_id}/reliability-shadow` is covered.
The authenticated account receives a five-request initial/idle burst, with
one request refilled every two seconds (30 per minute). This is a token-bucket
rate, not a promise of at most 30 requests in every rolling 60-second interval.
Ordinary DEVON routes, runtime execution, human approvals, and creative gates
are unchanged. `ARF_SHADOW_READ_ENABLED` remains off unless separately enabled
by the operator after production authenticated acceptance.

## Accounting and concurrency

Migration `030_arf_shadow_rate_limit` adds `arf_shadow_rate_limits`, with one
row per account, a foreign key to `users`, and a finite timestamp constraint.
`next_slot_at` is the theoretical next arrival time: each admitted request
advances it by two seconds, and at most five immediate arrivals fit. A long
idle period cannot accumulate more than that five-request burst.

PostgreSQL's conditional `INSERT ... ON CONFLICT DO UPDATE` serializes each
account's admission against the current locked row. Database `clock_timestamp()`
is used, not a caller timestamp or a worker-local clock. All workers connected
to the same database share the allowance; process restart or token renewal
cannot create a fresh budget. Requests cannot select an owner, rate or burst
through a query, body, task ID or forwarded-address header.

Each admission commits in a separate short security-accounting transaction
before task/evidence lookup. A later 404, 409, error or rolled-back request does
not refund it. A rejected request does not move the stored refill deadline.
The transaction is bounded by a two-second overall timeout, a 500ms database
lock wait and a 1500ms statement timeout. Missing schema, pool exhaustion,
lock timeout or database failure refuses diagnostics rather than bypassing
protection. Database errors and connection details are not returned.

| Condition | Response |
| --- | --- |
| Missing or invalid authentication | Existing 401 |
| Diagnostic flag absent, false or unrecognized | Existing 404; no budget row |
| Valid authenticated request with allowance | Continue existing owner/evidence checks |
| Allowance exhausted | 429, integer `Retry-After`, `Cache-Control: no-store` |
| Accounting unavailable | 503, `Retry-After: 2`, `Cache-Control: no-store` |

Tasks, approvals, evidence, publication decisions and policy records remain
read-only. The endpoint is **not database-write-free**: its own security
accounting is updated. Account deletion cascades only that account's counter.
There is no cleanup job and no extra external service.

## Limits and release checks

This is an authenticated diagnostic-work budget, not a network-level denial
of service defense. Authentication and the small accounting operation still
cost resources. Other endpoints and provider spend limits are not changed.

Tests cover the sixth immediate request, account and login isolation,
caller-supplied owner/IP/task changes, absence of evidence queries on 429,
concurrent database connections, real fresh Python processes, exact refill
intervals, bounded idle burst, database absence, lock contention, recovery,
account cleanup, and unchanged ordinary DEVON reads. The regression must fail
against the predecessor without the guard.

The SQL mirror, Alembic migration, fixture creation/cleanup and CI migration
checks move together. Require full tests, SQL/Alembic parity and independent
review before release. An authenticated production readback is still needed
before enabling diagnostics; isolated fixture tests are not that evidence.

## Rollback

Leave or set the diagnostic flag off before reverting the feature. Downgrading
030 removes only the request-accounting table, not tasks or evidence, but it
also discards budgets. The new handler refuses with 503 if enabled without
its required table. Do not implement an in-memory or unlimited fallback.

## Mechanism references

PostgreSQL 16 INSERT conflict handling:
https://www.postgresql.org/docs/16/sql-insert.html

PostgreSQL 16 row locks and current wall-clock time:
https://www.postgresql.org/docs/16/explicit-locking.html
https://www.postgresql.org/docs/16/functions-datetime.html
