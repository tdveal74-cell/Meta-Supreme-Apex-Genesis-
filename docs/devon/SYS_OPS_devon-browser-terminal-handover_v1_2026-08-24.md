---
title: DEVON Browser Terminal Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: devon-browser-terminal
pull_request: 18
purpose: implementation and verification record for a hosted DEVON terminal requiring no local shell
---

# DEVON Browser Terminal Handover v1

## Why this repair exists

The first Operator Terminal implementation in PR #17 was technically real but operationally wrong for Tee's requirement. It required a local shell to start the FastAPI API and Next.js frontend. Tee does not have a local terminal. A terminal that requires another terminal to launch it does not solve that problem.

This repair changes the launch model from:

```text
local shell -> local DEVON API + local Next.js -> Operator Terminal
```

to:

```text
Tee's browser
    |
    v
hosted DEVON /terminal
    |
    v
separate hosted Operator capability
    |
    v
Vercel Sandbox microVM
    |
    v
Meta repo workspace + snapshot continuity
```

The intended user action after production deployment is simply to open the hosted `/terminal` route in Safari or Chrome. There is no requirement for Terminal.app, Crosh, Linux mode, Python, pnpm, Docker, or a local shell on Tee's device.

## Canon boundary preserved

`deploy/soul/main.py` remains the existing read-only DEVON Soul phone lane. It is not given subprocess or shell capability.

The hosted command surface lives in `deploy/soul/app.py`, a separate deployment wrapper that imports the existing read-only app and adds the Operator routes. Command execution is delegated to an isolated Vercel Sandbox microVM.

Therefore:

- DEVON Soul does not execute subprocesses.
- DEVON core does not execute subprocesses.
- The Vercel function host is not used as the shell target.
- Tee's phone or Chromebook is not used as the shell target.
- Operator effects are isolated to the Sandbox workspace in v1.

## Artifacts created

1. `deploy/soul/app.py`
   - Hosted deployment wrapper.
   - Reuses the existing DEVON console authentication gate.
   - Registers Vercel request context for Sandbox SDK authentication.
   - Serves `/terminal`.
   - Adds authenticated Operator status and command routes.
   - Creates/restores isolated Vercel Sandbox sessions.
   - Executes the entered shell command inside the microVM.
   - Snapshots the workspace after each command for browser-session continuity.
   - Does not import or call local `subprocess`.

2. `deploy/soul/terminal.html`
   - Responsive browser terminal for phone, tablet, and desktop browsers.
   - Command transcript, working-directory field, Enter-to-run, reset, and clear controls.
   - Stores only the Sandbox snapshot id in browser session storage.
   - States the execution boundary in the UI.

3. `test_deploy_soul_operator.py`
   - Verifies anonymous requests are refused.
   - Verifies the hosted terminal and status route open after DEVON authentication.
   - Verifies only the separate Operator command endpoint introduces a mutation method.
   - Verifies fresh sessions start from Meta `main` and later commands restore only from a snapshot.
   - Verifies no production environment dictionary, password, or token is forwarded into Sandbox creation.
   - Verifies the working directory cannot escape `/vercel/sandbox`.
   - Verifies the wrapper never imports host-side subprocess execution.

## Artifacts modified

1. `deploy/soul/requirements.txt`
   - Adds pinned `vercel==0.10.0` for the Vercel Sandbox Python SDK.

2. `test_deploy_soul.py`
   - Preserves the existing read-only DEVON Soul behavioral checks.
   - Explicitly accounts for `app.py` as a deliberately separate deployment wrapper.
   - Adds `terminal.html` to the shipped secret-shape scan.

## Hosted Operator routes

### `GET /terminal`

Serves the browser Operator interface after the same DEVON console gate already used by the phone experience.

### `GET /api/v1/operator-terminal/status`

Reports the boundary explicitly:

- mode: `isolated-vercel-sandbox`
- repository: `tdveal74-cell/Meta-Supreme-Apex-Genesis-`
- ref: `main`
- production secrets injected: false
- GitHub write connected: false
- DEVON core executes: false

### `POST /api/v1/operator-terminal/command`

Runs one entered command in a Sandbox session. A fresh browser session starts from a shallow clone of Meta `main`. A later command restores the browser's prior Sandbox snapshot.

The requested working directory is restricted to `/vercel/sandbox` and descendants.

## Security posture v1

The browser terminal is deliberately useful without becoming an unbounded production shell.

### What the Sandbox gets

- an isolated Linux workspace
- a shallow checkout of the public Meta `main` branch for a fresh workspace
- the command Tee enters
- a prior Sandbox snapshot id when resuming that browser session

### What it does not get

- production DEVON environment variables
- Pinecone credentials
- DEVON console credentials
- a GitHub write token
- a Docker socket from the production host
- the production host filesystem

The browser terminal can edit, build, and test its own Sandbox copy. In v1 it cannot silently push those edits back to GitHub. A future GitHub-write adapter should remain a named, approval-gated capability rather than injecting a broad credential into the shell.

## Snapshot continuity

After each command the running Sandbox is snapshotted and stopped. The snapshot id is returned to the browser and stored in `sessionStorage`. The next command restores from that snapshot, so workspace edits survive between commands in the browser session without keeping a long-running shell process on Tee's device.

`Reset from Meta main` clears the browser snapshot reference so the next command starts from a clean Meta `main` workspace.

## Verification evidence

### Vercel deployment / route

The `devon-browser-terminal` branch is connected to the existing `devon-soul` Vercel project whose root is `deploy/soul`.

The preview deployment for the lint-fixed code head `edee954fd9eecf177b27ae3969ff69cc50f82e7d` reached Vercel state `READY`.

The preview branch alias now resolves `/terminal` to the actual DEVON Browser Terminal door. Before this repair `/terminal` on the hosted service was a 404.

The preview currently returns an authenticated-service refusal because `CONSOLE_TOKEN` is not configured in the Vercel Preview environment. The response is the Operator door itself and says the console gate is not configured. That gate was not bypassed or hard-coded for testing.

This preview limitation does not establish that a live Sandbox command has run. The authenticated Sandbox round trip remains a production smoke-test item after an authorized merge, because the available Vercel connector cannot copy the existing production-only console secret into Preview and this implementation will not weaken the gate to manufacture a green smoke test.

### GitHub CI, first repair head

On PR #18 head `85267abe075ce2e63127f1acf4113bc1f856d8b0`:

- Standalone offline flagship: PASS.
- Engine + cadence/security: PASS.
- Full PostgreSQL 16 + pgvector pytest suite: **611 passed, 4 warnings in 51.15s**.
- Ruff initially found two mechanical issues in `deploy/soul/app.py`: an unsorted import block and an unused `os` import.
- Those two lint findings were repaired in commit `edee954fd9eecf177b27ae3969ff69cc50f82e7d`.

The four pytest warnings are existing FastAPI/Starlette deprecation warnings and did not fail the test suite.

### Final-head gate

The final-head CI result must be read from GitHub before merge. Do not describe PR #18 as fully green until the lint-fixed/docs-inclusive head has completed its CI run successfully.

## Deliberate limits

- No production GitHub write credential in the shell.
- No direct production filesystem or Vercel-host shell access.
- No production secret injection into Sandbox commands.
- Browser-session continuity is snapshot-based, not a permanent PTY process.
- The current command API returns output after the command finishes rather than streaming every byte over a persistent WebSocket.
- Preview cannot perform the authenticated live Sandbox smoke test unless its own DEVON console credential is deliberately configured.

## Production acceptance sequence

1. GitHub CI passes on the final PR #18 head.
2. Tee explicitly authorizes merging PR #18.
3. Merge PR #18 into `main`.
4. Verify the `devon-soul` production deployment reaches `READY` on the merge commit.
5. Verify `https://devon-soul.vercel.app/terminal` resolves to the Operator route rather than 404.
6. Tee opens that URL in the browser and uses the existing DEVON console authentication.
7. First live smoke command: `pwd`.
8. Second: `git status`.
9. Edit a harmless Sandbox file, run another command, and confirm snapshot continuity.
10. Reset from Meta main and confirm a fresh workspace.

## Status

**REVIEW-READY, NOT MERGED.** PR #18 exists specifically so the browser-launch repair is not pushed into production without Tee's explicit ruling.
