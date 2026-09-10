"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  parseProjectsPayload,
  readProjectsVerdict,
  type ParsedProjects,
  type ProjectRow,
  type ProjectsRead,
} from "@/components/projects/projects-honesty";

/**
 * The door on projects: the estate's scoping construct.
 *
 * WHAT WAS BROKEN. `app/api/v1/projects.py` carries a complete, tested list,
 * create, get and patch surface, registered at `app/api/v1/router.py:35`, and on
 * commit 32883cf nothing under `apps/web` or `packages/ui` called any of it.
 * Measured, not remembered: `grep -rn "projects" --include=*.ts --include=*.tsx
 * apps/web packages/ui` returned no lines. So a person could not create a
 * project, which meant every `project_id` the rest of the estate accepts could
 * only ever be null: the graph route's filter
 * (app/api/v1/knowledge_graph.py:104), and the project scope on knowledge items
 * and search (app/api/v1/knowledge.py:34, :43, :53). The capability was real,
 * reachable by any token holder, and unreachable by a human. Nothing failed.
 *
 * WHAT THIS PANEL DOES, AND WHAT IT DELIBERATELY DOES NOT.
 *
 * It reads `GET /projects`, creates with `POST /projects`, and renames with
 * `PATCH /projects/{id}`. That is the whole surface a person needs to make the
 * scope usable, and it is where this panel stops.
 *
 * `ProjectUpdate` also accepts `status` with the pattern `^(active|archived)$`
 * (app/api/v1/projects.py:29), so archiving is one field away. This panel does
 * not send it. Archiving is a ruling about whether a scope is still in force,
 * and a button that quietly changes what the graph route will filter on belongs
 * behind a decision surface written for it, not tucked into a rename row. The
 * status the route returns IS shown on every row, so an archived project is
 * visible here rather than hidden; it is just not settable from here.
 *
 * Nothing on this panel runs an effect. Creating and renaming a project writes
 * two text columns and touches no tool, no intent and no adapter, so there is no
 * gate to route it through: CLAUDE.md's "WRITE and HIGH_IMPACT tools require
 * human approval" is about the tool call path, and this is not on it. Every
 * request here is sent by a person pressing a button on that request. There is
 * no auto-create, no seed and no default project, in either direction.
 *
 * THE HONESTY RULES IT HOLDS TO, all four proved in `scripts/projects-check.ts`:
 *
 *  - A failed read is never drawn as an empty list. Those are opposite
 *    instructions here: an empty list says create one, a failed read says fix
 *    the route. The ladder in `projects-honesty.ts` refuses to merge them.
 *  - A 200 carrying rows this panel cannot use is neither of those, and gets its
 *    own rung rather than being rounded to whichever is nearer.
 *  - No session token is its own state, distinct from both. No request was sent,
 *    so no failure is claimed.
 *  - No field is invented. A name, description, status or organization the route
 *    did not send renders as absent, never as a default.
 */

type Load =
  | { state: "loading" }
  | { state: "locked" }
  | { state: "ok"; parsed: ParsedProjects }
  | { state: "failed"; detail: string };

type Outcome =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "done"; sentence: string }
  | { kind: "failed"; detail: string };

/** The row currently open for rename, and the text in its field. */
type Editing = { id: string; value: string } | null;

/**
 * Report the load to the ladder.
 *
 * "loading" reports as locked rather than as a failure or as a count, because
 * mid-flight is not a fact about the list in either direction.
 */
function asRead(load: Load): ProjectsRead {
  if (load.state === "ok") {
    return {
      state: "ok",
      count: load.parsed.rows.length,
      malformed: load.parsed.malformedRows,
      duplicates: load.parsed.duplicateRows,
    };
  }
  if (load.state === "failed") return { state: "failed", detail: load.detail };
  return { state: "locked" };
}

function whenLabel(iso: string | null): string {
  if (iso === null) return "the route did not say";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString();
}

export function ProjectsPanel() {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creation, setCreation] = useState<Outcome>({ kind: "idle" });
  const [editing, setEditing] = useState<Editing>(null);
  const [rename, setRename] = useState<Record<string, Outcome>>({});
  const [readAt, setReadAt] = useState<Date | null>(null);

  const read = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setLoad({ state: "locked" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/projects`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setLoad({ state: "failed", detail: `the projects route answered ${response.status}` });
        return;
      }
      const parsed = parseProjectsPayload(await response.json());
      if (parsed === null) {
        // The route is declared List[ProjectResponse]. A body that is not a
        // list is a failed read, and falling through to an empty list here is
        // the one inversion this panel exists to refuse.
        setLoad({ state: "failed", detail: "the route did not return a list of projects" });
        return;
      }
      setLoad({ state: "ok", parsed });
      setReadAt(new Date());
    } catch (error) {
      setLoad({
        state: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
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

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const token = readDevonToken();
    if (!token) {
      setCreation({ kind: "failed", detail: "no session token in this browser, so nothing was sent" });
      return;
    }
    setCreation({ kind: "sending" });
    try {
      const body: { name: string; description?: string } = { name: trimmed };
      // An empty box is not an empty description, it is no description. Sending
      // "" would write a value the person never typed.
      const note = description.trim();
      if (note) body.description = note;
      const response = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        setCreation({
          kind: "failed",
          detail:
            response.status === 422
              ? "the route rejected the name as invalid (422)"
              : `the projects route answered ${response.status}`,
        });
        return;
      }
      const created = (await response.json()) as { id?: unknown; name?: unknown };
      const id = typeof created.id === "string" ? created.id : "";
      setCreation({
        kind: "done",
        sentence: id
          ? `Created as ${id}. It can now be passed as project_id to the knowledge and graph routes.`
          : "The route accepted the project but returned no id, so nothing can be scoped to it from here yet.",
      });
      setName("");
      setDescription("");
      await read();
    } catch (error) {
      setCreation({
        kind: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  async function saveRename(row: ProjectRow, next: string) {
    const trimmed = next.trim();
    if (!trimmed) return;
    const token = readDevonToken();
    if (!token) {
      setRename((current) => ({
        ...current,
        [row.id]: { kind: "failed", detail: "the session token is no longer in this browser, so nothing was sent" },
      }));
      return;
    }
    setRename((current) => ({ ...current, [row.id]: { kind: "sending" } }));
    try {
      const response = await fetch(`${API_BASE}/projects/${encodeURIComponent(row.id)}`, {
        method: "PATCH",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        // Name only. See the note at the top of this file on why status is not
        // sent from here even though the route accepts it.
        body: JSON.stringify({ name: trimmed }),
      });
      if (!response.ok) {
        setRename((current) => ({
          ...current,
          [row.id]: {
            kind: "failed",
            detail:
              response.status === 404
                ? "the route no longer has this project, so nothing was changed"
                : `the patch route answered ${response.status}`,
          },
        }));
        return;
      }
      const updated = (await response.json()) as { name?: unknown };
      const savedName = typeof updated.name === "string" ? updated.name : "";
      setRename((current) => ({
        ...current,
        [row.id]: {
          kind: "done",
          sentence: savedName
            ? `Renamed. The route now calls it ${savedName}.`
            : "The route accepted the change and returned no name, so what it is now called is not shown here.",
        },
      }));
      setEditing(null);
      await read();
    } catch (error) {
      setRename((current) => ({
        ...current,
        [row.id]: {
          kind: "failed",
          detail: error instanceof Error ? error.message : "the request did not complete",
        },
      }));
    }
  }

  const verdict = readProjectsVerdict(asRead(load));
  const toneClass =
    verdict.tone === "good"
      ? "border-emerald-400/30 text-emerald-200"
      : verdict.tone === "warn"
        ? "border-amber-400/35 text-amber-200"
        : "border-white/15 text-white/70";

  return (
    <div className="min-w-0 space-y-4">
      {load.state === "loading" ? (
        <p className="text-xs text-white/50">Reading the project list.</p>
      ) : (
        <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${toneClass}`}>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
            {verdict.label}
          </p>
          <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
        </div>
      )}

      {load.state === "locked" ? (
        <p className="text-xs leading-relaxed text-white/55">
          Sign in through Talk to DEVON. This panel will not guess at a list it did not read.
        </p>
      ) : null}

      {load.state === "failed" ? (
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      ) : null}

      {load.state === "ok" && load.parsed.rowsWithoutName > 0 ? (
        <p className="text-[11px] leading-relaxed text-amber-200">
          {load.parsed.rowsWithoutName}{" "}
          {load.parsed.rowsWithoutName === 1 ? "row carries" : "rows carry"} no name from the
          route. Those rows are shown by id rather than given one.
        </p>
      ) : null}

      {load.state === "ok" && load.parsed.rows.length > 0 ? (
        <ul className="min-w-0 space-y-2">
          {load.parsed.rows.map((row) => {
            const outcome = rename[row.id];
            // A narrowed local rather than a boolean: `editing?.id === row.id`
            // does not narrow `editing` to non-null inside the callbacks below.
            const draft = editing !== null && editing.id === row.id ? editing : null;
            return (
              <li
                key={row.id}
                className="min-w-0 rounded-xl border border-white/10 bg-black/25 px-3 py-2.5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  {row.name === null ? (
                    <p className="min-w-0 break-all font-mono text-xs text-amber-200">
                      {row.id}
                      <span className="ml-1.5 font-sans text-[11px] text-white/60">
                        (the route sent no name)
                      </span>
                    </p>
                  ) : (
                    <p className="min-w-0 break-words text-sm font-semibold tracking-tight text-white">
                      {row.name}
                    </p>
                  )}
                  <span className="shrink-0 rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                    {row.status ?? "status not sent"}
                  </span>
                </div>

                {row.description === null ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-white/50">
                    No description on this project.
                  </p>
                ) : (
                  <p className="mt-1 text-xs leading-relaxed text-white/70">{row.description}</p>
                )}

                <dl className="mt-2 grid gap-1 text-[11px] text-white/55 sm:grid-cols-2">
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Project</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">{row.id}</dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Organization</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">
                      {row.organizationId ?? "none"}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Created</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(row.createdAt)}</dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Updated</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(row.updatedAt)}</dd>
                  </div>
                </dl>

                {draft !== null ? (
                  <form
                    className="mt-2.5 flex flex-col gap-2 sm:flex-row"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void saveRename(row, draft.value);
                    }}
                  >
                    <label className="sr-only" htmlFor={`project-rename-${row.id}`}>
                      New name for this project
                    </label>
                    <input
                      id={`project-rename-${row.id}`}
                      aria-label="New name for this project"
                      value={draft.value}
                      onChange={(event) => setEditing({ id: row.id, value: event.target.value })}
                      className="min-w-0 flex-1 rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/30"
                    />
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="submit"
                        disabled={outcome?.kind === "sending" || !draft.value.trim()}
                        className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/10 disabled:text-white/50"
                      >
                        {outcome?.kind === "sending" ? "Saving" : "Save name"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(null)}
                        className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    type="button"
                    onClick={() => setEditing({ id: row.id, value: row.name ?? "" })}
                    className="mt-2.5 rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                  >
                    Rename
                  </button>
                )}

                {outcome?.kind === "failed" ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-red-300">
                    The rename was not saved: {outcome.detail}.
                  </p>
                ) : null}
                {outcome?.kind === "done" ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-white/70">
                    {outcome.sentence}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      <form onSubmit={create} className="space-y-2 border-t border-white/10 pt-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="min-w-0 flex-1">
            <label
              className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55"
              htmlFor="project-name"
            >
              New project name
            </label>
            <input
              id="project-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="What this scope is for"
              className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
            />
          </div>
          <div className="min-w-0 flex-1">
            <label
              className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55"
              htmlFor="project-description"
            >
              Description, optional
            </label>
            <input
              id="project-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Left blank means no description, not an empty one"
              className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
            />
          </div>
        </div>
        <button
          type="submit"
          // Also disabled on a failed read, which the first version was not.
          // projects-honesty.ts states that a failed read means the route is
          // down and that creating against it would be writing into something
          // whose state nobody can see. The panel drew the amber UNREADABLE
          // block and left this button live, so the module's doctrine and the
          // panel disagreed. Found by an adversary on 2026-09-10.
          disabled={
            creation.kind === "sending" ||
            !name.trim() ||
            load.state === "locked" ||
            load.state === "failed"
          }
          className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/10 disabled:text-white/50"
        >
          {creation.kind === "sending" ? "Creating" : "Create project"}
        </button>
      </form>

      {creation.kind === "failed" ? (
        <p className="text-xs leading-relaxed text-red-300">
          The project was not created: {creation.detail}.
        </p>
      ) : null}
      {creation.kind === "done" ? (
        <p className="text-xs leading-relaxed text-emerald-200">{creation.sentence}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Refresh
        </button>
        {readAt ? (
          <p className="text-[11px] text-white/55">List read {readAt.toLocaleTimeString()}.</p>
        ) : null}
      </div>

      <p className="text-xs leading-relaxed text-white/50">
        A project is a scope, not a container: creating one moves nothing into it. The knowledge
        routes and the graph route accept a project_id and filter on it, so a project only starts
        doing work once something is filed against it. Archiving is a separate ruling and is not
        offered here, though an archived project still shows its status above.
      </p>
    </div>
  );
}
