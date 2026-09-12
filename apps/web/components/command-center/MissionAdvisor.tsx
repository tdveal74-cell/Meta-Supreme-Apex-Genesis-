"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";

type Approval = {
  request_id?: string;
  title?: string;
  what_happens?: string;
  blast_radius?: string;
  reversible?: boolean;
  expires_at?: string;
};

type TaskStep = {
  title?: string;
};

type AgentTask = {
  task_id?: string;
  goal?: string;
  state?: string;
  failure_reason?: string;
  current_step?: number;
  plan?: { steps?: TaskStep[] };
};

type AdvisorItem = {
  key: string;
  tier: string;
  headline: string;
  detail: string;
  action: string;
};

type AdvisorState = "locked" | "loading" | "online" | "degraded";

function readToken() {
  try {
    return localStorage.getItem("devon-chat-token") || sessionStorage.getItem("devon-chat-token") || "";
  } catch {
    return "";
  }
}

function taskHeadline(task: AgentTask) {
  return task.goal?.trim() || task.task_id || "DEVON task";
}

function taskDetail(task: AgentTask) {
  const state = String(task.state || "unknown").replaceAll("_", " ");
  if (task.failure_reason) return `${state}: ${task.failure_reason}`;
  const index = Number(task.current_step || 0);
  const step = task.plan?.steps?.[index]?.title;
  return step ? `${state}. Current step: ${step}` : `State: ${state}.`;
}

export function MissionAdvisor() {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<AdvisorState>("locked");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    try {
      setOpen(localStorage.getItem("devon-mission-advisor-open") === "1");
    } catch {
      // Persistence is optional.
    }
  }, []);

  const toggle = useCallback(() => {
    setOpen((current) => {
      const next = !current;
      try {
        localStorage.setItem("devon-mission-advisor-open", next ? "1" : "0");
      } catch {
        // Persistence is optional.
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    const token = readToken();
    if (!token) {
      setState("locked");
      setApprovals([]);
      setTasks([]);
      return;
    }

    setState("loading");
    const [approvalResult, taskResult] = await Promise.allSettled([
      fetch(`${API_BASE}/devon/approvals`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_BASE}/agent-tasks?limit=50&offset=0`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      }),
    ]);

    let failures = 0;
    if (approvalResult.status === "fulfilled" && approvalResult.value.ok) {
      const data = await approvalResult.value.json();
      setApprovals(Array.isArray(data?.pending) ? data.pending : []);
    } else {
      setApprovals([]);
      failures += 1;
    }

    if (taskResult.status === "fulfilled" && taskResult.value.ok) {
      const data = await taskResult.value.json();
      setTasks(Array.isArray(data) ? data : []);
    } else {
      setTasks([]);
      failures += 1;
    }

    setCheckedAt(new Date());
    setState(failures === 0 ? "online" : "degraded");
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    const onStorage = () => void refresh();
    window.addEventListener("storage", onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", onStorage);
    };
  }, [refresh]);

  const items = useMemo<AdvisorItem[]>(() => {
    const ranked: AdvisorItem[] = [];

    for (const approval of approvals) {
      ranked.push({
        key: `approval-${approval.request_id || approval.title}`,
        tier: "RULING",
        headline: approval.title || "Human ruling required",
        detail:
          approval.what_happens ||
          approval.blast_radius ||
          "An effect is paused at DEVON's approval boundary.",
        action: "Rule on the approval in Talk to DEVON or the gated terminal.",
      });
    }

    const statePriority: Record<string, number> = {
      waiting_approval: 0,
      failed: 1,
      running: 2,
      planned: 3,
      pending: 3,
    };

    const active = tasks
      .filter((task) => !["completed", "cancelled"].includes(String(task.state || "").toLowerCase()))
      .sort((a, b) => {
        const aRank = statePriority[String(a.state || "").toLowerCase()] ?? 4;
        const bRank = statePriority[String(b.state || "").toLowerCase()] ?? 4;
        return aRank - bRank;
      });

    for (const task of active) {
      const stateName = String(task.state || "ACTIVE").replaceAll("_", " ").toUpperCase();
      ranked.push({
        key: `task-${task.task_id || task.goal}`,
        tier: stateName,
        headline: taskHeadline(task),
        detail: taskDetail(task),
        action:
          String(task.state || "").toLowerCase() === "failed"
            ? "Inspect the failure before retrying or creating replacement work."
            : "Continue through DEVON so governance and receipts stay attached.",
      });
    }

    return ranked.slice(0, 3);
  }, [approvals, tasks]);

  const label =
    state === "locked"
      ? "ADVISOR LOCKED"
      : state === "loading"
        ? "ADVISOR CHECKING"
        : `ADVISOR ${items.length}`;

  return (
    <div className="fixed bottom-3 left-3 z-[60] sm:bottom-5 sm:left-5">
      {open && (
        <section className="mb-2 w-[min(92vw,430px)] border border-[#3e617c] bg-[#071016]/95 shadow-2xl shadow-black/50 backdrop-blur-xl">
          <header className="flex items-center justify-between gap-3 border-b border-[#22384a] px-4 py-3">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#c77b4a]">Operational advisor</p>
              <p className="mt-1 text-xs font-semibold text-white">Three things demanding attention</p>
            </div>
            <button
              type="button"
              onClick={() => void refresh()}
              className="border border-[#22384a] px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-[#93a6b5] hover:border-[#c77b4a]/60 hover:text-white"
            >
              Refresh
            </button>
          </header>

          {state === "locked" ? (
            <div className="px-4 py-5 text-xs leading-5 text-[#93a6b5]">
              Sign in through <span className="text-white">Talk to DEVON</span>. Advisor ranking uses the live task ledger and pending approvals, not the old static Mission Control brief.
            </div>
          ) : items.length === 0 ? (
            <div className="px-4 py-5">
              <p className="text-sm font-medium text-emerald-200">No active block surfaced.</p>
              <p className="mt-2 text-xs leading-5 text-[#6f8494]">This means the current approval queue and visible nonterminal task ledger are quiet. It is not a claim that every external system is healthy.</p>
            </div>
          ) : (
            <ol className="divide-y divide-[#22384a] px-4">
              {items.map((item, index) => (
                <li key={item.key} className="grid grid-cols-[28px_1fr] gap-3 py-3.5">
                  <span className="font-mono text-xs text-[#4fb3a5]">0{index + 1}</span>
                  <div className="min-w-0">
                    <span className="inline-flex border border-[#d4a017]/35 px-2 py-0.5 font-mono text-[8px] font-semibold uppercase tracking-[0.12em] text-[#d4a017]">{item.tier}</span>
                    <p className="mt-2 text-sm font-semibold leading-5 text-white">{item.headline}</p>
                    <p className="mt-1 text-[11px] leading-5 text-[#93a6b5]">{item.detail}</p>
                    <p className="mt-2 font-mono text-[10px] leading-4 text-[#4fb3a5]">Next: {item.action}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}

          <footer className="border-t border-[#22384a] px-4 py-2.5 text-[9px] leading-4 text-[#526979]">
            Ranked by operational blocking state and required human ruling, not by invented business value.
            {state === "degraded" ? " One source failed to read." : ""}
            {checkedAt ? ` Checked ${checkedAt.toLocaleTimeString()}.` : ""}
          </footer>
        </section>
      )}

      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-2 border border-[#4fb3a5]/45 bg-[#091017]/95 px-3 py-2.5 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-[#8fd5cb] shadow-xl shadow-black/40 backdrop-blur transition hover:bg-[#4fb3a5]/10"
        aria-expanded={open}
      >
        <span
          className={`h-2 w-2 rounded-full ${
            state === "online"
              ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.7)]"
              : state === "loading"
                ? "bg-amber-300 animate-pulse"
                : state === "degraded"
                  ? "bg-amber-400"
                  : "bg-sky-300"
          }`}
        />
        {label}
      </button>
    </div>
  );
}
