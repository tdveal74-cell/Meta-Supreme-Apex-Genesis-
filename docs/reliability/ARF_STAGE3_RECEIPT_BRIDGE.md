# ARF Stage 3: deterministic receipt bridge (review candidate)

This slice introduces `RuntimeDeclaredChecksGateReader`, an owner-scoped,
read-only adapter for the existing `agent_verifications` and
`agent_tool_results` stores. The request-protection follow-up adds one
security-accounting table and migration, documented in
[ARF_SHADOW_RATE_LIMIT.md](ARF_SHADOW_RATE_LIMIT.md). It adds no background
job, automation or production configuration. The only new HTTP route remains
the default-disabled shadow readback described below.

The adapter attests **only `requirement_evidence`**, and only when a
current, completed task has nonempty declared checks, its exact current
verification receipt is intact, every required captured tool result belongs
to the same tenant, task and generation, and all checkers recompute to VERIFIED.
The immutable receipt's reported checks and evidence IDs must agree with
those recomputed results. Any discrepancy fails closed.

This does not establish task objective quality, source provenance, deployed
artifact truth, TSWS creative canon, TQO style or Script Doctor scoring,
reviewer acceptance, publication, model accuracy, or paid-render permission.
It can never grant an approval, execute an effect, or close a task. In particular
no new policy rule may reinterpret a deterministic-check receipt as a human
review or media verification. Unavailable evidence produces no affirmative gate.

Next: independently verify the provenance/independence of dedicated project
QC readers; use the existing user-scoped route with a guarded integration,
and add real PostgreSQL integration tests. Do not enable or promote ARF just
because these pure tests pass. GitHub PR and deploy require separate release
readback and human authorization under the repository's existing rules.

## Opt-in API readback (still shadow-only)

`app/api/v1/arf_shadow.py` adds `GET
/api/v1/agent-tasks/{task_id}/reliability-shadow`, registered through the
existing v1 router. The handler requires the existing authenticated user,
looks up only the user's owned task, fixes `domain=devon` and
`workflow_stage=build`, and returns a recommendation rather than changing
task state. Authenticated requests update only the shared request-budget
accounting before evidence lookup. `ARF_SHADOW_READ_ENABLED` defaults to off, and no environment
variable is changed by this patch. No route may accept caller-supplied review
or approval credentials. The `approval_db=None` posture deliberately does
not attest any WRITE or HIGH_IMPACT approval, even when the runtime performed
one. That remains held pending an audited separate-backend approval reader.

### Pre-activation review

Test the API with a real authenticated principal and separate tenant in a
nonproduction environment, verify rate limits, confirm no sensitive output
is exposed, and run the production-equivalent PostgreSQL and CI suites.
Do not activate via configuration until the operator approves this read-only
exposure and live source isolation is demonstrated. It does not implement
production enforcement or any creative-project-specific validator.

### Consistent database evidence (2026-10-21 repair candidate)

A PostgreSQL READ COMMITTED transaction can see one task version and later
intent or receipt rows from a newer version. The shadow reader now opens a
**fresh, dedicated** AsyncSession rather than reusing the session that read
the authenticated task. collect_evidence requires a session with no active
transaction and issues SET TRANSACTION ISOLATION LEVEL REPEATABLE READ,
READ ONLY before its first row query. Its task, intent, receipt and declared
gate reads share the resulting database snapshot. Reused transactions fail
closed. The route continues to set approval_db=None; independently hosted
DEVON approval records still lack an atomic cross-database snapshot and must
not be represented as verified approvals by this route.

Separately, the optional, unactivated recovery-history writer obtains a
transaction-scoped PostgreSQL advisory lock keyed by authenticated owner and
root task **before** validating lineage. It holds that lock across the insert
until the caller commits or rolls back. The caller must use transactionally
consistent READ COMMITTED history reads and must not commit or release the
transaction between validation and insertion. No history migration was
registered, and no writer was connected to production.

The regression suite includes local PostgreSQL interleavings with separate
connections, asserting a typed conflict for a competing lineage writer and
consistent evidence when a second connection commits a new effect during a
shadow read. Those integration cases run **only** with an explicitly supplied
disposable ARF_ISOLATED_TEST_DATABASE_URL and never use production credentials.
They do not certify separate approval backends, human review, publication or
the protected domain-specific gates.
