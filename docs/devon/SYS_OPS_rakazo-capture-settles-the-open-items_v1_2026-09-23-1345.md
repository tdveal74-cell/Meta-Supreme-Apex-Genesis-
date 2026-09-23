# The Rakazo capture ran, and settles what the morning record left open

Written 2026-09-23. This corrects
`SYS_OPS_the-editforge-host-runs-rakazo-and-more_v1_2026-09-23-0501.md`, which
listed the capture as not yet run and two facts as UNVERIFIED.

## How it was read

Tee ran `capture.sh` and a shorter follow-up read in the hPanel terminal on
`srv1936199` and sent two screenshots. The image digests in them were then
checked against the public registries rather than trusted as transcribed:
the Rakazo app and computer images on ghcr.io, and Ollama, Postgres and
busybox on Docker Hub or its `mirror.gcr.io` mirror. All five exist. A digest
altered by one character returned 404 from the mirror, so the check can fail.

## What changed from the morning record

The compose file in use is settled. Rakazo runs as compose project `rakazo`
from `/home/tee/rakazo`, on `docker-compose.images.yml` with sha256
`6872d812072d3ff517cc3fb55ce33aaf6cd32f773fbe252811b438bffb7693d7`. That hash
matches upstream `infra/compose/docker-compose.images.yml` at `elie222/rakazo`
commit `1a1f7b8` (2026-09-07), still unchanged at `2256bfa`. Nothing on the
host edits Rakazo's compose file.

Postgres is pinned. The morning record read plain `postgres:16` from
`docker ps` and flagged a mismatch with upstream. The container's configured
image is `postgres:16@sha256:e17e8606...`, the exact digest upstream pins.
`docker ps` had shortened the reference.

`rakazo-bot-team-792164ec...` runs the same computer image digest as
`rakazo-computer-1`. Upstream's supervisor creates desktop containers at
runtime named `rakazo-bot-<bot id>` (`infra/sandboxes/supervisor/src/computer-spec.ts`
line 301) from `RAKAZO_COMPUTER_IMAGE` (`index.ts`), so the morning's
UNVERIFIED on it is closed.

The moving-tag risk was stated too broadly. Upstream's compose file sets no
`pull_policy`, and no updater container runs on the host, so the images change
only on a deliberate pull or after a prune. The morning record's wording, "the
next pull installs whatever upstream pushed that day", is accurate. It is not
an automatic update.

## What was committed

`tdveal74-cell/rakazo-deploy` commit `21874d8`: `.env.example` with the 36 key
names from `/home/tee/rakazo/.env` and no values, `images.lock` with every
container's digest, `ollama-sidecar.sh` rebuilding the hand-started
`rakazo-local-model` (Ollama, model `qwen3:1.7b`) at its locked digest, and a
README with a five-command way back to the locked versions by retagging.

The tag variables in the host `.env` were not changed to `edge@sha256:...`.
Rakazo's supervisor looks up the computer image by that exact string and tries
to build it from source when the lookup fails. Whether the Docker daemon
resolves a tag and a digest together in that lookup was not tested. Nothing
on the host was changed.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rakazo-capture-settles-the-open-items_v1_2026-09-23-1345.md
DATE: 2026-09-23
DECISIONS: Tee ruled this correction be filed.
FINDINGS: The live Rakazo compose file is byte identical to upstream at 1a1f7b8. Postgres runs the upstream-pinned digest, and the morning's plain postgres:16 was docker ps shortening the reference. Bot team containers are created at runtime by Rakazo's supervisor. Images change only on a deliberate pull, not on their own. All nine containers' digests are recorded and each exists in its registry.
OPEN: Pinning the Rakazo images in the host .env is not done and needs a test of Docker resolving a tag plus digest reference before it is safe for the computer image. The rakazo-local-model rebuild script is a reconstruction and has not been run.
STATUS: Capture run, facts recorded in rakazo-deploy 21874d8, host unchanged.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
