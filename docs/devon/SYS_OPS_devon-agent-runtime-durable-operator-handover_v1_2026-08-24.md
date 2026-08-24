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
purpose: Record PostgreSQL Agent Runtime durability, authenticated Agent Tasks, transparent learning state, the generic capability-adapter boundary, the governed Operator adapter, the approval-binding security correction, verification evidence, operational limits, and the next build sequence.
---

# DEVON Durable Agent Tasks and Operator Adapter Handover v1

## 1. Starting state

PR #24, `feat(devon): add governed Agent Runtime v1`, was explicitly authorized by Tee and merged into `main` on 2026-08-24.

Merge commit:

```text
374a983844a9c399fc6fbc7b71a90f9cedf397a7
```

PR #25 starts from that merge and implements the first production-facing runtime layers:

1. PostgreSQL durable task and checkpoint state.
2. PostgreSQL durable, inspectable memory and versioned skill state.
3. An authenticated Agent Tasks API.
4. A generic capability-adapter contract.
5. The existing Operator Bridge as the first governed real execution adapter.

DEVON doctrine remains unchanged:

- `services/devon` owns doctrine, judgement, validation, and approval authority.
- `services/devon` does not execute subprocesses or network effects.
- Human rulings belong to Tee.
- The Agent Runtime owns resumable task state.
- Capability adapters own effects.
- An approval authorizes one exact described effect, not a general permission to act.

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
 +----------------------------+
 |                            |
 v                            v
PostgreSQL durability         DEVON Agent Runtime
 tasks/checkpoints            plan / act / observe
 memories/skills              approval-aware loop
 |                            |
 +-------------+--------------+
               |
               v
        DEVON ApprovalQueue
               |
               v
       capability registry
               |
               v
       Operator adapter
               |
               v
       Operator Bridge
               |
               v
       local process host
```

Dependency direction is one way. `services/devon` does not import Agent Runtime, SQLAlchemy, API, or Operator capability code.

## 3. Canonical sources opened

Sources opened during implementation and subsequent security audit included:

```text
docs/devon/SYS_OPS_devon-agent-runtime-handover_v1_2026-08-24.md
services/devon/approval.py
services/operator/bridge.py
services/operator/agent_adapter.py
services/agent_runtime/contracts.py
services/agent_runtime/store.py
services/agent_runtime/learning.py
services/agent_runtime/planner.py
services/agent_runtime/runtime.py
services/agent_runtime/tools.py
services/agent_runtime/governance.py
app/api/v1/devon.py
app/api/v1/operator.py
app/api/v1/router.py
app/db/session.py
app/models/__init__.py
app/models/workflow.py
app/models/memory.py
app/models/project.py
app/services/agent_tasks.py
conftest.py
.github/workflows/ci.yml
services/intelligence/providers/mock_provider.py
```

These reads established the current schema pattern, user ownership boundary, test migration mechanism, shared DEVON approval queue, shared Operator Bridge, and framework-free runtime contracts.

## 4. Persistence layer

### 4.1 Incremental schema

Added:

```text
database/schemas/005_agent_runtime_persistence.sql
```

Tables:

```text
agent_tasks
agent_task_checkpoints
agent_runtime_memories
agent_runtime_skills
```

Properties:

- canonical `TASK-*` IDs are preserved;
- task snapshots are JSONB;
- checkpoints are independently persisted for auditability;
- task, checkpoint, memory, and skill rows are owner-scoped;
- optional project association uses `ON DELETE SET NULL`;
- memories are inspectable and deletable;
- skills are unique by owner and normalized name;
- skill changes increment the stored version;
- indexes support owner/state and update-time retrieval.

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

The new models are explicitly registered so mapper configuration does not depend on incidental imports.

### 4.3 Persistence repositories

Added:

```text
app/services/agent_runtime_persistence.py
```

`AgentTaskRepository` supplies owner-scoped async save/get/list/delete. Task snapshots use PostgreSQL upsert. Checkpoints append by stable checkpoint ID.

`AgentLearningRepository` supplies owner-scoped memory and skill operations. Recall is deterministic lexical overlap in this layer. It is transparent retrieval, not hidden training.

### 4.4 Test schema path

Modified:

```text
conftest.py
.github/workflows/ci.yml
```

The test database applies migration 005 after migrations 001 through 004. Agent Runtime tables are included in cleanup. The explicit CI schema-presence gate names migration 005 so a missing migration fails loudly.

## 5. Canonical task round trip

Added:

```text
services/agent_runtime/serialization.py
```

`task_from_dict()` reconstructs the framework-free `AgentTask` contract from `AgentTask.to_dict()` including:

- plan and steps;
- tool arguments;
- step state;
- approval request IDs;
- observations;
- checkpoints;
- terminal task state;
- timestamps.

This prevents the database layer from becoming a second incompatible task model.

## 6. Approval binding, corrected design

Added and subsequently hardened:

```text
services/agent_runtime/governance.py
```

For each approval-required step, the runtime computes a SHA-256 binding over canonical sorted JSON containing:

```text
task_id
step_id
tool_name
exact tool arguments
```

The human-readable approval consequence contains:

```text
DEVON-RUNTIME-BINDING:<sha256>
```

The runtime passes capability metadata only after the authoritative approval state is `approved`:

```text
request_id
binding
task_id
step_id
tool_name
```

### 6.1 Security audit correction

During the subsequent GitHub adapter layer, static review found a trust gap in the first PR #25 implementation.

The first implementation generated a correct binding and stored its marker on the approval record, but the Operator capability boundary accepted a binding string supplied by the runtime and only checked whether that marker appeared on the approved record. The bridge did not independently recompute the hash from the arguments it was about to execute.

That was not strong enough to support the claim that the process boundary itself verified the exact effect.

The correction was backported into PR #25 before merge.

`require_approved_runtime_binding()` now runs at the capability boundary and:

1. requires `request_id`, `binding`, `task_id`, `step_id`, and `tool_name` metadata;
2. compares the metadata tool name to the adapter's known tool name with `hmac.compare_digest`;
3. independently recomputes SHA-256 from the actual arguments the adapter is about to use;
4. compares supplied and recomputed bindings with `hmac.compare_digest`;
5. requires the authoritative DEVON approval request to still exist;
6. requires approval state `approved`;
7. requires `requested_by == "DEVON Agent Runtime"`;
8. requires the approval consequence to contain the marker for the independently recomputed binding.

The adapter therefore does not treat runtime metadata as proof by itself.

## 7. Generic capability adapter contract

Added:

```text
services/agent_runtime/adapters.py
```

It defines the adapter registration boundary around governed `ToolSpec` instances. The Agent Runtime sees declared risk before execution.

This is the expansion point for GitHub, durable approval storage, browser automation, n8n, Drive, EditForge, GPU, deployment, scheduler, and MCP adapters.

## 8. Operator adapter

Added:

```text
services/operator/agent_adapter.py
```

### `operator.read`

Risk: `read`

- Requires the Operator Bridge to be configured.
- Reclassifies the exact command at the bridge.
- Executes only if the bridge says it is read-only.
- Refuses mutating or blocked commands.
- Uses argv execution with `shell=False`.

### `operator.command`

Risk: `high_impact`

- Always stops at the Agent Runtime's DEVON approval gate.
- Removes runtime approval metadata from the tool argument envelope.
- Passes the remaining exact effect arguments and approval identity to the bridge.
- Does not itself trust a supplied binding string.

Modified and hardened:

```text
services/operator/bridge.py
```

`execute_runtime_approved()` now receives the actual argument dictionary plus approval metadata. It invokes the shared exact-binding verifier before interpreting the command. Only after that verification does it build a `CommandPlan` from those same arguments.

It then:

- re-applies the Operator command classifier;
- refuses blocked commands;
- refuses read commands on the effectful tool and directs them to `operator.read`;
- executes with the approved timeout and working directory;
- crosses the process boundary through the existing `_run()` path.

This sequencing matters: approval verification is tied to the exact argument object used to build the eventual command plan.

The direct Operator Terminal approval flow remains separate and unchanged.

## 9. Durable application coordinator

Added:

```text
app/services/agent_tasks.py
```

The service reuses the existing per-process singletons:

```text
app.api.v1.devon._queue
app.api.v1.operator._bridge
```

The terminal and Agent Tasks API therefore consult one approval authority and one Operator Bridge per API process rather than parallel gates.

The service:

- loads durable learning context before planning;
- supports explicit validated steps for controlled workflows;
- otherwise uses the existing provider abstraction through `LLMPlanner`;
- restores tasks from PostgreSQL;
- advances the framework-free runtime;
- persists externally visible state transitions;
- exposes cancel and truthful logical rollback;
- exposes the governed tool catalog and Operator configuration state.

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

- existing authenticated-current-user dependency on every route;
- owner-scoped tasks, memories, and skills;
- project ID accepted only for a project owned by the authenticated user;
- unknown/cross-owner task retrieval returns 404;
- runtime state conflicts use 409;
- invalid explicit plans use 422;
- explicit-step and provider-planned task creation are both supported;
- the tool catalog states that Operator root confinement is not an OS sandbox.

## 11. Regression coverage

Added and hardened:

```text
test_devon_agent_tasks_api.py
```

Coverage includes:

1. durable `operator.read` execution and fetch after completion;
2. persisted checkpoint creation;
3. effectful command stopping before execution;
4. no effect before human approval;
5. approved exact command execution;
6. no second execution on ordinary completed-task replay;
7. durable memory create/list/context/delete;
8. durable skill version increment;
9. cross-owner task isolation;
10. an explicit argument-substitution attack: approval is created for `touch approved.txt`, then execution is attempted with `touch substituted.txt`; the capability boundary recomputes the binding, refuses the mismatch, and neither file is created.

## 12. Verification evidence

### 12.1 Pre-audit implementation

Earlier exact-head run `32755156675` on head `f74d652e5e9db87cb87e9668a5f9f6edf36151e2` passed:

```text
Standalone offline flagship: PASS
Engine + cadence/security: PASS
PostgreSQL 16 + pgvector API suite: PASS
Schema gate including 005: PASS
pytest: 641 passed, 4 warnings in 63.96s
Ruff: All checks passed!
```

Those results establish the persistence/API layer baseline, but they predate the approval-boundary correction above.

### 12.2 Security-repair evidence from stacked GitHub layer

The corrected shared runtime/Operator code was exercised on the stacked GitHub adapter branch before being backported here. Two successive PostgreSQL runs reached:

```text
650 passed, 4 warnings
```

The only failure on those stacked runs was Ruff I001 on a GitHub-layer module-level blank line in `app/services/agent_tasks.py`, unrelated to the shared approval verifier or Operator tests. The exact argument-substitution regression passed as part of those 650 tests.

### 12.3 Final PR #25 exact-head requirement

This handover commit moves the PR #25 head. A fresh GitHub Actions run over this handover-inclusive head is mandatory before PR #25 is called final. The result belongs on the PR record because writing the resulting run ID back into this file would create another new head.

## 13. Remaining operational limits

### 13.1 Approval state is still process-local

Task, checkpoint, memory, and skill state are PostgreSQL durable. The current DEVON `ApprovalQueue` default remains process-local.

A task already in `waiting_approval` survives in PostgreSQL, but its corresponding approval request does not survive an API process death. Do not claim restart-safe approval resumption or multi-worker approval consistency yet.

The next reliability layer should make approval state shared/durable or route the runtime through the already verified external approval queue.

### 13.2 External effects are not crash-atomic exactly once

Normal replay after a completed task is persisted does not re-run the effect and is regression-tested.

There remains a crash interval after an external effect succeeds but before the resulting task snapshot commit. A process death in that interval can leave the external system changed while durable runtime state still appears incomplete.

Adapter-specific idempotency keys, execution leases, and/or durable effect receipts are required before claiming crash-atomic exactly-once execution.

### 13.3 Operator root is not an OS sandbox

`DEVON_OPERATOR_ROOT` constrains working-directory resolution only. It is not a chroot, container, VM, seccomp profile, or filesystem sandbox.

An approved command runs with the operating-system permissions of the API process user and may explicitly address resources reachable by that user.

### 13.4 No broad shell interpreter

The bridge still uses `subprocess.run(..., shell=False)`. Native shell pipes, redirects, glob expansion, shell variables, and interactive PTY behavior are outside this layer.

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

Security-audit backport modified these existing PR #25 artifacts again:

```text
services/agent_runtime/governance.py
services/agent_runtime/runtime.py
services/operator/bridge.py
services/operator/agent_adapter.py
test_devon_agent_tasks_api.py
docs/devon/SYS_OPS_devon-agent-runtime-durable-operator-handover_v1_2026-08-24.md
```

No source file under `services/devon/` is modified by PR #25.

## 16. Runtime configuration

Operator capability remains disabled unless explicitly configured on the private execution host:

```bash
DEVON_OPERATOR_ENABLED=1
DEVON_OPERATOR_KEY=<strong purpose-made secret>
DEVON_OPERATOR_ROOT=/absolute/path/to/Meta-Supreme-Apex-Genesis-
```

Do not put the Operator key into a `NEXT_PUBLIC_*` environment variable or source control.

## 17. Next layer sequence

After PR #25 is authorized, merged, and stable:

1. GitHub capability adapter with allowlisted reads and approval-bound remote effects.
2. Durable/shared approval storage so waiting tasks survive process restart and multiple workers consult one authority.
3. Browser automation with explicit domain/action policy.
4. Isolated bounded subagent pool with budgets and parent-task accountability.
5. Durable scheduler with execution leases and delivery destinations.
6. MCP discovery/registration with risk declarations per exposed capability.
7. Browser/phone Agent Tasks UI showing plans, observations, checkpoints, approvals, costs, and receipts.
8. Autonomous skill proposals only after those layers are proven. Publication and modification remain reviewable and versioned.

Shared approval durability remains the first reliability prerequisite after the GitHub adapter because the PostgreSQL task layer makes the restart mismatch explicit.

## 18. Current status

PR #25 remains open and unmerged. No production deployment is claimed.

The security correction was deliberately applied before merge. Final acceptance requires the fresh handover-inclusive GitHub Actions run to pass all three lanes and Ruff, followed by a read-back of PR state.
