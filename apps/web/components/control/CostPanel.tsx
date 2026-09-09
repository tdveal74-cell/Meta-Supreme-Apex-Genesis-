"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";

/**
 * Safeguard 4 from the control plane brief: token budget and cost guardrails.
 *
 * The hard cap and the per account ledger already existed as migration 017,
 * refusing at 429 once a day's tokens reach the cap. What did not exist was any
 * route that read the ledger back, so this panel reads the one added beside it.
 *
 * The first draft of this panel rendered a per provider table. The 017 ledger
 * has no provider column: it is one row per account per UTC day. The table was
 * removed rather than filled with something plausible, and the route reports the
 * dimension as unavailable so its absence cannot be read as zero spend.
 */

type UsagePayload = {
  date: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  tokens: number;
  cap_tokens: number | null;
  remaining_tokens: number | null;
  resets_at: string;
  providers_available: boolean;
};

type Load =
  | { state: "loading" }
  | { state: "ready"; payload: UsagePayload }
  | { state: "signed-out" }
  | { state: "error"; detail: string };

function integer(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
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
        setLoad({ state: "error", detail: `the usage route answered ${response.status}` });
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
    return <p className="text-xs text-white/50">Reading today's usage.</p>;
  }

  if (load.state === "signed-out") {
    return (
      <p className="text-xs leading-relaxed text-white/50">
        No session token in this browser, so usage cannot be read. Usage is per account
        and this panel will not guess at a total.
      </p>
    );
  }

  if (load.state === "error") {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-300">Usage could not be read: {load.detail}.</p>
        <p className="text-xs leading-relaxed text-white/50">
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
  const cap = payload.cap_tokens;
  const capped = cap !== null && cap > 0;
  const used = capped ? Math.min(1, payload.tokens / cap) : 0;
  const nearCap = capped && used >= 0.8;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Figure label="Tokens today" value={integer(payload.tokens)} />
        <Figure label="Calls" value={integer(payload.calls)} />
        <Figure label="Daily cap" value={capped ? integer(cap) : "None set"} />
      </div>

      {capped ? (
        <div className="space-y-1.5">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full transition-all ${
                nearCap ? "bg-cyan-400" : "bg-cyan-400"
              }`}
              style={{ width: `${Math.round(used * 100)}%` }}
            />
          </div>
          <p className="text-xs leading-relaxed text-white/50">
            {integer(payload.remaining_tokens ?? 0)} tokens left before the cap refuses with
            a 429. The window is the UTC day {payload.date} and resets at{" "}
            {payload.resets_at.slice(11, 16)} UTC.
          </p>
        </div>
      ) : (
        <p className="text-xs leading-relaxed text-white/50">
          No daily cap is configured, so nothing refuses on budget today. The window is the
          UTC day {payload.date}.
        </p>
      )}

      <dl className="grid grid-cols-2 gap-2 text-xs">
        <Split label="Input tokens" value={integer(payload.input_tokens)} />
        <Split label="Output tokens" value={integer(payload.output_tokens)} />
      </dl>

      <div className="space-y-1 text-xs leading-relaxed text-white/50">
        {!payload.providers_available ? (
          <p>
            The ledger records one row per account per day and carries no provider column,
            so there is no per provider breakdown to show. Its absence is not zero spend.
          </p>
        ) : null}
        <p>
          Warning thresholds are not built. The cap is a hard refusal, so this shows how
          close the day is to it rather than claiming a warning was sent.
        </p>
      </div>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-white">{value}</p>
    </div>
  );
}

function Split({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between rounded-lg border border-white/5 bg-black/20 px-2.5 py-1.5">
      <dt className="text-white/50">{label}</dt>
      <dd className="tabular-nums text-white/75">{value}</dd>
    </div>
  );
}
