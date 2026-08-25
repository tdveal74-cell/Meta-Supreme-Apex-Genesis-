# DEVON n8n house conventions

Estate-wide patterns, extracted from the live organs (Soul Layer Write-Back,
Build 02 Ledger, Approval Queue, Ledger Feeder, Soul Committer). Follow them
when building or modifying ANY DEVON workflow, not just the learning lane.

## A success response is a claim, not a receipt

Every outbound HTTP node sets `neverError: true` + `fullResponse: true` and a
downstream code node reads `statusCode` back. 2xx is the only success; the
failure path emails an honest digest ("This is not a clean result") and the
work retries. Never let a workflow assume its own success.

## Own your idempotency; never borrow another organ's column

A workflow that must do something exactly once keeps its OWN data table of
what it has done (feed log, commit log), keyed on the natural id. Never mark
progress in a table another workflow upserts — Build 02 rewrites whole rows
from the envelope, so a foreign marker there gets wiped and the work repeats.

## Fail closed by data shape, not by routing

The Approval Queue's pattern: a refusal resolves to a sentinel that matches no
row, so a mis-wired graph writes nothing rather than something. Prefer designs
where the wrong path is structurally inert (deterministic upsert ids, hosts
that simply do not appear in the workflow) over designs that rely on a
condition node being wired correctly.

## Zero-item lanes are the quiet path

Poll workflows no-op silently when there is no work: a node that returns 0
items stops its lane, and that is correct. `alwaysOutputData: true` is used
ONLY where an empty read must not kill the chain (e.g. an empty idempotency
table on first run) and is always paired with a code guard that skips the
synthetic empty item.

## Item-count discipline

A node chained after an N-item node runs N times. Independent lookups chained
into a multi-item stream get `executeOnce: true`. Digest builders run once
over `$input.all()` and pair with sources by index via `$('Node').all()`.

## Approvals gate effects; email is the console

High-impact actions POST to `devon-approve-request` (title + what_happens
required — an approver cannot consent to the undescribed) and proceed only
when the queue row's status reads `approved`. Expiry is treated as rejection.
Notification emails go to Tee with `appendAttribution: false` and a
senderName naming the organ; activity emails only — silence means idle.

## Registration and secrets

Every new webhook/workflow is registered in `services/devon/vault.py` in the
same change (one path, one job). Credentials are n8n credentials by id
(Devon Capture Key `FYRvkRTOcROEYZ9P` for x-devon-key, Pinecone account
`3XjKfxbS7zFWEa48`, Gmail account `vsTKuAilHmpYCc5L`) — never literal tokens
in parameters, notes, or code nodes. Sticky notes on the canvas document what
the workflow does and why its guards exist; keep them truthful when editing.
