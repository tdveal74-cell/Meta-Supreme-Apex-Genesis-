// The wire shapes the DEVON API actually sends, read off the code rather than
// guessed at.
//
// GET /api/v1/agent-tasks returns a bare JSON array of AgentTask.to_dict()
// (app/api/v1/agent_tasks.py list_tasks, which maps every row through
// _task_view). The keys below are that dict, one for one, from
// services/agent_runtime/contracts.py.
//
// Two things this shape does NOT carry, and the matrix must not invent:
//   1. No lease field. The execution lease lives on the agent_tasks columns
//      lease_token, lease_owner and lease_expires_at plus the agent_task_runs
//      table (database/schemas/007_agent_task_execution_leases.sql), and no
//      route in docs/devon/hermes-surface.json exposes any of them.
//   2. No agent identity. A task carries a goal, a plan and a state. Nothing
//      on it names which agent owns it.

// TaskState in services/agent_runtime/contracts.py. Six values, lower case.
// The v1 control plane spec guessed IDLE, THINKING, EXECUTING, BLOCKED and
// FAILED; only FAILED has a counterpart here, and it is spelled "failed".
export const TASK_STATES = [
  "planned",
  "running",
  "waiting_approval",
  "completed",
  "failed",
  "cancelled",
] as const;

export type TaskState = (typeof TASK_STATES)[number];

// StepState in the same module. Six values, and note it adds "skipped" where
// TaskState has "cancelled".
export const STEP_STATES = [
  "planned",
  "running",
  "waiting_approval",
  "completed",
  "failed",
  "skipped",
] as const;

export type StepState = (typeof STEP_STATES)[number];

// ToolRisk in the same module.
export const TOOL_RISKS = ["read", "write", "high_impact", "blocked"] as const;

export type ToolRisk = (typeof TOOL_RISKS)[number];

export type ToolCallView = {
  name: string;
  arguments: Record<string, unknown>;
  reason: string;
  expected_outcome: string;
};

export type PlanStepView = {
  step_id: string;
  title: string;
  tool_call: ToolCallView;
  state: string;
  approval_request_id: string | null;
};

export type AgentPlanView = {
  goal: string;
  steps: PlanStepView[];
  completion_criteria: string[];
};

export type ObservationView = {
  step_id: string;
  ok: boolean;
  output: string;
  error: string;
  metadata: Record<string, unknown>;
  observed_at: string;
};

export type TaskCheckpointView = {
  checkpoint_id: string;
  task_id: string;
  current_step: number;
  step_states: string[][];
  observation_count: number;
  reason: string;
  created_at: string;
};

export type AgentTaskView = {
  task_id: string;
  goal: string;
  context: Record<string, unknown>;
  plan: AgentPlanView;
  state: string;
  current_step: number;
  observations: ObservationView[];
  checkpoints: TaskCheckpointView[];
  final_summary: string;
  failure_reason: string;
  created_at: string;
  updated_at: string;
};

// One entry of the `tools` array from GET /api/v1/agent-tasks/tools, which is
// ToolRegistry.describe() and therefore ToolSpec.to_dict().
export type ToolCatalogEntry = {
  name: string;
  description: string;
  risk: string;
  approval_required: boolean;
  reversible: boolean;
  blast_radius: string;
  parameters: string[];
};

// The whole catalog response. Only `tools` is read here; the sibling keys
// (operator, github, browser, council, expansion, execution) are what
// CapabilityDock already reads, and `execution.lease_seconds` is the lease
// duration setting, not a lease age for any task.
export type ToolCatalogResponse = {
  tools?: ToolCatalogEntry[];
  execution?: {
    shared_task_leases?: boolean;
    lease_seconds?: number;
  };
};

export function isTaskState(value: string): value is TaskState {
  return (TASK_STATES as readonly string[]).includes(value);
}

export function isToolRisk(value: string): value is ToolRisk {
  return (TOOL_RISKS as readonly string[]).includes(value);
}
