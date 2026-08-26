"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

type LineKind = "system" | "command" | "stdout" | "stderr" | "approval";

type TerminalLine = {
  id: number;
  kind: LineKind;
  text: string;
};

type CommandPlan = {
  command: string;
  cwd: string;
  risk: "read" | "write" | "blocked";
  approval_required: boolean;
  reason: string;
};

type ExecutionResult = {
  command: string;
  cwd: string;
  returncode: number;
  stdout: string;
  stderr: string;
  timed_out: boolean;
  truncated: boolean;
};

type ApprovalPayload = {
  request_id: string;
  token: string;
};

type CommandResponse = {
  state: "completed" | "approval_required";
  plan: CommandPlan;
  result?: ExecutionResult;
  approval?: ApprovalPayload;
};

type PendingApproval = {
  requestId: string;
  token: string;
  command: string;
  cwd: string;
  reason: string;
};

type OperatorStatus = {
  enabled: boolean;
  configured: boolean;
  root: string;
  devon_core_executes: boolean;
  boundary: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000/api/v1";

const initialLines: TerminalLine[] = [
  {
    id: 1,
    kind: "system",
    text: "DEVON Operator Terminal. DEVON plans and gates. The Operator Bridge executes.",
  },
  {
    id: 2,
    kind: "system",
    text: "Read-only commands can run directly. Mutating or unknown commands require your approval.",
  },
];

function errorMessage(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

async function readApiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

/**
 * The full Operator Terminal: transcript, approval gate, command form, and
 * the capability-boundary rail. Self-contained so it renders identically
 * embedded in the Command Center and full-screen at /terminal.
 */
export function OperatorTerminal() {
  const [key, setKey] = useState("");
  const [cwd, setCwd] = useState("");
  const [command, setCommand] = useState("");
  const [lines, setLines] = useState<TerminalLine[]>(initialLines);
  const [pending, setPending] = useState<PendingApproval | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<OperatorStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const sequence = useRef(10);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);

  const rootLabel = status?.root || "operator root not loaded";
  const ready = Boolean(status?.enabled && status?.configured);

  const statusLabel = useMemo(() => {
    if (statusError) return "API unavailable";
    if (!status) return "Checking bridge";
    if (!status.enabled) return "Bridge disabled";
    if (!status.configured) return "Key not configured";
    return "Bridge ready";
  }, [status, statusError]);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/operator/status`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(await readApiError(response));
        return response.json() as Promise<OperatorStatus>;
      })
      .then((data) => {
        if (active) setStatus(data);
      })
      .catch((error) => {
        if (active) setStatusError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines, pending]);

  function append(kind: LineKind, text: string) {
    if (!text) return;
    sequence.current += 1;
    setLines((current) => [...current, { id: sequence.current, kind, text }]);
  }

  function renderResult(result: ExecutionResult) {
    if (result.stdout) append("stdout", result.stdout.replace(/\n$/, ""));
    if (result.stderr) append("stderr", result.stderr.replace(/\n$/, ""));
    append(
      result.returncode === 0 ? "system" : "stderr",
      `exit ${result.returncode}${result.timed_out ? " | timed out" : ""}${
        result.truncated ? " | output truncated" : ""
      }`,
    );
  }

  async function submitCommand(event?: FormEvent) {
    event?.preventDefault();
    const raw = command.trim();
    if (!raw || busy || pending) return;
    if (!key) {
      append("stderr", "Operator key required. It is kept only in this page state and is not persisted.");
      return;
    }

    setBusy(true);
    append("command", `${cwd || "."} $ ${raw}`);
    setCommand("");

    try {
      const response = await fetch(`${API_BASE}/operator/command`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Devon-Operator-Key": key,
        },
        body: JSON.stringify({ command: raw, cwd: cwd || null, timeout_seconds: 60 }),
      });

      if (!response.ok) throw new Error(await readApiError(response));
      const data = (await response.json()) as CommandResponse;

      if (data.state === "completed" && data.result) {
        append("system", `${data.plan.risk.toUpperCase()} | ${data.plan.reason}`);
        renderResult(data.result);
        return;
      }

      if (data.state === "approval_required" && data.approval) {
        setPending({
          requestId: data.approval.request_id,
          token: data.approval.token,
          command: data.plan.command,
          cwd: data.plan.cwd,
          reason: data.plan.reason,
        });
        append("approval", `Approval required: ${data.approval.request_id}`);
        return;
      }

      append("stderr", "Operator returned an unrecognized response shape.");
    } catch (error) {
      append("stderr", errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "approve" | "refuse") {
    if (!pending || busy) return;
    const current = pending;
    setBusy(true);

    try {
      const decisionResponse = await fetch(`${API_BASE}/devon/approvals/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: current.requestId,
          token: current.token,
          decision,
          decided_by: "Tee",
        }),
      });

      if (!decisionResponse.ok) throw new Error(await readApiError(decisionResponse));
      const ruling = await decisionResponse.json();

      if (decision === "refuse" || !ruling.approved) {
        append("approval", `${current.requestId} refused. Nothing executed.`);
        setPending(null);
        return;
      }

      append("approval", `${current.requestId} approved. Executing the exact stored command.`);

      const executeResponse = await fetch(`${API_BASE}/operator/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Devon-Operator-Key": key,
        },
        body: JSON.stringify({ request_id: current.requestId, timeout_seconds: 60 }),
      });

      if (!executeResponse.ok) throw new Error(await readApiError(executeResponse));
      const executed = await executeResponse.json();
      renderResult(executed.result as ExecutionResult);
      setPending(null);
    } catch (error) {
      append("stderr", errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function onCommandKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitCommand();
    }
  }

  return (
    <div className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_330px]">
      <section className="flex min-h-[68vh] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#090d12] shadow-2xl shadow-black/30">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/20 px-4 py-3 text-xs">
          <div className="flex items-center gap-2 text-white/55">
            <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-300/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
            <span className="ml-2 font-mono text-white/45">operator@devon</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/30 px-3 py-1">
              <span className={`h-1.5 w-1.5 rounded-full ${ready ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span className="text-white/55">{statusLabel}</span>
            </span>
            <button
              type="button"
              onClick={() => setLines(initialLines)}
              className="rounded-md px-2 py-1 text-white/45 transition hover:bg-white/5 hover:text-white/80"
            >
              Clear transcript
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 font-mono text-[13px] leading-6 sm:px-6">
          {lines.map((line) => (
            <pre
              key={line.id}
              className={`mb-2 whitespace-pre-wrap break-words font-mono ${
                line.kind === "command"
                  ? "text-amber-200"
                  : line.kind === "stderr"
                    ? "text-red-300"
                    : line.kind === "approval"
                      ? "text-sky-300"
                      : line.kind === "system"
                        ? "text-white/45"
                        : "text-emerald-200/90"
              }`}
            >
              {line.text}
            </pre>
          ))}
          <div ref={transcriptEnd} />
        </div>

        {pending && (
          <div className="border-t border-sky-400/20 bg-sky-400/[0.06] px-4 py-4 sm:px-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-300">Human ruling required</p>
                <p className="mt-1 break-all font-mono text-sm text-white">{pending.command}</p>
                <p className="mt-1 text-xs text-white/45">{pending.reason}</p>
                <p className="mt-1 text-xs text-white/35">{pending.requestId}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decide("refuse")}
                  className="rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-white/70 transition hover:bg-white/5 disabled:opacity-40"
                >
                  Refuse
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decide("approve")}
                  className="rounded-lg bg-sky-300 px-4 py-2 text-sm font-semibold text-[#071017] transition hover:bg-sky-200 disabled:opacity-40"
                >
                  Approve and execute
                </button>
              </div>
            </div>
          </div>
        )}

        <form onSubmit={submitCommand} className="border-t border-white/10 bg-black/25 p-4 sm:p-5">
          <div className="mb-3 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.18em] text-white/35">Working directory</span>
              <input
                value={cwd}
                onChange={(event) => setCwd(event.target.value)}
                placeholder="."
                autoComplete="off"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white outline-none transition placeholder:text-white/20 focus:border-amber-300/40"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.18em] text-white/35">Operator key</span>
              <input
                value={key}
                onChange={(event) => setKey(event.target.value)}
                type="password"
                placeholder="Required for execution"
                autoComplete="off"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white outline-none transition placeholder:text-white/20 focus:border-amber-300/40"
              />
            </label>
          </div>

          <div className="flex gap-3 rounded-xl border border-white/10 bg-[#05080c] p-3 focus-within:border-amber-300/35">
            <span className="pt-1 font-mono text-sm text-amber-300">$</span>
            <textarea
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              onKeyDown={onCommandKeyDown}
              disabled={busy || Boolean(pending)}
              rows={2}
              placeholder={pending ? "Rule on the pending command first" : "git status"}
              spellCheck={false}
              className="min-h-12 flex-1 resize-none bg-transparent font-mono text-sm leading-6 text-white outline-none placeholder:text-white/20 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={busy || Boolean(pending) || !command.trim()}
              className="self-end rounded-lg bg-amber-300 px-4 py-2 text-xs font-bold text-[#151006] transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              {busy ? "RUNNING" : "EXECUTE"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-white/30">Enter executes. Shift+Enter adds a line. No shell pipe, redirect, glob, or variable expansion in v1.</p>
        </form>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300/75">Capability boundary</p>
          <h2 className="mt-2 text-base font-semibold text-white">DEVON never executes</h2>
          <p className="mt-2 text-sm leading-6 text-white/50">
            DEVON interprets, plans, validates, and gates. The separate Operator Bridge owns subprocess capability.
          </p>
          <div className="mt-5 space-y-3 text-xs text-white/50">
            <div className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.05] p-3">
              <p className="font-semibold text-emerald-300">READ</p>
              <p className="mt-1">Known read-only commands run after operator-key authentication.</p>
            </div>
            <div className="rounded-xl border border-sky-400/15 bg-sky-400/[0.05] p-3">
              <p className="font-semibold text-sky-300">WRITE / UNKNOWN</p>
              <p className="mt-1">Fails closed into DEVON&apos;s existing human approval gate.</p>
            </div>
            <div className="rounded-xl border border-red-400/15 bg-red-400/[0.05] p-3">
              <p className="font-semibold text-red-300">BLOCKED</p>
              <p className="mt-1">Privilege escalation and obvious host-destruction commands are refused.</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/35">Runtime</p>
          <dl className="mt-4 space-y-3 text-xs">
            <div>
              <dt className="text-white/35">API</dt>
              <dd className="mt-1 break-all font-mono text-white/65">{API_BASE}</dd>
            </div>
            <div>
              <dt className="text-white/35">Operator root</dt>
              <dd className="mt-1 break-all font-mono text-white/65">{rootLabel}</dd>
            </div>
            <div>
              <dt className="text-white/35">Bridge</dt>
              <dd className="mt-1 text-white/65">{statusLabel}</dd>
            </div>
          </dl>
          {statusError && <p className="mt-4 rounded-lg bg-red-400/10 p-3 text-xs leading-5 text-red-300">{statusError}</p>}
        </section>

        <section className="rounded-2xl border border-amber-300/15 bg-amber-300/[0.04] p-5 text-xs leading-5 text-white/45">
          <p className="font-semibold text-amber-200">Security note</p>
          <p className="mt-2">
            Working-directory confinement is not an OS sandbox. Approved commands retain the permissions of the API process user. Containerize the bridge before exposing it beyond a private operator environment.
          </p>
        </section>
      </aside>
    </div>
  );
}
