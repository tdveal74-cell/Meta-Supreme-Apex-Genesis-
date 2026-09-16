# The Command Center had no browser guard

2026-09-16. Tee asked whether the Unified Command Center is wired correctly and
whether DEVON is operationally green end to end. The wiring is correct and the
page is green, proven in a browser rather than asserted. The audit that proved
it found that nothing in CI had ever looked at the six status cards, so this
also adds the check that would have caught a lie there, and shows it failing on
four real mutations before trusting it.

DEVON end to end is not green. Two things are open on the VPS and neither is in
this repository.

## What was checked, and how

Every API path the route reaches was read off the five components it mounts and
the three they mount in turn, then cross checked against the app's own route
table. The table came from `app.openapi()["paths"]` on a booted app, not from a
grep and not from `router.routes`, which this FastAPI version makes lazy. Twenty
six distinct paths, none missing. `/operator/shell` is the one WebSocket, at
`app/api/v1/operator_shell.py:108`. The four `VpsActionGate` proxy actions are
all in the handler's own allowlist at
`apps/web/app/api/devon-ops/[action]/route.ts:11`.

Then the page was driven. PostgreSQL built from empty with `alembic upgrade
head` to `019_event_hash_chain`, the FastAPI app on 8000, a built Next server on
3000, Chromium 1194 under Playwright 1.56.1, which is what `panel-smoke-ci.yml`
pins. Every request the page sent answered 200, nothing threw, and all six cards
matched what the API had answered to the same calls made independently.

```
DEVON API        ONLINE          /health 200
Mind             SIMULATED       mock / mock-council-v1, simulated true
Operator bridge  LOCKED          enabled false, configured false
ChatGPT layer    ROUTING READY   DEVON canonical, 7 external surfaces ready
Heartbeat        6H SCHEDULE     static, and its detail says so
Write authority  TEE             static
```

The rest of the local gates: full Python suite 2637 passed, ruff clean, web
typecheck clean, build clean, all ten honesty checks exit 0, panel-smoke 129
checks, dock-smoke 41 checks, audio-check 8 checks.

## The gap that audit found

`/command-center` mounts five components. Exactly one of them had ever been
driven from a browser: `dock-smoke.mjs` opens the route three ways and asserts
the CapabilityDock's Soul readout. `panel-smoke.mjs` covers `/control`. So the
six cards at the top of `UnifiedCommandCenter.tsx`, the first thing a person
reads when they open the cockpit, had no guard of any kind.

Every honesty check under `apps/web/scripts` reads source text or an AST.
`next build` prerenders the route and `tsc` compiles it, so a card wired to the
wrong route, reading the wrong storage slot, or hardwired to a green word would
have passed every gate this estate has. That is the same shape as the gap
`panel-smoke.mjs` and `dock-smoke.mjs` were each built to close, one route at a
time. This closes the third.

`apps/web/scripts/command-smoke.mjs` makes 31 checks over three contexts:
signed out, with a real token, and with a token the API refuses. It grades the
four live cards against what the run's own API calls returned rather than
against sentences pinned in the file, captures every request off the wire and
asserts the bearer only on the route that needs one, reads each light's and each
word's computed colour, and checks `document.elementFromPoint` at the centre of
both so nothing painted over them counts as visible. It also walks every element
inside the section for opacity, visibility, filter, background image, transform,
clip path, font size and pseudo element content, because a critic working on the
dock in this same route on 2026-09-15 made four lies that `innerText` could not
see.

The three contexts are the load bearing part. A card that can only ever be green
passes one signed in pass and fails all three.

## Proving it bites

The check was run against four mutations of the real component, each reverted
after. A check that has never failed is a check nobody has tested.

```
setMindState("offline") -> ("online") on a refused probe
    red, 'LIVE' !== 'OFFLINE' on the refused token context

the operating layer fetch repointed at /health
    red, "the CHATGPT LAYER card says OFFLINE while the API answered ROUTING READY"

opacity-0 added to the detail paragraph in StatusCard
    red, "something inside the status section is painted in a way innerText
    cannot see", naming every hidden line and its text

the Heartbeat card deleted
    red, "the status cards are no longer the six pinned labels in order"
```

Each named the defect rather than timing out, which is the difference between a
check that reports and a check that merely goes red.

## A trap that cost three diagnoses

Two of those runs first came back as a settle timeout with nothing named, and
the first reading was that the new check was flaky. It was not. `next start`
serves the build it loaded at boot, so rebuilding `.next` underneath a running
one leaves it handing out HTML that names chunks only the new build carries.
Chromium then gets 400 on
`/_next/static/chunks/app/command-center/page-*.js`, React never hydrates, the
section never renders, and the only symptom is the timeout.

What made it recur is that `npx next start` is three processes, so killing the
first `pgrep` match leaves one bound to 3000 and the replacement fails silently
while the stale server keeps answering. Measured by watching the page: at t+0 it
rendered five cards, which was the previous mutation's build. CI does not hit
this, because the job builds once and then starts the server. The trap is
written into the script's own docstring so the next operator reads it before
re-deriving it.

## The favicon

`/favicon.ico` returned 404 on every navigation of every route, one console
error per page load, because no icon asset existed. `apps/web/app/favicon.ico`
is now a 32 by 32 icon carrying the mark the header already draws: the copper
ring, the dark field, the teal core. Verified the way the fault was found, by
re-running the browser probe and reading the console: errors none.

## What production is serving

Read back on 2026-09-16 at about 05:10Z against main at `18a285a`.

| Surface | State | Evidence |
|---|---|---|
| Railway `api` | live and current | `acb439a5` SUCCESS, created 04:57:17Z, finished 05:04:29Z, on `18a285a`; the alembic pre deploy hook ran at 05:04:20Z with nothing pending |
| Railway `scheduler-cron` | live and current | `dc5e24e1` SUCCESS at 05:05:07Z on `18a285a` |
| Railway `presence` | current on its own terms | last SUCCESS `5ed2ce17` at 04:29:06Z on `3993885`; `18a285a` SKIPPED and `3993885..origin/main` over `apps/presence` is empty |
| `meta-supreme-apex-genesis-web` | current on its own terms | last real production build `dpl_5VrhS1HydvNQwHCP2XoFNeFeUqyZ` READY on `56c3f40`; every production record since is CANCELED, and `56c3f40..origin/main` over `apps/web`, `packages/ui` and both lockfiles is empty |
| `devon-soul` | current on its own terms | `dpl_2NJr6w2Zt65SKVppHnVSGTSAhGr9` READY, target production, on `3993885`; `3993885..origin/main` over `deploy/soul` is empty |

Both Vercel skips were checked by hand against each project's own
`ignoreCommand` paths rather than trusted, which is what the `deploy-readback`
skill asks for. Nothing is owed to either surface.

One thing the `deploy-readback` skill does not name: Railway carries five
services in `devon-api`, and `scheduler-cron` appears nowhere in the file whose
whole job is knowing what production serves. The skill counts four surfaces.
That is the same count from the lane rather than from the estate that CLAUDE.md's
first law describes, and it is now recorded rather than fixed, because changing
that skill is its own arc.

The presence service is the only surface that reads itself back, and its
`/health` could not be read from this container. The network policy blocks
`*.up.railway.app`: curl gets a 403 on CONNECT from the agent proxy. So
`speech`, `livekit_configured`, `cors_origins` and `breaker` are unverified
here. Tee or a session with egress can read them.

## DEVON on the VPS is not green

**TQO FINAL V5 is red and its fix is unproven.** Its last two scheduled passes
both errored: execution 178 at 01:00:00Z and execution 226 at 04:00:00Z, both on
node `Render Lock: Other Brand`, both `Filter validation failed: Column(s)
"status" do not exist in the selected table`. That is the mirror table collision
PR #241 was written to fix.

The root cause is cleared at the data layer, checked rather than assumed:
`tqo_content` now resolves to exactly one table, `2GtmrFcTNqVMbddh`, carrying
`status` at column index 0, and the same read the failing node makes,
`tqo_content` filtered `status eq Rendering`, came back clean with zero rows and
no schema error. The lane has not run since. Its trigger is `Every 3h - Pipeline
Pass` and it last fired at 04:00Z, so the next pass is 07:00Z. Nothing has
proven the fix in production. The lane was deliberately not run by hand: it
claims rows, spends provider credits and writes to Airtable, so that is Tee's to
trigger.

**DEVON's own heartbeat is carrying an open finding.** Row 89 of
`devon_heartbeat_log`, beat at 04:00:15Z:

```
feeder_silent | COMPLETED jobs the feeder has not fed after 40 minutes
(feeder may be down, check its executions): 01M2KT8WM4RPZ90BCTZPVXH6HK
```

The Build 12 Ledger Feeder has zero executions on the VPS. Its only trigger is a
daily 02:00 America/New_York schedule, which is 06:00Z, and the cutover was
2026-09-15T22:00:24Z, so its first slot on the new host had not come around when
this was written. The Cloud copy, workflow `6hQD8YhiYzR1FFda`, carries the
identical single `Daily 02:00` trigger, so the port dropped nothing. The feeder
is unproven on the new host rather than proven down. A 40 minute silence
threshold watching a once daily feeder will fire on every beat between a job
completing and the next 02:00 ET, which is a threshold that does not match the
thing it watches.

Two things that are green on the VPS and worth saying: the heartbeat beat on
schedule at 04:00:15Z with a correct six hour gap from 22:00:24Z, and OS 29
succeeded at 04:49:45Z, which is the first live proof of PR #237's Cerebras
swap.

One thing that looked red and is not. Six webhook workflows errored together at
2026-09-15T23:39:31Z: the Event Bus, EditForge Handoff, the Conscious and
Subconscious Runtime, the Intelligence Router, the Live State Ledger and the
Spine Conformance Executor. Execution 138 carries the reason: the body was
`{"probe":"vps-cutover-door-proof"}` and the Event Bus answered `REFUSED: no
envelope`. That is the cutover door proof and the guards refusing a malformed
body, which is the method working.

## What is still open

The presence `/health` read cannot be made from an agent container on this
network policy, so four of its nine keys are unverified until Tee or an egress
capable session reads them.

TQO FINAL V5's next scheduled pass is 07:00Z and the Ledger Feeder's is 06:00Z.
Both need a look; neither was forced.

The heartbeat's `feeder_silent` threshold is 40 minutes against a feeder that
runs daily. Left alone deliberately, because changing an alarm to stop it
complaining is how an alarm gets ignored, and the right answer is Tee's call.

The `deploy-readback` skill counts four production surfaces and the estate has
five. Recorded here, not fixed here.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-command-center-had-no-browser-guard_v1_2026-09-16h.md
DATE: 2026-09-16
DECISIONS: Tee ruled to do all three of the audit's recommendations: add a browser guard for the Command Center status cards, add the missing favicon, and file this status doc. The TQO FINAL V5 lane was deliberately left to its own 07:00Z schedule rather than triggered by hand, because a real pass claims rows, spends provider credits and writes to Airtable, which is Tee's call and not a session's. The heartbeat's 40 minute feeder_silent threshold was left alone rather than widened to stop it firing, because retuning an alarm to silence it is how an alarm stops being read. The deploy-readback skill's four surface count was recorded rather than corrected, because changing that skill is its own arc.
FINDINGS: The Unified Command Center is wired correctly. All twenty six distinct API paths the route reaches resolve against the app's own OpenAPI route table, and the page was driven in real Chromium against a stack built from empty, where every request answered 200 and all six cards matched what the API independently returned. The gap the audit found: no check in CI had ever looked at those six cards. dock-smoke.mjs covers one of the five components the route mounts and panel-smoke.mjs covers /control, so a card wired to the wrong route or hardwired to a green word would have passed every gate. command-smoke.mjs now makes 31 checks over three contexts and was proven to bite on four real mutations of the component, each naming the defect rather than timing out: a refused probe lit green, the operating layer fetch repointed at /health, the detail line hidden with opacity-0, and the Heartbeat card deleted. Two of those runs first read as a flaky settle timeout and were not: next start serves the build it loaded at boot, and npx next start is three processes, so killing the first pgrep match leaves a stale server handing out HTML whose chunks the new build does not carry, Chromium gets 400 on its own JavaScript, and React never hydrates. Written into the script's docstring. /favicon.ico had been 404 on every navigation of every route; an icon carrying the header's own mark now serves and the console reads clean. Production is current on all five services, with both Vercel skips verified by hand against each project's own ignoreCommand paths. Railway carries a fifth service, scheduler-cron, that the deploy-readback skill does not name. DEVON on the VPS is not green: TQO FINAL V5 errored at 01:00Z and 04:00Z on the mirror table collision, and although the root cause is cleared at the data layer, verified by running the failing read itself, the lane has not run since. DEVON's own 04:00:15Z beat carries feeder_silent naming job 01M2KT8WM4RPZ90BCTZPVXH6HK, and the Build 12 Ledger Feeder has zero executions on the VPS because its daily 02:00 ET slot has not come around since the cutover; the Cloud copy carries the identical trigger, so nothing was lost in the port. The six webhook errors at 23:39:31Z were the cutover door proof being correctly refused, not a fault.
OPEN: The presence service /health cannot be read from an agent container because the network policy blocks *.up.railway.app with a 403 on CONNECT, so speech, livekit_configured, cors_origins and breaker are unverified. TQO FINAL V5's next scheduled pass is 07:00Z and the Ledger Feeder's is 06:00Z; both need a look and neither was forced. The heartbeat's feeder_silent threshold is 40 minutes against a daily feeder, so it will keep firing between a completed job and the next 02:00 ET until Tee rules on it. The deploy-readback skill counts four production surfaces and the estate has five.
STATUS: The Command Center is wired correctly and green, proven in a browser and now guarded by 31 browser checks wired into panel-smoke-ci.yml, with the guard shown failing on four mutations of the real component. The favicon 404 is closed and re-measured. Production is current on all five services. DEVON end to end is not green, and the two open items are both on the VPS and both waiting on a clock rather than on work.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
