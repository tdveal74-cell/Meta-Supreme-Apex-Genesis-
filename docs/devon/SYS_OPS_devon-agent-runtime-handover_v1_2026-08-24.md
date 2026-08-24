---
title: DEVON Agent Runtime Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: review-ready
repository: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-agent-runtime-v1
pull_request: 24
production_base: 67531cad95cc85dd903d81c58d4ea3f8c8461684
purpose: Record the first governed Hermes-class agent-runtime slice for DEVON, its architecture boundary, artifacts, verification evidence, deliberate limits, and next build sequence.
---

# DEVON Agent Runtime Handover v1

## 1. Ruling and architectural intent

The operator asked whether DEVON could become like Hermes Agent.

The answer implemented here is yes, but not by moving execution capability into
`services/devon`.

The load-bearing DEVON rule remains unchanged:

- DEVON core parses, plans, validates, and gates.
- DEVON core does not own network or subprocess effects.
- Human rulings belong to Tee.
- Execution belongs to capability-owning layers outside `services/devon`.

This PR therefore adds `services/agent_runtime` as a separate runtime layer.
Dependency direction is one way: the runtime may consume DEVON approval
contracts, while `services/devon` does not import the runtime.

Conceptually:

```text
Tee
  |
  v
DEVON core
identity / doctrine / judgement / approval authority
  |
  v
DEVON Agent Runtime
plan / task state / tool registry / memory / skills / checkpoints
  |
  v
DEVON ApprovalQueue for effectful steps
  |
  v
Capability adapters
Operator / Vercel Sandbox / GitHub / n8n / Drive / EditForge / GPU / browser
```

The last adapter layer is intentionally not all wired in this v1 PR.

## 2. Sources opened before implementation

Canonical Meta repository sources inspected on `main`:

- `docs/devon/DEVON.md`
- `services/devon/approval.py`
- `services/operator/bridge.py`
- `services/intelligence/providers/base.py`
- `services/intelligence/providers/factory.py`
- `app/services/intelligence.py`
- `app/api/v1/router.py`

These established the current DEVON non-execution invariant, human approval
contract, separate Operator boundary, and model-agnostic provider abstraction.

Public reference reviewed:

- `NousResearch/hermes-agent`
- current public README on 2026-08-24
- repository license reported as MIT

Hermes was used as an architectural reference for agent-loop, memory, skill,
scheduler, subagent, messaging, and execution-backend concepts. No Hermes source
code is copied into this PR.

## 3. What v1 implements

### 3.1 Resumable task contracts

`services/agent_runtime/contracts.py`

Defines explicit task and step states, tool risk, tool calls, validated plans,
observations, checkpoints, runtime results, and serializable task state.

Task states:

```text
planned
running
waiting_approval
completed
failed
cancelled
```

Tool risks:

```text
read
write
high_impact
blocked
```

### 3.2 Transparent memory and versioned skills

`services/agent_runtime/learning.py`

Provides a narrow `LearningStore` contract and an in-memory reference
implementation.

Properties:

- memories are inspectable records, not hidden model state;
- memories are deletable;
- recall is deterministic lexical overlap in v1;
- skills are inspectable procedural records;
- updating a skill increments its version;
- relevant memories and current skills can be injected into planning context;
- storage is process local until a durable adapter is added.

This is not model retraining and must not be described as one.

### 3.3 Pluggable task store

`services/agent_runtime/store.py`

Defines `AgentTaskStore` and a thread-safe in-memory implementation. The
interface is deliberately small so PostgreSQL, Redis, or another durable store
can replace it without changing the agent loop.

### 3.4 Governed tool registry

`services/agent_runtime/tools.py`

Defines tool specifications and an explicit registry.

Every registered tool declares:

- name;
- description;
- risk;
- handler;
- reversibility;
- blast radius.

Unknown tool names fail closed. Blocked tools do not execute. Synchronous and
asynchronous adapters are supported. Adapter exceptions become explicit failed
observations rather than disappearing.

### 3.5 Provider-backed planner

`services/agent_runtime/planner.py`

Provides:

- `Planner` protocol;
- deterministic `StaticPlanner` for tests and controlled workflows;
- `LLMPlanner` using Meta's existing model-agnostic `AIProvider` abstraction.

LLM output is not trusted as executable structure. The planner validates:

- one JSON object;
- non-empty steps;
- maximum 12 steps;
- every tool exists in the supplied registry;
- blocked tools are rejected;
- arguments are objects;
- completion criteria are a list.

The model can suggest a plan. The registry remains authority over capabilities.

### 3.6 Approval-aware agent loop

`services/agent_runtime/runtime.py`

Implements the v1 goal-to-completion loop:

```text
goal -> plan -> act -> observe -> next step -> finish
```

Policy behavior:

- READ tools run without a human ruling;
- WRITE and HIGH_IMPACT tools stop at the existing DEVON `ApprovalQueue`;
- the approval request states tool, arguments, task goal, reversibility, and
  blast radius;
- the one-time approval token is returned only when the request is raised;
- a resumed task re-reads the approval state;
- PENDING remains blocked;
- REFUSED or EXPIRED cancels the task and the effect does not run;
- APPROVED permits the exact registered tool step to run;
- a completed task is replay-safe at the runtime layer and is not executed a
  second time merely because `run_until_blocked` is called again;
- BLOCKED tools fail closed.

A resume defect was found during implementation before final acceptance: the
first loop version stopped immediately whenever task state was
`waiting_approval`, which would also prevent a newly approved task from
resuming. That was repaired so `run_next` rechecks the authoritative approval
state before deciding whether execution may continue.

### 3.7 Checkpoints and rollback truthfulness

The runtime checkpoints logical agent state before work.

Read-only logical state can be rewound to a checkpoint.

The runtime deliberately refuses to claim that a logical rollback undoes an
external effect. If an effectful step completed after a checkpoint, rollback
raises an error and requires the owning adapter to expose a real compensating
action.

This distinction is load bearing. A state pointer moving backwards is not proof
that GitHub, Vercel, n8n, Drive, or another external system was reversed.

## 4. Artifacts in PR #24

Added:

```text
services/agent_runtime/__init__.py
services/agent_runtime/contracts.py
services/agent_runtime/learning.py
services/agent_runtime/planner.py
services/agent_runtime/runtime.py
services/agent_runtime/store.py
services/agent_runtime/tools.py
test_devon_agent_runtime.py
docs/devon/SYS_OPS_devon-agent-runtime-handover_v1_2026-08-24.md
```

No `services/devon` source file is modified by this PR.

No production DEVON API route or browser UI is wired to this runtime in v1.

## 5. Regression coverage

`test_devon_agent_runtime.py` verifies:

1. a READ tool executes without approval;
2. a WRITE tool stops for an exact human ruling;
3. an approved WRITE executes once;
4. re-running a completed task does not replay the effect;
5. refusal cancels without executing the effect;
6. a BLOCKED tool fails closed;
7. read-only logical state can rewind to a checkpoint;
8. logical rollback refuses to hide a completed external effect;
9. memories are searchable, inspectable, and deletable;
10. skills version when updated;
11. the LLM planner accepts only registered tools;
12. an invented tool name is rejected.

## 6. Verified code-head evidence

Verified code head before this handover-only commit:

```text
db8a8dfa7c63d7f80afcdec8749302e1100f53d7
```

GitHub Actions run:

```text
32751774194
```

Results:

- Standalone offline flagship: PASS
- Engine + cadence/security: PASS
- PostgreSQL 16 + pgvector API suite: PASS
- pytest: `634 passed, 4 warnings in 54.75s`
- Ruff: `All checks passed!`

The four warnings are existing Starlette/FastAPI deprecation warnings and did
not fail the suite.

A new CI run is required on the final handover-inclusive head before PR #24 is
called review-ready.

## 7. Deliberate v1 limits

This PR is the load-bearing runtime core. It is not Hermes feature parity.

Not implemented yet:

- durable production task store;
- durable production memory/skills store;
- production API routes for agent tasks;
- browser/phone Agent Tasks UI;
- Vercel Sandbox tool adapter wired into the runtime;
- GitHub agent adapter;
- n8n, Drive, EditForge, GPU, or deployment adapters;
- browser automation;
- subagent pool or parallel delegation;
- built-in scheduler/cron;
- MCP server discovery or MCP tool registry;
- autonomous skill generation or self-modification;
- streaming agent events;
- environment snapshots that can truly roll external effects back.

The in-memory stores are suitable for deterministic tests and single-process
development only. They are not sufficient for unattended production work.

## 8. Recommended next build sequence

After v1 merges and remains stable:

1. PostgreSQL durable task, checkpoint, memory, and skill stores.
2. Generic adapter interface plus the existing Vercel Sandbox/Operator
   capability as the first execution toolset.
3. GitHub adapter with reads automatic and writes routed through DEVON approval.
4. Browser automation adapter with domain and action policy.
5. Isolated subagent pool with bounded concurrency, budgets, and parent task
   accountability.
6. Scheduler with durable jobs and explicit delivery destinations.
7. MCP discovery/registration with per-tool risk declarations.
8. Browser/phone Agent Tasks UI showing plan, progress, observations,
   checkpoints, approvals, cost, and receipts.
9. Only after those layers are proven, add autonomous skill proposals. Skill
   publication or modification should remain reviewable and versioned.

## 9. Production status

PR #24 is a review branch only.

It does not change the currently deployed `/terminal` production path and has
not been merged into `main` as of this handover commit.

Merge requires explicit operator authorization after the final
handover-inclusive CI head is green.
