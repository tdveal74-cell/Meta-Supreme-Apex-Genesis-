# The EditForge host runs Rakazo, and fourteen containers more than the record names

Written 2026-09-23. Tee asked for his Hostinger VPS that runs "Razako" to be
checked and given a repository. The software is spelled Rakazo, and a search
for the misspelling is why the first read found nothing on disk.

## How it was read

The Hostinger connector lists subscriptions and websites but exposes no read of
a virtual machine or its Docker projects, so it could confirm only that two
KVM 2 plans are active, both renewing 2026-09-28. The container list came from
Tee running a read-only command in the hPanel browser terminal on the box
labelled "EditForge VPS", hostname `srv1936199`, and sending two screenshots at
12:58 local time. Every row below is transcribed from those screenshots. None
was read directly by this session, which has no network path to the host.

## What the host runs

The 2026-09-05 estate map records EDITFORGE-HOST as "editforge web, provider,
edge and worker plus two 1backend containers". That was six. The screenshots
show twenty. Not all fourteen extra are new since then:
`1backend-ogy1-password-init-1` exited about two weeks ago and may already have
existed, uncounted, on 2026-09-05.

| container | image | state |
|---|---|---|
| editforge-web-1 | editforge-web:local-google-callback-20260921T053253Z | up 46 hours, healthy |
| editforge-edge-1 | caddy:2.10.2-alpine | up 3 days |
| editforge-worker-1 | ghcr.io/tdveal74-cell/editforge-worker:b00ab77829bb | up 7 days, healthy |
| editforge-provider-1 | ghcr.io/tdveal74-cell/editforge-provider:b00ab77829bb | up 7 days, healthy |
| editforge-identity-init-1 | busybox:1.37.0 | exited (0) 4 days ago |
| 1backend-ogy1-1backend-1 | crufter/1backend:default-0-latest | up 7 days |
| 1backend-ogy1-1backend-ui-1 | crufter/1backend-ui:latest | up 7 days |
| 1backend-ogy1-password-init-1 | curlimages/curl:latest | exited (0) 2 weeks ago |
| open-generative-ai | open-generative-ai-open-generative-ai | up 2 days |
| meta-supreme | meta-supreme-web:local | up 5 days |
| devon-soul | devon-soul:local | up 5 days, healthy |
| rakazo-api-1 | ghcr.io/elie222/rakazo/app:edge | up 3 days, healthy |
| rakazo-web-1 | ghcr.io/elie222/rakazo/app:edge | up 3 days |
| rakazo-worker-1 | ghcr.io/elie222/rakazo/app:edge | up 3 days |
| rakazo-supervisor-1 | ghcr.io/elie222/rakazo/app:edge | up 3 days, healthy |
| rakazo-postgres-1 | postgres:16 | up 4 days, healthy |
| rakazo-local-model | ollama/ollama:latest | up 2 days |
| rakazo-computer-1 | ghcr.io/elie222/rakazo/computer:edge | exited (0) 3 days ago |
| rakazo-bot-team-792164ec4541b33c83771f4c8802be40 | ghcr.io/elie222/rakazo/computer:edge | exited (0) 2 days ago |
| rakazo-data-init-1 | busybox:1 | exited (0) 3 days ago |

`meta-supreme` and `devon-soul` running here as locally built images is new
to the record. The 2026-09-06 operational report names Vercel as the home of
both surfaces. Which of the two is serving production is not settled by a
container list, and this doc does not claim either. Load `deploy-readback`
before saying.

## What Rakazo is

Rakazo is Elie Steinbock's open-source platform for persistent AI teammates,
Apache 2.0, at `github.com/elie222/rakazo`, read at commit `2256bfa` on
2026-09-23. The service names on this host line up with its
`infra/compose/docker-compose.images.yml` with three differences.
`rakazo-local-model` appears nowhere in upstream and was added on the host.
`rakazo-bot-team-...` is not an upstream compose service and looks spawned at
runtime, UNVERIFIED. Upstream pins postgres by digest in that file while the host
shows plain `postgres:16`, so which compose file is live is UNVERIFIED until
`capture.sh` runs.

Seven of the nine run on moving tags, the Rakazo images on `edge` and the
model on `latest`, so the next pull installs whatever upstream pushed that day
and the only trace of what ran before is the old image left on disk until a
prune. That is the first thing the deploy repository fixes,
by pinning digests.

## The repository

Tee ruled a private deploy repository over a fork: it holds only what exists on
this host and nowhere else, never upstream source. Creating
`tdveal74-cell/rakazo-deploy` failed with `403 Resource not accessible by
integration`: this session's GitHub connection can push to repositories it is
installed on but cannot create one. The first commit is staged locally
(README, a read-only `capture.sh`, a `.gitignore` that blocks `.env` and
keys) and waits on the empty repository existing.

A fresh critic broke the first version of `capture.sh` four ways: a bare
`TOKEN=`, secrets whose names matched no pattern, the body of a multi-line
key, and the sidecar's command all printed in clear. It was rewritten to mask by
allowlist, so only structural keys such as `image`, `restart`, `ports` and
`volumes` print a value and everything else prints `<v>`. Every case the
critic used was re-run through it against a stub `docker` and none leaked. It
has not run on the real host.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_the-editforge-host-runs-rakazo-and-more_v1_2026-09-23-0501.md
DATE: 2026-09-23
DECISIONS: Tee ruled a private deploy repository for Rakazo over a fork of upstream, and ruled this record be written.
FINDINGS: The software is Rakazo, upstream elie222/rakazo, Apache 2.0. It runs on srv1936199, the EditForge VPS, as nine containers, seven of them on moving edge or latest tags. The host runs twenty containers where the 2026-09-05 record names six, including locally built meta-supreme and devon-soul. The Hostinger connector has no VM read. GitHub repository creation is refused to this session's integration.
OPEN: Tee creates the empty private repository tdveal74-cell/rakazo-deploy and gives the Claude GitHub App access to it, then runs capture.sh on the host so the compose files, env key names and digests can be committed. Whether meta-supreme and devon-soul on this host are serving production is unverified.
STATUS: Inventory recorded from Tee's screenshots. Deploy repository content staged, not pushed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
