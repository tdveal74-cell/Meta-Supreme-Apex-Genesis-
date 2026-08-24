---
title: DEVON Browser Terminal Git-Root Hotfix Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: fix/devon-browser-terminal-git-root
pull_request: 21
---

# DEVON Browser Terminal Git-Root Hotfix Handover v1

## Incident

Production authentication and Sandbox creation were working after PRs #18 through #20, but the first real phone smoke test exposed a separate runtime assumption:

```text
/vercel/sandbox $ pwd
/vercel
exit 0

/vercel $ git status
fatal: not a git repository (or any of the parent directories): .git
exit 128
```

The Vercel microVM was healthy. The bug was that DEVON treated the Sandbox base cwd as if it were the Meta Git worktree.

## Root cause

`deploy/soul/app.py` used `sandbox.cwd` or a `pwd` fallback as `workspace_root`, then ran user commands there. The production runtime reported `/vercel`, which is a valid directory but not the checked-out Meta repository.

A Sandbox execution directory and a Git worktree are separate facts and must be verified independently.

## Repair

PR #21 introduces a verified Git-root resolver before every browser command.

1. Discover the Sandbox base directory from `sandbox.cwd`, with `pwd` fallback.
2. Test the base with `git rev-parse --show-toplevel`.
3. If it is not Git, perform a bounded search inside the isolated Sandbox root for `.git` and verify any candidate with Git itself.
4. If no valid worktree exists, clone public Meta `main` into `<sandbox-root>/devon-meta`.
5. Verify the clone with `git rev-parse --show-toplevel` before executing the user's command.
6. Treat stale browser paths `/vercel`, `/vercel/sandbox`, and `/home/vercel-sandbox` as compatibility aliases for the verified Meta worktree.
7. Constrain requested working directories to the verified Meta worktree.
8. Return both `workspace_root` (verified Git root) and `sandbox_root` so the two boundaries remain explicit.

## Artifacts modified

### `deploy/soul/app.py`

- adds `LEGACY_WORKSPACE_ALIASES`
- adds deterministic `META_REPO_DIRNAME = "devon-meta"`
- separates `_sandbox_root()` from `_repo_root()`
- adds `_git_toplevel()` verification
- bounded `.git` discovery inside the Sandbox only
- verified public clone fallback when no worktree exists
- maps stale browser cwd values to the verified worktree
- returns `repo_bootstrapped`, `workspace_root`, and `sandbox_root`
- preserves the DEVON Soul no-execution boundary
- preserves no production secret injection
- preserves no GitHub write credential in the Sandbox

### `test_deploy_soul_operator.py`

The fake now reproduces the production condition where `sandbox.cwd == "/vercel"` but `/vercel` is not a Git repository. Coverage verifies:

- DEVON does not execute the user command from the non-Git Sandbox cwd
- a missing worktree is bootstrapped to `/vercel/devon-meta`
- clone destination is deterministic
- the clone is verified before user execution
- the first user command runs from the verified repo root
- the persistent workspace reuses that repo on the next command
- old browser paths self-heal to the repo root
- path escape is refused
- production secrets are not passed to Sandbox creation
- the hosted wrapper still does not import Python `subprocess`

## Verification evidence before handover commit

Code head:

`ff2d4073a77e8975d6d4f65e8aed454b348c7641`

GitHub Actions run:

`32714329540`

Results:

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- PostgreSQL 16 + pgvector suite: `621 passed, 4 warnings in 54.58s`
- Ruff: `All checks passed!`

Vercel preview for the code head:

- deployment: `dpl_DNMNVKV8UVQRYhRKqgbx7qfX3cHG`
- state: READY
- route imports and serves the DEVON console gate
- preview does not receive the production `CONSOLE_TOKEN`, so authenticated Sandbox command execution is intentionally not claimed from preview

## Security boundary

This repair does not give DEVON Soul subprocess capability. The browser Operator remains a separate capability whose commands execute inside an isolated Vercel Sandbox microVM.

The Sandbox receives no production environment secrets and no GitHub write credential. The Meta fallback clone is read-only with respect to GitHub because it uses the public HTTPS repository URL without credentials.

Filesystem persistence remains local to the named Sandbox snapshot. This is not a production-host shell.

## Production acceptance after merge

Use the existing authenticated phone terminal without manually editing its stale cwd.

1. Refresh `/terminal`.
2. Run `pwd`.
3. Expected: exit 0 and a verified Meta repo path, such as `/vercel/devon-meta` or another verified source-provided worktree.
4. Run `git status`.
5. Expected: exit 0 and Git status for `tdveal74-cell/Meta-Supreme-Apex-Genesis-` on `main`.
6. Run another harmless command to confirm the same persistent workspace resumes.

Production authenticated acceptance cannot be claimed until the operator performs these commands because the production DEVON console credential is not exposed to the integration.

## Merge rule

Do not merge PR #21 until the final docs-inclusive head has a READY Vercel preview and all GitHub CI lanes pass.
