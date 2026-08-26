---
title: DEVON ChatGPT Complementary Operating Layer
type: SYS_OPS
version: 1
date: 2026-08-26
area: Systems
status: merged-remote-ci-green-deploy-pending
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base_ref: main
base_commit: 19d8ff3ed4ad374923d408cc8a8c0af5c00ebcf6
policy_contract: devon.operating-layer.v1
handoff_contract: devon.handoff.v1
audit_contract: devon.cross-model-audit.v1
return_contract: devon.artifact-return.v1
---

# DEVON ChatGPT Complementary Operating Layer v1

## Ruling

DEVON remains the only executive control plane. ChatGPT is a complementary
operating surface beside Claude. This build adds deterministic routing,
contracts, evidence gates, and a live Command Center representation. It does
not add another orchestrator, approval authority, shell, heartbeat, provider
router, or source of truth.

## Sources actually opened

| Source | Exact reference | What it governs here |
|---|---|---|
| Current repository main | `19d8ff3ed4ad374923d408cc8a8c0af5c00ebcf6` | Executable DEVON behavior and current Command Center |
| DEVON LLM Standing Instructions v3 | Authorized DEVON vault read on 2026-08-26 | Cross-model behavior, one-writer law, receipts, and honesty |
| DEVON Precedence Doctrine v2 | Authorized DEVON vault read on 2026-08-26 | Version precedence and human conflict rulings |
| DEVON Cross-Platform Capture Protocol | Authorized DEVON vault read on 2026-08-26 | Artifact and receipt return |
| DEVON Master Directory v6 | Authorized DEVON vault read on 2026-08-26 | Current vault map and nine-Area ruling |
| ChatGPT Work | `https://learn.chatgpt.com/docs/get-started-with-work` | Multi-step work and reviewable artifacts |
| Scheduled tasks | `https://learn.chatgpt.com/docs/automations` | Time and app-event triggers |
| Deep Research | `https://developers.openai.com/api/docs/guides/deep-research` | Current multi-source research with sources |

## Control plane

| Surface | Use it when | Authority boundary |
|---|---|---|
| DEVON | Route, hold conflicts, accept receipts, expose policy status | Only executive control plane |
| Claude | Reconcile DEVON canon and cross-system architecture through the established lane | Cannot make Tee's ruling |
| ChatGPT | Operator-facing synthesis, planning, critique, and the front door to complementary surfaces | Cannot replace DEVON or claim unprobed capability |
| Codex | Inspect, change, test, and review real repositories or local workspaces | Repository writes remain approval gated |
| Deep Research | Current multi-source work needs opened sources and citations | Cannot write canon |
| Work | A substantial multi-step task must create a reviewable file or workflow | Consequential actions still pause |
| Connected apps | The source or action belongs in an authorized service | Identity, scope, action, and read-back must be exact |
| Scheduled tasks | Work must recur, run later, or wake from a supported event | The trigger does not become an authority |

Cerebras stays where it already belongs. It is an intelligence provider layer,
not a work-surface router and not an orchestrator. Its live provider status
continues to come from the existing authenticated `/api/v1/intelligence/status`
route.

## Routing order

The policy is deterministic and effect free.

1. Human rulings stop at DEVON for Tee.
2. Canon writes go to the established Claude lane and still require approval.
3. Repository and local-machine work goes to Codex.
4. Deferred and recurring work goes to Scheduled Tasks with a separate action surface.
5. Connected-source work goes to the connected app.
6. Current multi-source evidence goes to Deep Research.
7. Multi-step reviewable artifacts go to Work.
8. Cross-system architecture goes to Claude.
9. Direct synthesis and short drafts stay in ChatGPT.

Every decision returns to DEVON with required evidence and a receipt. Routing
is a plan. The policy module has no network, process, model, app, or write
capability.

## Claude and ChatGPT handoff contract

`devon.handoff.v1` is bidirectional. A valid handoff contains:

- a stable handoff id
- one exact goal and context summary
- the sending and receiving surfaces
- canonical source title, URI, read time, and revision when available
- locked decisions and constraints
- requested outputs
- artifact paths and hashes when an artifact already exists
- verification commands
- unverified claims
- unresolved conflicts
- risk and explicit approval state for writes or high-impact work

An unresolved conflict cannot cross the boundary as ordinary context. It stops
for Tee. A same-artifact version can use precedence. A load-bearing
contradiction cannot.

## Cross-model audit loop

`devon.cross-model-audit.v1` enforces an independent verifier.

1. The producer returns the exact artifact, source manifest, and claimed checks.
2. A different surface opens the artifact and reruns applicable checks.
3. Findings name their evidence.
4. The producer repairs failed elements and returns a new hash.
5. The verifier reruns failures and regression checks against the new hash.
6. DEVON accepts the receipt or routes the conflict to Tee.

Acceptance requires an evidence-backed score of at least 99, no unresolved
critical or high finding, a different producer and verifier, concrete
verification evidence, and the final SHA-256 artifact hash. A score alone never
passes.

## Artifact and receipt return path

`devon.artifact-return.v1` plans a reviewable GitHub return without executing it.

- Base: current `main`
- Branch: `devon/handoff/<handoff-id>`
- Handoff manifest: `docs/devon/handoffs/<handoff-id>.json`
- Receipt: `docs/devon/receipts/<receipt-id>.json`
- Artifacts: their canonical repository-native paths, never duplicate copies
- Write sequence: create branch, write exact files, open pull request
- Verification: read every path at the created commit SHA, compare hashes, run repository-native checks, then read PR checks
- Merge authority: Tee through the existing DEVON approval authority

The planner rejects absolute paths, parent traversal, invalid hashes, unsafe ids,
and any base other than `main`. Its response states `executed: false`.

## Source of truth and conflict rules

1. Tee's explicit current ruling outranks every model and artifact.
2. Current `main` owns executable DEVON behavior and the current Command Center.
3. Current DEVON records own studio canon, prior decisions, and external system facts after a live read.
4. A same-artifact version may use precedence. A contradiction never does.
5. A load-bearing disagreement between main and a DEVON record stops for Tee.
6. A model output remains a proposal until the artifact is read back and verified.
7. Configured, available, live, and verified remain separate states.

The connected-source identifiers used during implementation are intentionally
excluded from this public repository. Runtime callers must resolve them through
an authorized DEVON source read instead of treating a public code constant as
an access path.

## Live Command Center representation

The Command Center now probes `/api/v1/devon/operating-layer/status` beside the
existing API, operator, provider, heartbeat, and write-authority reads.

The status response can prove that the DEVON policy API is live and that each
external surface has a contract. It cannot introspect a Claude, ChatGPT, Codex,
Deep Research, Work, connected-app, or scheduled-task session. Those surfaces
therefore display `contract_ready` and `live_verified: false` until their own
receipt supplies evidence. No invented green status is permitted.

## API surface

| Route | Purpose | Effect |
|---|---|---|
| `GET /api/v1/devon/operating-layer/status` | Canonical control-plane and surface status | Read only |
| `POST /api/v1/devon/operating-layer/route` | Deterministic capability selection | Plan only |
| `POST /api/v1/devon/operating-layer/handoff/validate` | Claude and ChatGPT contract validation | Validation only |
| `POST /api/v1/devon/operating-layer/audit/plan` | Independent verifier and loop plan | Plan only |
| `POST /api/v1/devon/operating-layer/audit/verdict` | Evidence-backed acceptance gate | Validation only |
| `POST /api/v1/devon/operating-layer/artifact-return/plan` | Branch, manifest, receipt, and read-back plan | Plan only |

## Preserved without replacement

- shared approval authority
- passkeys and password recovery
- governed Operator Bridge
- dedicated two-factor real shell
- effect receipts, leases, and idempotency ledger
- Cerebras intelligence provider lane
- heartbeat and continuity schedules
- DEVON persona and nine Areas
- current Unified Command Center

The corrected ecosystem map is recorded in
`SYS_SPEC_devon-ecosystem-control-map_v1_2026-08-26.md`. It includes The Quiet
Operator, The Shadow We Share, NCO Forge, and Ascension Caudex as distinct
portfolio outputs beneath the existing production and control planes. The
rendered map is stored at
`docs/devon/assets/SYS_PROOF_devon-ecosystem-control-map_v2_2026-08-26.jpg`.

## Verification state

Local verification completed on the feature branch:

- `git diff --check`: passed
- changed Python `py_compile`: passed
- changed Python Ruff check: passed
- operating-layer and DEVON integrity tests: 123 passed
- wider DEVON pure suite: 314 passed
- exact standalone CI test set, including the new operating-layer test: 114 passed
- public-source scrub, four-property completeness, and rendered-image hash gates: passed
- ASGI and OpenAPI smoke: six routes present, status HTTP 200, route HTTP 200,
  audit plan HTTP 200, sole-orchestrator assertion passed

Frontend package installation could not reach the package registry in the
local execution sandbox. Docker is not installed in this workspace. Frontend
typecheck, frontend build, full integration CI, preview, merge, deployment, and
production reachability remained unverified at the time of the paragraph above.
The read-back below supplies the evidence that has since arrived.

## Remote verification read-back, 2026-08-26 post-merge

Recorded from GitHub after the pull request landed, not asserted from memory.

- Pull request: #66, final head `0b9470a28d987590eaa4dbe53b09db1e2fd00608`
- Two follow-up commits landed on the branch before merge:
  - `32aef5c` shipped `services/devon/operating_layer.py` byte identical into
    `deploy/soul` and synced the drifted vendored `__init__.py`, closing the
    two `test_deploy_soul.py` vendoring failures from the first CI run
  - `0b9470a` closed two review findings fail closed: a handoff whose
    `requested_output` is missing or blank is now an error, and audit
    severities are normalised with unknown spellings refusing the verdict,
    both with negative controls
- CI on the final head, workflow runs `32945927159` and `32945927151`, all
  five checks success: Standalone offline flagship (canonical), Engine +
  cadence (no database), Railway container contract, API suite (PostgreSQL 16
  + pgvector, completed 2026-08-26T08:08:33Z), Next.js typecheck + build
- Merged by Tee's explicit authorization as
  `Merge PR #66: DEVON complementary ChatGPT operating layer`, merge commit
  `600522cc9d4ffb7b8bb76ab215b7655a4a207410`
- Read back after merge with a fresh fetch: `origin/main` equals the merge
  commit, the merged tree is identical to the final head, and the root and
  `deploy/soul` copies of `operating_layer.py` hash identically at main

Still unverified, stated so nobody assumes otherwise: Vercel preview and
production deployment (the free plan daily deploy cap was exhausted, retry
window roughly 24 hours), production reachability, external-surface live
sessions, and the live-environment items that always remain manual for Tee.

## Receipt boundary

The public repository stores the handoff, evidence, and receipt schemas but no
capture credential. A DEVON receipt for this build must travel through the
private authorized capture path. Git history is not a credential store.

GitHub CI, pull request checks, frontend typecheck, frontend build, and the
merge are now verified and recorded in the read-back section above. Preview,
production deployment, and external-surface live sessions remain unverified
until executed or read back.
