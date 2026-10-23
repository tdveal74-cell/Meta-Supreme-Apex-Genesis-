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
Local validation used Python 3.12.3; CI's Python 3.11 jobs remain a separate
exact-head release gate. No skipped test is represented as executed.
Record-only documentation checks passed 959 receipt-shape and integrity tests;
the prepared thread receipt parsed and validated with no violations.

## Deployment and rollback

Before this change, Railway API deployment
`a3a3ea35-18ec-4379-a324-1643c082cbac` was SUCCESS on baseline `faf600e5`,
updated `2026-10-23T00:59:32.229Z`. This is baseline evidence, not evidence that
this candidate is live. Exact-head CI and a post-merge deployment read-back
are required before claiming the update is deployed; those receipts belong in
the PR. No private browser is activated by this work.

Rollback is a revert of this compatibility PR through the same validation and
merge gates. There is no migration, stored-data conversion or configuration
change to undo. Reverting restores generic HTTP failure reporting; existing
approval and failed-browser behavior is unchanged.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_hermes-0225-compatibility_v1_2026-10-23-0806
DATE: 2026-10-23
DECISIONS: Tee requested DEVON be updated; adapt applicable Hermes v0.22.5 behavior to the custom runtime while preserving approvals, tenant isolation and canon.
FINDINGS: HTTP 429 lost structured evidence; the new typed failed read preserves status and bounded retry advisory without replay. Unavailable durable writers and failed browser launches already refuse safely and now have broader regression coverage. Independent real-source negative controls caught each guarded failure.
OPEN: Exact-head CI and post-merge deployment read-back must be recorded in the PR; external thread-log capture is unverified because its authenticated capture door was not used.
STATUS: Compatibility candidate prepared; release remains subject to validation and deployment receipts.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
