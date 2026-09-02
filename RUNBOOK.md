# Workflows — operational runbook

On-call reference for the Workflows feature (Phase 5). Assumes the package is
deployed and `alembic upgrade head` has run.

**If nothing is broken, you want `docs/OPERATING.md` instead** — the owner's
guide to running the system day to day. This document is incident triage.

Everything below is written against this repository's schema and settings but
**has not been executed**. Read each query before you run it; treat the SQL as
reviewed-not-tested until someone confirms it against a real database.

---

## 0. The rule that outranks every remedy here

Automation never commits an effect unattended. Memory writes, decision drafts
and exports pause for the workflow's owner on **every run**.

If an incident tempts you toward `WORKFLOW_APPROVAL_REQUIRED=false`, stop. That
setting exists so the engine can be tested without stubbing approvals; it is
deliberately absent from the API, the UI and `.env.example`. Turning it on in a
deployed environment silently converts the product into the thing it promises
not to be, and nothing in the audit trail will record that you did it. Every
procedure below works with gates on.

---

## 1. Deploy

**Fresh database**

```bash
alembic upgrade head
```

**Database that predates Alembic** (has the Phase 4 schema already)

```bash
alembic stamp 001_baseline
alembic upgrade head
```

`001_baseline` executes `database/schemas/001_initial_schema.sql` rather than
re-declaring it, so stamping is safe: the baseline and the file are the same
artifact. That file is frozen — never edit it again.

**Rollback**

```bash
alembic downgrade 001_baseline
```

This drops `workflow_runs` and `workflows.metadata`. **Run history is destroyed,
including approval records.** If the approvals matter for audit, export first:

```sql
COPY (SELECT * FROM workflow_runs) TO '/tmp/workflow_runs.csv' CSV HEADER;
```

The web route is additive — reverting the frontend build is enough on its own,
and is the cheaper rollback if the problem is UI-only.

---

## 2. Smoke test after deploy

Run in order. Stop at the first failure.

1. `GET /api/v1/workflows/step-types` returns `approval_required: true` and
   exactly three step types with `requires_approval: true`
   (`memory_write`, `decision_draft`, `export`).
2. Create a workflow from the UI's "New knowledge → risk scan" template.
3. Run it. It must return `awaiting_approval` with a `pending.preview`
   containing rendered text — not `{{ input }}`.
4. Confirm nothing was written yet: `GET /api/v1/memory` has no new row.
5. Approve. The run reaches `completed` and one memory row now exists.
6. Run again, reject. The run reaches `halted`, the memory count is unchanged,
   and the halted run is still listed in history.

Step 4 is the one that matters. If a memory row exists before approval, stop the
deploy and escalate — see §4.8.

---

## 3. Queries worth having open

```sql
-- Runs by status, last 24h
SELECT status, count(*) FROM workflow_runs
WHERE started_at > now() - interval '24 hours'
GROUP BY status ORDER BY count DESC;

-- Gates nobody has answered, oldest first
SELECT r.id, w.name, r.pending_step_id, r.started_at,
       now() - r.started_at AS waiting
FROM workflow_runs r JOIN workflows w ON w.id = r.workflow_id
WHERE r.status = 'awaiting_approval'
ORDER BY r.started_at;

-- Orphans: claim to be running, plainly are not (see 4.1)
SELECT id, workflow_id, started_at FROM workflow_runs
WHERE status = 'running' AND started_at < now() - interval '30 minutes';

-- Schedule health: what is due, what is broken
SELECT id, name, status, next_run_at, last_fired_at FROM workflows
WHERE definition->'trigger'->>'type' = 'schedule'
ORDER BY next_run_at NULLS FIRST;

-- Token spend by workflow, last 7 days
SELECT w.name,
       count(*) AS runs,
       sum((r.token_usage->>'total_tokens')::int) AS tokens
FROM workflow_runs r JOIN workflows w ON w.id = r.workflow_id
WHERE r.started_at > now() - interval '7 days'
GROUP BY w.name ORDER BY tokens DESC NULLS LAST;

-- Active workflows that have never completed a run
SELECT w.id, w.name FROM workflows w
WHERE w.status = 'active' AND NOT EXISTS (
  SELECT 1 FROM workflow_runs r
  WHERE r.workflow_id = w.id AND r.status = 'completed');
```

---

## 4. Incidents

### 4.1 Runs stuck in `running`

**Cause.** A run executes inside the HTTP request that started it. An API
restart, a deploy, an OOM kill, or a client disconnect mid-run leaves the row at
`running` with nothing to finish it.

**As of 5.1 this self-heals.** The API sweeps orphaned runs on startup —
`WORKFLOW_SWEEP_ON_STARTUP`, threshold `WORKFLOW_ORPHAN_TIMEOUT_MINUTES`
(default 30). A restart is both the likeliest cause and the moment the damage
becomes visible, so that is where the correction runs.

**Why 30 minutes and not 5.** A council step against a live provider can
legitimately take minutes. Too tight a threshold marks healthy in-flight runs
as failed while they continue to execute. Raise it if your provider is slow;
never drop it below the longest run you have seen.

**Manual sweep**, if runs predate 5.1 or the process has not restarted:

```sql
UPDATE workflow_runs
SET status = 'failed',
    error_message = 'Marked failed by operator: process ended mid-run',
    completed_at = now()
WHERE status = 'running' AND started_at < now() - interval '30 minutes';
```

**Why this is safe.** An effect step cannot have committed without a matching
`approvals` entry, written in the same transaction. A run killed mid-flight has
either fully committed an approved effect or done nothing — there is no
half-written state to repair.

**Fix properly.** Background execution. The SSE council endpoint has the same
shape and the same fix.

### 4.2 `409` — "Run X is waiting on step Y. Decide that one first."

Working as designed. One run may sit at a gate per workflow, because effect
steps interpolate earlier results and concurrent paused runs would make the
outcome depend on the order someone clicked.

Find it and resolve it:

```sql
SELECT id, pending_step_id FROM workflow_runs
WHERE workflow_id = '<id>' AND status = 'awaiting_approval';
```

Then approve or reject via the UI or
`POST /workflows/{id}/runs/{run_id}/approve`, naming the `payload_sha256` the
pending view showed as `expected_payload_sha256`. An approval whose pending
payload no longer renders as previewed (the pending view says `diverged`) is
refused 409; a rejection always closes the run, after which the definition can
be changed and a new run started. Never resolve a gate on a user's
behalf without asking them, since the approval is recorded under *your* user id.

### 4.3 `409` on delete — "This workflow has a run waiting for your approval"

Same cause as 4.2. Resolve or reject the gate, then delete.

### 4.4 Duplicate runs

Check whether the client sent `Idempotency-Key`. Without it, a double-submit of
a **read-only** workflow genuinely creates two runs — the awaiting-gate guard
cannot catch that case, because the first run never stopped.

The web client sends a key and holds it across retries. A third-party caller
that omits it is the likely source. Duplicates are harmless for read-only
workflows and impossible past a gate.

### 4.5 Provider `429` / `529`, runs failing at council steps

Runs end `failed` at the council step with the provider error on
`error_message`. Nothing downstream ran and nothing was written — no cleanup is
needed.

Turn down `COUNCIL_MAX_CONCURRENCY` (default 3) before touching
`AI_MAX_RETRIES`; retries against an overloaded provider make it worse. If it
is sustained, set affected workflows to `paused` rather than letting them fail
in a loop:

```sql
UPDATE workflows SET status = 'paused' WHERE id = '<id>';
```

### 4.6 `UndefinedColumn: column workflows.metadata does not exist`

Migration `002_workflow_runs` has not been applied. `alembic current`, then
`alembic upgrade head`.

### 4.7 Token spend spike

Run the spend query in §3. The usual cause is one workflow combining
`deliberate: true` with `full_council: true` on a frequent trigger —
`WORKFLOW_MAX_STEPS` bounds a single run's cost, not how often it fires.

Pause the workflow, then edit the council step down to named agents or a single
round. There is no per-workflow budget cap yet; the metering data exists
(`workflow_runs.token_usage`, `agent_runs.token_usage`) but nothing enforces
against it.

### 4.8 "It wrote something I never approved" — treat as sev-1

This contradicts the claim the whole feature rests on. Do not close it as user
error without the query.

```sql
SELECT status, pending_step_id, approvals, jsonb_pretty(step_results)
FROM workflow_runs WHERE id = '<run_id>';
```

Every effect that executed must have a matching `approvals` entry carrying
`decision`, `actor_id` and `at`. Three readings:

- **Entry present, actor is the complaining user** — the approval happened.
  Show them the timestamp. Likely a UI clarity problem; worth a design ticket.
- **Entry present, actor is someone else** — a shared account or an operator
  resolved it. Process problem, not a code bug.
- **Effect step has a result and no `approvals` entry** — genuine engine bug.
  Escalate immediately with the run id, pause every `active` workflow with an
  effect step, and do not deploy over it.

---

## 5. What this system will not do on its own

Say these plainly when asked; each is deliberate and documented.

- **Event triggers do not fire.** `event` triggers validate and store, but no
  event bus dispatches them. The API reports `awaiting_dispatcher: true` and
  the UI says so in words. `schedule` triggers *do* fire — see §7.
- **No outbound delivery.** `export` renders into the run record and reports
  `delivered: false`. No email, no webhooks.
- **No background execution.** See 4.1.
- **No rate limiting or usage enforcement.** Data is captured, nothing acts on
  it.
- **Cadences are UTC.** A workflow set to 07:00 fires at 07:00 UTC year-round;
  it does not follow a user's local wall clock across a DST change.

---

## 6. The dispatcher (Phase 5.1)

Scheduled workflows fire from cron, not from inside the API:

```cron
* * * * * cd /srv/app && python -m app.cli.dispatch >> /var/log/dispatch.log 2>&1
```

Exit `0` means the batch ran (including "nothing due" and "another dispatcher
held the lock"). Exit `1` means the batch itself failed — database unreachable
or an unexpected error. **A workflow that fails to dispatch does not fail the
batch**: one tenant's broken workflow must not stop everyone else's schedule.
A nonzero `failed` count with exit 0 is the signal to read the logs.

**Running two dispatchers is safe.** A Postgres advisory lock keeps them from
overlapping, and if they do race, every run carries an idempotency key of
`schedule:{slot}` against a UNIQUE index — the second insert is refused by the
database. The lock saves wasted provider calls; the index is what guarantees
correctness.

**Catch-up policy: fire once, then move on.** An hourly workflow whose
dispatcher was down for six hours fires once, not six times, and `next_run_at`
is recomputed from now. Firing the backlog would mean a burst of provider calls
for stale slots and, for a workflow with effects, six approval gates queued
behind one another.

### 6.1 A scheduled workflow is not firing

In order:

```sql
-- Does it have a slot at all?
SELECT id, name, status, next_run_at, last_fired_at FROM workflows
WHERE id = '<id>';
```

- `next_run_at IS NULL` on an active workflow — the cadence does not parse.
  Validation before 5.1 accepted any non-empty string, so older workflows can
  hold anything. Grep the dispatcher log for "unparseable cadence". Fix by
  saving the workflow again with a valid cadence: `hourly:MM`, `daily:HH:MM`,
  or `weekly:DOW:HH:MM`, all UTC.
- `status != 'active'` — only active workflows dispatch.
- `next_run_at` in the future — it is simply not due yet.
- Slot in the past and still not firing — the dispatcher is not running.
  Check cron, then check for a stuck advisory lock:

```sql
SELECT pid, granted FROM pg_locks WHERE locktype = 'advisory';
```

### 6.2 Every scheduled workflow is being skipped

Usually one dispatcher process wedged while holding the lock. Confirm with the
query above, then terminate the holder — `pg_terminate_backend(pid)` releases
it. The next tick proceeds normally.

### 6.3 A scheduled workflow with effects stops firing

By design: a run sitting at an approval gate blocks the next dispatch, because
firing again would queue a second gate behind an unresolved one. Resolve the
gate (§4.2) and it resumes at the next slot. A workflow that fires hourly but
is only approved daily will skip most of its slots — that is the honest
behaviour, not a bug, but it is worth telling the owner.

---

## 7. Where to look

| Question | File |
|---|---|
| What may a workflow contain, and why was this one rejected? | `services/workflows/definition.py` |
| When exactly does a run stop? | `services/workflows/engine.py` |
| What does a step actually do? | `apps/api/app/services/workflows.py` |
| Why did the API return this status code? | `apps/api/app/api/v1/workflows.py` |
| What is the intended behaviour? | `apps/api/tests/test_workflows_api.py` |

The tests are the specification. If an incident and a test disagree, the test is
the intended behaviour and the incident is a bug — not the other way round.
