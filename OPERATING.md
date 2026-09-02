# Operating manual

How to run Meta Supreme Apex Genesis as its owner.

This is not the incident runbook. When something is broken, go to
`docs/RUNBOOK.md` — it is written for whoever is on call, with the SQL and the
escalation paths. This document is the other thing: what operating this system
actually asks of you when it is working.

---

## 0. The one job that is yours

Everything in this system runs on its own except the decisions.

The Council deliberates without you. Knowledge is retrieved without you.
Scheduled workflows fire without you. But the moment a workflow wants to write
something to memory, open a decision record, or prepare an export, it stops and
waits — and it waits for **you**, every run, indefinitely.

That is the operating burden. Not uptime, not tuning: **answering gates**.

A workflow that fires hourly but only gets approved on Fridays will skip most
of its slots. That is correct behaviour, not a bug, but it means the schedule
you set is an upper bound on how often it can actually run. Set cadences you
will actually keep up with.

If you take nothing else from this document: **an unanswered gate is a stopped
workflow.** Check for them daily.

---

Running DEVON and EditForge together on one machine, with nothing hosted
involved, is its own runbook: `docs/OPERATING_LOCALLY.md`.

## 1. Starting and stopping

```bash
make up      # Postgres + API + web, in Docker
make down    # stop
make logs    # tail everything
```

- Frontend — http://localhost:3000
- API docs — http://localhost:8000/api/docs
- Health — http://localhost:8000/api/v1/health

Running the pieces separately, for development:

```bash
make api     # API only, with reload (needs the venv and a reachable DB)
make web     # Next.js only
```

**After any schema change**, before starting:

```bash
alembic upgrade head
```

First time on a database that predates Alembic:

```bash
alembic stamp 001_baseline && alembic upgrade head
```

---

## 2. First hour

In order. Each step depends on the one before it.

1. **Register** at `/register`. The first account is yours; there is no admin
   role yet, and no invitations — everything is scoped to the account that
   created it.
2. **Create a project.** Knowledge, decisions and workflows can all be scoped
   to one. You can skip this and work unscoped, but you will want the
   separation once there is more than one thread of work.
3. **Add knowledge before you ask anything.** The Council answers from what it
   can retrieve. An empty vault means it is reasoning from the question alone,
   which is the least interesting thing it does. Paste in text or upload
   `.txt`/`.md` — PDF and DOCX are not supported yet.
4. **Ask something real in the Command Center.** Not a test question. The
   system is built for questions where the disagreement between agents is the
   point, so ask something you would actually get two opinions on.
5. **Read the points of tension**, not just the synthesis. That is the part a
   single model would have smoothed over.
6. **Track it as a decision** if it was a decision. The recommendation gets
   filled in; the call stays blank until you record it.

---

## 3. The daily loop

**Answer your gates.** Workflows → anything showing "waiting on you." Read the
rendered payload — that is the actual text that would be written, not a
template. Approve, edit first, or reject. A rejection halts the run and is kept
with its reason; nothing is lost by refusing.

**Check what the Council recalled.** Responses say how many memories were used.
If that number is climbing and the answers are getting worse, you have
accumulated a bad memory — go to Settings → Memory and correct or pause it.
Memory is a list, not a black box; treat it as something you curate.

**Watch simulated mode.** If the provider is `mock`, every response is labeled
simulated. It is deterministic and offline and it is not intelligence. Useful
for testing flows, useless for actual judgment.

---

## 4. Going live with a real model

Until you do this, nothing costs money and nothing is real.

In `apps/api/.env`:

```bash
DEFAULT_AI_PROVIDER=anthropic      # or openai
ANTHROPIC_API_KEY=sk-ant-...
```

Restart the API. Check `GET /api/v1/intelligence/status` — `simulated` must be
`false`. The Command Center will stop showing the simulated notice.

**This is the moment the system starts spending.** Read §5 before you turn on
any scheduled workflow.

---

## 5. Cost

Every council run costs tokens. Three things drive the bill, in order:

| Setting | Effect |
|---|---|
| `full_council: true` | 9 agents instead of 3–4. Roughly triples a run. |
| `deliberate: true` | A second round where every agent re-reads the others. Roughly doubles it. |
| Trigger cadence | `hourly` is 24× `daily`. This is the one that actually hurts. |

A workflow with all three is the expensive shape: full council, two rounds,
hourly. That is ~50× a single-agent daily run.

**There is no budget cap.** Token usage is recorded per run
(`workflow_runs.token_usage`) and per agent (`agent_runs.token_usage`), and the
UI shows per-run totals — but nothing enforces a limit, and there is no
aggregate spend endpoint yet. Watch it yourself:

```sql
SELECT w.name, count(*) AS runs,
       sum((r.token_usage->>'total_tokens')::int) AS tokens
FROM workflow_runs r JOIN workflows w ON w.id = r.workflow_id
WHERE r.started_at > now() - interval '7 days'
GROUP BY w.name ORDER BY tokens DESC NULLS LAST;
```

If you are hitting provider rate limits, lower `COUNCIL_MAX_CONCURRENCY`
(default 3) before touching retries. Retrying into an overloaded provider makes
it worse.

---

## 6. Scheduled workflows

They only fire if cron is running the dispatcher. Install this once:

```cron
* * * * * cd /srv/app && python dispatch.py >> /var/log/dispatch.log 2>&1
```

Without it, `schedule` triggers are stored, valid, and inert. The workflow will
look active and never run.

**Cadences are UTC.** `daily:07:00` fires at 07:00 UTC year-round — it does not
follow your local clock through daylight saving. Three forms:

```
hourly:MM              hourly:15
daily:HH:MM            daily:07:00
weekly:DOW:HH:MM       weekly:mon:07:00
```

**Missed slots are skipped, not queued.** If the dispatcher is down for six
hours, an hourly workflow fires once when it comes back, not six times.
Deliberate — a backlog burst would queue six approval gates behind each other.

`event` triggers do not fire at all yet. They validate and store; nothing
dispatches them. The UI says so on the workflow.

---

## 7. Weekly, ten minutes

- **Gates older than a few days** — either answer them or pause the workflow.
  A permanently unanswered gate means the workflow is not doing its job.
- **Token spend** — the query in §5. Look for one workflow dominating.
- **Memory hygiene** — Settings → Memory. Delete what is stale, correct what is
  wrong. Bad memory compounds; it feeds every future answer.
- **Halted runs** — a pattern of rejections means the workflow's prompt is
  wrong, not that you keep changing your mind. Edit the step.
- **Schedule health**:

```sql
SELECT id, name, status, next_run_at, last_fired_at FROM workflows
WHERE definition->'trigger'->>'type' = 'schedule'
ORDER BY next_run_at NULLS FIRST;
```

`next_run_at IS NULL` on an active workflow means the cadence does not parse
and it will never fire. Re-save it with a valid one.

---

## 8. Never

- **Never set `WORKFLOW_APPROVAL_REQUIRED=false`.** It exists so the engine can
  be tested without stubbing approvals. In a running system it silently removes
  the guarantee the whole product rests on, and nothing in the audit trail
  records that you did it. There is no incident that this fixes.
- **Never edit `database/schemas/001_initial_schema.sql`.** It is frozen and
  Alembic's baseline executes it. Changes ship as migrations.
- **Never resolve someone else's gate.** The approval is recorded under your
  user id. On a shared account that makes the audit trail a fiction.
- **Never `alembic downgrade` past `002` on real data.** It drops
  `workflow_runs`, which is where every approval record lives. Export first.

---

## 9. What it will not do

Ask for these and you will be disappointed; they are not built, and the system
says so rather than pretending:

- Send anything outbound. `export` renders into the run record for you to read
  and copy — no email, no webhooks.
- Fire event triggers.
- Bill anyone, or support teams and shared permissions.
- Enforce a spend limit.
- Read PDFs or Word documents.
- Decide anything. It recommends; you record the call.

---

## 10. Before you trust it

The offline test suite passes — 49 tests covering the approval rule in
isolation, which is the part that matters most. **Nothing requiring a database
has been executed**: no migration applied, no API route exercised, no frontend
built, in the environment that produced this package.

Run it yourself before this handles anything real:

```bash
docker compose -f docker-compose.verify.yml up --abort-on-container-exit
```

Then walk §2 of `docs/RUNBOOK.md` — the six-step smoke test. Step 4 is the one
that matters: confirm no memory row exists *before* you approve. If one does,
stop and escalate.
