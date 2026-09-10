"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  GRAPH_BOX,
  classifyProvider,
  colourForSource,
  describeGaps,
  edgeCloseness,
  edgeKey,
  layoutNodes,
  parseGraphPayload,
  readGraphVerdict,
  sortEdges,
  sourceOrder,
  type GraphEdge,
  type ParsedGraph,
  type PlacedNode,
} from "./knowledge-graph.ts";

/**
 * Tier 2, the edges behind the memory.
 *
 * WHAT REPLACED WHAT
 *
 * components/mind/KnowledgePanel.tsx:7 says no graph is drawn here because "no
 * route exposes vector activations or edges between the indexes, so any graph
 * would be a picture of something nobody measured". GET /knowledge/graph now
 * measures them, so that refusal is spent. The obligation behind it is not: a
 * graph is the easiest surface in this estate to lie with, because a wrong one
 * still looks like a diagram of something. Everything below exists to keep this
 * panel from becoming the thing that comment warned about.
 *
 * THE FOUR WAYS THIS PANEL REFUSES TO LIE
 *
 *   1. Simulated vectors are named as simulated, at the top, before the picture.
 *      app/core/config.py:239 defaults EMBEDDING_PROVIDER to mock, and the mock
 *      provider is documented at services/intelligence/providers/embeddings.py:11
 *      as hashed bag-of-words, so it clusters on shared vocabulary and produces
 *      exactly the confident looking clumps a reader would take for meaning. A
 *      graph drawn from those is a graph of word overlap.
 *   2. Missing data is counted out loud. Items with no embedding have no vector
 *      and cannot be placed, so the panel says how many are absent rather than
 *      drawing what is left as if it were everything.
 *   3. A truncated edge list says it is truncated, and a route that will not say
 *      whether it truncated gets reported as that too.
 *   4. Nothing is one thing. No items, items with no embeddings, embeddings with
 *      no pair inside the threshold, and a failed request are four different
 *      facts, told apart in readGraphVerdict and in the failure branch here.
 *
 * WHY THE NUMBERS ARE IN THE DOM AND NOT IN THE SVG
 *
 * Every distance is readable as real HTML text: in the readout under the graph
 * on hover or focus, and in the full edge list below it. Drawing them as SVG
 * text instead would put them at roughly eight rendered pixels on the phone this
 * surface is built for, since the viewBox is 480 wide inside a column that is
 * often 340. scripts/control-check.ts bans any Tailwind size class under eleven
 * pixels and cannot see an SVG font-size attribute, so the check would have
 * passed and the number would still have been unreadable. Naming the banned
 * class here in prose trips that same check, which is how this comment was
 * written the second time.
 */

type Phase =
  | { kind: "signed-out" }
  | { kind: "loading" }
  | { kind: "failed"; status: number | null; detail: string }
  | { kind: "ready"; graph: ParsedGraph };

type Active = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

/** Floating point slack, so a slider at its maximum keeps the loosest edge. */
const KEEP_EPSILON = 1e-9;

function failureDetail(status: number): string {
  if (status === 401 || status === 403) {
    return `the route refused this browser's token with ${status}, so nothing is drawn rather than an empty graph`;
  }
  if (status === 404) {
    // Measured on 2026-09-09 with a two route FastAPI app: a literal path
    // registered after a parameterised path that also matches never runs. This
    // repository registers GET /knowledge/{item_id} at app/api/v1/knowledge.py:183,
    // so a graph route added below that line answers 404 through the item lookup.
    return "404. Either the graph route is not on this build, or it is registered below GET /knowledge/{item_id} and that parameterised route is answering first";
  }
  if (status >= 500) {
    return `the route answered ${status}, which is a server error and says nothing about the corpus`;
  }
  return `the graph route answered ${status}`;
}

export function KnowledgeGraphPanel() {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [active, setActive] = useState<Active>(null);
  const [ceilingPct, setCeilingPct] = useState(100);

  const load = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setPhase({ kind: "signed-out" });
      return;
    }
    setPhase({ kind: "loading" });
    try {
      const response = await fetch(`${API_BASE}/knowledge/graph`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setPhase({ kind: "failed", status: response.status, detail: failureDetail(response.status) });
        return;
      }
      const body: unknown = await response.json();
      const graph = parseGraphPayload(body);
      if (graph === null) {
        setPhase({
          kind: "failed",
          status: response.status,
          detail: "the route answered but the body is not an object, so there is no graph in it to read",
        });
        return;
      }
      setPhase({ kind: "ready", graph });
    } catch (error) {
      setPhase({
        kind: "failed",
        status: null,
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // A new payload gets the full picture back. Carrying a filter across a reload
  // would hide edges the reader never chose to hide.
  useEffect(() => {
    setActive(null);
    setCeilingPct(100);
  }, [phase]);

  const view = useMemo(() => {
    if (phase.kind !== "ready") return null;
    const graph = phase.graph;
    const placed = layoutNodes(graph.nodes, GRAPH_BOX);
    const byId = new Map<string, PlacedNode>(placed.map((entry) => [entry.node.id, entry]));
    return {
      graph,
      verdict: readGraphVerdict(graph),
      placed,
      byId,
      sources: sourceOrder(graph.nodes),
      edges: sortEdges(graph.edges),
      trust: classifyProvider(graph.provider),
    };
  }, [phase]);

  const span = useMemo(() => {
    if (!view || view.edges.length === 0) return null;
    // sortEdges puts the nearest first, so the ends of the list are the bounds.
    const min = view.edges[0].distance;
    const max = view.edges[view.edges.length - 1].distance;
    return max > min ? { min, max } : null;
  }, [view]);

  const ceiling = span === null ? null : span.min + ((span.max - span.min) * ceilingPct) / 100;
  const shownEdges = useMemo(() => {
    if (!view) return [] as GraphEdge[];
    if (ceiling === null) return view.edges;
    return view.edges.filter((edge) => edge.distance <= ceiling + KEEP_EPSILON);
  }, [view, ceiling]);

  const distanceWord = view?.trust === "simulated" ? "simulated distance" : "distance";

  const nodeLabel = useCallback(
    (placed: PlacedNode, edgeCount: number) => {
      const title = placed.node.title ?? "no title from the route";
      const source = placed.node.source ?? "source not reported";
      const degree = placed.node.degree === null ? "degree not reported" : `degree ${placed.node.degree}`;
      const created = placed.node.created_at ?? "created date not reported";
      return `${title}. ${source}, ${degree}, created ${created}. ${edgeCount} of the drawn edges touch it.`;
    },
    [],
  );

  const edgeLabel = useCallback(
    (edge: GraphEdge) => {
      if (!view) return "";
      const from = view.byId.get(edge.source)?.node.title ?? edge.source;
      const to = view.byId.get(edge.target)?.node.title ?? edge.target;
      const closeness = edgeCloseness(edge.distance, view.graph.maxDistance);
      const scale =
        closeness === null
          ? "The route named no threshold, so this distance has nothing to be scaled against and every edge is drawn the same."
          : `${Math.round(closeness * 100)} percent of the way in from the threshold of ${view.graph.maxDistance}.`;
      return `${from} to ${to}. ${distanceWord} ${edge.distance.toFixed(4)}. ${scale}`;
    },
    [view, distanceWord],
  );

  const activeText = useMemo(() => {
    if (!view || active === null) return null;
    if (active.kind === "node") {
      const placed = view.byId.get(active.id);
      if (!placed) return null;
      const touching = shownEdges.filter(
        (edge) => edge.source === active.id || edge.target === active.id,
      ).length;
      return nodeLabel(placed, touching);
    }
    const edge = shownEdges.find((candidate) => edgeKey(candidate) === active.key);
    return edge ? edgeLabel(edge) : null;
  }, [view, active, shownEdges, nodeLabel, edgeLabel]);

  const gaps = useMemo(() => (view ? describeGaps(view.graph, view.sources) : []), [view]);

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-white/70">
        Nodes are knowledge items, coloured by source. A line means the two items sit inside the
        route&apos;s distance threshold, drawn thicker and brighter the nearer they are. Every
        distance below is the number the route returned, not a similarity score derived from it.
      </p>

      {phase.kind === "loading" ? (
        <p className="text-xs text-white/60">Reading the graph.</p>
      ) : null}

      {phase.kind === "signed-out" ? (
        <p className="text-xs leading-relaxed text-white/60">
          No session token in this browser. The corpus is per account, so no graph is drawn rather
          than an empty one that could be read as a real one.
        </p>
      ) : null}

      {phase.kind === "failed" ? (
        <div className="space-y-2 rounded-xl border border-red-400/40 bg-red-400/10 px-3 py-2.5">
          <p className="text-xs font-semibold text-red-200">The graph could not be read.</p>
          <p className="text-[11px] leading-relaxed text-red-100/90">{phase.detail}.</p>
          <p className="text-[11px] leading-relaxed text-white/70">
            This is a failed read. It is not an empty corpus, and it is not a corpus with no edges.
            Those are different facts and this panel will not print one in place of another.
          </p>
        </div>
      ) : null}

      {view && view.trust === "simulated" ? (
        <div className="rounded-xl border border-amber-300/60 bg-amber-300/10 px-3 py-2.5">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-amber-200">
            These distances are simulated
          </p>
          <p className="mt-1.5 text-[11px] leading-relaxed text-amber-100/90">
            The route reports its embedding provider as{" "}
            <span className="font-semibold">{view.graph.provider}</span>. That provider builds
            hashed bag-of-words vectors, so two items are near each other when they share words,
            not when they share meaning. The clusters below are real arithmetic over fake vectors:
            read them as a wiring test of this panel and of the route, and read none of them as a
            finding about the corpus.
          </p>
        </div>
      ) : null}

      {view && view.trust === "unknown" ? (
        <div className="rounded-xl border border-white/25 bg-white/5 px-3 py-2.5">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-white/80">
            Provenance of these distances is unstated
          </p>
          <p className="mt-1.5 text-[11px] leading-relaxed text-white/70">
            The route named no embedding provider, so this panel cannot tell a real embedding from a
            simulated one. Treat every distance here as unverified until the route says which
            provider produced it.
          </p>
        </div>
      ) : null}

      {view ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Figure label="Nodes drawn" value={String(view.placed.length)} />
            <Figure
              label="Edges drawn"
              value={
                shownEdges.length === view.edges.length
                  ? String(view.edges.length)
                  : `${shownEdges.length} of ${view.edges.length}`
              }
            />
            <Figure
              label="Items"
              value={
                view.graph.counts?.items_total === null || view.graph.counts === null
                  ? "not reported"
                  : String(view.graph.counts.items_total)
              }
            />
            <Figure
              label="Threshold"
              value={view.graph.maxDistance === null ? "not reported" : String(view.graph.maxDistance)}
            />
          </div>

          {gaps.length > 0 ? (
            <div className="rounded-xl border border-white/15 bg-black/25 px-3 py-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
                What this picture is missing
              </p>
              <ul className="mt-1.5 space-y-1">
                {gaps.map((gap) => (
                  <li key={gap} className="text-[11px] leading-relaxed text-white/70">
                    {gap}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {view.verdict.kind !== "drawable" ? (
            <div className="rounded-xl border border-white/15 bg-black/25 px-3 py-3">
              <p className="text-xs font-semibold text-white/85">{view.verdict.headline}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/70">
                {view.verdict.detail}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <svg
                  viewBox={`0 0 ${GRAPH_BOX.width} ${GRAPH_BOX.height}`}
                  className="h-auto w-full min-w-[280px] rounded-xl border border-white/10 bg-black/30"
                  aria-labelledby="knowledge-graph-title knowledge-graph-desc"
                >
                  <title id="knowledge-graph-title">
                    {`Knowledge graph: ${view.placed.length} items, ${shownEdges.length} edges drawn`}
                  </title>
                  <desc id="knowledge-graph-desc">
                    {`Each mark is a knowledge item, placed on a ring grouped by source with the ` +
                      `most connected items pulled inward. Each line is a pair inside the route's ` +
                      `distance threshold. Every node and every line can be focused with the ` +
                      `keyboard, and its exact numbers appear in the readout under this graph. ` +
                      `The same list is written out in full below.`}
                  </desc>

                  {shownEdges.map((edge) => {
                    const from = view.byId.get(edge.source);
                    const to = view.byId.get(edge.target);
                    if (!from || !to) return null;
                    const key = edgeKey(edge);
                    const closeness = edgeCloseness(edge.distance, view.graph.maxDistance);
                    const lit =
                      (active?.kind === "edge" && active.key === key) ||
                      (active?.kind === "node" &&
                        (active.id === edge.source || active.id === edge.target));
                    // No threshold means no scale, so every edge is drawn the
                    // same width rather than given an invented one.
                    const opacity = closeness === null ? 0.5 : 0.2 + 0.75 * closeness;
                    const width = closeness === null ? 1.1 : 0.7 + 2.1 * closeness;
                    return (
                      <g
                        key={key}
                        role="img"
                        tabIndex={0}
                        aria-label={edgeLabel(edge)}
                        onFocus={() => setActive({ kind: "edge", key })}
                        onBlur={() => setActive(null)}
                        onMouseEnter={() => setActive({ kind: "edge", key })}
                        onMouseLeave={() => setActive(null)}
                      >
                        <title>{edgeLabel(edge)}</title>
                        {/* A line two pixels wide is not a target on a phone.
                            pointer-events is set explicitly because the default
                            visiblePainted will not reliably hit an invisible
                            stroke. */}
                        <line
                          x1={from.x}
                          y1={from.y}
                          x2={to.x}
                          y2={to.y}
                          stroke="#000000"
                          strokeOpacity={0}
                          strokeWidth={10}
                          pointerEvents="stroke"
                        />
                        <line
                          x1={from.x}
                          y1={from.y}
                          x2={to.x}
                          y2={to.y}
                          stroke={lit ? "#f8fafc" : "#cbd5e1"}
                          strokeOpacity={lit ? 1 : opacity}
                          strokeWidth={lit ? width + 1.6 : width}
                          strokeLinecap="round"
                          pointerEvents="none"
                        />
                      </g>
                    );
                  })}

                  {view.placed.map((placed) => {
                    const touching = shownEdges.filter(
                      (edge) => edge.source === placed.node.id || edge.target === placed.node.id,
                    ).length;
                    const lit =
                      (active?.kind === "node" && active.id === placed.node.id) ||
                      (active?.kind === "edge" &&
                        shownEdges.some(
                          (edge) =>
                            edgeKey(edge) === active.key &&
                            (edge.source === placed.node.id || edge.target === placed.node.id),
                        ));
                    return (
                      <g
                        key={placed.node.id}
                        role="img"
                        tabIndex={0}
                        aria-label={nodeLabel(placed, touching)}
                        onFocus={() => setActive({ kind: "node", id: placed.node.id })}
                        onBlur={() => setActive(null)}
                        onMouseEnter={() => setActive({ kind: "node", id: placed.node.id })}
                        onMouseLeave={() => setActive(null)}
                      >
                        <title>{nodeLabel(placed, touching)}</title>
                        {lit ? (
                          <circle
                            cx={placed.x}
                            cy={placed.y}
                            r={placed.radius + 4.5}
                            fill="none"
                            stroke={placed.colour}
                            strokeWidth={1.4}
                          />
                        ) : null}
                        <circle
                          cx={placed.x}
                          cy={placed.y}
                          r={placed.radius}
                          fill={placed.colour}
                          fillOpacity={lit ? 1 : 0.85}
                          stroke="#04070d"
                          strokeWidth={0.9}
                        />
                      </g>
                    );
                  })}
                </svg>
              </div>

              <p
                aria-live="polite"
                className="min-h-[3rem] rounded-lg border border-white/10 bg-black/20 px-2.5 py-2 text-[11px] leading-relaxed text-white/80"
              >
                {activeText ??
                  "Focus or hover any node or line to read its exact numbers here. Every edge is also written out with its distance below."}
              </p>

              <div className="flex flex-wrap gap-1.5">
                {view.sources.map((source) => {
                  const count = view.placed.filter((placed) => placed.sourceKey === source).length;
                  return (
                    <span
                      key={source}
                      className="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] text-white/70"
                    >
                      <span
                        aria-hidden
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: colourForSource(source, view.sources) }}
                      />
                      {source} <span className="tabular-nums text-white/60">{count}</span>
                    </span>
                  );
                })}
              </div>

              {span !== null && ceiling !== null ? (
                <div className="space-y-1.5">
                  <label
                    htmlFor="knowledge-graph-ceiling"
                    className="block text-[11px] font-medium text-white/80"
                  >
                    Hide edges looser than{" "}
                    <span className="tabular-nums">{ceiling.toFixed(4)}</span>
                  </label>
                  <input
                    id="knowledge-graph-ceiling"
                    aria-describedby="knowledge-graph-ceiling-note"
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={ceilingPct}
                    onChange={(event) => setCeilingPct(Number(event.target.value))}
                    className="w-full accent-cyan-300"
                  />
                  <p id="knowledge-graph-ceiling-note" className="text-[11px] leading-relaxed text-white/60">
                    This hides edges the route already returned. It does not ask the route for a
                    tighter threshold, so it can never reveal an edge the route left out.
                    Showing {shownEdges.length} of {view.edges.length}, between{" "}
                    <span className="tabular-nums">{span.min.toFixed(4)}</span> and{" "}
                    <span className="tabular-nums">{span.max.toFixed(4)}</span>.
                  </p>
                </div>
              ) : null}

              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
                  Every drawn edge and its {distanceWord}
                </p>
                <div className="mt-1.5 max-h-64 overflow-y-auto rounded-lg border border-white/10">
                  <ul className="divide-y divide-white/5">
                    {shownEdges.map((edge) => {
                      const key = edgeKey(edge);
                      const from = view.byId.get(edge.source);
                      const to = view.byId.get(edge.target);
                      return (
                        <li
                          key={key}
                          className={`px-2.5 py-1.5 text-[11px] leading-relaxed ${
                            active?.kind === "edge" && active.key === key
                              ? "bg-white/10 text-white"
                              : "text-white/70"
                          }`}
                        >
                          <span className="tabular-nums font-semibold text-white/85">
                            {edge.distance.toFixed(4)}
                          </span>{" "}
                          {from?.node.title ?? edge.source} to {to?.node.title ?? edge.target}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
            </>
          )}
        </>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:border-white/30 hover:text-white"
        >
          Reload the graph
        </button>
        <span className="text-[11px] text-white/60">
          Read once on mount. Nothing here polls, so what you see is the answer to one request.
        </span>
      </div>

      <p className="text-xs leading-relaxed text-white/60">
        The layout is deterministic: nodes are sorted by source, then by degree, then by created
        date, then by id, and placed on a ring with the most connected pulled inward. The same
        payload always draws the same picture, so two readings can be compared. Position carries no
        meaning beyond that grouping, and a short line does not mean two items are near each other
        in vector space. Only the printed distance says that.
      </p>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums text-white">{value}</p>
    </div>
  );
}
