---
title: DEVON Durable Agent Tasks and Operator Adapter Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready-pending-final-ci
repository: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-runtime-durable-operator
pull_request: 25
base_merge: 374a983844a9c399fc6fbc7b71a90f9cedf397a7
predecessor_pull_request: 24
purpose: Record the PostgreSQL durability layer, Agent Tasks API, generic capability adapter contract, approval-bound Operator adapter, verification evidence, operational limits, and next build sequence.
---

# DEVON Durable Agent Tasks and Operator Adapter Handover v1

## 1. Starting state and ruling

PR #24, `feat(devon): add governed Agent Runtime v1`, was explicitly authorized
by Tee and merged into `main` on 2026-08-24.

Merge commit:

```text
374a983844a9c399fc6fbc7b71a90f9cedf397a7
```

This PR starts from that merge commit and implements the first two items in the
v1 handover's recommended next-build sequence:

1. PostgreSQL durable task, checkpoint, memory, and skill storage.
2. A generic capability-adapter boundary with the existing Operator Bridge as
   the first real execution toolset.

It also adds the authenticated Agent Tasks API required to operate those layers.

The DEVON doctrine remains unchanged:

- `services/devon` owns identity, doctrine, judgement, validation, and approval
  authority.
- `services/devon` does not own subprocess or network effects.
- Human rulings belong to Tee.
- The Agent Runtime owns resumable task state.
- Capability adapters own effects.
- An approval is permission for the exact described effect, not general
  permission to act.

## 2. Architecture

```text
Tee
 |
 v
Authenticated Agent Tasks API
 app/api/v1/agent_tasks.py
 |
 v
Application coordinator
 app/services/agent_tasks.py
 |
 +--------------------------+
 |                          |
 v                          v
PostgreSQL durability       DEVON Agent Runtime
 tasks/checkpoints          plan / act / observe
 memories/skills            approval-aware loop
 |                          |
 +------------+-------------+
              |
              v
       DEVON ApprovalQueue
              |
              v
       Capability adapters
              |
              v
       Operator Bridge
              |
              v
       local process host
```

Dependency direction remains one way. `services/devon` does not import the
Agent Runtime, SQLAlchemy models, or Operator capability code.

## 3. Sources opened before implementation

Canonical Meta repository sources read during this build included:

```text
docs/devon/SYS_OPS_devon-agent-runtime-handover_v1_2026-08-24.md
services/devon/approval.py
services/operator/bridge.py
app/api/v1/devon.py
app/api/v1/operator.py
app/api/v1/router.py
app/db/session.py
app/models/__init__.py
app/models/workflow.py
app/models/memory.py
app/models/project.py
conftest.py
.github/workflows/ci.yml
services/agent_runtime/contracts.py
services/agent_runtime/store.py
services/agent_runtime/learning.py
services/agent_runtime/planner.py
services/agent_runtime/runtime.py
services/agent_runtime/tools.py
services/intelligence/providers/mock_provider.py
```

These reads established the current schema pattern, ownership rules, test
migration mechanism, shared DEVON approval queue, shared Operator Bridge, and
framework-free runtime contracts before new code was written.

## 4. Persistence layer

### 4.1 Incremental schema

Added:

```text
database/schemas/005_agent_runtime_persistence.sql
```

It creates four owner-scoped tables:

```text
agent_tasks
agent_task_checkpoints
agent_runtime_memories
agent_runtime_skills
```

Key properties:

- task IDs use the existing `TASK-*` runtime identity;
- task payloads are stored as canonical JSONB snapshots;
- checkpoints are stored independently as an audit-friendly history;
- task and checkpoint rows are scoped to the authenticated owner;
- project association is optional and uses `ON DELETE SET NULL`;
- memories are inspectable and deletable records;
- skills are unique by owner and normalized name;
- skill updates increment the version rather than silently replacing history
  semantics;
- indexes support owner/state and owner/update-time retrieval.

### 4.2 SQLAlchemy models

Added:

```text
app/models/agent_runtime.py
```

Models:

```text
AgentTaskRecord
AgentTaskCheckpointRecord
AgentRuntimeMemory
AgentRuntimeSkill
```

Modified:

```text
app/models/__init__.py
```

The new models are registered in the model package so mapper configuration and
test discovery do not depend on incidental imports.

### 4.3 Test database application

Modified:

```text
conftest.py
```

`005_agent_runtime_persistence.sql` is now applied after schemas 001 through
004. Agent Runtime tables are included in test cleanup before owner/project
rows are truncated.

Modified:

```text
.github/workflows/ci.yml
```

The explicit schema-presence gate now requires migration 005 as well as 001
through 004. This closes a gap found by reading the first successful PR #25 CI
log, where conftest used schema 005 but the explicit gate still named only the
older four migrations.

## 5. Canonical task round trip

Added:

```text
services/agent_runtime/serialization.py
```

`task_from_dict()` reconstructs the framework-free runtime contract from the
canonical `AgentTask.to_dict()` representation, including:

- plan and steps;
- tool calls and arguments;
- step state;
- approval request IDs;
- observations;
- checkpoints;
- completion/failure state;
- timestamps.

This keeps the database adapter from becoming a second task model with different
semantics.

Added:

```text
app/services/agent_runtime_persistence.py
```

`AgentTaskRepository` provides owner-scoped asynchronous save, get, list, and
delete operations. Task snapshots use PostgreSQL upsert. Checkpoints append by
stable checkpoint ID.

`AgentLearningRepository` provides owner-scoped asynchronous memory and skill
operations. Recall remains deterministic lexical overlap in this version.
This is transparent retrieval, not hidden model retraining.

## 6. Approval binding

Added:

```text
services/agent_runtime/governance.py
```

For every approval-required step, the runtime creates a SHA-256 binding over:

```text
task_id
step_id
tool_name
exact tool arguments
```

The canonical JSON is sorted before hashing. The approval consequence includes
a machine-readable marker:

```text
DEVON-RUNTIME-BINDING:<sha256>
```

Modified:

```text
services/agent_runtime/runtime.py
```

The runtime now:

1. computes the binding before raising an effect approval;
2. records the binding marker in `what_happens`;
3. rechecks the authoritative DEVON approval state on resume;
4. passes the request ID and binding to the capability adapter only after the
   request is approved.

This prevents a broad approval token from becoming permission to substitute a
different command after the human ruling.

## 7. Generic capability adapter boundary

Added:

```text
services/agent_runtime/adapters.py
```

It defines the `CapabilityAdapter` protocol and a registration helper. An
adapter names itself and registers governed `ToolSpec` instances into the
runtime registry.

This is the expansion point for later GitHub, browser, n8n, Drive, EditForge,
GPU, Vercel Sandbox, scheduler, and MCP capability packages.

## 8. Operator capability adapter

Added:

```text
services/operator/agent_adapter.py
```

It exposes two tools:

### `operator.read`

Risk: `read`

Behavior:

- requires the existing Operator Bridge to be configured;
- asks the bridge to classify the command;
- executes only when the bridge classifies the exact command as read-only;
- refuses mutating or blocked commands;
- uses argv execution with no shell expansion, matching the existing bridge.

### `operator.command`

Risk: `high_impact`

Behavior:

- always stops at DEVON human approval in the Agent Runtime;
- requires the runtime request ID and exact approval binding;
- asks the Operator Bridge to classify the command again;
- refuses commands still in the bridge's blocked set;
- refuses read commands and directs the caller to `operator.read`;
- crosses the process boundary only through `execute_runtime_approved()`.

Modified:

```text
services/operator/bridge.py
```

Added `execute_runtime_approved()`. It verifies:

1. the command is not blocked;
2. the DEVON approval request still exists;
3. the request state is `approved`;
4. the request's `what_happens` contains the exact runtime binding marker.

Only then does it call the existing `_run()` process execution path.

The bridge's original terminal approval flow remains intact.

## 9. Durable application coordinator

Added:

```text
app/services/agent_tasks.py
```

The service deliberately reuses the existing process singletons:

```text
app.api.v1.devon._queue
app.api.v1.operator._bridge
```

That means the terminal and Agent Tasks surface consult one DEVON approval
authority and one Operator Bridge per API process rather than creating parallel
approval universes.

The service:

- loads durable learning context before planning;
- supports explicit validated steps for deterministic controlled workflows;
- otherwise uses the existing provider abstraction through `LLMPlanner`;
- restores task snapshots from PostgreSQL before running;
- advances the framework-free Agent Runtime;
- persists every externally visible task transition before the API request
  completes;
- exposes task cancel and truthful logical rollback;
- exposes the registered tool catalog and Operator configuration state.

## 10. Authenticated Agent Tasks API

Added:

```text
app/api/v1/agent_tasks.py
```

Modified:

```text
app/api/v1/router.py
```

Routes:

```text
GET    /api/v1/agent-tasks/tools
GET    /api/v1/agent-tasks
POST   /api/v1/agent-tasks
GET    /api/v1/agent-tasks/{task_id}
POST   /api/v1/agent-tasks/{task_id}/run
POST   /api/v1/agent-tasks/{task_id}/cancel
POST   /api/v1/agent-tasks/{task_id}/rollback
DELETE /api/v1/agent-tasks/{task_id}

GET    /api/v1/agent-tasks/learning/memories
POST   /api/v1/agent-tasks/learning/memories
DELETE /api/v1/agent-tasks/learning/memories/{memory_id}

GET    /api/v1/agent-tasks/learning/skills
PUT    /api/v1/agent-tasks/learning/skills/{name}
```

Properties:

- every route requires the existing authenticated current-user dependency;
- tasks, memories, and skills are owner-scoped;
- a project ID is accepted only when the authenticated user owns the project;
- unknown tasks are returned as 404 rather than exposing cross-owner existence;
- runtime state conflicts use 409;
- invalid plans use 422;
- task creation can use explicit steps or provider-backed planning;
- the tool catalog states that Operator root confinement is not an OS sandbox.

## 11. Regression coverage

Added:

```text
test_devon_agent_tasks_api.py
```

Coverage includes:

1. a durable `operator.read` task executes and can be fetched after completion;
2. the read creates and persists a checkpoint;
3. an `operator.command` task stops before the effect;
4. the effect does not occur before approval;
5. DEVON approval resumes the exact bound command;
6. the completed task does not execute again on normal replay;
7. durable memories can be created, listed, injected into planning context, and
   deleted;
8. durable skills increment from version 1 to version 2 on update;
9. a second authenticated user cannot see another user's task;
10. an approved request carrying the wrong binding cannot authorize a different
    command.

## 12. Verified code-head evidence

The first complete implementation head before the CI-gate tightening and this
handover was:

```text
64ab5c4859faf170daf0d0dcd6e1e5ae9856cea3
```

GitHub Actions run:

```text
32754658696
```

Results read from GitHub Actions:

```text
Standalone offline flagship: PASS
Engine + cadence/security: PASS
PostgreSQL 16 + pgvector API suite: PASS
pytest: 640 passed, 4 warnings in 58.48s
Ruff: All checks passed!
```

The four warnings are existing Starlette/FastAPI deprecation warnings and did
not fail the suite.

A new exact-head CI run is required after the CI-gate and handover commits. PR
#25 must not be called final or merged until that final head is green.

## 13. Operational limits that remain true

### 13.1 Approval state is still process local

Task, checkpoint, memory, and skill state are now PostgreSQL durable.

The DEVON `ApprovalQueue` still uses its process-local default store. Therefore,
a task that is already `waiting_approval` is not fully restart-resumable if the
API process dies before the human decides. The task snapshot survives, but the
corresponding approval record does not.

Do not run multiple API workers for Agent Tasks approval work until the approval
store is made shared/durable or routed through the already verified external
approval queue.

### 13.2 External effects are not crash-atomic exactly once

Normal replay after a completed task is persisted does not re-run the effect and
is covered by regression tests.

There is still a crash window after an external process effect succeeds and
before the resulting task snapshot is committed to PostgreSQL. A process death
inside that window can leave the external system changed while the durable task
still appears not completed.

True crash-atomic exactly-once behavior requires adapter-specific idempotency,
receipts, or durable execution leases. This PR does not claim that property.

### 13.3 Operator root is not an operating-system sandbox

`DEVON_OPERATOR_ROOT` constrains the process working directory chosen by the
bridge. It is not a chroot, container, VM, seccomp profile, or filesystem
sandbox.

An approved command runs with the operating-system permissions of the API
process user and can explicitly address any resource that user can reach.

### 13.4 No broad shell interpreter was added

The Operator Bridge still uses argv execution with `shell=False`. Pipes,
redirects, glob expansion, shell variable expansion, and interactive shell
programs are not part of this layer.

## 14. Artifacts added in PR #25

```text
app/models/agent_runtime.py
app/services/agent_runtime_persistence.py
app/services/agent_tasks.py
app/api/v1/agent_tasks.py
database/schemas/005_agent_runtime_persistence.sql
services/agent_runtime/serialization.py
services/agent_runtime/governance.py
services/agent_runtime/adapters.py
services/operator/agent_adapter.py
test_devon_agent_tasks_api.py
docs/devon/SYS_OPS_devon-agent-runtime-durable-operator-handover_v1_2026-08-24.md
```

## 15. Artifacts modified in PR #25

```text
app/models/__init__.py
app/api/v1/router.py
services/agent_runtime/runtime.py
services/operator/bridge.py
conftest.py
.github/workflows/ci.yml
```

No source file under `services/devon/` is modified by this PR.

## 16. Remaining next-layer sequence

After PR #25 is merged and stable, continue in this order:

1. GitHub capability adapter. Reads automatic. Writes and remote effects through
   DEVON approval and exact binding.
2. Durable/shared approval store so a waiting task survives API process restart
   and multiple workers can consult one authority.
3. Browser automation adapter with domain allow/deny and action risk policy.
4. Isolated subagent pool with bounded concurrency, budgets, and parent task
   accountability.
5. Durable scheduler with delivery destinations and run leases.
6. MCP discovery/registration with risk declarations per exposed tool.
7. Browser/phone Agent Tasks UI showing plan, progress, observations,
   checkpoints, approvals, cost, and receipts.
8. Only after those layers are proven, autonomous skill proposals. Publication
   and modification remain reviewable and versioned.

The shared approval store is moved ahead of browser automation here because the
new PostgreSQL task layer exposes the restart mismatch clearly. It is a
reliability prerequisite for unattended multi-worker operation.

## 17. Current production status

PR #25 is open and unmerged as of this handover commit.

This branch adds production API code, but it is not on `main` until a human
explicitly authorizes PR #25 to merge. No deployment claim is made by this
handover.
