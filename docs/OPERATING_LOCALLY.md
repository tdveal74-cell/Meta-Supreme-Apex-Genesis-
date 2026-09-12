# Running DEVON and EditForge on one machine

For the days you are on your own. Nothing here needs an assistant, a browser
tab, or a network beyond your own box.

Two repositories, two processes, one connection between them:

| Piece | What it is | Where it listens |
|---|---|---|
| DEVON | the control plane. Decides, approves, orchestrates | `localhost:8000` |
| EditForge | the studio. Renders what DEVON approves | `localhost:3100` |

DEVON never renders. EditForge never decides. The token in the middle is the
whole relationship.

## Before you start

- **Node 20 or newer**, for EditForge.
- **Python 3.11 or newer**, for DEVON.
- **ffmpeg and ffprobe on PATH.** Without them the worker refuses renders and
  the studio reports itself not ready. On Ubuntu: `sudo apt install ffmpeg`.
  On macOS: `brew install ffmpeg`.
- **Docker**, only if you want the Compose path below. The no-Docker path does
  not need it.
- **Postgres**, for DEVON. `start-devon.sh` will start one in Docker if you
  have none, so this is only a real prerequisite when Docker is absent.

## 1. Start EditForge

From the EditForge repository. Pick one path; they are interchangeable from
DEVON's point of view because they share the same `.env` and the same token.

**With Docker**, the shape production runs:

```bash
./scripts/devon-local.sh
```

**Without Docker**, the same two services as plain Node processes:

```bash
./scripts/devon-local-nodocker.sh
```

Either way the first run generates three secrets into `.env` and prints them
back. Re-running rotates nothing, so you can run it as often as you like.

What you give up on the no-Docker path: container isolation, the pinned base
image, and the named volumes. It uses whatever ffmpeg is on PATH and keeps
state in `.local-run/`. Good for working; not the way to run something other
people depend on.

Stop them with `docker compose -f compose.local.yaml down` and
`./scripts/devon-local-nodocker.sh stop` respectively.

## 2. Check the studio honestly

```bash
curl -s http://localhost:3100/api/health
```

**Read `executionReady`, not `status`.** A studio whose worker is missing still
reports a `status`, and this route answers **HTTP 503** when anything is
degraded, so a bare `curl -f` will tell you nothing came back at all when
something plainly did. Read the body.

```json
{ "status": "healthy", "executionReady": true, "workerReachable": true }
```

`executionReady: false` almost always means ffmpeg is missing or the worker did
not start. Logs are `docker compose -f compose.local.yaml logs worker`, or
`.local-run/worker.log`.

## 3. Prove the token, which health does not

`/api/health` is deliberately open, so reaching it proves the studio is up and
nothing about your credential. The read that proves the credential is the same
lane every render command travels, and it spends nothing:

```bash
curl -s -H "Authorization: Bearer $EDITFORGE_MCP_TOKEN" \
  http://localhost:3100/api/edits
```

`{"executions":[]}` with HTTP 200 is a working credential. A 401 is the token,
not the studio. This distinction has bitten this estate before: a wrong token
used to report healthy and only surfaced later as a 401 on the first real
command.

## 4. Start DEVON

From the Meta-Supreme repository:

```bash
./start-devon.sh
```

It finds Python, installs into `.venv`, finds or starts Postgres, writes
`.env`, creates the tables, starts the API, and prints the console link and
token. Safe to re-run.

It writes the EditForge lane into `.env` already:

```dotenv
EDITFORGE_URL=http://localhost:3100
EDITFORGE_TOKEN=
```

**Paste the token** that EditForge printed into `EDITFORGE_TOKEN`. It is the
value EditForge calls `EDITFORGE_MCP_TOKEN`. Left empty, the lane fails closed:
DEVON refuses before making a request rather than calling out unauthenticated.

If you run DEVON itself inside Docker, use `http://host.docker.internal:3100`
instead of `localhost`.

## 5. Confirm the two are joined

Ask DEVON for EditForge status. It does the health check and the authenticated
read together, which is the pair that actually means something, and it uses the
credential DEVON holds rather than the one in your shell.

**The field to read is `live_verified`.** `configured: true` only says the two
settings are present. `live_verified: true` says the token was used against the
real lane and worked.

Three outcomes stay distinguishable on purpose, and each has a different fix:

| Response | What is wrong | Fix |
|---|---|---|
| `configured: false` | `EDITFORGE_TOKEN` is empty in DEVON's `.env` | paste the token from step 1 |
| `live_verified: false`, reason names a connection error | the studio is not running, or the URL is wrong | start it, or check the port |
| `live_verified: false`, reason says reachable but refused | studio is up, token is wrong | copy the token again, exactly |

## 6. What you can actually do locally

Runs on your machine with no provider credentials and no ability to spend:

`trim`, `reframe`, `derive-short`, `speed`, `captions`, `audio-mix`, `grade`,
and preview or master encoding. The FFmpeg worker compiles all of these itself.

**Refuses, loudly, by design:**

| Operation | Needs |
|---|---|
| `synthesize-voice`, `generate-full-motion`, `lip-sync` | the full `compose.yaml`, a consented identity registry, and a per-job ceiling |
| `split`, `reorder`, `title`, `transition`, episode and compilation assembly | `EDITFORGE_TIMELINE_ADAPTER_URL` |

An accepted operation with no compiler or adapter **fails**. It is never
silently skipped, so a missing capability shows up as an error rather than as a
render that quietly did less than you asked.

## 7. Working with your own footage

Point the studio at a directory of real media:

```dotenv
EDITFORGE_SOURCE_MEDIA_HOST_DIR=/root/Media Assets
```

It is mounted read only. `GET /api/sources` (authenticated) returns each
asset's name, size, modified time, SHA-256, and an `editforge-source:///...`
identifier. It never serves the bytes.

That SHA-256 is what an edit command binds to. A filename that looks like a
hash is not the content hash, so read it from `/api/sources` rather than
assuming. The `list_sources` MCP tool exposes the same catalogue, gated the
same way.

## 8. Pointing an MCP client at your local studio

`.mcp.json` in EditForge reads its address from the environment and falls back
to the hosted studio. Export both before starting the client:

```bash
export EDITFORGE_MCP_URL=http://localhost:3100/api/mcp
export EDITFORGE_MCP_TOKEN=<the same token again>
```

## 9. When something is wrong

| Symptom | Cause |
|---|---|
| Compose exits complaining a variable is unset | one of the three tokens is missing from `.env` |
| Health answers, `executionReady` false | ffmpeg missing, or the worker did not start |
| DEVON says URL and token are required | `EDITFORGE_TOKEN` is empty; the lane failed closed correctly |
| 401 on `/api/edits` | wrong token. The studio is fine |
| A command fails naming an adapter variable | that operation is not in the local stack. See section 6 |
| Image pull fails on the Compose path | your network cannot reach Docker Hub. Use the no-Docker runner |
| MCP still hitting the hosted studio | `EDITFORGE_MCP_URL` was not exported into the process that starts the client |

## 10. What is not local, and never will be

- **Production** is a separate stack: `compose.yaml` on the Hostinger VPS,
  answering at `editforge.online`. Nothing you do locally touches it.
- **The Vercel control plane** at `editforge.vercel.app` is a third thing
  again. As of 2026-08-30 that account is blocked, so it deploys nothing.
- **Paid provider work** cannot happen in the local lane at all. That is a
  property of the stack, not a setting.

## 11. One thing still unverified

`compose.local.yaml` has been validated by `docker compose config`, and CI
holds it to that on every push, but it has never been **built and booted**. The
no-Docker runner is what proved the application lane end to end; the container
packaging of it is still only config-checked, because the workspace that
verified everything else cannot pull the base image.

You can close that in one command on a machine with normal network access:

```bash
./scripts/devon-local.sh
```

Success looks like `executionReady: true` from
`http://localhost:3100/api/health` and HTTP 200 from the authenticated
`/api/edits` read. If you get both, the Compose path is proven and
`docs/devon/SYS_OPS_devon-editforge-local-operation_v1_2026-08-30.md` can drop
its remaining caveat.

If it fails at the image pull, that is your network and not the file, and the
no-Docker runner gets you working immediately.

## Deeper reference

- `EditForge/docs/LOCAL_OPERATION.md` for the studio side in detail.
- `EditForge/docs/DEVON_EXECUTION.md` for the command contract, the approval
  binding, and the full self-hosted stack.
- `OPERATING.md` in this repository for DEVON's own daily loop, cost, and the
  list of things it will never do on its own.
