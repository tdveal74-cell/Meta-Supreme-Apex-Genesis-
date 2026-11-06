# Hermes v0.23.0 compatibility integration

DEVON remains its own runtime. This change ports reviewed behavior into its
existing boundaries; it installs no upstream Hermes package or gateway.
Tee authorized completing, merging and deploying the reviewed fixes.

## Upstream receipt and scope

Rechecked 2026-11-06: the official latest release is v0.23.0, published
2026-11-05T21:32:33Z at 2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19.
GitHub release ID: 435665175. Use the version, commit and publication timestamp
to deduplicate later update checks; a release announcement is not a DEVON deploy.
Release: https://github.com/NousResearch/hermes-agent/releases/tag/v0.23.0
The official security advisory page reports no published advisories:
https://github.com/NousResearch/hermes-agent/security/advisories
That is not a claim that the release has no security fixes.

The release's approval hardening, curator locks, cron controls and memory
lifecycle work prompted a direct inspection of DEVON at
6cf649b749f6bbf24ad3fb6feb046c8b3f34f196. Earlier keyword-only absence claims
are superseded by the narrower findings below. These are DEVON implementations,
not claims that its source or feature set equals upstream.

## Runtime changes

| Boundary | Changed paths | Verified behavior |
|---|---|---|
| Approval consumption | `services/devon/approval.py`, its soul mirror, `app/services/devon_approval_store.py` | An approved record cannot authorize a new effect at or after its deadline. PostgreSQL locks the row before checking database wall time, including time spent waiting for the lock. The human ruling remains recorded. |
| Curated skills | `app/services/skill_revisions.py`, `app/api/v1/agent_skill_revisions.py`, `app/api/v1/agent_expansion.py`, `services/agent_runtime/learning.py` | Owner-scoped versioned lock transitions reject direct edits, evaluated promotion and rollback while locked. Existing per-owner/name transaction locks serialize writers and refresh stale ORM state. |
| Scheduled work | `app/services/hermes_expansion_persistence.py`, `app/services/agent_runtime_persistence.py`, `app/services/agent_tasks.py`, `app/api/v1/agent_expansion.py`, `app/api/v1/agent_tasks.py`, `services/agent_runtime/{runtime,expansion,expansion_tools,schedule_policy}.py` | Owner cancellation is durable and checked between tools; an in-flight effect retains its result and receipt. Explicit catch_up/skip policy preserves the original due slot across retry backoff. Existing schedules retain catch_up. |
| Browser reads | `services/browser/http_fetcher.py` | Read at most 200,000 response bytes before buffering; preserve the 50,000-character output limit. Request identity encoding and refuse compressed responses. Redirect and rate-limit protections remain. |
| Presence lifecycle | `apps/presence/main.py`, `apps/presence/livekit_publisher.py` | Early ready/open-send failure cleans the session owner mapping and sink. Partial LiveKit startup retains resource ownership for cleanup, including cancellation; source-close failure still attempts room disconnect while preserving the primary startup error. |
| Surface sentinel | `docs/devon/hermes-surface.json` | Routes advance from 33 to 36 for two curator-lock routes and schedule cancellation; 27 tools, 9 states, 152 columns, 8 counted Hermes migrations remain. |

No schema migration, credential change, provider switch, automatic skill
promotion, schedule execution, or private-record export is part of this patch.
WRITE/HIGH_IMPACT approval and receipt boundaries, tenant isolation, effect-free
core and canon remain in force. The skill lock applies to the runtime skill
store; it is not a sandbox for arbitrary filesystem writes.

## Current integration receipt

The canonical automation host remains https://n8n.editforge.online and current
storage is n8n Data Tables. Historical Cloud/Airtable records do not prove
current wiring. The November 5 inventory timeout recovered on a read-only
retry at 2026-11-06T08:45:08Z: run 42065126583, job 127798946987 read 310
workflows, 74 active, against 68 registry rows. All 17 repository automations
already had rows. Six active workflow IDs were independently verified missing:

- 943bt8loOkdGHssr: ACX - YouTube Reach Import and Review
- iVBlc3UwJKnaxNkM: DRAFT Jev Still Gate (TSWS + ACX) - inactive
- PH6yK59HZUl1npJr: NCO - YouTube Reach Import and Review
- VR21rYTCQWBs0SVc: TQO - YouTube Reach Import and Review
- 3x274kQbu1o2Li9Z: TQO Growth - Pilot Measurements and Review
- HDHQ4rWcRH42dX6A: TSWS - YouTube Reach Import and Review

`registry/automations.json` now claims exactly those six with owner Tee and
null review dates. The second workflow's live active flag controls inventory,
even though its title says inactive. No workflow was toggled or executed and
no end-to-end human review date was invented. The check now runs on relevant
pushes to main so the merged registry receives an authenticated readback.
The never-reviewed backlog remains visible. This inventory does not prove
every Data Table mapping, workflow credential or external delivery works.
The latest retrieved show-registry receipt is run 42058535540, job 127353472764,
at 2026-11-05T15:47:32Z: show_registry (xmNWLUm49QyZ4ysO) read 2 of 2 expected
rows CLEAN and show_series (s1IxySUuphOVrOqU) read 16 of 16 CLEAN. This verifies
those two Data Tables at that timestamp, not all tables or today's contents.

## Compatibility decisions

- DEVON already binds approval cards to their task and step. A stale card for
  a different request was already refused; the newly fixed defect is expiry
  at consumption, not a claim that upstream's exact defect was present.
- No generic paid MCP adapter or fixed-price declaration exists in the current
  tool registry. Upstream per-chat paid-MCP budgets are a future integration
  requirement; this patch neither invents prices nor adds unused budget code.
- Upstream's unified single-user gateway is a design difference, not evidence
  that DEVON's tenant-aware services should be replaced. No replacement ships.
- Upstream removes old browser tool names in favor of browser_exec. DEVON's
  own adapters keep their contracts. This patch does not activate a private
  browser worker or claim a production computer is provisioned.
  Its CI build exposed an unavailable Chromium pin. Following the standing
  exact-pin policy, all three packages move from 156.0.8078.73-1~deb12u1 to
  156.0.8078.79-1~deb12u1, verified in signed Debian metadata dated November 5.
  `deploy/browser-worker/seccomp-sources.md` records signatures and hashes.
  Debian still lists unresolved vulnerabilities; build availability does not
  clear production rollout. The worker remains disabled.
- No reachable DEVON PowerShell adapter was demonstrated. Its existing shell
  classifier work is not relabeled as a new PowerShell fix.
- Compressed browser responses now fail explicitly when a server ignores
  Accept-Encoding: identity. That bounded failure is the intentional tradeoff.

## Validation, release gate and rollback

The independent critic ran 113 targeted tests and killed six
mutations: reset original schedule slot, bypass curated lock, bypass cancellation,
unbound browser stream, stale presence owner binding, and bypass queued expiry.
The resulting LiveKit follow-up passed 64 publisher/presence tests. Five
failure-first cleanup cases failed on the baseline; an independent verifier's
own RTC probes also reproduced the defects and passed after the patch, including
real task cancellation, primary-error preservation and repeated close.
Local receipt/surface/registry checks passed 732 cases.
An existing wrong-turn interrupt test also assumed acknowledgment and state
were adjacent wire messages. Two reviewers reproduced legal audio interleaving
from the continuing producer. The test now covers ordinary and forced
interleaving, requires the correct acknowledgment with zero flushed frames,
rejects premature metrics/errors, and proves the real turn can still be stopped.
The affected suite passed 65 cases; two independent mutations that actually
cancelled the wrong turn failed. No runtime behavior was changed for this flake.

The corrected PostgreSQL critical cases passed 16 cases with no skips. The
expiry regression was independently shown to fail at its behavioral assertion
when only the SQL expiry predicate was removed, then passed after restoration.
An initial full run passed 9,811 tests and failed one new fixture because it
set expiry before creation. The fixture now ages creation, ruling and deadline
coherently; the database constraint is retained. A later full run hit disk
exhaustion near completion, which is an environment failure, not a pass.

Validation-location exception: the shared VPS began with little disk headroom.
Removing this run's disposable pytest fixtures recovered 1,232,752,640 bytes
and a fresh read showed 3.0 GB free. A fresh private database retained fsync and
full_page_writes, bounded its WAL, and the validator gained an owned basetemp
and a 256 MiB stop guard. Free space then fell by roughly 2 GB while this run's
measured database, logs and fixtures accounted for only tens of MB. Other host
activity was consuming space. The remaining validation moved to isolated
GitHub Actions under Tee's delegated decision authority. This is an explicit
exception to local validation before push, not a claim of a clean final local
full-suite run. The PR stays draft until all required checks pass on its head.

The final PR records the exact tested head, GitHub Actions gates, independent
mutation checks and post-merge production deployment IDs/commits. A ready preview
or merge alone is not evidence of production.

Rollback target is the preceding source commit
6cf649b749f6bbf24ad3fb6feb046c8b3f34f196. No schema downgrade is needed.
Prefer reverting a faulty compatibility slice while retaining security fixes.
Before a full-source revert, pause WRITE/HIGH_IMPACT dispatch because the old
runtime lacks the new consumption-time expiry guard. Hold skill mutations
because it does not enforce new curator locks; hold schedule execution if new
cancellation/skip policy must be retained. Existing revision records and effect
receipts must survive.
Do not replay an in-flight/orphaned effect or weaken approval checks as a
rollback shortcut. No production lock or cancellation was set by validation.

Pre-change Railway SUCCESS receipts were api
a4cfe313-ce0d-492c-b37a-51c2cea57c0f, presence
78c6d419-8efe-41a7-803e-77e9ddbe2dc1, and scheduler-cron
93288c3e-017d-4653-9cec-049dd4e602c7, all at that source commit.
All three configs use their Python 3.12 Dockerfiles; API waits for CI, while
presence and scheduler do not. The soul approval mirror must deploy, too.
The web app has no changed served inputs in this arc, so an unchanged production
web build can be current even if its repository commit is older.
At 2026-11-06T09:15:39Z, pre-change HTTP reads from the authorized VPS returned
200 from API health, Presence health and self-hosted n8n healthz. Presence read
Gemini inference, mock fallback, Cartesia speech, ElevenLabs ears, LiveKit
configured, audio_over_websocket false, and a closed breaker. This is a wiring
and reachability receipt, not a live voice/provider execution test.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_hermes-023-runtime-integration_v1_2026-11-06-0857.md
DATE: 2026-11-06
DECISIONS: Tee authorized reviewed compatibility fixes, merge and deployment; retain DEVON's custom runtime and governed boundaries.
FINDINGS: Approval expiry, startup cleanup and browser buffering defects reproduced; skill locks and schedule controls integrated; six missing live automation registry claims identified.
OPEN: Exact-head CI and production readback are recorded in the PR; external thread-log capture is unverified because its authenticated capture door was not used.
STATUS: Source integration candidate; no upstream package installation or full feature-parity claim.
