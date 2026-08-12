# Deploying Meta Supreme Apex Genesis

This repo holds two deployable things with two different homes, and one that is
not deployable today. Each section says which, and says what was actually
verified rather than what is intended.

---

## `apps/web` — Vercel

The Next.js marketing/shell app. This is the only surface in the repo that
belongs on Vercel.

### Importing it

Vercel auto-detects Next.js and the pnpm workspace. Exactly one setting is not
auto-detectable and must be set by hand:

| Field | Value |
|---|---|
| **Root Directory** | `apps/web` |
| Framework Preset | Next.js *(auto-detected)* |
| Build Command | *(leave default)* |
| Install Command | *(leave default)* |
| Output Directory | *(leave default)* |

Leave **"Include files outside of the Root Directory"** enabled — it is on by
default and it is what lets the build reach `packages/ui`. `apps/web` depends on
`@meta-supreme/ui` as `workspace:*`, so an install scoped to `apps/web` alone
resolves nothing and the build fails at the first `import` of a token.

There is deliberately no `vercel.json`. Every field above except Root Directory
is what Vercel already picks; a config file restating them would be one more
thing to drift out of sync with the dashboard.

### Environment variables

None. `apps/web` reads no secrets and calls no API at build time — it is four
statically prerendered routes. `NEXT_PUBLIC_API_URL` appears in the local
compose file but nothing in `apps/web` reads it today.

### Verifying before you push

This is the sequence Vercel runs, and it is the one that catches the failure
that actually bites on a first import — a lockfile that has drifted from the
manifests:

```bash
pnpm install --frozen-lockfile
pnpm --filter @meta-supreme/web build
```

`--frozen-lockfile` is the point. Vercel installs with it in CI, so a lockfile
that no longer matches `package.json` fails the deploy while a plain
`pnpm install` locally would have quietly repaired it and told you nothing.

Verified from a cleared `node_modules` at the commit that added this file:
install resolved 109 packages against the committed lockfile with no
resolution step, and the build emitted `/` and `/_not-found` as static.

---

## `apps/api` — not a Vercel target

FastAPI + SQLAlchemy/asyncpg. It does not go on Vercel, and this is not a
configuration gap to be closed later:

- It opens a database session **during startup** (`lifespan` calls
  `seed_agents`), so it needs a reachable PostgreSQL before it can serve a
  single request.
- It is a long-lived stateful process with a connection pool. Vercel's
  functions are the wrong shape for it — each invocation would pay full
  startup, seeding included.

Deploy it as a container to somewhere that runs containers and has a managed
Postgres attached. `apps/api/requirements.txt` is the full dependency set;
`infrastructure/docker/Dockerfile.api` is the image definition.

---

## Local containers

`infrastructure/docker/docker-compose.yml` brings up `db`, `api` and `web`.

The `web` service could never have built. `infrastructure/docker/Dockerfile.web`
is written correctly for a pnpm workspace — it copies `package.json`,
`pnpm-workspace.yaml`, `apps/web/package.json` and `packages/`, installs with
`--filter @meta-supreme/web...`, then works from `/app/apps/web`. The compose
service was handing it the wrong context and the wrong mounts:

| | Was | Now |
|---|---|---|
| `context` | `../../apps/web` | `../..` |
| `dockerfile` | `../../infrastructure/docker/Dockerfile.web` | `infrastructure/docker/Dockerfile.web` |
| source mount | `../../apps/web:/app` | `../../apps/web:/app/apps/web` |

With `apps/web` as the context, the Dockerfile's very first `COPY package.json
pnpm-workspace.yaml ./` had no such files to copy. The `dockerfile:` path also
climbed out of its own context, which the builder rejects on sight. And the
mount buried the workspace root under `apps/web`, so even a successful build
would have lost `packages/ui` at runtime and `@meta-supreme/ui` would stop
resolving. The `api` service one block above already used the repo root as its
context; `web` now matches it.

**This fix has not been executed.** There is no Docker daemon in the environment
it was made in, so it was derived by reading the Dockerfile against the compose
file rather than by running a build. Confirm before relying on it:

```bash
cd infrastructure/docker && docker compose build web
```

The stray `Dockerfile.web` that used to sit at the repository root has been
deleted. Nothing referenced it, and it was a different and genuinely broken
file — it copied only the root manifest and lockfile, so `pnpm install` found a
root with no dependencies and installed nothing, then ran `pnpm dev` at `/app`
where the root `package.json` defines `dev:web` and no `dev`. Two files with the
same name, one working and one not, is how the wrong one gets picked.

To run the web app without containers at all:

```bash
pnpm install --frozen-lockfile
pnpm dev:web
```
