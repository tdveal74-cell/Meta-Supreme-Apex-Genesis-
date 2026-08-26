"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DevonChat } from "@/components/devon/DevonChat";
import { OperatorTerminal } from "@/components/terminal/OperatorTerminal";
import { RealShell } from "@/components/terminal/RealShell";
import { API_BASE } from "@/lib/api-base";

type CheckState = "checking" | "online" | "offline" | "locked" | "scheduled" | "ready";
type ExecMode = "gated" | "shell";

type IntelligenceStatus = {
  provider?: string;
  model?: string;
  simulated?: boolean;
};

type OperatorStatus = {
  enabled?: boolean;
  configured?: boolean;
  root?: string;
};

type OperatingLayerStatus = {
  canonical_orchestrator?: string;
  second_orchestrator_created?: boolean;
  policy_version?: string;
  surfaces?: Array<{ surface?: string; contract_ready?: boolean; live_verified?: boolean }>;
};

const AREAS = [
  ["TQO", "The Quiet Operator"],
  ["TSWS", "The Shadow We Share"],
  ["NCO", "NCO Forge"],
  ["ACX", "Ascension Caudex"],
  ["HEALTH", "Health"],
  ["MONEY", "Money"],
  ["FAMILY", "Family"],
  ["LEARNING", "Learning"],
  ["SYS", "Systems"],
] as const;

const ORGANS = [
  { label: "Heartbeat", value: "6H", note: "Deterministic pulse" },
  { label: "Reflection", value: "24H", note: "Daily read-only mind pass" },
  { label: "Ledger Janitor", value: "02:30Z", note: "Stale-job sweep" },
  { label: "Backup", value: "SUN", note: "Learning-lane export" },
] as const;

function dotClass(state: CheckState) {
  if (state === "online") return "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,.7)]";
  if (state === "checking") return "bg-amber-300 animate-pulse";
  if (state === "locked" || state === "scheduled" || state === "ready") return "bg-sky-300";
  return "bg-red-400";
}

function labelClass(state: CheckState) {
  if (state === "online") return "text-emerald-200";
  if (state === "checking") return "text-amber-200";
  if (state === "locked" || state === "scheduled" || state === "ready") return "text-sky-200";
  return "text-red-200";
}

function StatusCard({
  label,
  state,
  value,
  detail,
}: {
  label: string;
  state: CheckState;
  value: string;
  detail: string;
}) {
  return (
    <div className="relative overflow-hidden border border-[#22384a] bg-[#0b141b]/80 px-4 py-3 backdrop-blur-md">
      <span className="absolute left-0 top-0 h-4 w-px bg-[#c77b4a]" />
      <span className="absolute left-0 top-0 h-px w-4 bg-[#c77b4a]" />
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6f8494]">{label}</p>
        <span className={`h-2 w-2 rounded-full ${dotClass(state)}`} />
      </div>
      <p className={`mt-2 font-mono text-xs font-semibold ${labelClass(state)}`}>{value}</p>
      <p className="mt-1 text-[11px] leading-4 text-[#6f8494]">{detail}</p>
    </div>
  );
}

export function UnifiedCommandCenter() {
  const [now, setNow] = useState<Date | null>(null);
  const [apiState, setApiState] = useState<CheckState>("checking");
  const [operatorState, setOperatorState] = useState<CheckState>("checking");
  const [operator, setOperator] = useState<OperatorStatus | null>(null);
  const [mindState, setMindState] = useState<CheckState>("checking");
  const [mind, setMind] = useState<IntelligenceStatus | null>(null);
  const [layerState, setLayerState] = useState<CheckState>("checking");
  const [operatingLayer, setOperatingLayer] = useState<OperatingLayerStatus | null>(null);
  const [lastProbe, setLastProbe] = useState<Date | null>(null);
  const [execMode, setExecMode] = useState<ExecMode>("gated");

  useEffect(() => {
    const saved = localStorage.getItem("devon-command-center-exec-mode");
    if (saved === "gated" || saved === "shell") setExecMode(saved);

    setNow(new Date());
    const clock = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(clock);
  }, []);

  const setMode = useCallback((mode: ExecMode) => {
    setExecMode(mode);
    try {
      localStorage.setItem("devon-command-center-exec-mode", mode);
    } catch {
      // Persistence is a convenience only.
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    setApiState("checking");
    setOperatorState("checking");
    setLayerState("checking");
    try {
      const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      setApiState(response.ok ? "online" : "offline");
    } catch {
      setApiState("offline");
    }

    try {
      const response = await fetch(`${API_BASE}/operator/status`, { cache: "no-store" });
      if (!response.ok) throw new Error("operator status unavailable");
      const data = (await response.json()) as OperatorStatus;
      setOperator(data);
      setOperatorState(data.enabled && data.configured ? "online" : "locked");
    } catch {
      setOperator(null);
      setOperatorState("offline");
    }

    try {
      const response = await fetch(`${API_BASE}/devon/operating-layer/status`, { cache: "no-store" });
      if (!response.ok) throw new Error("operating layer status unavailable");
      const data = (await response.json()) as OperatingLayerStatus;
      setOperatingLayer(data);
      setLayerState(
        data.canonical_orchestrator === "DEVON" && data.second_orchestrator_created === false
          ? "ready"
          : "offline",
      );
    } catch {
      setOperatingLayer(null);
      setLayerState("offline");
    }

    let token = "";
    try {
      token = localStorage.getItem("devon-chat-token") || sessionStorage.getItem("devon-chat-token") || "";
    } catch {
      token = "";
    }

    if (!token) {
      setMind(null);
      setMindState("locked");
    } else {
      try {
        const response = await fetch(`${API_BASE}/intelligence/status`, {
          cache: "no-store",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error("mind status unavailable");
        const data = (await response.json()) as IntelligenceStatus;
        setMind(data);
        setMindState("online");
      } catch {
        setMind(null);
        setMindState("offline");
      }
    }
    setLastProbe(new Date());
  }, []);

  useEffect(() => {
    void refreshStatus();
    const timer = window.setInterval(() => void refreshStatus(), 30000);
    const storageListener = () => void refreshStatus();
    window.addEventListener("storage", storageListener);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", storageListener);
    };
  }, [refreshStatus]);

  const dateLabel = useMemo(() => {
    if (!now) return "LOCAL TIME";
    return new Intl.DateTimeFormat("en-US", {
      weekday: "short",
      month: "short",
      day: "2-digit",
      year: "numeric",
    }).format(now);
  }, [now]);

  const timeLabel = useMemo(() => {
    if (!now) return "--:--:--";
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(now);
  }, [now]);

  const mindValue =
    mindState === "locked"
      ? "SIGN IN"
      : mindState === "online"
        ? mind?.simulated
          ? "SIMULATED"
          : "LIVE"
        : mindState.toUpperCase();

  const mindDetail =
    mindState === "online"
      ? `${mind?.provider || "provider"}${mind?.model ? ` · ${mind.model}` : ""}`
      : mindState === "locked"
        ? "Session required for provider status"
        : "Provider probe failed";

  return (
    <main className="min-h-screen overflow-hidden bg-[#050a0e] text-[#ede7dc]">
      <div className="pointer-events-none fixed inset-0 z-40 opacity-[0.035] [background:repeating-linear-gradient(0deg,transparent_0_3px,rgba(237,231,220,.55)_3px_4px)]" />
      <div className="pointer-events-none fixed inset-0 z-30 bg-[radial-gradient(120%_90%_at_50%_40%,transparent_52%,rgba(3,6,9,.62)_100%)]" />
      <div className="pointer-events-none fixed inset-x-0 top-0 h-[520px] bg-[radial-gradient(ellipse_at_top,rgba(199,123,74,.12),transparent_68%)]" />

      <div className="relative z-10 mx-auto max-w-[1780px] px-3 py-3 sm:px-5 lg:px-7">
        <header className="border-b border-[#22384a] pb-3">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex min-w-0 items-center gap-4">
              <div className="relative grid h-14 w-14 shrink-0 place-items-center rounded-full border border-[#c77b4a]/70 bg-[#0b141b] shadow-[0_0_28px_rgba(199,123,74,.18)]">
                <span className="absolute inset-2 rounded-full border border-[#d4a017]/40" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#4fb3a5] shadow-[0_0_14px_rgba(79,179,165,.8)]" />
              </div>
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#c77b4a]">Second brain · executive control plane</p>
                <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <h1 className="text-2xl font-semibold tracking-[0.18em] text-[#f2eee6] sm:text-3xl">DEVON</h1>
                  <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6f8494]">Unified Command Center</span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <a href="#conversation" className="border border-[#22384a] bg-[#0b141b]/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#93a6b5] transition hover:border-[#c77b4a]/60 hover:text-white">Talk</a>
              <a href="#estate" className="border border-[#22384a] bg-[#0b141b]/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#93a6b5] transition hover:border-[#c77b4a]/60 hover:text-white">Estate</a>
              <a href="#execution" className="border border-[#c77b4a]/45 bg-[#c77b4a]/10 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#e89b66] transition hover:bg-[#c77b4a]/20">Execution</a>
              <Link href="/council/deliberate" className="border border-[#22384a] bg-[#0b141b]/70 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#93a6b5] transition hover:border-[#d4a017]/60 hover:text-white">Council</Link>
              <div className="ml-1 border-l border-[#22384a] pl-3 text-right font-mono">
                <div className="text-lg font-semibold tracking-[0.12em] text-[#f2eee6]">{timeLabel}</div>
                <div className="text-[9px] uppercase tracking-[0.16em] text-[#6f8494]">{dateLabel}</div>
              </div>
            </div>
          </div>
        </header>

        <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6" aria-label="Estate status and configured organs">
          <StatusCard
            label="DEVON API"
            state={apiState}
            value={apiState === "online" ? "ONLINE" : apiState.toUpperCase()}
            detail={lastProbe ? `Probe ${lastProbe.toLocaleTimeString()}` : "Initial probe"}
          />
          <StatusCard label="Mind" state={mindState} value={mindValue} detail={mindDetail} />
          <StatusCard
            label="Operator bridge"
            state={operatorState}
            value={operatorState === "online" ? "READY" : operatorState.toUpperCase()}
            detail={operator?.root ? `Root ${operator.root}` : "Gated command execution"}
          />
          <StatusCard
            label="ChatGPT layer"
            state={layerState}
            value={layerState === "ready" ? "ROUTING READY" : layerState.toUpperCase()}
            detail={
              operatingLayer?.surfaces
                ? `${operatingLayer.surfaces.filter((surface) => surface.surface !== "devon" && surface.contract_ready).length} external surfaces contract ready. Live state stays unclaimed`
                : "DEVON policy probe failed"
            }
          />
          <StatusCard label="Heartbeat" state="scheduled" value="6H SCHEDULE" detail="Build 13 pulse configured. Live last-beat telemetry is not exposed here" />
          <StatusCard label="Write authority" state="locked" value="TEE" detail="Writes stop at human ruling" />
        </section>

        <section id="conversation" className="mt-4 grid gap-4 2xl:grid-cols-[minmax(0,1.58fr)_minmax(330px,.42fr)]">
          <div className="min-w-0">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#c77b4a]">Primary interface</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Talk to DEVON</h2>
              </div>
              <span className="hidden border border-[#22384a] bg-[#0b141b] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[#6f8494] sm:inline">Ask · direct · approve</span>
            </div>
            <DevonChat />
          </div>

          <aside id="estate" className="grid content-start gap-4">
            <section className="border border-[#22384a] bg-[#0b141b]/72 p-4 backdrop-blur-md">
              <div className="flex items-center justify-between gap-3 border-b border-[#22384a] pb-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#c77b4a]">Brain map</p>
                  <h2 className="mt-1 text-sm font-semibold text-white">Nine Areas</h2>
                </div>
                <span className="font-mono text-[9px] tracking-[0.14em] text-[#6f8494]">CANONICAL</span>
              </div>
              <div className="relative mx-auto my-5 grid aspect-square max-w-[310px] place-items-center rounded-full border border-[#22384a] bg-[radial-gradient(circle,rgba(199,123,74,.18),rgba(11,20,27,.28)_40%,transparent_68%)]">
                <div className="absolute inset-[12%] rounded-full border border-dashed border-[#3e617c]/70" />
                <div className="absolute inset-[31%] rounded-full border border-[#d4a017]/40 shadow-[0_0_28px_rgba(199,123,74,.14)]" />
                <div className="z-10 grid h-20 w-20 place-items-center rounded-full border border-[#c77b4a]/75 bg-[#091017] shadow-[0_0_30px_rgba(199,123,74,.28)]">
                  <div className="text-center">
                    <div className="font-mono text-[10px] font-semibold tracking-[0.18em] text-[#f2eee6]">DEVON</div>
                    <div className="mt-1 text-[8px] uppercase tracking-[0.12em] text-[#4fb3a5]">core</div>
                  </div>
                </div>
                {AREAS.map(([code, name], index) => {
                  const angle = (index / AREAS.length) * Math.PI * 2 - Math.PI / 2;
                  const x = 50 + Math.cos(angle) * 42;
                  const y = 50 + Math.sin(angle) * 42;
                  return (
                    <div
                      key={code}
                      title={name}
                      className="absolute -translate-x-1/2 -translate-y-1/2 border border-[#3e617c] bg-[#091017] px-2 py-1 font-mono text-[8px] font-semibold tracking-[0.1em] text-[#93a6b5] shadow-lg"
                      style={{ left: `${x}%`, top: `${y}%` }}
                    >
                      {code}
                    </div>
                  );
                })}
              </div>
              <p className="text-xs leading-5 text-[#6f8494]">One estate, nine ruled Areas. The control plane routes work without inventing a tenth.</p>
            </section>

            <section className="border border-[#22384a] bg-[#0b141b]/72 p-4 backdrop-blur-md">
              <div className="flex items-center justify-between gap-3 border-b border-[#22384a] pb-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#c77b4a]">Estate organs</p>
                  <h2 className="mt-1 text-sm font-semibold text-white">Continuity stack</h2>
                </div>
                <span className="h-2 w-2 rounded-full bg-[#4fb3a5] shadow-[0_0_12px_rgba(79,179,165,.8)]" />
              </div>
              <div className="mt-3 divide-y divide-[#22384a]">
                {ORGANS.map((organ) => (
                  <div key={organ.label} className="grid grid-cols-[1fr_auto] gap-3 py-3 first:pt-1">
                    <div>
                      <div className="text-xs font-medium text-[#d9e0e5]">{organ.label}</div>
                      <div className="mt-1 text-[10px] text-[#6f8494]">{organ.note}</div>
                    </div>
                    <div className="font-mono text-[10px] font-semibold tracking-[0.12em] text-[#d4a017]">{organ.value}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="border border-[#c77b4a]/35 bg-[#c77b4a]/[0.055] p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#e89b66]">Authority boundary</p>
              <p className="mt-2 text-sm font-semibold text-white">DEVON can think, route, read, plan, and execute reads.</p>
              <p className="mt-2 text-xs leading-5 text-[#93a6b5]">Effectful writes remain bound to your approval path. The real shell is your separate human operator door, not a bypass for DEVON.</p>
            </section>
          </aside>
        </section>

        <section id="execution" className="mt-5 border-t border-[#22384a] pt-5">
          <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#c77b4a]">Execution deck</p>
              <h2 className="mt-1 text-xl font-semibold text-white">One cockpit, two execution paths</h2>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-[#6f8494]">Use the gated terminal when DEVON should classify and pause writes for approval. Use the real shell when you are personally operating the server terminal.</p>
            </div>
            <div className="inline-flex w-fit border border-[#22384a] bg-[#091017] p-1">
              <button
                type="button"
                onClick={() => setMode("gated")}
                className={`px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] transition ${
                  execMode === "gated"
                    ? "bg-[#c77b4a]/18 text-[#e89b66]"
                    : "text-[#6f8494] hover:text-white"
                }`}
              >
                DEVON gated
              </button>
              <button
                type="button"
                onClick={() => setMode("shell")}
                className={`px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] transition ${
                  execMode === "shell"
                    ? "bg-[#4fb3a5]/15 text-[#8fd5cb]"
                    : "text-[#6f8494] hover:text-white"
                }`}
              >
                Real shell
              </button>
            </div>
          </div>

          {execMode === "gated" ? <OperatorTerminal /> : <RealShell />}
        </section>

        <footer className="mt-5 flex flex-col gap-2 border-t border-[#22384a] py-4 font-mono text-[9px] uppercase tracking-[0.14em] text-[#526979] sm:flex-row sm:items-center sm:justify-between">
          <span>DEVON · one control plane · receipts over claims</span>
          <span>Persistent device session · approval-gated writes · hardened operator shell</span>
        </footer>
      </div>
    </main>
  );
}
