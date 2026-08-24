---
title: DEVON Browser Terminal SDK Hotfix Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: fix/devon-browser-terminal-vercel-sdk
pull_request: 19
incident: production browser terminal could render but failed when creating its first Vercel Sandbox
---

# DEVON Browser Terminal SDK Hotfix Handover v1

## Incident

The hosted DEVON Browser Terminal shipped by PR #18 opened correctly on Tee's iPhone and authenticated successfully, but its first real command failed in production with:

```text
isolated operator sandbox failed: AttributeError: type object 'Sandbox' has no attribute 'create'
```

The command that exposed the failure was entered in the hosted DEVON terminal itself:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

This proved that the browser route, DEVON gate, mobile UI, and command POST path were live. It also proved that the Sandbox creation path had never been exercised against the deployed SDK contract.

## Root cause

`deploy/soul/requirements.txt` pinned `vercel==0.10.0`. The deployed code used an older Sandbox API shape:

```python
Sandbox.create(...)
sandbox.run_command(...)
```

The current Python Sandbox SDK used by this Vercel package line exposes module-level asynchronous functions and a Sandbox handle instead:

```python
from vercel import sandbox
from vercel.sandbox import GitSource

box = await sandbox.create_sandbox(...)
box = await sandbox.resume_sandbox(name=...)
result = await box.run_process(...)
```

The repository regression test also contained the same mistake. Its fake implemented `FakeSandbox.create` and `run_command`, so CI verified a fictional compatibility surface instead of the installed SDK contract.

## Official SDK evidence inspected

The hotfix was grounded against the current `vercel/vercel-py` source, not reconstructed from memory.

Verified source facts:

- The umbrella `vercel` Python package accepts `vercel-sandbox>=0.2.0,<0.5.0`.
- Current `vercel-sandbox` source version is `0.4.0`.
- `vercel.sandbox` exposes module-level `create_sandbox(...)` and `resume_sandbox(...)`.
- Current official examples use `GitSource(url=..., revision=...)` for Git-backed Sandboxes.
- Current official examples execute commands with `await box.run_process(...)`.
- Persistent Sandbox examples stop and later resume the named Sandbox.

## Artifacts modified

### 1. `deploy/soul/requirements.txt`

Now pins the exact Sandbox API contract implemented by this deployment:

```text
vercel==0.10.0
vercel-sandbox==0.4.0
```

### 2. `deploy/soul/app.py`

Replaced the removed API with the shipped module API:

- `vercel_sandbox.create_sandbox(...)`
- `vercel_sandbox.resume_sandbox(...)`
- `GitSource(...)`
- `await sandbox.run_process(..., capture_output=True)`
- `await sandbox.stop()` between browser commands

Workspace continuity now uses the identity of a named persistent Vercel Sandbox. The API returns `workspace_id` and also returns the same value in the old `snapshot_id` field so a browser page cached before this hotfix remains compatible.

An import-time SDK contract guard now verifies that `create_sandbox` and `resume_sandbox` are callable. If those entry points drift again, the Vercel preview fails instead of silently shipping another broken command path.

The DEVON Soul boundary remains unchanged. `deploy/soul/main.py` remains the read-only phone lane. The hosted wrapper does not import local `subprocess`, does not execute commands on the Vercel function host, does not inject production secrets into the microVM, and does not inject a GitHub write credential.

### 3. `test_deploy_soul_operator.py`

The test double now mirrors the shipped asynchronous module API and intentionally does not provide the removed methods.

New regression assertions cover:

- authenticated and anonymous route behavior
- fresh Git-backed persistent Sandbox creation
- named Sandbox resume on the next command
- `run_process(..., capture_output=True)`
- stop between commands for persistence
- no production secret/token/password injection
- workspace path confinement
- absence of `Sandbox.create` and `.run_command(` from deployed source
- presence of `create_sandbox`, `resume_sandbox`, and `.run_process(`
- exact deployed `vercel-sandbox==0.4.0` pin

### 4. `docs/devon/SYS_OPS_devon-browser-terminal-sdk-hotfix-handover_v1_2026-08-24.md`

This file. It records the incident, root cause, modified artifacts, evidence, and remaining production smoke test.

## Artifact inspected but not modified

`deploy/soul/terminal.html` was opened and reviewed during the incident. It still stores the browser continuity token under the historical `snapshot` variable and sends `snapshot_id`. The server hotfix deliberately accepts that field as an alias for `workspace_id`, so the deployed UI does not need a coordinated frontend change for this repair.

## Verification evidence

### GitHub CI, code head `7b31b3e815b20ee83c55fcf70887f6e4c5601c77`

Run: `32708387921`

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- Full PostgreSQL 16 + pgvector suite: PASS
- Pytest result: `614 passed, 4 warnings in 51.63s`
- Ruff: `All checks passed!`

The warnings are existing Starlette/FastAPI deprecation warnings and did not fail the suite.

### Vercel preview, same code head

Deployment: `dpl_Bo3u5dDReDYtbrmTpFRXKH3SoLNp`

- State: READY
- Branch: `fix/devon-browser-terminal-vercel-sdk`
- Commit: `7b31b3e815b20ee83c55fcf70887f6e4c5601c77`
- `/terminal` successfully imports and renders the DEVON Operator door.
- Preview returns 503 because `CONSOLE_TOKEN` is not configured in Preview. This is expected and was not bypassed.
- The import-time SDK guard is active in that deployment, so preview readiness now proves the required module-level Sandbox creation/resume functions exist in the installed deployment SDK.

## Current status

PR #19 is the production hotfix. It is review-ready but is not authorized to merge merely because this handover exists.

Production remains on the PR #18 implementation until PR #19 is explicitly merged.

## Post-merge acceptance

After PR #19 is merged and the exact merge commit reaches READY in production:

1. Open `https://devon-soul.vercel.app/terminal`.
2. Use the existing DEVON console gate as normal.
3. Run a harmless command such as `pwd` or `git status` first.
4. Confirm a workspace id is returned and the next command resumes the same workspace.
5. Re-run the command that originally exposed the incident if still desired.
6. If a new live-service error appears, treat that output as authoritative and repair the next boundary before declaring the terminal fully accepted.

No local Terminal app, Crosh, Linux mode, Python, pnpm, Docker, or device-local shell is required.