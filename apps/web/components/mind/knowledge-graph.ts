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
  /** Chunks of this item that carry a vector, from the route. null when unstated. */
  embeddedChunks: number | null;
  /** Edges touching this node, DERIVED from the payload's edge list. */
  degree: number | null;
};

export type GraphEdge = {
  source: string;
  target: string;
  distance: number;
  /**
   * The route says this distance may be LOWER than reported, so it is a ceiling
   * rather than a measurement. `assemble_graph` raises it when either endpoint
   * had its chunk list truncated by chunk_cap (app/services/knowledge_graph.py
   * :524), because the pairs it never compared could have been nearer. A panel
   * that prints such a number as the distance is overstating how far apart two
   * items are, and it is the direction that makes a graph look sparser and
   * safer than the corpus really is. null when the route did not say.
   */
  distanceIsUpperBound: boolean | null;
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
  /** Items whose vectors came from a simulated provider. */
  items_simulated_embeddings: number | null;
  edges_returned: number | null;
  edges_capped: boolean | null;
  /** True when node_cap bit, so this is not the whole graph. */
  nodes_capped: boolean | null;
  /** True when chunk_cap bit, so distances are upper bounds. */
  chunks_truncated: boolean | null;
  /** The route's own verdict on its vectors. Authoritative over the name. */
  embedding_provider_simulated: boolean | null;
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

/*
 * THE COUNTS ARE FLAT ON THE WIRE, and reading them as nested was the worst
 * defect of this arc.
 *
 * GET /api/v1/knowledge/graph returns one flat object: items_total, items_ready,
 * items_embedded, nodes_capped and the rest sit beside `nodes` and `edges`, not
 * inside a `counts` member. This function was called as `readCounts(raw.counts)`,
 * so it hit `isRecord(undefined)` and returned null on EVERY real payload.
 *
 * An adversary measured the consequence on 2026-09-10 with a payload built by the
 * route's own assemble_graph: 12 ready items, items_embedded 0, ten node rows all
 * carrying embedded_chunk_count 0, and the edge query skipped entirely because
 * fewer than two nodes had a vector. The panel rendered:
 *
 *   "Embedded nodes, no pair close enough to connect."
 *
 * Nothing was embedded. No pair was ever compared. The panel asserted a
 * measurement over a query that did not run, on the one surface in this estate
 * whose entire justification is refusing to do that. Reproduced here before the
 * fix and again after it, with the same generated payload.
 *
 * The field names below were always right. Only the level was wrong, which is why
 * no test caught it: test_knowledge_graph.py pins the flat shape and this file's
 * fixtures were hand written nested, so both suites were green about different
 * payloads. That is why the guard added alongside this fix generates its payload
 * from assemble_graph instead of writing one by hand.
 */
function readCounts(value: unknown): GraphCounts | null {
  if (!isRecord(value)) return null;
  const total = finiteOrNull(value.items_total);
  const ready = finiteOrNull(value.items_ready);
  const embedded = finiteOrNull(value.items_embedded);
  // Every count absent means this is not a graph payload at all. One absent
  // count is a degraded payload the panel should report rather than refuse.
  if (total === null && ready === null && embedded === null) return null;
  return {
    items_total: total,
    items_ready: ready,
    items_embedded: embedded,
    items_unembedded: finiteOrNull(value.items_unembedded),
    items_simulated_embeddings: finiteOrNull(value.items_simulated_embeddings),
    edges_returned: finiteOrNull(value.edges_returned),
    edges_capped: boolOrNull(value.edges_capped),
    nodes_capped: boolOrNull(value.nodes_capped),
    chunks_truncated: boolOrNull(value.chunks_truncated),
    embedding_provider_simulated: boolOrNull(value.embedding_provider_simulated),
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
  // The counts live at the top level beside nodes and edges. Asking for a
  // `counts` member reported every real payload as missing its counts.
  if (readCounts(raw) === null) missingFields.push("counts");
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
      // embedded_chunk_count is what the route sends per node, and it is the
      // only thing that makes "embedded nodes" a statement of fact rather than
      // an assumption. `degree` is NOT sent by the route and never was: it is
      // derived below from the edges the payload carries, which is what degree
      // means. Reading a field the route does not send and then counting its
      // absence produced a warning on every successful read, which teaches a
      // reader to ignore the real ones.
      const embeddedChunks = finiteOrNull(row.embedded_chunk_count);
      nodes.push({
        id,
        title: textOrNull(row.title),
        source: textOrNull(row.source),
        created_at: textOrNull(row.created_at),
        embeddedChunks,
        degree: null,
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
      edges.push({
        source,
        target,
        distance,
        distanceIsUpperBound: boolOrNull(row.distance_is_upper_bound),
      });
    }
  }

  // Degree is a property of the edge list, so it is computed here rather than
  // trusted from the wire. A node the payload draws no edge to has degree 0,
  // which is a fact about this payload and not a missing value.
  const degrees = new Map<string, number>();
  for (const edge of edges) {
    degrees.set(edge.source, (degrees.get(edge.source) ?? 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) ?? 0) + 1);
  }
  for (const node of nodes) node.degree = degrees.get(node.id) ?? 0;

  // Only a node whose embedded chunk count the route did not state is unknown.
  nodesWithoutDegree = nodes.filter((node) => node.embeddedChunks === null).length;

  return {
    nodes,
    edges,
    counts: readCounts(raw),
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
 * THE FLAG DECIDES, NOT THE NAME. An earlier version of this function took only
 * the provider name and returned "real" for anything it did not recognise as a
 * fake. That was wrong in the one case a default launch actually produces.
 * `embedding_provider_identity` in app/services/knowledge_graph.py:196 reports
 * `embedding_provider: "unavailable"` with `embedding_provider_simulated: True`
 * when it cannot build a provider at all, and "unavailable" matches none of the
 * fake substrings, so it fell through to "real". Reading the name alone made a
 * hard provider failure render as verified semantic distance.
 *
 * It is not a rare path. `start-devon.sh` writes DEFAULT_AI_PROVIDER=cerebras,
 * `_embedding_provider` resolves through DEFAULT_AI_PROVIDER, and only mock and
 * openai implement embed at all (services/intelligence/providers/embeddings.py
 * :126 and :151 set those two names, and nothing else does). So a default launch
 * raises ProviderConfigError, the route reports "unavailable", and the old
 * function called it real.
 *
 * So the route's own flag is the primary input. It is the field the route
 * computes deliberately and fails CLOSED on: it is declared
 * `embedding_provider_simulated: bool = True` (knowledge_graph.py:162) and it
 * stays raised on the unavailable path even though no vector provenance is
 * known there.
 *
 * The name is kept as a PESSIMISTIC OVERRIDE only, never as a promotion. The
 * route derives the flag as `name == "mock"`, so a fake added later under some
 * other name would arrive with the flag lowered; the substring arms catch that.
 * A name the flag calls real but this function does not recognise reads
 * "unknown" rather than "real", which understates rather than overstates. The
 * cost of understating is a caution nobody needed. The cost of overstating is a
 * picture that looks like evidence.
 */

/**
 * Provider names that genuinely embed. Read off the source, not off settings:
 * `services/intelligence/providers/embeddings.py` sets `name = "mock"` at :126
 * and `name = "openai"` at :151, and those are the only two concrete providers,
 * so openai is the entire real set. "abstract" at :60 is the ABC's placeholder
 * and never reaches a payload. Adding a real provider means adding it here, and
 * until it is added its distances read "unknown", which is the safe direction.
 */
const REAL_EMBEDDING_PROVIDERS = new Set(["openai"]);

/** Names that say "not a real vector", for a fake added under a new name. */
const FAKE_NAME_MARKS = ["mock", "simulat", "fake", "stub", "dummy"];

export function classifyProvider(
  name: string | null | undefined,
  simulated: boolean | null | undefined,
): ProviderTrust {
  const value = (name ?? "").trim().toLowerCase();

  // 1. The route said the vectors are simulated. That is the answer, whatever
  //    the name is, because this flag is the field the route fails closed on.
  if (simulated === true) return "simulated";

  // 2. The name says fake even though the flag did not. Disagreement between
  //    the two resolves to the cautious reading rather than to the flag: the
  //    flag is only `name == "mock"`, so it cannot know about a new fake.
  if (FAKE_NAME_MARKS.some((mark) => value.includes(mark))) return "simulated";

  // 3. The route did not send the flag at all. Absent is not "real". A payload
  //    that omits the field is degraded, and a degraded payload must not be
  //    able to certify its own distances.
  if (simulated === null || simulated === undefined) return "unknown";

  // 4. The flag says real. Only a name known to actually embed earns "real";
  //    "", "unknown", "unavailable" and anything unrecognised read "unknown".
  if (REAL_EMBEDDING_PROVIDERS.has(value)) return "real";
  return "unknown";
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
  // Counts present and readable, and no node came back. Distinct from
  // "unsourced", which is the counts being absent: saying "no counts to explain
  // why" over counts that were read is the panel inventing its own blindness.
  | { kind: "no-nodes"; headline: string; detail: string }
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

  // `embedded === 0 && nodeCount > 0` USED TO BE A DISAGREEMENT CLAUSE HERE, and
  // it is not a disagreement at all. The route's node query selects every item
  // with status 'ready' whether or not it carries a vector, while items_embedded
  // counts only items with at least one non-null embedding. So ten ready nodes and
  // zero embedded is the ordinary "nothing has been embedded yet" state, and it was
  // being reported as the route contradicting itself. Worse, it stole the branch
  // below that says exactly the right thing, making `no-embeddings` unreachable
  // for the only payload that produces it.
  //
  // What remains are the two real contradictions: zero items with nodes returned,
  // and embedded items with no nodes at all.
  if (
    (total === 0 && nodeCount > 0) ||
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
    // Only claim the counts are absent when they ARE absent. This branch said
    // "no counts to explain why" over payloads whose counts were present and
    // readable, which is the panel inventing its own blindness.
    return counts === null
      ? {
          kind: "unsourced",
          headline: "No nodes, and no counts to explain why.",
          detail:
            "The route returned an empty node list and no counts, so this cannot tell an " +
            "empty corpus from a corpus with nothing embedded. Both are possible and " +
            "neither is shown as fact.",
        }
      : {
          kind: "no-nodes",
          headline: "The counts report items, and no node came back.",
          detail:
            `counts reports ${total ?? "an unstated number of"} items and ` +
            `${embedded ?? "an unstated number"} embedded, and the node list is empty. ` +
            "Nothing is drawn, and the counts are shown because they were read rather " +
            "than guessed.",
        };
  }

  if (parsed.edges.length === 0) {
    // "Every pair sits further apart than the threshold" is a claim about a
    // comparison, and it is only true if the comparison ran. The route skips the
    // edge query entirely unless at least two nodes carry a vector, so this
    // sentence used to assert a measurement over a query that never executed.
    // Now it counts the nodes that actually carry vectors and says which case
    // this is.
    const vectorBearing = parsed.nodes.filter(
      (node) => node.embeddedChunks !== null && node.embeddedChunks > 0,
    ).length;
    const unstated = parsed.nodes.filter((node) => node.embeddedChunks === null).length;

    if (unstated === nodeCount) {
      return {
        kind: "no-edges",
        headline: "No edges, and the nodes do not say whether they carry vectors.",
        detail:
          `${nodeCount} nodes came back with zero edges, and none of them stated an ` +
          "embedded chunk count. So this cannot tell an unembedded corpus from a corpus " +
          "whose pairs are all far apart, and neither is claimed.",
      };
    }
    if (vectorBearing < 2) {
      return {
        kind: "no-edges",
        headline: "Too few embedded nodes for any pair to compare.",
        detail:
          `${nodeCount} nodes came back and ${vectorBearing} of them carry a vector. A ` +
          "distance needs two, so the route did not run the edge query at all. This is a " +
          "pipeline state, and no claim is made about how far apart anything is.",
      };
    }
    return {
      kind: "no-edges",
      headline: "Embedded nodes, no pair close enough to connect.",
      detail:
        `${vectorBearing} of ${nodeCount} nodes carry a vector and zero edges came back. ` +
        `Every compared pair sits further apart than the threshold${threshold}, so this ` +
        "picture is edgeless because the comparison ran and found nothing near.",
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

/**
 * Whether the ring's radius actually encodes degree FOR THIS PAYLOAD.
 *
 * The layout above does pull well connected nodes inward: `radius` is
 * `outer * (1 - 0.3 * share)` where share is degree over the maximum degree. But
 * that collapses whenever every node has the SAME degree, and the commonest such
 * case is the one a new corpus produces: no edges at all, so every degree is 0,
 * so every share is 0, so every mark lands on one ring with only the parity
 * stagger between them.
 *
 * The screen reader description used to claim "most connected items pulled
 * inward" unconditionally. Over a real ten node payload with no edges that
 * sentence described a layout the picture did not have, and the description is
 * the whole picture for anyone using a screen reader. So the claim is now
 * conditional on this function, and this function is exported so a check can
 * assert the two move together instead of a reviewer trusting they do.
 *
 * Returns false for an empty list: nothing is encoded when nothing is placed.
 */
export function radiusEncodesDegree(nodes: GraphNode[]): boolean {
  if (nodes.length === 0) return false;
  let max = 0;
  let min = Number.POSITIVE_INFINITY;
  for (const node of nodes) {
    const degree = node.degree ?? 0;
    if (degree > max) max = degree;
    if (degree < min) min = degree;
  }
  // max > 0 rules out the all-zero case; min < max rules out a regular graph
  // where every node has the same nonzero degree and the radius is again flat.
  return max > 0 && min < max;
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

    // nodes_capped is a DIFFERENT truncation from edges_capped and it was parsed
    // and then never read. An edge cap hides relationships between items that
    // are drawn; a node cap hides whole items, so pairs can be missing because
    // one end was never a candidate. Saying only the first would let a reader
    // believe every item is on the canvas.
    if (counts.nodes_capped === true) {
      notes.push(
        "The route capped the node list, so whole items are missing from this canvas and any pair with one end outside the cap was never compared.",
      );
    } else if (counts.nodes_capped === null) {
      notes.push(
        "The route did not say whether it capped the node list, so this canvas cannot be claimed to hold every item.",
      );
    }

    // chunks_truncated is the reason a distance can be a ceiling rather than a
    // measurement, and it was also parsed and never read. The per-edge flag
    // below marks WHICH edges; this says the corpus-level fact once.
    if (counts.chunks_truncated === true) {
      notes.push(
        "At least one item had more chunks than the route compares, so some pairs were scored on part of their text. Those distances are ceilings: the true distance can only be smaller, never larger.",
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

  // Which edges are ceilings rather than measurements. Counted from the edges
  // actually parsed, so this cannot claim more than the payload carries.
  const ceilings = graph.edges.filter((edge) => edge.distanceIsUpperBound === true).length;
  if (ceilings > 0) {
    notes.push(
      `${ceilings} of the ${graph.edges.length} drawn edge${graph.edges.length === 1 ? "" : "s"} ` +
        `report a distance that is an upper bound, not a measurement, because an item at one end had more chunks than the route compares. Those two items may be nearer than they are drawn.`,
    );
  }
  const unstatedBounds = graph.edges.filter((edge) => edge.distanceIsUpperBound === null).length;
  if (unstatedBounds > 0 && unstatedBounds === graph.edges.length) {
    notes.push(
      "The route did not say, for any edge, whether its distance is a measurement or an upper bound, so no distance here can be treated as exact.",
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
