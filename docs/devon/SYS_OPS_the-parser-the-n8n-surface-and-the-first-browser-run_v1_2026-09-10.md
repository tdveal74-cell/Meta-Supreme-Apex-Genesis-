# The parser, the n8n surface, and the first time a panel was driven

Status record for the arc that follows PR #194 and PR #195. Supersedes nothing.
It closes three things the previous record left open by name: the n8n telemetry
surface, the intent parser enrichment, and "no panel driven from a browser".

## The three lanes

Each was built in its own worktree, handed to its own adversary, and integrated
here. Nine of the thirteen findings were fixed by the lanes themselves. Four
needed the parent, because they touched files a lane may not edit or because the
fix was a ruling rather than a patch.

### Lane 1: the intent parser, below its floor

DEVON's router knew 91 trigger phrases. It now knows 299, and a declined parse
no longer throws the work away: it can name the intent it nearly matched and put
that back to the person as a question.

The widening exposed a lane nothing defended. An ANCHORED prefix hit takes a
flat score of 0.95 and never consults the intent's own floor, which was
survivable at 91 triggers and was not at 299. Measured rather than argued: of
299 triggers followed by neutral prose, 197 routed, 49 of them to an EFFECT and
24 to an approval gated one. "message is on the list for tomorrow" reached
send_message.

The fix is a per intent declaration rather than a global constant. Every intent
already declares its own floor, so it declares its own `max_payload_words` too,
and an anchored EFFECT hit with more remaining words than its intent will carry
is refused. Three candidate rules were measured against two corpora before one
was chosen. The chosen rule takes prose leaks from 10 of 10 to 0 of 10 and
breaks 0 of 18 real commands.

Two negative controls, both red, both reverted byte identical. Neutering the
rule restored every leak; dropping the per intent bound in favour of a flat cap
broke real commands. `services/devon/commands.py` and its `deploy/soul` mirror
both hash `2bec21a1f58ad0e2`, and `assistant.py` and its mirror both hash
`a1f2d77fddc8fbbe`, so the phone lane and the API lane are the same parser.

Seven gated routes remain from the trigger sweep. They were checked against the
base parser at `5ff4348` and are PRE EXISTING, not caused by this change. One
candidate fix for them was measured and REFUSED: a two word minimum breaks
"message Karrie", which worked at baseline.

The suggestion path never offers an effect, at any score. That is not a filter,
it is the first rule of `may_be_suggested`, and it exists because the top
candidate for "fire up chrome" at `5ff4348` was "reboot the computer". A
suggestion also carries `understood` False and `executed` False, with no plan
and no approval card, so nothing but a person can act on one.

### Lane 2: the n8n telemetry surface, cycle three

`GET /api/v1/n8n/executions` is the first route in this repository that reads
the n8n instance. The Execution Hub panel drew a placeholder saying no such
route existed; that sentence is now false and the placeholder is gone.

Tee ruled on 2026-09-10: cut the projected exhaustion date, ship what ran and
what failed and how much of the cap is burned. The projection was the least
valuable figure on the tier and the most expensive one to be right about. No
date on this tier is projected forward. Every one is observed from an execution
row or stated by configuration.

The burn against a plan cap is still DERIVED, and the reader refuses to hand it
over bare: an execution id gap added to a figure a human read off the provider's
usage page, against a ceiling nothing here measured. `readCap` returns it only
with its basis beside it, and refuses it entirely when the ids of a window
contradict its clock.

The source guard over that reader has now been beaten three times, and the third
is the one worth recording. The law was stated by SHAPE and resolved through the
TypeScript checker, and an adversary walked a bare burn figure past all five
rules three separate ways with 61 checks green. R1 resolves a derived field to
the property SYMBOL declared on a payload type, which is precise and is blind to
a read off a receiver that lost that type. The bypasses were ordinary
TypeScript, not obfuscation, and the first is idiomatic React:

    function BurnBar({ data }: { data: { used_fraction: number | null } })

R6 is the answer: it ignores the receiver entirely and refuses the NAME, at all
three read sites, everywhere in the scanned set. It is deliberately coarser than
R1 and that was MEASURED before it was chosen. Across `app`, `components` and
`lib`, the four derived names occur outside the reader exactly once, in a
comment, so R6 has nothing to false positive on.

R6 was then proved rather than assumed. With its three branches removed, the law
misses exactly five probes, A, B, D, A2 and A3, and no others. Reverted byte
identical, confirmed by sha256 either side.

### Lane 3: the browser smoke run, and what it found

Every arc in this repository has carried the same caveat: no panel had ever been
driven from a browser. `next build` prerenders all six control plane routes and
`tsc` compiles them, so each renders its INITIAL state without throwing. No
`fetch` in any of them had ever executed. Every honesty check under
`apps/web/scripts` reads source text or an AST. So a wrong path, a malformed
Authorization header, a body parsed against the wrong key or a CORS refusal
would have passed every gate this estate has.

`.github/workflows/panel-smoke-ci.yml` is the eighth CI job. It stands
PostgreSQL, the FastAPI app and a built Next server up inside the job, registers
a throwaway account through the real registration path, seeds one row per panel
carrying a nonce minted in that process, and opens all six routes in real
Chromium.

It asserts two independent layers per panel, so a defect has to defeat both. The
NONCE cannot be in the bundle, in a fixture or in anybody's cache, so if it is on
the page the browser fetched it. And the SHIPPED LADDER'S OWN SENTENCE: the
harness runs the same payload through the same pure modules the panel runs it
through and asserts the rendered verdict verbatim, with the ladder's other rungs
asserted absent by name.

Run here on 2026-09-10 against a stack stood up in this container:
**129 checks passed in real Chromium over 6 routes in 5.9s.** That is the first
time any panel in this estate has been proved to read.

## The finding the smoke run made about itself

The first run of it was RED, and it blamed the wrong thing.

With the web server on port 3001 and everything else identical, every API side
check passed, the page loaded, no page error was thrown, and `/control/roster`
rendered "ROSTER UNREADABLE ... Failed to fetch". The panel was correct. The
harness was wrong: `app/core/config.py:CORS_ORIGINS` allows exactly
`http://localhost:3000` and `http://127.0.0.1:3000`, so a run pointed at any
other origin is refused at the browser, and that refusal reads everywhere it
surfaces as a broken read.

A red that names the wrong culprit is the failure this estate is organised
against, so the condition is now MEASURED before any panel is opened: a real
CORS preflight, from the real origin, against a route the panels really call.
The allowlist is not read from a file, because a file is a claim and the header
the browser will obey is the fact.

Proved both ways against one live stack: at origin 3000 the run passes its 129
checks; at origin 3001, serving perfectly well, it dies with 0 checks run and an
error naming the origin, the preflight status, the absent header and the file to
change.

## CI is EIGHT jobs

Five in `.github/workflows/ci.yml`, then `web-ci.yml`, then `audio-ci.yml`, and
now `panel-smoke-ci.yml`. The eighth is path filtered to the five panel
components and their pure modules, the six routes they are served on, the module
that resolves the API origin, the token slot they read, the six API modules they
call, the router that mounts those, and the check itself.

Its named residual, stated rather than left to be found: a panel read can also
break further inside the API, in a service, a model or a migration, and this
filter does not reach there. The api job in `ci.yml` runs the Python suite on
every push, so such a change is not unguarded; it is simply not guarded by this
job. Widening the filter to all of `app/` and `services/` would put a browser
download on most pull requests in the estate, which is how a smoke run gets
disabled.

Same posture as the audio job on the browser: Playwright installed globally in
the job rather than added as a devDependency, because a lockfile change would
put that cost inside web-ci's own path filter and make every web pull request
pay it. Both `loadPlaywright` and `findChromium` THROW, so a runner without
Chromium turns the job red rather than green.

`SMOKE_API_BASE` must never point at a deployed surface. The run registers an
account and writes a project, a memory, a decision and a workflow.

## What was measured before this was pushed

| gate | result |
|---|---|
| standalone, `PYTHONPATH` unset, 23 files counted from `ci.yml` | 655 passed |
| `import standalone_api`, same stripped environment | exit 0 |
| container contract import | exit 0 |
| engine | 25 passed, 2 deselected |
| full api suite | 2379 passed |
| `ruff check .` | All checks passed |
| `tsc --noEmit` | exit 0 |
| `next build` | exit 0 |
| control 39, honesty 4, learning 14, workflow 34, decisions 31 | all exit 0 |
| memory 36, projects 25, roster 34, presence 31, n8n 61 | all exit 0 |
| panel smoke, real Chromium | 129 checks passed |

One earlier full api run reported a single failure,
`test_presence_service.py::test_interrupt_for_another_turn_acks_without_cancelling`,
a websocket frame ordering assertion, while a `next build` was running
concurrently on this four CPU container. It passes 3 of 3 in isolation, 32 of 32
in its own file, and the clean run above is green over the same commit. It is
not in this diff and nothing in this diff touches presence.

`dependency-audit` was NOT reproduced here, and that is stated rather than
papered over. `requirements.txt`, `deploy/soul/requirements.txt` and
`pnpm-lock.yaml` are all unchanged by this arc, so its inputs are identical to
its last green run. The only change to `apps/web/package.json` is two script
entries. Reproducing the lane needs `pip-audit`, which the pinned closure does
not carry and which can perturb it.

## The read back, added 2026-09-10 after the merge

This section replaces an OWED claim that was already false when it was written.
The claim was that `devon-soul` was owed a build because `deploy/soul` changed.
It was not owed: the merge to `main` built it automatically, like the other
three. Read back from the platforms rather than reasoned, all four surfaces on
`d2b13f6`:

| surface | evidence |
|---|---|
| Railway `api` | deployment `90710b80` SUCCESS 09:54:17Z on `d2b13f6`; log carries alembic at head, `agent registry seeded`, `CORS allows 5 origin(s)` and `Application startup complete` |
| Railway `presence` | deployment `38f0feb0` SUCCESS 09:47:56Z on `d2b13f6` |
| Vercel `meta-supreme-apex-genesis-web` | `dpl_8eoYJeFcLF4PPhsWfjXqkizJkkm6` READY, target `production`, on `d2b13f6` |
| Vercel `devon-soul` | `dpl_4M3hHuxdamxX3EEKb4SR9sj9KWR8` READY, target `production`, on `d2b13f6` |

So the phone lane already carries the 299 trigger table, the per intent payload
bound and the suggestion path. Every `target` was checked rather than inferred
from `state`, which is the trap this estate has fallen into once.

**The one surface that reads itself back, read by Tee 2026-09-10.** This
container's egress proxy refused the CONNECT with a 403, so `GET /health` on the
presence host could not be read from here. Tee opened it on his phone and the
nine pinned keys came back:

```
status ok · service devon-presence · inference cerebras · fallback mock
speech cartesia · livekit_configured false · audio_over_websocket true
cors_origins [5] · breaker primary closed, 0 opens, 0 closes, 0 total_breaches
```

Three readings, and only the first is news.

**`speech` is `cartesia`, not `mock`.** The owned voice lane is live in
production. That is the compliance critical one, and it is now read off the
service rather than inferred from a deployment record.

**What it does NOT prove, stated so nobody reads it as more than it is.**
`/health` publishes the ADAPTER, never the voice id, which is deliberate. So
this says the Cartesia lane is wired; it does not say which voice is loaded, and
Tee's own rule is that nothing ships without a human listening end to end. The
listen is still owed. `last_ttft_ms` is null and `opens`, `closes` and
`total_breaches` are all zero, which says this deployment has served no speech
at all yet, so the breaker being closed is an untested closed rather than a
proven one.

**`livekit_configured` false is BY DESIGN and is not a finding.** Graded before
being raised: `apps/presence/main.py:87` returns `not livekit_configured` for
`audio_over_websocket`, so the socket carries PCM precisely when LiveKit is
absent, and `SYS_OPS_audible-presence_v1_2026-09-09.md` already records that the
browser path is the whole path and the LiveKit publisher is unbuilt and
unnecessary for it. `audio_over_websocket true` beside it is the two halves
agreeing.

**`cors_origins` carries the production web domain.** The five are the three
Vercel hosts including `meta-supreme-apex-genesis-web.vercel.app` plus the two
loopbacks, which is the same five the api service logged on its own startup. A
wrong list here is the failure that makes the chat's `POST /tts` fail silently
with a discarded 200, so it is worth having read rather than assumed.

## The prose leak dig, 2026-09-10, and why it stops here

Tee ruled keep digging for a clean rule. This is the dig, and it closes with a
negative result rather than a rule. Recorded so nobody re-derives it.

**The harness.** 299 triggers by 20 neutral tails is 5980 utterances, plus the
19 real commands from `test_devon_commands.py`. Twenty tails rather than four so
a candidate cannot be fitted to a handful. Current parser, measured:

| | count |
|---|---|
| reach an approval gated EFFECT | 140 |
| reach an ungated EFFECT | 420 |
| reach a READ | 4340 |
| real commands broken | 0 of 19 |

**Correction to what the arc reported.** The leak was written up as seven
routes. Seven is the count of GATED routes, and it is one intent rather than
seven: all seven triggers belong to `send_message`. Counting every EFFECT the
leak is 28 triggers across three intents, `send_message` (7, gated),
`search_web` (11, ungated) and `play_youtube` (10, ungated). The three that leak
are exactly the three payload taking effects that declare no
`max_payload_words`, which is the bound this arc added. `open_app` declares 2
and does not leak.

**The blast radius, graded before being raised, and the safety reading
withdrawn.** `services/devon` is effect free, which is a CLAUDE.md invariant and
holds here. `_do_search_web` and `_do_play_youtube` both return
`executed=False` with the reason "browser effects are proposed, never opened
unattended", and `send_message` stops at an approval card. So all 560 EFFECT
leaks produce a wrong sentence and zero actions. This is a conversational
quality defect, not a safety one, and a rule was being hunted for it as though
it were the latter.

**The whole score based class of fixes is dead, and now for every margin rather
than one.** The arc already recorded that making an anchored effect clear its
own floor breaks `search for the grid spec`. Sweeping the margin from 0.00 to
0.70 in eleven steps shows the curves cross and never separate:

| margin | gated leaks | effect leaks | real commands broken |
|---|---|---|---|
| 0.00 | 0 | 0 | 10 |
| 0.25 | 0 | 26 | 5 |
| 0.30 | 7 | 53 | 4 |
| 0.50 | 137 | 350 | 0 |
| 0.70 | 140 | 420 | 0 |

There is no value where both columns are zero. The score is not the
discriminator.

**A closed class opener rule gets 40 percent and is then defeated by the trigger
table itself.** Refusing a remainder that OPENS with a member of a genuinely
closed English class, the finite forms of be, have and do plus the modals, takes
the gated leaks from 140 to 84 and the effect leaks from 420 to 260, breaking 0
of 19 real commands. The class was chosen as a class rather than assembled from
the tails, precisely so the misses would be honest evidence.

The misses are two kinds, and the second is the one that settles it. First, open
class verbs and adverbs no list can enumerate without being fitted: sounds,
seems, means, matters, never, always, already, still, again. Second, and
structural: `'look that up'` and `'look that up for me'` are BOTH triggers of
`search_web`, so "look that up for me is on the list for tomorrow" anchors on
the shorter one and the remainder opens with "for" instead of "is". Any rule
about the remainder's first word is defeated wherever one trigger is a prefix of
another, which is a property of the trigger table rather than of English.

**The recommendation, and it is not to ship the 40 percent.** Forty percent of a
politeness problem is not worth another rule and another word list in the
parser's hot path, and a partial list invites the next session to add a few more
words, which is the fitted list trap this file already warns about. The
behaviour stays, the measurement is filed, and the dig is closed.

## Open

- Seven trigger sweep routes still reach a gate on prose. They are pre existing
  at `5ff4348`, the obvious fix was measured and refused because it breaks a
  real command, and they need a ruling rather than another guess.
- `control-check.ts`'s `BELOW_AA` matches only `text-` classes, so a `bg-white/N`
  used as a non text indicator passes it anywhere in the control tree. The
  obvious regex widening was measured and fires on four non offences. It needs
  the JSX to distinguish an indicator from a surface, which is a change to the
  panels rather than to the check. The computed contrast helper in
  `n8n-telemetry-check.ts` is reusable for the arithmetic half.
- No contrast has been measured on a real screen. The smoke run proves the reads
  happen; it does not look at them.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_the-parser-the-n8n-surface-and-the-first-browser-run_v1_2026-09-10.md
DATE: 2026-09-10
DECISIONS: Cut the n8n cap projection and ship the burn with its basis, on Tee's
ruling, because the projection was the least valuable figure on the tier and the
most expensive to be right about. Do the intent parser before the content
pipeline, on Tee's ruling, overruling the recommendation. Bound an anchored
effect's payload PER INTENT rather than by a global cap, because every intent
already declares its own floor and a flat cap across intents is the bug. Refuse
the two word minimum that would close the last seven gated routes, because it
breaks "message Karrie", which worked at baseline. Add R6 as a deliberately
coarse NAME backstop under the shape rules rather than trying to make R1
symbol resolution see through a lost type. Wire the smoke run as its own path
filtered job rather than a step in web-ci, the same ruling the audio job got, so
a browser download does not land on every web pull request. Measure the CORS
origin with a real preflight before opening any panel, so a harness fault cannot
be reported as a panel fault.
FINDINGS: Thirteen adversary findings across three lanes, nine fixed in lane and
four by the parent. The anchored prefix lane was undefended and widening the
trigger table from 91 to 299 walked 197 of 299 prose utterances into a route, 49
to an effect and 24 to an approval gate. The n8n source law was beaten a third
time, by three ordinary TypeScript reads that R1 is blind to because it resolves
by property symbol. A getattr walk could not read a verb it reached for and said
nothing. A stated used_fraction was trusted without being cross checked against
the figures it claims to summarise. And the smoke run's own first red blamed a
panel for a CORS refusal the harness had caused.
OPEN: Nobody has heard DEVON end to end yet. /health was read by Tee on
2026-09-10 and reports speech cartesia, so the owned voice lane is live, but it
publishes the adapter and never the voice id, and the breaker has served no
speech at all, so which voice is loaded and whether it sounds right are both
unverified and only Tee's ears settle them. The prose leak dig is CLOSED with a
negative result rather than a rule, and the recommendation is to leave the
behaviour; a ruling from Tee to ship the measured 40 percent anyway would
reopen it. Seven pre existing trigger sweep routes still gate on prose and
need a ruling, not a guess. control-check's BELOW_AA still cannot see a non text
indicator and the fix belongs in the panels. No contrast measured on a screen.
dependency-audit not reproduced here; its inputs are unchanged.
STATUS: pushed to claude/dreamy-wright-pv1f3l, draft PR opened, awaiting the head
run; eight jobs expected on this diff
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
