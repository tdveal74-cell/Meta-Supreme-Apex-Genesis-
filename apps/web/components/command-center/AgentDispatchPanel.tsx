"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { API_BASE } from "@/lib/api-base";
import { dispatchGoal, dispatchRequest, parseDispatchTask, taskRunLimit, type DispatchTask } from "@/lib/agent-dispatch";

type Pending = { taskId: string; requestId: string; token: string; step: DispatchTask["plan"]["steps"][number] };
function readToken() {
  try { return localStorage.getItem("devon-chat-token") || sessionStorage.getItem("devon-chat-token") || ""; }
  catch { return ""; }
}
const button = "rounded-lg border border-white/20 px-3 py-2 text-sm disabled:opacity-40";

export function AgentDispatchPanel() {
  const [tasks, setTasks] = useState<DispatchTask[]>([]);
  const [goal, setGoal] = useState("");
  const [parent, setParent] = useState("");
  const [steps, setSteps] = useState(8);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [message, setMessage] = useState("Reading your tasks.");
  const [pending, setPending] = useState<Pending | null>(null);
  const ownerToken = useRef("");
  const lock = useRef(false);
  const currentToken = () => {
    const token = readToken();
    if (!token || token !== ownerToken.current) throw new Error("Your session changed. Refresh the task list before continuing.");
    return token;
  };
  const putTask = (task: DispatchTask) => setTasks(old => [task, ...old.filter(t => t.task_id !== task.task_id)].slice(0, 50));
  const refresh = useCallback(async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setLoaded(false);
    try {
      const token = readToken();
      if (ownerToken.current !== token) { setTasks([]); setPending(null); setParent(""); }
      ownerToken.current = token;
      const data = await dispatchRequest(API_BASE, token, "/agent-tasks?limit=50&offset=0");
      if (!Array.isArray(data)) throw new Error("Task list is unreadable.");
      setTasks(data.map(parseDispatchTask)); setLoaded(true);
      setMessage("Up to 50 recent tasks. Creating a task plans it; Run starts it.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Task read failed."); }
    finally { lock.current = false; setBusy(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (lock.current || !loaded || pending) return;
    lock.current = true; setBusy(true);
    try {
      const request = dispatchGoal(goal, parent, steps);
      const task = parseDispatchTask(await dispatchRequest(API_BASE, currentToken(), request.path, request.body));
      putTask(task); setGoal(""); setMessage("Task created and planned. Review it before pressing Run.");
    } catch (error) {
      setLoaded(false);
      setMessage(`${error instanceof Error ? error.message : "Creation failed."} A request may have arrived. Refresh and inspect the list before trying again.`);
    } finally { lock.current = false; setBusy(false); }
  }
  async function run(task: DispatchTask) {
    if (lock.current || !loaded || (pending && pending.taskId !== task.task_id)) return;
    lock.current = true; setBusy(true);
    try {
      const result = await dispatchRequest(API_BASE, currentToken(), `/agent-tasks/${encodeURIComponent(task.task_id)}/run`,
        { max_steps: taskRunLimit(task) }, `dispatch-${crypto.randomUUID()}`);
      const updated = parseDispatchTask(result.task); putTask(updated);
      const step = updated.plan.steps[updated.current_step];
      if (updated.state === "waiting_approval" && step?.approval_request_id && typeof result.approval_token === "string" && result.approval_token) {
        setPending({ taskId: updated.task_id, requestId: step.approval_request_id, token: result.approval_token, step });
        setMessage("An effect requires your ruling. Keep this tab open until you decide.");
      } else {
        if (updated.state !== "waiting_approval" || pending?.requestId !== step?.approval_request_id) setPending(null);
        setMessage(updated.state === "waiting_approval" ? "Waiting on the existing approval. Any token already held in this panel is preserved." : `Task state: ${updated.state}.`);
      }
    } catch (error) {
      setLoaded(false);
      setMessage(`${error instanceof Error ? error.message : "Run failed."} No retry was sent. Refresh and inspect the task before another run.`);
    } finally { lock.current = false; setBusy(false); }
  }
  async function decide(decision: "approve" | "refuse") {
    if (lock.current || !pending) return;
    lock.current = true; setBusy(true);
    try {
      const result = await dispatchRequest(API_BASE, currentToken(), "/devon/approvals/decide",
        { request_id: pending.requestId, token: pending.token, decision });
      if (result.ok !== true || result.state !== (decision === "approve" ? "approved" : "refused") || result.approved !== (decision === "approve")) throw new Error("The ruling was not accepted. Refresh the task before continuing.");
      setPending(null); setMessage("Ruling recorded. Press Run on that task to continue.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Ruling failed. No automatic retry was sent."); }
    finally { lock.current = false; setBusy(false); }
  }
  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-7 sm:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Agent dispatch</h1>
        <div className="flex gap-3"><Link href="/command-center" className={button}>Sign in / Command Center</Link><button className={button} onClick={() => void refresh()} disabled={busy}>Refresh tasks</button></div>
      </div>
      <p className="text-sm text-white/65">Give DEVON a goal or create a child agent under one of your tasks. Agents use the configured model and tools. Read steps can spend provider tokens. Writes and high-impact tools stop for your approval.</p>
      <p role="status" className="rounded-lg border border-white/15 p-3 text-sm">{message}</p>
      <form onSubmit={create} className="space-y-3 rounded-xl border border-white/15 p-4">
        <label className="block text-sm">Goal<textarea value={goal} onChange={e => setGoal(e.target.value)} required maxLength={20000} rows={3} className="mt-2 w-full rounded bg-white/5 p-3" /></label>
        <div className="flex flex-wrap gap-4">
          <label className="text-sm">Parent task<select value={parent} onChange={e => setParent(e.target.value)} className="ml-2 max-w-xs rounded bg-[#101923] p-2"><option value="">New top-level task</option>{tasks.map(t => <option key={t.task_id} value={t.task_id}>{t.goal.slice(0, 70)}</option>)}</select></label>
          <label className="text-sm">Step limit<input type="number" min={1} max={12} value={steps} onChange={e => setSteps(Number(e.target.value))} className="ml-2 w-16 rounded bg-white/5 p-2" /></label>
          <button className={button} disabled={busy || !loaded || !goal.trim() || !!pending}>Create planned {parent ? "child agent" : "task"}</button>
        </div>
      </form>
      {pending && <section aria-label="Agent approval" className="space-y-3 rounded-xl border border-amber-400/50 p-4">
        <h2 className="font-semibold">Rule on this step</h2><p>{pending.step.title}</p>
        <pre className="overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(pending.step.tool_call, null, 2)}</pre>
        <p className="text-sm text-white/65">This decision applies only to request {pending.requestId}. It does not approve the rest of the task. If a ruling response was lost, use Run / continue task below to resume it. Run may execute a step whose approval was already recorded.</p>
        <button className={button} disabled={busy} onClick={() => void decide("approve")}>Approve this step</button>{" "}<button className={button} disabled={busy} onClick={() => void decide("refuse")}>Refuse this step</button>
      </section>}
      <div className="space-y-3">{loaded && tasks.length === 0 && <p>No tasks returned for this account.</p>}{tasks.map(task => <section key={task.task_id} className="space-y-2 rounded-xl border border-white/15 p-4">
        <h2 className="font-medium">{task.goal}</h2><p className="text-xs text-white/60">{task.task_id} · {task.state}{task.context?.parent_task_id ? ` · child of ${task.context.parent_task_id}` : ""}</p>
        <details><summary className="cursor-pointer text-sm">Review plan and result</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify({ plan: task.plan, summary: task.final_summary, failure: task.failure_reason }, null, 2)}</pre></details>
        <button className={button} disabled={busy || !loaded || (!!pending && pending.taskId !== task.task_id) || !["planned", "waiting_approval", "running"].includes(task.state)} onClick={() => void run(task)}>Run / continue task</button>
      </section>)}</div>
    </main>
  );
}
