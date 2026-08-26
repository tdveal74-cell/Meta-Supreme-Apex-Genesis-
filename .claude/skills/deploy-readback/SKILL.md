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

**The fix, already shipped:** each project root carries a `vercel.json` with an
`ignoreCommand`. Vercel runs it before building; **exit 0 skips, any other exit
builds**.

```
apps/web      git diff --quiet HEAD^ HEAD -- ':/apps/web' ':/packages/ui' ':/pnpm-lock.yaml' ':/pnpm-workspace.yaml'
deploy/soul   git diff --quiet HEAD^ HEAD -- ':/deploy/soul'
```

`meta-supreme-web` deliberately watches beyond its own root: it imports
`@meta-supreme/ui` from `packages/ui` in `tailwind.config.ts` and
`app/layout.tsx`, so a theme change touching no file under `apps/web` still has
to rebuild. Narrowing that rule would ship a stale brand and the skip would be
silent. `devon-soul` needs no widening because it vendors everything it uses.

**If you change either rule, prove it cannot silently skip a real change.** A
false skip ships stale code with no failure anywhere.

### Reading a skipped build correctly

An ignored build is recorded as **`CANCELED`**, and the Vercel bot comments
"Skipped Deployments / Ignored" with the deployment ids. That is the rule
working, not a failure and not the cap. Do not report it as a problem and do
not try to force the build.

Distinguish the three by evidence, never by assumption:

| Appearance | Means |
|---|---|
| `CANCELED` plus an "Ignored" bot comment | The `ignoreCommand` skipped it. Correct. |
| No deployment created at all for a qualifying commit | Possible cap. Check whether any build has succeeded recently. |
| A build that ran and reached `READY` | Capacity exists. The cap is not currently biting. |

There is no quota-remaining endpoint in the available tooling. Read behaviour,
say you are reading behaviour, and point at the dashboard Usage page for the
actual number rather than inventing one.

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
