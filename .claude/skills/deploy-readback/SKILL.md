---
name: deploy-readback
description: Verify what this estate's three production surfaces are actually serving, and diagnose Vercel deploy-quota exhaustion. Load before claiming anything is deployed or live, when asked whether production is current, when a Vercel deploy is blocked or skipped, when promoting a deployment to production, or when a status doc claims a deployment state. Compiled from the 2026-08-26 session where green previews were reported as production while all three surfaces sat stale.
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

## The three surfaces

| Surface | What it serves | How to read it |
|---|---|---|
| Railway `api` | The FastAPI app, the ledger, migrations | `list-deployments`, then `get-logs` on the deployment id |
| Vercel `meta-supreme-web` | The web app and Command Center, root `apps/web` | `list_deployments` for the project |
| Vercel `devon-soul` | The phone lane, root `deploy/soul` | `list_deployments` for the project |

**Count the Vercel projects before trusting any of this.** On 2026-08-27 a
diagnosis assumed two and there were four, all deploying from this one
repository: `meta-supreme-web` and `devon-soul` above, plus
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

The free plan allows 100 deployments a day, counted across the account.

**How it gets exhausted:** before 2026-08-26 both projects rebuilt on every
commit to every branch regardless of whether the change could affect them. One
docs-only commit produced four builds that could not have differed from their
predecessors. The cap was then reached while shipping almost nothing, and it
blocked the production deploys that mattered.

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

`meta-supreme-web` deliberately watches beyond its own root: it imports
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

### The first preview on a new branch always builds

The fail-open guard is not only a safety net for damaged history: it fires
routinely, on every branch's first push. A new branch has no previous
successful deployment, so `VERCEL_GIT_PREVIOUS_SHA` is empty, the guard exits
1, and the build runs no matter what the commit touched.

**So do not predict a skip on a pull request from path reasoning.** On
2026-08-27 a docs-only commit was pushed to a fresh branch with a PR body
claiming both Vercel projects would correctly skip. All three active projects
built previews. Nothing was broken; the prediction applied production-branch
reasoning to a first preview. The build log settles it in one line, and is the
only honest way to tell a fail-open build from a rule failure:

```
Running "if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ] || ! git cat-file -e ..."
Running "vercel build"
```

The rule ran and chose to build. Contrast a genuine skip, where the
`ignoreCommand` line is followed by the build being ignored rather than by
`vercel build`.

Practical consequences. A preview building on a docs-only PR is expected and
is not evidence the rule is broken. Every PR branch therefore costs at least
one build per active project regardless of its paths, which is worth knowing
when the daily cap is near. And the skips worth checking are the ones on
**main**, where a previous SHA exists and the comparison is real.

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
| A build that ran and reached `READY` | There was headroom **at that moment**. See below. |

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
meta-supreme-web LIVE   <dpl_id> READY target "production" on <commit>
devon-soul       STALE  production still on <commit>; current main is <commit>
```

External operating surfaces (Claude, ChatGPT, Codex, connected apps, scheduled
tasks) report `contract_ready` with `live_verified: false` until each returns
its own receipt. That is correct behaviour in the CapabilityDock, not a fault.
No invented green.
