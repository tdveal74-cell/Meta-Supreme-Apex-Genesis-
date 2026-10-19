# Runtime evidence and skill revision gates

Supersedes the remaining-implementation list in
`docs/AGENT_EVALUATION_BASELINE.md` for code implementation. It does not
supersede live provider measurement requirements.

The authenticated task coordinator records owner-scoped tool outputs outside
conversation snapshots and emits immutable declared-check receipts. Completion
state remains separate from verification. Output hashes, supported JSON
schemas, adapter success and captured artifact properties have deterministic
checkers. Missing checks and evidence fail closed. Evidence commits with the
lease-fenced result; rollback clears current verification without rewriting
prior receipts.

Route traces retain versions, frozen input hashes, stopping reasons, evidence,
latency and execution budget. Aggregation keeps denominators and excludes
unmeasured routes. Calibration uses owned server receipts with at least two
named evaluators and reports false approvals and shared errors separately from
agreement. No model votes can override a runtime verdict.

Skill edits and rollbacks append immutable exact-byte versions with provenance.
Evaluation attempts retain failed and unsupported candidates as well as passing
ones. Evolved promotion requires human approval, exact owned candidate/task
binding, a fresh passing registered-runner receipt and the expected active
version. The bundled runner is a narrow four-case public receipt-policy contract
suite. It does not evaluate general natural-language skills or establish a
fresh final holdout. Existing lost legacy versions cannot be recovered.

See `docs/AGENT_RUNTIME_EVIDENCE.md` for routes, retention, checker limits and
operational use. Independent critics reproduced and parent fixes corrected
context-hash aliasing and malformed-field server errors. Review also found
failed evaluations were not retained; they now are. Pure negative controls
caught weakened integer checking and unconditional skill success.

## Validation and deployment state

- Initial database integration: 13 passed; expanded integration: 22 passed.
- Migration upgrade/downgrade/upgrade and SQL/Alembic shape parity passed at
  `029_runtime_evidence` across 878 shape lines.
- Independent pure trust-boundary checks cover stale leases, forged references,
  corrupted bytes, owner/task query binding and rollback verdict clearing.
- Final full Python suite: 4,964 passed, 1 skipped in 421.27 seconds, exit 0.
  Validation checkout tree `1cc6dc1002cbddee8dcdcad75c9c0b2a53729b9b`
  exactly matched implementation commit `f4a7109` before this receipt update.
- Canonical standalone CI commands passed: 1,735 Python tests, 1 skipped, plus
  all selected Node syntax and behavior commands. Engine/security: 25 passed.
- Container imports, pinned Ruff, web typecheck/build, all ten selected web
  check commands and 960 documentation/receipt/reconciliation checks passed.
- Root and soul Python audits found no known vulnerabilities. pnpm 10 audit
  exited zero under the existing policy (one high advisory already ignored).
- Alembic-built database integration subset: 68 passed in 41.13 seconds, exit 0,
  covering ledger, knowledge and the new runtime/skill APIs.
- Final independent review: 68 pure checks passed; no further confirmed defect.
- Hosted CI and deployment read-back are pending publication. This receipt
  does not claim the follow-up is live; inspect the release PR's exact-head
  workflow and commit deployment statuses for subsequent release evidence.

## Operational items that remain unverified

No paid model benchmark or production authenticated runtime task has been run
by this arc. Live route behavior, real cost, fresh final holdout performance and
judge independence need their own receipts. The code infrastructure does not
convert those missing measurements into favorable results. No orchestration or
compaction treatment is enabled by this change.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: Runtime evidence and immutable skill gates
DATE: 2026-10-19
DECISIONS: keep task completion distinct from declared-check verification; preserve external-effect human gates; retain failed evaluations; require exact owned fresh evidence for evolved promotion
FINDINGS: context omitted from route task hashes and malformed checker types were reproduced and fixed; failed skill attempts previously disappeared before insertion and now persist; public fixture agreement is not semantic truth or unseen holdout quality
OPEN: hosted CI and release read-back pending publication; production authenticated runtime smoke, live route benchmark and fresh final skill holdout remain unverified
STATUS: implementation, independent review and full local validation complete; hosted release gates pending
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
