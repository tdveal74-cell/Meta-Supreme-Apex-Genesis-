---
title: DEVON Browser Terminal Remote Main Tracking Hotfix Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
repository: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: fix/devon-browser-terminal-remote-main-v2
pull_request: 23
production_base: 6bf2b48488b87c9dae0cf18e4540a3cea0b087c5
purpose: Record the authenticated production failure after PR 22, the verified root cause, the safe remote-tracking repair, discarded implementation attempts, artifacts, and verification evidence.
---

# DEVON Browser Terminal Remote Main Tracking Hotfix Handover v1

## 1. Production evidence

Authenticated production acceptance after PR #22 proved that the DEVON browser terminal could find the real Meta worktree, but branch normalization failed before the requested `git status` command ran.

The phone/browser output reported:

```text
isolated operator sandbox failed: RuntimeError:
could not attach detached worktree to main:
...
fatal: cannot set up tracking information;
starting point 'origin/main' is not a branch
```

Git also warned that the checkout was leaving many commits behind when attempting to switch away from detached HEAD. This was evidence that the worktree could contain meaningful detached history and that any repair needed a preservation step before moving HEAD.

## 2. Source of truth inspected

The canonical deployed implementation was opened from `main` before this repair:

- `deploy/soul/app.py`
- production base merge: `6bf2b48488b87c9dae0cf18e4540a3cea0b087c5`

The relevant PR #22 implementation verified `refs/remotes/origin/main`, then created local `main` with:

```text
git switch -c main --track origin/main
```

That command assumed `origin/main` was configured as a Git remote-tracking branch.

## 3. Root cause

Vercel GitSource can provide a shallow detached checkout where the commit object or ref at `refs/remotes/origin/main` is resolvable, while the repository is missing the remote fetch/tracking metadata Git needs to accept `origin/main` as a branch for `--track`.

Therefore:

- object/ref existence is not sufficient evidence of a configured remote-tracking branch;
- `git rev-parse --verify refs/remotes/origin/main` can succeed while `git switch -c main --track origin/main` still fails;
- DEVON must configure and fetch the exact tracking refspec itself before creating local `main`.

## 4. Final repair

The final implementation remains in the canonical deployment module. No compatibility wrapper is shipped.

`deploy/soul/app.py::_ensure_main_branch()` now:

1. Returns immediately when the worktree is already on a local branch.
2. Checks `git status --porcelain` while detached.
3. Preserves dirty detached workspaces without fetch, switch, reset, or checkout.
4. Resolves the detached `HEAD` commit.
5. Preserves that commit under `devon/recovery-<sha12>` if the recovery ref does not already exist.
6. Explicitly sets:

```text
remote.origin.fetch=+refs/heads/main:refs/remotes/origin/main
```

7. Explicitly fetches:

```text
git fetch --depth 1 origin +refs/heads/main:refs/remotes/origin/main
```

8. Verifies the fully qualified `refs/remotes/origin/main` ref.
9. If no local `main` exists, creates it from the fully qualified ref:

```text
git switch -c main refs/remotes/origin/main
```

10. If local `main` already exists, refuses to move a divergent branch. It only switches and fast-forwards when local `main` is an ancestor of fetched `origin/main`.
11. Explicitly configures:

```text
branch.main.remote=origin
branch.main.merge=refs/heads/main
```

12. Verifies the active local branch is actually `main` before returning success.

The repair deliberately does not use `reset --hard`, forced checkout, `switch -C`, or a destructive overwrite of a divergent local branch.

## 5. Regression repair

`test_deploy_soul_operator.py` was updated inside its existing subprocess-isolated probe.

The fake GitSource state now reproduces the exact production condition:

- verified worktree;
- detached HEAD;
- clean tree;
- `refs/remotes/origin/main` can resolve;
- no usable remote tracking metadata exists initially;
- `--track origin/main` is modeled as a failure;
- the fully qualified branch creation succeeds only after the explicit fetch refspec is configured and fetched.

The regression requires:

- explicit `remote.origin.fetch` configuration;
- explicit fully qualified fetch;
- `git switch -c main refs/remotes/origin/main`;
- no `git switch -c main --track origin/main`;
- detached HEAD recovery ref creation;
- explicit branch upstream configuration;
- dirty detached workspaces remain untouched.

Keeping this regression inside the pre-existing subprocess probe avoids mutating the parent pytest process event-loop state.

## 6. Final artifacts in PR #23

Modified:

- `deploy/soul/app.py`
- `test_deploy_soul_operator.py`

Added by this handover commit:

- `docs/devon/SYS_OPS_devon-browser-terminal-remote-main-hotfix-handover_v1_2026-08-24.md`

No `app_legacy.py` or standalone remote-main test is present in the final tree.

## 7. Discarded attempts and artifact history

For audit completeness, two non-final implementation paths were created during diagnosis and were deliberately removed or abandoned before merge.

### 7.1 Abandoned staging branch

Branch:

```text
fix/devon-browser-terminal-remote-main
```

Temporary artifact:

```text
.github/workflows/devon-remote-main-hotfix-builder.yml
```

The GitHub App did not execute the temporary branch workflow as intended. This branch is not the PR #23 source and must not be merged.

### 7.2 Removed wrapper attempt on PR #23 history

An intermediate PR #23 commit temporarily introduced:

- `deploy/soul/app_legacy.py`
- a compatibility-wrapper form of `deploy/soul/app.py`
- `test_devon_remote_main_tracking.py`

CI correctly rejected that shape because:

- the deployment-accounting guard treated `app_legacy.py` as an unguarded shipped module;
- the canonical source-contract test expected the implementation directly in `app.py`;
- the standalone test used `asyncio.run()` in the parent pytest process, closing the default event loop and causing unrelated DEVON Soul tests to fail later.

Those files are absent from the corrected PR tree. The final repair uses only the canonical deployment module and existing isolated regression suite.

## 8. Verification evidence before handover commit

Verified code head:

```text
0e10e51b053e59a653fc1947ca7aeb504661cdd7
```

Vercel preview:

```text
dpl_DJbe7cENZrA4j72Vvyf4sfFVFgjY
```

Result: `READY` on the exact code head.

GitHub Actions:

```text
run 32744486349
```

Results:

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- PostgreSQL 16 + pgvector API suite: PASS
- pytest: `625 passed, 4 warnings in 59.07s`
- Ruff: `All checks passed!`

Warnings are existing Starlette/FastAPI deprecation warnings and did not fail the suite.

## 9. Security boundary remains unchanged

This hotfix changes Git branch normalization only.

Still true:

- DEVON Soul remains read-only.
- DEVON core does not execute shell commands.
- Commands execute only inside the isolated Vercel Sandbox Operator capability.
- Production secrets are not injected into the Sandbox.
- GitHub write credentials are not connected to the Sandbox.
- Dirty detached workspaces are preserved instead of silently reset or switched.
- A divergent local `main` is not forcibly overwritten.

## 10. Final merge gate

This document is added after the code-head verification above. The documentation-inclusive PR head must independently pass GitHub CI and produce a READY Vercel preview before PR #23 can be described as merge-ready.

Production remains on PR #22 until explicit operator authorization to merge PR #23.

## 11. Production acceptance after merge

Refresh the existing DEVON browser terminal and run:

```text
git status
```

Expected clean-workspace result:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

If a workspace contains dirty detached user edits, DEVON should preserve the detached state rather than silently moving it.
