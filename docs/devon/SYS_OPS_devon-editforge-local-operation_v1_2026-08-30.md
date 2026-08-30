---
title: DEVON EditForge Local Operation
type: SYS_OPS
version: 1
date: 2026-08-30
area: Creation
status: verified-booted
owner: DEVON
---

# DEVON EditForge Local Operation v1

## Ruling

DEVON can drive the media execution lane entirely on one machine. Running both
sides on localhost changes the address and nothing else: DEVON remains the only
executive control plane, EditForge remains the media execution engine, and the
approval binding to the exact intent hash is unchanged.

## What was actually blocking it

The capability was built. The wiring was not. Every default addressed the hosted
deployment, and nothing in either repository's setup path offered a local one.

| Default | Where | Effect |
|---|---|---|
| `EDITFORGE_URL = "https://editforge.vercel.app"` | `app/core/config.py` | local DEVON calls the hosted studio |
| No EditForge lane in the generated `.env` | `start-devon.sh` | fresh install has no token; the lane fails closed |
| MCP url pinned to `editforge.vercel.app/api/mcp` | `EditForge/.mcp.json` | the connector cannot address a local studio |
| `EDITFORGE_IDENTITY_REGISTRY_FILE` required | `EditForge/compose.yaml` | the stack refuses to start for picture work that never touches a provider |

## The local shape

EditForge's `compose.local.yaml` runs the control plane and the FFmpeg worker
only. It is `compose.yaml` without the identity-locked provider service and its
required registry secret, under its own Compose project name so the two stacks
never share a volume. `EditForge/scripts/devon-local.sh` brings it up and prints DEVON's two
lines. `EditForge/docs/LOCAL_OPERATION.md` is the runbook.

`start-devon.sh` now writes the lane into a fresh `.env`, and appends it to an
existing `.env` that predates it, without touching anything already there:

```dotenv
EDITFORGE_URL=http://localhost:3100
EDITFORGE_TOKEN=
```

`http://host.docker.internal:3100` where DEVON itself runs in Docker on the same
host. An empty token still fails closed. `EditForgeConfig.configured` is false,
and the client refuses before any request reaches the network.

## What the local lane cannot do

Clone voice, full motion, and lip sync are not in it. Their adapter URLs are
unset, so an accepted operation that asks for one fails; it is never silently
skipped. Nonlinear assembly is the same, pending
`EDITFORGE_TIMELINE_ADAPTER_URL`. Those need the full `compose.yaml`, a consented
identity registry, and a per-job ceiling. No paid render should be submitted
before Tee approves the exact identity, source assets, and ceiling. EditForge's
`docs/DEVON_EXECUTION.md` carries that path.

Picture and finishing work is unaffected: trim, reframe, derive-short, speed,
captions, audio-mix, grade, and preview/master encoding all compile in the worker
with no provider credentials at all.

## Verified evidence

Configuration:

- `compose.local.yaml` resolves under `docker compose config`, and CI holds it
  to the same contract check as `compose.yaml`.
- `start-devon.sh` and both EditForge runners pass `bash -n`.
- `.env` generation exercised on all three paths: fresh write, append to an
  existing `.env`, and a re-run that changes nothing.
- Token generation fills only blank values, so re-running rotates no credential
  DEVON is already holding.

Booted, 2026-08-30, in the configuration workspace:

- `/api/health` on `http://localhost:3100` returned `executionReady: true`,
  with `workerConfigured` and `workerReachable` both true.
- An authenticated read of `/api/edits` returned HTTP 200. No token returned
  401, and a wrong token returned 401, so the gate is load bearing rather than
  decorative. `/api/sources` is gated the same way.
- The worker reported `status: healthy` with `ffmpeg` and `ffprobe` both true.
- The runner stopped what it started, leaving nothing listening.

That boot used `scripts/devon-local-nodocker.sh`, which runs the same two
services as plain Node processes. `compose.local.yaml` itself was not built,
because the egress policy in that workspace refuses Docker Hub's blob CDN and
the base image cannot be pulled. So the application lane is proven end to end,
and the container packaging of it is still proven only by `docker compose
config`. A first Compose boot on a host with registry access closes that.

## Production, for contrast

The production studio is a separate stack: `compose.yaml` on a Hostinger VPS,
answering at `editforge.online`. Tee confirmed on 2026-08-30 that its health
check passes and that service, storage, worker and execution are reachable and
operational. That is a statement from the owner rather than something this
repository verified, and it says nothing about the local lane, which is a
different file on a different address.
