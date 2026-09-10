"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  approvalBody,
  availableReferences,
  buildDefinition,
  describeStart,
  parseCatalog,
  readCatalogVerdict,
  readGateRuling,
  readListVerdict,
  readSummary,
  reportedLabel,
  REQUIRED_CONFIG_FIELD,
  type PendingGate,
  type StepDraft,
  type StepTypeEntry,
  type WorkflowRead,
} from "@/components/control/workflow-honesty";

/**
 * The door on the workflow engine.
 *
 * WHAT WAS BROKEN. Ten registered operations across six paths in
 * app/api/v1/workflows.py, and 2374 lines behind them, counted on this commit:
 * app/api/v1/workflows.py 617, app/services/workflows.py 612, services/workflows/
 * 905 and app/services/dispatcher.py 240, with app/models/workflow.py 99 and
 * dispatch.py 49 beside them. The workflows table is declared in
 * 001_initial_schema.sql and workflow_runs in 002_workflow_runs.sql, and
 * dispatch.py is a cron entrypoint the API image ships. NOTHING could create a
 * workflow. Measured on this commit by grepping apps/web and packages/ui for
 * "workflows": two hits, app/page.tsx and scripts/honesty-check.ts, and both are
 * prose explaining that the surface does not exist. The engine only ever ran
 * definitions nobody had a way to author, and the approval gate that the whole
 * design is built around had no one standing at it.
 *
 * WHAT THIS DOES. Lists workflows, reads the step catalog, composes and creates
 * one, starts a run, shows the run history, and answers the approval gate.
 *
 * THE GATE IS A RULING, NOT A FORMALITY. app/services/workflows.py seals the
 * rendered payload as a sha256 the moment a run pauses. This panel renders that
 * exact payload in full above the buttons, never a template and never a
 * summary, prints the seal, and sends the seal back as expected_payload_sha256
 * so the server refuses the approval if the run has since moved. When the API
 * reports the gate as diverged there is NO approve control at all, only a
 * reject: approving a payload while displaying a different one is the single
 * worst thing this door could do, and readGateRuling in workflow-honesty.ts is
 * the only thing that may call a gate approvable.
 *
 * NOTHING HERE RUNS AN EFFECT WITHOUT A PERSON. Starting a run executes read
 * steps only; the engine stops in front of every memory_write, decision_draft
 * and export. There is no approve-all, no auto-approve, no bulk control, and no
 * request this panel can send that decides a step the run is not sitting in
 * front of, because approvalBody builds a one-key decisions map from the
 * pending step the API named.
 *
 * WHERE THE NUMBERS COME FROM. Every count on this panel is a field a route
 * sent. A field that did not arrive renders as "not reported" rather than as 0,
 * and a workflow whose stored definition does not parse shows no step count at
 * all, because describe_definition reports zero there and zero is not what it
 * measured.
 */

/* ------------------------------------------------------------------ */
/* Route shapes, as app/api/v1/workflows.py declares them               */
/* ------------------------------------------------------------------ */

type RunSummaryRow = {
  id: string;
  status: string;
  pending_step_id: string | null;
  started_at: string;
  completed_at: string | null;
};

type WorkflowRow = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  project_id: string | null;
  summary: unknown;
  run_count: unknown;
  last_run: RunSummaryRow | null;
  created_at: string;
  updated_at: string;
};

type StepResultRow = {
  step_id?: unknown;
  step_type?: unknown;
  status?: unknown;
  summary?: unknown;
  error?: unknown;
  latency_ms?: unknown;
};

type RunRow = {
  id: string;
  workflow_id: string;
  status: string;
  trigger: string;
  trigger_input: string | null;
  steps: StepResultRow[];
  pending: PendingGate | null;
  approvals: Record<string, unknown>;
  token_usage: Record<string, unknown>;
  latency_ms: unknown;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
};

type Load<T> =
  | { state: "loading" }
  | { state: "locked" }
  | { state: "ok"; value: T }
  | { state: "failed"; detail: string };

type Action =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "failed"; detail: string }
  | { kind: "done"; sentence: string };

/* ------------------------------------------------------------------ */
/* Fetch, with the API's own refusal text kept verbatim                 */
/* ------------------------------------------------------------------ */

/**
 * FastAPI answers a refusal with {"detail": ...}. Those sentences are written
 * by the engine and they are more precise than anything this panel could
 * invent, so they are surfaced as they arrive rather than replaced by a
 * generic message.
 */
function detailFrom(status: number, body: unknown, route: string): string {
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return `${route} answered ${status}: ${detail}`;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      const msg = typeof first?.msg === "string" ? first.msg : JSON.stringify(detail[0]);
      const loc = Array.isArray(first?.loc) ? ` at ${first.loc.join(".")}` : "";
      return `${route} answered ${status}: ${msg}${loc}`;
    }
  }
  return `${route} answered ${status}`;
}

type Answer = { ok: true; data: unknown } | { ok: false; detail: string };

async function call(
  path: string,
  route: string,
  token: string,
  init?: RequestInit,
): Promise<Answer> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers || {}),
      },
    });
    if (!response.ok) {
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        body = null;
      }
      return { ok: false, detail: detailFrom(response.status, body, route) };
    }
    if (response.status === 204) return { ok: true, data: null };
    return { ok: true, data: await response.json() };
  } catch (error) {
    return {
      ok: false,
      detail: error instanceof Error ? error.message : `the request to ${route} did not complete`,
    };
  }
}

function asRead<T>(load: Load<T[]>): WorkflowRead {
  // "loading" reports as locked rather than as a failure or a count: mid flight
  // is not a fact about the route in either direction. The one thing that must
  // never happen is a failed read arriving here as a count, which is why the
  // failed branch carries no number at all.
  if (load.state === "ok") return { state: "ok", count: load.value.length };
  if (load.state === "failed") return { state: "failed", detail: load.detail };
  return { state: "locked" };
}

function whenLabel(iso: string | null | undefined): string {
  if (!iso) return "not recorded";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return String(iso);
  return at.toLocaleString();
}

function toneClass(tone: "neutral" | "warn" | "good" | "bad"): string {
  if (tone === "good") return "border-emerald-400/30 text-emerald-200";
  if (tone === "warn") return "border-amber-400/35 text-amber-200";
  if (tone === "bad") return "border-red-400/40 text-red-200";
  return "border-white/15 text-white/70";
}

let draftSeq = 0;
function newDraft(type: string): StepDraft {
  draftSeq += 1;
  return { key: `draft-${draftSeq}`, id: "", type, body: "", rawConfig: "{}" };
}

/* ------------------------------------------------------------------ */
/* The panel                                                            */
/* ------------------------------------------------------------------ */

export function WorkflowDoor() {
  const [list, setList] = useState<Load<WorkflowRow[]>>({ state: "loading" });
  const [catalog, setCatalog] = useState<Load<StepTypeEntry[]>>({ state: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Load<RunRow[]>>({ state: "loading" });
  // The workflow id `runs` was read for. One `runs` state is shared by every
  // row, so without this the rows of the workflow that was open a moment ago
  // render inside the card of the one just opened, gate and approve control
  // included, until the effect below fires. Found by an adversary on
  // 2026-09-10. The server answers 404 on a ruling sent that way, so nothing was
  // ever written, but the ruling would have been given over another workflow's
  // payload, which is the same defect the seal exists to prevent.
  const [runsFor, setRunsFor] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const [composerOpen, setComposerOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [drafts, setDrafts] = useState<StepDraft[]>([]);
  const [creating, setCreating] = useState<Action>({ kind: "idle" });

  const [runInput, setRunInput] = useState("");
  const [starting, setStarting] = useState<Action>({ kind: "idle" });
  const [ruling, setRuling] = useState<Action>({ kind: "idle" });

  /* -------------------------------------------------------------- */
  /* Reads                                                            */
  /* -------------------------------------------------------------- */

  const loadTop = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setList({ state: "locked" });
      setCatalog({ state: "locked" });
      setRuns({ state: "locked" });
      return;
    }
    setList({ state: "loading" });
    setCatalog({ state: "loading" });

    const [listed, catalogued] = await Promise.all([
      call("/workflows?limit=100", "the workflow list route", token),
      call("/workflows/step-types", "the step catalog route", token),
    ]);

    if (!listed.ok) {
      setList({ state: "failed", detail: listed.detail });
    } else if (!Array.isArray(listed.data)) {
      // An unreadable payload is a failed read. Falling through to an empty
      // array here would render "you have no workflows" over an unknown list.
      setList({ state: "failed", detail: "the workflow list route did not return a list" });
    } else {
      setList({ state: "ok", value: listed.data as WorkflowRow[] });
      setCheckedAt(new Date());
    }

    if (!catalogued.ok) {
      setCatalog({ state: "failed", detail: catalogued.detail });
    } else {
      const parsed = parseCatalog(catalogued.data);
      if (parsed === null) {
        setCatalog({
          state: "failed",
          detail: "the step catalog route did not return the step_types shape this panel reads",
        });
      } else {
        setCatalog({ state: "ok", value: parsed });
      }
    }
  }, []);

  const loadRuns = useCallback(async (workflowId: string) => {
    const token = readDevonToken();
    setRunsFor(workflowId);
    if (!token) {
      setRuns({ state: "locked" });
      return;
    }
    setRuns({ state: "loading" });
    const answer = await call(
      `/workflows/${encodeURIComponent(workflowId)}/runs?limit=25`,
      "the run history route",
      token,
    );
    if (!answer.ok) {
      setRuns({ state: "failed", detail: answer.detail });
      return;
    }
    if (!Array.isArray(answer.data)) {
      setRuns({ state: "failed", detail: "the run history route did not return a list" });
      return;
    }
    setRuns({ state: "ok", value: answer.data as RunRow[] });
  }, []);

  useEffect(() => {
    void loadTop();
    // Same storage wake as SkillProposalGate, so signing in through Talk to
    // DEVON in another tab brings this panel up without a reload.
    const onStorage = () => void loadTop();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [loadTop]);

  useEffect(() => {
    if (!selectedId) {
      // NOT { state: "ok", value: [] }. The run history route was never called
      // here, and an ok read of zero rows renders "This workflow has never run",
      // which would be a fabricated successful read of a route nobody asked.
      setRuns({ state: "loading" });
      setRunsFor(null);
      return;
    }
    void loadRuns(selectedId);
  }, [selectedId, loadRuns]);

  const workflows = list.state === "ok" ? list.value : [];
  const selected = useMemo(
    () => workflows.find((row) => row.id === selectedId) ?? null,
    [workflows, selectedId],
  );

  const listVerdict = readListVerdict(asRead(list));
  const catalogVerdict = readCatalogVerdict(asRead(catalog));

  /* -------------------------------------------------------------- */
  /* Writes                                                           */
  /* -------------------------------------------------------------- */

  const built = useMemo(() => buildDefinition(drafts), [drafts]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const token = readDevonToken();
    if (!token) {
      setCreating({ kind: "failed", detail: "no session token in this browser, so nothing was sent" });
      return;
    }
    if (!name.trim()) {
      setCreating({ kind: "failed", detail: "a workflow needs a name" });
      return;
    }
    if (!built.ok) {
      setCreating({
        kind: "failed",
        detail: `this composer will not send the definition yet: ${built.refusals.join(" ")}`,
      });
      return;
    }
    setCreating({ kind: "sending" });
    const answer = await call("/workflows", "the create route", token, {
      method: "POST",
      body: JSON.stringify({
        name: name.trim(),
        description: description.trim() || null,
        definition: built.definition,
      }),
    });
    if (!answer.ok) {
      setCreating({ kind: "failed", detail: answer.detail });
      return;
    }
    const created = answer.data as WorkflowRow;
    setCreating({
      kind: "done",
      sentence: `Created as ${created.id} with status ${created.status}. It has run nothing: a run is started below and every effect step in it stops for your ruling.`,
    });
    setName("");
    setDescription("");
    setDrafts([]);
    setComposerOpen(false);
    await loadTop();
    setSelectedId(created.id);
  }

  async function startRun() {
    if (!selected) return;
    const token = readDevonToken();
    if (!token) {
      setStarting({ kind: "failed", detail: "no session token in this browser, so nothing was sent" });
      return;
    }
    setStarting({ kind: "sending" });
    const answer = await call(
      `/workflows/${encodeURIComponent(selected.id)}/runs`,
      "the start run route",
      token,
      { method: "POST", body: JSON.stringify({ input: runInput }) },
    );
    if (!answer.ok) {
      setStarting({ kind: "failed", detail: answer.detail });
      return;
    }
    const run = answer.data as RunRow;
    setStarting({
      kind: "done",
      sentence:
        run.status === "awaiting_approval"
          ? `Run ${run.id} ran its read steps and STOPPED in front of ${run.pending?.step_id ?? "a step the API did not name"}. Nothing was written. Your ruling is below.`
          : `Run ${run.id} finished with status ${run.status}. Nothing was written without a ruling.`,
    });
    setRunInput("");
    await loadRuns(selected.id);
    await loadTop();
  }

  async function rule(run: RunRow, decision: "approved" | "rejected") {
    if (!selected) return;
    const pending = run.pending;
    if (!pending) return;
    const gate = readGateRuling(run.status, pending);
    let body;
    try {
      body = approvalBody(gate, pending, decision);
    } catch (error) {
      // approvalBody refuses to build a ruling the gate does not allow. Reaching
      // here means a control was rendered that should not have been, so the
      // refusal is surfaced rather than swallowed.
      setRuling({
        kind: "failed",
        detail: error instanceof Error ? error.message : "the ruling was refused before it was sent",
      });
      return;
    }
    const token = readDevonToken();
    if (!token) {
      setRuling({ kind: "failed", detail: "no session token in this browser, so nothing was sent" });
      return;
    }
    setRuling({ kind: "sending" });
    const answer = await call(
      `/workflows/${encodeURIComponent(selected.id)}/runs/${encodeURIComponent(run.id)}/approve`,
      "the approve route",
      token,
      { method: "POST", body: JSON.stringify(body) },
    );
    if (!answer.ok) {
      setRuling({ kind: "failed", detail: answer.detail });
      await loadRuns(selected.id);
      return;
    }
    const after = answer.data as RunRow;
    setRuling({
      kind: "done",
      sentence:
        decision === "rejected"
          ? `Rejected. The step did not execute and the run is now ${after.status}.`
          : `Approved. The engine executed ${pending.step_id} and the run is now ${after.status}.`,
    });
    await loadRuns(selected.id);
    await loadTop();
  }

  /* -------------------------------------------------------------- */
  /* Render                                                           */
  /* -------------------------------------------------------------- */

  return (
    <div className="space-y-5">
      <Verdict verdict={listVerdict} loading={list.state === "loading"} loadingText="Reading the workflow list." />

      {list.state === "failed" ? (
        <p className="text-xs leading-relaxed text-white/50">
          This is a failed read, not an empty list. Workflows may exist on this account and a run
          of one may be waiting on a ruling this panel cannot see.
        </p>
      ) : null}

      <Verdict
        verdict={catalogVerdict}
        loading={catalog.state === "loading"}
        loadingText="Reading the step catalog."
      />

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void loadTop()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Refresh
        </button>
        {catalogVerdict.semanticsKnown ? (
          <button
            type="button"
            onClick={() => setComposerOpen((open) => !open)}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
          >
            {composerOpen ? "Close composer" : "Compose a workflow"}
          </button>
        ) : (
          <p className="text-[11px] leading-relaxed text-white/50">
            The composer is closed because the step catalog is not readable. Which steps stop for a
            ruling is that route&apos;s answer, and this panel will not offer step types it has not
            been told about.
          </p>
        )}
        {checkedAt ? (
          <p className="text-[11px] text-white/50">List read {checkedAt.toLocaleTimeString()}.</p>
        ) : null}
      </div>

      {composerOpen && catalog.state === "ok" ? (
        <Composer
          types={catalog.value}
          name={name}
          setName={setName}
          description={description}
          setDescription={setDescription}
          drafts={drafts}
          setDrafts={setDrafts}
          built={built}
          creating={creating}
          onSubmit={create}
        />
      ) : null}

      {creating.kind === "done" ? (
        <p className="text-xs leading-relaxed text-emerald-200">{creating.sentence}</p>
      ) : null}
      {creating.kind === "failed" && !composerOpen ? (
        <p className="text-xs leading-relaxed text-red-300">
          The workflow was not created: {creating.detail}.
        </p>
      ) : null}

      {list.state === "ok" && list.value.length > 0 ? (
        <ul className="space-y-2">
          {list.value.map((row) => {
            const facts = readSummary(row.summary);
            const isOpen = row.id === selectedId;
            const waiting = row.last_run?.status === "awaiting_approval";
            return (
              <li
                key={row.id}
                className="min-w-0 rounded-xl border border-white/10 bg-black/25 px-3 py-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold tracking-tight text-white">{row.name}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {waiting ? (
                      <span className="rounded-full border border-amber-400/40 bg-amber-400/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-200">
                        Awaiting ruling
                      </span>
                    ) : null}
                    <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
                      {row.status}
                    </span>
                  </div>
                </div>

                {row.description ? (
                  <p className="mt-1.5 text-xs leading-relaxed text-white/60">{row.description}</p>
                ) : null}

                <p
                  className={`mt-1.5 text-xs leading-relaxed ${facts.parses ? "text-white/60" : "text-red-300"}`}
                >
                  {facts.sentence}
                </p>

                <dl className="mt-2 grid gap-1 text-[11px] text-white/50 sm:grid-cols-2">
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Runs recorded</dt>
                    <dd className="min-w-0 tabular-nums text-white/70">
                      {reportedLabel(row.run_count)}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Last run</dt>
                    <dd className="min-w-0 text-white/70">
                      {row.last_run
                        ? `${row.last_run.status}, ${whenLabel(row.last_run.started_at)}`
                        : "never run"}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Workflow</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">{row.id}</dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Created</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(row.created_at)}</dd>
                  </div>
                </dl>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(isOpen ? null : row.id);
                    setStarting({ kind: "idle" });
                    setRuling({ kind: "idle" });
                    // Same commit as the selection change, so the card that
                    // opens cannot paint the rows of the one that was open.
                    setRuns({ state: "loading" });
                    setRunsFor(null);
                  }}
                  className="mt-2.5 rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                >
                  {isOpen ? "Close runs" : "Open runs and gates"}
                </button>

                {isOpen ? (
                  <div className="mt-3 space-y-4 border-t border-white/10 pt-3">
                    <StartRun
                      workflow={row}
                      sentence={describeStart(facts, row.status)}
                      input={runInput}
                      setInput={setRunInput}
                      starting={starting}
                      onStart={() => void startRun()}
                    />
                    <RunHistory
                      runs={runsFor === row.id ? runs : { state: "loading" }}
                      ruling={ruling}
                      onRule={(run, decision) => void rule(run, decision)}
                      onRetry={() => void loadRuns(row.id)}
                    />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      <p className="text-xs leading-relaxed text-white/50">
        Runs are started here by hand. A run reads and reasons unattended and then stops in front of
        every step that writes something, and this panel is the only place in the estate where that
        stop can be answered. Approving one is a ruling on the exact payload printed above the
        buttons, and the hash of that payload is sent with the approval so the server refuses it if
        the run has moved on.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pieces                                                               */
/* ------------------------------------------------------------------ */

function Verdict({
  verdict,
  loading,
  loadingText,
}: {
  verdict: { label: string; tone: "neutral" | "warn" | "good"; sentence: string };
  loading: boolean;
  loadingText: string;
}) {
  if (loading) return <p className="text-xs text-white/50">{loadingText}</p>;
  return (
    <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${toneClass(verdict.tone)}`}>
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
        {verdict.label}
      </p>
      <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
    </div>
  );
}

function StartRun({
  workflow,
  sentence,
  input,
  setInput,
  starting,
  onStart,
}: {
  workflow: WorkflowRow;
  sentence: string;
  input: string;
  setInput: (value: string) => void;
  starting: Action;
  onStart: () => void;
}) {
  const inputId = `wf-run-input-${workflow.id}`;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
        Start a run
      </p>
      <p className="text-xs leading-relaxed text-white/60">{sentence}</p>
      <label className="sr-only" htmlFor={inputId}>
        Trigger input for this run
      </label>
      <textarea
        id={inputId}
        value={input}
        onChange={(event) => setInput(event.target.value)}
        rows={2}
        placeholder="The input every {{ input }} in this workflow renders to. May be left empty."
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
      />
      <button
        type="button"
        disabled={starting.kind === "sending"}
        onClick={onStart}
        className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
      >
        {starting.kind === "sending" ? "Starting" : "Start a run"}
      </button>
      {starting.kind === "failed" ? (
        <p className="text-[11px] leading-relaxed text-red-300">
          The run was not started: {starting.detail}.
        </p>
      ) : null}
      {starting.kind === "done" ? (
        <p className="text-[11px] leading-relaxed text-white/70">{starting.sentence}</p>
      ) : null}
    </div>
  );
}

function RunHistory({
  runs,
  ruling,
  onRule,
  onRetry,
}: {
  runs: Load<RunRow[]>;
  ruling: Action;
  onRule: (run: RunRow, decision: "approved" | "rejected") => void;
  onRetry: () => void;
}) {
  if (runs.state === "loading") {
    return <p className="text-xs text-white/50">Reading the run history.</p>;
  }
  if (runs.state === "locked") {
    return (
      <p className="text-xs leading-relaxed text-white/50">
        No session token in this browser, so the run history was not requested. Nothing is claimed
        about whether this workflow has ever run.
      </p>
    );
  }
  if (runs.state === "failed") {
    return (
      <div className="space-y-2">
        <p className="text-xs leading-relaxed text-red-300">
          The run history could not be read: {runs.detail}.
        </p>
        <p className="text-xs leading-relaxed text-white/50">
          This is a failed read, not a workflow with no runs. A run of this workflow may be waiting
          on a ruling right now and this panel cannot see it.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }
  if (runs.value.length === 0) {
    return (
      <p className="text-xs leading-relaxed text-white/70">
        The run history route answered and returned no rows. This workflow has never run.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
        Runs, newest first
      </p>
      {runs.value.map((run) => (
        <RunCard key={run.id} run={run} ruling={ruling} onRule={onRule} />
      ))}
    </div>
  );
}

function RunCard({
  run,
  ruling,
  onRule,
}: {
  run: RunRow;
  ruling: Action;
  onRule: (run: RunRow, decision: "approved" | "rejected") => void;
}) {
  const gate = readGateRuling(run.status, run.pending);
  const steps = Array.isArray(run.steps) ? run.steps : [];
  const usage = (run.token_usage || {}) as Record<string, unknown>;

  return (
    <div className="min-w-0 rounded-xl border border-white/10 bg-black/30 px-3 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="min-w-0 break-all font-mono text-[11px] text-white/70">{run.id}</p>
        <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
          {run.status}
        </span>
      </div>

      <dl className="mt-2 grid gap-1 text-[11px] text-white/50 sm:grid-cols-2">
        <div className="flex min-w-0 items-baseline gap-1.5">
          <dt className="shrink-0">Trigger</dt>
          <dd className="min-w-0 text-white/70">{run.trigger}</dd>
        </div>
        <div className="flex min-w-0 items-baseline gap-1.5">
          <dt className="shrink-0">Started</dt>
          <dd className="min-w-0 text-white/70">{whenLabel(run.started_at)}</dd>
        </div>
        <div className="flex min-w-0 items-baseline gap-1.5">
          <dt className="shrink-0">Finished</dt>
          <dd className="min-w-0 text-white/70">
            {run.completed_at ? whenLabel(run.completed_at) : "still open"}
          </dd>
        </div>
        <div className="flex min-w-0 items-baseline gap-1.5">
          <dt className="shrink-0">Tokens</dt>
          <dd className="min-w-0 tabular-nums text-white/70">
            {reportedLabel(usage.total_tokens)} total ({reportedLabel(usage.input_tokens)} in,{" "}
            {reportedLabel(usage.output_tokens)} out)
          </dd>
        </div>
      </dl>

      {run.trigger_input ? (
        <>
          <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
            Trigger input
          </p>
          <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-[11px] leading-relaxed text-white/75">
            {run.trigger_input}
          </pre>
        </>
      ) : null}

      {run.error_message ? (
        <p className="mt-2 text-[11px] leading-relaxed text-red-300">
          The engine recorded an error: {run.error_message}
        </p>
      ) : null}

      {steps.length > 0 ? (
        <>
          <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
            Steps the engine actually ran
          </p>
          <ul className="mt-1 space-y-1.5">
            {steps.map((step, index) => (
              <li
                key={`${String(step.step_id ?? index)}-${index}`}
                className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2"
              >
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="font-mono text-[11px] text-white/75">
                    {String(step.step_id ?? "step id not reported")}
                  </span>
                  <span className="text-[11px] text-white/50">
                    {String(step.step_type ?? "type not reported")}
                  </span>
                  <span
                    className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${
                      step.status === "completed"
                        ? "text-emerald-200"
                        : step.status === "rejected"
                          ? "text-white/70"
                          : "text-red-300"
                    }`}
                  >
                    {String(step.status ?? "status not reported")}
                  </span>
                </div>
                {typeof step.summary === "string" && step.summary ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-white/70">{step.summary}</p>
                ) : null}
                {typeof step.error === "string" && step.error ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-red-300">{step.error}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-2 text-[11px] leading-relaxed text-white/50">
          The run carries no step results.
        </p>
      )}

      {Object.keys(run.approvals || {}).length > 0 ? (
        <>
          <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
            Rulings already recorded
          </p>
          <ul className="mt-1 space-y-1">
            {Object.entries(run.approvals).map(([stepId, entry]) => {
              const record = (entry || {}) as Record<string, unknown>;
              return (
                <li key={stepId} className="text-[11px] leading-relaxed text-white/70">
                  <span className="font-mono">{stepId}</span>{" "}
                  {String(record.decision ?? "decision not reported")} by{" "}
                  <span className="font-mono break-all">
                    {String(record.actor_id ?? "actor not reported")}
                  </span>{" "}
                  at {whenLabel(typeof record.at === "string" ? record.at : null)}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {run.status === "awaiting_approval" ? (
        <Gate run={run} gate={gate} ruling={ruling} onRule={onRule} />
      ) : null}
    </div>
  );
}

/**
 * The human gate, presented as a ruling.
 *
 * The payload is printed in full before any button exists, field by field and
 * then as the exact JSON the seal was taken over. There is no clamp and no
 * expander: the thing being approved is the artifact, and a title is not the
 * artifact. When the gate is not approvable there is no approve control in the
 * DOM at all, rather than a disabled one, because a disabled control still
 * reads as "this is the normal thing to do here".
 */
function Gate({
  run,
  gate,
  ruling,
  onRule,
}: {
  run: RunRow;
  gate: ReturnType<typeof readGateRuling>;
  ruling: Action;
  onRule: (run: RunRow, decision: "approved" | "rejected") => void;
}) {
  const pending = run.pending;
  const sending = ruling.kind === "sending";

  return (
    <div className={`mt-3 rounded-xl border bg-black/40 px-3 py-3 ${toneClass(gate.tone)}`}>
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
        {gate.label}
      </p>
      <p className="mt-1.5 text-xs leading-relaxed">{gate.sentence}</p>

      {pending ? (
        <>
          <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
            What would be written
          </p>
          <dl className="mt-1 grid gap-1 text-[11px] text-white/50 sm:grid-cols-2">
            <div className="flex min-w-0 items-baseline gap-1.5">
              <dt className="shrink-0">Step</dt>
              <dd className="min-w-0 break-all font-mono text-white/75">{pending.step_id}</dd>
            </div>
            <div className="flex min-w-0 items-baseline gap-1.5">
              <dt className="shrink-0">Kind</dt>
              <dd className="min-w-0 text-white/75">{pending.step_type}</dd>
            </div>
            <div className="flex min-w-0 items-baseline gap-1.5">
              <dt className="shrink-0">Filed under project</dt>
              <dd className="min-w-0 break-all font-mono text-white/75">
                {pending.project_id ?? "no project"}
              </dd>
            </div>
            <div className="flex min-w-0 items-baseline gap-1.5">
              <dt className="shrink-0">Payload seal</dt>
              <dd className="min-w-0 break-all font-mono text-white/75">
                {pending.payload_sha256 || "no seal sent"}
              </dd>
            </div>
          </dl>

          {pending.preview && typeof pending.preview === "object" ? (
            <ul className="mt-2 space-y-1.5">
              {Object.entries(pending.preview).map(([key, value]) => (
                <li key={key}>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/55">
                    {key}
                  </p>
                  <pre className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/50 px-2.5 py-2 text-[11px] leading-relaxed text-white/80">
                    {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
                  </pre>
                </li>
              ))}
            </ul>
          ) : null}

          <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
            The payload the seal was taken over
          </p>
          <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/50 px-2.5 py-2 text-[11px] leading-relaxed text-white/75">
            {JSON.stringify(
              {
                step_id: pending.step_id,
                step_type: pending.step_type,
                preview: pending.preview,
                project_id: pending.project_id,
              },
              null,
              2,
            )}
          </pre>
        </>
      ) : (
        <p className="mt-2 text-[11px] leading-relaxed text-white/70">
          The API sent no pending block with this run, so there is nothing to display and nothing
          here to rule on.
        </p>
      )}

      {/* Equal weight, reject first. A gate where refusing costs more than
          accepting is not a gate. */}
      <div className="mt-3 flex flex-wrap gap-2">
        {gate.rejectable && pending ? (
          <button
            type="button"
            disabled={sending}
            onClick={() => onRule(run, "rejected")}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
          >
            Reject, write nothing
          </button>
        ) : null}
        {gate.approvable && pending ? (
          <button
            type="button"
            disabled={sending}
            onClick={() => onRule(run, "approved")}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
          >
            Approve this {pending.step_type}
          </button>
        ) : null}
      </div>
      {!gate.approvable ? (
        <p className="mt-1.5 text-[11px] leading-relaxed text-white/60">
          No approval is offered for this gate. Nothing on this panel can execute the step while it
          is in this state, and the API refuses it as well.
        </p>
      ) : null}

      {ruling.kind === "sending" ? (
        <p className="mt-2 text-[11px] text-white/70">Sending the ruling.</p>
      ) : null}
      {ruling.kind === "failed" ? (
        <p className="mt-2 text-[11px] leading-relaxed text-red-300">
          The ruling was not recorded: {ruling.detail}.
        </p>
      ) : null}
      {ruling.kind === "done" ? (
        <p className="mt-2 text-[11px] leading-relaxed text-white/75">{ruling.sentence}</p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The composer                                                         */
/* ------------------------------------------------------------------ */

function Composer({
  types,
  name,
  setName,
  description,
  setDescription,
  drafts,
  setDrafts,
  built,
  creating,
  onSubmit,
}: {
  types: StepTypeEntry[];
  name: string;
  setName: (value: string) => void;
  description: string;
  setDescription: (value: string) => void;
  drafts: StepDraft[];
  setDrafts: (value: StepDraft[]) => void;
  built: ReturnType<typeof buildDefinition>;
  creating: Action;
  onSubmit: (event: React.FormEvent) => void;
}) {
  const gated = types.filter((entry) => entry.requires_approval).map((entry) => entry.type);

  function patch(key: string, change: Partial<StepDraft>) {
    setDrafts(drafts.map((draft) => (draft.key === key ? { ...draft, ...change } : draft)));
  }

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3 rounded-xl border border-white/10 bg-black/25 px-3 py-3"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
        Compose a workflow
      </p>
      <p className="text-xs leading-relaxed text-white/60">
        The trigger is manual. The step catalog reports only manual as dispatchable on this build,
        so a schedule or event trigger composed here would be one this API says nothing fires; those
        are storable through the API itself and are deliberately not offered on this panel. Steps
        that stop for a ruling, as that same route reports them:{" "}
        {gated.length ? gated.join(", ") : "none on this build"}.
      </p>

      <div>
        <label className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60" htmlFor="wf-name">
          Name
        </label>
        <input
          id="wf-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="What this workflow is for"
          className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
        />
      </div>

      <div>
        <label
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60"
          htmlFor="wf-description"
        >
          Description
        </label>
        <textarea
          id="wf-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
          placeholder="Optional. What a person reading this later needs to know."
          className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
        />
      </div>

      <div className="space-y-2">
        {drafts.map((draft, index) => {
          const entry = types.find((candidate) => candidate.type === draft.type);
          const field = REQUIRED_CONFIG_FIELD[draft.type];
          const refs = availableReferences(drafts, index);
          return (
            <div key={draft.key} className="rounded-lg border border-white/10 bg-black/30 px-2.5 py-2.5">
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-0 flex-1">
                  <label
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60"
                    htmlFor={`wf-step-id-${draft.key}`}
                  >
                    Step {index + 1} id
                  </label>
                  <input
                    id={`wf-step-id-${draft.key}`}
                    aria-label={`Step ${index + 1} id`}
                    value={draft.id}
                    onChange={(event) => patch(draft.key, { id: event.target.value })}
                    placeholder="lowercase_with_underscores"
                    className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 font-mono text-[11px] text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <label
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60"
                    htmlFor={`wf-step-type-${draft.key}`}
                  >
                    Type
                  </label>
                  <select
                    id={`wf-step-type-${draft.key}`}
                    value={draft.type}
                    onChange={(event) => patch(draft.key, { type: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-[11px] text-white/85 outline-none transition focus:border-white/25"
                  >
                    {types.map((candidate) => (
                      <option key={candidate.type} value={candidate.type}>
                        {candidate.type}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => setDrafts(drafts.filter((row) => row.key !== draft.key))}
                  className="rounded-lg border border-white/15 px-2.5 py-1.5 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                >
                  Remove
                </button>
              </div>

              <p className="mt-1.5 text-[11px] leading-relaxed text-white/60">
                {entry?.description || "The catalog sent no description for this type."}{" "}
                {entry
                  ? entry.requires_approval
                    ? "The catalog reports this step as requiring a ruling, so every run stops in front of it."
                    : "The catalog reports this step as running unattended."
                  : "This type was not in the catalog, so nothing is claimed about whether it stops for a ruling."}
              </p>

              {field !== undefined ? (
                <div className="mt-2">
                  <label
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60"
                    htmlFor={`wf-step-body-${draft.key}`}
                  >
                    {field}
                  </label>
                  <textarea
                    id={`wf-step-body-${draft.key}`}
                    value={draft.body}
                    onChange={(event) => patch(draft.key, { body: event.target.value })}
                    rows={3}
                    placeholder={`The ${field} this step runs on`}
                    className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-[11px] leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
                  />
                  <p className="mt-1 text-[11px] leading-relaxed text-white/55">
                    References this step may use: {refs.map((ref) => `{{ ${ref} }}`).join(", ")}. The
                    definition parser refuses a forward or unknown reference at save time, and its
                    refusal is printed here verbatim.
                  </p>
                </div>
              ) : (
                <div className="mt-2">
                  <label
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60"
                    htmlFor={`wf-step-raw-${draft.key}`}
                  >
                    Raw config JSON
                  </label>
                  <textarea
                    id={`wf-step-raw-${draft.key}`}
                    value={draft.rawConfig}
                    onChange={(event) => patch(draft.key, { rawConfig: event.target.value })}
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-white/85 outline-none transition focus:border-white/25"
                  />
                  <p className="mt-1 text-[11px] leading-relaxed text-white/55">
                    This build has no field map for the type {draft.type}, so the composer will not
                    guess a field name for it. Write the config object the API expects.
                  </p>
                </div>
              )}
            </div>
          );
        })}

        <button
          type="button"
          onClick={() => setDrafts([...drafts, newDraft(types[0]?.type ?? "")])}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
        >
          Add a step
        </button>
      </div>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
          Exactly what will be sent
        </p>
        {built.ok ? (
          <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/45 px-2.5 py-2 text-[11px] leading-relaxed text-white/75">
            {JSON.stringify(built.definition, null, 2)}
          </pre>
        ) : (
          <ul className="mt-1 space-y-1">
            {built.refusals.map((refusal) => (
              <li key={refusal} className="text-[11px] leading-relaxed text-amber-200">
                {refusal}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-[11px] leading-relaxed text-white/55">
          Those are this panel declining to send something it can already see is malformed. They are
          not a verdict that the definition is valid: the parser in services/workflows/definition.py
          decides that, and whatever it says comes back as a refusal printed here word for word.
        </p>
      </div>

      <button
        type="submit"
        disabled={creating.kind === "sending" || !built.ok || !name.trim()}
        className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/10 disabled:text-white/50"
      >
        {creating.kind === "sending" ? "Creating" : "Create as a draft"}
      </button>
      <p className="text-[11px] leading-relaxed text-white/55">
        A created workflow starts in status draft and runs nothing on its own. Creating it is not
        starting it.
      </p>

      {creating.kind === "failed" ? (
        <p className="text-[11px] leading-relaxed text-red-300">
          The workflow was not created: {creating.detail}.
        </p>
      ) : null}
    </form>
  );
}
