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
- **Never predict from a number your own action changed.** Found 2026-09-23,
  against the paragraph below that was written to prevent it. A prediction was
  made from `lastEmailed` at 2026-09-19T16:00Z while the session's own manual
  run six hours earlier had already moved it to 2026-09-22T22:25Z. Re-read the
  value out of the artifact, not out of the plan you made before you acted.
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

CI is SEVENTEEN jobs, and on most pull requests you will see five. Five are in
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
does not, no pixel and no sample. The steward skill describes ci.yml's five
jobs and web-ci.yml's one, and since 2026-10-31 it sends the reader here for the
total. Before editing this number again, count it from the files.

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
then takes twelve seconds to die. The Heartbeat failed TEN consecutive runs
from 2026-09-20T16:00 to 2026-09-22T22:00, seven of them by the time this
paragraph was first written, every one killed at `Send Pulse` by `Invalid login:
535-5.7.8`, and the watchdog printed `OK: the Pulse last beat at
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

**That credential is live again as of 2026-09-22T22:25:33Z, and the proof is not
the settings dialog.** Tee repaired `AgSGuaA2pnZsrZcJ` in place rather than
making a new one, and it is still the only credential of type `smtp` on the
instance, so all twenty nodes came back on the one fix. Proving it took reading
the lane's own receipt, because a green execution does not separate a send from
a skipped send: `Only If Email` returns `[]` on a quiet beat, so execution 601
on 2026-09-20 read `success` in 0.165s having sent nothing at all. The receipt
is `devon_heartbeat_log` row 122, `beat_at 2026-09-22T22:25:32.599Z`, where
`emailed` flipped to `yes` at 22:25:33.426Z, and `Mark Emailed` runs only off
the success output of `Send Pulse`. Row 121, the 22:00:15Z beat twenty five
minutes earlier, still reads `no` on the same workflow, unedited since
2026-09-17T12:30Z, with the same credential id on the node. To prove a mail
credential here, run the Heartbeat and read that column. Do not report a
credential panel's test button as a result.

**Testing a rate limited alert lane by hand SPENDS the window you meant to watch
it in, and that manual run is not proof the schedule works.** Ruled worth filing
by Tee 2026-09-23. The manual run at 22:25:32Z proved the send and, in the same
stroke, set `lastEmailed` to its own timestamp. `EMAIL_EVERY_H` is 22, so the
scheduled beats at 04:00, 10:00 and 16:00 were 5.6h, 11.6h and 17.6h past it and
NONE of them should send. Execution 819 fired unattended at 2026-09-23T04:00:15Z
and returned success in 0.213s with row 124 reading `emailed: no`, which is the
lane working correctly and proving nothing about the send. THE HEARTBEAT'S OWN
first unattended send was therefore pushed to its 22:00:15Z beat, 23.6h out.

**That sentence said "the first unattended send" until 11:18Z the same day, and
it was a lane fact written as an estate fact, in the commit that follows "count
from the estate, not from the lane."** Reading the mailbox rather than the one
workflow: estate mail resumed at 2026-09-22T23:35:54Z, seventy minutes after the
repair, and SEVEN messages were delivered before the Heartbeat's window even
opened. `DEVON Precedence Guard` execution 855 is the confirmed scheduled one,
`mode: trigger` at 2026-09-23T11:00:55Z, delivered and carrying a real result.
The rate limit rule above is still true of the lane it was written about, and
the estate was never waiting on it. When a claim is about the whole channel,
read the whole channel: the mailbox is one search.

This estate is mostly rate limited alert lanes, so the shape recurs:
Heartbeat on `EMAIL_EVERY_H`, and every finding keyed so a persisting condition
alerts once and then rides the daily pulse. Before hand firing one, work out
what its own clock will do afterwards, and expect to wait a full period for the
unattended proof. What a manual run does prove is the credential and the send
path; what only a scheduled run proves is the schedule.

**GOOGLE DRIVE IS ALIVE TOO, measured 2026-09-23T11:00:55Z, so everything below
about it being dead is history rather than state.** It could not
be settled from an execution list: `DEVON Precedence Guard` swallows its Drive
failure and dies at the send, so its `status: error` could not separate a dead
credential from a live one, and `DEVON - _To Delete Auto-Purge` retains exactly
one execution, the 2026-09-20T14:00:56Z clean read that bracketed the death.
With mail alive the Guard's own verdict finally arrived: execution 855,
`mode: trigger`, success in 3.136s against 0.52s and 0.98s on the two dead days,
and the email reads `Scanned 188 files in _Devon Core` with real file ids and
created timestamps. A swallowed failure cannot produce that, so `NW3vR6nNcMoUkJyJ`
is live and the EIGHTEEN Drive nodes across SIX workflows below are back.

Two open items came with it, and they are Tee's rather than defects: one
byte-identical duplicate pair in `_Devon Core`, both named
`SYS_LOG_ruling-build01-closure_2026-08-23.md`, and one unversioned canon file,
`CONTEXT-PILL_2026-09-22-2220.md`.

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
then wrote into Airtable a Notes string composed BEFORE the move was attempted,
"Moved to _To Delete on <date>", and set `Triaged: true` whatever came back.

`TQO FINAL V5`: `Repurpose: Drop Caption File` and `Repurpose: Drop Video` both
swallow, and `Repurpose: Mark Handed Off` then PATCHed the slot to `Status:
Ready` with a `Posted At` stamp and a note saying the file was dropped in the
Repurpose folder and "if nothing appears, the workflow on their side is not
pointed at this folder". It blamed a downstream lane for a file this one never
wrote.

**BLAST RADIUS ZERO, AND THE FIRST WRITE-UP OF THIS SAID OTHERWISE.** That
version read "every duplicate it touched since the credential died is recorded
as filed and closed", which was taken from the code and never from the data.
Measured 2026-09-22: `Inbox Captures` (tbl4ziFRbl5mnUcKc) holds 13 rows, all
read; none carries a "Moved to _To Delete" note, none is Triaged, and exactly
one has a `Filename` at all, so no duplicate pair can form. `Publishing Slots`
(tblQgQ3JdpoKOANXh) holds zero rows. Neither lane has ever written a false
record. The defect is real and would have landed on the first matching row; it
had not landed. Grade the blast radius from the store, not from the branch that
would have taken it.

Both were repaired the same day on Tee's ruling, fix the code and leave the
records. A `Confirm Move` node and a `Confirm Drop` node read the Drive file id
back and compose the note honestly in both directions, and on a failure the
repurpose PATCH carries the Notes field ONLY, leaving `Status` and `Posted At`
untouched rather than inventing a new option under `typecast`. Nineteen fixture
cases, both bodies, success and dead credential and 200-with-no-id and an empty
error object.

The two lanes recover differently, which is worth knowing before trusting
either. `Find Duplicates` reads every capture row with no `Triaged` filter, so
the sweep re-detects the same duplicate and rewrites its own note on the next
run. `Repurpose: Due Slots` selects on `{Status}='Pending'`, so a slot flipped
to `Ready` is never selected again and would have been stranded permanently.

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

The twelfth arrived on 2026-10-06: `.github/workflows/registry-check.yml`,
`schedule` only, once a day at 07:41Z, plus `workflow_dispatch`. It runs
`scripts/show_registry_seed.py --check` against the two n8n data tables the
show registry module seeds, `show_registry` and `show_series`, and goes red on
drift, on a stranger row or on a missing `N8N_VPS_KEY`. It never seeds: settling
drift is a ruling. Tee ruled it daily on a card the same day, because a check
on merge alone would miss a hand edit made in the n8n editor. Counted from the
`jobs:` keys of the eight files in `.github/workflows`, not from this paragraph.

The thirteenth arrived on 2026-10-07: `.github/workflows/carousel-render.yml`,
`schedule` only, once a day at 12:13Z, plus `workflow_dispatch`. Tee ruled one
carousel per episode, automatic, from our own HTML templates, for review only.
It reads both content tables, draws every packaged carousel in Chromium with
`tools/carousel/render.mjs`, and uploads the slides as the run's artifact. It
never posts and never writes to the instance, and it goes red on a missing
`N8N_VPS_KEY` like the other scheduled jobs. Counted from the `jobs:` keys of
the nine files in `.github/workflows`, not from this paragraph.

The fourteenth and fifteenth arrived without moving this count. It said
THIRTEEN while the files held fourteen from 2026-10-21 and fifteen from
2026-10-22, found on 2026-10-31 when the sixteenth was added and the `jobs:`
keys were counted. The fourteenth is
`.github/workflows/quality90-ai-review.yml`, committed to main as `067d32d` on
2026-10-21: pull requests only, filtered to `services/quality90_ai/**`,
`n8n/quality90-ai/**` and itself, so it never runs on main. Its one job,
`offline`, runs the reviewer's byte and source binding tests, the n8n signature
tests and a compile check, and its step names say no model call and no write.
The fifteenth is `.github/workflows/browser-worker-ci.yml`, merged in PR #400
on 2026-10-22: pull requests and pushes to main, filtered to
`deploy/browser-worker/**`, `app/services/devon_browser.py`,
`app/services/agent_tasks.py`, `test_devon_browser.py` and itself. It runs
`deploy/browser-worker/validate.sh`, and its header says a missing Chromium, an
unsupported sandbox or any skipped test is red, and that it activates no worker.

So the number is pinned now:
`test_estate_reconcile.py::test_the_ci_job_count_is_counted_from_the_workflows`
sums the `jobs:` keys of every file in `.github/workflows` against the number
in the first sentence of this section, and fails when a workflow file is named
nowhere in this section. A new workflow moves this prose in the same commit or
the api job goes red.

The sixteenth arrived on 2026-10-31: `.github/workflows/dependency-audit-daily.yml`,
`schedule` once a day at 05:23Z plus `workflow_dispatch`. It runs ci.yml's
`dependency-audit` job exactly, and
`test_estate_reconcile.py::test_the_daily_audit_runs_what_the_ci_audit_runs`
fails when the two jobs differ in anything but their names, so change both
together. It exists because on
2026-10-30 four advisories against `pyasn1` 0.6.4 turned the audit red on PR
#441, which touched no requirements file. Main's last run, the day before, had
been green and the advisories were newer than it, so the vulnerable pin sat in
the closure Railway builds with nothing reading it until somebody pushed. Tee
ruled it on a card on 2026-10-31, "Add it". It reads only and uses no secret.
The critic of this workflow found that the audits masked each other: one red
`pip_audit` call stopped the soul host's audit and `pnpm audit` from running, so
an advisory left open hid any newer one behind it. Each audit now runs after an
earlier one goes red, and `pip_audit` runs with `--strict`, so a dependency it
could not check fails the audit. Without the flag it prints a skip and exits 0.
Both changes are in ci.yml's job as well. A red run is most often a new advisory, but
a registry or advisory service that did not answer turns it red too, so read the
log before bumping a pin. An advisory left open turns it red every day until it
is fixed.

The seventeenth arrived on 2026-10-31: `.github/workflows/presence-image-ci.yml`,
pull requests and pushes to `main`, path filtered to `apps/presence/**`,
`services/**`, `requirements.txt`, `infrastructure/docker/Dockerfile.presence` and
itself. It builds the presence image, imports the app inside it, starts it and
reads `GET /health`. It exists because, read on 2026-10-31, every live Railway
deployment had been built with Railpack on Python 3.13 while CI built the
Dockerfiles on 3.12,
so the job named "Railway container contract" tested an image Railway never
built, found while scoping Tee's ruling of that morning to build the presence
image in CI and confirmed by two independent verifiers. Tee ruled on a card to
point Railway at the Dockerfiles, which makes this job and the container job
build what deploys for each service that has been switched, and for none that
has not. Scouting for the switch found the API reads
`policies/reliability/profiles.v1.json` per request and `Dockerfile.api` did not
copy it; it does now, and the container job checks the file is in the image.
Whether a service is switched is a Railway setting and this file cannot show it:
read `build.builder` from `get-service-config`, and a build log for its `FROM`
line, before saying what production runs. A builder changed back in the
dashboard reopens the gap and nothing here would notice.

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
  test_devon_rsi.py test_devon_rsi_ops.py test_devon_rsi_experiments.py \
  test_agent_evaluation.py test_agent_benchmarks.py \
  test_runtime_verification.py test_skill_evaluation_policy.py \
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
  test_provider_watchdog.py test_devon_show_registry.py test_show_registry_seed.py \
  test_devon_lesson_registry.py test_gate_ledger.py test_jev_route.py \
  test_ledger_receipt.py test_code_worker.py test_watch_long.py \
  test_mpt_shorts.py test_openmontage_installer.py test_ltx_build_graph.py

python3 -m pytest -q --tb=short          # full api suite, needs the database
python3 -m ruff check .
pnpm --filter @meta-supreme/web typecheck && pnpm --filter @meta-supreme/web build
```

The dependency audit lane needs a tool the pinned closure does not carry, and
installing it can perturb that closure, so the hook leaves it out. Reproduce it
on demand, in a throwaway environment when you can:

```bash
python3 -m pip install pip-audit
python3 -m pip_audit --strict -r requirements.txt --progress-spinner off
python3 -m pip_audit --strict -r deploy/soul/requirements.txt --progress-spinner off
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
every push. Merge only with Tee's explicit authorization, which has been
standing since 2026-10-11; the ruling is below. After a designated
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

Ruled again by Tee 2026-10-22, in chat: "All rulings on inline cards multiple
choice." It followed a run of reports that ended with the decisions written as
prose lists, "Your rulings: either exempt this one table write from the gate,
or stand the routine down" and "Three things waiting on you", which is the
2026-09-16 failure in a shorter form. A ruling is never a sentence in a report.
It is a multiple choice question on an `AskUserQuestion` card, two to four
options, the recommended one first, each option's cost in its own description.
A scheduled or webhook wake has nobody to answer a card and is often barred
from messaging him at all, so it holds the decision and asks it on a card the
next time he is present; it does not write the choice into its closing line.
An instruction for him to carry out, such as a test only his phone can run, is
not a ruling and can stay in prose.

**Merge approval is standing.** Ruled by Tee 2026-10-11, in chat, after a
session asked him to merge PR #325, a records-only correction, on a card: "You
have my approval to merge at all times." So a session no longer asks for a
merge. It merges a PR it opened on its designated branch once every check on
the PR's head commit has passed, there is no merge conflict, and no review
thread is waiting on it, using a merge commit titled `Merge PR #N: <title>`,
which is the form the steward skill already names for a standing grant. The
two paragraphs above that say his authorization arrives in chat stay true: it
arrived, once, and it stands until he withdraws it.

The grant covers the merge and nothing before or after it. Full local
validation before every push, a fresh critic before an arc closes, and the
deploy read-back after a merge all still apply, and a red check is never
merged past on a guess that it is a flake. It covers nothing else that is his
to decide either: publishing an n8n workflow, setting a variable or a secret,
and every other ruling still go to him on a card.

## The outward gate and its ledger

Ruled by Tee 2026-10-14, "Yes on all 3 decisions", after a read of every cloud
session found 1,810 outward high tier calls and 45 merges, 49 workflow edits, 36
publishes, 29 workflow executions and 29 force pushes that ran with no answered
card and no message from him in the 30 minutes before.

`.claude/hooks/gate_ledger.py`, wired in `.claude/settings.json` on PreToolUse,
PostToolUse and PostToolUseFailure, refuses a gated call unless a human signal
sits inside 2 hours before it: a message Tee typed, or an answered
`AskUserQuestion` card. A refusal means put the decision on a card and retry.
Do not rephrase the call to get past it.

The window was 30 minutes from 2026-10-14 and became 2 hours on 2026-10-28,
ruled by Tee on a card, "All", after a day in which reads on the VPS and n8n
stopped every half hour for a fresh word from him. The trade he accepted is an
outward call running on a word up to two hours old. `WINDOW_MIN` in the hook
is the number; this paragraph is not.

- Gated: every n8n write (publish, unpublish, archive, execute, update,
  restore, data table writes, folder moves); every tool on a server named
  Railway, Airtable, Vercel, Supabase, Hostinger, Rakazo, Blotato, Docusign,
  Zapier, Remote Desktop Commander, Runpod, Graphify or WaveSpeed except a read (get, list, search, describe, query and the like, listed
  in `READ_VERB`), and except a WaveSpeed generate, edit or extend call that only asks for a price (`estimate_only` true); GitHub Actions triggers; Drive trash; a curl that writes to a
  non-local host; a wget that posts to one; `gh workflow run`, `gh api` writes
  and GraphQL mutations, `gh release`, `gh repo`, `gh secret` and `gh variable`
  changes, `gh run rerun`; and any force push, delete push or mirror push except
  `--force-with-lease` to a `claude/` branch. The daily `gh pr` and `gh issue`
  flow is not gated. A connector registered under a
  UUID name is matched by the listed suffixes and the Hostinger prefixes only,
  and Rakazo `send_message` needs the server name. Drive create and update, and
  GitHub pull request and comment calls, are deliberately not gated.
- Ledger only: merges (the MCP tool and `gh pr merge`), because the standing
  approval of 2026-10-11 covers them, and `test_workflow`. The gated list is `GATED_SUFFIXES` in the file; moving a
  tool in or out is a commit, and a ruling.
- Ledger only, by argument rather than by tool: the daily reflection's own row.
  Ruled by Tee 2026-10-22 on a card, "Exempt that one row", after the gate
  refused the scheduled reflection on 2026-10-16 and 2026-10-17, as it would
  any scheduled run, and the Pulse raised `reflection_missing` on every beat
  from 233 to 258. The runs from 10-18 to 10-22 also found the n8n connector
  signed out, which is a separate cause this does not touch. `add_data_table_rows`
  passes with nobody present only when it is exactly that row: an n8n server,
  table `RuPMZKXkqcbuHRKa` in project `qbrcjkbIoorbwot6`, exactly the three call
  keys and one row of exactly the six row keys, every value a string, kind
  `reflection`, empty `vitals` and `findings`, `emailed` "no", a non-empty text
  of at most 900 characters, and a `beat_at` such as `2026-10-23T11:42:03.000Z`
  (a `Z` or `+00:00` suffix, at most six fractional digits, ASCII digits)
  within 10 minutes of the hook's clock. Any other table, row shape or n8n
  write is gated as before. The freshness bound matters: the Pulse anchors its
  reflection watch on a reflection up to 1h ahead, so a forward-dated row could
  otherwise silence the alarm. And at most one per 12 hours in a session, ruled
  by Tee on a second card the same day, "One per 12 hours", after a critic
  showed a looping session could write the row without end, each one replacing
  the reflection in his Pulse email. The hook reads the session's transcripts,
  subagent files included, for a completed write to that table; one inside 12
  hours, a transcript it cannot read, or one that restarts at a compact
  boundary inside the window (as a session rebuilt on a fresh disk does, so
  the history before it is gone) sends the call to the ordinary gate. Across
  the 16 completed writes this session's transcript still holds, from
  2026-09-23, the shortest gap is 14.9 hours, so the cap would have refused
  none of them.
- A webhook turn, a scheduled check-in, a task notification, a peer agent
  report and a context summary are all user turns in the transcript and none of
  them is a signal. The test is `origin.kind == "human"` on the entry. An
  answered card is presence, not consent: the hook cannot read the answer, so a
  card answered no still opens the window, and reading the answer stays the
  model's job.
- It fails closed on a gated call when the transcript cannot be read, and there
  is no environment switch that turns it off. A ledger that cannot be written
  does not refuse a call. A broken reader cannot lock a
  session out of reading or editing, because only gated calls are touched.
- The ledger is `.claude/ledger/gate-ledger.jsonl`, ignored by git and scrubbed
  of anything shaped like a token. It lives in the container, so it records the
  session and is not a durable archive.
- `python3 scripts/ledger_receipt.py` renders the ledger as a DEVON RECEIPT in
  the standing format, validated by `services/devon/receipts.py`, and prints it.
  It writes and posts nothing. Filing it is a separate act through the
  devon-thread-log skill (a claude.ai account skill, not in this repository) or the `devon-capture` door, which needs the
  `x-devon-key` header. That key is not in this repository and is not set in the
  cloud environment, so nothing posts automatically; setting it as an
  environment secret is Tee's, and a curl to the webhook is itself gated.

Not a sandbox: it reads the command text of curl, wget, gh and git, so a write
through `npx vercel`, `railway up`, an inline python or node script, or the
GitHub MCP file tools (`push_files`, `create_or_update_file`,
`enable_pr_auto_merge`) is invisible to it. It catches the unprompted call,
which is what the audit measured. A gated call reads the whole transcript, about
0.4 s on a 53 MB file. A session with no human in it, a scheduled or webhook
run, is refused on every gated call by design.

Unverified: what the harness does with the wrapper's `exit 1` when the script or
python3 is missing. The contract was recalled, not measured, and it is meant to
be a visible non-blocking error rather than python's blocking exit 2.

A subagent's hook input is measured now, in both directions. The script reads
the session file when `transcript_path` is under `/subagents/`, and on
2026-10-31 the ledger of one session held 52 `gate-allow` rows from subagents
and workflow agents. 43 were gated calls, each reason naming the age of the
parent's card (14) or message (29), as in "card 23.1 min ago", and 9 were
ungated Bash calls reading `not gated`. Subagents also left 6 `gate-deny` rows,
5 of them from one workflow when the card was 164 to 166 minutes old and one
from an earlier run at 300. So a workflow agent's gated call passes on Tee's
word in the parent session and is refused when that word ages out. The cost of
that: a workflow can outlive the window. Seven read-only verifiers and a critic
on one box took 151 minutes, and four of the verifiers and the critic were
refused mid-run. Most of that time was two verifiers each held on one Remote
Desktop Commander call from 18:56Z to 21:14Z, about 138 minutes; the cause was
not found. Keep a workflow that makes gated calls short, or ask the card again
before it starts the part that needs the gate.

## The Jev router

Ruled by Tee 2026-10-16 over a recommendation to hold it. The first version
(PR #368) was held after four findings were confirmed against its scrubbing,
and Tee ruled on 2026-10-17, on a card, "Hold it, rebuild as allowlist". This
section describes the rebuild. `.claude/hooks/jev_route.py`, wired on PreToolUse
for exactly Bash, Edit, Write, NotebookEdit and every MCP tool, asks Jev,
TypeSafe's typed decision model, two independent yes/no questions about each of
those calls before it runs: would a dedicated tool (Read, Grep, Glob, Edit,
Write) do this step better, and does the step change something outside the
repository or something that cannot be undone. At or above a probability of 0.8
the second asks Tee and, failing that, the first denies the call with a reason.
Every other answer prints nothing. The hook never prints allow, so it can only
narrow what runs. Read, Grep and Glob are not matched at all.

**It ships with `SEND = True` since 2026-10-29, and the container never holds the
key.** It shipped off first, ruled by Tee 2026-10-28, carrying his earlier ruling
that the container never holds the TypeSafe key. He ruled it on 2026-10-29 on a
card, "Supervised first call": one call made by hand before any commit, then the
one line. A copy of the hook with only the `SEND` line changed, fed one Bash call
at 2026-10-29T00:10:44Z through the environment's proxy, wrote an `answered` row
from `jev-1.14.0` in 549 ms. The module constant still gates every request: set
back to `SEND = False`, the hook makes no request, opens no socket and writes an
`off` row for each call it can read, and a ledger of `off` rows is then the
configured state and not a fault. Input it cannot read, which is anything that is
not a JSON object with a tool name, gets a `bad_input` row first, switch or no
switch. Turning it off again is a ruling and a one line commit, as `ENFORCE` is.
`test_jev_route.py` pins the shipped value the same way and pins the line.

The hook reads no key from any environment variable and sends no Authorization
header of its own. An earlier version read `TYPESAFE_API_KEY`; that variable is
now ignored, and a test sets it and checks that it goes nowhere. Tee added the
key as a network secret in the cloud environment, where the agent proxy adds it
to requests for `api.typesafe.ai`, so the request has to go through the proxy the
environment sets and not around it. On a machine whose environment names no such
proxy, a local checkout for one, the request goes to the host directly with no
key: the outline still leaves, the API answers 401, and three in a row open the
breaker. The hook builds its opener for
each request with `ProxyHandler()`, which reads `HTTPS_PROXY` and `NO_PROXY`,
uses the default TLS context, which trusts `SSL_CERT_FILE`, and changes one
thing: a redirect is refused. The earlier opener, built once at import, did not
disable the proxy either (its default handlers include `ProxyHandler`, checked
on Python 3.13); the change is that it is built for each request, so a proxy set
after the module loaded is the one used. A proxy that does not add the header
gets HTTP 401 from the API. That is an `error` row, it prints nothing, the call
runs as it would without the hook, and three in a row open the breaker for ten
minutes. An error row holds the exception's class name or a fixed phrase and
never an exception's text.

`test_jev_route.py` proves the routing against loopback only. A guard on every
in-process test refuses to resolve or connect to anything but the loopback
interface and fails the test that tries, and each child process starts under the
same guard with an environment whose only proxy is the fake one. With
`HTTPS_PROXY` at a fake proxy, the `CONNECT api.typesafe.ai:443` reaches it, from
a call in the test process and from a real process. A fake proxy that answers the
tunnel with a self signed certificate for `api.typesafe.ai`, named in
`SSL_CERT_FILE`, receives a request with no Authorization header and a body that
is the outline only, and the same tunnel is refused when `SSL_CERT_FILE` names
another certificate. The shipped file, run as a process with that proxy in its
environment, goes through it, and with no proxy in its environment it reaches
nothing but loopback under the guard.

**What leaves the machine is an outline that is built, never a call that is
cleaned.** The first version scrubbed the raw call, and every scrubber missed
something: Basic auth, Cookie headers, `curl -u` values and secret values under
a field name nobody had listed. This one never starts from the raw call. The
pieces that may leave are these and no others. The tool name. For Bash, each
program name, each flag name (`-X`, `--force`) and never a flag's value, plus
the file paths the call names. For Edit, Write and NotebookEdit, the file path
and the names of the input fields. For every MCP tool, the names of the input
fields. No value of any kind leaves: not a command argument that is not a path,
a quoted string, a heredoc body, an assignment such as `TOKEN=abc`, a header, a
file's content or an MCP field's value. A piece outside letters, digits and
`. _ / ~ -` is dropped, not escaped. A path over 200 characters is dropped. A
path is written lexically before anything else is done to it: repeated slashes (a
leading `//` included) collapse, `.` and `..` are resolved from the text alone,
so no filesystem is touched and a link is not followed, and a trailing slash
goes. Then the home directory is written `~`, so `//home/alice/x`,
`/home//alice/x`, `/home/bob/../alice/x` and `~/../alice/x` are each `~/x`. A
path that still holds the home directory's last component, the account name, as a
component of its own after that is a spelling the hook cannot map, and it is
dropped: `/proc/self/root/home/alice/x`, `/home/ALICE/x`, `/mnt/alice` and
`~alice/x` do not leave. The comparison ignores case, and a component that only
contains the name (`alice-backup`) is another name and does leave. The tool name,
one character for the join and the text stop at 2,000 characters together, at a
piece boundary, so 1,999 is the most that is sent. A bare word in a command
counts as a path only when it names something that exists on the machine, and a
call looks at no more than 64 bare words, so a secret that fits the character
class cannot pass as one. A redirect target is a path by syntax and needs no such
test. Only the first 64 KiB of a command is read, cut back to the last blank,
newline, `;`, `|` or `&` in it, so a word the cut lands in is never read.

The edges, stated so a verifier does not have to find them. A short flag cannot
be told from a flag with its value stuck to it, so a single dash flag is kept
only when it is one to three letters or is one of the find primaries kept in
`FIND_FLAGS` (`-name`, `-type`, `-exec`, `-maxdepth` and the other eighteen of
the twenty two), and a two letter value after a one letter flag would pass, after
a program that is a known command (below); `-phunter2` does not. A long flag is
`--` and up to 30 letters, digits and single hyphens, none at either end, with
no more than four digits in all. A program name is up to 40 letters, digits,
`.`, `_` and `-`, starts with a letter or a digit, and has no more than four
digits either. Only the keys of the input object itself leave, never a key below
the top. Ruled by Tee 2026-10-28 on a card: Top-level only. A key under a
parameter is the caller's data (a map keyed by ids, names or tokens, a header, an
environment variable), and a random 24 character alphanumeric token fits the key
rule 58 times in a hundred, and 69 when it starts with a letter (measured on
random tokens, not worked out), so Jev sees `variables` and not the names under
it. A top level key leaves only when it starts with a letter, is made of letters,
digits and `_ . -`, is 30 characters at most and carries no more than four
digits; at most 60 keys leave, taken from the first 200 of the object, and a
short top level key that is itself a secret would still leave. A redirect to
`/dev/tcp/HOST/PORT` or `/dev/udp/HOST/PORT` is a socket and
not a path, so it is dropped, however the path spells it (`//dev/tcp/...`,
`/./dev/tcp/...`, `/x/../dev/tcp/...`). A path that exists and has a secret in its own name
is a path and leaves. Subcommands do not leave, so Jev sees `git` and
`--force` and not `push`. Whether Jev can judge anything from so little is not
known; the ledger is where that gets measured. A flag's name has to be typed
bare: a quoted string that starts with a dash is a value and is not sent, and so
is whatever follows the `=` in `--name="value"`, while `--name` is.

**A program name leaves only when it is a command on the machine the hook runs
on.** Ruled by Tee 2026-10-28 on a card, "Known commands only", after four verify
rounds against the shell reader each found a new way for a value to leave as a
"program name", and the last of the four found more than the one before it (six
findings against `59ef1ed` and three against `c65e5c7`, by the fix commits). The
reader cannot be made to model the shell perfectly, so this closes the class from
the other side. A word the reader takes for a program is sent only when it is a
bash builtin or reserved word from a list pinned in `jev_route.py` (61 builtins
and 22 reserved words, taken from `bash -c 'compgen -b; compgen -k'` in the
container on 2026-10-28, bash 5.2.21(1)-release, both recorded beside the list),
or a name the hook process's `PATH` resolves to an executable file, or, for a
word with a `/` in it, an existing executable file. Any other word is dropped, and
so is every flag of the same simple command, because a word the reader wrongly
took for a program carries its neighbours with it. A reader mistake that takes
data for a program now costs a word and does not leak one. That sentence said
"every reader mistake" until round 5, which found the gate does not reach a
redirect target: it is a path by syntax and is sent untested, so a comment, an
array subscript or a here-document delimiter the reader took for code could send
one. There the reader's own stops are the only defence. The gate is on what the
reader hands out and replaces none of its defences: `test_jev_route.py` runs each reader test twice,
once with the value not installed and once with the value installed as a command,
so the gate cannot be what keeps a value out of a test, and a further test fails
when a row names a program no test machine has. Nothing is run to find out. A
lookup is a stat on a path, bash is never started and the list is a constant. A
word over 64 characters is not looked up, a name is looked up once per call, and a
call stops looking after 128 distinct names. Only the first 128 directories of
`PATH` are searched, empty entries not counted, so a 1 MB command of distinct
words costs at most 128 names times 128 directories in stats, 16,384. And no name
is looked up once the hook has run for one second from the moment it starts
reading its input (`LOOKUP_BUDGET_S`): a lookup cut off half way finds nothing,
and the names after that moment are dropped, builtins and reserved words
excepted, which need no lookup. The names after any of the three caps are dropped.
The first version of this paragraph had the name cap and not the directory cap or
the deadline, and measured against a `PATH` of 40 directories: against a `PATH`
of 10,000 directories the same 1 MB command was 1.28 million stats and 45 seconds
on this container, and the hook is killed at 5 seconds and leaves no row. The test
now runs 10,000 real directories through a real process, written as relative
names because one environment variable is capped at 128 KiB, and pins the stat
count and the deadline apart. The cost, accepted with the ruling: Jev sees less. A
script, a tool or a program named by a path that is not installed where the hook
runs is dropped with its flags, so the same call can read thinner in one
container than in another, a program named by a path over 64 characters is
dropped even when it exists, a name first seen after the 128th lookup is
dropped even when `PATH` has it, and so is a command that lives only in the 129th
directory of `PATH` or later. A program that is installed, such as `git` or
`curl`, is unchanged. The edge: a secret that is itself the name of an installed
command still leaves when the reader takes it for a program, because the gate asks
whether a word is a command and not whether it is a secret, so a value that is
both a command name and in a program slot passes the reader and the gate.

**The reader models a small part of the shell and stops at the first thing
outside it.** A reader that guesses at syntax it lacks reads data as commands,
and every program word is sent. Independent verifiers found that the first
rebuild (`2216592`) did exactly that: an array literal, a `case` pattern, the
operands of `[[ ]]` and `$(( ))`, a `${X:-a;b}` default, an ANSI-C string with an
escaped quote, a double quote nested inside `$( )` inside a double quoted string (the
`git commit -m "$(cat <<'EOF' ... )"` idiom), the tail of a quoted string after
`sudo`, `watch` or `time`, and any word after a closing `)` or backtick were
each read as a program, and the first word of each went out. It now reads simple
commands, pipelines and lists, `if`, `while`, `until`, `for`, `select`, brace groups,
subshells, quotes and escapes, `$( )`, backticks and `<( )` with their own quote
state at any nesting up to 8, redirects including `&>` and `&>>`, heredocs and
here-strings. It reads past, without looking inside, `$(( ))`, `(( ))`, `[[ ]]`,
`${ }`, `$' '` and the literal of an array assignment. A line continuation is
not there: bash removes it before it reads a token, so the reader steps over it
between words, joins what is on both sides of it inside a word and counts it as
no quote. A `$` followed by one inside double quotes ends the read, because
whether the `$` opens an expansion depends on the character bash sees once the
pair is gone. A bare `case` ends the read wherever it stands, whatever the reader
thinks the command is, because a case pattern is data that looks like a command,
and so does a bare `[[` that does not begin a command or follow the reserved word
`time`: read there it is an argument (`echo [[`) or the reader has lost its
place, and the text after it is not an expression to skip. A `[[` that does
begin a command is read to its `]]` without looking in, except that a `$( )` or
backticks inside it is read as the command list it is and a `#` that begins a
word is a comment, which runs nothing. The `]]` is the first one that is a word by
itself, as bash has it: after a blank or a newline and before a blank, a newline,
`;`, `&`, `|`, `)` or a `<` or `>` that does not open `<(` or `>(`, a line
continuation counting as nothing, so `]` then a continuation then `]` is the word
and a continuation neither ends the blank before a `]]` or a `#` nor hides a
comment. A `]]` glued to a parenthesis ends the read, because it is the end of a
group or the end of a regular expression (`[[ a =~ (b)]]` never closes there), and
so does one before a `(`, `<(` or `>(`. A reader that closed on fewer of these
than bash does goes on to a later `]]` that is data, a here-document body or a
quoted string, and reads code there. `$$` is the process id, so the `(` in
`"$$(x y)"` is text and nothing in it runs. A `$( )`, a `<( )` and a pair of
backticks are parsed apart from the command around them: a here-document the
outer command waits for takes its body from the line after the whole line, not
from a newline inside one. Inside one, bash finds where the substitution ends
before it parses what is in it, and a here-document body does not hide the end:
a body line that begins with the delimiter and goes on (`E)`, `E )`, `E) # c`)
ends the here-document and the substitution together, and inside backticks any
closing backtick in a body cuts it. The reader ends a body only at a line that is
the delimiter, so it would go on to a later line that is the delimiter in other
data and read what follows as code. A body line inside a substitution that begins
with the delimiter and is not it, and any body line with a backtick in it inside
backticks, ends the read. A plain subshell does neither, and the reader does not
stop for it there. A subshell is part of the outer parse and shares it.
`NAME=value` before the program is skipped after `env`, `sudo`, `watch` and the
reserved word `time`, and nowhere else: after `nohup`, `exec`, `command`,
`builtin`, `xargs`, `doas`, and `time` typed after an assignment, a redirect or a
quote (then it is `/usr/bin/time`), it is the name of the program to run, and the
word after it is only an argument. A here-document delimiter is literal text,
and when it is typed bare the body is expanded, so a body line that ends in an odd
number of backslashes is joined to the next before it is compared with the
delimiter, as bash does. It stops, drops the rest of the command and sends what
it had read before that point, at a `case`, a `[[` that does not begin a command,
a function definition, a coprocess, an extglob group, a `${ }` with a quote, a
backslash, a backtick, a brace or a newline in it or a `$` followed by `(`, `{`,
`'` or `"` (a plain `$Y` is read past), arithmetic with a quote, a backtick or a
backslash in it or parentheses that do not pair, the legacy `$[ ]`
arithmetic, a backslash inside backticks, a line continuation inside an operator
(`<\` then `<EOF` is a heredoc once bash joins the lines), a here-document
delimiter with an expansion in it, a here-document delimiter that runs into `<(`
or `>(` (bash reads those two characters into the word and runs nothing in a
delimiter), a here-document a `$( )` leaves pending when
it closes, inside backticks a comment, a backslash in an ANSI-C string and a
here-document line that ends in a backslash (bash cuts a backtick body at the
closing backtick and undoes its backslashes before it reads a word, so where a
comment ends, where the string closes and which lines continue are not what the
text shows), `NAME[` at the start of a command when the subscript does not close
before a blank, an operator, a quote, an escape or an expansion other than
`$NAME` (bash reads it as the head of an array assignment and takes the word to
the matching `]`, so `m[k >f ]=1` is one word and runs nothing, and `a`, a line
continuation and `[k >f ]=1` is that word too, because the name and the `[` are
found with the continuations taken out), an element of an array literal with a `[` whose subscript does not close the same way (bash keeps
the whole subscript in the element, so `[a)]=1` is one word and the literal goes on),
text glued to the `)` that ends an array literal (`a=()$(>f)` is one word, a line
continuation between the two counting as nothing), a `#` after an
operator or a parenthesis inside `[[ ]]`, a `]]` glued to a parenthesis or before
a `(`, a `$` followed by a line continuation inside double quotes, the word
`alias`, a word that names `expand_aliases` or `BASH_ALIASES`, an expansion handed
to `shopt`, a subshell
after an assignment or a redirect, a stray `)`, an unterminated region, a quote
or an escape the text ends inside and nesting past 8. A command list inside `$( )`, `<( )` or
backticks that stops before its closer sends nothing from inside it, because a
list that never closes is not known to be one, and a word the read stopped inside
is never judged, which includes the cut at 64 KiB landing inside a quote. A
program name comes from a whole word that is a plain piece: a word with a space,
a colon or an `=` in it is a string or an assignment and its tail is not a
program. An assignment is one only when its name and its `=` are typed bare, and
a reserved word only when it is typed bare with nothing read ahead of it on its
command: `"FOO=bar"`, `\if`, `FOO=bar if` and `> f if` are each a command name
and the word after is its argument, as bash has it. The cost is fidelity and not
secrecy: a command that stops early shows Jev less, and `foo() { rm -rf x; }`
shows nothing, or `foo` where a command by that name is installed (the read stops
at the parenthesis, and `foo` is sent only if the gate knows it), and never the
`rm`. This example said `foo` and not the `rm` until the known commands gate
changed it. A bare `case`, or a `[[` away from the start of a
command, that bash reads as an ordinary argument, as in `grep case src`, costs
the commands after it for the same reason. This paragraph said the cost of a
bare `[[` was fidelity and not secrecy until the skip to its `]]` was found to
read a comment and a quoted here-document body after `echo [[` as command lists.
`test_jev_route.py` pins each construct as a value place, runs the whole table
again inside fourteen wrapping commands, and runs a seeded fuzz that puts a
canary only in quoted text nested three deep. It also replays every Bash
reproduction from the verify rounds that was a program name or a flag leaving as
one, and from round 5 a redirect target leaving, with the value installed as a
command and with it not. The round 5 and round 6 rows are also run through real
bash, when bash is the pinned version, to show that bash creates no file and runs
no command from what they hide. It also inserts a line continuation at every index
of a corpus, the constructs above among it, and fails when the outline gains
anything the unbroken command did not have.

Round 6, against `ab83181`, found five more ways a redirect target or a program
name left. Four are closed at the place the reader looked at the raw text where
bash looks at the text with the continuations removed, or at the end of a
construct where bash ends it earlier than the reader does: a `$` then a
continuation then `(` or `{` inside double quotes, which bash reads as an
expansion and the reader read as text, ending the string at an inner quote; the
head of an array assignment split by a continuation (`a`, a continuation,
`[k >f ]=1`); a `[[ ]]` whose `]]` is closed across a continuation, after a `)` or
before a `<` or `>` (the reader went on to a later `]]` that was a here-document
body and read code there), and one whose comment follows a continuation; and a
here-document inside `$( )`, `<( )` or backticks ended by `E)` or a closing
backtick on the delimiter line. The fifth, runtime parse state, is the alias:
after `shopt -s expand_aliases` an alias can expand to the start of a
here-document, so the lines after it are data to bash. A static reader cannot
know what a later word expands to, so the read ends at the word `alias` wherever
it is typed (as a program, as an argument such as `eval alias f=g` or
`command -p alias`, or inside a string such as `eval "x=1; alias f=g"`), at a word
that names `expand_aliases` or `BASH_ALIASES`, and at an expansion handed to
`shopt`. `unalias`, `aliases`, `alias.co` and `--alias` are other words, and a
`git commit -m "fix alias handling"` ends the read as well, which costs the
commands after it. The edge, unverified in the harness: an alias that the shell's
profile or a file the command sources defines, one the command writes with a
here-document and then sources included, is not in the text, and nothing here
sees it.

Round 7, against `ecc10b0`, found two more ways a redirect target or a flag left,
both in the array literal, which the reader steps over without looking in. Bash
keeps a `)` inside the subscript of an element, so `declare -A m=([a)]=1 [b>f ]=2)`
is one word that runs nothing, and the reader closed the literal at that `)` and
read the rest as commands: a redirect target, which no gate tests, a flag after a
known program such as `declare`, and the name of an installed command. Text glued
to the `)` that ends a literal is the same word in bash (`a=()$(>f)`), and the
reader started a new command there. Both are closed in the reader and not in the
gate. A `[` in an array literal is stepped over only when its subscript closes with
a `]` before a blank, an operator, a quote, an escape, a `)` or an expansion other
than `$NAME`, which is the scan the head of a command already used, and otherwise
the read ends. After the `)` that ends a literal only a blank, a separator, a
closer or the end of the text may follow, a line continuation counting as nothing,
and otherwise the read ends. The cost is fidelity: an array with a blank in a
subscript (`[a b]=1`), or text after its `)`, shows Jev less. The rows are also run
through real bash, as for rounds 5 and 6. Separately, the proxy tests failed on
Python 3.11, which is the version the standalone job in CI runs: `http.client`
puts `HTTP/1.0` on the `CONNECT` line up to 3.11 and `HTTP/1.1` from 3.12, and the
tests had the second written into them, so the file passed on 3.12 and 3.13 and
would have gone red in CI. They compare the host and the port now.

Round 8, on 2026-10-28, was the nits that independent verifiers raised several
times each. Each was reproduced first, fixed at its root and given a test that
fails on the old code. A `PATH` of 10,000 directories ran the lookups to 45
seconds (the known commands paragraph above). A ledger line nested past the JSON
parser, 60,000 brackets, raised `RecursionError`, which `ledger_tail()` did not
catch, so one such line in the last 256 KiB turned every call into a `crash` row
until it aged out. The home directory was written `~` only for the exact spelling
`HOME` plus `/`, and `//home/alice/x`, `/home//alice/x` and `/home/bob/../alice/x`
let the account name out (the path rules above). The model string from the answer
went into the ledger as it came, 5,012 characters with an escape in it in the
reproduction. The unpinned properties were found by mutation: every bound in the
hook, each moved one step either way, and the suite run against each. Of 143
mutants of the bounds and of the lookup and path code, 80 survived the suite with
the tests for the first four nits in it. They included the 64 KiB cap, `doas` in
the wrappers, the find primaries, the 8 MiB input cap, the 256 KiB ledger tail,
the 1 MiB answer cap, the 60 and 200 key limits, the four digit limit, the
breaker window and the two ends of a probability. Tests now say each number
literally. 17 mutants still survive: 3 are constants that the shipped numbers test
pins by value, 3 are one of two bounds that each hold the property (`MAX_PATH`
and the `PIECE` pattern, `FIELD` and `MAX_FIELD_LEN`), 2 are the factor in the
millisecond conversion of the latency, and 9 are equivalent mutants, each
compared with the original and found to differ nowhere: on generated inputs for
eight, and for the ninth, a read of `MAX_STDIN + 2` characters, on inputs from one
under the cap to a thousand over it. The reader's own index arithmetic was not mutated; its reproductions are
the tests above.

It ships in shadow mode, `ENFORCE = False`: it asks, records the answer and
prints nothing. Enforcement is a separate ruling and a one line commit, and
`test_jev_route.py` pins the shipped value so a fixture cannot flip it quietly.
A deny recorded in shadow mode never counts toward the repeat pass described
below, so flipping the flag starts every session clean.

It fails open and it is fast. The whole hook, request included, is held inside
2.5 seconds of its 5 second timeout whatever the input: the request gets what is
left once 0.6 of a second is set aside for start up and the ledger write, and
`test_jev_route.py` feeds a 1 MB command through a real process to measure it,
against a `PATH` of 10,000 directories as well as a short one. That sentence was
untrue of a long `PATH` until the lookups got a directory cap and a deadline (the
known commands paragraph above), which are why the outline is built inside its
second of the budget. A line of the ledger that is not JSON, or is nested deeper
than the parser will follow, is skipped when the tail is read, like any other bad
line, and does not stop the call. With `SEND` off, a refused host, a redirect, the deadline passing, an HTTP error
(a 401 from a proxy that added no key among them), a malformed answer, input
that is not JSON, input over 8 MiB or a tool name outside the character class,
the call runs exactly as it would without the hook, so a quiet hook proves
nothing. After three failed requests in a row it sends nothing for ten minutes,
so a dead vendor costs three deadlines and not one per call.

`.claude/ledger/jev-route.jsonl` gets one row for each call the hook sees, and
that file is the only evidence that Jev decided anything. The outcome is
`answered`, `error`, `off`, `repeat_pass`, `breaker_open`, `bad_input` or
`crash`. Only an `answered` row carries the two probabilities, and only a row
that made a request carries the latency. A row that made no request neither adds
to the failure streak nor ends it. A deny prints only after its row is written,
because that row is what lets the identical call through the second time once
enforcement is on. A row holds the time, the session id (cut at 100 characters),
the tool name (cut at 200), whether the hook was enforcing, the decision and the
outcome. A row that got as far as the outline also holds a hash of the raw call,
so "identical" means identical input, and `sent_chars`, the length of the tool
name and the outline as built. That is what was sent only on a row that made a
request. A `repeat_pass` or `breaker_open` row carries the length of an outline
that was built and then not sent, and an `off`, `bad_input` or endpoint refused
row carries none. The model is written as the answer named it only when it is
`jev-` and up to 36 letters, digits, dots and hyphens, 40 characters at most, and
as `unrecognised` otherwise; the answer itself still counts. A row holds no copy
of the input. An ask is asked every time and a different call is never passed by
a deny of another.

It cannot pick a tool, choose a path or retry. Jev answers typed questions and
writes no text, and no hook can swap one tool for another. It sits beside the
outward gate above and neither reads the other.

`test_jev_route.py` proves the hook's own logic against a loopback stub and
proves nothing about Jev's judgment. Measured once, by the hand-run call of
2026-10-29 above and from one container: the API accepted the request and its
answer parsed as two probabilities, the agent proxy added the key, and the TLS
tunnel verified under the `SSL_CERT_FILE` that session carried. Another
environment whose proxy does not add the key shows a run of 401 rows. Unverified:
the request and answer shapes beyond that one call, which the first version
recorded checking against TypeSafe's OpenAPI spec 0.2.0 and `typesafe-sdk` 0.7.5
on 2026-10-16 and this rebuild did not re-read;
what the harness does with the wrapper's `exit 1`, as under the gate; and
whether a fresh verifier finds a piece that leaves and should not. Also
unverified: which `PATH` the harness gives a hook, because the code reads the
`PATH` of its own process and no live session has been measured, and how much of a
real call Jev still sees once the programs that are not installed are dropped,
which `sent_chars` in the ledger is where that gets measured. The 0.8 threshold is
a starting guess, to be set from the ledger once real answers exist.

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

## Workflow stages

Ruled by Tee 2026-10-16. Every workflow script splits its agents by what they
are allowed to touch, and each kind has its own agent type in `.claude/agents/`,
so the tier and the tool limits live in one file each instead of in every
script.

| stage | `agentType` | edits files | isolation |
|---|---|---|---|
| scan | `scanner` | never | none |
| edit | `editor` | yes, one fix | own worktree |
| verify | `verifier` | never in the main checkout | own worktree |

**A `scanner` cannot reach a connector.** Its tools are Read, Grep and Glob, so
it has no MCP tool and no `ToolSearch` to load one. Found 2026-10-31, when a
sweep of all 25 TSWS workflows on the VPS n8n instance by 25 scanner agents
returned 25 failed reads and 2.7 million tokens of repository evidence by the
run's own tally, each row saying honestly that the live read was not made. A
read of n8n, Drive, Airtable or any other connector is the main session's or a
`general-purpose` agent's (a built-in type with no file in `.claude/agents/`,
so the definition rule below does not reach it; measured the same day, when the
Drive guide sweep's 39 readers and verifiers ran as `general-purpose` and read
Drive over MCP), and a workflow that needs one says so in its agent type.

Pass `agentType` on every `agent()` call and leave `model` unset, so the
definition decides the tier: a model named in the script outranks the one in
the definition. Pass `isolation: 'worktree'` on every editor and verifier call
too. Both definitions set it, but no page says a workflow honours that field,
so the script does not rely on it.

The main session writes the script and reads only what survived verification.
A workflow returns its confirmed findings and its unverified ones, each
unverified one with the reason it could not be settled. Refuted findings are
dropped, and the script logs how many.

`.claude/settings.json` sets `worktree.baseRef` to `head`, so a worktree should
start on the parent's HEAD rather than on `origin/main`. Every editor still
echoes `git rev-parse --short HEAD` first, because that echo is the proof. The
other two traps under "Running a critic" still apply: put `PYTHONPATH` on each
command line, since shell state does not carry between commands, and never let
two agents run against the shared `meta_supreme_test`. Editors run only checks
that need no database. Anything that does runs one agent at a time, in a plain
loop in the script, never inside `parallel()` or `pipeline()`.

An editor commits its one fix on a branch named for its finding and returns the
sha. Worktrees share one object store, so the main session can cherry-pick that
sha directly. It takes only the edits whose finding survived verification, one
at a time, and after each one a fresh verifier re-runs the failing check before
the fix is reported as done.

## Findings and fix loops

Ruled by Tee 2026-10-16.

**Every finding gets an independent verifier before it is reported.** A
finding is a claim that something is wrong: broken, missing, miscounted or out
of date. Before it reaches Tee, a chat reply, a PR or a status doc, a separate
agent checks it in a fresh context. It is handed the claim and the evidence
cited for it, never the finder's reasoning, and it is told to refute the claim
by re-running the check itself. A refuted finding is dropped. One the verifier
cannot settle is reported as unverified, with the reason. The finder rereading
its own work does not count, because a finder agrees with itself. A verifier's
verdict is not a new finding and needs no verifier of its own.

**A fix loop stops after two consecutive rounds with no progress.** A round is
one change plus one re-run of the check that failed. It made progress if the
measured failure shrank: fewer failing tests, fewer open findings, or the first
failure moving later in the run. After two rounds in a row without that, stop
guessing. Report what each round changed and what it measured, give the next
hypothesis, and put the decision to Tee on a card. On a pull request this
session owns, stopping still means one comment on the PR naming the failing
check and why it is not fixed yet, never silence. The cap of three revision
cycles in the `agent-output-gauntlet` skill still holds beside this rule, and
whichever is reached first ends the loop.

## Skills in this repository

`.claude/skills/` carries twenty-four. Seventeen are ours: `steward` (CI and PR
conventions, load it for anything touching either), `deploy-readback` (what the
production surfaces are actually serving), `estate-reconcile` (checking records
against the live estate), `devon-learning-lane` (the Build 12 learning lane and
the n8n house conventions), `devon-grill` (interviewing Tee for the context no
file holds, filed as `docs/devon/CAPTURE_*`), `shadow-we-share-brand` (the
podcast's brand system, its flagship standard, palette, mark and voice),
`startup-reverse-engineering` (turning a named startup into one business to
build: the steal, the wedge and a verdict, with every figure sourced or marked
unverified), `paste-loop` (handing Tee one command or Colab cell for his own
device and judging the output he pastes back: one step, the exact success line,
a pass or fail verdict first), `tsws-repair-workflows` (running and judging the
three TSWS editable repair methods and their synthetic tests, with the twenty
defects the 2026-10-13 gauntlet found and the test that now guards each one),
`tsws-shot-prompt` (writing, running and judging a TSWS generation prompt on
WaveSpeed or its Cinema Studio from the live canon on Drive: end frame first, a
head sheet for the start frame, and the alignment checks measured on SH020 on
2026-10-30), `tqo-viral-output` (drafting Quiet Operator Shorts and long-form
episodes to the working hook patterns of the niche, inside the live episode
canon, with no invented metric), `nco-forge-viral-output` (the same for NCO
Forge, with the stolen valor, benefits and combat footage lines from its canon
branch), `acx-viral-output` (the same for Ascension Caudex awakening content,
with physics words held as metaphor and no health, fear or conspiracy claims),
`genjutsu-open-workflow` (installing or judging the Genjutsu persona-swap app,
what it sends off the machine, and the three changes required before any key
goes in), `watch-long` (long-form video evidence from a cloud session:
ten minute windows read by Gemini, then one synthesis, because the relay in
front of the container cuts a request at its 30 second first byte and a cold
whole video of twenty minutes or more does not make it; measured 2026-10-28
and written into its SKILL.md), `openmontage` (installing and driving
calesthio/OpenMontage, an AGPL-3.0 agent-driven video production system, from
a pinned commit outside this repository by its own installer, with the owned
voice, spend and publishing rules its defaults would break; installed and a
zero-key demo rendered 2026-10-30, then put through a gauntlet review and
hardened 2026-10-31; its installer's guards are tested offline in
`test_openmontage_installer.py`), and `mpt-shorts` (MoneyPrinterTurbo held to
one flow: our own script, Tee-clone voiceover and local clips assembled into
one vertical Short through `tools/mpt_shorts/render_short.py`, which refuses
the keyword-to-video template YouTube will not monetize; audited and rendered
in a sandbox on 2026-10-31). Neither is vendored: no upstream file is copied
in, so neither carries an `UPSTREAM.md`, and each one's provenance lives in its
SKILL.md.

This paragraph said six and five until 2026-09-12, when a session counted the
directory instead of the sentence. `shadow-we-share-brand` had been committed
since `962f104` and was named nowhere. Do not edit these two numbers by hand:
`test_estate_reconcile.py::test_the_skill_inventory_is_counted_from_the_directory`
reads the directory and fails when they drift, which is the only reason this
line can now be trusted.

The eleventh, `scroll-craft`, is vendored third-party work: Nate Herk's
scroll-driven landing page skill, MIT, copied from `nateherkai/scroll-craft`.
Never edit it in place, fixes go upstream, and `test_vendored_skills.py`
enforces that against `MANIFEST.sha256` rather than trusting the prose. Read
`.claude/skills/scroll-craft/UPSTREAM.md` before syncing it, which also means
regenerating that manifest, and before adding `nateherk-design` to the pinned
marketplace, which would double load the same skill name. Its scripts want
Node 18+, a full ffmpeg, and `playwright-core` plus Chrome;
`node .claude/skills/scroll-craft/scripts/doctor.mjs` says which are present.
None of them are pinned or installed by this repository.

The twelfth, `hypit`, is vendored too: Hypit.AI's video direction and
production skill, copied from `hypit-ai/hypit` on 2026-10-16. Same rules and
the same test, one manifest per skill. Its licence is NOT MIT: it is Apache 2.0
plus conditions, free for our own work and our own output, and a commercial
licence is needed before it runs as a hosted service for other parties or ships
inside anything sold. `.claude/skills/hypit/UPSTREAM.md` carries the full
reading. The folder runs nothing itself, but following it means installing the
`@hypit/hypit` runtime and connecting paid model providers, and both of those
are Tee's to approve. Do not also install it with `npx skills add -g`, which
would load a second copy under the same name.

The thirteenth, `typesafe-ai`, is vendored too: TypeSafe AI's skill for
building with its System One models, Jev among them, copied from
`typesafe-ai/skills` at `65a39f3` on 2026-10-16. MIT, one Markdown file, runs
nothing. Same rules and the same test. Tee asked for it installed and used on
this project, and the plugin install lands in the ephemeral `$HOME`, so this
copy is what loads. Do not also install `typesafe@typesafe-ai`, which carries
the same skill. Its first rule is to read `docs.typesafe.ai`. The cloud network
policy refused that host early on 2026-10-16 and answered it later the same
day, after Tee updated the environment; `.claude/skills/typesafe-ai/UPSTREAM.md`
records both reads and what was checked on each.

The fourteenth, `watch`, is vendored too: Bradley Bonanno's `/watch` skill,
which turns a video URL or local file into timestamped frames and a transcript
for the agent to read, or hands the whole video to Gemini when a
`GEMINI_API_KEY` is set. Copied from `bradautomates/claude-video` at `03ceb42`
(release 0.3.2) on 2026-10-28, after Tee sent a screen recording of a YouTube
Short that named it. MIT. Same rules and the same test. Unlike the other three
it ships ten Python scripts that run `ffmpeg` and `yt-dlp` and, by the user's
choice at setup, send video to Google, audio to Groq or OpenAI, or install a
1.5 GB WhisperX environment. None of that runs until the skill is invoked and
the setup wizard is answered. Its scripts fail 23 house lint rules, so
`ruff.toml` excludes that one directory rather than editing upstream code.
`yt-dlp` and Deno are not in the cloud image, `ffmpeg` is; the scripts were
read in full and not executed here. The API key, if Tee wants the Gemini
engine, is his to set, and in a cloud session `~/.config/watch/.env` lives in
the ephemeral `$HOME`, so it does not persist between tasks. The skill's own
wizard offers to take the key pasted in chat; never take that route here,
because the gate ledger reads every transcript. Do not also add
`bradautomates/claude-video` as a plugin marketplace in a session that has
this checkout; its `SessionStart` hook was deliberately not vendored.
`.claude/skills/watch/UPSTREAM.md` carries the full reading.

Three more are vendored too, from Tee rather than from GitHub: `effectcraft`,
`filmcraft` and `photocraft`, three of the thirteen ArtCraft skills installed
on his VPS, ruled on a card on 2026-10-31, "Vendor the three that touch this
work", each "with a manifest and UPSTREAM.md, a separate PR". Each is a
`SKILL.md`, an `evidence.md` claim table and a three line `agents/openai.yaml`,
and filmcraft adds two `references/` files. They were written for Tee on
2026-10-18 against the storytold clean room Rust reimplementations of After
Effects (`storytold/effectcraft` v0.11.1), Premiere Pro (`storytold/filmcraft`
v0.9.0) and Photoshop (`storytold/photocraft` v0.10.0), all three alpha by
their own parity tables, all three MIT OR Apache-2.0, read from the
repositories at the documented commits rather than from the skill text, since
the filmcraft one never says. They came as `ArtCraft_Skills_for_Claude.zip`,
sha256 `39ce1650184662d1c4c4db5168e4d7e660b971a7390b369379e665445bb29f60`,
and every file was checked against the zip's own `MANIFEST.json` before it
was copied, eleven of eleven. Same rules and the same test, with one
difference the test now carries: the copy had no licence file, because the
skills are Tee's and not a third party's, so none is written for them here and
`test_vendored_skills.py` pins its absence. Fixes go to the source copy on the
VPS and come back as a new zip; a file edited under `.claude/skills/` fails
the manifest. The apps are in neither this repository nor the cloud image. The
zip's README says they live under `/opt/artcraft` on `srv1936199`, which is
unverified from a cloud session, while the skills' own launch lines are
written for macOS `.app` bundles, so read the VPS before running one. The
EffectCraft and FilmCraft control channels carry no authentication; the
PhotoCraft one takes a token, which is a credential and never goes into chat.
Each `UPSTREAM.md` carries the full reading.

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
