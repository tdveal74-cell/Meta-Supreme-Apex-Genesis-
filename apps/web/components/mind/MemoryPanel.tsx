"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  armDelete,
  confirmDelete,
  DELETE_DISARMED,
  deleteIsArmedFor,
  describeDeletion,
  describeFilter,
  describeRecall,
  disarmDelete,
  filterMemories,
  importanceLabel,
  originLabel,
  parseMemoryPayload,
  readMemoryVerdict,
  statedOr,
  summarizeMemories,
  type DeleteGate,
  type MemoryRead,
  type MemoryTally,
  type ParsedMemories,
  type ParsedMemory,
} from "@/components/mind/memory-honesty";

/**
 * Long term memory: read it, write one, edit one, delete one.
 *
 * WHAT WAS BROKEN. app/api/v1/memory.py carries four finished routes over the
 * `memories` table, registered at app/api/v1/router.py:48 and covered by
 * test_memory_api.py. Measured on 32883cf, `grep -rn "/memory" apps/web` had
 * exactly one hit and it was a comment in app/page.tsx recording that nothing
 * here calls the route. So the estate could store, edit, pause and hard delete
 * a memory, and no person could do any of it. Meanwhile the Council writes
 * memories about the owner on its own: app/services/intelligence.py:333 calls
 * persist_memory_candidates after every exchange, which stamps
 * metadata.origin = "council_interaction" and stores up to five rows plus a
 * fallback. Rows were accumulating where their subject could not read them.
 *
 * The landing page said so out loud until 2026-09-10. It advertised "long-term
 * memory you can edit or delete" and the sentence was deleted rather than made
 * true. This panel makes it true; see NOTES.md for the honesty-check.ts entries
 * that then have to move.
 *
 * WHY DELETION IS TWO TAPS. `delete_memory` is `await db.delete(memory)`: a hard
 * delete, no archive, no tombstone, no undo, and the route's own docstring says
 * "Hard deletes only." A single tap on a destructive irreversible action against
 * a row the owner may not have written is not a ruling, it is an accident
 * waiting. So the gate is a state machine in memory-honesty.ts and not a
 * boolean here: arming shows exactly what would be lost, and confirmDelete is
 * the only thing that may say a request leaves, for the one id that was armed.
 *
 * WHY PAUSE SITS BESIDE DELETE. is_active false is the reversible version of the
 * same intent: app/services/memory.py:87 filters recall on is_active, so a
 * paused row is stored, visible, editable and unreachable. Offering only delete
 * would push a reversible want down an irreversible path.
 *
 * WHAT THIS PANEL WILL NOT DO. It writes nothing on load, seeds nothing, and
 * deletes nothing on a single tap. Every request here is one the person pressed
 * a button for, against their own token, on their own rows. No WRITE or
 * HIGH_IMPACT tool is reachable from here and nothing here runs an effect, so
 * the human gate on effects is untouched by it.
 *
 * WHAT IT WILL NOT CLAIM. A failed read is drawn as unreadable and lists
 * nothing; an empty store is drawn as empty; a filter that matched nothing is
 * drawn as a filter, naming the stored total. No field the route did not send is
 * defaulted: importance and the active flag stay visibly absent. All of that is
 * decided in memory-honesty.ts and proved in scripts/memory-check.ts.
 */

const MEMORY_TYPES = [
  "preference",
  "context",
  "decision",
  "lesson",
  "pattern",
  "other",
] as const;

const IMPORTANCES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

type Read =
  | { state: "pending" }
  | { state: "locked" }
  | { state: "ok"; parsed: ParsedMemories }
  | { state: "failed"; detail: string };

type Outcome =
  | { kind: "sending" }
  | { kind: "failed"; detail: string }
  | { kind: "done"; sentence: string };

/** The create form. Every field here is a value the person can see before it is sent. */
type Draft = {
  content: string;
  memoryType: string;
  importance: number;
};

/**
 * The edit form, where null means "leave as stored".
 *
 * memoryType and importance start null on purpose. Seeding them from the row and
 * sending them back looks harmless and is not: a row whose importance the route
 * never sent would be saved at whatever the control happened to show, which is
 * this panel writing a number nobody chose into the database. So an edit sends
 * only the keys the person actually set.
 */
type EditDraft = {
  content: string;
  memoryType: string | null;
  importance: number | null;
};

/**
 * The wire from a fetch result into the verdict ladder.
 *
 * Kept as a named top level function, not inlined, for the reason the learning
 * panel learned on 2026-09-10: control-check and learning-check both bind the
 * ladder to the adapter, because a correct ladder wired up wrong renders the lie
 * anyway. Every branch here maps to the state of the same name. There is no
 * branch that turns a failure into a count.
 */
export function asRead(read: Read): MemoryRead {
  if (read.state === "failed") return { state: "failed", detail: read.detail };
  if (read.state === "locked") return { state: "locked" };
  if (read.state === "pending") return { state: "pending" };
  const tally = summarizeMemories(read.parsed);
  // A payload that was not a list has no tally, and a read with no tally is a
  // failed read. It must not fall through to a count.
  if (tally === null) {
    return {
      state: "failed",
      detail: `the route answered 200 with ${
        read.parsed.shape === "not-a-list" ? read.parsed.sawType : "an unreadable body"
      } where a list of memories was expected`,
    };
  }
  return { state: "ok", tally };
}

function whenLabel(iso: string | null): string {
  if (iso === null) return "not sent by the route";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString();
}

export function MemoryPanel() {
  const [read, setRead] = useState<Read>({ state: "pending" });
  const [gate, setGate] = useState<DeleteGate>(DELETE_DISARMED);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditDraft>({
    content: "",
    memoryType: null,
    importance: null,
  });
  const [draft, setDraft] = useState<Draft>({
    content: "",
    memoryType: "preference",
    importance: 5,
  });
  const [writing, setWriting] = useState<Outcome | null>(null);
  const [filter, setFilter] = useState("");
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    const token = readDevonToken();
    // Disarm on every reload. Fail closed: an armed row whose list just changed
    // underneath it is not a row anybody ruled on.
    setGate(disarmDelete());
    if (!token) {
      setRead({ state: "locked" });
      return;
    }
    setRead({ state: "pending" });
    try {
      const response = await fetch(`${API_BASE}/memory?include_inactive=true`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setRead({
          state: "failed",
          detail: `the memory route answered ${response.status}`,
        });
        return;
      }
      const parsed = parseMemoryPayload(await response.json());
      setRead({ state: "ok", parsed });
      // Stamped only when the body actually WAS a list. It used to be stamped
      // here unconditionally, so a 200 carrying {"detail":"Not authenticated"}
      // rendered "MEMORY UNREADABLE ... it says nothing about what is stored"
      // in the header and a fresh "Store read <now>." in the footer at the same
      // time. A read that yielded no store may not stamp a successful read.
      if (parsed.shape === "list") setCheckedAt(new Date());
    } catch (error) {
      setRead({
        state: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void load();
    // Same storage wake as SkillProposalGate: signing in through Talk to DEVON
    // in another tab brings this panel up without a reload. No timer, because a
    // poll that lands mid ruling would move the row a person is deciding about.
    const onStorage = () => void load();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [load]);

  const rows: ParsedMemory[] = read.state === "ok" && read.parsed.shape === "list"
    ? read.parsed.rows
    : [];
  const asMemoryRead = asRead(read);
  const verdict = readMemoryVerdict(asMemoryRead);
  const tally: MemoryTally | null = asMemoryRead.state === "ok" ? asMemoryRead.tally : null;
  const outcome = useMemo(() => filterMemories(rows, filter), [rows, filter]);
  const filterSentence = tally === null ? null : describeFilter(outcome, tally);

  function note(id: string, value: Outcome) {
    setOutcomes((current) => ({ ...current, [id]: value }));
  }

  async function patch(row: ParsedMemory, body: Record<string, unknown>, sentence: string) {
    const token = readDevonToken();
    if (!token) {
      note(row.id, {
        kind: "failed",
        detail: "the session token is no longer in this browser, so nothing was sent",
      });
      return;
    }
    note(row.id, { kind: "sending" });
    try {
      const response = await fetch(`${API_BASE}/memory/${encodeURIComponent(row.id)}`, {
        method: "PATCH",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        note(row.id, {
          kind: "failed",
          detail:
            response.status === 404
              ? "this memory is no longer on the route, so nothing changed"
              : `the memory route answered ${response.status}`,
        });
        return;
      }
      note(row.id, { kind: "done", sentence });
      setEditingId(null);
      await load();
    } catch (error) {
      note(row.id, {
        kind: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  /**
   * The destructive path. It asks memory-honesty.ts for permission and obeys a
   * refusal: an id that was not armed sends nothing and says why.
   */
  async function destroy(row: ParsedMemory) {
    const ruling = confirmDelete(gate, row.id);
    if (!ruling.proceed) {
      note(row.id, {
        kind: "failed",
        detail: `no delete was sent: ${ruling.reason}`,
      });
      return;
    }
    const token = readDevonToken();
    if (!token) {
      note(row.id, {
        kind: "failed",
        detail: "the session token is no longer in this browser, so nothing was sent",
      });
      return;
    }
    note(row.id, { kind: "sending" });
    try {
      const response = await fetch(`${API_BASE}/memory/${encodeURIComponent(row.id)}`, {
        method: "DELETE",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        note(row.id, {
          kind: "failed",
          detail:
            response.status === 404
              ? "this memory was already gone, so nothing was deleted twice"
              : `the delete answered ${response.status}`,
        });
        return;
      }
      setGate(disarmDelete());
      note(row.id, {
        kind: "done",
        sentence: "Deleted. The row is gone from the database and cannot be recovered here.",
      });
      await load();
    } catch (error) {
      note(row.id, {
        kind: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  async function write(event: React.FormEvent) {
    event.preventDefault();
    const content = draft.content.trim();
    if (!content) return;
    const token = readDevonToken();
    if (!token) {
      setWriting({
        kind: "failed",
        detail: "no session token in this browser, so nothing was sent",
      });
      return;
    }
    setWriting({ kind: "sending" });
    try {
      const response = await fetch(`${API_BASE}/memory`, {
        method: "POST",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        // Every field is sent explicitly. importance has a server side default of
        // 5, and a default the person did not choose is a number this panel put
        // in the database on their behalf.
        body: JSON.stringify({
          content,
          memory_type: draft.memoryType,
          importance: draft.importance,
        }),
      });
      if (!response.ok) {
        setWriting({
          kind: "failed",
          detail: `the memory route answered ${response.status}`,
        });
        return;
      }
      const saved = parseMemoryPayload([await response.json()]);
      const id = saved.shape === "list" && saved.rows[0] ? saved.rows[0].id : null;
      setWriting({
        kind: "done",
        sentence:
          id === null
            ? "Stored. The route answered without an identifier, so this panel cannot name the row it created."
            : `Stored as ${id}. It reaches a Council answer only when a message shares a word with it.`,
      });
      setDraft({ content: "", memoryType: draft.memoryType, importance: draft.importance });
      await load();
    } catch (error) {
      setWriting({
        kind: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  const toneClass =
    verdict.tone === "good"
      ? "border-emerald-400/30 text-emerald-200"
      : verdict.tone === "warn"
        ? "border-amber-400/35 text-amber-200"
        : "border-white/15 text-white/70";

  return (
    <div className="space-y-4">
      <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${toneClass}`}>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
          {verdict.label}
        </p>
        <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
      </div>

      {verdict.code === "unreadable" ? (
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      ) : null}

      {tally !== null && tally.malformed > 0 ? (
        <p className="text-[11px] leading-relaxed text-amber-200">
          {tally.malformed} {tally.malformed === 1 ? "row" : "rows"} came back with no usable
          identifier and {tally.malformed === 1 ? "is" : "are"} not listed. A row with no id
          cannot be edited or deleted, and inventing one would name a memory that does not
          exist.
        </p>
      ) : null}

      {/* The list is rendered ONLY when the rows in hand are the store. Every
          other verdict lists nothing rather than a short list that reads as a
          complete one. */}
      {verdict.rowsAreTheStore && tally !== null ? (
        <>
          {tally.total > 0 ? (
            <div className="flex flex-col gap-1.5">
              <label
                className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
                htmlFor="memory-filter"
              >
                Filter the rows shown
              </label>
              <input
                id="memory-filter"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="a word in the memory text"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
              />
              {filterSentence ? (
                <p className="text-[11px] leading-relaxed text-white/70">{filterSentence}</p>
              ) : null}
            </div>
          ) : null}

          <ul className="space-y-2.5">
            {outcome.shown.map((row) => {
              const rowOutcome = outcomes[row.id];
              const sending = rowOutcome?.kind === "sending";
              const armed = deleteIsArmedFor(gate, row.id);
              const notice = describeDeletion(row);
              const editingThis = editingId === row.id;
              return (
                <li
                  key={row.id}
                  className="min-w-0 rounded-xl border border-white/10 bg-black/25 px-3 py-3"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
                      {statedOr(row.memoryType, "type not sent")}
                    </span>
                    <span className="text-[11px] tabular-nums text-white/60">
                      {importanceLabel(row.importance)}
                      {row.isActive === false ? ", paused" : null}
                      {row.isActive === null ? ", active flag not sent" : null}
                    </span>
                  </div>

                  {row.content === null ? (
                    <p className="mt-2 text-xs leading-relaxed text-amber-200">
                      The route sent this row with no content, so there is nothing to show and
                      nothing here fills it in.
                    </p>
                  ) : (
                    <p
                      className={`mt-2 text-xs leading-relaxed ${
                        row.isActive === false ? "text-white/60" : "text-white/85"
                      }`}
                    >
                      {row.content}
                    </p>
                  )}

                  <p className="mt-2 text-[11px] leading-relaxed text-white/60">
                    {describeRecall(row)}
                  </p>

                  <dl className="mt-2 grid gap-1 text-[11px] text-white/50 sm:grid-cols-2">
                    <div className="flex min-w-0 items-baseline gap-1.5">
                      <dt className="shrink-0">Identifier</dt>
                      <dd className="min-w-0 break-all font-mono text-white/70">{row.id}</dd>
                    </div>
                    <div className="flex min-w-0 items-baseline gap-1.5">
                      <dt className="shrink-0">Origin</dt>
                      <dd className="min-w-0 text-white/70">{originLabel(row.origin)}</dd>
                    </div>
                    <div className="flex min-w-0 items-baseline gap-1.5">
                      <dt className="shrink-0">Stored</dt>
                      <dd className="min-w-0 text-white/70">{whenLabel(row.createdAt)}</dd>
                    </div>
                    <div className="flex min-w-0 items-baseline gap-1.5">
                      <dt className="shrink-0">Last edited</dt>
                      <dd className="min-w-0 text-white/70">{whenLabel(row.updatedAt)}</dd>
                    </div>
                  </dl>

                  {editingThis ? (
                    <form
                      className="mt-3 space-y-2 rounded-lg border border-white/10 bg-black/30 px-2.5 py-2.5"
                      onSubmit={(event) => {
                        event.preventDefault();
                        // Only the keys the person set. See EditDraft above: a
                        // seeded control sending itself back is how a panel
                        // writes a value nobody chose.
                        const body: Record<string, unknown> = {};
                        const next = edit.content.trim();
                        if (next) body.content = next;
                        if (edit.memoryType !== null) body.memory_type = edit.memoryType;
                        if (edit.importance !== null) body.importance = edit.importance;
                        if (Object.keys(body).length === 0) {
                          note(row.id, {
                            kind: "failed",
                            detail:
                              "nothing was changed in the form, so no edit was sent rather than an empty write being made",
                          });
                          return;
                        }
                        void patch(row, body, "Edited. The stored row is what you see now.");
                      }}
                    >
                      <label
                        className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
                        htmlFor={`memory-edit-content-${row.id}`}
                      >
                        Memory text
                      </label>
                      <textarea
                        id={`memory-edit-content-${row.id}`}
                        value={edit.content}
                        onChange={(event) =>
                          setEdit((current) => ({ ...current, content: event.target.value }))
                        }
                        rows={3}
                        className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
                      />
                      <p className="text-[11px] leading-relaxed text-white/60">
                        Leaving this empty sends no content key, so the stored text is left
                        exactly as it is. The route rejects an empty string rather than
                        blanking a memory.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <div className="flex flex-col gap-1">
                          <label
                            className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
                            htmlFor={`memory-edit-type-${row.id}`}
                          >
                            Type
                          </label>
                          <select
                            id={`memory-edit-type-${row.id}`}
                            value={edit.memoryType ?? ""}
                            onChange={(event) =>
                              setEdit((current) => ({
                                ...current,
                                memoryType: event.target.value === "" ? null : event.target.value,
                              }))
                            }
                            className="rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-white/85 outline-none focus:border-white/25"
                          >
                            <option value="" className="bg-[#04070d]">
                              leave as stored
                            </option>
                            {MEMORY_TYPES.map((type) => (
                              <option key={type} value={type} className="bg-[#04070d]">
                                {type}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="flex flex-col gap-1">
                          <label
                            className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
                            htmlFor={`memory-edit-importance-${row.id}`}
                          >
                            Importance
                          </label>
                          <select
                            id={`memory-edit-importance-${row.id}`}
                            value={edit.importance === null ? "" : String(edit.importance)}
                            onChange={(event) =>
                              setEdit((current) => ({
                                ...current,
                                importance:
                                  event.target.value === "" ? null : Number(event.target.value),
                              }))
                            }
                            className="rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs tabular-nums text-white/85 outline-none focus:border-white/25"
                          >
                            <option value="" className="bg-[#04070d]">
                              leave as stored
                            </option>
                            {IMPORTANCES.map((value) => (
                              <option key={value} value={value} className="bg-[#04070d]">
                                {value}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="submit"
                          disabled={sending}
                          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                        >
                          Save edit
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  ) : null}

                  {/* THE TWO STEP. Nothing destructive is one tap: this button
                      arms, and the block it reveals is the only place a delete
                      can be sent from. */}
                  {armed ? (
                    <div className="mt-3 rounded-lg border border-red-400/40 bg-red-500/10 px-2.5 py-2.5">
                      <p className="text-xs font-semibold text-red-200">{notice.headline}</p>
                      <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-red-200/90">
                        What will be lost
                      </p>
                      <p className="mt-1 whitespace-pre-wrap break-words rounded border border-red-400/25 bg-black/40 px-2 py-1.5 text-xs leading-relaxed text-white/85">
                        {notice.losing}
                      </p>
                      <ul className="mt-2 space-y-0.5 text-[11px] text-white/70">
                        {notice.facts.map((fact) => (
                          <li key={fact} className="break-all">
                            {fact}
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-[11px] leading-relaxed text-red-200">
                        {notice.irreversible}
                      </p>
                      <p className="mt-1.5 text-[11px] leading-relaxed text-white/70">
                        {notice.alternative}
                      </p>
                      <div className="mt-2.5 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => setGate(disarmDelete())}
                          className="rounded-lg border border-white/20 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:border-white/35 hover:text-white"
                        >
                          Keep it
                        </button>
                        <button
                          type="button"
                          disabled={sending}
                          onClick={() => void destroy(row)}
                          className="rounded-lg border border-red-400/50 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:border-red-300 hover:text-red-100 disabled:opacity-40"
                        >
                          Delete permanently
                        </button>
                        {row.isActive !== false ? (
                          <button
                            type="button"
                            disabled={sending}
                            onClick={() =>
                              void patch(
                                row,
                                { is_active: false },
                                "Paused instead of deleted. The row is stored and out of recall.",
                              )
                            }
                            className="rounded-lg border border-white/20 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:border-white/35 hover:text-white disabled:opacity-40"
                          >
                            Pause instead
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingId(row.id);
                          setEdit({
                            // The text opens with the stored text so an edit is an
                            // edit. When the route sent none, it opens empty rather
                            // than with a placeholder standing in for content. The
                            // other two open at "leave as stored", never seeded.
                            content: row.content ?? "",
                            memoryType: null,
                            importance: null,
                          });
                        }}
                        className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                      >
                        Edit
                      </button>
                      {row.isActive === true ? (
                        <button
                          type="button"
                          disabled={sending}
                          onClick={() =>
                            void patch(
                              row,
                              { is_active: false },
                              "Paused. Stored, visible here, and out of recall.",
                            )
                          }
                          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                        >
                          Pause
                        </button>
                      ) : null}
                      {row.isActive === false ? (
                        <button
                          type="button"
                          disabled={sending}
                          onClick={() =>
                            void patch(
                              row,
                              { is_active: true },
                              "Resumed. Recall can reach it again when a message shares a word with it.",
                            )
                          }
                          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                        >
                          Resume
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => setGate(armDelete(row.id))}
                        className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-red-400/50 hover:text-red-200"
                      >
                        Delete
                      </button>
                    </div>
                  )}

                  {rowOutcome?.kind === "sending" ? (
                    <p className="mt-2 text-[11px] text-white/70">Sending.</p>
                  ) : null}
                  {rowOutcome?.kind === "failed" ? (
                    <p className="mt-2 text-[11px] leading-relaxed text-red-300">
                      {rowOutcome.detail}.
                    </p>
                  ) : null}
                  {rowOutcome?.kind === "done" ? (
                    <p className="mt-2 text-[11px] leading-relaxed text-white/70">
                      {rowOutcome.sentence}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      <form onSubmit={write} className="space-y-2 border-t border-white/10 pt-4">
        <label
          className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
          htmlFor="memory-new-content"
        >
          Write a memory
        </label>
        <textarea
          id="memory-new-content"
          value={draft.content}
          onChange={(event) =>
            setDraft((current) => ({ ...current, content: event.target.value }))
          }
          rows={3}
          placeholder="A preference, a ruling or a fact the Council should carry into later answers"
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
        />
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label
              className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
              htmlFor="memory-new-type"
            >
              Type
            </label>
            <select
              id="memory-new-type"
              value={draft.memoryType}
              onChange={(event) =>
                setDraft((current) => ({ ...current, memoryType: event.target.value }))
              }
              className="rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs text-white/85 outline-none focus:border-white/25"
            >
              {MEMORY_TYPES.map((type) => (
                <option key={type} value={type} className="bg-[#04070d]">
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label
              className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50"
              htmlFor="memory-new-importance"
            >
              Importance, sent as chosen
            </label>
            <select
              id="memory-new-importance"
              value={draft.importance}
              onChange={(event) =>
                setDraft((current) => ({ ...current, importance: Number(event.target.value) }))
              }
              className="rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs tabular-nums text-white/85 outline-none focus:border-white/25"
            >
              {IMPORTANCES.map((value) => (
                <option key={value} value={value} className="bg-[#04070d]">
                  {value}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={writing?.kind === "sending" || !draft.content.trim()}
            className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/5 disabled:text-white/50"
          >
            {writing?.kind === "sending" ? "Writing" : "Write memory"}
          </button>
        </div>
        <p className="text-[11px] leading-relaxed text-white/60">
          Importance is a real multiplier on recall, not a label: the score is the shared word
          count times importance over ten times a decay of about 30 days, and the top 5 reach
          the answer. The value shown above is the value sent.
        </p>
      </form>

      {writing?.kind === "done" ? (
        <p className="text-xs leading-relaxed text-emerald-200">{writing.sentence}</p>
      ) : null}
      {writing?.kind === "failed" ? (
        <p className="text-xs leading-relaxed text-red-300">
          The memory was not stored: {writing.detail}.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-white/10 pt-3">
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Refresh
        </button>
        <p className="text-[11px] text-white/50">
          {checkedAt ? `Store read ${checkedAt.toLocaleTimeString()}.` : "Not read yet."}
        </p>
      </div>

      <p className="text-[11px] leading-relaxed text-white/60">
        These rows are not all yours. The Council writes memories about you after an exchange
        and stamps them as its own, so this panel is where you find out what it decided to keep.
        Nothing here approves a write anywhere else in the estate, and nothing here runs an
        effect: every request is one you pressed a button for, against your own account.
      </p>
    </div>
  );
}
