# The Soul tile reads Railway, not devon-soul

Status doc, 2026-09-15. Closes the diagnostic that arrived as a handover
titled "MESH READOUT DIAGNOSTIC". Extends
`SYS_OPS_six-doors-closed-and-a-scheduler-that-runs_v1_2026-09-10.md`, which
gave the Scheduler tile in `CapabilityDock.tsx` an honest three way read; this
arc gives the Soul tile the same and records why the handover went to the wrong
surface.

## What the handover said, and what was measured

The handover said the DEVON capability mesh reads 6/7 with the Soul tile grey
and "recall off", that the mesh polls the `devon-soul` Vercel project through
`/api/v1/soul`, and that `devon-soul` needs `SOUL_RECALL_ENABLED=true`,
`PINECONE_API_KEY` and `SOUL_DEVON_HOST` before it will answer active.

Three of those four sentences are wrong, and each was a cheap check.

| claim | check | what was true |
|---|---|---|
| the mesh polls `devon-soul` | `apps/web/lib/api-base.ts:7` and `CapabilityDock.tsx:143` | a production build sends every dock fetch to `https://api-production-5644.up.railway.app/api/v1`, the platform API on Railway, unless `NEXT_PUBLIC_API_URL` overrides it |
| the readout could still be `devon-soul` | `CapabilityDock.tsx:200`, `activeCount` returns 0 when `/agent-tasks/tools` fails, and `deploy/soul/main.py` serves no such route | a 6/7 readout is only reachable through the platform API |
| which service answered the phone | Railway http log, deployment `84ad6a1c`, api service | `GET /api/v1/soul/status` 200 from an iPhone at 04:48:52Z and 04:54:06Z, in the same burst as `/agent-tasks/tools`, `/agent-expansion/schedules` and `/devon/operating-layer/status`, which are the four fetches in `CapabilityDock.refresh()` |
| `devon-soul` needs `SOUL_RECALL_ENABLED` | `grep -rn SOUL_RECALL_ENABLED deploy/soul` | no hit in that service's own code. `deploy/soul/main.py:494-506` keys `/api/v1/soul/status` on `PINECONE_API_KEY` alone; the only match under `deploy/soul` is a docstring in the vendored `assistant.py` |
| `devon-soul` is missing its key | `https://devon-soul.vercel.app/api/v1/health`, read through the Vercel fetch tool | `{"status":"healthy","console_token_set":true,"soul_key_set":true}`. That service has its key and was never the one asked |
| what turns the platform tile on | `app/api/v1/soul.py:77` | `enabled = settings.SOUL_RECALL_ENABLED and bool(settings.PINECONE_API_KEY)`, both defaulting off in `app/core/config.py:152-153` |
| what the Railway api service carries | `list-variables` on project `devon-api`, service `api`, environment `production` | 41 variable names. None of `SOUL_RECALL_ENABLED`, `PINECONE_API_KEY`, `SOUL_DEVON_HOST`, `SOUL_TEE_HOST` |

So the tile is grey because the service it reads has no soul variables at all.
Nothing that reaches the Railway build can light it: `infrastructure/docker/Dockerfile.api`
copies no `.env` and carries no `ENV` line for either variable, and the only
place in the tree that writes `SOUL_RECALL_ENABLED=true` is `start-devon.sh:143-156`,
into a gitignored local `.env` the image never sees.

## The one thing that lights it, and who does it

On Railway, project `devon-api` (`3bf31602-1e72-4fac-ade7-4c89106d8896`),
service `api` (`c8e24427-74bd-4b71-85c8-d9b9bd496cf4`), environment
`production`, set two variables:

```
SOUL_RECALL_ENABLED=true
PINECONE_API_KEY=<the soul layer's key, from the Pinecone console, never from Drive>
```

`SOUL_DEVON_HOST` needs no setting on the platform. `app/core/config.py:159`
already defaults it to `https://devon-soul-jw37oa2.svc.aped-4627-b74a.pinecone.io`,
which is the host the handover quoted in the session,
`devon-soul-jw37oa2.svc.aped-4627-b74a.pinecone.io`, with the scheme the quoted
copy lacks. The handover itself is not in this repository; its text is what
arrived in the session. That "needs no setting" is true of the platform only:
the phone lane reads the same variable with no default (`deploy/soul/main.py:186`),
so on `devon-soul` it decides whether DEVON's own soul is searched at all, and
the dock never asks that service. If it is set anyway it has to carry `https://`: `services/intelligence/soul.py:281`
builds the search URL by string concatenation, and a scheme-less host reaches
httpx as an unsupported protocol, which `_request` reports as
`ProviderServerError("Network error calling Pinecone: ...")` inside the
recall's `errors` list, with no crash.

The restart is what lights the tile, not the variable write:
`app/core/config.py:304-309` builds `settings` once per process and
`app/services/soul.py:18` caches `get_soul_layer()` for its life. Railway
restarting a service when a variable changes is platform behaviour this
repository cannot verify; confirm it from the deployment list after the fact.

The key is Tee's secret and no file in the tree holds it. A session with the
Railway connector could write the flag, and writing a production variable is
his call and never a session's, so neither is done here. The network policy
blocks `railway.app` from this container, so the read back below is his too.

## How to know it worked

1. The dock. Open the Command Center on the phone, sign in through Talk to
   DEVON once, open the mesh. The headline reads `MESH 7/7`, the Soul tile
   reads "recall on", and the Soul recall note under the grid reads "Soul
   recall is on. Configured rather than probed: the status route never calls
   Pinecone, so only a recall proves the connection." That last sentence is
   true and it is the reason step 3 exists.
2. The route. With the Bearer token the dock uses (`devon-chat-token` in the
   browser's localStorage):
   `curl -H "Authorization: Bearer <token>" https://api-production-5644.up.railway.app/api/v1/soul/status`
   answers `"enabled": true`.
3. The connection. Same token:
   `curl -H "Authorization: Bearer <token>" "https://api-production-5644.up.railway.app/api/v1/soul/recall?q=owned%20voice"`
   answers with `records` from `tee-soul-layer` first, `tee_count` above zero,
   and an empty `errors` list. A non-empty `errors` list names which soul did
   not answer and why, and that is the vector connection failing, not the flag.
4. The deploy log. Railway shows a new container start after the variable
   change. Without it, step 2 still answers `false` from the cached layer.

## What the code did wrong

The dock threw away everything the status route told it. `soul === null`,
which is what a 401 on a stale token or an unreachable API produces, rendered
as "recall off", the same words the route uses when it answers
`enabled: false`. The route's `detail`, which names the two variables, was
never shown. And nothing on the panel said which host it reads. That is the
Scheduler defect of 2026-09-10 in a new tile, and it is the whole reason a
diagnostic spent itself on the wrong Vercel project.

`CapabilityDock.tsx` now derives every Soul statement from one value,
`soulState`, which is `"unread"` when the status object is null and otherwise
`"on"` or `"off"` by `enabled`. The light is `soulState === "on"`, the tile
detail is a three entry map keyed on it, the panel header is the same word
upper cased, and the note branches on it. The status object is read in exactly
two places, `enabled` in that expression and `detail` in the note, and the
note carries the route's own `detail` followed by the host whose environment
the variables belong to, derived from `API_BASE`. The on branch says
configured rather than probed, because `app/api/v1/soul.py:76` reads "without
touching Pinecone" and means it. A checking arm covers the first in flight
read, and the off fallback names the two variables itself so the sentence
always has an antecedent.

The first version of this change pinned one ternary and was beaten; the
critic section below has the count. What holds it now:

`apps/web/scripts/honesty-check.ts` section 1b, six checks that pin the
`soulState` expression exactly, the three tile words as data, that the object
is bound once and read in those two places only, that `setSoul` stores null
or the awaited `soulResult.value.json()` and nothing else and only under the
ok test, that `apiHost` is `new URL(API_BASE).host` with no literal anywhere
in it, and that the note reads `detail`, names `apiHost` in its off branch,
and renders under a plain className inside the Soul recall panel. Seventeen
mutations, the critic's twelve adapted to the new shape plus five more, each
went red with the assertion named for it, and the file was restored byte
identical after each.

`apps/web/scripts/dock-smoke.mjs`, the check that cannot be edited around.
It stands beside `panel-smoke.mjs` in `panel-smoke-ci.yml`, opens
`/command-center` in real Chromium with a real token and then with one the
API refuses, and asserts the rendered words against words pinned in the
script: "recall off", the route's detail word for word, and the API host in
the first; "status unread", `MESH 0/7` and the failed read footer in the
second. Run here against a local stack built the way that job builds it: 21
checks passed, and `panel-smoke.mjs` passed its 129 on the same stack. The
first attempt died at registration with `relation "users" does not exist`,
because the local `meta_supreme` database had never been stamped and
`alembic heads` had been read as `alembic current`; `alembic upgrade head`
ran 18 upgrades and the second attempt passed. The job runs that step before
starting the API, which is why it is there.

Measured on `27abd48`, the first rework: `check:honesty` 10 checks; typecheck and the
production build exit 0; the other nine `check:*` scripts exit 0;
`test_devon_integrity.py` 262 passed; no dash and no banned word in any
changed file.

## The dash that had main red

Main's api job has been red since run #735, the PR #216 merge `400fded` at
2026-09-14T22:33:08Z, `1 failed, 2509 passed` on every run through #744 and
on one line: `VpsActionGate.tsx:272` carried an en dash between 3 and 500 in
the Reason label, which `test_devon_integrity.py::test_no_em_dashes_in_the_web_surface`
refuses. This paragraph said #739 until the readiness audit listed the runs
from the Actions API; the last green run on `main` is #733 on `95fbdd5`, the
commit the Railway api serves. The file's own error string at line 121 already says "3 to 500
characters", so the label now says the same, in its own commit, separate from
the Soul change. It is on this branch because the branch cannot go green
without it and the rule it restores has no exception path.

## What the critic found

The arc ran three refuters and a mutating critic in an isolated worktree on
the first commit, plus a cold prose reader, through a workflow. Every refuter
returned refuted false at high confidence with executed checks; their
corrections are folded into the sections above (the Railway build wording,
the restart, the phone lane's `SOUL_DEVON_HOST`, and two stale sentences in
`DEPLOY.md`, corrected in their own commit).

The critic returned QUARANTINE, head `fc24a8c` echoed, tree clean at exit.
Eleven of its twelve mutations made the panel lie while `check:honesty`
stayed green: the on and off arms swapped, the failure branch of the status
read storing `{ enabled: false }` so a 401 rendered as "recall off",
`API_BASE` in a dead branch of `apiHost`, the detail read and overwritten,
the header keyed on the object, the light keyed on `tee_host_configured`, the
note rendered under `hidden`, the off branch naming the devon-soul project.
The one it caught was a pure rename, with a message that misdescribed why.
Its verdict was right: the first commit's message had claimed the guard held
by shape, and it held for one ternary. That claim is withdrawn and the rework
above is the answer to it. Two nits stand corrected here as well: the status
route in `deploy/soul/main.py` starts at line 490, not 494, and a wrong or
revoked key lights the tile until a recall fails, which the note now says.

The prose reader found no dash and no banned word and flagged two sentences as
stronger than their backing: that only Tee can set the variables, and that the
config default is "the exact host the handover names". Both are reworded
above.

## What could not be measured here

- Direct reads of `api-production-5644.up.railway.app` and `devon-soul.vercel.app`
  from this container: the egress proxy refuses both hosts under the
  organization policy. The Railway log and the Vercel fetch tool stood in.
- The `devon-soul` project's variable names: the Vercel project tool returns
  no environment block. Its own `/api/v1/health` was read instead, which is
  the honest answer for that surface and says the key is set.
- The compiled `API_BASE` inside the deployed web bundle. The Railway http log
  shows the phone's dock hitting Railway, which is the traffic itself and
  stronger than the bundle, so the bundle was not chased.
- Anything after Tee sets the variables. Steps 1 to 4 above are his.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-soul-tile-reads-railway_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: none ruled. The recommendation put to Tee is to set SOUL_RECALL_ENABLED=true and PINECONE_API_KEY on the Railway api service and nothing on devon-soul, and to leave SOUL_DEVON_HOST unset because the config default already carries the right host with its scheme. Two calls were mine: the dock change was made, with no proposal step, because it is the same honesty fix the Scheduler tile got on 2026-09-10 and it is guarded the same way; and the en dash on main was fixed in its own commit instead of being reported, because the branch cannot go green without it and the rule has no exception path. Both are one revert if Tee disagrees.
FINDINGS: the DEVON capability mesh reads the Railway platform API at api-production-5644.up.railway.app for all four of its fetches, api-base.ts:7 and CapabilityDock.tsx:141-146, confirmed by the Railway http log on deployment 84ad6a1c showing an iPhone hitting /api/v1/soul/status in the same burst as the other three; the devon-soul Vercel project is never asked by the dock, never reads SOUL_RECALL_ENABLED, and already has its key, its /api/v1/health answering soul_key_set true; the Railway api service carries none of the four SOUL variables, so app/api/v1/soul.py:77 computes enabled false from the config defaults and the tile is grey on configuration alone; SOUL_DEVON_HOST defaults at config.py:159 to the exact host the handover names, with the scheme, so it needs no setting; the dock rendered a failed status read as "recall off", discarded the route's detail naming the variables, and named no host, which is why the handover went to the wrong surface; main's api job was red on exactly one test, the en dash at VpsActionGate.tsx:272, 1 failed 2509 passed on run #744; the first Soul guard was beaten eleven times by one critic and its rework nine times by a second, and what holds now is thirteen shape checks plus a browser smoke that captures the request, reads the pixels and drives the on state, 35 checks over three contexts with 29 mutations red; DEPLOY.md said there was no vercel.json and that nothing read NEXT_PUBLIC_API_URL, both false against the tree, corrected in their own commit.
OPEN: Tee sets the two variables on Railway api and runs the four read back steps; the recall probe in step 3 is the only proof of the Pinecone connection, because the status route never calls Pinecone by design; the dock's "recall on" therefore means configured, and a revoked key would still read green until a recall fails, which is a deliberate trade against polling Pinecone every 45 seconds and is stated on the panel; the handover's origin, a Gemini iOS webview also seen in the Railway log at 04:54:06Z, carried three wrong claims that a file read would have caught, and whatever produced it should be pointed at this doc before it is asked again; the dock smoke drives the on state through a route mock because the stack the job stands up carries no soul variables, so a real on read against a configured API is still Tee's step 1.
STATUS: filed with five code commits and this doc on the designated branch, draft PR, nothing merged and nothing set on any live surface. The Soul tile stays grey until Tee sets the variables. Every claim above was measured today against the live estate or read off a named file and line, and the four things that could not be measured are listed, with no rounding up.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
