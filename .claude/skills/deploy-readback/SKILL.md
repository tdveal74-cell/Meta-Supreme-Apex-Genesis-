---
name: deploy-readback
description: Verify what this estate's five production surfaces are actually serving (Railway api, presence and scheduler-cron, and two Vercel projects), and diagnose Vercel deploy-quota exhaustion. Load before claiming anything is deployed or live, when asked whether production is current, when a Vercel deploy is blocked or skipped, when promoting a deployment to production, or when a status doc claims a deployment state. Compiled from the 2026-08-26 session where green previews were reported as production while all three surfaces sat stale.
---

# Deployment read-back

Merging is not deploying. A green check is not a live surface. This skill is
how to find out what production actually serves, and how not to repeat the
2026-08-26 failure where "Ready" statuses were reported as shipped while
production had not moved for hours.

## Rule zero: a claim of live is worth only the evidence attached to it

Never report a surface as deployed without a read-back that names the
deployment id, its state, and its commit. "The workflow passed" and "the PR
merged" are not deployment evidence. If the evidence cannot be produced, the
honest answer is "unverified", not an optimistic one.

## The five surfaces

This section said **three** until 2026-09-09 and **four** until 2026-09-16, and
each correction came the same way: somebody counted from the estate instead of
reading this list. The presence service was the fourth, found by a critic on
2026-09-09; it has been on its own Railway host since PR #188,
`apps/web/lib/api-base.ts:26-29` hardcodes its production URL as the fallback,
and DEVON's voice reaches Tee through it and through nothing else.

`scheduler-cron` is the fifth, found on 2026-09-16 by a session that called
`list-services` on the Railway project while reading production back. Railway
answers with four services, `api`, `presence`, `scheduler-cron` and `Postgres`,
and only two of them were named here. It deploys from the same commit as `api`
and it had been deploying the whole time, unwatched by this file.

**So count the surfaces from `list-services` and `list_projects`, never from
this table.** Twice now the table has been the thing that was wrong, in the file
whose whole job is knowing what production serves, which is exactly the
count-from-the-lane miss CLAUDE.md's first law describes.

| Surface | What it serves | How to read it |
|---|---|---|
| Railway `api` | The FastAPI app, the ledger, migrations | `list-deployments`, then `get-logs` on the deployment id |
| Railway `presence` | DEVON's voice and live inference, root `apps/presence`: `POST /tts`, the WebSocket lane, LiveKit tokens | `list-deployments`, then `GET /health` on the public host, which a container CAN reach since 2026-09-16 (see below) |
| Railway `scheduler-cron` | The scheduled lane, `python dispatch.py` on a `*/5 * * * *` cron | `list-deployments`; it carries no public host of its own to read back |
| Vercel `meta-supreme-apex-genesis-web` | The web app and Command Center, root `apps/web` (recorded as `meta-supreme-web` until 2026-09-02; that project no longer exists) | `list_deployments` for the project |
| Vercel `devon-soul` | The phone lane, root `deploy/soul` | `list_deployments` for the project |

**THE THREE RAILWAY SERVICES DO NOT DEPLOY ON THE SAME RULE, AND ONE OF THEM
STOPS WHEN CI IS RED.** Read from `get-service-config` on 2026-09-16, because
this file had said `scheduler-cron` deploys from the same commit as `api`, and
that is only true while CI is green.

| service | `source.checkSuites` | `build.watchPatterns` |
|---|---|---|
| `api` | **true** | none, so every commit to main |
| `scheduler-cron` | false | none, so every commit to main |
| `presence` | false | `apps/presence/**`, `services/**`, `requirements.txt` |

`checkSuites: true` means Railway holds the `api` deploy until GitHub's check
suites finish, and **SKIPS it outright when they fail**. Measured the same day,
twice, on the same pair of commits. Main went red on `71f96e2` and `api`'s
deploy sat WAITING from 08:30:08Z and then turned SKIPPED at 08:35:58Z, so that
commit never reached the API at all. The fix merged as `2ca6ec1`, `api` sat
WAITING from 08:39:07Z, CI run 827 passed at 08:45:08Z, and the deploy went
SUCCESS at 08:46:03Z, one minute later.

`scheduler-cron` has no such gate. On that same red commit it deployed anyway,
SUCCESS at 08:35:07Z, so for ten minutes the cron lane was running `71f96e2`
while the API was still serving `c0a2ea9`. **A red main splits the two apart
rather than freezing both**, and nothing announces it. So when CI on a merge
commit is red, do not report the estate as simply stale: say which service took
the commit and which one refused it.

`presence` is the only service with watch patterns, and `services/**` is in
them, so a change anywhere under `services/` deploys the voice lane. That is
wider than it looks: adding `services/devon/data_tables.py` triggered a
presence rebuild on 2026-09-16.

**The presence service reads itself back, which the other four cannot.**
`GET /health` is unauthenticated and returns the nine keys pinned by
`test_presence_service.py::test_health_says_only_these_things_and_no_more`:
`inference` and `fallback` name the live providers, `speech` says whether the
Cartesia clone or the mock is wired, `livekit_configured` is the deployed
variable set rather than the repo default, `cors_origins` is the list whose being
wrong makes the chat's `POST /tts` fail silently with a discarded 200, and
`breaker` carries the live circuit state. So for this one surface the honest
answer to "what is production serving" comes from the service itself rather than
from a deployment record, and a claim about its wiring that was not read off
`/health` is unverified. The key set is pinned deliberately: a field added there
is published to anybody, so it is a decision and not a debugging leftover.

**AND A CONTAINER CAN NOW READ IT. Tee opened it on 2026-09-16.** For most of
that day it could not: the network policy blocked `*.up.railway.app`, `curl`
got `CONNECT tunnel failed, response 403` from the agent proxy, and the one
surface that can prove its own wiring was the one surface no session could
prove. Tee added `*.up.railway.app` under Custom allowed domains in the Claude
Code environment settings, which is the same remedy the two n8n hosts needed
and for the same reason: a key alone was never enough.

Proven by the read itself, not by the setting being saved:

```
curl https://presence-production-d272.up.railway.app/health   200, nine keys
curl https://api-production-5644.up.railway.app/api/v1/health 200, healthy
```

The wildcard covers both hosts and any Railway service added later. **So read
`/health` rather than saying unverified.** The four fields nothing else could
reach came back `speech: cartesia`, `livekit_configured: false`,
`cors_origins` naming five origins, and `breaker` closed with zero breaches.
`livekit_configured: false` is the expected state, pinned by
`test_presence_service.py:106`, and `audio_over_websocket` is defined as `not
livekit_configured`, so the pair reading `false, true` is the design rather
than a gap.

A denial is still a denial: if this ever answers 403 again, say so with the
reason rather than retrying it, and check whether the environment changed.

**Count the Vercel projects before trusting any of this.** On 2026-08-27 a
diagnosis assumed two and there were four, all deploying from this one
repository: `meta-supreme-web` (since retired) and `devon-soul` above, plus
`meta-supreme-apex-genesis` and `meta-supreme-apex-genesis-web`, both imported
on 2026-08-26. The third had no `ignoreCommand` and rebuilt on every push to
every branch, which is what actually exhausted the cap; it was paused on Tee's
instruction. `list_projects` is the only honest answer to "how many are there",
and the Vercel commit statuses on a PR head name every project that ran, which
is how the extra two were found.

Identifiers live in the estate's own records rather than here, because a stale
id in a skill file is worse than no id. Read them from
`docs/devon/SYS_SPEC_devon-ecosystem_v1_2026-08-26.md` under "Deployment, read
back", or from the project list, and confirm they still resolve.

## The trap that caused the failure: `target`

A Vercel deployment carries a `target` field.

- `target: "production"` is production.
- `target: null` is a **preview**. It is not live on the production domain no
  matter how green it looks.

On 2026-08-26 every recent deployment on both projects read `READY`, and every
one of them was a preview. Production was several commits behind on both
surfaces, and the report said shipped. **Check `target` on every deployment
before drawing any conclusion from `state`.** A `READY` preview and a `READY`
production build are indistinguishable unless you look.

The same applies to the production domain. The build URL
(`*-tdveal74-5020s-projects.vercel.app`) is not the production domain, and
passkeys bind to the production hostname through `PASSKEY_RP_ID`. A sign-in
that works on one will fail on the other.

## Reading Railway

Railway does not show a commit in the deployment list the way Vercel does.
Confirm the migration actually ran by reading the deploy logs for the alembic
line, for example `Running upgrade 011_passkeys -> 012_live_state_ledger`.
That line is the proof the schema moved; a `SUCCESS` status alone is not.

Migrations run through Railway's `preDeployCommand` (`alembic upgrade head`),
configured in the Railway dashboard rather than in repo config. **This is
deliberate: never handle the production `DATABASE_URL` to run a migration by
hand.** The existing hook already has the credential and already runs at the
right moment.

Railway legitimately sits behind main when the intervening commits cannot
change the container (docs, `vercel.json`, CI workflow files). Say so with the
reason rather than treating it as drift.

## Redeploying Railway: do not use `redeploy`

The `redeploy` tool reuses the existing build, so it re-ships the **same, stale
commit**. To pick up a new commit, use the Railway agent to create a fresh
deployment from the current head.

## Vercel quota

**The account is on the Pro plan as of 2026-09-04**, read from `list_teams`,
which reports `"plan": "pro"` for `tdveal74-5020s-projects`. Everything below
about the free plan's 100 deployments a day is kept as history, because it is
what shaped these rules and it explains the `ignoreCommand` that is still in
both project roots. It no longer describes this account's limit. Read the plan
from `list_teams` rather than assuming either one, and read the actual number
from the dashboard Usage page, because there is still no quota endpoint in the
tooling.

The rules below survive the plan change on their own merit. A wrong skip ships
stale code silently whatever the plan is, and that is the failure worth
preventing, not the cost of a build.

**How the free plan cap got exhausted:** before 2026-08-26 both projects
rebuilt on every commit to every branch regardless of whether the change could
affect them. One docs-only commit produced four builds that could not have
differed from their predecessors. The cap was then reached while shipping
almost nothing, and it blocked the production deploys that mattered.

**The mitigation, already shipped:** each project root carries a `vercel.json`
with an `ignoreCommand`. Vercel runs it before building; **exit 0 skips, any
other exit builds**. Call it a mitigation rather than a fix: it reliably stops
the build, and whether it stops the deployment being counted is unproven. See
"What the ignoreCommand does and does not save" below.

```
if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ] || ! git cat-file -e "$VERCEL_GIT_PREVIOUS_SHA^{commit}" 2>/dev/null; then exit 1; fi
git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" HEAD -- <that project's paths>
```

**The comparison base is the load bearing part.** `VERCEL_GIT_PREVIOUS_SHA` is
the commit of the last successful deployment, which Vercel exposes only when an
ignore step is configured. The first version of these rules compared `HEAD^`
with `HEAD`, which asks "did this one commit touch my paths" when the question
that decides a build is "does what production is serving differ from main".
Those agree only while every build actually runs.

They came apart on 2026-08-26. The cap refused the build carrying
`apps/web/components/devon/DevonChat.tsx`, so it became owed; the next merge
touched nothing under `apps/web`, so the old rule skipped it, and would have
skipped every later commit that also missed those paths. The change sat
stranded in main, production served without it, no check failed, and the skip
was reported as success. `devon-soul` escaped only because the next merge
happened to touch `deploy/soul`, so it built and carried its own owed change
along; luck is not a mechanism.

**The rule fails open, deliberately, against this repository's usual
direction.** No previous SHA, or one this checkout does not contain, means
build. A needless build costs one deployment. A wrong skip ships stale code and
says nothing, and the silence is what makes that expensive.

`meta-supreme-apex-genesis-web` deliberately watches beyond its own root: it imports
`@meta-supreme/ui` from `packages/ui` in `tailwind.config.ts` and
`app/layout.tsx`, so a theme change touching no file under `apps/web` still has
to rebuild. Narrowing that rule would ship a stale brand and the skip would be
silent. `devon-soul` needs no widening because it vendors everything it uses.

**If you change either rule, prove it cannot silently skip a real change.** A
false skip ships stale code with no failure anywhere.

### What the ignoreCommand does and does not save

It saves the build: no build minutes, no build time, and no risk of shipping a
rebuilt artifact nobody asked for.

**It probably does not save the deployment count.** The cap's error code is
`api-deployments-free-per-day`, which counts deployments *created*, and an
ignored build is still a created deployment record. On 2026-08-26 four ignored
deployments were created between 11:49 and 12:07, and the next deployment at
12:15 was refused outright. That sequence is consistent with ignored
deployments counting.

This is read off behaviour rather than off Vercel's accounting, so treat it as
the working assumption and not a settled fact. The safe posture either way:
**do not describe the ignoreCommand as making commits free.** It makes them
cheap in build time. Whether it makes them free against the daily count is
unproven, and the optimistic reading is the one that burned this estate.

### A preview builds when the BRANCH has no previous deployment

The fail-open guard is not only a safety net for damaged history: it fires
whenever a branch ref has no deployment behind it. `VERCEL_GIT_PREVIOUS_SHA` is
then empty, the guard exits 1, and the build runs no matter what the commit
touched.

**The condition is the branch ref's deployment history, not the branch's
novelty, and in this repository those come apart.** The convention here is to
recycle the designated branch name after every merge, restarting it from
`origin/main` and force pushing. Vercel keeps that ref's deployment history
across the force push, so the second and later lives of a recycled branch have a
previous SHA from the outset and the guard never fires. PR #93 proved it: its
very first push recorded Ignored on all three active projects, on a branch name
that had already carried PR #92. Saying "a new branch always builds" would have
predicted a build there and been wrong.

**So do not predict either outcome on a pull request from path reasoning.** On
2026-08-27 a docs-only commit was pushed to a genuinely fresh branch with a PR
body claiming both Vercel projects would correctly skip. All three active
projects built previews. Nothing was broken; the prediction applied
production-branch reasoning to a first preview. The build log settles it in one
line, and is the only honest way to tell a fail-open build from a rule failure:

```
Running "if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ] || ! git cat-file -e ..."
Running "vercel build"
```

The rule ran and chose to build. Contrast a genuine skip, where the
`ignoreCommand` line is followed by the build being ignored rather than by
`vercel build`.

**From the second push onward the comparison base is the branch's own last
deployment, not production.** The same PR proved it: push two touched only the
skill file, and all three active projects recorded Ignored, because
`VERCEL_GIT_PREVIOUS_SHA` then pointed at push one on that branch. So a preview
skip means "nothing changed since I last built this branch", which is a
different question from the one a skip on `main` answers. Do not read a preview
skip as evidence about what production serves.

Practical consequences. A preview building on a docs-only PR is expected and is
not evidence the rule is broken. A branch's first ever push costs one build per
active project regardless of its paths, which is worth knowing when the daily
cap is near; a recycled branch does not, which is a quiet argument for the
recycling convention. And the skips worth auditing are the ones on **main**,
where the comparison base is production and a wrong skip ships stale code.

**Two projects can answer differently on the same push, and that is still the
guard rather than a broken rule.** On 2026-09-04, PR #133 pushed `d032283` to
`claude/github-repo-install-5wtko6`, a records-only commit touching neither
project's paths. `devon-soul` recorded Ignored. `meta-supreme-apex-genesis-web`
built a preview to READY.

What is proven, from the build log and from git:

- The web rule ran and chose to build. Its log reads `Running "if [ -z
  "$VERCEL_GIT_PREVIOUS_SHA" ...` and then `Running "vercel build"`, which is
  the fail-open signature, not a skip.
- It cannot have been a path match. `f476195..d032283` and `edaf03e..d032283`
  are both empty over `apps/web`, `packages/ui`, `pnpm-lock.yaml` and
  `pnpm-workspace.yaml`, so no plausible comparison base would have built.
- So the guard fired: either the previous SHA was empty or `git cat-file -e`
  could not find it in the checkout.
- The difference between the two projects lines up with how far back each one's
  last successful deployment sits. The web build restored cache from
  `XeMEfHQZju83jE28yW2aovwk9Voq`, the production deployment on `f476195`, many
  commits back, while `devon-soul` last built successfully at `edaf03e`, which
  is `d032283`'s immediate parent.

What is **not** proven: that the shallow clone is why `git cat-file -e` failed.
That is the obvious explanation and it fits every observation here, but the log
does not echo `VERCEL_GIT_PREVIOUS_SHA` and nothing in the tooling reports the
clone depth, so it stays a hypothesis. Settling it would mean changing the
`ignoreCommand` to echo the variable, which costs a build and has not been
done.

**The next push settled that it is not stable, and did not settle why.** Three
minutes later `ec8ccd1` went to the same branch, another records-only commit,
and **both** projects recorded Ignored, the web one included. So the same
branch produced a build and then a skip on consecutive pushes with nothing
relevant changing in the diff. The one thing that did change is that the web
project now had a successful deployment of its own on this ref, at `d032283`,
the immediate parent.

That is consistent with the empty-variable reading and with the unreachable-SHA
reading alike, so it is one more observation rather than a proof. It does kill
the inference a reader would otherwise draw from the paragraph above, that this
project simply builds and the other simply skips. Neither is a property of the
project.

The practical reading, which does not depend on the hypothesis: a project whose
last successful deployment is several commits back will tend to fail open and
build, and a project that built recently will skip, so the same branch can
answer differently from one push to the next. That is the guard working in the
safe direction. It costs a build; a wrong skip costs a silent stale production.
Do not read such a build as a broken rule, do not read two projects disagreeing
as one of them being wrong, and do not read one push's outcome as a prediction
of the next.

### Reading a skipped build correctly

An ignored build is recorded as **`CANCELED`**, and the Vercel bot comments
"Skipped Deployments / Ignored" with the deployment ids. That is the rule
working rather than a failure, so do not report it as a problem and do not try
to force the build.

A refusal looks completely different and names itself:

```
Deployment failed for project <name> with the following error:
Resource is limited - try again in 24 hours
(more than 100, code: "api-deployments-free-per-day").
```

Distinguish them by evidence, never by assumption:

| Appearance | Means |
|---|---|
| `CANCELED` plus an "Ignored" bot comment | The `ignoreCommand` skipped it. Correct. |
| A bot comment naming `api-deployments-free-per-day` | The cap. Nothing will deploy until the window rolls. |
| A commit status reading **"Account is blocked"** | An account-level block. See below. Not the cap, and not a build failure. |
| A build that ran and reached `READY` | There was headroom **at that moment**. See below. |

### An account block is a third thing, and it looks like neither

Seen four times: 2026-09-02 into 2026-09-03, again on 2026-09-04, again
on 2026-09-05 from some point between 18:55Z (the last record created on both
projects, commit 21caa65) and 19:23Z (the push of 88a002d, which created
none), and again on 2026-09-15 between 22:52:51Z and 23:35:20Z. The Vercel
commit statuses on the head read `failure` with the description
**"Account is blocked"**, pointing at
`https://vercel.com/knowledge/why-is-my-account-deployment-blocked`.

This paragraph said three until the fourth, and the fourth is the one that
kills the comfortable reading. It is the first block recorded since the account
moved to Pro on 2026-09-04, so a block is not the free plan and upgrading did
not stop it. Four occurrences in a fortnight is a recurrence rather than an
incident, and nothing in the tooling has ever named a reason for any of them.
Why it keeps happening is unanswered here, and it is worth Tee asking Vercel
rather than each session re-deriving the same diagnosis.

The 2026-09-15 gap is the cleanest recorded instance of the signature, because
five pushes landed inside it. Both projects created their last record at
22:52:51Z on `cb8de0e`. `b2d6f4a` at 23:35:20Z, `5906af9` at 23:48:53Z,
`70bbf04` at 23:55:51Z, `bada32e` at 23:58:59Z and `122f0e3` at 00:06:55Z each
created no deployment record on either project, while GitHub Actions ran and
went green on the same commits. Actions green and Vercel silent, at the same
time, on the same head, is what a block looks like.

**It cleared, and the clearing was read the same way.** The merge of PR #231
at 00:29:48Z created four records within a minute, two per project, on
`e71f215`. That is the verification this section prescribes: a record
appearing, not a status turning green. The block therefore ran roughly 97
minutes, from some point after 22:52:51Z to before 00:29:53Z. It is the only
one of the four whose duration this file can state, so treat it as one
measurement rather than a typical length.

Two things that window is worth remembering for. Nothing was stranded by it:
checked from each project's own `ignoreCommand` paths, no commit in the whole
40-record window touched `apps/web`, `packages/ui` or the lockfiles, so every
ignored production build in it was a correct skip. And `devon-soul` production
built to READY on the merge rather than skipping, because that merge carried
`deploy/soul/services/devon/vault.py`, which is the shape worth watching: a
block that had lasted into a `deploy/soul` change would have held a real
production update, silently, with only an absence to show for it.

It is not the daily cap. The cap names itself (`api-deployments-free-per-day`)
and it is a refusal of one deployment; a block is account wide and the tooling
never names a reason. It is not a build failure either, so re-running, pushing
an empty commit, or changing code does nothing. **Only a human on the Vercel
account can clear it.**

**Its signature is the absence of records.** While blocked, no deployment
record of any kind is created on any project, so `list_deployments` simply has
a gap. On 2026-09-02 that gap ran from 22:39Z to 13:16Z the next day on both
projects. That absence is the tell, because a blocked account and a quiet
account look identical in every status field.

**So that is also how you verify it cleared**, and it is stronger evidence than
any status turning green: push, then check that a deployment record was created
at all. `CANCELED` is enough. On 2026-09-04 the merge of PR #132 created
records on both projects at 19:24:57Z, which settled the block without needing
a successful build.

**Merging past a block is correct; shipping past one is not.** The `ci.yml`
workflow is the merge gate, and these statuses are third-party. But while a
block stands, nothing in the estate can deploy, so anything owed to a surface
stays owed and silent. Say so, and check what is owed rather than assuming.

### Verify a skip yourself rather than trusting it

`CANCELED` means the rule chose to skip. It does not prove the rule was right,
and a wrong skip is the expensive failure. Read each project's real
`ignoreCommand` out of its own `vercel.json` (not out of this file, which can
go stale) and run the same comparison by hand, from the commit of the last
deployment that actually built to `main`:

```
git diff --stat <last built commit> <main> -- <that project's paths>
```

Empty means nothing is owed and the skip was correct. Anything listed is owed
to production and nothing will tell you. Done on 2026-09-04 for both projects
against `edaf03e`: both empty, both surfaces correct at a commit behind main.

**A build succeeding does not mean the cap has reset.** The window is rolling,
so a slot ageing out lets one or two builds through while the account is still
over its daily count. On 2026-08-26 a promotion built successfully at 11:10 and
was read as proof the quota had reset; a deployment was refused at 12:15. One
success is a point, not a trend, and it says nothing about the next request.

There is no quota-remaining endpoint in the available tooling. Read behaviour,
say plainly that you are reading behaviour, and point at the dashboard Usage
page for the actual number rather than inferring one. If asked whether the
quota has reset, the only honest answers are a refusal seen (no) or a
dashboard reading (yes); a recent success is neither.

## Promotion costs a build

Promoting a preview to production in the Vercel dashboard **builds a new
deployment** using the production environment. The dialog says so. It does not
reuse the existing build and it is not free against the cap.

`npx vercel promote` from a session will fail with "No existing credentials
found" and is not worth pursuing; promote from the dashboard.

## Write it back

Both failures of 2026-08-26 were the same shape: a document asserting a state
that reality had since left behind, with nothing writing back. The deletion
protection line and the deployment line were each stale the moment they merged.

So when a read-back changes what is true, **amend the artifact that claims
otherwise in the same arc**, and say plainly whether the new line is something
this repository verified or something stated by a person. A reader who needs
certainty should be told where to go and check.

## Report format

State each surface separately, and never merge verified and unverified into one
optimistic sentence.

```
Railway api      LIVE   deployment <id> SUCCESS <time> on <commit>, migration <rev> applied
Railway presence LIVE   deployment <id> SUCCESS <time>; /health speech=cartesia livekit_configured=false breaker=closed
meta-supreme-apex-genesis-web LIVE   <dpl_id> READY target "production" on <commit>
devon-soul       STALE  production still on <commit>; current main is <commit>
```

External operating surfaces (Claude, ChatGPT, Codex, connected apps, scheduled
tasks) report `contract_ready` with `live_verified: false` until each returns
its own receipt. That is correct behaviour in the CapabilityDock, not a fault.
No invented green.
