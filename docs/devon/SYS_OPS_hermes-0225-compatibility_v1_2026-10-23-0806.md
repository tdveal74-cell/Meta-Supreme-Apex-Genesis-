# Hermes v0.22.5 compatibility

Status record, 2026-10-23. Baseline DEVON main is
`faf600e5d7a0d8d26944038dc7974dfd9028add8`; implementation and regression
candidate is `d5b52fee10e3e678bfb5c60392383cdaf68d89b3`.
This record supersedes no earlier deployment receipt.

## Official evidence

[Hermes v0.22.5](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.5)
was published at `2026-10-23T05:28:45Z`. Its notes call the release October 22.
Annotated tag `56b6a31fededdf7364e1a0a79548d144e7fd81a3` resolves to commit
`bf0203a794a07aac3ff764972ab9087baa4e4f4e`. The latest-release API was checked
again October 23 and still names v0.22.5. The public
[advisories page](https://github.com/NousResearch/hermes-agent/security/advisories)
shows no published repository advisories; the advisories API was unavailable
through the connector, so that API did not establish the result.

DEVON is a custom runtime. This change neither installs upstream Hermes nor
claims that an upstream release updates DEVON automatically.

| Upstream evidence | DEVON applicability and action |
|---|---|
| [455e0a7402b57198f0712105494b970fb3902c22](https://github.com/NousResearch/hermes-agent/commit/455e0a7402b57198f0712105494b970fb3902c22), throttling distinguished from replay | DEVON has no identical-call failure streak. Its HTTP fetch adapter did lose structured 429 evidence. Preserve that evidence without adding a retry policy. |
| [2463bdcbbaf458a4c104ba4956ca20ad48fb5375](https://github.com/NousResearch/hermes-agent/commit/2463bdcbbaf458a4c104ba4956ca20ad48fb5375), unavailable delegation backend refuses | DEVON persists child tasks instead of selecting these backends. Existing missing-writer refusal precedes approval spending. Add coverage for spawn, scheduling and skill proposals. |
| [cd818a4d054dc28203577f2fcf27397bed7a281a](https://github.com/NousResearch/hermes-agent/commit/cd818a4d054dc28203577f2fcf27397bed7a281a), failed background launch cannot claim success | DEVON already records unknown and quarantines failed browser startup. Add factory-exception and nonexistent-executable coverage, including receipt replay and refusal to reuse the session UUID. |

The upstream welcome-trial scheduler fallback, backend registry, plugin migration
and desktop dependency changes are not demonstrated DEVON defects. No upstream
package, memory format, scheduler policy or skills activation policy is imported.

## Changed behavior

`services/browser/http_fetcher.py` raises a typed `ReadRateLimited` on HTTP 429.
`services/browser/agent_adapter.py` returns a failed read with `http_status: 429`
and `rate_limited: true`. ASCII delta-seconds from Retry-After are included only
when at most 86400. Missing, malformed, signed, date-form and oversized values
are omitted. Arbitrary provider response text is not copied into this result.
There is no successful read receipt and no automatic replay or sleep.

The ordinary runtime still fails the read task. The advisory does not grant
permission to retry, spend, run effects or bypass an approval. Successful page
text mentioning 429 is not classified as throttling. Redirect and URL credential
refusals remain in place.

Regression files are `test_devon_browser_fetch_boundary.py`,
`test_devon_hermes_expansion.py` and `deploy/browser-worker/worker.test.mjs`.
The latter two change tests only. The effect-free core, tenant ownership,
durable intent ordering, approval consumption and canon are unchanged.
Self-hosted `https://n8n.editforge.online` and n8n Data Tables remain canonical;
this patch writes no workflow, table, credential or deployment setting.

## Validation

Focused parent checks: 986 passed across fetch boundaries, expansion, receipt
shape and integrity; full repository Ruff passed. Independent 429 review:
15 passed, then removing the actual 429 branch caused 10 failures; restoring it
returned 15 passes. Header and status probes also passed. Two broader tests
were blocked by local AF_UNIX permissions and are not counted as passing.

The fresh closing critic used its own clean worktree at the candidate SHA:
32 Python tests and 13 Node tests passed, with 7 explicit integration skips.
Real-source negative controls failed all three missing-writer cases when the
guard was removed or approval was spent prematurely. Both failed-browser cases
failed when unknown was changed to completed. Every mutation was restored.

Full isolated validation ran on exact candidate `d5b52fe`, Python 3.12.3,
in `/opt/devon/hermes-0225-validation-20261023/repo`. Its disposable pgvector
database and anonymous volume were removed after the run. Logs are retained
under that directory's sibling `logs/`.

| Check | Result |
|---|---|
| Canonical standalone and API/passkey/Cerebras imports | Passed |
| Strict standalone, database variables unset, CI Node fixtures included | 2221 passed, 1 skipped |
| Engine without database variables | 25 passed, 2 deselected |
| Full API suite | 5887 passed, 3 skipped, 56 subtests passed |
| Migration upgrade, downgrade to 004, upgrade to head 030 | Passed |
| SQL versus Alembic schema equivalence | 884 shape lines identical |
| Ledger and knowledge tests against Alembic schema | 49 passed |
| Full repository Ruff | Passed |
| Root and Soul pip-audit | No known vulnerabilities |
| pnpm 10 audit | Exit 0; existing ignored high advisory GHSA-vfj7-8cjw-p6xm remains |
| Actual sandboxed Chromium worker | 20 passed, zero failures or skips |
| Python proxy and boundary checks | 8 passed |

Browser validation image ID is
`65697e4288b865ed6a277f0742fc762f594ff2cbe8ca68efa2e7a9be7b2c3985`.
That first validation reused the existing Docker package layer. A later clean
GitHub build in run `39962141277` failed because all three pinned Chromium
`155.0.8059.79-1~deb12u1` packages were absent from fresh Debian APT metadata.
This did not invalidate the executed sandbox tests, but it did expose an
unproven clean-build claim. The follow-up repairs the three exact package pins
in `deploy/browser-worker/Dockerfile` to `156.0.8078.47-1~deb12u1`, the candidate
from the signed bookworm-security amd64 index. The live
[Debian security tracker](https://security-tracker.debian.org/tracker/source-package/chromium)
independently confirms that version; cached package pages still named 155.
The Node base digest, sandbox flags, seccomp policy and network restrictions
are unchanged. At independent editor commit
`d3b462f4abab2f96925984d93824f795f92b3f9c`, a no-cache build installed all three
156 packages and produced image
`7c27b521037d44416cb03951f9652bda7d8f393b7c0b86b6f965ba7aa241557e`.
Its actual worker tests passed 20 with zero failures or skips, and its full
validation passed all 8 proxy tests. A fresh independent critic read the
committed diff, APT install and dpkg logs, and actual-image test receipts;
no material findings. The original failed clean build is the negative control.
The required full parity rerun on that candidate passed its strict standalone
2221 with 1 skip, engine 25 with 2 deselections, and API 5892 with 3 skips and
56 passing subtests. The API run took 572.33 seconds. Migration round trip to
head 030 and the 884-line SQL/Alembic schema equivalence passed again.
Imports, full Ruff, all CI Node fixtures, the 49 Alembic-ledger tests, root and
Soul pip-audit, and pnpm audit passed again. The same existing ignored high
pnpm advisory remains. Actual image validation again passed 20 worker and
8 proxy tests with zero skips. Logs are retained at
`/opt/devon/chromium-pin-parity-20261023/logs`; the independent no-cache build
log is `/opt/devon/chromium-pin-clean-20261023-build.log`. The fresh disposable
database container and anonymous volume were removed and both validation
worktrees were clean. Record-only documentation updates were checked locally
after these receipts were added.
Local validation used Python 3.12.3; CI's Python 3.11 jobs remain a separate
exact-head release gate. No skipped test is represented as executed.
Record-only documentation checks passed 959 receipt-shape and integrity tests;
the prepared thread receipt parsed and validated with no violations.
Main advanced to `e48fd6be8f4cc2a11e1bf1f05238777c648e1897` while this record
was prepared. Its difference from baseline is confined to the outward hook
and its tests. A separate integration worktree merged that main with the PR
candidate without conflicts; gate, ledger, fetch and expansion checks passed
877 with 1 explicit skip, under its own absolute PYTHONPATH.
The exact integration tree was `bdee6cd6d7ca3cb45c956b4f35b9e0f247d21395`.

## Deployment and rollback

Before this change, Railway API deployment
`a3a3ea35-18ec-4379-a324-1643c082cbac` was SUCCESS on baseline `faf600e5`,
updated `2026-10-23T00:59:32.229Z`. This is baseline evidence, not evidence that
this candidate is live. Exact-head CI and a post-merge deployment read-back
are required before claiming the update is deployed; those receipts belong in
the PR. No private browser is activated by this work.

Rollback can restore the prior successful API deployment artifact, or revert
the Python compatibility change through the same validation and merge gates.
Retain the independently validated Chromium pin repair in a source rollback:
restoring the unavailable 155 pin would break clean browser builds again.
There is no migration, stored-data conversion or configuration change to undo.
Reverting the Python change restores generic HTTP failure reporting; existing
approval and failed-browser behavior is unchanged.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_hermes-0225-compatibility_v1_2026-10-23-0806
DATE: 2026-10-23
DECISIONS: Tee requested DEVON be updated; adapt applicable Hermes v0.22.5 behavior to the custom runtime while preserving approvals, tenant isolation and canon.
FINDINGS: HTTP 429 lost structured evidence; the new typed failed read preserves status and bounded retry advisory without replay. Unavailable durable writers and failed browser launches already refuse safely and now have broader regression coverage. Independent real-source negative controls caught each guarded failure. A clean GitHub build exposed withdrawn Chromium 155 packages hidden by local Docker caching; all three pins move together to Debian security version 156 with sandbox policy unchanged.
OPEN: Exact-head CI and post-merge deployment read-back must be recorded in the PR; external thread-log capture is unverified because its authenticated capture door was not used.
STATUS: Compatibility candidate prepared; release remains subject to validation and deployment receipts.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
