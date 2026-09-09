"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";

/**
 * Safeguard 4 from the control plane brief: token budget and cost guardrails.
 *
 * The hard cap and the per account ledger already existed (migration
 * 017_provider_usage, and a 429 refusal when the cap is reached). What did not
 * exist was any route that reads the table, so this panel reads the route added
 * beside it and shows nothing it cannot source.
 */

type ProviderRow = {
  provider: string;
  tokens: number;
  cost_usd: number;
  calls: number;
};

type UsagePayload = {
  date: string;
  tokens: number;
  cost_usd: number;
  cap_tokens: number | null;
  remaining_tokens: number | null;
  providers: ProviderRow[];
};

type Load =
  | { state: "loading" }
  | { state: "ready"; payload: UsagePayload }
  | { state: "signed-out" }
  | { state: "error"; detail: string };

function integer(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function money(value: number): string {
  return `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

export function CostPanel() {
  const [load, setLoad] = useState<Load>({ state: "loading" });

  const read = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setLoad({ state: "signed-out" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/usage`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setLoad({
          state: "error",
          detail: `the usage route answered ${response.status}`,
        });
        return;
      }
      setLoad({ state: "ready", payload: (await response.json()) as UsagePayload });
    } catch (error) {
      setLoad({
        state: "error",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void read();
  }, [read]);

  if (load.state === "loading") {
    return <p className="text-xs text-white/45">Reading today's usage.</p>;
  }

  if (load.state === "signed-out") {
    return (
      <p className="text-xs text-white/45">
        No session token in this browser, so usage cannot be read. Usage is per account and
        this panel will not guess at a total.
      </p>
    );
  }

  if (load.state === "error") {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-300">Usage could not be read: {load.detail}.</p>
        <p className="text-xs text-white/40">
          This is a failed read, not a zero. Nothing below is being shown as spend.
        </p>
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }

  const { payload } = load;
  const capped = payload.cap_tokens !== null && payload.cap_tokens > 0;
  const used = capped ? Math.min(1, payload.tokens / (payload.cap_tokens as number)) : 0;
  const nearCap = capped && used >= 0.8;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Figure label="Tokens today" value={integer(payload.tokens)} />
        <Figure label="Cost today" value={money(payload.cost_usd)} />
        <Figure
          label="Daily cap"
          value={capped ? integer(payload.cap_tokens as number) : "None set"}
        />
      </div>

      {capped ? (
        <div className="space-y-1.5">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full transition-all ${
                nearCap ? "bg-amber-400" : "bg-emerald-400"
              }`}
              style={{ width: `${Math.round(used * 100)}%` }}
            />
          </div>
          <p className="text-xs text-white/45">
            {integer(payload.remaining_tokens ?? 0)} tokens left before the cap refuses with a
            429. The window is the UTC day {payload.date}.
          </p>
        </div>
      ) : (
        <p className="text-xs text-white/45">
          No daily cap is configured, so nothing refuses on budget today. The window is the UTC
          day {payload.date}.
        </p>
      )}

      {payload.providers.length === 0 ? (
        <p className="text-xs text-white/45">
          No provider calls recorded today. This account has genuinely spent nothing.
        </p>
      ) : (
        <table className="w-full text-left text-xs">
          <thead className="text-white/40">
            <tr>
              <th className="pb-1.5 font-medium">Provider</th>
              <th className="pb-1.5 text-right font-medium">Calls</th>
              <th className="pb-1.5 text-right font-medium">Tokens</th>
              <th className="pb-1.5 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody className="text-white/70">
            {payload.providers.map((row) => (
              <tr key={row.provider} className="border-t border-white/5">
                <td className="py-1.5">{row.provider}</td>
                <td className="py-1.5 text-right tabular-nums">{integer(row.calls)}</td>
                <td className="py-1.5 text-right tabular-nums">{integer(row.tokens)}</td>
                <td className="py-1.5 text-right tabular-nums">{money(row.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="text-xs text-white/35">
        Warning thresholds are not built. The cap is a hard refusal, so this panel shows how
        close the day is to it rather than claiming a warning was sent.
      </p>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-white">{value}</p>
    </div>
  );
}
