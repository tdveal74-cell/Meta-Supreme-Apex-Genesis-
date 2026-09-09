# SYS_OPS: the unified control plane, and the output checked back against the brief (v1, 2026-09-09)

Date: 2026-09-09
Supersedes: nothing. Continues the arc that
`SYS_OPS_control-plane-foundations_v1_2026-09-08` closed, which delivered the
four files the brief listed and left the workspace itself unbuilt.
Ruled by Tee 2026-09-09: build it to completion, merge on the session's own
recommendation, rulings on a card, AAA Flagship MVP as the bar.

## Why this arc existed at all

Tee asked what the estate had been doing if the thing was not built. The answer
was that the four Immediate Deliverables of the 2026-09-08 brief had all shipped
and merged, and the workspace that unifies them had not. The pieces lived on
separate pages with no one surface to stand on, and nothing was deployed, so
there was nothing to open. That gap is what this arc closed on the repository
side. It does not close the deployment side, and this document does not pretend
otherwise.

## The output, checked against the original brief

Every row was verified by reading the file or running the command named beside
it, not from memory.

### The three tiers

| Tier | State | Evidence |
|---|---|---|
| Sovereign Admin Panel | Built | `/control` tier 1: agent readiness, ledger provenance, security and secrets |
| Interactive Cognitive 3D Hub | Built | tier 2: the presence stage and the knowledge corpus |
| Execution and Pipeline Monitor | Built, one panel unwired | tier 3: token budget reads a real route, n8n has none |

### The five modules

| Module | State | Evidence |
|---|---|---|
| 3D avatar with LiveKit, Cerebras and Cartesia voice, barge-in VAD | Partly | the canvas carries 8 morph target references, the audio hook 11 LiveKit references, the VAD an attack window at threshold 0.02. No LiveKit, Cartesia or live Cerebras endpoint was ever reached, so the audio path stays unproven |
| Agent readiness matrix | Built | `apps/web/components/readiness/`, reading the real task states and the Hermes surface manifest for tool risk |
| Second brain knowledge graph | Built as a corpus, not a graph | `apps/web/components/mind/`. No route exposes vector activations or edges between the namespaces, so no graph is drawn and the panel says so |
| n8n operations hub | Not built | no route in this repository reads the instance. The panel shows API health and states that a chart there would be invented |
| Security shell and secret vault | Shell live, vault absent by design | both shells predate this arc and the panel points at them. Nothing generates or stores secrets; a vault is a ruling |

### The four safeguards

| Safeguard | State | Evidence |
|---|---|---|
| Adaptive sliding window buffer | Built | `apps/presence/buffer.py`: priority 2 drops first, then 1, then 0 thinned to every other frame. Audio is never delayed or dropped; only the face adapts |
| Circuit breaker on TTFT above 500 ms with fallback | Built | `apps/presence/breaker.py`, `DEFAULT_TTFT_THRESHOLD_MS = 500.0`, with the fallback continuing the same turn on the same socket |
| SHA-256 on every event transition with a signed Universal Receipt | Built and hardened | migration 019, `services/devon/provenance.py`, and four gauntlet passes against it |
| Token and cost guardrails | Built, and now readable | the cap and ledger since 017; `GET /api/v1/usage` and the cost panel added here. Warning thresholds are still not built |

### The four Immediate Deliverables

| Deliverable | State | Evidence |
|---|---|---|
| Complete project structure map | Delivered 2026-09-08 | `SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08`, every path marked lives, built or not built |
| Production Docker Compose | Delivered 2026-09-08 | seven services: postgres, redis, migrate, api, presence, web, n8n |
| Core react-three-fiber 3D canvas | Delivered 2026-09-08 | `/presence`, blendshape frames over WebSocket, LiveKit audio hook, client VAD |
| Postgres schema for the Live State Ledger | Delivered, and it predated the brief | all six tables the brief named exist in `012_live_state_ledger.sql`; migration 019 added the chain and the signed receipt |

## What this arc added

`/control`, one surface, three tiers, built for a phone because that is the
primary device. Every panel carries a badge saying whether it reads a real
route, reads one with fields it cannot source, or waits on a route that does not
exist, and a partial or unwired panel must say why. That is structural rather
than a footnote: a workspace that renders all three states identically is the
drift the map document exists to prevent.

`GET /api/v1/usage` reads the spend ledger that migration 017 had been enforcing
a cap against since it landed without ever exposing it. Read only, scoped to the
caller, and it takes the cap from the same setting the refusal reads so the
figure shown cannot drift from the figure enforced.

Hard rule 1 now reaches the web surface. The integrity test had only ever read
`services/devon` and `docs/devon`, and the product surface a reader actually
sees had accumulated twenty two banned marks including the homepage headline.
All twenty two were restructured, the guard covers `apps/web`, and a second test
fails if that glob ever matches fewer than forty files.

## Findings

Reading the schema corrected the code rather than the other way round. The cost
panel was written first and rendered a per provider table. The 017 ledger is one
row per account per UTC day with no provider column, so the table was deleted
rather than filled with something plausible, and both the route and the panel
now report the dimension as unavailable so its absence cannot be read as zero
spend. This is the first law working as intended, and it is the second time in
two arcs that a panel or a count written before the file was read turned out to
be wrong.

A real browser found two defects a green build could not. A badge reading "Live
data" sat above a panel that had no session and could read nothing, which is
precisely the overclaim the badge was introduced to prevent; it now reads "Fully
sourced", which cannot be mistaken for a claim about the numbers on screen. And
the page overflowed a phone by 45 pixels, because a grid item defaults to a
minimum width of its content, so the presence panel pushed the page sideways.
Both are fixed and re-measured at zero.

Two builders commissioned for the usage route and the knowledge panel produced
nothing and had exited by the time they were checked. This session built both
slices itself rather than leaving the plane half mounted. The two that did
deliver, the readiness matrix and the provenance card, were wired as they came.

The method also produced three mistakes worth recording. `pkill -f` matched this
session's own shell and returned exit 144, which `CLAUDE.md` already documents
and which was walked into anyway. A stale server held the port and served the
previous build, so the first re-measurement after a fix measured the old page
and had to be redone after finding the process by port. And two smoke checks
failed on wrong needles rather than real defects, once on a case difference,
which is a reminder that a failing check is a claim about the check as much as
about the code.

## What is not verified

Nothing is deployed. This is a route in a repository, not a live surface, and a
green preview would not change that. No LiveKit, Cartesia or live Cerebras
endpoint was reached, so the voice path of the cognitive tier is typed and
tested against mocks and nothing more. The n8n tier has no data source. The
API's CORS allowlist defaults to port 3000 and whether the deployed web origin
is allowed is a deployment setting this session cannot read.

## The next gate

Deploy it, and read it back with the `deploy-readback` skill rather than
trusting a preview. Then a human opens `/control` on a phone and looks at it,
because nothing here ships on a screenshot taken by the thing that built it.
After that, in order: a read route over the n8n executions API so tier 3 stops
being honest about nothing; the owned likeness; and a LiveKit and Cartesia lane
proved end to end by a human listening.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_unified-control-plane_v1_2026-09-09
DATE: 2026-09-09
DECISIONS: Tee ruled build it to completion, merge on the session's own recommendation, rulings on a card, AAA Flagship MVP as the bar; the n8n tier ships honest and unwired rather than carrying an invented chart; the security shell is linked rather than embedded so a bug on the control plane cannot reach a PTY on the API container; the per provider breakdown was deleted rather than faked once the schema showed no provider column; hard rule 1 was extended to the web surface rather than left as a rule nothing checked
FINDINGS: the four Immediate Deliverables had all shipped while the workspace that unifies them had not, which is what the two word question exposed; the cost panel was written before the 017 schema was read and assumed a provider column that does not exist; a real browser caught a badge reading "Live data" above a panel that could read nothing, and 45 pixels of horizontal overflow on a phone, neither visible to a green build; the web surface carried twenty two banned marks including the homepage headline because the integrity test never read it; two of four commissioned builders produced nothing and this session built their slices; pkill -f matched this session's own shell at exit 144, a stale server served a previous build through one re-measurement, and two smoke checks failed on wrong needles rather than real defects
OPEN: nothing is deployed and no surface is live; the n8n tier has no read route; LiveKit, Cartesia and live Cerebras remain unreached so the voice path is unproven; warning thresholds on the budget are not built; whether the deployed web origin is in the API CORS allowlist is unread; the owned likeness and the secret vault stay with Tee
STATUS: /control built with three tiers and seven panels, five reading real routes and two honest about having none; GET /api/v1/usage added read only with nine tests; full API suite 1693 passed, integrity 204 passed, ruff clean, tsc and next build clean at 20.5 kB; twelve browser checks signed out and six signed in against a live API at 390px with zero horizontal overflow; PR #181 open
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
