"use client";

import { FormEvent, useCallback, useState } from "react";

/**
 * Restricted VPS production action gate.
 * Sits beside the existing Railway OperatorTerminal / RealShell.
 * Does not replace those surfaces. All signing happens server-side.
 */

type ActionChoice = "run:tqo" | "run:nco" | "system:pause" | "system:resume";

type GateStatus =
  | "idle"
  | "requesting"
  | "pending"
  | "approving"
  | "rejecting"
  | "done"
  | "error";

type ApprovalData = {
  id?: string;
  request_id?: string;
  status?: string;
  state?: string;
  [key: string]: unknown;
};

type Receipt = {
  request_id?: string;
  status?: string;
  state?: string;
  operation?: string;
  target?: string;
  reason?: string;
  approved_by?: string;
  rejected_by?: string;
  created_at?: string;
  updated_at?: string;
  message?: string;
  error?: string;
  ok?: boolean;
  approval?: ApprovalData;
  requires_human_approval?: boolean;
  [key: string]: unknown;
};

const ACTION_OPTIONS: { value: ActionChoice; label: string }[] = [
  { value: "run:tqo", label: "run / tqo" },
  { value: "run:nco", label: "run / nco" },
  { value: "system:pause", label: "system / pause" },
  { value: "system:resume", label: "system / resume" },
];

async function callProxy(
  action: string,
  body?: Record<string, unknown>,
): Promise<Receipt> {
  const res = await fetch(`/api/devon-ops/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = (await res.json().catch(() => ({
    ok: false,
    error: `${res.status} ${res.statusText}`,
  }))) as Receipt;
  if (!res.ok && !data.error) {
    data.error = `HTTP ${res.status}`;
  }
  return data;
}

/**
 * Extract the request_id from either top-level or nested in approval object
 */
function getRequestId(receipt: Receipt): string | undefined {
  return receipt.request_id || (receipt.approval as ApprovalData)?.request_id || (receipt.approval as ApprovalData)?.id;
}

/**
 * Extract the status from either top-level or nested in approval object
 */
function getStatus(receipt: Receipt): string | undefined {
  return (
    receipt.status ||
    receipt.state ||
    (receipt.approval as ApprovalData)?.status ||
    (receipt.approval as ApprovalData)?.state
  );
}

export function VpsActionGate() {
  const [choice, setChoice] = useState<ActionChoice>("system:pause");
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState<GateStatus>("idle");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState("");

  const [op, target] = choice.split(":") as [string, string];

  const isBusy =
    status === "requesting" ||
    status === "approving" ||
    status === "rejecting";

  const hasRequest = Boolean(getRequestId(receipt || {}));
  const showPendingControls =
    hasRequest &&
    (status === "pending" || status === "approving" || status === "rejecting");

  const requestAction = useCallback(
    async (event?: FormEvent) => {
      event?.preventDefault();
      if (isBusy) return;

      const trimmed = reason.trim();
      if (trimmed.length < 3 || trimmed.length > 500) {
        setError("Reason must be 3 to 500 characters");
        return;
      }

      setError("");
      setStatus("requesting");
      setReceipt(null);

      try {
        const data = await callProxy("request", {
          operation: op,
          target,
          reason: trimmed,
        });

        console.log("=== VPS RESPONSE (requestAction) ===");
        console.log("Full response:", data);
        console.log("data.approval:", data.approval);
        console.log("data.requires_human_approval:", data.requires_human_approval);
        console.log("getRequestId():", getRequestId(data));
        console.log("getStatus():", getStatus(data));

        if (data.error || data.ok === false) {
          setError(data.error || data.message || "Request failed");
          setStatus("error");
          setReceipt(data);
          return;
        }

        setReceipt(data);
        // If requires_human_approval is true, we're in pending state
        const currentStatus = getStatus(data);
        const isPending = data.requires_human_approval === true || currentStatus === "pending";
        console.log("isPending:", isPending);
        console.log("Setting status to:", isPending ? "pending" : "done");
        setStatus(isPending ? "pending" : "done");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    },
    [isBusy, op, reason, target],
  );

  const decide = useCallback(
    async (decision: "approve" | "reject") => {
      const requestId = getRequestId(receipt || {});
      if (!requestId || isBusy) return;

      setError("");
      setStatus(decision === "approve" ? "approving" : "rejecting");

      try {
        const body =
          decision === "approve"
            ? { request_id: requestId, approved_by: "Tee" }
            : { request_id: requestId, rejected_by: "Tee" };

        const data = await callProxy(decision, body);

        if (data.error || data.ok === false) {
          setError(data.error || data.message || `${decision} failed`);
          setStatus("error");
          setReceipt((prev) => ({ ...prev, ...data }));
          return;
        }

        setReceipt((prev) => ({ ...prev, ...data }));
        setStatus("done");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    },
    [isBusy, receipt],
  );

  const refreshStatus = useCallback(async () => {
    const requestId = getRequestId(receipt || {});
    if (!requestId || isBusy) return;

    setError("");
    try {
      const data = await callProxy("approval-status", {
        request_id: requestId,
      });

      if (data.error) {
        setError(data.error);
        return;
      }

      setReceipt((prev) => ({ ...prev, ...data }));
      const currentStatus = getStatus(data);
      if (currentStatus && currentStatus !== "pending" && data.requires_human_approval !== true) {
        setStatus("done");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [isBusy, receipt]);

  const reset = () => {
    setStatus("idle");
    setReceipt(null);
    setError("");
    setReason("");
  };

  return (
    <section className="border border-[#c77b4a]/35 bg-[#0b141b]/80 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between gap-3 border-b border-[#22384a] pb-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#e89b66]">
            VPS production gate
          </p>
          <h2 className="mt-1 text-sm font-semibold text-white">
            ops.editforge.online
          </h2>
        </div>
        <span className="font-mono text-[9px] tracking-[0.14em] text-[#6f8494]">
          HMAC · Tee only
        </span>
      </div>

      <p className="mt-3 text-xs leading-5 text-[#93a6b5]">
        Restricted actions only. Signing is server-side. This panel does not
        replace the Railway operator terminal or the real shell.
      </p>

      <form onSubmit={requestAction} className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-[#6f8494]">
            Action
          </span>
          <select
            value={choice}
            onChange={(e) => setChoice(e.target.value as ActionChoice)}
            disabled={isBusy || showPendingControls}
            className="w-full border border-[#22384a] bg-[#091017] px-3 py-2 font-mono text-xs text-[#ede7dc] outline-none focus:border-[#c77b4a]/50 disabled:opacity-40"
          >
            {ACTION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-[#6f8494]">
            Reason (3 to 500 chars)
          </span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={isBusy || showPendingControls}
            rows={2}
            placeholder="Why this action is required"
            className="w-full resize-none border border-[#22384a] bg-[#091017] px-3 py-2 font-mono text-xs text-[#ede7dc] outline-none placeholder:text-[#6f8494]/50 focus:border-[#c77b4a]/50 disabled:opacity-40"
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={isBusy || showPendingControls || reason.trim().length < 3}
            className="border border-[#c77b4a]/45 bg-[#c77b4a]/15 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#e89b66] transition hover:bg-[#c77b4a]/25 disabled:opacity-30"
          >
            {status === "requesting" ? "Requesting…" : "Request"}
          </button>

          {showPendingControls && (
            <>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void decide("reject")}
                className="border border-white/15 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#93a6b5] transition hover:bg-white/5 disabled:opacity-30"
              >
                {status === "rejecting" ? "Rejecting…" : "Reject"}
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void decide("approve")}
                className="border border-emerald-400/40 bg-emerald-400/10 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-300 transition hover:bg-emerald-400/20 disabled:opacity-30"
              >
                {status === "approving" ? "Approving…" : "Approve"}
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void refreshStatus()}
                className="border border-[#22384a] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#6f8494] transition hover:text-white disabled:opacity-30"
              >
                Refresh
              </button>
            </>
          )}

          {(status === "done" || status === "error") && (
            <button
              type="button"
              onClick={reset}
              className="border border-[#22384a] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#6f8494] transition hover:text-white"
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {error && (
        <p className="mt-3 border border-red-400/20 bg-red-400/10 px-3 py-2 font-mono text-[11px] text-red-300">
          {error}
        </p>
      )}

      {receipt && (
        <div className="mt-3 border border-[#22384a] bg-[#091017] p-3 font-mono text-[11px] leading-5 text-[#93a6b5]">
          <p className="text-[10px] uppercase tracking-[0.16em] text-[#6f8494]">
            Receipt
          </p>
          
          {/* Extracted top-level fields */}
          {getRequestId(receipt) && (
            <p className="mt-1 break-all text-[#ede7dc]">
              request_id · {getRequestId(receipt)}
            </p>
          )}
          
          {getStatus(receipt) && (
            <p>
              status ·{" "}
              <span
                className={
                  getStatus(receipt) === "pending"
                    ? "text-amber-300"
                    : getStatus(receipt) === "approved"
                      ? "text-emerald-300"
                      : getStatus(receipt) === "rejected"
                        ? "text-red-300"
                        : "text-[#ede7dc]"
                }
              >
                {getStatus(receipt)}
              </span>
            </p>
          )}

          {receipt.requires_human_approval !== undefined && (
            <p>
              requires_human_approval ·{" "}
              <span className="text-[#ede7dc]">
                {String(receipt.requires_human_approval)}
              </span>
            </p>
          )}

          {/* Approval object nested fields */}
          {receipt.approval && typeof receipt.approval === "object" && (
            <>
              <p className="mt-2 text-[10px] uppercase tracking-[0.16em] text-[#6f8494]">
                approval:
              </p>
              {Object.entries(receipt.approval as Record<string, unknown>).map(
                ([key, value]) => {
                  if (value === null || value === undefined) return null;
                  return (
                    <p key={key} className="ml-2">
                      {key} · <span className="text-[#ede7dc]">{String(value)}</span>
                    </p>
                  );
                }
              )}
            </>
          )}

          {/* Other top-level fields */}
          {Object.entries(receipt).map(([key, value]) => {
            // Skip fields we've already rendered
            if (["request_id", "status", "state", "requires_human_approval", "approval", "DEVON_OPS_SECRET", "secret"].includes(key)) return null;
            if (value === null || value === undefined || typeof value === "object") return null;
            
            return (
              <p key={key}>
                {key} · <span className="text-[#ede7dc]">{String(value)}</span>
              </p>
            );
          })}
        </div>
      )}

      <p className="mt-3 text-[10px] leading-4 text-[#6f8494]">
        Real production actions still require your fresh, specific approval.
        Do not approve without intentional intent.
      </p>
    </section>
  );
}
