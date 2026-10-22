// All effects remain on the existing authenticated, tenant-scoped runtime.
// No retries: a lost write response may still represent a committed request.
export type DispatchTask = {
  task_id: string; goal: string; state: string; current_step: number;
  plan: { steps: { title?: string; approval_request_id?: string; tool_call?: unknown }[] };
  context?: { max_steps?: number; parent_task_id?: string };
  final_summary?: string; failure_reason?: string;
};

export function parseDispatchTask(value: unknown): DispatchTask {
  const t = value as DispatchTask;
  if (!t || typeof t.task_id !== "string" || !t.task_id || typeof t.goal !== "string" ||
      typeof t.state !== "string" || !Number.isInteger(t.current_step) ||
      !t.plan || !Array.isArray(t.plan.steps)) throw new Error("The API returned an unreadable task. Refresh before continuing.");
  return t;
}

export function dispatchGoal(goal: string, parent: string, maxSteps: number) {
  const text = goal.trim();
  if (!text || text.length > 20_000) throw new Error("Enter a goal of 1 to 20,000 characters.");
  if (!Number.isInteger(maxSteps) || maxSteps < 1 || maxSteps > 12) throw new Error("Choose 1 to 12 steps.");
  return parent
    ? { path: "/agent-expansion/subagents", body: { goal: text, parent_task_id: parent, max_steps: maxSteps, inherit_context_keys: [] } }
    : { path: "/agent-tasks", body: { goal: text, context: { max_steps: maxSteps } } };
}

export function taskRunLimit(task: DispatchTask) {
  const n = task.context?.max_steps;
  return typeof n === "number" && Number.isInteger(n) && n >= 1 && n <= 12 ? n : 8;
}

export async function dispatchRequest(base: string, token: string, path: string, body?: unknown,
  idempotencyKey?: string, fetcher: typeof fetch = fetch) {
  if (!token) throw new Error("Sign in on the Command Center first.");
  const response = await fetcher(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session expired. Sign in again on the Command Center.");
    if (response.status === 403) throw new Error("This account is not permitted to perform that action.");
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `Request refused (HTTP ${response.status}).`);
  }
  return response.json();
}
