"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";

type ToolCatalog = {
  operator?: { enabled?: boolean; configured?: boolean };
  github?: { configured?: boolean; allowed_repositories?: string[] };
  browser?: { enabled?: boolean; live_fetch?: boolean; navigate_requires_approval?: boolean };
  council?: { enabled?: boolean; agents?: string[]; observation_reaches_approval_cards?: boolean };
  expansion?: { scheduler?: boolean; subagents?: boolean; skill_proposals?: boolean; materialize_due_schedules?: boolean };
  execution?: { effect_receipts?: boolean; shared_task_leases?: boolean; idempotency_ledger?: boolean };
};

type SoulStatus = {
  enabled?: boolean;
  tee_host_configured?: boolean;
  devon_host_configured?: boolean;
  detail?: string;
};

type Schedule = {
  schedule_id?: string;
  goal?: string;
  run_at?: string;
  task_id?: string | null;
  state?: string;
};

type OperatingSurface = {
  surface?: string;
  status?: string;
  contract_ready?: boolean;
  live_verified?: boolean;
};

type OperatingLayerStatus = {
  canonical_orchestrator?: string;
  second_orchestrator_created?: boolean;
  policy_version?: string;
  surfaces?: OperatingSurface[];
};

type MeshState = "locked" | "loading" | "online" | "degraded";

function tokenFromDevice() {
  try {
    return localStorage.getItem("devon-chat-token") || sessionStorage.getItem("devon-chat-token") || "";
  } catch {
    return "";
  }
}

function Indicator({ ok }: { ok: boolean }) {
  return (
    <span
      className={`h-1.5 w-1.5 rounded-full ${
        ok
          ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.7)]"
          : "bg-[#526979]"
      }`}
    />
  );
}

export function CapabilityDock() {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<MeshState>("locked");
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null);
  const [soul, setSoul] = useState<SoulStatus | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [operatingLayer, setOperatingLayer] = useState<OperatingLayerStatus | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    try {
      setOpen(localStorage.getItem("devon-capability-dock-open") === "1");
    } catch {
      // Persistence is optional.
    }
  }, []);

  const toggle = useCallback(() => {
    setOpen((current) => {
      const next = !current;
      try {
        localStorage.setItem("devon-capability-dock-open", next ? "1" : "0");
      } catch {
        // Persistence is optional.
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    const token = tokenFromDevice();
    if (!token) {
      setState("locked");
      setCatalog(null);
      setSoul(null);
      setSchedules([]);
      setOperatingLayer(null);
      return;
    }

    setState("loading");
    const headers = { Authorization: `Bearer ${token}` };
    const [toolsResult, soulResult, schedulesResult, operatingLayerResult] = await Promise.allSettled([
      fetch(`${API_BASE}/agent-tasks/tools`, { cache: "no-store", headers }),
      fetch(`${API_BASE}/soul/status`, { cache: "no-store", headers }),
      fetch(`${API_BASE}/agent-expansion/schedules`, { cache: "no-store", headers }),
      fetch(`${API_BASE}/devon/operating-layer/status`, { cache: "no-store" }),
    ]);

    let failures = 0;

    if (toolsResult.status === "fulfilled" && toolsResult.value.ok) {
      setCatalog((await toolsResult.value.json()) as ToolCatalog);
    } else {
      setCatalog(null);
      failures += 1;
    }

    if (soulResult.status === "fulfilled" && soulResult.value.ok) {
      setSoul((await soulResult.value.json()) as SoulStatus);
    } else {
      setSoul(null);
      failures += 1;
    }

    if (schedulesResult.status === "fulfilled" && schedulesResult.value.ok) {
      setSchedules((await schedulesResult.value.json()) as Schedule[]);
    } else {
      setSchedules([]);
      failures += 1;
    }

    if (operatingLayerResult.status === "fulfilled" && operatingLayerResult.value.ok) {
      setOperatingLayer((await operatingLayerResult.value.json()) as OperatingLayerStatus);
    } else {
      setOperatingLayer(null);
      failures += 1;
    }

    setCheckedAt(new Date());
    setState(failures === 0 ? "online" : "degraded");
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 45000);
    const onStorage = () => void refresh();
    window.addEventListener("storage", onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", onStorage);
    };
  }, [refresh]);

  const activeCount = useMemo(() => {
    if (!catalog) return 0;
    return [
      Boolean(catalog.operator?.enabled && catalog.operator?.configured),
      Boolean(catalog.github?.configured),
      Boolean(catalog.browser?.enabled),
      Boolean(catalog.council?.enabled),
      Boolean(catalog.expansion?.scheduler),
      Boolean(catalog.execution?.effect_receipts),
      Boolean(soul?.enabled),
    ].filter(Boolean).length;
  }, [catalog, soul]);

  const nextSchedule = useMemo(() => {
    const pending = schedules
      .filter((item) => item.run_at && !item.task_id)
      .sort((a, b) => new Date(a.run_at || 0).getTime() - new Date(b.run_at || 0).getTime());
    return pending[0] || null;
  }, [schedules]);

  const shellLabel =
    state === "locked"
      ? "MESH LOCKED"
      : state === "loading"
        ? "MESH CHECKING"
        : `MESH ${activeCount}/7`;

  return (
    <div className="fixed bottom-[4.75rem] right-3 z-[60] sm:bottom-[5.25rem] sm:right-5">
      {open && (
        <section className="mb-2 w-[min(92vw,380px)] border border-[#3e617c] bg-[#071016]/95 shadow-2xl shadow-black/50 backdrop-blur-xl">
          <header className="flex items-center justify-between border-b border-[#22384a] px-4 py-3">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#c77b4a]">DEVON capability mesh</p>
              <p className="mt-1 text-xs font-semibold text-white">Live control-plane readout</p>
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
              Sign in through <span className="text-white">Talk to DEVON</span> once on this device. The mesh will then read authenticated capability, soul, and schedule status without another form.
            </div>
          ) : (
            <div className="p-4">
              <div className="grid grid-cols-2 gap-px overflow-hidden border border-[#22384a] bg-[#22384a]">
                {[
                  ["Operator", Boolean(catalog?.operator?.enabled && catalog?.operator?.configured), "gated effects"],
                  ["GitHub", Boolean(catalog?.github?.configured), `${catalog?.github?.allowed_repositories?.length || 0} repo scope`],
                  ["Browser", Boolean(catalog?.browser?.enabled), catalog?.browser?.live_fetch ? "live fetch" : "guarded/offline"],
                  ["Council", Boolean(catalog?.council?.enabled), `${catalog?.council?.agents?.length || 0} agents`],
                  ["Scheduler", Boolean(catalog?.expansion?.scheduler), `${schedules.length} scheduled`],
                  ["Receipts", Boolean(catalog?.execution?.effect_receipts), "effect ledger"],
                  ["Soul", Boolean(soul?.enabled), soul?.enabled ? "recall on" : "recall off"],
                  ["Leases", Boolean(catalog?.execution?.shared_task_leases), "fenced runs"],
                ].map(([label, ok, detail]) => (
                  <div key={String(label)} className="bg-[#0b141b] px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <Indicator ok={Boolean(ok)} />
                      <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#93a6b5]">{String(label)}</span>
                    </div>
                    <p className="mt-1.5 pl-3.5 text-[10px] text-[#526979]">{String(detail)}</p>
                  </div>
                ))}
              </div>

              <div className="mt-3 border border-[#22384a] bg-black/15 px-3 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#6f8494]">Next scheduled goal</span>
                  <span className="font-mono text-[9px] text-[#d4a017]">{nextSchedule?.run_at ? new Date(nextSchedule.run_at).toLocaleString() : "NONE"}</span>
                </div>
                <p className="mt-1 truncate text-[10px] text-[#93a6b5]">{nextSchedule?.goal || "No unmaterialized scheduled goal is currently visible."}</p>
              </div>

              <div className="mt-3 border border-[#3e617c] bg-[#071016] px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#c77b4a]">Complementary layer</span>
                  <span className="font-mono text-[9px] text-sky-200">
                    {operatingLayer?.canonical_orchestrator === "DEVON" && operatingLayer?.second_orchestrator_created === false
                      ? "DEVON ROUTES"
                      : "UNVERIFIED"}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(operatingLayer?.surfaces || [])
                    .filter((surface) => surface.surface !== "devon")
                    .map((surface) => (
                      <span
                        key={surface.surface}
                        title={surface.live_verified ? "Live verified" : "Contract ready. External live state is not probed"}
                        className="border border-sky-400/25 bg-sky-400/[0.06] px-2 py-1 font-mono text-[8px] uppercase tracking-[0.1em] text-sky-100/80"
                      >
                        {surface.surface?.replaceAll("_", " ")}
                      </span>
                    ))}
                </div>
                <p className="mt-2 text-[9px] leading-4 text-[#526979]">
                  Policy readiness is live. External Claude, ChatGPT, Codex, Research, Work, app, and task sessions remain unclaimed until their own receipts arrive.
                </p>
              </div>

              <p className="mt-3 text-[9px] leading-4 text-[#526979]">
                {state === "degraded" ? "One or more telemetry reads failed. " : ""}
                {checkedAt ? `Checked ${checkedAt.toLocaleTimeString()}.` : ""} Heartbeat remains a separate deterministic n8n pulse.
              </p>
            </div>
          )}
        </section>
      )}

      <button
        type="button"
        onClick={toggle}
        className="ml-auto flex items-center gap-2 border border-[#c77b4a]/55 bg-[#091017]/95 px-3 py-2.5 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-[#e89b66] shadow-xl shadow-black/40 backdrop-blur transition hover:bg-[#c77b4a]/15"
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
        {shellLabel}
      </button>
    </div>
  );
}
