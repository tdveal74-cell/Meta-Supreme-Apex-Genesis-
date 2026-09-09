"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";

/**
 * Tier 3, the execution side.
 *
 * The brief asked for an n8n operations hub: execution telemetry, a retry and
 * queue viewer, version sync against GitHub. None of it is built, and this
 * panel does not pretend otherwise. The executor of record is the VPS instance
 * at n8n.editforge.online, and nothing in this repository exposes a route that
 * reads it: the only bridge is scripts/n8n_migrate.py, which is a script run by
 * a human, not an API this page could call.
 *
 * What the panel can honestly show is the health of the API this workspace
 * itself depends on, so the tier is not an empty rectangle.
 */

type Health =
  | { state: "checking" }
  | { state: "up"; detail: string }
  | { state: "down"; detail: string };

export function ExecutionHubPanel() {
  const [health, setHealth] = useState<Health>({ state: "checking" });

  const probe = useCallback(async () => {
    setHealth({ state: "checking" });
    try {
      const response = await fetch(`${API_BASE}/health`);
      if (!response.ok) {
        setHealth({ state: "down", detail: `health answered ${response.status}` });
        return;
      }
      const body = (await response.json()) as Record<string, unknown>;
      const version = typeof body.version === "string" ? body.version : "version not reported";
      setHealth({ state: "up", detail: version });
    } catch (error) {
      setHealth({
        state: "down",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void probe();
  }, [probe]);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">
          DEVON API
        </p>
        <p className="mt-1 flex items-center gap-2 text-sm text-white/80">
          <span
            className={`h-2 w-2 rounded-full ${
              health.state === "up"
                ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.7)]"
                : health.state === "checking"
                  ? "animate-pulse bg-amber-300"
                  : "bg-red-400"
            }`}
          />
          {health.state === "checking"
            ? "Checking"
            : health.state === "up"
              ? `Reachable, ${health.detail}`
              : `Unreachable, ${health.detail}`}
        </p>
      </div>

      <div className="space-y-2 text-xs leading-relaxed text-white/45">
        <p>
          Execution telemetry, the retry and queue viewer, and version sync against GitHub are
          not built. The executor of record is the n8n instance at n8n.editforge.online, and no
          route in this repository reads it. The existing bridge is a script a human runs, not
          an interface this page can call, so there is nothing here to render yet.
        </p>
        <p>
          Building this tier honestly needs a read route over the n8n executions API first.
          Until that exists, a chart here would be invented rather than measured.
        </p>
      </div>
    </div>
  );
}
