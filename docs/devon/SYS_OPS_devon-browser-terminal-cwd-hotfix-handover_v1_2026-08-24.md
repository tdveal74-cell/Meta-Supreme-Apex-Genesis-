---
title: DEVON Browser Terminal CWD Hotfix Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: fix/devon-browser-terminal-cwd
pull_request: 20
incident: production Sandbox existed but the Operator hard-coded a nonexistent /vercel/sandbox working directory
---

# DEVON Browser Terminal CWD Hotfix Handover v1

## Incident

After PR #19 fixed the Vercel Sandbox Python SDK mismatch, the hosted DEVON Browser Terminal successfully created a real isolated Sandbox. The first harmless production smoke test was:

```bash
pwd
```

The live terminal returned:

```text
bash: line 1: cd: /vercel/sandbox: No such file or directory
exit 74
```

This proved that the DEVON gate, browser UI, command API, Sandbox creation, and shell process path were live. The remaining failure was a false workspace-path assumption.

## Root cause

`deploy/soul/app.py` still defined `/vercel/sandbox` as a fixed workspace root and manually emitted `cd -- /vercel/sandbox` before every user command.

That path came from the original browser-terminal design and was not a Vercel Python Sandbox contract.

Vercel's current official Python persistent Git Sandbox example was opened during this repair. It sets the working directory with:

```python
cwd = cwd_override if cwd_override is not None else box.cwd
```

and then passes that value to `run_process(..., cwd=cwd)`. The example explicitly describes the default as the image working directory.

## Repair

### `deploy/soul/app.py`

The Operator no longer assumes a static microVM filesystem path.

For every fresh or resumed Sandbox it now:

1. Reads `sandbox.cwd` from the live SDK handle.
2. If `sandbox.cwd` is absent, executes a harmless `pwd` probe without a forced cwd.
3. Validates that the discovered root is an absolute path.
4. Treats the historical `/vercel/sandbox` browser value as an alias meaning "use the discovered workspace root".
5. Resolves relative working directories under the discovered root.
6. Refuses working directories outside that root.
7. Runs the user shell with `run_process(..., cwd=resolved_cwd, capture_output=True)` instead of prepending a manual `cd` to a guessed path.
8. Returns both the actual `cwd` and `workspace_root` to the browser.

DEVON Soul remains read-only. Commands remain inside the Vercel Sandbox. Production secrets and a GitHub write credential are still not injected.

### `test_deploy_soul_operator.py`

The fake Sandbox now reports `/home/vercel-sandbox` through its `cwd` property so the test cannot pass by relying on `/vercel/sandbox`.

Coverage verifies:

- stale `/vercel/sandbox` browser state maps to the runtime-reported root
- the response returns the runtime root
- `run_process` receives the runtime root through its `cwd=` argument
- the `pwd` fallback works when `sandbox.cwd` is missing
- path escape to `/etc` is refused
- persistent Sandbox stop/resume behavior remains intact
- no production secret/token/password is injected into Sandbox creation
- removed SDK methods do not return
- `/vercel/sandbox` cannot return as a hard-coded `WORKSPACE_ROOT`

## Vercel source evidence

Official file inspected:

`vercel/vercel-py/src/vercel-sandbox/examples/sandbox_04_dev_server.py`

The relevant current behavior is that the Git-backed Sandbox example uses `box.cwd` when the caller has not supplied a working-directory override, and then passes that directory through Sandbox filesystem/process operations.

## Verification state

Vercel preview for code head `89cd3ba4b572447ab3f006636a6194fe2874cc7e`:

- deployment `dpl_5jgMTndceNVxzM2YsxPCQuanfhit`
- state: READY
- branch: `fix/devon-browser-terminal-cwd`
- PR: #20

GitHub CI for the same code head was started as run `32710145065`. At handover creation, the offline flagship lane had passed and remaining lanes were still running. Final merge authorization must use the final docs-inclusive head and require all CI lanes to pass.

## Production acceptance after merge

1. Refresh `https://devon-soul.vercel.app/terminal`.
2. Run `pwd` without editing the existing Working Directory field. The stale `/vercel/sandbox` value must self-heal to the live Sandbox root.
3. Confirm exit code 0.
4. Confirm the Working Directory field changes to the actual path returned by Vercel.
5. Run `git status` and confirm exit code 0 in the same persistent workspace.
6. Only after these harmless commands pass should installation or mutation commands be attempted.

No local Terminal app, Crosh, Linux mode, Python, pnpm, or Docker is required on the user's device.
