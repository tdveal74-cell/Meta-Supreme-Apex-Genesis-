---
title: DEVON Hermes Expansion Handover
type: SYS_OPS
version: 1
date: 2026-08-24
area: Systems
status: expansion-ready-pending-final-ci
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
branch: feat/devon-hermes-expansion
---

# DEVON Hermes Expansion Handover

## Delivered

1. **Subagents** — `SubAgentSpec` + `runtime.spawn_subagent` (WRITE, approval-gated). Bounded max_steps (1–12). Proposes child goal under parent; does not bypass receipts.
2. **Scheduler** — `ScheduledGoal` + `InMemoryScheduleStore` + `runtime.schedule_goal`. Due scan via `store.due()`. No silent effects.
3. **Browser** — `BrowserCapabilityAdapter` with allowlisted `browser.fetch` (READ) and approval-gated `browser.navigate` (WRITE). Offline stub safe for CI.
4. **Skill proposals** — `SkillProposalStore` drafts from completed observations; `decide(approve=True|False)`. Promotion is human-only.

## Wiring

- `build_tool_registry()` registers Operator, GitHub, Browser, Expansion tools
- Tool catalog exposes browser + expansion capability flags

## Governance

- `services/devon` untouched
- WRITE tools still stop at approval queue in AgentRuntime
- Effect receipts still apply when recorder is injected

## Limits of this slice

- Schedule store is process-local (durable DB schedule table is a later slice)
- Browser fetch uses offline stub unless a fetcher is injected
- Subagent spawn records the child plan; parent→child durable link table is a later slice
- Skill approve path does not yet auto-call learning.upsert_skill (explicit promote API next)
