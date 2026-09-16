# Four open items, closed or handed back

2026-09-16. The Command Center arc left four things open. Tee ruled "fix it
all". Two are fixed and proven, one is a guard against the class of fault rather
than the instance, and one cannot be fixed from a session at all. This says
which is which, because a list that reports four fixes when one of them is a
handback is the kind of green that costs a morning.

## 1. The heartbeat cried wolf about the feeder, and was blind to a real one

DEVON's 04:00:15Z beat reported `feeder_silent` against the Build 12 Ledger
Feeder. The feeder was armed, correct and simply not due: it runs once a day at
02:00 America/New_York, and the rule called any COMPLETED job unfed after forty
minutes.

That threshold matched nothing, and it was wrong in both directions.

It was a **false positive on every beat**. A job completing at 03:00 ET is not
late at 03:40; it is waiting for a slot twenty three hours away. The rule
alerted until the feeder ran, which on 2026-09-16 meant the one finding DEVON
carried about himself was untrue.

It was also a **false negative in the case it was named for**. Its own text said
"feeder may be down", but the loop only looked when a COMPLETED job happened to
be waiting. A feeder that died during a quiet week was invisible to it. That is
the worse half, and nobody had noticed it because the noisy half was so loud.

So the one finding is split in two, and neither reads a wall clock guess. Both
read the feed log's own newest `fed_at`:

| finding | fires when | what it means |
|---|---|---|
| `feeder_down` | the newest `fed_at` is more than 26h old, or there is none | the feeder missed its daily slot, whether or not anything is waiting |
| `feeder_skipped` | the feeder ran AFTER a COMPLETED job and still did not carry it | a defect, visible on the first beat after the feeder's own slot |

`feeder_down` needs at least one COMPLETED job to have existed ever, so a
genuinely empty estate is not alarmed at forever.

**Proven against what it replaces.** `n8n/devon/heartbeat/compose_pulse.test.mjs`
runs the real node body over six sets of rows, including the real rows of that
morning, and reimplements the retired rule in eight lines purely so the test can
show it firing where the new one is silent. A fix nobody measured against the
behaviour it replaces is a claim.

```
A  the real 04:00Z estate          feeder_down fires, feeder_skipped does not
B  after the feeder ran at 06:00Z  neither fires
C  feeder ran and passed a job     feeder_skipped, naming that job and no other
D  a job waiting for its slot      silent, and the OLD rule fired here
E  feeder dead 180h, all jobs fed  feeder_down, and the OLD rule was blind
F  nothing has ever completed      silent
```

Cases D and E are the point. D is the false positive, E is the false negative,
and the old rule is shown doing both.

Live on the VPS as version `738d6d58` of workflow `EEDrp2jLlw2Ssd5b`. The
version diff confirms exactly one node and exactly one field changed, nothing
added or removed, and the new value read back matches the mirror. The previous
version is `6cb17f49` if it needs to go back.

**It was NOT proven by a manual run, on purpose.** Firing the heartbeat by hand
writes a row into `devon_heartbeat_log`, which is where DEVON's continuity
lives: an off schedule pulse becomes the next beat's `previousPulse`, and it
would likely email Tee a duplicate. The 10:00Z beat proves it on its own
schedule at no cost, and a check-in is armed to read it.

## 2. The Data Table name collision has a guard now

A Data Table resolved in NAME mode is only as stable as every other name in the
project: a new name that merely CONTAINS an existing one captures it. That is
what took the TQO lane down silently for four and a half hours on 2026-09-15.

The hazard belongs to the NAME SET, not to any workflow, which is what makes it
checkable in one place for all 73 by-name nodes at once.
`services/devon/data_tables.py` is the pure detector,
`scripts/n8n_table_collision_check.py` runs it against a live project, and
`test_devon_data_tables.py` proves it bites:

```
the live 52 table estate               exit 0, no collisions
the estate at 2026-09-15T23:38Z        exit 1, all three real pairs named
an estate it cannot read               exit 2, refusing to call it safe
```

Exit 2 is a third answer deliberately. A check that cannot see the estate must
never report it clean, which is how the original incident stayed quiet: 72 of
the 73 nodes returned zero rows and carried on.

The rule is written into the n8n house conventions, which CLAUDE.md already
sends every session to before it touches any DEVON workflow.

**What this is NOT.** It does not convert the 73 nodes to id mode. That is the
durable fix and it is still unstarted, because Tee ruled on 2026-09-16 that
renaming the table beats editing the workflows: one rename fixed all 73 nodes,
while V5 alone would have meant 31 changes inside 240. Reopening those 31 nodes
in the lane that recovered this morning is his call and not a session's. The
guard makes the hazard loud; the conversion would make it impossible.

## 3. deploy-readback counted four surfaces and the estate has five

`list-services` on the Railway project answers `api`, `presence`,
`scheduler-cron` and `Postgres`. Only two were named in the file whose whole job
is knowing what production serves. `scheduler-cron` deploys from the same commit
as `api` and had been deploying the whole time, unwatched.

That section said three until 2026-09-09 and four until today, and both
corrections came the same way: somebody counted from the estate instead of
reading the list. It now says so, and says to count from `list-services` and
`list_projects` rather than from its own table.

## 4. The presence health read cannot be fixed from a session

`GET /health` on the presence service is the only self read this estate has, and
an agent container cannot make it. Measured again today: the network policy
blocks `*.up.railway.app` and curl gets `CONNECT tunnel failed, response 403`
from the agent proxy. That is a policy denial, not an outage, and retrying it is
wasted.

So `speech`, `livekit_configured`, `cors_origins` and `breaker` stay unverified
from a container, every time, until the policy changes. The remedy is Tee's and
it has a precedent: both n8n hosts were 403 blocked the same way until he added
them under Custom allowed domains in the Claude Code environment settings, and a
key alone was not enough. Adding `presence-production-d272.up.railway.app`, or
`*.up.railway.app` for both Railway hosts, closes it the same way.

This is written into `deploy-readback` rather than left as a session's memory,
so the next session says unverified instead of inferring it from a deployment
record.

## What the local validation caught

Three things, and each was the kind that a green run in the wrong place would
have hidden.

`test_deploy_soul.py` builds its vendored module map by globbing
`services/devon/*.py`, so a new module there is not optional in the phone lane:
it must ship into `deploy/soul/services/devon/` byte identical or the parity
test fails. `data_tables.py` did, on the first full suite run, and the fix was
to ship the copy rather than to exempt the file. That also pulls this branch
into `web-ci.yml`, whose path filter carries `deploy/soul/**`, so the ten
honesty checks and the production Next build are in scope for this pull request
and were run here: all ten clean, build clean.

The mirror's own claim got measured instead of asserted. `compose_pulse.js`
says it is what runs, so the live node's `jsCode` was read back from version
738d6d58 and diffed against the file. From the first `const` to the last line
the two are identical, 12013 bytes each, no differing line. The header differs
on purpose and says so in its own text: the live copy names the workflow by its
display name, which carries an em dash this repository does not ship, so the
file names it by id. Aligning the headers would cost a republish of an active
workflow for a comment, and the version the 10:00Z beat has to prove is the one
already published.

The cold re-read found one more, in the checker written an hour earlier. A
mistyped path fell out of `main` as an uncaught `FileNotFoundError`, and Python
exits 1 on that. Exit 1 is this checker's alarm code, so a typo would have
reported collisions that nobody had looked for and sent the next reader hunting
a rename nothing needed. The unreadable case now catches `OSError` too and exits
2 with the rest, and a test drives a path that does not exist. Three answers
only work while each one means one thing.

## A fifth thing, found while reading production back

This is appended to this doc rather than filed as `l`, because a new doc today
would need a fifth letter on the day the letter raced four times, and this is
the same arc closing out.

Reading the estate back after the merge turned up something `deploy-readback`
had wrong in a way that matters more than the surface count. The file said
`scheduler-cron` deploys from the same commit as `api`. Read from
`get-service-config` instead, the three Railway services deploy on three
different rules:

| service | `source.checkSuites` | `build.watchPatterns` |
|---|---|---|
| `api` | true | none, so every commit to main |
| `scheduler-cron` | false | none, so every commit to main |
| `presence` | false | `apps/presence/**`, `services/**`, `requirements.txt` |

`checkSuites: true` means Railway holds `api` until GitHub's check suites
finish and skips it when they fail. Both halves were measured the same morning
on the same pair of commits. On the red `71f96e2` the `api` deploy waited from
08:30:08Z and turned SKIPPED at 08:35:58Z, so that commit never reached the
API. On the green `2ca6ec1` it waited from 08:39:07Z, CI run 827 passed at
08:45:08Z, and the deploy succeeded at 08:46:03Z.

`scheduler-cron` carries no such gate, and on the red commit it deployed
anyway, SUCCESS at 08:35:07Z. So for ten minutes the cron lane ran `71f96e2`
while the API served `c0a2ea9`. A red main does not freeze the estate, it
splits it, and nothing announces that. The rule is now in `deploy-readback`
with both measurements.

`presence` is the only service with watch patterns, and `services/**` is one of
them, which is wider than it reads: adding `services/devon/data_tables.py` was
enough to rebuild the voice lane.

## What is still open

The 10:00Z beat has not happened yet. `feeder_down` and `feeder_skipped` should
both be absent from it; that is expected, not verified.

Resolving Data Tables by id rather than by name is unstarted and needs Tee's
word, because it reopens the 31 V5 nodes he ruled against touching.

The presence `/health` read waits on the network policy.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_four-open-items-closed_v1_2026-09-16k.md
DATE: 2026-09-16
DECISIONS: Tee ruled "fix it all" on the four items the Command Center arc left open. The heartbeat's feeder rule was fixed at the root rather than retuned: the forty minute threshold is replaced by two findings that read the feed log's own newest fed_at, because widening a threshold to stop an alarm complaining is how an alarm stops being read. The heartbeat was deliberately NOT fired by hand to prove the fix, because a manual run writes into devon_heartbeat_log, which is where DEVON's continuity lives, and would likely email a duplicate pulse; the 10:00Z beat proves it free. The Data Table hazard got a guard rather than the id conversion, because Tee ruled on 2026-09-16 that renaming the table beats editing the workflows, and reopening V5's 31 nodes in the lane that recovered this morning is his call rather than a session's. The presence health read was handed back rather than worked around, because it is a network policy the session cannot change.
FINDINGS: The heartbeat's feeder_silent rule was wrong in both directions and only the noisy half had been noticed. False positive: it called a COMPLETED job unfed after 40 minutes while the feeder that carries it runs once a day, so the 04:00:15Z beat reported a feeder that was armed and simply not due until 06:00Z. False negative, and worse: its own text said "feeder may be down" but the loop only looked when a COMPLETED job happened to be waiting, so a feeder that died on a quiet week was invisible. Both are now proven by a harness that drives the real node body over the real rows of that morning and reimplements the retired rule to show it firing where the new one is silent, six scenarios and eight checks. Live as version 738d6d58 of EEDrp2jLlw2Ssd5b, with the version diff confirming exactly one node and one field changed and the previous version 6cb17f49 recorded for revert. The Data Table collision hazard belongs to the name set rather than to any workflow, which is why one checker covers all 73 by-name nodes at once; it reports exit 0 on the live 52 table estate, exit 1 on the estate as it stood at 2026-09-15T23:38Z naming all three real pairs, and exit 2 rather than a false green when it cannot read the input. Railway carries five services and deploy-readback named four; scheduler-cron had been deploying from the same commit as api the whole time, unwatched, and that section had already been wrong once before in the same direction. The presence /health read fails with a 403 on CONNECT from the agent proxy, which is a policy denial and not an outage. The doc letter raced again: i looked free from a directory listing and was held by open PR #243, caught by listing open pull requests, so this doc is j. Local validation added three more. test_deploy_soul.py globs services/devon/*.py to build its vendored map, so data_tables.py had to ship into deploy/soul/services/devon/ byte identical, and that also pulls this branch into web-ci.yml, whose filter carries deploy/soul/**, so the ten honesty checks and the Next build were run here and are clean. The mirror's own parity was measured rather than asserted: the live jsCode of version 738d6d58 read back and diffed against compose_pulse.js is identical from the first const down, 12013 bytes each, with the header differing on purpose and saying so. And the collision checker exited 1 on a mistyped path, borrowing its own alarm code for an unreadable input; it catches OSError now and exits 2 with the rest. The letter raced a fourth time, and this doc was the one that lost. It was named j after listing open pull requests, which was the rule as written and still not enough: PR #244 carried its own j on a branch, merged first at 08:29Z, and the collision existed only in the merge commit that followed. main went red on 71f96e2 with test_devon_receipt_shape.py naming the duplicate, and this doc is now k. The derived suffix that replaces the letter starts 2026-09-17 and would have prevented it. Reading production back after the merge found a fifth thing, appended to this doc rather than filed as l. deploy-readback said scheduler-cron deploys from the same commit as api; get-service-config says the three Railway services deploy on three different rules. api carries source.checkSuites true, so Railway holds it until GitHub's check suites finish and skips it when they fail: on the red 71f96e2 it waited from 08:30:08Z and turned SKIPPED at 08:35:58Z, and on the green 2ca6ec1 it waited from 08:39:07Z until CI run 827 passed at 08:45:08Z then succeeded at 08:46:03Z. scheduler-cron has no gate and deployed the red commit anyway at 08:35:07Z, so for ten minutes the cron lane ran 71f96e2 while the API served c0a2ea9. A red main splits the estate rather than freezing it.
OPEN: The 10:00Z beat is expected to carry neither feeder finding and that is unverified until it lands. Resolving Data Tables by id rather than by name is the durable fix, is unstarted, and needs Tee's word because it reopens the 31 V5 nodes he ruled against editing. The presence /health read stays unverified from any agent container until *.up.railway.app is added under Custom allowed domains, which only Tee can do.
STATUS: Two of four fixed and proven, one guarded at the class rather than the instance with the instance fix handed back, one handed back entirely. The heartbeat fix is live on the VPS and mirrored in the repo with a behaviour test wired into CI. The collision detector, its checker and its tests are in the repo. deploy-readback now counts five surfaces and records that the presence read cannot be made from a container.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
