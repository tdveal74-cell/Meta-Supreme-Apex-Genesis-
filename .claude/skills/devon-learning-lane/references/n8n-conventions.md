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
same change (one path, one job). Credentials are n8n credentials by id, never
literal tokens in parameters, notes, or code nodes: Devon Capture Key
`FYRvkRTOcROEYZ9P` for x-devon-key, Pinecone account `3XjKfxbS7zFWEa48`, and
for outbound mail the SMTP account `mu7nJRSpkAfkzLdF`. Sticky notes on the
canvas document what the workflow does and why its guards exist; keep them
truthful when editing.

**Mail moved off Gmail OAuth on 2026-09-05.** Gmail account `vsTKuAilHmpYCc5L`
went invalid on its own and took the Heartbeat, the Error Alarm and every other
lane that emails down with it, unnoticed for nine days. The Heartbeat and Error
Alarm now use `n8n-nodes-base.emailSend` on the SMTP credential, proven by
execution 5600 returning a real `250 2.0.0 OK` from gsmtp.

**The conversion is complete, audited 2026-09-12.** All 49 workflows on the
instance were read in full: `vsTKuAilHmpYCc5L` is referenced by ZERO nodes, and
all thirteen mail nodes across the eleven workflows that email run on the SMTP
credential. An earlier draft of this section warned that other workflows still
carried the dead credential and were each a silent failure until moved; that is
no longer true and the credential is now orphaned in the store. Proven from the
destination, not from the wiring: the Pulse mailed on 8, 9, 10 and 11 September
and an approval card landed 2026-09-12T20:52:00Z. An OAuth refresh token expires
with no warning; an SMTP password does not.

## Say what you did, with counts, or the digest is a green light with nothing behind it

Compiled 2026-09-07 from Austin Marchese's automation framework, where the
failure mode is named green light drift: an automation reports success for work
it did not do. It is the first law of `CLAUDE.md` pointed at machines instead of
at a session. That law governs what a session may assert. Until now nothing
governed what a workflow may assert, and the estate has already paid for the
gap: the Build 12 envelope read `not_captured` forever, and the Face, the
Heartbeat and the operational report all repeated it. Three surfaces
confidently reporting a wrong state.

So a terminal notification never says only that it ran. It names what it
touched, with numbers, and where the numbers came from:

- not "daily brief ran", but "analysed 41 of 41 emails from the Inbox view,
  200 Slack messages, 10 calendar events"
- not "sweep complete", but "read 128 ledger rows, 3 non-terminal past 96h,
  3 cancelled, 0 refused"

The number is the point. An operator who sees "1 of 1 emails" on a day they
know they got forty has caught a broken automation in one glance, and no
alerting rule would have fired, because nothing failed. A count that cannot be
produced is itself the finding: report the refusal, never a bare success.

The quiet path is not exempt. A zero item run says "0 of 128 rows matched",
not silence, because silence and a broken read look identical.

## Break before you spend, not after

The estate catches failure after the money is gone. `DEVON Error Alarm` and
`OS Error Handler` are both Error Triggers, which by definition fire on a crash
that has already happened. Nothing refuses a run whose dependencies are down
before it starts consuming executions.

So a workflow that depends on a credential, a table, a host or a connector
checks that they answer BEFORE it does any work, and refuses the run with a
message naming what is missing and how to fix it. A refusal is data, not a
crash: it takes the quiet path, emails once, and does not retry into the same
wall.

This is a burn lever as much as a correctness one. The 2026-09-06 measurement
put the instance at 314 saved executions in 24 hours, 11 an hour, about 264 a
day, against a cap that the cutover runbook expects to hit between 2026-09-17
and 2026-09-25. A lane that discovers at node 30 that its credential died has
spent thirty nodes to learn what node 1 could have told it.

Preflight what the run cannot proceed without, not everything. The test is
whether the run is guaranteed to fail without it.
