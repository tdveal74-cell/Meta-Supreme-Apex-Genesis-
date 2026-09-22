# A fresh beat is not a finished run

DEVON's Heartbeat has been dead at the send for thirty six hours and the
watchdog built to notice exactly that printed OK four times a day through all of
it. The mail credential is Tee's to fix. The blind spot was mine, and it is
fixed here.

## What is actually broken

`DEVON - Heartbeat (Build 13)` (`EEDrp2jLlw2Ssd5b`) has failed seven consecutive
runs, 2026-09-20T16:00:15Z through 2026-09-22T04:00:15Z. Every one of them died
at the node `Send Pulse`, an `emailSend` node on SMTP credential
`AgSGuaA2pnZsrZcJ`, with the same reply from Google:

```
Invalid login: 535-5.7.8 Username and Password not accepted.
httpCode: EAUTH
```

The node carries `retryOnFail: true, maxTries: 3, waitBetweenTries: 5000`, so
each failure burns twelve seconds and change. Execution 729 measured 12399ms at
that node against a total run of 12.56s, which is why the failed runs take 11 to
13 seconds while the healthy ones took 165ms.

`DEVON - Error Alarm` (`bqcnIS0Qv4RkTCU1`) fires correctly on each of those
failures and then dies itself, one second later, at its `Alert Tee` node. Same
credential. Its own note says why: "Moved off Gmail OAuth 2026-09-05, same lane
as the Heartbeat, so one working mail password revives both." That is true in
both directions. One password revives both organs and one dead password kills
both, so the alarm and the thing it watches share a single point of failure.

## The credential is the whole alarm surface

Counted from the workflow list rather than from the two lanes this session
happened to open, because taking that count from a lane is the miss the first
law tabulates. Four active workflows send on `AgSGuaA2pnZsrZcJ`:

| workflow | node | on a send failure |
|---|---|---|
| `DEVON - Heartbeat (Build 13)` | `Send Pulse` | errors, three tries, 12s |
| `DEVON - Error Alarm` | `Alert Tee` | errors, one try, 1s |
| `DEVON Pipeline Watchdog` | `Send Watchdog Alert` | errors, but only on a run that has something to report |
| `OS - Error Handler (all pipelines)` | `Send Email Alert` | `onError: continueRegularOutput`, so it reports SUCCESS |

That is every alerting path DEVON has, on one Gmail app password, and the
password is dead. The last of the four is the worst of them: the error handler
that every pipeline names swallows its own send failure and finishes green, so
an execution list shows nothing wrong while no fault email has gone anywhere.
It is the same soft failure shape the provider watchdog was built for in
September, in the one lane whose job is to tell you when something broke.

Its sticky note records that this has happened before, in the same words the
Heartbeat uses: "moved off Gmail OAuth on 2026-09-05. Credential
vsTKuAilHmpYCc5L went invalid on its own around 1 September and every alert
since then died at the send."

What still works is the two GitHub Actions watchdogs, and only because they
deliberately carry no SMTP at all. The provider watchdog is green and reporting.
The Pulse watchdog was blind until this change.

The last DEVON email that reached Tee was the pulse of 2026-09-19T16:00:15Z, row
106 in `devon_heartbeat_log`, `emailed: yes`, `updatedAt 16:00:17.331Z`. Every
row since carries `emailed: no`.

`Mark Emailed` sits downstream of `Send Pulse`, so it has not run either, and
`lastEmailed` is frozen at that same timestamp in every beat's vitals. The
`Only If Email` gate reads that value, finds it stale, and opens on every run.
That is why all seven failed rather than only the daily one. The failure feeds
itself, which is the loud direction and is worth keeping.

The node's own note is now falsified by measurement and the comment should be
read with that in mind: "Moved off Gmail OAuth 2026-09-05. An SMTP password does
not expire silently the way a refresh token does." It did.

## Why nothing reported it

`scripts/pulse_watchdog.py` read one thing, the newest `pulse` row's `beat_at`,
and judged the estate on it. `Record Beat` sits on a branch parallel to the
email branch, both fed by `Compose Pulse`, so the row lands about 150ms into a
run that then takes twelve seconds to die. Execution 729 started at
04:00:15.037Z and wrote row 116 at 04:00:15.184Z. The watchdog read that row at
03:34:07Z on its own schedule, computed 5.6h, and printed:

```
OK: the Pulse last beat at 2026-09-21T22:00:15.119000Z, 5.6h ago, inside the
7.5h threshold. 96 pulse row(s) read.
```

That beat belongs to execution 714, which errored. The line is arithmetically
correct and completely wrong about the thing it exists to say.

This is the third instance in one arc of the same shape. A Cerebras node with
`neverError` turns a provider refusal into a successful execution. A workflow
with `saveDataSuccessExecution: none` leaves a successful run with nothing to
read. And now a beat row written before the failure that kills the run. In all
three the monitor reads an artifact that is produced before the thing it is
meant to detect, so the artifact keeps arriving while the organ dies behind it.
The first law names this as asserting when the check was cheap and sitting right
there. The estate commits the same error the prose warns about.

The workflow file predicted it in writing on 2026-09-17: "An alerting path with
its own SMTP credential would be one more thing that can rot quietly, which is
the failure this estate has already paid for once, when the Pulse's own Gmail
credential died on 1 September and every alert after it died at the send with
nobody told." That prediction came true three days later against the replacement
credential. The watchdog was right to keep itself off SMTP and still could not
see the outage, because it was reading the wrong signal rather than the wrong
channel.

## What changed

The beat is now a necessary condition and no longer a sufficient one. The script
also asks n8n for errored executions of the Heartbeat workflow itself, over
`/api/v1/executions?status=error&workflowId=...`, the same filter
`scripts/provider_watchdog.py` already proves against this instance. An errored
run inside the same 7.5h window is an alarm, and the script opens the newest one
to name the failing node in the message.

`verdict` keeps its contract and answers whether the beat is fresh. A new
`run_verdict` answers whether the run that wrote it finished. `combine` takes
both, and lets ALARM beat CANNOT_CHECK on purpose, because a known dead Pulse is
news and an unreadable run list is the absence of news. A fresh beat with an
unreadable run list returns CANNOT_CHECK rather than OK, since half a check is
not a pass.

Graded honestly, because over-calling a finding is its own error: one transient
failure now turns the job red for up to 7.5h, which is two or three red runs and
two or three emails about something already recovered. That trade is right only
because this shape has cost the estate twice, nine days of dead Gmail OAuth from
2026-09-01 and thirty six hours of dead SMTP from 2026-09-20, and in both cases
the channel that should have reported it was the channel that had failed. The
Heartbeat runs four times a day. One failure is worth one red job.

## What proves it

Ten tests, with the fixtures copied verbatim out of the live instance on
2026-09-22: the seven errored executions with their real ids and timestamps,
deliberately not in newest-first order, and execution 729 opened with
`includeData=true` and trimmed to the keys the script reads.

The load bearing case replays the outage and carries a negative control that
asserts the beat reading, on its own, still returns OK on the same data. Without
that control the test would pass against an implementation that had changed
nothing, which this repository has shipped before.

Two tests drive `main` itself rather than the pure functions, because
`verdict` and `run_verdict` are separate and `main` is the only place that knows
both have to run. Mutating `main` back to the beat only reading turns exactly
those two red and leaves the other twenty one green, then restoring turns them
green again. That is the measurement, not a claim about it.

The standalone job list returns 1002 passed, up from 992 by the ten added, and
`ruff check .` is clean across the repository.

## What is left, and whose it is

The credential is Tee's and only Tee's. A new Gmail app password on
`tdveal74@gmail.com` pasted into the n8n credential `AgSGuaA2pnZsrZcJ` revives
the Heartbeat and the Error Alarm together. Nothing in this repository can do
it, and this session never handles the secret.

Until then every DEVON email is going nowhere, including DEVON's own reflection
of 2026-09-22T06:15:30Z, row 117, which asks Tee to attach the n8n vps connector
to a standalone reflection Routine so his voice stops needing a build session
awake. That reflection is `emailed: no` like the rest.

Unverified here, and named rather than papered over: this session cannot reach
the VPS with an API key, so `run_verdict` is proven against fixtures and the
live path is proven only by the same `get_json` helper the existing beat read
already uses in production. The first real run of the changed script on `main`
is the measurement that closes it, and it should ALARM on the current outage
rather than pass.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_a-fresh-beat-is-not-a-finished-run_v1_2026-09-22-0624
DATE: 2026-09-22
DECISIONS: the beat check was kept and demoted from sufficient to necessary rather than replaced; the run check reads errored executions of the Heartbeat rather than inspecting a status field whose name has moved across n8n versions; ALARM beats CANNOT_CHECK in combine so a definite finding is never masked by a partial read; a fresh beat with an unreadable run list returns CANNOT_CHECK rather than OK; the failing node name is a nicety that can never downgrade a correct alarm; one transient failure going red for up to 7.5h was accepted on the record rather than tuned away
FINDINGS: all four of DEVON's alerting lanes send on one Gmail app password AgSGuaA2pnZsrZcJ and it is dead, counted from the workflow list rather than from a lane; the OS Error Handler that every pipeline names sets onError continueRegularOutput on its send, so it reports SUCCESS while no fault email goes anywhere; DEVON Heartbeat failed seven consecutive runs 2026-09-20T16:00 through 2026-09-22T04:00, every one at Send Pulse on SMTP credential AgSGuaA2pnZsrZcJ with 535-5.7.8 Username and Password not accepted; the DEVON Error Alarm dies on the same credential one second after each failure, so the alarm and the organ it watches share one point of failure; the Pulse watchdog reported OK throughout because Record Beat writes its row about 150ms into a run that takes twelve seconds to die; Mark Emailed never runs so lastEmailed is frozen and Only If Email now opens on every run, which is why all seven failed rather than only the daily one; the last email that reached Tee was 2026-09-19T16:00:15Z and every row since reads emailed no; this is the third instance in one arc of a monitor reading an artifact produced before the failure it exists to catch; the node comment claiming an SMTP password does not expire silently the way a refresh token does is falsified by measurement
OPEN: the SMTP credential is Tee's to replace and nothing here can do it, so the Heartbeat and the Error Alarm stay dead until he does; DEVON's reflection of 2026-09-22T06:15:30Z asks for the n8n vps connector on a standalone reflection Routine and is itself unemailed; the live path of the new run check is unproven from this container because no API key is reachable here, and the first scheduled run on main is what closes it; the new run check covers the Heartbeat only, so the Pipeline Watchdog and the soft failing OS Error Handler are still unwatched by anything; whether DEVON's alerting gets a second channel that does not share one credential is a ruling for Tee and was not taken here
STATUS: scripts/pulse_watchdog.py now reads the beat and the runs, with run_verdict, newest_failure, combine, fetch_failed_runs and failure_detail added and the HTTP helper factored; ten tests added from live fixtures including a negative control and two that drive main; mutating main back to the beat only reading turns exactly those two red and restoring turns them green; standalone list 1002 passed, ruff clean, pulse-watchdog.yml records the outage and the accepted cost
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
