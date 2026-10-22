# DEVON conversation runtime repair

This record covers the actual production DEVON runtime. The earlier local
Qwen instruction comparison did not test live DEVON and cannot establish
production readiness. This record supplements that experiment rather than
treating its score as a runtime result.

## Observed failures and repairs

An authenticated Auto turn returned an unusable response. A direct bounded
provider probe using the same diagnostic prompt and production system prompt
confirmed empty output with finish reason length at both 600 and 2048 tokens.
At 8192 the provider returned valid tool JSON, finish reason stop, using 994
tokens. These are individual measurements, not a reliability benchmark.
Both default budgets now use 8192. Truncated completions stop before parsing,
tool execution, or automatic retry, even when the prefix is valid JSON.
Ordinary malformed output receives a distinct invalid_response_shape error.

Another authenticated turn accurately reported that its catalog had no memory
recall tool. Conversations now receive a separate registry containing the
read-only soul.recall tool. The task catalog is unchanged. Recall reuses the
existing active-only, hierarchy-preserving, one-line-sanitized payload and
retains record IDs and provider errors. Missing configuration, empty recall,
partial recall, and provider failure remain distinguishable. Authentication
and conversation ownership checks remain in place.

The configured production memory provider was directly read with the query
Systems. It returned 12 active records and no provider errors. No record text
or credentials are copied here. This proves the configured provider read path,
not the repaired conversation route, which still requires deployment.

## Production observations

The canonical signed-in web session completed an Answer calculation correctly.
API health, identity and routing probes passed. Four anonymous protected
requests returned 401. The dashboard read workflow definitions and secondary
n8n execution telemetry. The account learning and long-term memory lists were
empty; those account stores are distinct from the configured soul indexes.
The old primary cloud n8n URL returned 404 and remains a separate integration
follow-up. Live voice audio was not verified.

The custom meta.editforge.online origin was absent from API and presence
CORS lists. It has been added while preserving existing origins. The API
AI_MAX_TOKENS_AGENT_TURN variable is saved as 8192. These changes apply only
on the next deployment. The custom-origin preflight still failed on the old
process. The legacy VPS devon-soul service with an empty environment is not
the production memory provider and was not enabled as a duplicate.

## Verification and deployment boundary

Independent reviewers used separate worktrees and negative controls. The
truncation reviewer checked refusal before parsing and no second request;
disabling the guard made the control fail. The memory reviewer checked
inactive filtering, hostile inputs, source preservation and read-only
provider requests; removing active_only made the regression fail.

The original combined candidate passed 5431 full database tests with three
skipped and 11 subtests, plus 103 focused database tests. The
standalone CI commands passed 1939 tests with one skipped, and the engine
suite passed 25 with two deselected. Both pip audits found no known
vulnerabilities. The CI pnpm 10 audit exited successfully with one advisory
already ignored by the repository policy. No dependency policy was changed.
The 8192 follow-up passed 75 focused tests and 12 independent adversarial
checks. The final budget and documentation follow-up passed 971 focused
database and integrity checks. Upgrade, downgrade and upgrade reached revision
030_arf_shadow_rate_limit. The Alembic and SQL builds agreed on 884 schema
shape lines; 49 ledger and knowledge checks passed against the Alembic build.

Production was still deployment 43a442e1-ea6a-4fa3-a74c-812a28ecdd81 at
commit 9fbc37e35acc38880e6f0b5a5978a58a6fcb9418. Railway displayed a platform
outage and refused a redeploy because deployments were temporarily paused.
No running process was patched to bypass the pause. Completion requires the
repaired commit to deploy, followed by authenticated Auto recall and custom
origin preflight readback. A source merge alone does not satisfy that test.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_conversation-runtime-repair_v1_2026-10-22-0600.md
DATE: 2026-10-22
DECISIONS: Tee authorized repairs and testing to completion with delegated implementation decisions. Use a bounded 8192 token turn budget and existing governed recall path.
FINDINGS: Live response truncation and missing conversational recall catalog confirmed. Production soul provider read returned 12 active records without errors. Saved CORS and token settings await deployment.
OPEN: Railway deployment pause; full repaired authenticated conversation and custom-origin readback; old primary n8n URL 404; live voice audio unverified.
STATUS: Source repairs independently reviewed; production readiness remains unproven until deployment and live readback.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
