---
title: DEVON Operator Terminal Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
branch: devon-operator-terminal
pull_request: 17
purpose: implementation and verification record for the gated DEVON Operator Terminal
---

# DEVON Operator Terminal Handover v1

## Outcome

A real operator terminal has been added to Meta Supreme Apex Genesis without moving process execution into DEVON core.

The load-bearing rule remains intact:

> DEVON parses, plans, validates and gates. DEVON does not execute.

Process execution lives in a separate `services/operator` capability boundary. Mutating or unknown commands use DEVON's existing human approval queue before the exact stored command can execute.

## Architecture

```text
Tee
  |
  v
DEVON Terminal UI
  |
  +--> DEVON core: interpret / validate / gate
  |          |
  |          +--> existing ApprovalQueue
  |                    |
  |                    +--> approve / refuse by Tee
  |
  +--> Operator API
             |
             v
       Operator Bridge
             |
             v
       local process host
```

`services.devon` does not import `services.operator`. The subprocess dependency points only from the separate operator layer toward DEVON's approval contract.

## Artifacts created in this build

### New

1. `services/operator/__init__.py`
   - Defines the operator package boundary.

2. `services/operator/bridge.py`
   - Authenticated execution bridge.
   - Uses `shell=False` and argv execution.
   - Defaults disabled.
   - Enforces a configured working-directory root.
   - Classifies read, approval-gated, and blocked commands.
   - Bounds command length, runtime, and captured output.
   - Stores the exact approved command plan by request id.
   - Makes approved execution single-use.

3. `app/api/v1/operator.py`
   - `GET /api/v1/operator/status`
   - `POST /api/v1/operator/command`
   - `POST /api/v1/operator/execute`
   - Requires `X-Devon-Operator-Key` for execution calls.
   - Uses the same process-local DEVON approval queue as `/api/v1/devon/approvals/decide`.

4. `test_operator_bridge.py`
   - Covers direct read execution.
   - Covers fail-closed classification for unknown commands.
   - Covers environment-dump approval gating.
   - Covers approval-before-write behavior.
   - Covers single-use execution.
   - Covers working-directory escape refusal.
   - Covers blocked host-destruction commands.
   - Covers operator-key rejection.

5. `apps/web/app/terminal/page.tsx`
   - DEVON Operator Terminal interface.
   - Operator key remains in React page state only and is not persisted by the page.
   - Working-directory input.
   - Command transcript.
   - Read-result rendering.
   - Approval card with Approve and Refuse controls.
   - Approved-command execution.
   - Bridge status and capability-boundary display.

6. `.github/workflows/web-ci.yml`
   - Locked pnpm install.
   - TypeScript typecheck.
   - Next.js production build.

7. `docs/devon/SYS_OPS_devon-operator-terminal-handover_v1_2026-08-24.md`
   - This handover and verification record.

### Modified

1. `app/api/v1/router.py`
   - Mounts `operator.router` beside the existing DEVON surface.

2. `apps/web/app/page.tsx`
   - Adds discoverable Operator Terminal navigation and calls to action.

## Command policy v1

### Direct after operator-key authentication

Known read-only commands such as `pwd`, `ls`, `cat`, selected Git inspection commands, and selected Docker inspection commands.

### Human approval required

Unknown or potentially mutating commands. Examples include file writes, most Git state changes, most Docker state changes, and environment dumps such as `env` or `printenv`.

The command is stored before approval. The execute endpoint takes the request id, not a replacement command, so an approved request cannot be swapped to a different command at execution time.

### Blocked at the bridge

Privilege escalation and obvious host-destruction commands including `sudo`, `su`, `doas`, shutdown/reboot commands, disk-formatting tools, and `rm` aimed at protected host root paths.

## Required runtime configuration

The bridge is deliberately off until configured.

```bash
DEVON_OPERATOR_ENABLED=1
DEVON_OPERATOR_KEY=<strong purpose-made secret>
DEVON_OPERATOR_ROOT=/absolute/path/to/Meta-Supreme-Apex-Genesis-
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Do not put the operator key in source control or in a `NEXT_PUBLIC_*` variable.

## Verified evidence

Verification was run by GitHub Actions against PR #17 and the PR merge commit generated from branch head `98a57fa1e4e848c8fbe7b4300b237c5891b732a9` plus `main` at `262fe3f479827f1128e695fb2fe985a723c6d419`.

### Python and API

- Standalone offline flagship job: PASS.
- Engine + cadence / security job: PASS.
- PostgreSQL 16 + pgvector full suite: PASS.
- Exact pytest result: **602 passed, 4 warnings in 50.57s**.
- Ruff: **All checks passed**.

The four pytest warnings are Starlette/FastAPI deprecation warnings in existing dependency paths and tests. They did not fail the suite.

### Web

- `pnpm install --frozen-lockfile`: PASS, lockfile up to date, 109 packages installed.
- `pnpm --filter @meta-supreme/web typecheck`: PASS.
- `pnpm --filter @meta-supreme/web build`: PASS.
- Next.js production compile: PASS.
- `/terminal` emitted as a static route at approximately 4.04 kB route size and 110 kB first-load JS in this run.

The web build reported two non-blocking pre-existing ecosystem warnings: the shared UI package has no explicit package module type, and pnpm ignored the `sharp` install script under its build-script approval policy. Neither blocked compilation, type validation, static generation, or the production build.

## Security boundary that remains

`DEVON_OPERATOR_ROOT` confines the subprocess working directory. It is not a chroot, container sandbox, VM boundary, or operating-system permission boundary.

An approved command still runs with the OS permissions of the API process user and may explicitly address resources that user can reach. Before the bridge is exposed beyond a private single-operator environment, run it inside a least-privilege container or dedicated execution host with only the volumes, sockets, credentials, and network destinations it actually needs.

The operator key is a capability gate, not a replacement for full production identity, session management, network isolation, TLS, or host hardening.

## Deliberate v1 limits

- Output is returned after command completion. There is no PTY or WebSocket/SSE streaming yet.
- Shell syntax is not interpreted. Pipes, redirects, glob expansion, shell variables, and shell built-ins are intentionally absent in v1.
- Approval state and pending execution state are process-local. Use one API worker until both are moved to a shared durable store.
- This bridge executes on the API host only. Remote SSH, GitHub Actions, n8n, EditForge, and GPU hosts should be added later as explicit named adapters rather than hidden shell behavior.
- There is no production deployment or host configuration in this change. The feature is review-ready in PR #17, not merged into `main` by this handover.

## Acceptance status

**REVIEW-READY.** Code, regression tests, full Python/API suite, Ruff, TypeScript typecheck, and Next.js production build passed on the code head recorded above.

Do not describe the terminal as production-hardened until it is deployed behind private access and the Operator Bridge is isolated with least-privilege host/container permissions.
