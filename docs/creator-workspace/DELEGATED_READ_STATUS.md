# Creator Workspace delegated metadata reader

Date: 2026-10-21
Release posture: default disabled. A merged implementation is not an active grant or a successful production read.

## Purpose and authority

DEVON remains the existing second brain. Creator Workspace is an editorial working area, not another knowledge database. This integration discovers existing DEVON project metadata without transferring a personal browser JWT, passkey, recovery key or service-wide credential. It does not assert that DEVON's PostgreSQL knowledge inventory mirrors the authoritative Drive tree. An empty inventory is reported, never repaired by silently copying Drive or inventing projects.

Tee authorized the recommended implementation decisions and production integration in the current conversation. Content publication, paid generation, source promotion, Graphify memory writes and unrelated production changes remain excluded.

## Separate machine principal

The API accepts a dedicated CreatorRead authorization scheme only on three GET routes under `/api/v1/creator-workspace`. This principal is not CurrentUser and is not accepted by ordinary user routes. A personal JWT is not accepted as this grant. Existing passkeys and user-authentication dependencies are unchanged.

The operator-provisioned configuration is `DEVON_CREATOR_READ_GRANT`. The credential is generated from 256 random bits and prefixed `cwread_`. Only its SHA-256 digest reaches the server configuration. The raw credential belongs in a root-private client service file outside the editorial workspace, never a command argument, source repository, log or chat. No production credential is included in this change. Fixture tokens are synthetic.

Exact grant fields: `enabled`, `grant_id`, `scope`, `key_sha256`, `not_before`, `expires_at`, `owner_id`, `owner_email`, `projects`. Missing, unknown or duplicate fields are refused. So are truthy non-booleans, malformed UUIDs, wildcard or duplicate cross-brand project assignments, naive or overflowing timestamps and grants lasting more than 30 days. The digest comparison is constant-time. Disabling or removing a grant takes effect when that server configuration is running; it is not a claim of instantaneous revocation in an older replica.

An inventory grant resolves one explicitly configured active account email. Ambiguous matches refuse. It lists only that account's project IDs, names and states, cannot retrieve knowledge metadata, and cannot create an account or project. An active grant instead pins the verified owner UUID and explicit per-brand project UUIDs, has no email fallback and cannot list account-wide inventory. Provisioning is a privileged operator action, not an unauthenticated enrollment endpoint.

## Read boundaries

- `GET /status` returns the delegated principal, owner, grant ID, expiry and scope, never the credential.
- `GET /projects` is inventory-only, bounded to 50 rows per request.
- `GET /{brand}/knowledge?project_id=<uuid>` is active-grant-only, bounded to 20 ready-item metadata rows per request.

Every request begins a fresh PostgreSQL REPEATABLE READ, READ ONLY transaction with a three-second statement timeout. A previously active session is refused rather than rolled back. Queries require an active owner, a nondeleted owned project and correctly owned ready knowledge items. A misprovisioned foreign project ID in the allowlist still cannot defeat database ownership. Unknown and unauthorized projects receive the same refusal.

Returned metadata uses an explicit field allowlist. Raw content and arbitrary metadata are omitted. Source references must be HTTPS, omit embedded credentials and have query strings/fragments removed. No source URL is fetched. Results remain metadata candidates, not verified claims, approved canon or publication authority. All responses and refusals set no-store. No schema migration, provider call, new database or scheduled executor is introduced.

## Client

`tools/creator_workspace_reader.py` is a standard-library GET-only client pinned to the verified DEVON API origin. It rejects redirects, non-JSON or oversized responses, duplicate IDs, mismatched grant/owner/brand/project scope, expired grants and any returned effect-authorization flag. One foreign item refuses the entire response. Private extra fields are not returned.

Client configuration defaults to `/etc/creator-workspace/devon-read-client.json`; the separate credential defaults to `/etc/creator-workspace/devon-read.key`. The credential must be a regular, single-link file owned by the current service user, inaccessible to group/other, without symlinks in its path. Config cannot embed a credential or change the API origin. Expiry is checked again before every request. The client never uses a personal JWT as fallback, stores a knowledge cache or invokes an AI model.

Commands are `status`, `inventory`, and `metadata --brand <brand> --project-id <verified-uuid>`. A successful metadata call still returns `source_contents_fetched=false`, `source_claims_verified=false` and `publishing_authorized=false`.

## Executed validation

Implementation followed failing tests. Nineteen initial grant tests failed before the module existed; six real PostgreSQL/API tests failed with unregistered routes before implementation. Later negative cases reproduced and fixed an extreme-offset refusal and expiry rechecking before each client request.

The focused suite now has 64 tests: 22 grant tests, 11 real PostgreSQL/API tests and 31 offline client tests. It passes with synthetic fixtures and mock providers. The API suite proves actual PostgreSQL read-only enforcement by attempting an UPDATE and checking that the record did not change. It also checks inactive owners, deleted projects, reused transactions and bounded pagination.

A separate checkout and process tested four deliberate source mutations: removing digest checking, removing the brand guard, making the database transaction writable, and removing owner predicates. Each mutation caused the intended test to fail. After restoring the exact source, all 64 focused tests passed again. Candidate files were hash-checked unchanged throughout.

A small local-model static review was also attempted. Its unsupported vulnerability claims were not accepted as findings or certification. Timezone equivalence, correctly shaped wrong keys, foreign-project behavior and read-only semantics were settled by executed checks. The mutation checks are measured adversarial evidence, not a claim of independent human security certification.

Full-repository test output, source hashes, migration round-trip, import contracts and audit results are recorded separately for this revision. The initial full run had three unrelated subprocess failures because the isolated PATH did not contain the virtualenv `python`. Restoring the expected PATH fixed all three without changing tests or guards. Python dependency audits found no known vulnerabilities. The existing pnpm major-10 audit policy passes with one pre-existing ignored high advisory, `GHSA-vfj7-8cjw-p6xm`; this change adds no exception or dependency. An inadvertent pnpm major-12 audit was not treated as the project's CI environment.

All validation databases are disposable, resource-limited, loopback-only and contain synthetic data. Production records and credentials are not used by the tests. Native GitHub checks must pass on the proposed head before merge; deployment and live-grant readback remain separate acceptance steps.

## Activation and rollback

Before activation, verify the deployed revision, generate a dedicated protected client credential, verify the configured active account, inspect an inventory-only response, and narrow it to existing explicitly mapped brand projects. Do not activate an empty or inferred project map. Then verify positive scoped metadata reads, wrong-brand/unapproved-project refusal, ordinary-user-route refusal and mutation refusal. Record only nonsecret evidence.

The API grant enables metadata discovery, not semantic body retrieval or cross-brand sharing. Original-source verification and human content approval remain required. Existing Graphify PR #372 keeps its own non-writing and deployment gates; no hint is overridden here.

Rollback disables/removes the grant, verifies refusal from the running deployment, and removes the dedicated client credential. It does not alter DEVON's personal sessions, passkeys, original knowledge or source canon. Client and server configuration must expire together; no unverified automatic renewal is included.
