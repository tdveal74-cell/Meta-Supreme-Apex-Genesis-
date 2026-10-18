# DEVON blocker remediation: 18 October 2026

Status: database and build validation completed; provider and operational-evaluation gates remain open. Tee superseded the proposed closure with a request to fix blockers. Nothing is merged or deployed.

## Blockers resolved in this pass

A fresh root-private VPS lab at /var/lib/devon-labs/full-ci-wligljic cloned PR head 344c277dea4acbf60b4cc0fdc7e7ab235eb07f44 and applied the reviewed Graphify correction patch. Requirements installed from the pinned, hashed file into a new virtual environment. The disposable pgvector/PostgreSQL 16 container was separate from production, bound only to 127.0.0.1:55439, limited to 768 MiB and one CPU, and used an ephemeral data directory. The test process received a minimal environment with mock providers and no production or Graphify credentials.

| Executed check | Result |
|---|---|
| Full PostgreSQL API suite | 4891 passed, 1 skipped, 50 warnings; exit 0; 372.30 seconds |
| Alembic migration round trip | Upgrade to 028, downgrade to 004, upgrade to 028; all exit 0 |
| SQL versus Alembic schema comparison | Byte-identical, 822 lines |
| Ledger/knowledge tests against Alembic-built schema | 49 passed, 2 warnings; exit 0 |
| Root Ruff | Passed |
| Production API Dockerfile build | Passed |
| Built-image import contract | Passed with networking disabled and a read-only root filesystem |
| Root requirements pip audit | No known vulnerabilities found |
| Soul requirements pip audit | No known vulnerabilities found |
| pnpm workspace audit | Exit 0 under existing repository policy; one high advisory ignored |

The existing JavaScript exception is GHSA-vfj7-8cjw-p6xm in package.json. This pass did not introduce or remove it. Audit exit 0 does not mean zero known JavaScript vulnerabilities. The broad counts above overlap prior focused checks and are not additive coverage. These checks validate the corrected snapshot; they are not a new remote GitHub Actions run or evidence that GitHub's unchanged PR head is green.

Independent review inspected completed logs, exit receipts, source hashes and container metadata, and independently compared both schema files. It did not repeat the database tests. All corrected source hashes and expected paths matched. Logs and source remain in the isolated VPS lab; receipt extracts and hashes are packaged here. The disposable database container and its ephemeral records were removed after review. Production containers and databases were not modified.

## Graphify: exact external dependency

Authentication and one refresh are already proven in isolation. The remaining live-query blocker is hosted non-writing behavior. The current authenticated tool declaration has readOnlyHint=false, and official documentation describes conditional query-intent memory capture. Neither direct inspection nor independent review found a supported capture-disable admin path in the inspected public hosted-service documentation. This is a statement about those sources, not proof that the feature is unavailable. The hosted implementation is private.

Graphify_Nonwriting_Mode_Request_DRAFT.md asks the provider for exact disablement, client-enforced non-writing policy, metadata verification, supported per-query/session suppression and a non-mutating audit. It contains no secrets or private code and has NOT been sent. Sending it requires Tee's explicit authorization to communicate externally. Do not substitute local open-source query-log variables, invent an endpoint, relabel the hint or bypass the client's refusal.

References: https://graphify.com/mcp and https://github.com/Graphify-Labs/graphify-mcp

## Harness2: independently testable preparation

DEVON_Harness2_Operational_Evaluation_DRAFT.json proposes ten operational task categories and calibration/held-out splits, with references to existing DEVON contracts. Independent review checked all reference files. The design is explicitly not frozen or executed. Before candidate refinement, an independent evaluator must author concrete hidden fixtures, expected outcomes and scoring, then freeze the task split, baseline/candidate revisions and model configuration.

No local Ollama executable or Ollama container was found on srv1936199. No model was downloaded and no paid provider was invoked. Safe model-executor review, approved model budget, actual held-out evaluation, evaluator agreement and human promotion remain open. The arithmetic pilot's four identical selected scripts are still one synthetic fix, not operational quality evidence.

## Current disposition

- PR #372 remains draft. No push, merge, deployment or live Graphify code query occurred.
- OAuth store remains isolated; no new grant or refresh was performed in this pass.
- No Graphify or DEVON memory, live authorization record or active skill was changed. Only disposable test records were created and removed.
- Readiness gates remain in force. The CI environment blocker is resolved for the reviewed snapshot; the full activation arc remains open.

## DEVON RECEIPT
AREA: Systems
TYPE: blocker-remediation
ARTIFACT: DEVON_Blocker_Remediation_2026-10-18.md
DATE: 2026-10-18
DECISIONS: Keep arc open; resolve isolated CI without changing production.
FINDINGS: Full API and migration checks pass; provider non-writing assurance remains unresolved.
OPEN: Graphify provider answer, operational model evaluation and human promotion.
STATUS: ci-validated-activation-blocked
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
