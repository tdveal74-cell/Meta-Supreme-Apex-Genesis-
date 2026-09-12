# Six doors closed, and a scheduler claim that is a deployment reading

Status record for the arc that ended with PR #194, merged as `135fc80`.
Supersedes nothing; it is the first record of these six surfaces.

## What was wrong

Six subsystems were complete, tested and unreachable. The routes existed, the
tests passed, and nothing under `apps/web` called any of them, so the capability
was real and nobody could use it. That is a worse failure than a missing feature,
because every gate in the estate reads green over it.

| door | the shut door, measured on `32883cf` |
|---|---|
| workflows | ten registered operations over about 2374 lines, and the only mentions of `workflows` under `apps/web` were two pieces of prose saying the surface did not exist. The approval gate the whole engine is designed around had nobody standing at it. |
| decisions | `app/api/v1/decisions.py` registered and tested; `handleDecision` on the deliberate page was a `console.info`, so a visitor's ruling lived in one browser tab until a reload discarded it |
| memory | four finished routes, and `app/services/intelligence.py:333` writing memories about the owner after every exchange, into a store the owner had no way to read |
| projects | four routes with no caller, so the `project_id` the knowledge routes and the graph route filter on could only ever be null |
| agents | the roster and detail routes had no caller; `grep -rn "/agents"` over `apps/web` and `packages/ui` returned nothing at all |
| scheduler | `agent_schedules` rows written durably by a route, and the only thing that turns one into work had a single caller: a manual HTTP route. The cron the API image ships drove workflow rows only. |

## What shipped

One commit, `c77151a`, merged as `135fc80`. 44 files changed, 13,282
insertions, 105 deletions.

Each door is a panel, a pure honesty module with no DOM and no network, and its
own check that binds the two together. Every read is ranked so a failed read
cannot render as an empty state, and every panel is mounted twice: on `/control`
and on a standalone route, so a door does not depend on the shared shell to be
open.

The scheduler door is not a panel. It is `dispatch.py` lane 2, which enumerates
the owners holding a due `agent_schedules` row and calls the existing owner
scoped materializer once per owner, on that owner's own session, under that
owner's tenant binding, holding its own advisory lock. It creates tasks and
executes none: `create_task` plans and saves, and `run_until_blocked` is a
different method reachable only from `POST /api/v1/agent-tasks/{task_id}/run`.

## The ruling that matters most: a runner in the image is not a runner that runs

The first version of the capability catalog flipped `expansion.scheduler` and
`scheduler_status.runs_goals` to `True` on the strength of the runner existing in
this repository. `test_devon_scheduler_honesty.py` demanded exactly that: it
coupled `runs_goals` to whether an automatic call site of the materializer
existed, read with `ast`.

An adversary measured the deployment instead of the repository, and the coupling
was to the wrong fact. On 2026-09-10 the live Railway project held exactly three
services (api, presence, Postgres), no cron or job service, a long running
uvicorn container up since 03:14:30Z, and zero log lines mentioning `dispatch`
over roughly two hours against a documented per minute schedule. The image
carried a runner that nothing ran, and `CapabilityDock.tsx` would have lit a
green Scheduler tile directly above goals that still could not fire. That is the
same defect the estate corrected to `False` earlier the same day, arriving by a
new door.

So the two facts are reported apart, and the couplings split with them:

- `runner` names the module, and is coupled to the `ast` call graph in both
  directions. A runner that exists must be named; a name with no call site fails.
- `runs_goals`, `tick_scheduled_in_this_deployment` and the plain `scheduler`
  flag follow `SCHEDULER_TICK_INSTALLED`, which defaults to `False`, is set per
  Railway service, and is an operator statement about one deployment rather than
  something the process can measure. Nothing inside a container can see a Railway
  cron definition or a host crontab.
- `runs_goals` may never be `True` while `runner` is `None`. A tick cannot
  schedule a runner that does not exist.

The test proves the second coupling by moving the setting and re-reading the
catalog, rather than restating it, and asserts the sentence the dock renders
verbatim moves with it and keeps the words `human gated` in the scheduled branch.

## What the six adversaries found, and what was done

Every door was attacked by a fresh agent in its own worktree at `32883cf`, each
one checking out the exact commit and echoing `git rev-parse --short HEAD` back.
Four returned `safe_to_integrate: true`, two returned `false`. Every finding
below was reproduced before it was fixed and re-measured after.

**A live defect in shipped code.** `app/council/deliberate/page.tsx:155` built
its headline from a boolean chain listing `create-failed` and `refused` and not
`locked`. A signed out visitor who pressed Record decision fell through to the
else branch and read "Sending your call to the decision record" forever, over a
request that was never sent. The headline is now a switch over the union in the
pure module, and a check enumerates all seven outcome kinds and asserts only one
with a request actually in flight may claim one is.

**A failed owner re-planned every tick, forever.** `materialize_due_schedules`
plans through the provider before anything can fail, and nothing advanced the
schedule rows, so the same rows were due again on the next tick. Measured over
three consecutive real ticks with `attach_task` raising after the plan: three
planner calls, zero tasks committed, the row still `due` with `task_id` NULL. On
a per minute cron that is 1,440 provider calls a day for one broken schedule.
`app/services/dispatcher.py:143` already had the rule and states it in its own
comment. A failed owner's due rows are now pushed 15 minutes forward with the
reason written to `failure_reason`, and a deferral that cannot land is named as
spinning rather than reported as one that worked.

**A guard that reads a literal is not reading a rendering, twice more.** This is
the third and fourth instance of the class. `MemoryPanel.tsx`'s verdict block
could be made to paint `MEMORY EMPTY` for an unreadable read with all 32 memory
checks, `control-check` and `tsc` exiting 0; an AST check now asserts the two JSX
expressions in that block are the ladder's own fields with no conditional, and
bans every label the ladder owns from appearing as a literal in the component.
`projects-check.ts:100` matched a `state: "failed"` in the catch block about 239
characters below the branch it meant to guard, so keeping the branch and
replacing its body left 23 checks green over a 500 rendering as "You own no
projects"; it now captures the branch body and bans an ok state inside it.

**Reasons that were not the real reason.** A duplicate project id was refused and
reported as "carrying no usable id" when its id was perfectly usable, so an
operator sent looking for a null id in the payload would not have found one.
Duplicates are counted apart now and each refusal names its own cause. The memory
panel promised recall on word overlap alone while `app/services/memory.py` has
three gates; the two it omitted were measured against the real service rather
than argued: the project scope at `memory.py:88-93`, and a 200 row candidate
window at `memory.py:95` that an owner crosses in roughly 40 to 200 exchanges.

**Two coverage holes that let a lie through every gate.** A list payload that is
not an array had no check at all, and deleting the panel's guard rendered
`WORKFLOWS PRESENT` in a good tone with an undefined count while 31 checks, `tsc`
and `control-check` all exited 0. The ladder now refuses a count that is not a
finite whole number, so it no longer depends on its one caller being correct, and
both branches are asserted. The roster panel's non array guard was unguarded in
exactly the same way.

**Smaller ones, all reproduced.** One workflow's runs, gate and approve control
could render inside another workflow's card for one commit; the server answers
404 on a ruling sent that way so nothing was written, but the ruling would have
been given over another workflow's payload, which is what the seal exists to
prevent. Runs are now bound to the id they were read for. The projects Create
button stayed live over a failed read the panel had just drawn as unreadable,
contradicting its own module's stated doctrine. A read that yielded no store
stamped a fresh successful read time, so the header said the store could not be
read while the footer said "Store read now". `activeClaim` took an `isActive`
argument and never read it, so a row whose own payload said inactive was
described as "listed as active"; the contradiction is now counted from the rows
and drawn in warn rather than good. `ScheduleRunReport`'s docstring claimed
immutability that `frozen=True` does not provide for a list; the outcomes are a
tuple now and a check appends to it and asserts the verdict does not move. A
blank but set `scan_error` degraded to `nothing_due` and healthy. A failed scan
emitted empty owner lists that read as nobody missed.

## The guards that grew

`web-ci.yml` gained five honesty jobs, so every check in this arc runs somewhere
rather than existing on disk. `control-check.ts`'s tree grew from 12 files to 18.
Five of those are the new panels; the sixth is `KnowledgeGraphPanel.tsx`, mounted
on `/control` earlier the same day and missing from a list whose own docstring
says it holds every file mounted under `/control`. Its input count moved from 4
to 11, counted with the check's own regex rather than taken from a note.

`ci.yml`'s standalone lane and the matching list in `CLAUDE.md` both gained the
pure scheduler report test, and the two lists were reconciled from the files
themselves: 22 entries each, no difference in either direction.

The landing page makes its workflow and memory claims again because they are true
again, and `DISCLAIMERS` in `honesty-check.ts` is empty for the first time. Both
exemptions came out with the sentences they exempted, so all three claims now
pass by being satisfied rather than by being excused.

## The gate, with real exit codes

Read from `$?` on unpiped runs.

```
standalone, as ci.yml runs it, PYTHONPATH unset      471 passed    exit 0
full api suite                                      2088 passed    exit 0
ruff check .                                        All checks passed!
check:control 39   check:workflow 34   check:memory   36
check:roster  34   check:decisions 31  check:projects 25
check:presence 31  check:learning  14  check:honesty   4
tsc --noEmit                                        exit 0, no output
next build                                          exit 0
```

CI on `c77151a`: all five `ci.yml` jobs green plus Web CI green. `audio-ci.yml`
correctly did not run: it is path filtered to five audio files and this change
touched none of them.

## The deployment read-back

The code landing is not the door opening. `SCHEDULER_TICK_INSTALLED` was left
unset through the merge, so the estate claimed nothing until a tick had actually
been read back from the platform.

**Railway service `scheduler-cron`**, id `6a96a99e-138d-4f42-b84d-960343db2c7d`,
project `devon-api`, environment production. Source `main`, root `.`, builder
RAILPACK, start command `python dispatch.py`, restart policy NEVER, cron schedule
`*/5 * * * *`. Eight variables, every one a cross service reference to `api`, so
no secret value passed through the session that created it.

The schedule is five minutes rather than the one minute `OPERATING.md` documents
for a host crontab, because Railway's minimum cron interval is five minutes,
schedules are evaluated in UTC, and a run still active when the next is due is
skipped rather than terminated. Read from Railway's own documentation, not
assumed.

Deployment `94615284-89bd-4830-a023-20d80196510e`, SUCCESS. Two ticks read back,
at `2026-09-10T06:37:25Z` and `2026-09-10T06:40:17Z`, both `succeeded`. The first
tick's log, quoted from the deploy log rather than described:

```
app.services.dispatcher      | dispatch complete: 0 started, 0 skipped, 0 failed
app.services.agent_scheduler | agent schedule runner: no owner has a due schedule;
                               nothing to materialize
app.cli.dispatch             | agent schedules: no owner has a due schedule;
                               nothing to materialize
```

Two facts in that log are worth naming because they are the design working in
production rather than in a test. The advisory lock keys are `6233365` and
`6233366`, which are `0x5F1D15` and `0x5F1D16`: the two lanes hold different
keys, so neither can lock the other out for a whole tick. And the owner scan ran
as written, `state IN ('pending','due') AND run_at <= now AND task_id IS NULL`,
grouped and ordered by `owner_id` with `LIMIT 200`.

`nothing to materialize` is the correct answer here: no `agent_schedules` row is
due on this account. The lane is proven to run, not proven to have work.

**Only then** was `SCHEDULER_TICK_INSTALLED` set to `true` on the `api` service.
The api redeployed as `dc1d5351-0917-42f9-8968-42b7d14cbe83`, SUCCESS at
`06:46:29Z` on commit `135fc80`, log reading `Application startup complete` and
`Uvicorn running on http://0.0.0.0:8080`.

## What is still unverified, and by whom

1. **No panel in this arc has been driven from a browser.** `next build` compiles
   every one and emits all six routes, and the six `/control` routes prerender,
   which means each panel rendered its initial state without throwing. No fetch
   in any of the six doors has executed against a running API from a browser.
   Tee settles this by opening `https://meta-supreme-apex-genesis-web.vercel.app/control`,
   signing in through `/devon` first because five of the six panels are account
   scoped and will otherwise show their locked state.
2. **The live capability catalog was not read back over HTTP.**
   `GET /api/v1/agent-tasks/tools` takes `CurrentUser`, so it needs Tee's session
   token, and this container's egress policy refuses the Railway domain outright
   (`connect_rejected` on `api-production-5644.up.railway.app:443`). What is
   measured instead: the variable is present on the api service, the api
   redeployed to SUCCESS afterwards on the merge commit, and locally the string
   `true` parses to `True` and flips the catalog to the scheduled branch. The one
   unmeasured link is the live HTTP response. Tee settles it by looking at the
   Scheduler tile in the Command Center: it should now read as running, with the
   sentence about the task still being human gated under it.
3. **Contrast is checked by class pattern, not by measurement.** No panel has
   been rendered and no contrast ratio measured on a screen or at phone width.
4. **The n8n telemetry surface is not in this arc.** Its second fix and adversary
   cycle returned `safe_to_integrate: false` with two survivors: a future dated
   basis producing a wall whose date and day count are a year apart, and a render
   law enforced over exactly one file so a helper extracted into a neighbour
   reopens it silently. Cycle three is running under a standing three cycle
   limit; it ships separately or it is quarantined with its report.
5. **A stray Railway service exists and it is mine.** A `create-deployment` call
   meant to redeploy `scheduler-cron` created a new service named
   `Meta-Supreme-Apex-Genesis-`, id `6fb2feb3-9edb-48c5-b239-6ed7d00d1396`, with
   no variables, no start command and no data. Its deletion was staged, and the
   staged patch on this environment then reported 57 changes rather than 1.
   Neither the Railway MCP tools nor the Railway agent can enumerate a patch's
   contents, so applying it would apply 56 changes nobody in this session can
   read, and an earlier unrelated staged patch was explicitly out of bounds. It
   was therefore left alone. The service is offline and holds nothing; the cost
   is a failed build of a few seconds on each push to `main`. Tee removes it from
   the dashboard, or authorises applying the patch once he has seen what is in
   it.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_six-doors-closed-and-a-scheduler-that-runs_v1_2026-09-10.md
DATE: 2026-09-10
DECISIONS: Close all six remaining doors in one pass rather than one PR each,
because they share five files and six sequential integrations would have merged
by hand six times. Report the runner's existence and the deployment's schedule as
two separate facts, and light the dock from the second, because an adversary
proved a runner in the image fires nothing. Default SCHEDULER_TICK_INSTALLED to
False so a deployment that never heard of it claims nothing, and set it only
after a tick was read back. Ship the six doors without waiting for the n8n
telemetry surface, which failed its second adversary cycle. Take the Railway cron
at five minutes rather than one, because that is the platform's minimum. Leave
the accidentally created service in place rather than apply a staged patch whose
other 56 changes cannot be enumerated.
FINDINGS: A live headline on the deliberate page that told a signed out visitor a
request was in flight forever, over a request never sent; a failed owner
re-planning through the provider on every tick indefinitely, measured at three
plans over three ticks; two more instances of a guard reading a literal rather
than a rendering, one of which beat all 32 of its own checks plus control-check
and tsc; a refusal reason that named the wrong cause for a duplicate id; a recall
promise naming one of three gates, the other two measured against the live
service; two payload shape guards with no check behind them, one of which
rendered an undefined count in a good tone; a runs and approve control from one
workflow rendering inside another's card; a create button live over a read the
same panel drew as unreadable; a successful read time stamped on a read that
yielded nothing; a claim function ignoring the argument it was handed; an
immutability docstring that three lines disproved; a blank scan error degrading
to a healthy nothing_due; and empty owner lists on a failed scan that read as
nobody missed.
OPEN: No panel driven from a browser and no contrast measured on a screen; the
live capability catalog unread over HTTP because the route needs Tee's token and
this container's egress refuses the Railway domain; the n8n telemetry surface at
cycle three of three; one stray Railway service whose deletion is staged inside
an unreadable patch; the intent parser enrichment, never started.
STATUS: merged as 135fc80, all six CI jobs green on c77151a, cron live with two
ticks read back, api redeployed with the flag set
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
