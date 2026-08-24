---
title: DEVON GitHub Capability Adapter Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: merge-authorized-pending-clean-ci
repository: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-github-adapter-clean
supersedes_pull_request: 26
predecessor_pull_request: 25
base_merge: 3dd2ee5af6ad5ea6714666f3df970922c40c22c1
purpose: Record the governed GitHub capability adapter, its security boundaries, clean rebase after PR 25, artifacts, verification evidence, runtime configuration, and remaining operational limits.
---

# DEVON GitHub Capability Adapter Handover v1

## 1. Starting state

PR #25, `feat(devon): durable Agent Tasks and governed Operator adapter`, was
explicitly authorized by Tee and merged into `main` on 2026-08-24.

Merge commit:

```text
3dd2ee5af6ad5ea6714666f3df970922c40c22c1
```

The first GitHub adapter branch was opened as PR #26. During final security
review, the shared runtime approval boundary was hardened and the same repair
was backported into PR #25 before PR #25 merged. That made the original stacked
branch ancestry diverge from the newly merged `main` and GitHub reported PR #26
as not mergeable.

No force merge was used. The GitHub-only delta was rebuilt on this clean branch
from the verified PR #25 merge commit.

## 2. Architecture

```text
Tee
 |
 v
Authenticated Agent Tasks API
 |
 v
DEVON Agent Runtime
 plan / act / observe
 |
 +---------------------------+
 |                           |
 v                           v
READ GitHub tools       Effectful GitHub tools
 automatic              DEVON approval required
 |                           |
 +-------------+-------------+
               |
               v
        GitHub Capability Adapter
               |
               v
        Allowlisted GitHub REST client
               |
               v
        GitHub repository scope
```

`services/devon` remains execution-free. Network effects live in
`services/github`, outside DEVON core.

## 3. Runtime configuration

Required for live GitHub capability execution:

```text
DEVON_GITHUB_TOKEN=<purpose-made GitHub token>
DEVON_GITHUB_ALLOWED_REPOS=owner/repo[,owner/repo...]
DEVON_GITHUB_API_URL=https://api.github.com   # optional
```

Security rules:

- only `DEVON_GITHUB_TOKEN` is consulted;
- generic `GITHUB_TOKEN` is deliberately not used as fallback;
- the token is never accepted as a task argument;
- the token is never returned in the tool catalog;
- repository access fails closed unless the exact `owner/name` is allowlisted;
- redirects are not followed by the REST client;
- file reads and writes are bounded to 1 MB;
- file reads require valid base64 and strict UTF-8 text;
- Git refs are validated against dangerous Git ref sequences;
- PR numbers must be positive integers;
- commit SHA inputs must be full 40- or 64-character hexadecimal object IDs.

## 4. Tool surface

### Automatic READ tools

```text
github.repo_status
github.read_file
github.pull_request
```

These execute only inside an allowlisted repository.

### Approval-gated WRITE tools

```text
github.create_branch
github.create_pull_request
```

### Approval-gated HIGH_IMPACT tools

```text
github.write_file
github.merge_pull_request
```

A pull-request merge additionally requires `expected_head_sha`. This pins the
human ruling to one exact code revision and prevents an approval from floating
to a later changed head.

## 5. Approval binding

The adapter uses the shared hardened runtime approval verifier merged through
PR #25.

For every effectful GitHub tool, the capability boundary independently
recomputes the SHA-256 binding from:

```text
task_id
step_id
tool_name
exact effect arguments
```

It then verifies all of the following before network execution:

1. approval metadata is present and structurally valid;
2. the authoritative DEVON approval request still exists;
3. the request state is approved;
4. the request was created by the DEVON Agent Runtime;
5. metadata tool name matches the capability being executed;
6. the caller-supplied binding matches the independently recomputed binding;
7. the approval consequence contains the exact binding marker.

A caller cannot reuse an approved request while changing a branch name, file
write, PR target, merge SHA, or other effect argument.

## 6. Artifacts created in this layer

```text
services/github/__init__.py
services/github/client.py
services/github/agent_adapter.py
test_devon_github_agent_adapter.py
docs/devon/SYS_OPS_devon-github-capability-adapter-handover_v1_2026-08-24.md
```

## 7. Artifacts modified in this layer

```text
app/services/agent_tasks.py
```

The application coordinator now registers `GitHubCapabilityAdapter` beside the
existing Operator adapter and reports GitHub configured state plus the explicit
allowlist without exposing credentials.

The shared approval hardening files are already part of merged PR #25 and are
therefore not duplicated in this clean delta:

```text
services/agent_runtime/governance.py
services/agent_runtime/runtime.py
services/operator/agent_adapter.py
services/operator/bridge.py
test_devon_agent_tasks_api.py
```

## 8. Regression coverage

The clean branch carries network-isolated tests using `httpx.MockTransport`.
Coverage includes:

1. an allowlisted file read executes without human approval;
2. the GitHub token is used internally and is absent from task output/catalog;
3. a non-allowlisted repository fails closed before network access;
4. PR merge is classified high-impact and stops for DEVON approval;
5. approved PR merge sends the exact expected head SHA to GitHub;
6. an approved binding cannot be reused after effect arguments are changed;
7. the client refuses generic `GITHUB_TOKEN` fallback;
8. repository identities must be exact allowlisted `owner/name` values.

The original PR #26 code head was independently verified before the clean
rebuild:

```text
head: 30e9923a4859e1596bf5eff927c19605282eb6f2
GitHub Actions run: 32765920731
Standalone offline flagship: PASS
Engine + cadence/security: PASS
PostgreSQL 16 + pgvector API suite: PASS
pytest: 650 passed, 4 warnings in 62.72s
Ruff: All checks passed!
```

The four warnings were existing Starlette/FastAPI deprecation warnings and did
not fail the suite.

This clean rebase must also pass the repository CI at its own exact head before
merge. No force merge or bypass is authorized.

## 9. Limits that remain true

### Approval storage

The current default DEVON ApprovalQueue remains process-local. Agent task data
is PostgreSQL durable, but an approval already waiting for a ruling is not fully
restart-safe until approval storage is shared/durable.

### External effect atomicity

GitHub effects are not crash-atomic exactly once across the interval between a
remote effect succeeding and the resulting task snapshot commit. Adapter-level
idempotency/receipts are still needed for that property.

### Repository allowlist is not GitHub permission isolation

The DEVON allowlist limits which repository names the adapter will call. The
underlying GitHub token should still be created with least privilege because
GitHub itself ultimately enforces the token's remote permissions.

### No arbitrary GitHub API proxy

This layer exposes only the named methods implemented in the capability client.
It is not a generic user-supplied URL or arbitrary REST request executor.

## 10. Next recommended layer

After this GitHub adapter is merged and stable, the next reliability layer is:

```text
durable/shared DEVON approval storage
```

That should precede unattended multi-worker/browser expansion so tasks waiting
for a human ruling survive process restart and all workers consult one approval
authority.

## 11. Merge status

Tee explicitly authorized merge on 2026-08-24.

This branch is eligible for merge only after its exact-head CI is green. The
merge must use the exact expected head SHA. After merge, `main` must be read back
and the original conflicted PR #26 should be closed as superseded rather than
force-merged.
