# DEVON made audible, and three lanes given doors

    status: presence proven by ear; capture lane reachable; two rented voices
            removed; four stranded subsystems found and one ruled for build
    date: 2026-09-09
    supersedes: nothing. Extends SYS_OPS_audible-presence_v1_2026-09-09.md,
            which recorded the adapter as built and unheard.

## What actually happened

Tee heard his own cloned voice come out of DEVON for the first time. Measured
from the page at the moment it spoke: provider cerebras, TTFT 303 ms, breaker
closed, 8 tokens, 113 frames sent and 113 received with 0 dropped and 0 stray,
10 audio chunks scheduled with 0 late and 0 that would not decode, 1.8 seconds
of audio, playback reading playing. Nothing in that path had ever been proven
before tonight.

Getting there took fixing things that were not the voice.

## The presence service could never have been heard

Two links were missing and neither failed loudly.

`apps/web/lib/api-base.ts` resolved `PRESENCE_BASE` to `http://localhost:8010`
with no production branch, two declarations below an `API_BASE` that has one.
So a deployed page dialled whichever machine was viewing it. And the presence
service had zero Railway domains, so there was nothing to dial even with the
variable set. Tee generated `presence-production-d272.up.railway.app` and that
host is now the production fallback.

The Cartesia key was on the api service, where nothing reads it. Only
`apps/presence` does. It is now a Railway reference to the api service's copy,
so the value never passed through an agent session and there is one source of
truth. `SECRET_KEY` is referenced the same way, so a drift between the two
services cannot silently close every socket at 4401.

That the key and voice id carry real values is proven by a startup rather than
asserted: `apps/presence/settings.py:206` refuses to boot on an empty key and
`:212` on an empty voice id, and deployment `e34fc609` came up SUCCESS.

## The capture lane had no door either

`POST /api/v1/soul/propose` is the only caller of `knowledge_loop.propose` in
the estate, and the only human surface reaching it was the platform console,
which wants a CurrentUser JWT pasted into a field by hand. So DCD-07, wired in
PR #186 and written up as unproven, was unreachable rather than unexercised.

DEVON chat gains a fourth instrument, keep. It proposes and stops; approving
still needs `DEVON_RULING_KEY`, which no endpoint returns.

The enrichment summary, produced on every enriched capture and read by nothing,
now reaches `what_happens` on the approval card. Additive, labelled as the
model's, checked by the ledger's own `check_payload`. The title keeps Tee's own
words, because a paraphrase in the line he approves is the transformation the
first law refuses.

## Two surfaces were speaking as DEVON in a rented voice

Tee opened `/devon` and DEVON answered in a stock female browser voice.
`DevonChat.tsx` called `window.speechSynthesis`, preferred an en-GB voice named
daniel or arthur, and otherwise took any installed English voice. Three wrongs
and the gender was the smallest: the voice was rented rather than owned, the
preferred branch reached for a British male when DEVON is Southeastern US with
a drawl, and the fallback had no floor so he sounded like whoever's machine was
open.

The presence service gained `POST /tts`. The chat now streams the same clone
`/presence` uses, decoded by the same tested player.

A critic then found `deploy/soul/console.html` still running the identical
implementation, served in production by two hosts. Its `Voice` object now
refuses rather than degrades. The estate's rule carries no exception path for
channel identity and a served surface was breaking it.

## What the guards cost to get right

Three text-based versions of the capture reachability guard were beaten in one
evening, each shipping the lane dead with every gate green:

- presence assertions in a name-sliced region, beaten by an early return, a
  body replaced by one string, an earlier decoy, and a dead neighbour
- a uniqueness count on one declaration string, beaten by a neighbour under any
  other name
- a hand written string blanker, whose quote regexes mis-paired on apostrophes
  in JSX prose and erased the declaration the check existed to find

The guard now parses the file with the TypeScript compiler, which is already a
dependency because `tsc` runs in the same job. A token inside a string is a
StringLiteral node and can never be a CallExpression, which ends the class
rather than patching it.

## Four capabilities nothing can reach

An estate-wide sweep enumerated 127 routes under `/api/v1` two independent ways
and diffed them against every caller in the web app, both consoles and the
scripts. Ninety-one have no caller; most are legitimately spare. Four are not.

1. **The skill proposal gate has no door.** Every completed agent task
   auto-writes a human-gated proposal (`agent_tasks.py:513`,
   `DEVON_AUTO_SKILL_PROPOSE` defaults on at `:174`) and the trigger is
   reachable from `DevonChat.tsx:405`. The two routes that would let Tee see
   and decide them have no caller anywhere. CLAUDE.md says skill promotion is
   human gated; it is gated so that nobody can open it.
2. **The learning store is structurally always empty.** `agent_tasks.py:246`
   injects `devon_learning` into every planning context; its only write paths
   are routes nothing calls. Every plan DEVON makes is told he has memories and
   skills and handed two empty lists.
3. **Scheduled goals never run.** `materialize_due_schedules` has no call site
   and no cron, while `CapabilityDock.tsx:174` renders exactly the
   never-materialized rows under a hardcoded green Scheduler light.
4. **The workflow engine is stranded.** Ten routes, roughly 2,400 lines, two
   migrations, 969 lines of tests and a cron entrypoint in the image, with no
   way to create a workflow. The landing page advertises it.

Tee ruled the skill gate first, then the learning store.

## Stale records found in shipped UI

Three surfaces told Tee things that were not true, each written when it was
true and never rechecked.

- The control plane named the VPS as executor of record while the cutover doc
  said cutover not started. Cloud is executing: measured from a live webhook
  trigger reading `thequietoperator.app.n8n.cloud`, and an hourly Driver Poll
  at 23:00:00Z.
- The Tier 2 panel said no Cartesia endpoint had been reached, hours after Tee
  heard it.
- The Scheduler indicator is a hardcoded true, not a probe.

The n8n census also reconciled: 64 workflows on 2026-09-06 against 49 today is
a cleanup, not drift. The inactive population fell from 25 to 7 while active
rose from 39 to 42. This tool cannot list archived workflows, so whether the
fifteen were deleted or archived is unverified.

## Counted from the lane instead of the estate, three times

Five API paths that were eleven. A standalone total of 292 that the job gave as
261. A voice sweep over `apps/web` that missed a served console. Each was a
count taken from the thing being grepped rather than from the estate, which is
the miss CLAUDE.md's first law is written about. The 292 is now true because
`test_presence_service.py` was registered in the job rather than because the
number was edited down.

## Unverified

- Nobody has heard the chat speak in the clone. The presence page is proven;
  `/devon` is not.
- Nobody has filed a capture through keep, so DCD-07's live readback is still
  open.
- Whether the VPS is executing anything is unknown; both hosts are blocked from
  the agent container.
- Whether the fifteen missing workflows were deleted or archived.

## The fourth critic, and why a guard file needed four passes

Three critics ran on this arc. Each one closed its predecessor's bypasses and
each one found new ones, and the fourth found the pattern behind all of them.

**The guards proved presence and never proved reachability.** The capture guard
was rewritten to parse rather than grep, which genuinely closed all four
text-based bypasses; the fourth critic then got past the parser three ways
without touching a token it asserts on, each shipping the capture lane dead at
26 checks passed and `tsc` exit 0:

- the propose call wrapped in `if (!utterance)`, dead for every real input
  because `send()` already refuses empty text
- `.filter((option) => option !== "keep")` between the mode list literal and
  its `.map`, so the array still contained keep and the button was gone
- real dispatch moved to `switch (mode) { case "keep": ... }` with the
  `=== "keep"` the guard reads left behind in a `useCallback` nothing calls

The second and third are this arc's original defect restated exactly: a
capability that exists and that no person can reach. Proving a node exists in a
subtree proves nothing about whether control ever arrives there. Three helpers
close it: conditional ancestors between the call and the handler body must be
zero, the mode list must reach `.map` with nothing element-dropping applied to
it, and both `=== "keep"` and `case "keep":` are counted as dispatch sites with
the enclosing declaration required to be called.

**The largest finding was that the voice ban did not run.** `check:control`
holds it, `check:control` runs in exactly one workflow, and that workflow is
path filtered to `apps/web`, `packages/ui` and three root files.
`deploy/soul/console.html` matches none of them. So a pull request restoring the
rented voice in the served console and nowhere else kept both copies byte
identical, passed all 97 console tests, never triggered `web-ci` at all, and
would have landed with every job green. The finding the third critic raised was
reintroducible without CI noticing, because the guard lived on the wrong side of
a path filter.

Two fixes. The narrow one adds `deploy/soul/**` and `docs/devon/assets/**` to
that filter. The load bearing one is `test_devon_owned_voice.py`, in `ci.yml`,
which has no path filter at all: a compliance rule Tee stated with no exception
path is now checked on every push to every path rather than only when somebody
happens to touch the web workspace.

**A fixed list cannot guard the file that does not exist yet.** The ban was four
hardcoded paths. The critic added a fifth file carrying the exact implementation
this arc removed and the check reported ok. Both copies of the ban now glob and
assert a floor on what the glob found, the pattern `test_devon_integrity.py`
already used, because a glob matching nothing passes vacuously and reads
identically to one that matched everything. Measured from the estate: 55 web
sources, three served consoles.

**And the check one line below the rewritten one was still on the beaten
mechanism.** Check 26 sliced the file by `indexOf("const speak = useCallback(")`.
That is bypass shape 4 from the commit that fixed its neighbour. An unmounted
decoy component earlier in the file satisfied every assertion while the real
handler was a no-op, so DEVON was silent on `/devon` with the whole gate green.
Fixing one check and leaving its neighbour is how a guard file ends up with a
soft edge nobody remembers.

### Twelve controls, and the one that caught me

Every closure was proved by breaking it. Five bypasses reproduce red in
`check:control` with messages naming the actual defect, four reproduce red in
the Python twin including the console-only restore that was supposed to land
green, and two reproduce red on the presence health payload.

Three controls exist to prove the guards do not fail on correct code, and one of
them caught a defect I was about to ship. Hoisting the mode list to
`const MODES = [...]` and mapping that is an ordinary refactor, and the first
version of the render clause failed on it, printing that the list is not
rendered by a method call when it plainly was. That is the same class of error
the critic raised against three existing messages: a guard that fails for a
reason it cannot name. It now traces through the binding. Without the control it
would have shipped, and the next person to tidy that file would have lost an
hour to it.

`declarationsNamed` also accepts `function <name>()` now, because it read only
the const form, failed closed on a legitimate refactor, and then explained
itself as "declared 0 times; a second declaration means this check may be
reading the wrong one", which is a sentence about the opposite problem.

### Where this ban deliberately stops

The critic restored a fully working rented voice past every mark with
`window['speech' + 'Synthesis']` and it passed. That is true and it is not being
closed. The fix is either banning computed member access across the estate,
which breaks correct code, or an arms race against string concatenation, which
the next critic wins with a different split. Nobody writes that by accident;
this guard exists to stop a regression, a copy paste or a shortcut, and all
three name the API. Recorded and graded low rather than papered over.

### What the fourth pass confirmed rather than found

- 292 standalone tests is correct, and correct because the file was registered
  rather than because the number was edited down. The same list minus
  `test_presence_service.py` gives 261.
- The `ci.yml` list and the `CLAUDE.md` list are identical, file for file.
- Both console copies stay byte identical, and `test_deploy_soul.py` asserts
  exactly one non-superseded console exists, which closes "add a v11 with a
  voice".
- The console still works with `Voice` neutered: every call site resolves on
  the refusing stub.

### The fourth production surface

`deploy-readback` named three surfaces and there are four. The presence service
has been on its own Railway host since PR #188, `api-base.ts` hardcodes its
production URL, and DEVON's voice reaches Tee through it and through nothing
else. It was never written down, in the file whose whole job is knowing what
production serves, which is the count-from-the-lane miss again. It is recorded
now, including that this is the one surface that reads itself back: `GET /health`
returns the live provider, the speech lane, the deployed LiveKit state, the CORS
list and the breaker, so a claim about its wiring that was not read off `/health`
is unverified.

That health payload is also pinned to exactly nine keys, the way the soul host's
is, because it is unauthenticated: a field added there is published to anybody,
so it should be a decision rather than a debugging leftover.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_devon-audible-and-reachable_v1_2026-09-09.md
DATE: 2026-09-09
DECISIONS: Cartesia proven by ear on /presence; chat and console voices moved
off browser speech synthesis; capture lane given a reachable surface; capture
guard rewritten to parse rather than grep, then again to prove reachability
rather than presence; the owned voice ban given a Python twin in ci.yml so it
runs with no path filter; both copies of the ban globbed with a floor; the
obfuscation bypass graded low and left open on the record; deploy-readback
corrected from three production surfaces to four; skill proposal door ruled
first of four stranded subsystems, learning store second.
FINDINGS: Four capabilities nothing can reach, one of them breaking the stated
skill-promotion invariant; two served surfaces renting a voice; three stale
claims in shipped UI; four counts taken from a lane rather than the estate, the
fourth being deploy-readback's own surface count; the voice ban itself
unreachable in CI for a console-only change, so the previous critic's headline
finding was reintroducible with every job green; a guard proving presence where
only reachability matters, beaten three ways without touching a token it
asserts on; one false positive in my own fix, caught by its own control before
it shipped.
OPEN: chat voice unheard; DCD-07 live readback unfiled; VPS execution status
unknown; fate of fifteen workflows unverified; learning store, scheduler and
workflow engine still stranded; check:audio runs in no workflow; the console
mute button still toggles over a refusing Voice; the tier 2 sourceNote freezes
a point-in-time measurement with no detector; the full api suite unrun by the
fourth critic because the shared cluster forbids a concurrent run.
STATUS: presence audible and proven; capture lane reachable and unproven; the
guards behind both now proved by twelve controls rather than by assertion
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
