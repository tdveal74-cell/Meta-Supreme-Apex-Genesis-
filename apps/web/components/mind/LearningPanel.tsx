"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import { readLearningVerdict, type LearningRead } from "@/components/mind/learning-honesty";

/**
 * Tier 2, what DEVON has actually learned.
 *
 * WHY THIS PANEL EXISTS
 *
 * app/services/agent_tasks.py:246 injects `devon_learning` into the planning
 * context of every agent task, and its read path
 * (app/services/agent_runtime_persistence.py, AgentLearningRepository.context_for)
 * answers from two tables that nothing in this repository ever wrote to. The
 * only writers are POST /agent-tasks/learning/memories,
 * PUT /agent-tasks/learning/skills/{name} and the promote branch of the
 * skill-proposal decide route, and on 2026-09-09 a sweep of the whole tree
 * found no caller for any of them outside tests. So the store was empty by
 * construction, and the emptiness was invisible: no surface read it either.
 *
 * This panel is the missing caller. It reads both list routes and it writes a
 * memory, which is the smallest thing that makes the store non-empty by a
 * human's own hand rather than by a seed nobody asked for.
 *
 * Two honesty rules it holds to, both of them one line of code away from being
 * broken and both proved in scripts/learning-check.ts:
 *
 *  - A failed read is never drawn as an empty store. Those are opposite facts
 *    and the verdict ladder in learning-honesty.ts refuses to merge them.
 *  - Stored is not recalled. Memory search is token overlap against the task
 *    goal, so a stored memory reaches a plan only when its words appear in that
 *    goal. The panel says so rather than implying every memory is in play.
 *
 * Nothing here invents a figure. Counts and rows are what the routes returned,
 * and when a route does not answer the panel says that instead.
 */

type MemoryRow = {
  memory_id: string;
  text: string;
  tags: string[];
  source: string;
  created_at: string;
  updated_at: string;
};

type SkillRow = {
  name: string;
  description: string;
  version: number;
  provenance: string;
  updated_at: string;
};

type Rows<T> =
  | { state: "loading" }
  | { state: "locked" }
  | { state: "ok"; rows: T[] }
  | { state: "failed"; detail: string };

type Submission =
  | { state: "idle" }
  | { state: "saving" }
  | { state: "saved"; memoryId: string }
  | { state: "failed"; detail: string };

function asRead<T>(rows: Rows<T>): LearningRead {
  // "loading" is deliberately reported as locked rather than as a failure or as
  // a count: mid-flight is not a fact about the store either way.
  if (rows.state === "ok") return { state: "ok", count: rows.rows.length };
  if (rows.state === "failed") return { state: "failed", detail: rows.detail };
  return { state: "locked" };
}

export function LearningPanel() {
  const [memories, setMemories] = useState<Rows<MemoryRow>>({ state: "loading" });
  const [skills, setSkills] = useState<Rows<SkillRow>>({ state: "loading" });
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [submission, setSubmission] = useState<Submission>({ state: "idle" });

  const load = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setMemories({ state: "locked" });
      setSkills({ state: "locked" });
      return;
    }
    setMemories({ state: "loading" });
    setSkills({ state: "loading" });

    const headers = { Authorization: `Bearer ${token}` };
    const [memoryResult, skillResult] = await Promise.allSettled([
      fetch(`${API_BASE}/agent-tasks/learning/memories?limit=200`, {
        cache: "no-store",
        headers,
      }),
      fetch(`${API_BASE}/agent-tasks/learning/skills`, { cache: "no-store", headers }),
    ]);

    if (memoryResult.status !== "fulfilled") {
      setMemories({ state: "failed", detail: "the request did not complete" });
    } else if (!memoryResult.value.ok) {
      setMemories({
        state: "failed",
        detail: `the memories route answered ${memoryResult.value.status}`,
      });
    } else {
      setMemories({ state: "ok", rows: (await memoryResult.value.json()) as MemoryRow[] });
    }

    if (skillResult.status !== "fulfilled") {
      setSkills({ state: "failed", detail: "the request did not complete" });
    } else if (!skillResult.value.ok) {
      setSkills({
        state: "failed",
        detail: `the skills route answered ${skillResult.value.status}`,
      });
    } else {
      setSkills({ state: "ok", rows: (await skillResult.value.json()) as SkillRow[] });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const body = text.trim();
    if (!body) return;
    const token = readDevonToken();
    if (!token) {
      setSubmission({ state: "failed", detail: "no session token in this browser" });
      return;
    }
    setSubmission({ state: "saving" });
    try {
      const response = await fetch(`${API_BASE}/agent-tasks/learning/memories`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          text: body,
          tags: tags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
          source: "operator",
        }),
      });
      if (!response.ok) {
        setSubmission({
          state: "failed",
          detail: `the memories route answered ${response.status}`,
        });
        return;
      }
      const saved = (await response.json()) as MemoryRow;
      setSubmission({ state: "saved", memoryId: saved.memory_id });
      setText("");
      setTags("");
      await load();
    } catch (error) {
      setSubmission({
        state: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  async function forget(memoryId: string) {
    const token = readDevonToken();
    if (!token) return;
    const response = await fetch(`${API_BASE}/agent-tasks/learning/memories/${memoryId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      setSubmission({
        state: "failed",
        detail: `deleting ${memoryId} answered ${response.status}`,
      });
      return;
    }
    await load();
  }

  const loading = memories.state === "loading" || skills.state === "loading";
  const verdict = readLearningVerdict(asRead(memories), asRead(skills));
  const toneClass =
    verdict.tone === "good"
      ? "border-emerald-400/30 text-emerald-200"
      : verdict.tone === "warn"
        ? "border-amber-400/35 text-amber-200"
        : "border-white/15 text-white/70";

  return (
    <div className="space-y-4">
      {loading ? (
        <p className="text-xs text-white/50">Reading the learning store.</p>
      ) : (
        <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${toneClass}`}>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em]">
            {verdict.label}
          </p>
          <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
        </div>
      )}

      {memories.state === "failed" || skills.state === "failed" ? (
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      ) : null}

      {memories.state === "ok" && memories.rows.length > 0 ? (
        <ul className="space-y-1.5">
          {memories.rows.slice(0, 8).map((row) => (
            <li
              key={row.memory_id}
              className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs leading-relaxed text-white/80">{row.text}</p>
                <button
                  type="button"
                  onClick={() => void forget(row.memory_id)}
                  className="shrink-0 rounded border border-white/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-white/45 transition hover:border-red-400/40 hover:text-red-200"
                  aria-label={`Forget ${row.memory_id}`}
                >
                  Forget
                </button>
              </div>
              <p className="mt-1 font-mono text-[10px] text-white/45">
                {row.memory_id}, {row.source}
                {row.tags.length ? `, ${row.tags.join(" ")}` : ", untagged"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      {memories.state === "ok" && memories.rows.length > 8 ? (
        <p className="text-[11px] text-white/50">
          Showing the 8 most recent of {memories.rows.length}.
        </p>
      ) : null}

      {skills.state === "ok" && skills.rows.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {skills.rows.map((row) => (
            <span
              key={row.name}
              className="rounded-full border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] text-white/60"
              title={row.description}
            >
              {row.name} <span className="tabular-nums text-white/45">v{row.version}</span>
            </span>
          ))}
        </div>
      ) : null}

      <form onSubmit={submit} className="space-y-2">
        <label className="sr-only" htmlFor="learning-text">
          Memory text
        </label>
        <textarea
          id="learning-text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={3}
          placeholder="A durable instruction, ruling or fact DEVON should carry into future plans"
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs leading-relaxed text-white/85 outline-none transition placeholder:text-white/40 focus:border-white/25"
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="learning-tags">
            Tags, comma separated
          </label>
          <input
            id="learning-tags"
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="tags, comma separated"
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/40 focus:border-white/25"
          />
          <button
            type="submit"
            disabled={submission.state === "saving" || !text.trim()}
            className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:border-white/5 disabled:text-white/30"
          >
            {submission.state === "saving" ? "Writing" : "Write memory"}
          </button>
        </div>
      </form>

      {submission.state === "saved" ? (
        <p className="text-xs text-emerald-200">
          Stored as {submission.memoryId}. It reaches a plan only when its words overlap that
          task&apos;s goal.
        </p>
      ) : null}
      {submission.state === "failed" ? (
        <p className="text-xs text-red-300">The memory was not stored: {submission.detail}.</p>
      ) : null}

      <p className="text-xs leading-relaxed text-white/50">
        Memories and skills are inspectable, replaceable and deletable by design, and this
        panel is the only writer in the estate. Skills are shown read only here: a skill is
        created by promoting an approved proposal or by the skills route, both of which are
        human gated, so this panel does not offer a shortcut past that gate.
      </p>
    </div>
  );
}
