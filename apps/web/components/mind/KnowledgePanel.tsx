"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";

/**
 * Tier 2, the memory behind the face.
 *
 * The brief calls this the second brain knowledge graph across Drive, Notion
 * and Pinecone namespaces. No graph is drawn here, and that is deliberate: no
 * route exposes vector activations or edges between the indexes, so any graph
 * would be a picture of something nobody measured. What the routes do give is
 * the corpus itself and a real search over it, which is what this shows.
 *
 * Distance from the search route is a distance, not a score. Smaller is nearer,
 * so it is labelled as distance rather than dressed up as a percentage
 * confidence that the API never returned.
 */

type KnowledgeItem = {
  id: string;
  title: string;
  source_type: string;
  source_uri: string | null;
  status: string;
  chunk_count: number;
  created_at: string;
};

type SearchHit = {
  knowledge_item_id: string;
  title: string;
  source_type: string;
  chunk_index: number;
  content: string;
  distance: number;
};

type Corpus =
  | { state: "loading" }
  | { state: "signed-out" }
  | { state: "ready"; items: KnowledgeItem[] }
  | { state: "error"; detail: string };

type Search =
  | { state: "idle" }
  | { state: "running" }
  | { state: "done"; hits: SearchHit[]; query: string }
  | { state: "error"; detail: string };

export function KnowledgePanel() {
  const [corpus, setCorpus] = useState<Corpus>({ state: "loading" });
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<Search>({ state: "idle" });

  const load = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setCorpus({ state: "signed-out" });
      return;
    }
    setCorpus({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/knowledge`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setCorpus({ state: "error", detail: `the knowledge route answered ${response.status}` });
        return;
      }
      setCorpus({ state: "ready", items: (await response.json()) as KnowledgeItem[] });
    } catch (error) {
      setCorpus({
        state: "error",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const bySource = useMemo(() => {
    if (corpus.state !== "ready") return [];
    const counts = new Map<string, number>();
    for (const item of corpus.items) {
      counts.set(item.source_type, (counts.get(item.source_type) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [corpus]);

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    const token = readDevonToken();
    if (!token) {
      setSearch({ state: "error", detail: "no session token in this browser" });
      return;
    }
    setSearch({ state: "running" });
    try {
      const response = await fetch(`${API_BASE}/knowledge/search`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, limit: 5 }),
      });
      if (!response.ok) {
        setSearch({ state: "error", detail: `search answered ${response.status}` });
        return;
      }
      setSearch({ state: "done", hits: (await response.json()) as SearchHit[], query: text });
    } catch (error) {
      setSearch({
        state: "error",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  return (
    <div className="space-y-4">
      {corpus.state === "loading" ? (
        <p className="text-xs text-white/50">Reading the corpus.</p>
      ) : null}

      {corpus.state === "signed-out" ? (
        <p className="text-xs leading-relaxed text-white/50">
          No session token in this browser. The corpus is per account, so nothing is shown
          rather than an empty one.
        </p>
      ) : null}

      {corpus.state === "error" ? (
        <div className="space-y-2">
          <p className="text-xs text-red-300">The corpus could not be read: {corpus.detail}.</p>
          <p className="text-xs text-white/50">
            This is a failed read. It does not mean the corpus is empty.
          </p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
          >
            Try again
          </button>
        </div>
      ) : null}

      {corpus.state === "ready" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Figure label="Items" value={String(corpus.items.length)} />
            <Figure
              label="Chunks"
              value={String(corpus.items.reduce((n, i) => n + (i.chunk_count || 0), 0))}
            />
          </div>

          {corpus.items.length === 0 ? (
            <p className="text-xs leading-relaxed text-white/50">
              This account has no knowledge items. That is a real empty corpus, read from
              the route, not a failed request.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-1.5">
                {bySource.map(([source, count]) => (
                  <span
                    key={source}
                    className="rounded-full border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] text-white/60"
                  >
                    {source} <span className="tabular-nums text-white/50">{count}</span>
                  </span>
                ))}
              </div>

              <ul className="space-y-1.5">
                {corpus.items.slice(0, 5).map((item) => (
                  <li
                    key={item.id}
                    className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2"
                  >
                    <p className="truncate text-xs text-white/80">{item.title}</p>
                    <p className="mt-0.5 text-[11px] text-white/50">
                      {item.source_type}
                      {item.status !== "ready" ? `, ${item.status}` : ""}
                      {item.chunk_count ? `, ${item.chunk_count} chunks` : ", not chunked"}
                    </p>
                  </li>
                ))}
              </ul>
              {corpus.items.length > 5 ? (
                <p className="text-[11px] text-white/50">
                  Showing the 5 most recent of {corpus.items.length}.
                </p>
              ) : null}
            </>
          )}
        </>
      ) : null}

      <form onSubmit={runSearch} className="flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="knowledge-query">
          Search the corpus
        </label>
        <input
          id="knowledge-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search the corpus"
          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/85 outline-none transition placeholder:text-white/50 focus:border-white/25"
        />
        <button
          type="submit"
          className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white"
        >
          Search
        </button>
      </form>

      {search.state === "running" ? (
        <p className="text-xs text-white/50">Searching.</p>
      ) : null}
      {search.state === "error" ? (
        <p className="text-xs text-red-300">Search failed: {search.detail}.</p>
      ) : null}
      {search.state === "done" ? (
        search.hits.length === 0 ? (
          <p className="text-xs text-white/50">
            Nothing matched {`"${search.query}"`}. The search ran and returned no rows.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {search.hits.map((hit) => (
              <li
                key={`${hit.knowledge_item_id}-${hit.chunk_index}`}
                className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate text-xs text-white/80">{hit.title}</p>
                  <span className="shrink-0 tabular-nums text-[11px] text-white/50">
                    distance {hit.distance.toFixed(3)}
                  </span>
                </div>
                <p className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-white/50">
                  {hit.content}
                </p>
              </li>
            ))}
          </ul>
        )
      ) : null}

      <p className="text-xs leading-relaxed text-white/50">
        No route exposes vector activations or edges between the Drive, Notion and Pinecone
        namespaces, so no graph is drawn. Distance is the raw distance the search route
        returns, where smaller is nearer, not a confidence score.
      </p>
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
