"use client";

import { useMemo } from "react";

type HudState = "checking" | "online" | "offline" | "locked" | "scheduled";

function signal(state: HudState) {
  if (state === "online") return "bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,.85)]";
  if (state === "checking") return "animate-pulse bg-amber-200";
  if (state === "locked" || state === "scheduled") return "bg-sky-300 shadow-[0_0_10px_rgba(125,211,252,.65)]";
  return "bg-red-400 shadow-[0_0_10px_rgba(248,113,113,.65)]";
}

export function CinematicHud({
  apiState,
  mindState,
  operatorState,
  provider,
  model,
  timeLabel,
}: {
  apiState: HudState;
  mindState: HudState;
  operatorState: HudState;
  provider?: string;
  model?: string;
  timeLabel: string;
}) {
  const health = useMemo(() => {
    const states = [apiState, mindState, operatorState];
    const online = states.filter((state) => state === "online").length;
    if (states.some((state) => state === "offline")) return { label: "DEGRADED", pct: Math.max(28, online * 30) };
    if (states.some((state) => state === "checking")) return { label: "SYNCING", pct: 66 };
    return { label: "NOMINAL", pct: 100 };
  }, [apiState, mindState, operatorState]);

  return (
    <div className="relative overflow-hidden border border-[#2b4558]/90 bg-[linear-gradient(135deg,rgba(8,19,27,.94),rgba(5,10,14,.82)_48%,rgba(10,23,30,.9))] shadow-[0_24px_90px_rgba(0,0,0,.45),inset_0_0_80px_rgba(79,179,165,.025)]">
      <div className="pointer-events-none absolute inset-0 opacity-35 [background-image:linear-gradient(rgba(79,179,165,.055)_1px,transparent_1px),linear-gradient(90deg,rgba(79,179,165,.055)_1px,transparent_1px)] [background-size:34px_34px] [mask-image:linear-gradient(to_bottom,black,transparent_92%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#4fb3a5]/70 to-transparent" />
      <div className="pointer-events-none absolute -left-24 top-1/2 h-56 w-56 -translate-y-1/2 rounded-full border border-[#4fb3a5]/10 shadow-[0_0_90px_rgba(79,179,165,.08)]" />
      <div className="pointer-events-none absolute -right-24 top-1/2 h-64 w-64 -translate-y-1/2 rounded-full border border-[#c77b4a]/10 shadow-[0_0_100px_rgba(199,123,74,.08)]" />

      <div className="relative grid min-h-[170px] gap-5 p-4 sm:p-5 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
        <div>
          <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.2em] text-[#668092]">
            <span className={`h-1.5 w-1.5 rounded-full ${signal(apiState)}`} />
            Executive systems mesh
          </div>
          <div className="mt-4 flex items-end gap-3">
            <div className="font-mono text-3xl font-semibold tracking-[0.12em] text-[#f5f0e7] sm:text-4xl">{health.pct}</div>
            <div className="pb-1 font-mono text-[9px] uppercase tracking-[0.18em] text-[#4fb3a5]">{health.label}</div>
          </div>
          <div className="mt-3 h-1.5 max-w-[320px] overflow-hidden bg-[#12232d]">
            <div
              className="h-full bg-[linear-gradient(90deg,#356c70,#4fb3a5,#d4a017)] shadow-[0_0_18px_rgba(79,179,165,.45)] transition-[width] duration-700"
              style={{ width: `${health.pct}%` }}
            />
          </div>
          <p className="mt-3 max-w-sm text-[10px] leading-5 text-[#718898]">
            Live operator mesh, intelligence identity, governed execution, and scheduled continuity in one control plane.
          </p>
        </div>

        <div className="relative mx-auto grid h-32 w-32 place-items-center sm:h-36 sm:w-36">
          <div className="absolute inset-0 rounded-full border border-[#315268]/70 shadow-[0_0_45px_rgba(79,179,165,.12)]" />
          <div className="absolute inset-[9%] animate-[spin_18s_linear_infinite] rounded-full border border-dashed border-[#4fb3a5]/55 motion-reduce:animate-none" />
          <div className="absolute inset-[20%] animate-[spin_12s_linear_infinite_reverse] rounded-full border border-[#d4a017]/35 motion-reduce:animate-none" />
          <div className="absolute inset-[31%] rounded-full border border-[#c77b4a]/55 bg-[radial-gradient(circle,rgba(79,179,165,.2),rgba(9,16,23,.9)_62%)] shadow-[0_0_28px_rgba(79,179,165,.2),inset_0_0_22px_rgba(212,160,23,.08)]" />
          <div className="absolute h-[116%] w-px bg-gradient-to-b from-transparent via-[#4fb3a5]/25 to-transparent" />
          <div className="absolute h-px w-[116%] bg-gradient-to-r from-transparent via-[#c77b4a]/25 to-transparent" />
          <div className="relative text-center">
            <div className="font-mono text-[10px] font-bold tracking-[0.26em] text-white">DEVON</div>
            <div className="mt-1 font-mono text-[8px] uppercase tracking-[0.18em] text-[#4fb3a5]">Cognitive core</div>
          </div>
        </div>

        <div className="lg:text-right">
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#668092]">Inference identity</div>
          <div className="mt-3 font-mono text-sm font-semibold uppercase tracking-[0.12em] text-[#f5f0e7]">
            {provider || "Session locked"}
          </div>
          <div className="mt-1 font-mono text-[10px] tracking-[0.08em] text-[#c77b4a]">{model || "Authenticate to reveal live model"}</div>
          <div className="mt-4 grid grid-cols-3 gap-2 lg:ml-auto lg:max-w-[320px]">
            {[
              ["API", apiState],
              ["MIND", mindState],
              ["OPS", operatorState],
            ].map(([label, state]) => (
              <div key={label} className="border border-[#22384a] bg-black/20 px-2 py-2 text-center">
                <div className="flex items-center justify-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${signal(state as HudState)}`} />
                  <span className="font-mono text-[8px] font-semibold tracking-[0.12em] text-[#a9bac5]">{label}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 font-mono text-[9px] tracking-[0.16em] text-[#5e7484]">SYNC {timeLabel}</div>
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-0 left-0 h-5 w-5 border-b border-l border-[#c77b4a]/80" />
      <div className="pointer-events-none absolute right-0 top-0 h-5 w-5 border-r border-t border-[#4fb3a5]/80" />
    </div>
  );
}
