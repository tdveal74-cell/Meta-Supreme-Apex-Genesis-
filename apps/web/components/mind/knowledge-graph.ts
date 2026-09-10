/**
 * The knowledge graph's arithmetic and its refusals, kept out of the component
 * so both can be proved.
 *
 * WHY THIS IS A SEPARATE MODULE
 *
 * apps/web/components/mind/KnowledgePanel.tsx:7 refuses to draw a graph at all,
 * and its reason is the right one: "any graph would be a picture of something
 * nobody measured". A graph route now measures it, so the refusal moves rather
 * than disappears. Every way this picture could lie is decided here, by a pure
 * function with no DOM and no network, because that is the only version a check
 * can mutate and re-measure. apps/web/scripts/control-check.ts tests these
 * directly, the same way it tests readVerdict in components/ledger/
 * provenance-payload.ts.
 *
 * THE THREE LIES THIS MODULE EXISTS TO REFUSE
 *
 *   1. A mock vector. services/intelligence/providers/embeddings.py:11 says the
 *      mock provider produces "normalized hashed bag-of-words vectors, so
 *      overlapping vocabulary yields genuinely higher cosine similarity". That
 *      is a lexical overlap wearing a semantic distance's clothes. It clusters,
 *      it looks convincing, and it means nothing about meaning. classifyProvider
 *      is what stops the panel presenting those distances as real.
 *   2. A silent omission. An item with no embedding has no vector, so it cannot
 *      be placed. Drawing the rest without saying how many are absent turns a
 *      partial picture into a complete-looking one.
 *   3. An invented field. A degraded payload that is missing counts must produce
 *      "the route did not say", never a zero. parseGraphPayload keeps every
 *      absent field as null for exactly this reason.
 */

/* ------------------------------------------------------------------ */
/* The wire shape                                                     */
/* ------------------------------------------------------------------ */

/**
 * One node as the route sends it. Every field except the id is nullable here
 * because a field the route omitted must stay visibly absent: a title defaulted
 * to the id, or a degree defaulted to zero, is a value this panel made up.
 */
export type GraphNode = {
  id: string;
  title: string | null;
  source: string | null;
  created_at: string | null;
  degree: number | null;
};

export type GraphEdge = {
  source: string;
  target: string;
  distance: number;
};

/**
 * The route's own tally. Nullable per field, not per object: a route that sends
 * counts with one key missing is a real case, and the panel has to say which
 * key it did not get rather than read the gap as zero.
 */
export type GraphCounts = {
  items_total: number | null;
  items_ready: number | null;
  items_embedded: number | null;
  items_unembedded: number | null;
  edges_returned: number | null;
  edges_capped: boolean | null;
};

export type ParsedGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** null when the payload carried no counts object at all. Never zeroes. */
  counts: GraphCounts | null;
  /** The route's distance threshold, or null when it named none. */
  maxDistance: number | null;
  /** The embedding provider the route named, or null when it named none. */
  provider: string | null;
  /** Nodes the parser refused because they carried no usable id. */
  malformedNodes: number;
  /** Edges refused for shape: a missing endpoint or a non finite distance. */
  malformedEdges: number;
  /** Edges naming a node the route did not return, so nothing to draw between. */
  unresolvedEdges: number;
  /** Edges from a node to itself, which this layout has no mark for. */
  selfEdges: number;
  /** Nodes that came back with no degree, so they are drawn at the base size. */
  nodesWithoutDegree: number;
  /** Top level keys the payload did not carry. */
  missingFields: string[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function textOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function boolOrNull(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function readCounts(value: unknown): GraphCounts | null {
  if (!isRecord(value)) return null;
  return {
    items_total: finiteOrNull(value.items_total),
    items_ready: finiteOrNull(value.items_ready),
    items_embedded: finiteOrNull(value.items_embedded),
    items_unembedded: finiteOrNull(value.items_unembedded),
    edges_returned: finiteOrNull(value.edges_returned),
    edges_capped: boolOrNull(value.edges_capped),
  };
}

/**
 * Read a graph payload without trusting any part of it.
 *
 * Returns null only when the body is not an object, which is a transport
 * failure rather than a degraded graph. Everything else comes back with the
 * rows that survived and a count of the rows that did not, so the panel can
 * report the shortfall instead of quietly drawing less than it was sent.
 */
export function parseGraphPayload(raw: unknown): ParsedGraph | null {
  if (!isRecord(raw)) return null;

  const missingFields: string[] = [];
  if (!Array.isArray(raw.nodes)) missingFields.push("nodes");
  if (!Array.isArray(raw.edges)) missingFields.push("edges");
  if (!isRecord(raw.counts)) missingFields.push("counts");
  if (finiteOrNull(raw.max_distance) === null) missingFields.push("max_distance");
  if (textOrNull(raw.embedding_provider) === null) missingFields.push("embedding_provider");

  const nodes: GraphNode[] = [];
  let malformedNodes = 0;
  let nodesWithoutDegree = 0;
  const seen = new Set<string>();
  if (Array.isArray(raw.nodes)) {
    for (const row of raw.nodes) {
      if (!isRecord(row)) {
        malformedNodes += 1;
        continue;
      }
      const id = textOrNull(row.id);
      if (id === null || seen.has(id)) {
        // A duplicate id would place one node twice and double its edges.
        malformedNodes += 1;
        continue;
      }
      seen.add(id);
      const degree = finiteOrNull(row.degree);
      if (degree === null) nodesWithoutDegree += 1;
      nodes.push({
        id,
        title: textOrNull(row.title),
        source: textOrNull(row.source),
        created_at: textOrNull(row.created_at),
        degree,
      });
    }
  }

  const edges: GraphEdge[] = [];
  let malformedEdges = 0;
  let unresolvedEdges = 0;
  let selfEdges = 0;
  if (Array.isArray(raw.edges)) {
    for (const row of raw.edges) {
      if (!isRecord(row)) {
        malformedEdges += 1;
        continue;
      }
      const source = textOrNull(row.source);
      const target = textOrNull(row.target);
      const distance = finiteOrNull(row.distance);
      if (source === null || target === null || distance === null) {
        // An edge with no readable distance cannot be drawn honestly: its
        // thickness would be a guess and its readout would be blank.
        malformedEdges += 1;
        continue;
      }
      if (source === target) {
        selfEdges += 1;
        continue;
      }
      if (!seen.has(source) || !seen.has(target)) {
        unresolvedEdges += 1;
        continue;
      }
      edges.push({ source, target, distance });
    }
  }

  return {
    nodes,
    edges,
    counts: readCounts(raw.counts),
    maxDistance: finiteOrNull(raw.max_distance),
    provider: textOrNull(raw.embedding_provider),
    malformedNodes,
    malformedEdges,
    unresolvedEdges,
    selfEdges,
    nodesWithoutDegree,
    missingFields,
  };
}

/* ------------------------------------------------------------------ */
/* Whether the distances mean anything                                */
/* ------------------------------------------------------------------ */

export type ProviderTrust = "simulated" | "real" | "unknown";

/**
 * Decide whether the distances behind this graph came from a real embedding.
 *
 * app/core/config.py:239 defaults EMBEDDING_PROVIDER to "mock", and
 * app/services/knowledge.py:248 reports the provider as
 * getattr(provider, "name", "unknown"), whose values are set at
 * services/intelligence/providers/embeddings.py:126 and :151 as exactly "mock"
 * and "openai". So the three names that actually reach this function are mock,
 * openai and unknown. The substring arms below are for a provider added later
 * whose name says simulated without saying mock: a new fake must fail closed,
 * because the cost of a simulation read as real is a graph that looks like
 * evidence.
 */
export function classifyProvider(name: string | null | undefined): ProviderTrust {
  const value = (name ?? "").trim().toLowerCase();
  if (value === "") return "unknown";
  if (value === "unknown") return "unknown";
  if (
    value.includes("mock") ||
    value.includes("simulat") ||
    value.includes("fake") ||
    value.includes("stub") ||
    value.includes("dummy")
  ) {
    return "simulated";
  }
  return "real";
}

/**
 * Closeness in 0..1 against the route's threshold, where 1 is touching and 0
 * sits exactly on the threshold.
 *
 * Returns null when the route named no threshold. A caller that gets null must
 * draw every edge the same and say so: inventing a scale would make thickness
 * carry a comparison nobody supplied.
 */
export function edgeCloseness(distance: number, maxDistance: number | null): number | null {
  if (maxDistance === null || !Number.isFinite(maxDistance) || maxDistance <= 0) return null;
  if (!Number.isFinite(distance)) return null;
  const clamped = Math.min(Math.max(distance, 0), maxDistance);
  return 1 - clamped / maxDistance;
}

/* ------------------------------------------------------------------ */
/* Four kinds of nothing, told apart                                  */
/* ------------------------------------------------------------------ */

export type GraphVerdict =
  | { kind: "drawable" }
  | { kind: "no-items"; headline: string; detail: string }
  | { kind: "no-embeddings"; headline: string; detail: string }
  | { kind: "no-edges"; headline: string; detail: string }
  | { kind: "unsourced"; headline: string; detail: string }
  | { kind: "disagreement"; headline: string; detail: string };

/**
 * An empty picture has several causes and they are not the same news. A corpus
 * with no items is a fact about the account. A corpus whose items are not
 * embedded is a fact about the pipeline. A corpus that is embedded but has no
 * pair inside the threshold is a fact about the corpus itself. Rendering one
 * blank box for all three, or for a failed request, is the thing this refuses.
 * The failed request is the component's to report, because only the component
 * knows the request failed.
 *
 * The copy lives here rather than in JSX so control-check can assert the four
 * messages are actually different from each other.
 */
export function readGraphVerdict(parsed: ParsedGraph): GraphVerdict {
  const counts = parsed.counts;
  const total = counts?.items_total ?? null;
  const embedded = counts?.items_embedded ?? null;
  const nodeCount = parsed.nodes.length;
  const threshold =
    parsed.maxDistance === null
      ? ", which the route did not state"
      : ` of ${parsed.maxDistance}`;

  if (
    (total === 0 && nodeCount > 0) ||
    (embedded === 0 && nodeCount > 0) ||
    (embedded !== null && embedded > 0 && nodeCount === 0)
  ) {
    return {
      kind: "disagreement",
      headline: "The route's counts and its nodes do not agree.",
      detail:
        `counts reports ${total ?? "an unstated number of"} items and ` +
        `${embedded ?? "an unstated number"} embedded while ${nodeCount} nodes came back. ` +
        "Those cannot both be right, so nothing is drawn rather than one of them being picked.",
    };
  }

  if (total === 0) {
    return {
      kind: "no-items",
      headline: "This corpus has no items.",
      detail:
        "The route answered and reported zero knowledge items for this account. That is a real " +
        "empty corpus read from the route, not a failed request, so there is nothing to place.",
    };
  }

  if (embedded === 0) {
    return {
      kind: "no-embeddings",
      headline: "Items exist, none of them are embedded.",
      detail:
        `The route reports ${total ?? "an unstated number of"} items and zero embedded. A node ` +
        "needs a vector before any distance to it exists, so this is a pipeline state and not an " +
        "empty corpus.",
    };
  }

  if (nodeCount === 0) {
    return {
      kind: "unsourced",
      headline: "No nodes, and no counts to explain why.",
      detail:
        "The route returned an empty node list and no counts, so this cannot tell an empty " +
        "corpus from a corpus with nothing embedded. Both are possible and neither is shown as " +
        "fact.",
    };
  }

  if (parsed.edges.length === 0) {
    return {
      kind: "no-edges",
      headline: "Embedded nodes, no pair close enough to connect.",
      detail:
        `${nodeCount} embedded nodes came back and zero edges. Every pair sits further apart ` +
        `than the threshold${threshold}, so this picture is genuinely edgeless rather than ` +
        "truncated or broken.",
    };
  }

  return { kind: "drawable" };
}

/* ------------------------------------------------------------------ */
/* A layout that does not move                                        */
/* ------------------------------------------------------------------ */

/** The bucket for a node whose source the route did not name. */
export const UNREPORTED_SOURCE = "source not reported";

/**
 * Node fills, keyed by the source's position in a sorted list so the same
 * corpus always gets the same colours. Chosen light enough to read against the
 * ACX void background, #04070d.
 */
export const SOURCE_COLOURS = [
  "#67e8f9",
  "#fca5a5",
  "#a5b4fc",
  "#86efac",
  "#fcd34d",
  "#f0abfc",
  "#7dd3fc",
  "#fdba74",
] as const;

export const UNKNOWN_SOURCE_COLOUR = "#94a3b8";

export type LayoutBox = { width: number; height: number; pad: number };

export const GRAPH_BOX: LayoutBox = { width: 480, height: 480, pad: 28 };

export type PlacedNode = {
  node: GraphNode;
  x: number;
  y: number;
  radius: number;
  colour: string;
  sourceKey: string;
};

/**
 * A total order over nodes. Total matters: any pair that compares equal here
 * would be placed in whatever order the route happened to send, and the layout
 * would move between two responses carrying the same data. The id tiebreak is
 * what makes the comparison total, so it is load bearing rather than tidy.
 *
 * String comparison is done with the relational operators, not localeCompare,
 * because localeCompare depends on the runtime's locale data and would give two
 * machines two different pictures of one corpus.
 */
export function compareNodes(a: GraphNode, b: GraphNode): number {
  const aSource = a.source ?? UNREPORTED_SOURCE;
  const bSource = b.source ?? UNREPORTED_SOURCE;
  if (aSource !== bSource) return aSource < bSource ? -1 : 1;
  const aDegree = a.degree ?? 0;
  const bDegree = b.degree ?? 0;
  if (aDegree !== bDegree) return bDegree - aDegree;
  const aMade = a.created_at ?? "";
  const bMade = b.created_at ?? "";
  if (aMade !== bMade) return aMade < bMade ? -1 : 1;
  if (a.id !== b.id) return a.id < b.id ? -1 : 1;
  return 0;
}

/** Every source present, sorted, so a colour index never depends on send order. */
export function sourceOrder(nodes: GraphNode[]): string[] {
  const keys = new Set<string>();
  for (const node of nodes) keys.add(node.source ?? UNREPORTED_SOURCE);
  return [...keys].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

export function colourForSource(source: string | null, order: string[]): string {
  const key = source ?? UNREPORTED_SOURCE;
  const index = order.indexOf(key);
  if (index < 0) return UNKNOWN_SOURCE_COLOUR;
  return SOURCE_COLOURS[index % SOURCE_COLOURS.length];
}

/** True when there are more sources than colours, so two of them repeat a fill. */
export function paletteRepeats(order: string[]): boolean {
  return order.length > SOURCE_COLOURS.length;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Place nodes on a ring, grouped by source, hubs pulled inward.
 *
 * Deterministic by construction: no Math.random, no Date, no iteration over an
 * unsorted map. Two renders of the same payload give byte identical coordinates,
 * which is the only way two screenshots of this panel can be compared. A force
 * layout would have been prettier and would have moved every time.
 *
 * The ring is grouped rather than arbitrary so an edge crossing the middle means
 * two sources are near each other in vector space, which is the one structural
 * claim this picture is entitled to make.
 */
export function layoutNodes(nodes: GraphNode[], box: LayoutBox = GRAPH_BOX): PlacedNode[] {
  const ordered = [...nodes].sort(compareNodes);
  const order = sourceOrder(nodes);
  const count = ordered.length;
  const centreX = box.width / 2;
  const centreY = box.height / 2;
  const outer = Math.max(0, Math.min(box.width, box.height) / 2 - box.pad);
  let maxDegree = 0;
  for (const node of ordered) maxDegree = Math.max(maxDegree, node.degree ?? 0);

  return ordered.map((node, index) => {
    const angle = count <= 1 ? -Math.PI / 2 : (index / count) * Math.PI * 2 - Math.PI / 2;
    const share = maxDegree > 0 ? (node.degree ?? 0) / maxDegree : 0;
    // Index parity staggers the ring into two lanes so adjacent marks do not
    // touch at high node counts, and it is a function of the sorted index, so
    // it is as stable as the order itself.
    const stagger = index % 2 === 0 ? 0 : outer * 0.11;
    const radius = count <= 1 ? 0 : Math.max(0, outer * (1 - 0.3 * share) - stagger);
    return {
      node,
      x: round2(centreX + radius * Math.cos(angle)),
      y: round2(centreY + radius * Math.sin(angle)),
      radius: round2(3.2 + 3.6 * Math.sqrt(share)),
      colour: colourForSource(node.source, order),
      sourceKey: node.source ?? UNREPORTED_SOURCE,
    };
  });
}

/** The nodes of an edge, or null when either end was not placed. */
export function edgeEnds(
  edge: GraphEdge,
  placed: Map<string, PlacedNode>,
): { from: PlacedNode; to: PlacedNode } | null {
  const from = placed.get(edge.source);
  const to = placed.get(edge.target);
  if (!from || !to) return null;
  return { from, to };
}

/** A stable key for an edge, so React never reorders one row onto another. */
export function edgeKey(edge: GraphEdge): string {
  return `${edge.source}~${edge.target}~${edge.distance}`;
}

/** Edges sorted nearest first, deterministically. */
export function sortEdges(edges: GraphEdge[]): GraphEdge[] {
  return [...edges].sort((a, b) => {
    if (a.distance !== b.distance) return a.distance - b.distance;
    if (a.source !== b.source) return a.source < b.source ? -1 : 1;
    if (a.target !== b.target) return a.target < b.target ? -1 : 1;
    return 0;
  });
}

/* ------------------------------------------------------------------ */
/* What the payload leaves out                                        */
/* ------------------------------------------------------------------ */

/**
 * Everything the payload leaves out or contradicts, in the payload's own terms.
 *
 * Split out as a plain function over the parsed graph so scripts/control-check.ts
 * can assert that an unembedded count and a capped edge list actually produce a
 * sentence, rather than a reviewer trusting that the JSX above covers it.
 */
export function describeGaps(graph: ParsedGraph, sources: string[]): string[] {
  const notes: string[] = [];
  const counts = graph.counts;

  if (counts === null) {
    notes.push(
      "The route sent no counts, so this panel cannot say how many items are absent from the picture. Read the graph as an unknown fraction of the corpus.",
    );
  } else {
    const total = counts.items_total;
    const embedded = counts.items_embedded;
    if (counts.items_unembedded !== null && counts.items_unembedded > 0) {
      notes.push(
        `${counts.items_unembedded} item${counts.items_unembedded === 1 ? "" : "s"} ` +
          `${total === null ? "" : `of ${total} `}have no embedding, so they are not in this picture at all.`,
      );
    } else if (counts.items_unembedded === null && total !== null && embedded !== null) {
      const derived = total - embedded;
      notes.push(
        derived > 0
          ? `The route sent no items_unembedded. Its own ${total} total and ${embedded} embedded leave ${derived} item${derived === 1 ? "" : "s"} out of this picture.`
          : "The route sent no items_unembedded, and its own total and embedded counts agree, so nothing appears to be left out.",
      );
    } else if (counts.items_unembedded === null) {
      notes.push(
        "The route sent no items_unembedded and not enough of the other counts to work it out, so how much is missing is unknown.",
      );
    }

    if (counts.edges_capped === true) {
      notes.push(
        `This graph is truncated. The route capped the edge list${counts.edges_returned === null ? "" : ` at ${counts.edges_returned}`}, so there are more pairs inside the threshold than are drawn here.`,
      );
    } else if (counts.edges_capped === null) {
      notes.push(
        "The route did not say whether it capped the edge list, so this graph cannot be claimed to be complete.",
      );
    }

    const arrived =
      graph.edges.length + graph.malformedEdges + graph.unresolvedEdges + graph.selfEdges;
    if (counts.edges_returned !== null && counts.edges_returned !== arrived) {
      notes.push(
        `The route says it returned ${counts.edges_returned} edges and ${arrived} arrived. One of those two is wrong and this panel is not guessing which.`,
      );
    }
  }

  if (graph.malformedNodes > 0) {
    notes.push(
      `${graph.malformedNodes} node row${graph.malformedNodes === 1 ? "" : "s"} carried no usable id, or repeated one, and were dropped rather than placed twice.`,
    );
  }
  if (graph.malformedEdges > 0) {
    notes.push(
      `${graph.malformedEdges} edge row${graph.malformedEdges === 1 ? "" : "s"} had no readable distance or endpoint, so they are not drawn: a line with a guessed thickness would be an assertion.`,
    );
  }
  if (graph.unresolvedEdges > 0) {
    notes.push(
      `${graph.unresolvedEdges} edge${graph.unresolvedEdges === 1 ? "" : "s"} name a node the route did not return, so there is nothing to draw between.`,
    );
  }
  if (graph.selfEdges > 0) {
    notes.push(
      `${graph.selfEdges} edge${graph.selfEdges === 1 ? "" : "s"} join a node to itself, which this layout has no mark for.`,
    );
  }
  if (graph.nodesWithoutDegree > 0) {
    notes.push(
      `${graph.nodesWithoutDegree} node${graph.nodesWithoutDegree === 1 ? "" : "s"} came back with no degree, so they are drawn at the base size and sit on the outer lane by default.`,
    );
  }
  if (graph.maxDistance === null) {
    notes.push(
      "The route named no distance threshold, so every line is drawn the same weight. Thickness carries no comparison here and only the printed distance does.",
    );
  }
  if (paletteRepeats(sources)) {
    notes.push(
      `There are ${sources.length} sources and fewer fills than that, so two sources share a colour. The legend is authoritative, the fill is not.`,
    );
  }
  if (graph.missingFields.length > 0) {
    notes.push(`The payload carried no usable ${graph.missingFields.join(", ")}.`);
  }
  return notes;
}
