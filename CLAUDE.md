# CLAUDE.md

Project memory for Meta Supreme Apex Genesis. Read this first, then load the
`steward` skill before touching CI or a PR.

## The first law: check before you claim

Ruled by Tee 2026-09-06, after a single night produced five assertions that a
cheap check would have caught. This governs everything below it.

**Do not state anything as fact when a check is available and you have not run
it.** Not "probably", not "should be", not a number you remember. Either verify
it or label it unverified. "Unverified" is always an acceptable answer here;
a confident wrong one never is.

The failure mode is not guessing in the abstract. It is asserting when the
check was cheap and sitting right there:

| what was claimed | what it cost to check | what was true |
|---|---|---|
| "the system prompt is not in this repository at all", written three times | opening one file | it is in `validate_and_plan.js` and already carried the rule |
| digits either side of a dash mean a range, so rewrite it | one test case | "120 [dash] 30% above my last one" became "120-30%", a fabricated number |
| the quadratic regex is fixed | re-running the timing | it was not; the per-line rewrite only moved the backtracking |
| thirteen webhook paths take the key | reading the webhook nodes | fifteen, and the miss was an ACTIVE door |
| the capture tokens are a security finding | working out the blast radius | they are a deliberate design, and the flag was withdrawn |

Rules that follow from it:

- **Read the file before saying where something lives.** A path is not a memory.
- **Count from the estate, not from the lane.** That count has now been wrong
  twice in the same direction, eleven then thirteen, because it was taken from
  a dependency list instead of from the workflows themselves.
- **A fix is not fixed until it is re-measured.** Reproduce the failure, apply
  the change, show the same measurement clean. Three of the entries above
  passed every gate the estate had and were still wrong.
- **Never widen a rule on speculation about intent.** If a transformation could
  change a number, a name, a path or a line of dialogue, refuse instead. A
  refusal costs a retry; a wrong guess lands unread in Tee's Drive.
- **Grade your own findings before raising them.** Work out the actual blast
  radius. Over-calling a finding spends Tee's attention and is its own error.
- **Green is not correct.** CI passed on every one of those. Tests do not read
  the artifact; a human or an executed adversarial case does.
- **An n8n edit is a DRAFT until it is published, and the tool says success
  either way.** Found 2026-09-22 on `OS - Error Handler (all pipelines)`.
  `update_workflow` returned `appliedOperations: 2` while the running workflow
  was untouched: `versionId` held the new draft and `activeVersionId` still held
  the old live version. Reporting that as fixed would have been a false claim
  about production with a successful tool call behind it. Call
  `publish_workflow`, then read the workflow back and check `activeVersionId`
  equals `versionId` and `activeVersion.sameAsDraft` is true. The status docs
  have done this read back since 2026-09-15; it belongs here because this file
  is what a session reads first.
- **A green watchdog run means no refusal inside its window, never that the
  outage is over.** Claimed 2026-09-22, from three consecutive green provider
  watchdog runs at 20:05Z, 00:13Z and 05:15Z. It cost one execution read to
  disprove: `TQO FINAL V5` execution 679 took HTTP 402 from Cerebras at
  2026-09-21T10:20:00Z. The watchdog was right and the reading was wrong.
  `WINDOW_H` is 6.0 and the lane that calls Cerebras fires once a day on
  `Daily 6am - Script Writer`, 10:20Z, so roughly eighteen hours out of every
  twenty four are green whether or not the provider is refusing. It did alarm,
  three times, runs 13 and 14 on 2026-09-20 and run 18 on 2026-09-21, the last
  reading `ALARM: ... Failing node(s): Write Script (Cerebras)`. Before reading
  a green watchdog as recovery, check how often the lane it watches actually
  calls the provider. Where the cadence is longer than the window, green is the
  expected answer and carries no information.

When a check genuinely cannot be run here, say so with the reason and name who
can run it. The 2026-09-06 rotation negative test is the model: the network
policy blocked it, that was stated plainly rather than papered over, and Tee
ran it himself and got the 401.

## What this is

An intelligence operating system, not a chatbot. A FastAPI service under
`app/` and `services/`, a Next.js workspace under `apps/web` and
`packages/ui`, PostgreSQL 16 with pgvector, Alembic migrations under
`database/`. Agents recommend, humans decide: every WRITE or HIGH_IMPACT tool
call is human gated.

Orientation docs, in the order worth reading them: `README.md`,
`ARCHITECTURE.md`, `RUNBOOK.md`, `OPERATING.md`, `docs/devon/DEVON.md`.
The `docs/devon/SYS_OPS_*` files are the dated status record; the newest one
on a topic supersedes the older ones.

## Environment

The SessionStart hook (`.claude/hooks/session-start.sh`) runs on Claude Code
on the web and prepares everything below, so in a web session it is already
done. On a local machine the hook exits immediately and you do it yourself.

```bash
python3 -m pip install -r requirements.txt   # add --ignore-installed if the
                                             # Debian PyYAML shim blocks it
pnpm install --frozen-lockfile
export DEFAULT_AI_PROVIDER=mock EMBEDDING_PROVIDER=mock ENVIRONMENT=test
export PYTHONPATH=$PWD:$PWD/apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme_test
```

PostgreSQL 16 binaries are in the image but there is no initialised cluster and
no pgvector, so a cold container needs
`apt-get install -y postgresql-16-pgvector` and an `initdb` before anything
touches the database.

The cluster lives at `/var/lib/pgtest`, not at the empty Debian skeleton in
`/var/lib/postgresql/16/main`. Pointing `pg_ctl` at the skeleton fails with
`could not access the server configuration file`, which reads like a broken
install and is not one. The cluster does not survive a container restart:

```bash
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/pgtest -l /tmp/pg.log start"
```

`ConnectionRefused` in the middle of a run is the cluster going away, not a
test failure. It shows up as a hundred or more collection ERRORs.

## Reproducing CI

CI is ELEVEN jobs, and on most pull requests you will see five. Five are in
`.github/workflows/ci.yml` (`standalone` then `container` and `engine` then
`api`, plus `dependency-audit` on every push). The sixth is
`.github/workflows/web-ci.yml`, path filtered to the web workspace, so a run of
Python-only PRs makes CI look like five. The seventh arrived on 2026-09-10:
`.github/workflows/audio-ci.yml`, filtered to the files that can change what
the speaker produces, so it appears only on a change to the audio path. It said
FIVE files until 2026-09-17, when the push to talk build added a second check to
the same job: `check:capture` drives the shipped capture worklet through the same
Chromium and measures the stream it hands over. Nine paths now, and the job runs
in both directions, the speaker and the microphone. It went in here rather than
into a ninth workflow because the whole cost of this job is the browser install,
and a separate one would pay it twice. Count the paths from the file.
`ruff check .` runs at the end of the api job, not as a job of its own.

The audio job exists because `check:audio` ran in no workflow at all and four
separate review passes found that. Its script's docstring said so deliberately:
it needs Playwright and a Chromium binary, neither pinned by this repository, so
it costs a browser download on every run that triggers it. Tee ruled on
2026-09-10 to wire it path filtered rather than into `web-ci.yml`. It installs
Playwright globally in the job instead of adding a devDependency, because a
lockfile change would put the cost inside web-ci's own path filter and make
every web pull request pay it. Both `loadPlaywright` and `findChromium` THROW
when missing, so a runner without Chromium turns the job red rather than green,
which is the direction that matters.

The eighth arrived on 2026-09-10: `.github/workflows/panel-smoke-ci.yml`,
filtered to the five control plane panels, the six routes they are served on
and the six API modules they read. It stands PostgreSQL, the FastAPI app and a
built Next server up inside the job, registers a throwaway account through the
real registration path, seeds one row per panel carrying a nonce, and drives all
six routes in real Chromium. It exists because `next build` prerenders those
routes and `tsc` compiles them while no `fetch` in any panel had ever executed,
and every honesty check under `apps/web/scripts` reads source text or an AST.
Same posture as the audio job: Playwright global rather than a devDependency,
and both resolvers THROW so a runner without Chromium turns it red. Do not point
`SMOKE_API_BASE` at a deployed surface: the run registers an account and writes
a project, a memory, a decision and a workflow.

The ninth arrived on 2026-09-11 in `df52510`, and this paragraph said eight
until 2026-09-15, when a readiness audit counted the `jobs:` keys of the five
files in `.github/workflows` instead of trusting the sentence: `render-worker-ci.yml`,
filtered to `deploy/render-worker/**`, runs on pull requests and on pushes to
`main`. Its own comment says what it proves, the argv and filter graphs the
builders emit and the HTTP contract against a listening server, and what it
does not, no pixel and no sample. The steward skill still says five jobs plus
a sixth; that count is older still. Before editing this number again, count it
from the files.

The tenth arrived on 2026-09-17: `.github/workflows/pulse-watchdog.yml`, and it
is the first one that will NEVER appear on a pull request. It has no `push` and
no `pull_request` trigger at all, only `schedule` every three hours and
`workflow_dispatch`, so it runs on `main` and nowhere else. It reads the Build
13 beat log on the VPS over the n8n public API and exits non-zero when the
newest `pulse` row is older than the Pulse's own `MISSED_BEAT_H`. It exists
because `missed_beat` is computed BY the Pulse, so the Pulse can report a late
beat and never a stopped one, and every organ that could watch it lives on the
same instance and dies with it. The alarm channel is the job going red and
GitHub mailing the owner; there is deliberately no SMTP in it. It needs one
repository secret, `N8N_VPS_KEY`, and until that exists every run goes red with
exit 2 saying so, which is the intended direction: a watchdog that skipped
quietly when unconfigured would report green while watching nothing. Its
decision logic is unit tested in `test_pulse_watchdog.py` in the standalone job;
those tests prove the verdict function and prove nothing about the key or the
host, and the file says so.

**It shipped reading one signal and that signal lied for thirty six hours.**
Found 2026-09-22. `Record Beat` sits on a branch parallel to the email branch,
both fed by `Compose Pulse`, so the beat row lands about 150ms into a run that
then takes twelve seconds to die. The Heartbeat failed seven consecutive runs
from 2026-09-20T16:00 to 2026-09-22T04:00, every one killed at `Send Pulse` by
`Invalid login: 535-5.7.8`, and the watchdog printed `OK: the Pulse last beat at
2026-09-21T22:00:15.119000Z, 5.6h ago` from the row an errored run had written.
The script now also reads errored executions of the Heartbeat itself and alarms
on one inside the same window. The lesson generalises past this file: a monitor
that reads an artifact produced BEFORE the failure it looks for will keep
reading a healthy artifact off a dead organ. That is the third instance in one
arc, after the `neverError` provider nodes and `saveDataSuccessExecution: none`.

**SIXTEEN workflows send on one credential, across TWENTY `emailSend` nodes,
and this paragraph said FOUR and then AT LEAST SIX before anyone counted.** SMTP
credential `AgSGuaA2pnZsrZcJ` carries every alerting node in the estate. Not one
`emailSend` anywhere sits on a different credential, so one dead password takes
the whole channel. The Gmail OAuth credential it replaced died the same way on
2026-09-01.

Counted on 2026-09-22 by reading all 45 active workflows and the credential id
on every node, not by opening the ones a session could name. The workflows:
Heartbeat, `DEVON - Error Alarm`, `DEVON Pipeline Watchdog`, `OS - Error Handler
(all pipelines)`, `DEVON Capture Nudge`, `DEVON Precedence Guard`, `DEVON -
Monthly Credential Review`, `DEVON - _To Delete Auto-Purge`, `DEVON - Weekly
Table Backup`, `DEVON - Ledger Janitor`, `DEVON Approval Queue`, `DEVON Soul
Layer Write-Back`, `DEVON - Build 12 Ledger Feeder` (two nodes), `DEVON - Driver
Poll`, `DEVON - Soul Committer` (three nodes), `OS 29 - Platform Policy Sensor`
(two nodes).

Two of those change what the outage costs. `OS 29 - Platform Policy Sensor` is
the compliance lane, scanning platform policy pages daily, and email is its only
channel. `DEVON - Weekly Table Backup` has no sink but email either: it builds
four CSVs and discards them, so there is no backup at all while the send is
dead.

The two earlier numbers are the lesson. FOUR came from the workflows a session
chose to open on name and was written up as "counted from the workflow list",
which was false. AT LEAST SIX came from adding two the error list happened to
surface, which is still reading the lane rather than the estate, and it was
written as a floor precisely because nobody had run the enumeration. Running it
took reading 45 workflows. Do not raise or lower this number by reading another
execution; re-run the enumeration.

`OS - Error Handler` set `onError: continueRegularOutput` until 2026-09-22, so
the error handler every pipeline names reported SUCCESS while no fault email
went anywhere. Tee ruled it loud that day and executions 766 and 769 now read
`status: error` where the same lane read `status: success` before. The two
GitHub Actions watchdogs still work, and only because they deliberately carry no
SMTP.

**A second credential is also dead, and TWO of the lanes it feeds write a
false record rather than failing.** Google Drive OAuth credential
`NW3vR6nNcMoUkJyJ`, dead between 2026-09-20T14:00:57Z and 2026-09-21T11:00:55Z,
bracketed by the Auto-Purge's last clean read. Found because `DEVON Precedence
Guard` composes its own honest alarm, "Could not read _Devon Core, so duplicates
could not be checked. The credential \"Google Drive account\" needs to be
reconnected. This is NOT a clean result", and then dies at the send on the SMTP
credential. One dead credential hid another.

Counted from the estate on 2026-09-22, all 45 active workflows, credential id on
every node: EIGHTEEN Drive nodes across SIX workflows. The count matters less
than the split by error handling.

| workflow | nodes | on failure |
|---|---|---|
| `TQO FINAL V5` | 9 | 3 throw, 6 swallow |
| `DEVON - Drive Draft Writer` | 3 | swallow, then refuse with a named reason |
| `DEVON - iPhone Inbox Capture` | 2 | both throw |
| `DEVON - _To Delete Auto-Purge` | 2 | the read throws, so nothing is purged |
| `DEVON Precedence Guard` | 1 | swallows, composes the BLIND alarm above |
| `DEVON - Duplicate Sweep` | 1 | swallows, then writes a false record |

A node that throws is safe here: the run dies and nothing is claimed. The two
that are worse than being down are the ones that swallow and then write.

`DEVON - Duplicate Sweep`: `Move to _To Delete` swallows, and `Mark Superseded`
then writes into Airtable a Notes string composed BEFORE the move was attempted,
"Moved to _To Delete on <date>", and sets `Triaged: true`. Every duplicate it
touched since the credential died is recorded as filed and closed, and none of
them moved.

`TQO FINAL V5`: `Repurpose: Drop Caption File` and `Repurpose: Drop Video` both
swallow, and `Repurpose: Mark Handed Off` then PATCHes the slot to `Status:
Ready` with a `Posted At` stamp and a note saying the file was dropped in the
Repurpose folder and "if nothing appears, the workflow on their side is not
pointed at this folder". It blames a downstream lane for a file that was never
written.

Graded honestly: those nine TQO nodes have NOT fired since the credential died.
Every `TQO FINAL V5` failure from 2026-09-19 on is the Cerebras 402, execution
614 read back to confirm, and the successful runs exit in under a second having
found no work. The provider outage stopped the pipeline upstream of every Drive
node. That damage is armed, not done, and it lands the day a model provider
answers again.

The whole TSWS block, all six workflows, carries no Drive credential at all. It
works through the render worker on the VPS filesystem.

Second order: the Action Router's allowlist routes `drive.draft` to the Drive
Draft Writer, and the Face's system prompt names that executor as the one chosen
when a job "reads like a draft, outline, script, memo, brief or checklist". It
refuses cleanly, but `saveDataSuccessExecution: none` means the refusals leave
no execution to read.

The eleventh arrived on 2026-09-17 alongside the tenth, and for the same reason
one layer down: `.github/workflows/provider-watchdog.yml`, `schedule` only, every
three hours at :30. It reads the instance's errored executions and goes red when
a model provider is refusing calls. It exists because the content pipeline has
now been stopped twice by exactly that and neither time did anything report it.
On 2026-08-14 the teardown found both script writers dead on Anthropic's "Your
credit balance is too low". On 2026-09-17 Cerebras answered HTTP 402 to eight
scheduled runs between 01:00Z and 19:00Z, with seventeen nodes of `TQO FINAL V5`
routed through it, and it was found by a session that had come to look at
something else.

The ruling asked for a balance alarm. Anthropic publishes no balance endpoint
and neither does Cerebras, so that was only a third buildable and the script
says so in its own docstring rather than implying otherwise. It watches refusals
instead, which every vendor emits: 402 and 401 alarm because they never clear
themselves, 429 is counted and reported because it usually does. It shares
`N8N_VPS_KEY` with the Pulse watchdog and fails the same way when the secret is
absent.

**Do not pause a content trigger to quieten a provider outage.** This watchdog
reads FAILURES, so a paused workflow produces none and it would report OK over a
pipeline just as dead. The noise is the signal. That trap is written into the
workflow file too, because it is the obvious next thing a tired operator would
reach for.

**A lane that swallows its provider's refusal is invisible to an error list.**
Found hours after that script shipped, by reading the live nodes for a different
question. `TQO FINAL V5` throws on a refusal and lands in the error list. `DEVON
Face` and `DEVON Drive Draft Writer` do not: both set `neverError` and
`onError: continueRegularOutput` on their Cerebras node, on purpose, so a 402
there produces a SUCCESSFUL execution and Face answers "I could not reach my
language lane, ask again in a minute", which reads the same on day one and day
eight. The watchdog now reads the newest successful runs of every lane that
calls a provider host and swallows the answer, derived from the workflows rather
than listed, so a third lane written that way is covered the day it lands.

**FOUR lanes cannot be covered, and this paragraph said ONE until the watchdog
itself corrected it.** A lane that sets `saveDataSuccessExecution: none` leaves
nothing for any execution reader to open on a successful run, so a swallowed
refusal there is invisible. The first live run, 2026-09-18T01:06:58Z, named
them: `DEVON Drive Draft Writer`, `DEVON Intake Former`, `DEVON Intelligence
Router` and `DEVON iPhone Inbox Capture`. The count was written from the two
workflows a session happened to read rather than from the estate, which is the
same miss the first law tabulates, committed in the commit that shipped the fix
for it. The script derives the list precisely so nobody has to count; do not
edit that number by hand, read it out of a run.

The refusal is not lost in any of them, it is just not in an execution: the
draft writer returns `refused` on the envelope and the state ledger holds it,
and `iPhone Inbox Capture` falls back to keyword tagging and writes "Cerebras
unavailable (HTTP 402), fell back to keyword matching" into the Airtable row's
Notes. That last one matters more than it reads: every phone capture during a
provider outage is tagged by keyword instead of by the model, and the only
evidence is a sentence in a field nobody opens. Reporting coverage that does not
exist is the failure the script exists to prevent, so it discloses the gap in
both the OK line and the ALARM line.

Graded honestly, because over-calling a finding is its own error: the first
version DID catch the 2026-09-17 outage and the test replaying it passes
unchanged. The gap is an outage confined to the soft failing lanes, which is
what a provider split or a paused content trigger would produce.

**A new schedule only workflow does not fire at its first slots, and that is
not a defect.** Measured twice, which is the only reason it is written as a
rule rather than a guess:

| workflow | registered | first `event: schedule` run | delay |
|---|---|---|---|
| `pulse-watchdog.yml` | 2026-09-17T11:14:49Z | 16:21:01Z | 5h06m |
| `provider-watchdog.yml` | 2026-09-17T22:56:31Z | 2026-09-18T04:59:54Z | 6h03m |

The provider watchdog passed its 00:30Z and 03:30Z slots unfired and then ran
at 04:59:54Z, an hour and a half after the slot it belongs to. Lateness does not
stop after the first run either: the Pulse's scheduled runs have landed at
16:21:01Z, 20:59:10Z, 23:29:55Z and 03:26:54Z against a `0 */3` cron, so twenty
to ninety minutes late is ordinary and a skipped slot has been seen. Wait about
six hours and two slots before calling a new scheduled workflow broken, and use
`workflow_dispatch` to prove the script itself in the meantime, which is how
both of these were proven.

This corrects the reasoning in `PR #272`, not its conclusion. That merge said a
missed slot is platform behaviour and cited the gaps between consecutive Pulse
runs. The gap argument was the weak half: gaps say nothing about a workflow that
has never fired. The first run delay is the half that carries it, and it was
available and unused at the time.

**The alarm going red every three hours during an outage is the design, not a
new fault.** The channel is the job failing and GitHub mailing the owner, so a
provider refusal that lasts a week produces a red job and an email every three
hours for a week. Silence is the failure mode this replaced.

**The standalone list above drifted and was regenerated from `ci.yml`.** It
named 30 files while the job ran 36, missing `test_devon_data_tables.py`,
`test_devon_table_id_conversion.py`, `test_devon_provider_billing.py`,
`test_devon_spoken_input.py`, `test_presence_hearing.py` and
`test_presence_livekit_publisher.py`, so a local run reported 114 fewer tests
than CI and a commit message carried the wrong count. Regenerate it from the
job rather than editing it by hand.

The standalone job runs with no database. This paragraph said it also runs
with **no** `PYTHONPATH` until 2026-09-09, when a worktree agent read the file
and found otherwise: `ci.yml` sets `PYTHONPATH` in its top level `env:` block
(line 14), which applies to every job, and `standalone` declares no override.
Reproducing it with the variable unset is therefore **stricter than CI, not
equal to it**, which is why the commands below are still the ones to run: they
catch an import CI would let through. Keep the list of files in step with the
job, which is the real thing the local run mirrors.

```bash
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -c "import standalone_api"
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q \
  test_billing.py test_definition.py test_providers.py test_schedule.py \
  test_workflow_engine.py test_devon_hermes_expansion.py \
  test_devon_hermes_durable_followon.py test_devon_learning_loop.py \
  test_devon_operating_layer.py test_devon_editforge_execution.py \
  test_devon_data_tables.py test_devon_table_id_conversion.py \
  test_devon_provider_billing.py test_devon_spoken_input.py \
  test_devon_hermes_surface.py test_devon_receipts.py \
  test_devon_capture_enrichment.py test_presence_cartesia.py \
  test_presence_service.py test_presence_hearing.py \
  test_presence_livekit_publisher.py test_devon_owned_voice.py \
  test_devon_learning_context_honesty.py test_knowledge_graph.py \
  test_knowledge_graph_fixtures.py test_devon_scheduler_honesty.py \
  test_devon_scheduler_report_honesty.py test_devon_console_voice_honesty.py \
  test_n8n_telemetry.py test_devon_vision_path.py \
  test_devon_vision_fixture.py test_pulse_watchdog.py \
  test_devon_rule_ledger.py test_devon_wager.py test_devon_tqo_canon.py \
  test_provider_watchdog.py

python3 -m pytest -q --tb=short          # full api suite, needs the database
python3 -m ruff check .
pnpm --filter @meta-supreme/web typecheck && pnpm --filter @meta-supreme/web build
```

The dependency audit lane needs a tool the pinned closure does not carry, and
installing it can perturb that closure, so the hook leaves it out. Reproduce it
on demand, in a throwaway environment when you can:

```bash
python3 -m pip install pip-audit
python3 -m pip_audit -r requirements.txt --progress-spinner off
python3 -m pip_audit -r deploy/soul/requirements.txt --progress-spinner off
pnpm audit --audit-level=moderate
```

`pytest ... | tail` and `tsc ... | tail` report tail's exit code. A run with
154 errors exits 0 through a pipe. Redirect to a file and check `$?`.

ESLint is not configured here. `next lint` drops into its interactive setup and
exits non-zero, which looks like a lint failure and is not one.

**Do not run the standalone job while the full suite is running.** Found on
2026-09-17. The full api suite was running in the background when the standalone
list was run in the same container, and
`test_presence_service.py::test_interrupt_for_another_turn_acks_without_cancelling`
failed with `assert 'frame' == 'state'`: the socket delivered an audio frame
where the test expected the state change, which is an ordering assertion losing
to CPU contention. The job took 14.21s under load and 7.28s alone, and it
returned `992 passed` alone, on `origin/main` in a clean worktree, and on the
branch. This is the CPU sibling of the database collision documented under
"Running a critic": neither is a defect in the branch, and both cost a
diagnostic detour if the concurrency is not noticed. Run one suite at a time,
and re-run alone before believing a timing failure.

The full failure catalogue with root causes lives in the `steward` skill.
Check it before inventing a new theory.

## Invariants that never get relaxed to make CI green

- `services/devon` stays effect free
- WRITE and HIGH_IMPACT tools require human approval
- Orphan effect intents refuse automatic retry; the intent commits durably
  before the adapter runs
- Receipts commit atomically with the lease fenced result
- Skill promotion is human gated; proposals dedupe by goal slug
- Materialize and spawn never auto run effects
- `deploy/soul/main.py` has no mutating routes. The one permitted non-GET is
  `POST /api/v1/soul/conflict-search`, which is a read only recall query, and
  it is allowlisted explicitly in `test_deploy_soul.py`
- No em or en dashes in `services/devon/*.py` or `docs/devon/*.md`.
  `test_devon_integrity.py` enforces it. Restructure the sentence, do not swap
  the punctuation

## Adding a migration

A new migration touches four places in `ci.yml`, not three: the two `for f in
001... ; do test -s` existence loops, the `assert revision == "<head>"`
inside the Python heredoc of the "Fresh Alembic deploy" step, and the `for f
in 002_workflow_runs ...` loop in the "same database" step that applies the
SQL scripts beside the Alembic build. The fourth arrived with 018 and this
paragraph said three until 019 counted from the file (2026-09-08), which is
the same miss the first law describes. It also touches two lists in
`conftest.py`: `_INCREMENTAL_SCHEMAS` and `_DATA_TABLES`, where FK order
matters. Miss either list and every test touching the new tables fails with
`relation "agent_..." does not exist`. Count the places with
`grep -n "<previous head>" .github/workflows/ci.yml` before editing, never
from this paragraph. `_DATA_TABLES` is the truncate list, so it only changes
when the migration adds a table; 021 added none and touched only the first.

Confirm the current head with `alembic heads`, never from a doc.

**An uncommitted migration turns one test red, and it is not a defect.** Found
with 021 on 2026-09-17. `test_estate_reconcile.py::test_the_deployed_head_is_
read_at_the_newest_successful_deployment` fails with `assert '020' == '021'`
while the new revision file sits in the working tree unstaged or uncommitted.
The two readers genuinely disagree at that moment: `_alembic_head()` globs
`database/migrations/versions` on disk and sees the new file, while
`_deployed_alembic_head` runs `git ls-tree` at a commit and does not. Commit
the migration and the test passes; 83 passed immediately after. Do not chase
it, and do not "fix" the test. It is measuring the right thing, which is that
the deployed head comes from the deployed commit rather than from your tree.

## Adding a module to services/devon

A new `.py` file there is three places, not one. The module itself, then a byte
identical copy under `deploy/soul/services/devon/`, then `__init__.py` in both
if the package exports it. `test_deploy_soul.py` builds its vendored map by
globbing the real directory, so a new module is required in the deployed copy
the moment it exists, and a drifted copy fails on bytes rather than on
behaviour. Found on 2026-09-17 by the full api suite and by nothing before it:
the standalone job, ruff and the module's own tests were all green while the
soul service would have shipped without the new rules. `test_devon_integrity.py`
also globs the directory, so the dash ban, the network import ban and the
`ast.parse` check apply the moment the file lands, and a doctrine module named
in its `DOCTRINE_MODULES` map must declare a `SOURCE` or `SOURCES` that names a
checkable origin.

Copy with `cp`, never by hand, and re-run `python3 -m pytest -q test_deploy_soul.py`.

## Ship discipline

Small PRs on the designated branch, draft first, full local validation before
every push. Merge only with Tee's explicit authorization. After a designated
branch's PR merges, restart the branch from `origin/main` under the same name.
Close an arc with a dated `docs/devon/SYS_OPS_*` status doc and a DEVON thread
log receipt.

A handover's "CI green" is a claim, not a fact. Check the Actions history for
the claimed head SHA before building on it. A green Vercel preview is not
production; load the `deploy-readback` skill before saying any surface is live.

**Tee's word in the session is the review of record.** Ruled 2026-09-09, after
a close-out doc recorded the GitHub timeline carrying no `reviewed` event on
PR #176 and six seconds between leaving draft and merging. GitHub review is not
the gate here and a missing `reviewed` event is not a finding; do not wait on
one, and do not write it up as a gap. His explicit authorization is still
required to merge, and it arrives in chat.

**Rulings go on an inline card, not in prose.** Ruled by Tee 2026-09-16, after
a session put a live outage, a merge question and four handed back items into
one paragraph and asked him to find the decisions in it. A card puts the
options beside each other with their costs and takes one tap; a paragraph asks
him to do the sorting. So every decision that is his to make is asked with
`AskUserQuestion`, the recommended option first, and each option's cost written
into its own description rather than into the text around the card. This
loosens nothing above it. His authorization to merge is still explicit and
still arrives from him; the card is how it is asked for, never a substitute for
having it.

## The receipt on a status doc

Ruled 2026-09-09. Every `docs/devon/SYS_OPS_*.md` carries a `## DEVON RECEIPT`
block with nine keys, `AREA`, `TYPE`, `ARTIFACT`, `DATE`, `DECISIONS`,
`FINDINGS`, `OPEN`, `STATUS` and `TOKEN`, the capture token line verbatim, and
a `DATE` matching the date in the filename. Extra keys are welcome; those nine
are the floor. `test_devon_receipt_shape.py` enforces it, so do not describe
the rule in prose and hope.

Ruled 2026-09-15: from 2026-09-16 every status doc's filename carries a
sequence letter after the date, `_v1_2026-09-16a.md`, then `b`, `c` within the
same day and unique across that day, because the readiness audit found six
same day pairs that supersede each other in an order the filenames could not
express. The same test enforces it; docs dated on or before 2026-09-15 keep
their names.

Ruled 2026-09-16, on the first full day that letter existed, because it
collided that same day. Two sessions forty three minutes apart each wrote a
2026-09-16 doc and each picked `a`. Neither was careless: an unmerged branch is
invisible from another container, so both read an empty day and both took the
first free letter, and PR #235 merging second turned `main` red. A picked
suffix races whenever two sessions write on the same day.

So from 2026-09-17 the suffix is the UTC hour and minute the doc was written,
`_v1_2026-09-17-0342.md`. Get it from `date -u +%Y-%m-%d-%H%M` rather than by
reading the directory; the point is that it is derived, not chosen, so two
sessions reach different answers without seeing each other. A collision now
takes two docs written in the same minute, and the same test still catches it.
2026-09-16 itself stays letters only: its docs are already named, and digits
sort before letters, so allowing both forms on one day would misorder the only
thing the suffix exists to order.

Enforcement is an exemption list of exact filenames, not a date cutoff, because
a new doc can carry an old date in its name and a filename cannot be forged
that way. The list is the migration backlog and it may only shrink: one test
fails if it names a doc that no longer exists, another fails if a listed doc
already satisfies the canon and is still listed. Forty five docs were exempt
when the rule landed, most of them August handovers that may not be status docs
at all, which is a call for Tee rather than forty guesses.

`services/devon/receipts.py` is a different format for a different job, the
thread log capture path. It reads a `=== DEVON RECEIPT v1 ===` block and
`detect_format` returns None for every status doc. Do not try to make one
satisfy the other.

## Running a critic

Every arc here closes with a fresh critic, and a critic earns its verdict by
mutating the real source: registering a tool that should not exist, deleting a
guard, feeding an input nothing else feeds it, then reverting. That is the
method working rather than a critic misbehaving.

**Spawn it with `isolation: "worktree"`.** A critic, or any subagent told to
mutate the source, gets its own checkout. The session's own tree is not scratch
space, and a critic that shares it costs three ways. All three happened in one
session, 2026-09-09, PR #177:

- The stop hook reported uncommitted changes that were the critic's.
  `app/api/v1/router.py`, a new `app/api/v1/agent_skills.py` and
  `app/api/v1/agent_tasks.py` each appeared and reverted inside three commands.
  Committing them would have pushed a throwaway probe as if it were the work.
- Any check the parent runs while a critic holds a mutation is measuring the
  critic's source, not the branch's. A green run in that window proves nothing
  and has to be thrown away and repeated.
- A critic that stops mid mutation leaves dirt with no owner, and the next
  session cannot tell it from real work.

If foreign changes do turn up in the tree, do not commit them and do not
revert them blind. Ask whether the path is in your own diff first, with
`git diff --name-only <base>..HEAD`, and leave alone anything that is not.
A path you did not touch belongs to something still running.

**The worktree does not start on your HEAD.** Measured on 2026-09-09: the
parent sat on `b8fd28b` and the new worktree came up on `2b09dbd`, which is
`origin/main`, so `test_devon_hermes_surface.py` did not exist in the critic's
checkout at all. A critic handed the wrong commit reviews code the branch does
not have and reports green, which is the most expensive answer it can give.
Check the commit out yourself as the first instruction in the prompt, and make
the agent echo `git rev-parse --short HEAD` back in its report so a wrong base
shows up in the receipt rather than in the verdict:

```
git fetch origin <branch> && git checkout -B verify <sha>
git rev-parse --short HEAD    # must match the sha you meant
```

Two things that are already handled, so nobody re-derives them:
`.claude/worktrees/` is in `.gitignore`, and the worktree is removed on its own
when the agent leaves it unchanged.

**The isolation is of the filesystem only, and the database bites.** Every
worktree shares this container's one PostgreSQL cluster, so two agents running
the full suite are writing the same `meta_supreme_test`, and `conftest.py`
truncates one global `_DATA_TABLES` list after every test. Measured on
2026-09-09, when this was written as a caution and then promptly happened: a
worktree agent's suite returned `8 failed, 1493 passed, 56 errors`, the errors
reading `duplicate key value violates unique constraint "users_email_key"`,
with a second session running the identical suite from another worktree. The
retry collided with a third session, both blocked in `pg_stat_activity` on
`Lock / relation` with one `TRUNCATE` waiting on the other. On a private
database the same commit returned `1557 passed`. So a suite that fails only
while a critic is out is the cluster, not the branch. Give a concurrent run
its own database rather than re-running into the same collision, and know that
`test_live_state_ledger_provenance.py` hardcodes `meta_supreme_test` for the
TEMP privilege check, so that one test alone must run against the real name.

**Check `PYTHONPATH` before running anything in a worktree.** The inherited
value points at the main checkout, so pytest imports the parent's code while
the run appears to be testing the worktree. Same shape as the wrong base
commit above: a green that means nothing. Set it to absolute worktree paths.

## Skills in this repository

`.claude/skills/` carries seven. Six are ours: `steward` (CI and PR
conventions, load it for anything touching either), `deploy-readback` (what the
production surfaces are actually serving), `estate-reconcile` (checking records
against the live estate), `devon-learning-lane` (the Build 12 learning lane and
the n8n house conventions), `devon-grill` (interviewing Tee for the context no
file holds, filed as `docs/devon/CAPTURE_*`), `shadow-we-share-brand` (the
podcast's brand system, its flagship standard, palette, mark and voice).

This paragraph said six and five until 2026-09-12, when a session counted the
directory instead of the sentence. `shadow-we-share-brand` had been committed
since `962f104` and was named nowhere. Do not edit these two numbers by hand:
`test_estate_reconcile.py::test_the_skill_inventory_is_counted_from_the_directory`
reads the directory and fails when they drift, which is the only reason this
line can now be trusted.

The seventh, `scroll-craft`, is vendored third-party work: Nate Herk's
scroll-driven landing page skill, MIT, copied from `nateherkai/scroll-craft`.
Never edit it in place, fixes go upstream, and `test_vendored_skills.py`
enforces that against `MANIFEST.sha256` rather than trusting the prose. Read
`.claude/skills/scroll-craft/UPSTREAM.md` before syncing it, which also means
regenerating that manifest, and before adding `nateherk-design` to the pinned
marketplace, which would double load the same skill name. Its scripts want
Node 18+, a full ffmpeg, and `playwright-core` plus Chrome;
`node .claude/skills/scroll-craft/scripts/doctor.mjs` says which are present.
None of them are pinned or installed by this repository.

A pinned plugin is not a substitute here. `.claude/settings.json` enabling a
plugin does not install it, and in a Claude Code on the web session
`~/.claude/plugins/installed_plugins.json` reads empty while all three pinned
plugins show as enabled. `~/.claude/skills/` is no better: `$HOME` is in the
ephemeral container. Anything that has to load in a web session is committed
under `.claude/skills/`.

`.claude/settings.json` also pins three community plugins through the
`meta-supreme-pinned` marketplace in `.claude-plugin/marketplace.json`. Each
machine installs them once:

```bash
claude plugin install agentic-guardrails@meta-supreme-pinned
claude plugin install backend-security-skills@meta-supreme-pinned
claude plugin install test-generator@meta-supreme-pinned
```

Remove any `@claude-community` copy of the same name, which would otherwise
load beside the pinned one and win.
