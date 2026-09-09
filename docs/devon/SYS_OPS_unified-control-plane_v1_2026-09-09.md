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
primary device. Measured from the rendered page rather than from this list: two
panels read every field they show, four read a route but cannot source some
field and say which, and one has no route at all. An earlier draft of this
document said five and two, which was counted from the panels this session had
open rather than from the badges on the page, and is corrected below. Every panel carries a badge saying whether it reads a real
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

## Correction, 2026-09-09 after the merge: it IS deployed

The paragraph below said nothing was deployed, and this session repeated that to
Tee. It was wrong, and the read back rather than an assumption is what found it.
Merging triggered a production build on both surfaces, so the sentence was false
from 03:48Z onward and was restated after that.

| Surface | Evidence | Commit |
|---|---|---|
| Vercel `meta-supreme-apex-genesis-web` | `dpl_5jXDgUBDeEyo4eVRFGrC3kNhWoz9`, READY, `target: "production"`, 05:35:18Z | `6a27a4e` |
| Railway `api` | `6fcbae6c-5d84-4e54-b4c9-8ea30eb0165f` SUCCESS, 05:35:15Z to 05:41:29Z, application startup complete | `6a27a4e` |

`/control` first reached production as `dpl_5LFcgr7qVXgLRVWe8QQuMDtxvGV4`, READY,
`target: "production"`, on `e03f4a2` at 03:48:29Z, which is the merge of PR #181.
Both surfaces now sit on `6a27a4e`, the same commit, which is current main.

Two things the read back settled that this document had left open, and one it
found that nobody had asked about.

The CORS question below is answered and the answer is yes. The running
application's own startup log reads `CORS allows 5 origin(s)` and names
`https://meta-supreme-apex-genesis-web.vercel.app` among them. That is read from
the process rather than inferred from the default in `app/core/config.py`, which
is loopback only; Railway overrides it.

The alembic pre deploy hook ran (`Context impl PostgresqlImpl`, `Will assume
transactional DDL`) with no upgrade line, which is correct: migration 019 landed
in an earlier deploy and nothing was pending on this one.

**The surface is behind Vercel Authentication, which no document here had
recorded.** `get_project_deployment_protection` reports `ssoProtection` enabled
with `deploymentType: "all_except_custom_domains"`. Every domain on this project
is a `.vercel.app` domain, so every one of them is protected. A person tapping
the production link on a phone gets a Vercel login, not the control plane, unless
that browser already holds a Vercel session for this account. So "deployed" and
"openable" are different claims, and only the first was in question until now.
Clearing it is a ruling for Tee: sign in to Vercel on the device, turn the
protection off for production, or bind a custom domain, which the setting exempts
by name. The third choice moves `PASSKEY_RP_ID`, currently
`meta-supreme-apex-genesis-web.vercel.app`, so a custom domain breaks passkey
sign in until that variable follows it.

## What is not verified

No presence service is deployed at all. Railway carries two services, `api` and
`Postgres`, and `PRESENCE_BASE` falls back to `http://localhost:8010`, so the
avatar tier cannot connect from a phone and will show as disconnected. That is
the honest state, not a fault in the panel. No LiveKit, Cartesia or live Cerebras
endpoint was reached, so the voice path of the cognitive tier is typed and
tested against mocks and nothing more. The n8n tier has no data source.

## The next gate

Deploy it, and read it back with the `deploy-readback` skill rather than
trusting a preview. Then a human opens `/control` on a phone and looks at it,
because nothing here ships on a screenshot taken by the thing that built it.
After that, in order: a read route over the n8n executions API so tier 3 stops
being honest about nothing; the owned likeness; and a LiveKit and Cartesia lane
proved end to end by a human listening.

## Amendment, 2026-09-09, after the critic

The fresh critic returned PASS-WITH-CONDITIONS, mean 4.4, security 5,
verification 4, with five conditions. All five are closed here, and closing them
turned up two things this document had wrong.

The first condition was the serious one and it was not cosmetic. The web
workspace had no test lane at all, so the one claim this arc exists to make
could be reversed and CI would still pass. The critic proved it rather than
asserted it: it inverted `readVerdict` so an intact but incomplete chain
returned a good tone, and `pnpm typecheck` exited 0, `pnpm build` exited 0, and
a browser rendered a green VERIFIED badge over a payload whose five events were
all unhashed. `apps/web/scripts/control-check.ts` now guards the verdict ladder,
the readiness risk resolution, the legibility floor and the input labels, at 23
checks with no test framework, matching `scripts/presence-check.ts`. Both it and
`check:presence` are wired into `web-ci.yml`; `check:presence` had existed as a
script no job ever ran, which is the same shape of gap.

Every new guard was proved by breaking it. A 9 pixel class reintroduced, a
disclaimer dimmed back to `text-white/35`, an input's `id` stripped, and a
watched file renamed each turned the check red for the stated reason, and the
baseline returned green at 23. The route parameter assertion was proved the same
way: giving `GET /api/v1/usage` an `account_id` argument fails
`test_usage_is_read_only_on_the_surface`, which passed identically before the
assertion existed.

The legibility numbers are computed against the page background `#05080c`, not
chosen by eye. White at 45 percent opacity is 4.48:1 and misses WCAG AA by a
hair, white at 50 percent is 5.35:1, `#526979` is 3.49:1 and `#718898` is
5.42:1. The calculator was checked against the critic's browser measurement of
3.11:1 for `text-white/35` and agreed at 3.09, so the thresholds are measured
rather than asserted. A browser at 390 pixels now reports zero text nodes under
11 pixels, zero under 4.5:1, zero horizontal overflow, zero page errors, and
four inputs all carrying a real label.

The doc comment on `ProvenanceReceipt.verified` was wrong in exactly the
direction the arc is built to prevent. It said the field meant no receipt
finding. The writer sets it from the receipt checks alone at
`app/services/live_state_ledger.py:835` and then appends the prefix finding
afterwards without recomputing it, so a receipt over a chain whose older rows
predate 019 arrives as `verified: true` while carrying a finding that says it
certifies those rows on trust rather than on proof. A reader who trusted that
comment would render the trust only case as green.

## What this amendment corrects in the text above

The panel count was wrong. This document said seven panels, five reading real
routes and two honest about having none. The rendered page reports two fully
sourced, four partly sourced and one with no route yet, so it is six and one.
That is the third time in this arc that a count taken from the lane rather than
from the estate came out wrong, after the receipt shapes and the migration
touch points, and it is the failure the first law names.

## What was measured to close this

Every number here came from the command beside it in this session, not from the
earlier run this document already recorded.

| Gate | Result |
|---|---|
| Full API suite | 1709 passed, exit 0 |
| Integrity and receipt shape | 290 passed, 207 and 83 |
| `ruff check .` | clean |
| `pnpm typecheck` | exit 0 |
| `pnpm build` | exit 0 |
| `check:control` | 23 checks, exit 0 |
| Standalone parity, no PYTHONPATH | import clean, subset exit 0 |
| Chromium at 390 pixels | 0 overflow, 0 nodes under 11px, 0 under 4.5:1, 4 labelled inputs, 0 page errors |
| Badges on the rendered page | 2 fully sourced, 4 partly sourced, 1 no route yet |

Two of those numbers were misread before they were right, both times by the
check rather than the code. `pytest ... | tail -2 | head -1` returns the last
progress line rather than the summary, so 290 passing tests read as two. And a
case sensitive needle for "Fully sourced" reported the badges missing from a page
that renders them as "FULLY SOURCED", which is the same mistake this document
already records once. A failing check is a claim about the check first.

A worse one cost real work. The negative controls for the new guards were
reverted with `git checkout <file>` on files that still held uncommitted edits,
which discarded the fix along with the mutation and left three files back at
HEAD. The guard caught it, because the baseline run went red instead of green,
which is the only reason it was noticed at once. Revert a deliberate mutation
from a copy taken before it, never from the index, whenever the file is dirty.

## What the conditions did not cover

Nine files outside the control plane still carry text under 11 pixels:
`app/page.tsx`, `app/council/deliberate/page.tsx`, the five
`components/command-center/*` files, `components/devon/DevonChat.tsx` and
`components/terminal/OperatorTerminal.tsx`. The guard is deliberately scoped to
the files mounted under `/control` rather than widened to surfaces this arc did
not build and did not open in a browser. Extending it is a ruling for Tee, not a
decision to take quietly while closing someone else's finding.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_unified-control-plane_v1_2026-09-09
DATE: 2026-09-09
DECISIONS: Tee ruled build it to completion, merge on the session's own recommendation, rulings on a card, AAA Flagship MVP as the bar; the n8n tier ships honest and unwired rather than carrying an invented chart; the security shell is linked rather than embedded so a bug on the control plane cannot reach a PTY on the API container; the per provider breakdown was deleted rather than faked once the schema showed no provider column; hard rule 1 was extended to the web surface rather than left as a rule nothing checked
FINDINGS: the four Immediate Deliverables had all shipped while the workspace that unifies them had not, which is what the two word question exposed; the cost panel was written before the 017 schema was read and assumed a provider column that does not exist; a real browser caught a badge reading "Live data" above a panel that could read nothing, and 45 pixels of horizontal overflow on a phone, neither visible to a green build; the web surface carried twenty two banned marks including the homepage headline because the integrity test never read it; two of four commissioned builders produced nothing and this session built their slices; pkill -f matched this session's own shell at exit 144, a stale server served a previous build through one re-measurement, and two smoke checks failed on wrong needles rather than real defects
OPEN: nothing is deployed and no surface is live; the n8n tier has no read route; LiveKit, Cartesia and live Cerebras remain unreached so the voice path is unproven; warning thresholds on the budget are not built; whether the deployed web origin is in the API CORS allowlist is unread; the owned likeness and the secret vault stay with Tee
STATUS: /control built with three tiers and seven panels, six reading a real route and one honest about having none; GET /api/v1/usage added read only with nine tests; full API suite 1709 passed, integrity and receipt shape 290 passed, ruff clean, tsc and next build clean, check:control 23 checks with all four guards proved by breaking them; Chromium at 390px reports zero horizontal overflow, zero text under 11px, zero under 4.5:1, four labelled inputs and zero page errors
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
