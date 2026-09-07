---
title: Austin Marchese six step automation framework, analysed and scoped against the estate
type: SYS_OPS
version: 1
date: 2026-09-07
area: Systems
status: analysis-complete-three-imports-proposed-awaiting-ruling
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: 3f0bf4c
branch: claude/video-analysis-incorporation-9h6rtc
supersedes: none
---

# Austin Marchese, "The Easiest Way to Automate 99% Of Your Life With Claude"

## Verdict in one paragraph

Five of the nine points in his framework are already in place here, one is
half in place, and three are not. The five already in place are the load
bearing ones, and they are built harder here than in his stack. His headline
architectural insight, skill driven automation, is this repository's existing
design and is documented in `CLAUDE.md` for a stronger reason than the one he
gives. His reusable utility pattern is in production as sub workflow
`o4ctniOsIq2VSfgm`, called from 27 nodes across TSWS 01 to 05. Three ideas are
worth importing, one piece of his advice should be rejected outright for this
operation, and one question he asks lands on a live defect in six active
scheduled workflows. The video is good general teaching. It is not a blueprint
for a 64 workflow estate, and adopting his stack wholesale would be a
downgrade.

## Source record

| Field | Value |
|---|---|
| Video | The Easiest Way to Automate 99% Of Your Life With Claude |
| Channel | Austin Marchese, 88,200 subscribers |
| Video id | `ktY1b2-OKRA` |
| Duration | 22:34 |
| Published | 2026-09-07 13:45Z |
| Read at | 2026-09-07 search snapshot: 3,215 views, 84 likes, 19 comments, 459 views per hour. The vidiq hourly series near the same time reports 487 views per hour; the two are not reconciled here |
| Sponsor | CodeRabbit, mid roll at about the 25 percent mark |
| Evidence | Full transcript pulled through vidiq and read end to end, not skimmed |

His stated minimum viable stack: Claude Routines for the trigger, Claude
Skills for the logic, the Claude desktop app for monitoring. Every automation
is trigger plus logic plus monitoring, and his argument is that complex
setups lose on maintenance cost, not on capability.

## His six steps, measured against what is already here

| His step | State in this estate | Evidence |
|---|---|---|
| 1. Automation spike: build the ugliest end to end version first to prove no blockers | Practised informally, never named or required | no repository hit for the pattern |
| 2. Make results transferable: the routine references a skill file, so updating the skill updates the routine | Already the architecture, for a better reason | `.claude/skills/` carries six committed skills; `CLAUDE.md` records that `~/.claude/skills/` is ephemeral in a web session, so anything that must load is committed |
| 3. When, how often, where to run | Thirteen active workflows run on an enabled schedule trigger; six of them carry a real defect, see below | `docs/devon/n8n-cloud-census_2026-09-06.json` |
| 4a. Calibrate, net new features, output format | Ordinary practice here | not a gap |
| 4b. Self correcting and self breaking systems | Half present. Failure is caught after the spend, not before it | DEVON Error Alarm and OS Error Handler are both error triggers, which fire on a crash that already happened |
| 5a. Utility skills, so one fix propagates | Already in production at scale | `o4ctniOsIq2VSfgm` is TSWS 00 Render Job, called from 27 nodes across TSWS 01 to 05 (01 six, 02 nine, 03 three, 04 five, 05 four) |
| 5b. Consolidate notifications to one place you actually check | Present | SMTP to Tee, plus the approval queue |
| 5c. Explicit updates, his "green light drift" | Absent as a rule, and the estate has already been bitten by it | see import one |
| 6. Constraint driven versus enhancement automation, and prune the rest | Absent as a filter | 64 workflows, 39 active, throwaways still resident |

## The three imports, in priority order

### 1. Green light drift, his highest value idea and the only one that is urgent

His rule: an automation must report what it actually did, with counts, not
that it succeeded. Not "daily brief ran". Instead "analysed 41 of 41 emails,
200 Slack messages, 10 calendar events". The operator then reads the number
and knows instantly whether the run was real. He calls the failure mode green
light drift: AI reporting success for work it did not do.

This is the same law as the first law in `CLAUDE.md`, pointed at machines
instead of at the agent. `CLAUDE.md` governs what a session may assert.
Nothing governs what an automation may assert. That asymmetry is the gap.

The estate has already paid for it once. Per
`docs/devon/SYS_OPS_devon-learning-capture-and-execution-burn_v1_2026-09-06.md`,
nothing told the job envelope it had been fed, so every driver run job read
`not_captured` forever, and the Face, the Heartbeat and the operational
report all repeated it. Three surfaces confidently reported a wrong state.
That is the same class of defect, running in the opposite direction.

Proposed rule: every scheduled workflow's terminal notification names the
counts it processed and the source it read them from. Nothing ships a bare
success string.

### 2. Self breaking preflight

His rule: before an automation does anything, check that every connection it
needs is available, and if one is missing, stop immediately with a message
naming the fix. Break fast and early rather than burning tokens on work that
was never going to complete.

The estate catches failure after the spend. DEVON Error Alarm and OS Error
Handler are error triggers, so by definition they run only once a workflow
has already crashed. A preflight gate is a different thing and is not present
as a named pattern.

This lands directly on an open ruling. The 2026-09-06 burn document measured
314 saved executions in 24 hours, and from the quiet window 11 an hour, about
264 a day (that document, lines 144 and 156). Its own verdict paragraph words
this as "264 an hour by hour steady state", which reads as a rate and is not
one; the body is authoritative. The levers to cut it were left as Tee's
decision. A preflight that refuses a run whose dependencies are down is one of
those levers, and it is the one that costs nothing in capability.

### 3. Constraint versus enhancement, and pruning

His filter: an automation either removes a constraint in the day or increases
the value produced. If it does neither, do not build it. And because the world
is dynamic, an automation that used to help may no longer help, so pruning is
part of the job.

The census shows 64 workflows, 39 active, 6 unreadable, with items still
resident that are named as disposable, including a credential probe explicitly
labelled throwaway, a one off directory correction, and a smoke test. This is
a cheap, low risk sweep and a good use of the existing `estate-reconcile`
lane rather than a new build.

## The rejection

**"Stay local unless you can't."** Wrong for this operation, and it should not
be imported even as a default.

His reasoning is sound in general: an external machine adds variables you have
not tested. His own stated exception is that work which cannot miss a run
belongs in the cloud. This estate is entirely inside that exception. There is
no always on local host to hang a trigger on (Tee's stated primary device is
an iPhone 15 Pro; no repository file records a device, and the Chromebook line
in `docs/FLAGSHIP_SPEC.md` is the product's rendering viewport, not an
operator machine), and the scheduled lanes carry ledger feeding, backups,
purges and watchdogs where a missed run is a real cost. Cloud is already the
correct answer here and is already the answer in place.

Recording this explicitly so a later session does not read his rule as
guidance and try to move a lane local.

## The live finding

Six of the thirteen active scheduled workflows set no workflow level timezone,
so their hour resolves in the instance default rather than an intended one.
Read from the 2026-09-06 census, which is the record and not the instance:

| Workflow | Schedule | Census note |
|---|---|---|
| DEVON Build 12 Ledger Feeder | daily 02:00 | no workflow timezone set |
| DEVON Capture Nudge | daily 08:00 | no workflow timezone set, resolves in instance default |
| DEVON Ledger Janitor | daily 02:30 | sets no timezone, the description says UTC |
| DEVON Pipeline Watchdog | every 4 hours | no workflow timezone set |
| DEVON Precedence Guard | daily 07:00 | no workflow timezone set |
| DEVON Weekly Table Backup | weekly Sunday 03:10 | sets no timezone, the description says UTC |

Others in the same estate do set it explicitly to `America/New_York`, which is
what makes this a drift rather than a house convention. The risk is not
theoretical after the n8n Cloud to VPS cutover, because the instance default
is a property of the host and the host changed.

**Unverified.** This is read from a census one day old. The live instance is
the authority and has not been read in this session. Confirm against the
instance before changing anything.

## Second incorporation path: the format, for TQO

Austin is a direct peer in the TQO lane, presenter led AI teaching, 88,200
subscribers. His ceiling is higher than one video: his top three long form are
845,043 views (breakout 28.38), 560,384 (50.17) and 380,732 (276.34), with
207,667 (4.3) fourth. Two are over 500,000. His format is worth reading as a
competitive artifact, not only as content, and he should be read as a serious
operator in this lane rather than a mid tier one.

What his format confirms about the TQO standard. That standard is Tee's
stated operating preference (learning objective in the first 30 seconds, a
three to five step checklist); no file in this repository carries it, which is
itself worth fixing:

- He states the learning objective inside the first 30 seconds, at 0:00 to
  0:29, before any teaching. Same rule.
- He carries a numbered checklist through the whole runtime and recaps it
  twice, at step six and at the close. His six is above the three to five
  range and he needs two recaps to hold it, which is an argument for staying
  at the lower end.

The one beat worth taking:

- **"On screen is a prompt you can run."** He repeats this at every step. It
  converts a teaching video into an artifact the viewer leaves with, and it is
  proof rather than claim, which fits the anti hype positioning exactly. The
  stated TQO format has the checklist but no takeaway asset.

What to leave:

- The subscription giveaway for comments. Engagement bait, off brand for a
  calm anti hype channel.
- The resume flex biography block in the description. Off brand.

## Recommended order, smallest surface first

1. Confirm the six timezone entries against the live instance, then set them.
   Cheapest, and it is a correctness fix, not a feature.
2. Write the explicit outcome rule into the house conventions in the
   `devon-learning-lane` skill, then apply it to the scheduled lanes one at a
   time, starting with the Ledger Feeder.
3. Add a preflight refusal to the same lanes, as one of the burn levers.
4. Run the prune as an `estate-reconcile` pass.
5. TQO format change is independent of all of the above and can run in
   parallel.

## What was not verified in this session

- The live n8n instance was not read. Every workflow claim comes from
  `docs/devon/n8n-cloud-census_2026-09-06.json`, dated one day before this
  document.
- No workflow was inspected node by node for whether it already reports
  counts. The green light drift item is a proposal for a house rule, not a
  defect report against a named workflow.
- The TQO format claims come from Tee's stated operating preference, not from
  any file in this repository. No repository artifact records the TQO video
  format, and `TQO FINAL V5` is marked inactive in the census while
  `OPERATOR.md` line 113 still lists it active. That drift predates this
  document and is not addressed by it.
- The device premise behind the rejection is Tee's stated preference, not a
  repository fact. The argument only needs "no always on local host", which
  holds on any candidate device.
- The two views per hour figures (459 and 487) come from different vidiq
  surfaces at close times and were not reconciled.
- Nothing in this document was executed, changed or deployed. It is analysis
  and a set of recommendations. Every item above is Tee's ruling.

This version corrects four errors caught by an adversarial review before
commit: a burn rate stated per hour that the source states per day, an active
scheduled workflow count of sixteen where the census supports thirteen, a
timezone finding that listed five of the six affected workflows, and an
underived "eighty percent" carrying the verdict.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_austin-marchese-automation-framework-incorporation_v1_2026-09-07
DATE: 2026-09-07
SOURCE: youtube ktY1b2-OKRA, Austin Marchese, full transcript read
DECISIONS: none, three imports proposed and one rejection recorded, all awaiting Tee's ruling
FINDINGS: six of thirteen active scheduled workflows carry no workflow timezone, unverified against the live instance
STATUS: analysis complete, nothing executed
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
