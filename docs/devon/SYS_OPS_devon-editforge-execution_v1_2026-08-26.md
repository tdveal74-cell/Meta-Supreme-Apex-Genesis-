---
title: DEVON EditForge Execution
type: SYS_OPS
version: 1
date: 2026-08-26
area: Creation
status: implemented-local-verification-complete
command_contract: editforge.edit-command.v1
receipt_contract: editforge.edit-receipt.v1
---

# DEVON EditForge Execution v1

## Ruling

DEVON is the only executive control plane. EditForge is a self-hostable media
execution engine underneath it. This implementation gives DEVON the governed effect
path required to authorize, execute, poll, retry, and cancel edits; it does not create
a second orchestrator.

`services/devon/editforge_execution.py` remains a network-free validation and approval
contract. `app/services/editforge_client.py` owns authenticated transport at the
FastAPI effect boundary, preserving the core package's no-network integrity law.

Publication, deletion, canon changes, and clone/voice identity changes remain absent
from the execution API. They require their own explicit authority and cannot be smuggled
inside an edit operation.

## Supported portfolio work

| Work | DEVON requirement | EditForge execution |
|---|---|---|
| Long form | locked project/cut/canon and exact operation approval | timeline/adapter assembly, FFmpeg finish, preview/master |
| Short form | locked source and output dimensions | derive/reframe, captions, mix, grade, MP4 encode |
| Micro-drama | locked project canon plus full-motion operation | clone voice, full motion, lip sync, episode assembly |

Identity work requires all four values before approval: clone id, voice id, identity
version, and `consentRecorded: true`. TSWS and Ascension Caudex commands must name their
own canon revisions; cross-property canon is refused.

## DEVON API

| Route | Behavior |
|---|---|
| `GET /api/v1/devon/editforge/status` | Reads live self-hosted/hosted EditForge health and execution readiness |
| `POST /api/v1/devon/editforge/authorize` | Creates approval bound to the exact intent SHA-256 |
| `POST /api/v1/devon/editforge/execute` | Requires approved matching intent; builds and sends the scoped command |
| `GET /api/v1/devon/editforge/executions/{command_id}` | Polls and validates the worker receipt |
| `POST /api/v1/devon/editforge/executions/{command_id}/retry` | Retries a failed immutable revision |
| `POST /api/v1/devon/editforge/executions/{command_id}/cancel` | Cancels without deleting the record |

The shared DEVON approval queue remains the authority. The approval consequence carries
`EDITFORGE_INTENT_SHA256=<digest>`, and execution recalculates that digest. A changed
operation, source, identity, canon, or output no longer matches.

## Self-hosted operation

EditForge's `compose.yaml` publishes only the web/control plane. Its worker stays on the
render network and includes FFmpeg and FFprobe. Durable command records, worker jobs,
and rendered artifacts live on named volumes.

DEVON configuration:

```dotenv
EDITFORGE_URL=http://host.docker.internal:3100
EDITFORGE_TOKEN=<EditForge EDITFORGE_MCP_TOKEN>
EDITFORGE_TIMEOUT_SECONDS=60
```

The DEVON development compose file maps `host.docker.internal` to the host gateway, so
an API container can operate a host-published EditForge stack. When both processes run
directly on the host, use `http://localhost:3100`.

The status route distinguishes:

- `configured`: DEVON has a URL and token;
- `live_verified`: EditForge answered;
- EditForge `executionReady`: its worker is configured and healthy.

DEVON must not call execute when only `configured` is true.

## Receipt acceptance

DEVON accepts a terminal receipt only when:

- schema is `editforge.edit-receipt.v1`;
- command id matches the requested command;
- revision id matches EditForge's recorded immutable revision;
- state is `completed`, `failed`, or `cancelled`;
- every returned artifact has a URI and SHA-256;
- a completed receipt includes at least one artifact.

EditForge additionally prevents a late completion callback from overwriting a recorded
cancellation.

## Verification performed

- root and `deploy/soul` service copies: byte identical;
- targeted DEVON, operating-layer, integrity, vendoring, health, and OpenAPI tests:
  226 passed after rebasing onto the current main branch;
- Python compile passed;
- EditForge unit/route suite and production build are recorded in that repository.

Live clone/full-motion rendering is intentionally not claimed. It requires Tee's actual
consented clone/voice identifiers, media, provider adapter endpoints, and credentials in
the self-hosted environment.
