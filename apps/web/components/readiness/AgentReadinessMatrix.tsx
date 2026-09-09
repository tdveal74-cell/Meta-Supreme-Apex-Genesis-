"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { API_BASE } from "@/lib/api-base";
import { PINNED_TOOL_COUNT } from "./pinned-tool-risk";
import {
  TASK_STATES,
  isTaskState,
  type AgentTaskView,
  type TaskState,
  type ToolCatalogEntry,
  type ToolCatalogResponse,
  type ToolRisk,
} from "./readiness-types";
import {
  RISK_LABEL,
  ageLabel,
  buildCatalogIndex,
  summarizeTaskRisk,
  type RiskSource,
  type TaskRiskSummary,
} from "./risk-resolution";

/**
 * Agent readiness matrix.
 *
 * The v1 control plane spec (docs/devon/SYS_SPEC_devon-control-plane-workspace
 * _v1_2026-09-08.md, Tier 2) lists this as "not built", puts it at
 * apps/web/components/readiness/, and says the reads would come from
 * /api/v1/agent-tasks and the agent_task_runs lease rows. Two of those three
 * turned out to be usable and the third did not, so this component says which:
 *
 *   GET /api/v1/agent-tasks        supplies the rows, their state, their plan
 *                                  and their timestamps.
 *   GET /api/v1/agent-tasks/tools  supplies the live risk class per tool name,
 *                                  which is how the risk column is filled.
 *   the lease rows                 are NOT reachable. agent_tasks carries
 *                                  lease_token, lease_owner and
 *                                  lease_expires_at, and agent_task_runs
 *                                  carries the fenced run history, but
 *                                  AgentTask.to_dict() serialises none of it
 *                                  and no route in
 *                                  docs/devon/hermes-surface.json exposes it.
 *                                  So the lease age column is labelled
 *                                  unavailable in every row rather than filled
 *                                  with the last update time wearing a lease's
 *                                  name.
 *
 * The spec also guessed the states were IDLE, THINKING, EXECUTING, BLOCKED and
 * FAILED. The code defines planned, running, waiting_approval, completed,
 * failed and cancelled. This renders the six the code defines.
 *
 * Three display states are all real and all distinct: a failed request says so
 * and shows its status, a successful request that returned nothing says the
 * list was empty, and neither one is drawn as a grid of blanks.
 */

export type AgentReadinessMatrixProps = {
  /**
   * Bearer token to use. When omitted the component reads the same
   * devon-chat-token that the rest of the workspace stores on the device, and
   * shows a locked panel when there is none.
   */
  token?: string;
  /**
   * Refresh interval in milliseconds. Pass 0 to fetch once and never poll.
   * Default 20000.
   */
  pollMs?: number;
  /**
   * Page size handed to GET /agent-tasks. The route clamps to 1..100, so this
   * does too. Default 50, which is the route's own default.
   */
  limit?: number;
  /** Extra classes on the outer section. */
  className?: string;
};

type FetchPhase = "locked" | "loading" | "ready" | "error";

type RequestFailure = {
  status: number | null;
  statusText: string;
  detail: string;
};

type MatrixRow = {
  task: AgentTaskView;
  state: TaskState | null;
  risk: TaskRiskSummary;
};

const STATE_ORDER: readonly TaskState[] = [
  "running",
  "waiting_approval",
  "planned",
  "failed",
  "cancelled",
  "completed",
];

const STATE_LABEL: Record<TaskState, string> = {
  planned: "PLANNED",
  running: "RUNNING",
  waiting_approval: "WAITING APPROVAL",
  completed: "COMPLETED",
  failed: "FAILED",
  cancelled: "CANCELLED",
};

const STATE_CLASS: Record<TaskState, string> = {
  running: "border-emerald-400/40 bg-emerald-400/[0.08] text-emerald-200",
  waiting_approval: "border-amber-400/40 bg-amber-400/[0.08] text-amber-200",
  planned: "border-sky-400/35 bg-sky-400/[0.06] text-sky-200",
  failed: "border-rose-400/40 bg-rose-400/[0.08] text-rose-200",
  cancelled: "border-[#3e617c] bg-white/[0.03] text-[#93a6b5]",
  completed: "border-teal-400/30 bg-teal-400/[0.05] text-teal-100/85",
};

const RISK_CLASS: Record<ToolRisk, string> = {
  read: "border-sky-400/35 bg-sky-400/[0.06] text-sky-200",
  write: "border-amber-400/40 bg-amber-400/[0.08] text-amber-200",
  high_impact: "border-rose-400/45 bg-rose-400/[0.09] text-rose-200",
  blocked: "border-violet-400/40 bg-violet-400/[0.08] text-violet-200",
};

const UNAVAILABLE = "not available";

function tokenFromDevice(): string {
  try {
    return (
      localStorage.getItem("devon-chat-token") ||
      sessionStorage.getItem("devon-chat-token") ||
      ""
    );
  } catch {
    return "";
  }
}

async function describeFailure(response: Response): Promise<RequestFailure> {
  let detail = "";
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (body !== undefined) {
      detail = JSON.stringify(body);
    }
  } catch {
    detail = "";
  }
  return {
    status: response.status,
    statusText: response.statusText || "",
    detail,
  };
}

function transportFailure(reason: unknown): RequestFailure {
  const message =
    reason instanceof Error ? reason.message : String(reason ?? "unknown error");
  return { status: null, statusText: "no HTTP response", detail: message };
}

function Chip({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] ${className}`}
    >
      {children}
    </span>
  );
}

function Unavailable({ title }: { title: string }) {
  return (
    <span
      title={title}
      className="font-mono text-[9px] uppercase tracking-[0.1em] text-[#526979]"
    >
      {UNAVAILABLE}
    </span>
  );
}

function SourceMark({ source }: { source: RiskSource }) {
  if (source === "catalog") {
    return (
      <span title="Risk read live from GET /agent-tasks/tools" className="text-[9px] text-emerald-300/70">
        live
      </span>
    );
  }
  if (source === "manifest") {
    return (
      <span
        title="Live tool catalog unavailable. Risk read from the pinned docs/devon/hermes-surface.json manifest"
        className="text-[9px] text-amber-300/70"
      >
        pinned
      </span>
    );
  }
  return (
    <span
      title="Neither the live catalog nor the pinned manifest knows this tool name"
      className="text-[9px] text-[#526979]"
    >
      unknown
    </span>
  );
}

export function AgentReadinessMatrix({
  token: tokenProp,
  pollMs = 20000,
  limit = 50,
  className = "",
}: AgentReadinessMatrixProps) {
  const [phase, setPhase] = useState<FetchPhase>("loading");
  const [tasks, setTasks] = useState<AgentTaskView[]>([]);
  const [catalogTools, setCatalogTools] = useState<ToolCatalogEntry[] | null>(null);
  const [catalogFailure, setCatalogFailure] = useState<RequestFailure | null>(null);
  const [taskFailure, setTaskFailure] = useState<RequestFailure | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const pageSize = Math.max(1, Math.min(Math.trunc(limit) || 50, 100));

  const refresh = useCallback(async () => {
    const token = tokenProp || tokenFromDevice();
    if (!token) {
      setPhase("locked");
      setTasks([]);
      setCatalogTools(null);
      setCatalogFailure(null);
      setTaskFailure(null);
      return;
    }

    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;

    setPhase((current) => (current === "ready" ? "ready" : "loading"));

    const init: RequestInit = {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    };

    const [tasksResult, toolsResult] = await Promise.allSettled([
      fetch(`${API_BASE}/agent-tasks?limit=${pageSize}&offset=0`, init),
      fetch(`${API_BASE}/agent-tasks/tools`, init),
    ]);

    if (controller.signal.aborted) return;

    // The tool catalog is the risk column's live source. Losing it degrades the
    // risk provenance to the pinned manifest; it does not invalidate the rows.
    if (toolsResult.status === "fulfilled" && toolsResult.value.ok) {
      const body = (await toolsResult.value.json()) as ToolCatalogResponse;
      setCatalogTools(Array.isArray(body?.tools) ? body.tools : []);
      setCatalogFailure(null);
    } else {
      setCatalogTools(null);
      setCatalogFailure(
        toolsResult.status === "fulfilled"
          ? await describeFailure(toolsResult.value)
          : transportFailure(toolsResult.reason),
      );
    }

    // The task list is the matrix. Without it there is nothing true to draw.
    if (tasksResult.status === "fulfilled" && tasksResult.value.ok) {
      const body = await tasksResult.value.json();
      setTasks(Array.isArray(body) ? (body as AgentTaskView[]) : []);
      setTaskFailure(null);
      setPhase("ready");
    } else {
      setTasks([]);
      setTaskFailure(
        tasksResult.status === "fulfilled"
          ? await describeFailure(tasksResult.value)
          : transportFailure(tasksResult.reason),
      );
      setPhase("error");
    }

    setCheckedAt(new Date());
    setNow(Date.now());
  }, [pageSize, tokenProp]);

  useEffect(() => {
    setNow(Date.now());
    void refresh();
    const interval = pollMs > 0 ? window.setInterval(() => void refresh(), pollMs) : 0;
    const clock = window.setInterval(() => setNow(Date.now()), 5000);
    const onStorage = () => void refresh();
    window.addEventListener("storage", onStorage);
    return () => {
      if (interval) window.clearInterval(interval);
      window.clearInterval(clock);
      window.removeEventListener("storage", onStorage);
      inFlight.current?.abort();
    };
  }, [pollMs, refresh]);

  const catalogIndex = useMemo(() => buildCatalogIndex(catalogTools), [catalogTools]);

  const rows = useMemo<MatrixRow[]>(
    () =>
      tasks.map((task) => ({
        task,
        state: isTaskState(task.state) ? task.state : null,
        risk: summarizeTaskRisk(task, catalogIndex),
      })),
    [tasks, catalogIndex],
  );

  // Every state the code defines gets a count, including the zeros, so a state
  // with no work reads as measured rather than as missing.
  const counts = useMemo(() => {
    const tally = new Map<TaskState, number>();
    for (const state of TASK_STATES) tally.set(state, 0);
    let unrecognized = 0;
    for (const row of rows) {
      if (row.state) {
        tally.set(row.state, (tally.get(row.state) || 0) + 1);
      } else {
        unrecognized += 1;
      }
    }
    return { tally, unrecognized };
  }, [rows]);

  const groups = useMemo(() => {
    const byState = STATE_ORDER.map((state) => ({
      state,
      label: STATE_LABEL[state],
      rows: rows.filter((row) => row.state === state),
    })).filter((group) => group.rows.length > 0);

    const strays = rows.filter((row) => row.state === null);
    if (strays.length > 0) {
      byState.push({
        state: "planned",
        label: "STATE NOT IN THE TASKSTATE ENUM",
        rows: strays,
      });
    }
    return byState;
  }, [rows]);

  const clock = now ?? Date.now();

  return (
    <section
      className={`border border-[#3e617c] bg-[#071016]/95 text-[#93a6b5] shadow-2xl shadow-black/40 ${className}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[#22384a] px-4 py-3">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#c77b4a]">
            DEVON agent readiness
          </p>
          <h2 className="mt-1 text-sm font-semibold text-white">Task state and tool risk matrix</h2>
          <p className="mt-1 font-mono text-[9px] leading-4 text-[#526979]">
            Rows from GET /agent-tasks. Risk from GET /agent-tasks/tools, falling back to the{" "}
            {PINNED_TOOL_COUNT} tool manifest pinned in docs/devon/hermes-surface.json.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {phase === "loading" && (
            <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-amber-300">
              reading
            </span>
          )}
          <button
            type="button"
            onClick={() => void refresh()}
            className="border border-[#22384a] px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-[#93a6b5] transition hover:border-[#c77b4a]/60 hover:text-white"
          >
            Refresh
          </button>
        </div>
      </header>

      {phase === "locked" && (
        <div className="px-4 py-6 text-xs leading-5">
          <p className="text-white">No token on this device.</p>
          <p className="mt-1 text-[#93a6b5]">
            GET /agent-tasks is owner scoped and authenticated. Sign in once through Talk to DEVON,
            or pass a token to this component, and the matrix will read. Nothing is drawn until
            then, because an empty grid would read as no work rather than as no access.
          </p>
        </div>
      )}

      {phase === "loading" && tasks.length === 0 && (
        <div className="px-4 py-6 text-xs leading-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-amber-300">
            Reading the task list
          </p>
          <p className="mt-1 text-[#526979]">
            No rows are shown while the request is open. A blank matrix here would be a guess.
          </p>
        </div>
      )}

      {phase === "error" && taskFailure && (
        <div className="px-4 py-6 text-xs leading-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-rose-300">
            The request for GET /agent-tasks failed
          </p>
          <p className="mt-2 border border-rose-400/30 bg-rose-400/[0.06] px-3 py-2 font-mono text-[10px] text-rose-100">
            {taskFailure.status === null
              ? `no HTTP response: ${taskFailure.detail}`
              : `${taskFailure.status} ${taskFailure.statusText}${taskFailure.detail ? `: ${taskFailure.detail}` : ""}`}
          </p>
          <p className="mt-2 text-[#93a6b5]">
            The matrix is not drawn. Nothing is known about agent readiness from a failed read, and
            an empty grid would claim otherwise.
            {taskFailure.status === 401
              ? " A 401 means the token on this device is missing or expired; sign in again."
              : ""}
          </p>
        </div>
      )}

      {phase === "ready" && (
        <div className="px-4 py-4">
          <div className="grid grid-cols-2 gap-px overflow-hidden border border-[#22384a] bg-[#22384a] sm:grid-cols-3 lg:grid-cols-6">
            {TASK_STATES.map((state) => (
              <div key={state} className="bg-[#0b141b] px-3 py-2.5">
                <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-[#6f8494]">
                  {STATE_LABEL[state]}
                </p>
                <p className="mt-1 font-mono text-base text-white">{counts.tally.get(state) ?? 0}</p>
              </div>
            ))}
          </div>

          {counts.unrecognized > 0 && (
            <p className="mt-2 font-mono text-[9px] text-amber-300">
              {counts.unrecognized} task(s) reported a state outside the six TaskState values. They
              are grouped separately below and their state is printed verbatim.
            </p>
          )}

          {rows.length === 0 ? (
            <div className="mt-4 border border-[#22384a] bg-[#0b141b] px-3 py-5 text-xs leading-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-sky-200">
                The request succeeded and returned zero tasks
              </p>
              <p className="mt-1 text-[#526979]">
                This is an empty list from a 200, not a failed read and not a placeholder. The
                authenticated owner has no agent tasks in the first {pageSize} rows.
              </p>
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto border border-[#22384a]">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <thead>
                  <tr className="bg-[#0b141b] font-mono text-[8px] uppercase tracking-[0.14em] text-[#6f8494]">
                    <th className="px-3 py-2 font-normal">State</th>
                    <th className="px-3 py-2 font-normal">Task</th>
                    <th className="px-3 py-2 font-normal">Step</th>
                    <th className="px-3 py-2 font-normal">Peak tool risk</th>
                    <th className="px-3 py-2 font-normal">Approval</th>
                    <th className="px-3 py-2 font-normal" title="No route exposes the execution lease">
                      Lease age ({UNAVAILABLE})
                    </th>
                    <th className="px-3 py-2 font-normal">Last update</th>
                  </tr>
                </thead>
                {groups.map((group) => (
                  <tbody key={group.label} className="border-t border-[#22384a]">
                    <tr>
                      <td
                        colSpan={7}
                        className="bg-black/25 px-3 py-1.5 font-mono text-[8px] uppercase tracking-[0.18em] text-[#c77b4a]"
                      >
                        {group.label} ({group.rows.length})
                      </td>
                    </tr>
                    {group.rows.map(({ task, state, risk }) => {
                      const steps = task.plan?.steps?.length ?? 0;
                      const activeStep =
                        task.current_step >= 0 && task.current_step < steps
                          ? task.plan.steps[task.current_step]
                          : null;
                      return (
                        <tr key={task.task_id} className="border-t border-[#22384a]/60 align-top">
                          <td className="px-3 py-2.5">
                            {state ? (
                              <Chip className={STATE_CLASS[state]}>{STATE_LABEL[state]}</Chip>
                            ) : (
                              <Chip className="border-amber-400/40 bg-amber-400/[0.08] text-amber-200">
                                {String(task.state || "empty")}
                              </Chip>
                            )}
                          </td>
                          <td className="max-w-[24rem] px-3 py-2.5">
                            <p className="truncate text-[11px] text-white" title={task.goal}>
                              {task.goal || "(no goal text)"}
                            </p>
                            <p className="mt-0.5 font-mono text-[9px] text-[#526979]">
                              {task.task_id}
                            </p>
                            {task.failure_reason ? (
                              <p className="mt-0.5 text-[9px] text-rose-300/80" title={task.failure_reason}>
                                {task.failure_reason}
                              </p>
                            ) : null}
                          </td>
                          <td className="px-3 py-2.5">
                            <p className="font-mono text-[10px] text-[#93a6b5]">
                              {steps === 0 ? "no plan steps" : `${Math.min(task.current_step + 1, steps)} of ${steps}`}
                            </p>
                            {activeStep ? (
                              <p
                                className="mt-0.5 max-w-[14rem] truncate text-[9px] text-[#526979]"
                                title={`${activeStep.title} (${activeStep.state})`}
                              >
                                {activeStep.title}
                              </p>
                            ) : null}
                          </td>
                          <td className="px-3 py-2.5">
                            {risk.peak?.risk ? (
                              <div className="flex flex-col gap-1">
                                <div className="flex items-center gap-1.5">
                                  <Chip className={RISK_CLASS[risk.peak.risk]}>
                                    {RISK_LABEL[risk.peak.risk]}
                                  </Chip>
                                  <SourceMark source={risk.peak.source} />
                                </div>
                                <p
                                  className="max-w-[14rem] truncate font-mono text-[9px] text-[#526979]"
                                  title={risk.peak.blastRadius || risk.peak.name}
                                >
                                  {risk.peak.name}
                                </p>
                              </div>
                            ) : risk.toolNames.length === 0 ? (
                              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[#526979]">
                                no tool call planned
                              </span>
                            ) : (
                              <Unavailable
                                title={`Not in the live catalog or the pinned manifest: ${risk.unresolved.join(", ")}`}
                              />
                            )}
                            {risk.peak?.risk && risk.unresolved.length > 0 ? (
                              <p
                                className="mt-1 font-mono text-[9px] text-amber-300/80"
                                title={risk.unresolved.join(", ")}
                              >
                                {risk.unresolved.length} tool name(s) unresolved
                              </p>
                            ) : null}
                          </td>
                          <td className="px-3 py-2.5">
                            {risk.toolNames.length === 0 ? (
                              <span className="font-mono text-[9px] text-[#526979]">not applicable</span>
                            ) : risk.peak?.risk ? (
                              <span
                                className={`font-mono text-[9px] uppercase tracking-[0.1em] ${
                                  risk.approvalRequired ? "text-amber-200" : "text-[#6f8494]"
                                }`}
                              >
                                {risk.approvalRequired ? "human gated" : "no gate"}
                              </span>
                            ) : (
                              <Unavailable title="Approval follows the tool risk, and no risk resolved" />
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <Unavailable title="AgentTask.to_dict() carries no lease field, and no route exposes agent_tasks.lease_expires_at or the agent_task_runs rows" />
                          </td>
                          <td className="px-3 py-2.5">
                            <p className="font-mono text-[10px] text-[#93a6b5]">
                              {ageLabel(task.updated_at, clock) ?? UNAVAILABLE}
                            </p>
                            <p className="mt-0.5 font-mono text-[9px] text-[#526979]">
                              created {ageLabel(task.created_at, clock) ?? UNAVAILABLE} ago
                            </p>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                ))}
              </table>
            </div>
          )}

          <div className="mt-3 space-y-1.5 border-t border-[#22384a] pt-3 font-mono text-[9px] leading-4 text-[#526979]">
            <p>
              <span className="text-[#6f8494]">Lease age is {UNAVAILABLE}.</span> The lease columns
              exist (agent_tasks.lease_token, lease_owner, lease_expires_at, and the agent_task_runs
              rows from schema 007), but AgentTask.to_dict() serialises none of them and no agent
              route publishes them. Last update is task.updated_at and is not a lease age. Filling
              the column from it would be a fabricated number.
            </p>
            <p>
              <span className="text-[#6f8494]">Agent identity is {UNAVAILABLE}.</span> One row is one
              task. A task carries a goal, a plan, a state and timestamps; nothing on it names an
              agent, so the matrix does not claim a per agent view.
            </p>
            <p>
              <span className="text-[#6f8494]">Risk is per task, not per step.</span> Peak tool risk
              is the highest declared risk among the distinct tools the plan names, ranked blocked
              above high impact above write above read. Approval follows ToolSpec.approval_required,
              which is true for write and high impact.
            </p>
            {catalogFailure && (
              <p className="text-amber-300/85">
                The live tool catalog read failed (
                {catalogFailure.status === null
                  ? `no HTTP response: ${catalogFailure.detail}`
                  : `${catalogFailure.status} ${catalogFailure.statusText}`}
                ), so every risk below is marked pinned and comes from the manifest rather than from
                the running API.
              </p>
            )}
            {checkedAt && <p>Checked {checkedAt.toLocaleTimeString()}. Page size {pageSize}.</p>}
          </div>
        </div>
      )}
    </section>
  );
}

export default AgentReadinessMatrix;
