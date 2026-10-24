# ARF DEVON shadow activation and acceptance

This record supersedes the release-status statements in
`SYS_OPS_arf-stage3a-receipt-readback-review_2026-10-20-1148.md` and
`SYS_OPS_arf-shadow-request-budget_v1_2026-10-20-1324.md`.
Their implementation history remains intact.

## Scope

ARF supplies authenticated, owner-scoped DEVON build-stage recommendations.
It cannot execute a task, close one, approve effects, attest human review,
or enforce creative-project acceptance. Task and evidence data are read-only;
the request limiter writes its own security-accounting rows.

PR #417 adds a console task picker, diagnostic summary and bounded six-request
acceptance check. Both served console copies are byte-identical. Requests use
the existing session authentication and fixed same-origin GET routes. Results
render as text without task goals, credentials or raw evidence payloads.

## Release evidence

The independently reviewed candidate and GitHub head
`9403f4c6e61f4e9571ce04ac9a24b259bb49a9ba` share tree
`fb4acd045ed689fd402184f84e2a0d95588b6069`.
PR #417 merged as `7030c5ffba13cc404c7b4e259e1c9570a8ce3f60` after
all PR workflows passed. All five main-branch CI jobs also passed before
Railway released the API deployment.

| Check | Observed result |
| --- | --- |
| Full disposable PostgreSQL suite | 6,061 passed, 3 skipped, 56 subtests passed |
| Standalone Python suite | 2,341 passed, 1 skipped |
| Client behavior and focused checks | 8 Node cases and 29 focused pytest checks passed |
| Authentication negative control | Removing the client guard failed the expected test; restored candidate passed |
| Real two-account acceptance | Own-task 200, cross-account 404, unchanged task state for both accounts |
| Dedicated PostgreSQL concurrency | Both snapshot and competing-history-writer tests passed |
| Migration validation | Upgrade, downgrade, upgrade and SQL/Alembic schema parity passed |
| Ledger and knowledge on Alembic schema | 49 passed |
| Web validation | Typecheck, all Web CI checks and production build passed |
| Other validation | Engine/import checks, Ruff, Python dependency audits and pnpm audit passed |
| Hosted PR verification | CI, Web CI and real Chromium Panel smoke CI passed |

The initial additional Alembic test run used a stale disposable Docker host
port after a network attachment. It failed to connect. Updating the test
harness to the actual mapped port produced the 49-pass result above. No
application code, assertion or production configuration was changed for it.

## Production acceptance

Observed on 2026-10-24 between 09:57:47 and 09:59:16 UTC, against the
application merge SHA above:

| Surface or acceptance check | Observed result |
| --- | --- |
| Railway API deployment | `77b7c6c1-78c4-40e8-a67b-dd5e5d3bc496`, SUCCESS at 09:57:47 UTC |
| Signed-in console | New ARF controls served at `https://api-production-5644.up.railway.app/console`; five owned tasks loaded |
| Owned-task diagnostic | HTTP 200, `WOULD_HOLD`, DEVON/build, one blocking reason, zero evidence references |
| Unknown task | HTTP 404; this alone is not evidence of cross-account isolation |
| Unauthenticated diagnostic | HTTP 401 |
| Six concurrent owned-task reads | Five HTTP 200 results and one HTTP 429 with `Retry-After: 2`, in 327 ms; no automatic retry |
| Read after budget refill | HTTP 200, `WOULD_HOLD` again |
| API health | HTTP 200, healthy at 09:58:50 UTC |
| Scheduler deployment | `670aed5c-132a-4a2a-9579-b36b0f9a6349`, SUCCESS at the same merge SHA |
| Soul deployment | `dpl_4Hjov5oEPBnG2vvq5A7Yngky8tqj`, READY, production, same merge SHA; `devon-soul.vercel.app` alias attached |

The authenticated 200 responses establish that shadow reads are effectively
enabled in production. No feature-flag value was changed during this console
release. The configuration connector redacts values, so this record relies on
the authenticated runtime behavior rather than claiming a raw value readback.

Nonproduction account-isolation results are not represented as production
cross-account measurements. The Soul production alias returned HTTP 401 to an
unauthenticated request; its rendered console was not separately inspected.
The signed-in acceptance above was performed on the Railway API console.
No production tasks were created, executed or modified for these checks.

These are time-stamped application observations. The subsequent documentation
merge does not invalidate them or imply that the deployment IDs above identify
that later documentation build.

A separate validated thread-log receipt is saved in
`receipts/ARF_shadow_activation_2026-10-24.txt`. External thread-log delivery
was not attempted.

## Rollback and limits

Set `ARF_SHADOW_READ_ENABLED=false` on the API service to disable this
diagnostic exposure. Do not remove the accounting table while reads are
enabled. Accounting failure must refuse diagnostics with 503 rather than
fall back to an unlimited or process-local budget.

The approved budget remains five immediate requests with one request
refilled every two seconds. It is not a strict rolling-window cap. Dedicated
creative QC, human acceptance, publication permission and independent approval
backend attestation remain outside this activated slice.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_arf-devon-shadow-activation_v1_2026-10-24-0950.md
DATE: 2026-10-24
DECISIONS: Release the reviewed read-only DEVON diagnostic console under Tee's standing merge and deployment authorization; preserve existing ownership, approval and request-budget controls.
FINDINGS: PR #417 and main CI passed; production owned reads returned 200 with WOULD_HOLD; unauthenticated access returned 401; unknown task returned 404; a six-read burst returned five 200s and one 429 with Retry-After 2; reads recovered; isolated account, concurrency, migration, dependency and web acceptance passed.
OPEN: Creative-domain enforcement, human acceptance and separate approval-backend attestation are not implemented by this slice; external thread-log delivery was not attempted; Soul rendered content behind authentication was not separately inspected.
STATUS: DEVON/build read-only shadow diagnostics enabled and production acceptance verified at the recorded application deployment.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
