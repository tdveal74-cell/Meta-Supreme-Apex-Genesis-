---
title: DEVON Browser Terminal Main Branch Hotfix Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: fix/devon-browser-terminal-main-branch
pull_request: 22
---

# DEVON Browser Terminal Main Branch Hotfix Handover v1

## Purpose

Record the final branch-state repair discovered during authenticated production acceptance of the hosted DEVON Browser Terminal.

## Source of truth opened

The repair was grounded against the merged Meta repository implementation at `deploy/soul/app.py` on `main`. The file confirmed that DEVON verified the Git worktree but did not attach a source-provided detached HEAD checkout to a local branch.

## Production evidence

Authenticated browser-terminal acceptance after PR #21 showed:

```text
pwd
/vercel/Meta-Supreme-Apex-Genesis-
exit 0

git status
Not currently on any branch.
nothing to commit, working tree clean
exit 0
```

This proved that the Git worktree repair succeeded, but Vercel's GitSource checkout could still arrive at detached HEAD.

## Root cause

`_repo_root()` correctly verified or bootstrapped a Meta Git worktree, but the command path moved directly from verified worktree resolution to user-command execution. No branch-state normalization existed between those steps.

The UI identified `main` as the target ref while the actual live Git worktree was detached.

## Repair

`deploy/soul/app.py` now adds:

- `_git_branch()` using `git symbolic-ref --quiet --short HEAD`.
- `_ensure_main_branch()` between verified repo discovery and user-command execution.
- Existing local branches are preserved.
- A clean detached worktree resolves `origin/main`, creates or switches to local tracking `main`, and verifies the result.
- A dirty detached worktree is preserved as detached instead of being reset, switched, or otherwise risking user edits.
- Command receipts now include `branch` and `branch_attached`.

This repair does not add GitHub write credentials. It only changes branch state inside the isolated persistent Sandbox worktree.

## Safety properties

The branch repair deliberately does not use `reset --hard`, `checkout -f`, `switch -C`, or any command that can silently discard user edits.

When detached HEAD has uncommitted changes, DEVON returns branch state `detached` and does not switch branches.

When detached HEAD is clean, DEVON may fetch the public `origin/main` ref if required and then attach local `main`.

DEVON Soul remains read-only. Operator execution remains in the isolated Vercel Sandbox. Production secrets and GitHub write credentials are not injected.

## Regression coverage

`test_deploy_soul_operator.py` now covers:

- non-Git Sandbox cwd bootstrap into a verified Meta worktree,
- resumed verified worktree reuse,
- clean detached worktree attachment to local tracking `main`,
- dirty detached worktree preservation without switch/reset,
- stale browser-path compatibility aliases,
- worktree confinement,
- no production secret injection,
- no subprocess use by the hosted wrapper,
- pinned Vercel Sandbox SDK contract.

## Verification evidence before this handover commit

Code head: `9b40093cd71e5cca3a3f507620fdd83a29983fb3`

Vercel preview:

- deployment `dpl_6g52GJL6oBm2mtBCurirV2UEXkf2`
- state: READY
- exact commit: `9b40093cd71e5cca3a3f507620fdd83a29983fb3`

GitHub Actions run `32735232932`:

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- PostgreSQL 16 + pgvector suite: `624 passed, 4 warnings in 55.53s`
- Ruff: `All checks passed!`

## Production acceptance after merge

Refresh the existing hosted terminal and run:

```text
git status
```

Expected result for the current clean production workspace:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

The command should exit `0`.

If a detached workspace contains user edits, DEVON must preserve them and must not silently switch or reset the worktree.

## Merge gate

PR #22 is not production until the final docs-inclusive head also passes GitHub CI and has a READY Vercel preview. Merge requires explicit operator authorization.
