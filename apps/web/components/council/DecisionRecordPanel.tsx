"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  describeWriteOutcome,
  parseDecisionList,
  parseDecisionRow,
  prepareRuling,
  readDecisionsVerdict,
  rulingForOption,
  trackedState,
  type DecisionRow,
  type DecisionsRead,
  type TrackedState,
} from "@/components/council/decision-record";

/**
 * The door on the decision record.
 *
 * WHAT WAS BROKEN. app/api/v1/decisions.py carries five operations across three
 * paths and is registered at app/api/v1/router.py:50. On commit 32883cf a grep
 * across apps/web and packages/ui found no caller: the two hits were a comment
 * on the deliberate page saying so and the CLAIMS entry in
 * scripts/honesty-check.ts holding the landing page to it. The Council exists to
 * put a human at the end of it, and the record of that human final call had no
 * surface, so nothing on this estate could be looked back at.
 *
 * WHAT THIS PANEL REACHES, AND WHY ALL OF IT
 *
 *   GET    /decisions              the record itself
 *   GET    /decisions/{id}         re-read one row after ruling on it
 *   PATCH  /decisions/{id}         the human final call
 *   POST   /decisions/from-message a Council exchange put on the record
 *
 * POST /decisions is the deliberate page, which is where a package is ruled on.
 * PATCH is here because from-message creates a decision with status "open" and
 * no chosen_option: a panel that could create those and not rule on them would
 * close one door by opening another.
 *
 * WHY THE EXCHANGE PICKER IS NOT A FIELD TO PASTE AN ID INTO. The from-message
 * route wants an assistant message id. A box to paste one into is the same
 * shape as the platform console that scripts/control-check.ts already records as
 * a surface nobody can really use, so the conversations and their assistant
 * turns are read and listed and a person presses a button on the exchange they
 * mean.
 *
 * WHY STATUS IS ALWAYS SENT. update_decision advances an open decision to
 * "decided" by itself when chosen_option arrives with no status. Recording a
 * note against a decision and closing it are two different acts, so the status
 * on every request from here is read off the control the human set.
 *
 * NOTHING HERE RUNS AN EFFECT. Every request on this panel reads or writes the
 * decision record. No tool is invoked, nothing is materialized and nothing is
 * spawned, so the human gate on WRITE and HIGH_IMPACT tools is untouched by it.
 */

type Load = { state: "loading" } | DecisionsRead;

type RowOutcome =
  | { kind: "sending" }
  | { kind: "failed"; detail: string }
  | { kind: "done"; sentence: string };

type Draft = { note: string; call: string; status: "open" | "decided" };

type ConversationRow = { id: string; title: string | null; updatedAt: string | null };

type ConversationsLoad =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "locked" }
  | { state: "failed"; detail: string }
  | { state: "ok"; rows: ConversationRow[] };

type MessageRow = { id: string; content: string; createdAt: string | null };

type MessagesLoad =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "failed"; detail: string }
  | { state: "ok"; rows: MessageRow[]; total: number };

const EMPTY_DRAFT: Draft = { note: "", call: "", status: "decided" };

/**
 * The wire from a fetch result into the verdict ladder, and the one line in
 * this file that can invert the panel's only load bearing claim.
 *
 * A critic beat the learning panel on 2026-09-10 not through its ladder but
 * through the adapter feeding it: one line turning a failed read into
 * `{state: "ok", count: 0}` rendered "LEARNING EMPTY" over a store that had not
 * been read, and every check passed. So this adapter is a named module level
 * function rather than an inline expression, because that is the version
 * scripts/decisions-check.ts can find, read and refuse.
 *
 * "loading" is deliberately reported as locked rather than as a failure or as a
 * row count: mid flight is not a fact about the record either way.
 */
function asRead(load: Load): DecisionsRead {
  if (load.state === "ok") {
    return { state: "ok", rows: load.rows, malformed: load.malformed };
  }
  if (load.state === "failed") {
    return { state: "failed", detail: load.detail };
  }
  return { state: "locked" };
}

function whenLabel(iso: string | null): string {
  if (!iso) return "the route did not say";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString();
}

function failureDetail(error: unknown): string {
  return error instanceof Error ? error.message : "the request did not complete";
}

export function DecisionRecordPanel() {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, RowOutcome>>({});
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});

  const [conversations, setConversations] = useState<ConversationsLoad>({ state: "idle" });
  const [selected, setSelected] = useState<string>("");
  const [messages, setMessages] = useState<MessagesLoad>({ state: "idle" });
  const [fromMessage, setFromMessage] = useState<Record<string, RowOutcome>>({});

  const read = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setLoad({ state: "locked" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/decisions`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setLoad({
          state: "failed",
          detail: `the decisions route answered ${response.status}`,
        });
        return;
      }
      const parsed = parseDecisionList(await response.json());
      if (parsed === null) {
        // An unreadable payload is a failed read. Falling through to an empty
        // list here would draw "nothing has been decided" over an unknown record.
        setLoad({ state: "failed", detail: "the route did not return a list of decisions" });
        return;
      }
      setLoad({ state: "ok", rows: parsed.rows, malformed: parsed.malformed });
      setCheckedAt(new Date());
    } catch (error) {
      setLoad({ state: "failed", detail: failureDetail(error) });
    }
  }, []);

  useEffect(() => {
    void read();
    // Same storage wake as SkillProposalGate, so signing in through Talk to
    // DEVON in another tab brings this panel up without a reload.
    const onStorage = () => void read();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [read]);

  const draftFor = useCallback(
    (id: string): Draft => drafts[id] ?? EMPTY_DRAFT,
    [drafts],
  );

  const setDraft = useCallback((id: string, patch: Partial<Draft>) => {
    setDrafts((current) => ({ ...current, [id]: { ...(current[id] ?? EMPTY_DRAFT), ...patch } }));
  }, []);

  /** Put a freshly read row back in place of the one on screen. */
  const replaceRow = useCallback((updated: DecisionRow) => {
    setLoad((current) => {
      if (current.state !== "ok") return current;
      return {
        ...current,
        rows: current.rows.map((row) => (row.id === updated.id ? updated : row)),
      };
    });
  }, []);

  /** PATCH one decision with the human final call. */
  const rule = useCallback(
    async (row: DecisionRow, option: string) => {
      const token = readDevonToken();
      if (!token) {
        setOutcomes((current) => ({
          ...current,
          [row.id]: {
            kind: "failed",
            detail: "the session token is no longer in this browser, so nothing was sent",
          },
        }));
        return;
      }
      const draft = drafts[row.id] ?? EMPTY_DRAFT;
      const ruling = rulingForOption(option, draft.note, draft.status);
      const prepared = prepareRuling(ruling);
      if (!prepared.ok) {
        setOutcomes((current) => ({
          ...current,
          [row.id]: { kind: "failed", detail: prepared.reason },
        }));
        return;
      }
      setOutcomes((current) => ({ ...current, [row.id]: { kind: "sending" } }));
      try {
        const response = await fetch(`${API_BASE}/decisions/${encodeURIComponent(row.id)}`, {
          method: "PATCH",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(prepared.body),
        });
        if (!response.ok) {
          setOutcomes((current) => ({
            ...current,
            [row.id]: {
              kind: "failed",
              detail: `the decision route answered ${response.status}`,
            },
          }));
          return;
        }
        const updated = parseDecisionRow(await response.json());
        if (updated === null) {
          setOutcomes((current) => ({
            ...current,
            [row.id]: {
              kind: "failed",
              detail:
                "the route accepted the ruling and answered with a body this panel could not read, so what is on the record is unconfirmed",
            },
          }));
          return;
        }
        replaceRow(updated);
        setOutcomes((current) => ({
          ...current,
          [row.id]: {
            kind: "done",
            sentence: describeWriteOutcome({
              kind: "recorded",
              decisionId: updated.id,
              ruling,
            }),
          },
        }));
        setDrafts((current) => ({ ...current, [row.id]: EMPTY_DRAFT }));
      } catch (error) {
        setOutcomes((current) => ({
          ...current,
          [row.id]: { kind: "failed", detail: failureDetail(error) },
        }));
      }
    },
    [drafts, replaceRow],
  );

  /** GET one decision, so the row on screen is the row on the record. */
  const reread = useCallback(async (row: DecisionRow) => {
    const token = readDevonToken();
    if (!token) {
      setOutcomes((current) => ({
        ...current,
        [row.id]: {
          kind: "failed",
          detail: "the session token is no longer in this browser, so nothing was read",
        },
      }));
      return;
    }
    setOutcomes((current) => ({ ...current, [row.id]: { kind: "sending" } }));
    try {
      const response = await fetch(`${API_BASE}/decisions/${encodeURIComponent(row.id)}`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setOutcomes((current) => ({
          ...current,
          [row.id]: {
            kind: "failed",
            detail:
              response.status === 404
                ? "this decision is no longer on the record, so the row above is stale"
                : `re-reading it answered ${response.status}`,
          },
        }));
        return;
      }
      const fresh = parseDecisionRow(await response.json());
      if (fresh === null) {
        setOutcomes((current) => ({
          ...current,
          [row.id]: { kind: "failed", detail: "the route answered with a row this panel could not read" },
        }));
        return;
      }
      replaceRow(fresh);
      setOutcomes((current) => ({
        ...current,
        [row.id]: { kind: "done", sentence: "Re-read from the record just now." },
      }));
    } catch (error) {
      setOutcomes((current) => ({
        ...current,
        [row.id]: { kind: "failed", detail: failureDetail(error) },
      }));
    }
  }, [replaceRow]);

  /* --- the Council exchange picker ------------------------------- */

  const loadConversations = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setConversations({ state: "locked" });
      return;
    }
    setConversations({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/conversations`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setConversations({
          state: "failed",
          detail: `the conversations route answered ${response.status}`,
        });
        return;
      }
      const payload: unknown = await response.json();
      if (!Array.isArray(payload)) {
        setConversations({
          state: "failed",
          detail: "the route did not return a list of conversations",
        });
        return;
      }
      const rows: ConversationRow[] = [];
      for (const entry of payload) {
        if (typeof entry !== "object" || entry === null) continue;
        const record = entry as Record<string, unknown>;
        if (typeof record.id !== "string") continue;
        rows.push({
          id: record.id,
          title: typeof record.title === "string" ? record.title : null,
          updatedAt: typeof record.updated_at === "string" ? record.updated_at : null,
        });
      }
      setConversations({ state: "ok", rows });
    } catch (error) {
      setConversations({ state: "failed", detail: failureDetail(error) });
    }
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    if (!conversationId) {
      setMessages({ state: "idle" });
      return;
    }
    const token = readDevonToken();
    if (!token) {
      setMessages({
        state: "failed",
        detail: "the session token is no longer in this browser, so nothing was read",
      });
      return;
    }
    setMessages({ state: "loading" });
    try {
      const response = await fetch(
        `${API_BASE}/conversations/${encodeURIComponent(conversationId)}`,
        { cache: "no-store", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) {
        setMessages({
          state: "failed",
          detail: `the conversation route answered ${response.status}`,
        });
        return;
      }
      const payload: unknown = await response.json();
      const raw =
        typeof payload === "object" && payload !== null
          ? (payload as Record<string, unknown>).messages
          : undefined;
      if (!Array.isArray(raw)) {
        setMessages({ state: "failed", detail: "the route did not return a message list" });
        return;
      }
      const rows: MessageRow[] = [];
      for (const entry of raw) {
        if (typeof entry !== "object" || entry === null) continue;
        const record = entry as Record<string, unknown>;
        if (record.role !== "assistant") continue;
        if (typeof record.id !== "string") continue;
        rows.push({
          id: record.id,
          content: typeof record.content === "string" ? record.content : "",
          createdAt: typeof record.created_at === "string" ? record.created_at : null,
        });
      }
      setMessages({ state: "ok", rows: rows.reverse(), total: raw.length });
    } catch (error) {
      setMessages({ state: "failed", detail: failureDetail(error) });
    }
  }, []);

  const recordFromMessage = useCallback(
    async (messageId: string) => {
      const token = readDevonToken();
      if (!token) {
        setFromMessage((current) => ({
          ...current,
          [messageId]: {
            kind: "failed",
            detail: "the session token is no longer in this browser, so nothing was sent",
          },
        }));
        return;
      }
      setFromMessage((current) => ({ ...current, [messageId]: { kind: "sending" } }));
      try {
        const response = await fetch(`${API_BASE}/decisions/from-message`, {
          method: "POST",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message_id: messageId }),
        });
        if (!response.ok) {
          setFromMessage((current) => ({
            ...current,
            [messageId]: {
              kind: "failed",
              detail: `the from-message route answered ${response.status}`,
            },
          }));
          return;
        }
        const created = parseDecisionRow(await response.json());
        setFromMessage((current) => ({
          ...current,
          [messageId]: {
            kind: "done",
            sentence: created
              ? `On the record as decision ${created.id}, status ${created.status ?? "the route did not say"}. No final call is recorded yet: rule on it above.`
              : "The route accepted it and answered with a body this panel could not read, so the new decision id is unconfirmed. Refresh the record above.",
          },
        }));
        await read();
      } catch (error) {
        setFromMessage((current) => ({
          ...current,
          [messageId]: { kind: "failed", detail: failureDetail(error) },
        }));
      }
    },
    [read],
  );

  /* --- render ----------------------------------------------------- */

  const observed = useMemo(() => asRead(load), [load]);

  const verdict = readDecisionsVerdict(asRead(load));
  const toneClass =
    verdict.tone === "good"
      ? "border-emerald-400/30 text-emerald-200"
      : verdict.tone === "warn"
        ? "border-amber-400/35 text-amber-200"
        : "border-white/15 text-white/70";

  const rows = load.state === "ok" ? load.rows : [];
  const shown = rows.slice(0, 8);

  return (
    <div className="space-y-4">
      {load.state === "loading" ? (
        <p className="text-xs text-white/60">Reading the decision record.</p>
      ) : (
        <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${toneClass}`}>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
            {verdict.label}
          </p>
          <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
        </div>
      )}

      {load.state === "failed" ? (
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
        >
          Try again
        </button>
      ) : null}

      {shown.length > 0 ? (
        <ul className="space-y-3">
          {shown.map((row) => {
            const outcome = outcomes[row.id];
            const busy = outcome?.kind === "sending";
            const draft = draftFor(row.id);
            const open = row.status === "open";
            return (
              <li
                key={row.id}
                className="min-w-0 rounded-xl border border-white/10 bg-black/25 px-3 py-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="min-w-0 text-sm font-semibold leading-snug tracking-tight text-white">
                    {row.question ?? "The route sent no question for this decision."}
                  </p>
                  <span className="shrink-0 rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
                    {row.status ?? "status not sent"}
                  </span>
                </div>

                <dl className="mt-2 grid gap-1 text-[11px] text-white/55 sm:grid-cols-2">
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Decision</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">{row.id}</dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Origin</dt>
                    <dd className="min-w-0 text-white/70">
                      {row.origin ?? "the route did not say"}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Recorded</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(row.createdAt)}</dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Last change</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(row.updatedAt)}</dd>
                  </div>
                </dl>

                <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                  The final call
                </p>
                {row.chosenOption ? (
                  <p className="mt-1 text-xs leading-relaxed text-white/80">{row.chosenOption}</p>
                ) : (
                  <p className="mt-1 text-xs leading-relaxed text-white/60">
                    No call is on the record for this decision yet.
                  </p>
                )}
                {row.outcomeNotes ? (
                  <p className="mt-1 text-xs leading-relaxed text-white/70">
                    Note: {row.outcomeNotes}
                  </p>
                ) : null}
                {row.outcome ? (
                  <p className="mt-1 text-xs leading-relaxed text-white/70">
                    Outcome: {row.outcome}
                  </p>
                ) : null}

                <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                  What the Council put forward
                </p>
                {row.recommendation ? (
                  <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-[11px] leading-relaxed text-white/75">
                    {row.recommendation}
                  </pre>
                ) : (
                  <p className="mt-1 text-xs leading-relaxed text-white/60">
                    The record carries no recommendation for this decision.
                  </p>
                )}

                {row.agentsConsulted && row.agentsConsulted.length > 0 ? (
                  <p className="mt-1.5 text-[11px] leading-relaxed text-white/55">
                    Seats consulted: {row.agentsConsulted.join(", ")}.
                  </p>
                ) : null}

                {open ? (
                  <div className="mt-3 space-y-2 rounded-lg border border-white/10 bg-black/20 px-2.5 py-2.5">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                      Record your call
                    </p>

                    <label className="sr-only" htmlFor={`note-${row.id}`}>
                      Note to record with this call
                    </label>
                    <textarea
                      id={`note-${row.id}`}
                      value={draft.note}
                      onChange={(event) => setDraft(row.id, { note: event.target.value })}
                      rows={2}
                      placeholder="Why this call, in your own words. Optional."
                      className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
                    />

                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <label
                        className="text-[11px] text-white/60"
                        htmlFor={`status-${row.id}`}
                      >
                        Record this as
                      </label>
                      <select
                        id={`status-${row.id}`}
                        value={draft.status}
                        onChange={(event) =>
                          setDraft(row.id, {
                            status: event.target.value === "open" ? "open" : "decided",
                          })
                        }
                        className="rounded-lg border border-white/15 bg-black/40 px-2.5 py-1.5 text-[11px] text-white/80 outline-none focus:border-white/30"
                      >
                        <option value="decided">a final call, closing the decision</option>
                        <option value="open">a note, leaving the decision open</option>
                      </select>
                    </div>

                    {row.options && row.options.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {row.options.map((option) => (
                          <button
                            key={option}
                            type="button"
                            disabled={busy}
                            onClick={() => void rule(row, option)}
                            className="max-w-full rounded-lg border border-white/15 px-3 py-1.5 text-left text-[11px] font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] leading-relaxed text-white/60">
                        This decision carries no option list, so there is nothing to pick from.
                        Write the call below instead.
                      </p>
                    )}

                    <label className="sr-only" htmlFor={`call-${row.id}`}>
                      Your call in your own words
                    </label>
                    <textarea
                      id={`call-${row.id}`}
                      value={draft.call}
                      onChange={(event) => setDraft(row.id, { call: event.target.value })}
                      rows={2}
                      placeholder="A call in your own words, instead of one of the options above."
                      className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
                    />
                    <button
                      type="button"
                      disabled={busy || draft.call.trim().length === 0}
                      onClick={() => void rule(row, draft.call.trim())}
                      className="rounded-lg border border-white/15 px-3 py-1.5 text-[11px] font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/5 disabled:text-white/50"
                    >
                      Record the call written above
                    </button>

                    <p className="text-[11px] leading-relaxed text-white/55">
                      This writes to the decision record only. Nothing here runs a tool, and no
                      effect follows from a call being recorded.
                    </p>
                  </div>
                ) : null}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void reread(row)}
                    className="rounded-lg border border-white/15 px-3 py-1.5 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                  >
                    Re-read from the record
                  </button>
                  {outcome?.kind === "sending" ? (
                    <span className="text-[11px] text-white/60">Talking to the record.</span>
                  ) : null}
                </div>

                {outcome?.kind === "failed" ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-red-300">
                    Nothing changed on the record: {outcome.detail}.
                  </p>
                ) : null}
                {outcome?.kind === "done" ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-white/75">
                    {outcome.sentence}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {load.state === "ok" && rows.length > shown.length ? (
        <p className="text-[11px] text-white/60">
          Showing the {shown.length} most recently changed of {rows.length}.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Refresh
        </button>
        <p className="text-[11px] text-white/55">
          {checkedAt ? `Record read ${checkedAt.toLocaleTimeString()}.` : ""}
        </p>
      </div>

      <ExchangePicker
        conversations={conversations}
        selected={selected}
        messages={messages}
        fromMessage={fromMessage}
        decisionsRead={observed}
        onLoad={() => void loadConversations()}
        onSelect={(id) => {
          setSelected(id);
          void loadMessages(id);
        }}
        onRecord={(id) => void recordFromMessage(id)}
      />
    </div>
  );
}

/**
 * Put a Council exchange on the record.
 *
 * Split out so the panel above stays about the record itself, and kept in the
 * same file because it is one door and has no other caller.
 */
function ExchangePicker({
  conversations,
  selected,
  messages,
  fromMessage,
  decisionsRead,
  onLoad,
  onSelect,
  onRecord,
}: {
  conversations: ConversationsLoad;
  selected: string;
  messages: MessagesLoad;
  fromMessage: Record<string, RowOutcome>;
  decisionsRead: DecisionsRead;
  onLoad: () => void;
  onSelect: (id: string) => void;
  onRecord: (id: string) => void;
}) {
  return (
    <section className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
        Put a Council exchange on the record
      </p>
      <p className="mt-1.5 text-[11px] leading-relaxed text-white/60">
        POST /decisions/from-message takes the synthesis of one assistant turn as the
        recommendation and its recommended actions as the options, and leaves the final call
        open for you. Reading your conversations is a separate request, so it is made only when
        you ask for it.
      </p>

      {conversations.state === "idle" ? (
        <button
          type="button"
          onClick={onLoad}
          className="mt-2.5 rounded-lg border border-white/15 px-3 py-1.5 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
        >
          Read my conversations
        </button>
      ) : null}

      {conversations.state === "loading" ? (
        <p className="mt-2.5 text-[11px] text-white/60">Reading your conversations.</p>
      ) : null}

      {conversations.state === "locked" ? (
        <p className="mt-2.5 text-[11px] leading-relaxed text-white/60">
          No session token in this browser, so no request was sent. Conversations are scoped to
          one account.
        </p>
      ) : null}

      {conversations.state === "failed" ? (
        <div className="mt-2.5 space-y-1.5">
          <p className="text-[11px] leading-relaxed text-red-300">
            Your conversations could not be read: {conversations.detail}.
          </p>
          <p className="text-[11px] leading-relaxed text-white/60">
            This is a failed read, not an account with no conversations. There may be exchanges
            waiting to go on the record and this panel cannot see them.
          </p>
          <button
            type="button"
            onClick={onLoad}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
          >
            Try again
          </button>
        </div>
      ) : null}

      {conversations.state === "ok" && conversations.rows.length === 0 ? (
        <p className="mt-2.5 text-[11px] leading-relaxed text-white/70">
          The route answered and returned no conversations on this account, so there is no
          Council exchange to record.
        </p>
      ) : null}

      {conversations.state === "ok" && conversations.rows.length > 0 ? (
        <div className="mt-2.5 flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="text-[11px] text-white/60" htmlFor="exchange-conversation">
            Conversation
          </label>
          <select
            id="exchange-conversation"
            value={selected}
            onChange={(event) => onSelect(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-white/15 bg-black/40 px-2.5 py-1.5 text-[11px] text-white/80 outline-none focus:border-white/30"
          >
            <option value="">Pick one of {conversations.rows.length}</option>
            {conversations.rows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.title ?? "untitled"}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {messages.state === "loading" ? (
        <p className="mt-2.5 text-[11px] text-white/60">Reading that conversation.</p>
      ) : null}

      {messages.state === "failed" ? (
        <p className="mt-2.5 text-[11px] leading-relaxed text-red-300">
          That conversation could not be read: {messages.detail}. This is a failed read, not a
          conversation with no assistant turns in it.
        </p>
      ) : null}

      {messages.state === "ok" && messages.rows.length === 0 ? (
        <p className="mt-2.5 text-[11px] leading-relaxed text-white/70">
          That conversation was read and holds {messages.total}{" "}
          {messages.total === 1 ? "message" : "messages"}, none of them an assistant turn. Only
          an assistant turn can go on the record, so there is nothing here to record.
        </p>
      ) : null}

      {messages.state === "ok" && messages.rows.length > 0 ? (
        <ul className="mt-2.5 space-y-2">
          {messages.rows.slice(0, 6).map((message) => {
            const tracked = trackedState(message.id, decisionsRead);
            const outcome = fromMessage[message.id];
            return (
              <li
                key={message.id}
                className="min-w-0 rounded-lg border border-white/10 bg-black/30 px-2.5 py-2"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-[11px] text-white/60">
                    {message.createdAt ? whenLabel(message.createdAt) : "time not sent"}
                  </p>
                  <TrackedBadge state={tracked} />
                </div>
                <p className="mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-[11px] leading-relaxed text-white/75">
                  {message.content || "This turn carries no text."}
                </p>
                <button
                  type="button"
                  disabled={outcome?.kind === "sending"}
                  onClick={() => onRecord(message.id)}
                  className="mt-2 rounded-lg border border-white/15 px-3 py-1.5 text-[11px] font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                >
                  Record this exchange
                </button>
                {outcome?.kind === "sending" ? (
                  <p className="mt-1.5 text-[11px] text-white/60">Sending it to the record.</p>
                ) : null}
                {outcome?.kind === "failed" ? (
                  <p className="mt-1.5 text-[11px] leading-relaxed text-red-300">
                    Nothing was recorded: {outcome.detail}.
                  </p>
                ) : null}
                {outcome?.kind === "done" ? (
                  <p className="mt-1.5 text-[11px] leading-relaxed text-white/75">
                    {outcome.sentence}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {messages.state === "ok" && messages.rows.length > 6 ? (
        <p className="mt-2 text-[11px] text-white/60">
          Showing the 6 most recent assistant turns of {messages.rows.length}.
        </p>
      ) : null}
    </section>
  );
}

/**
 * Whether this exchange is already on the record. "unknown" is a real answer
 * and is drawn as one: saying "not recorded" over a record nobody could read is
 * how a person ends up recording the same exchange twice.
 */
function TrackedBadge({ state }: { state: TrackedState }) {
  const text =
    state === "tracked"
      ? "already on the record"
      : state === "untracked"
        ? "not on the record"
        : "record unread, so unknown";
  const tone =
    state === "tracked"
      ? "border-emerald-400/30 text-emerald-200"
      : state === "untracked"
        ? "border-white/15 text-white/60"
        : "border-amber-400/35 text-amber-200";
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium tracking-[0.06em] ${tone}`}
    >
      {text}
    </span>
  );
}
