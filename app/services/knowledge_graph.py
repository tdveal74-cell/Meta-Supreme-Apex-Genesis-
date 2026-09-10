"""
The measured knowledge graph: real nodes, real edges, nothing invented.

Why this module exists. `apps/web/components/mind/KnowledgePanel.tsx:10-12`
refused to draw a graph, and the refusal was correct at the time: no route
exposed edges between the indexes, so any graph would have been a picture of
something nobody measured. This module is the measurement, so that panel can
stop refusing.

What an edge is, precisely. An item holds many chunks, and every chunk carries
its own vector. The item-to-item edge published here is the MINIMUM cosine
distance over all considered chunk pairs of the two items, which is the honest
closest point of contact between two documents. It is not a mean (a mean is
dominated by the unrelated bulk of two long documents) and it is not a
similarity percentage (the database returns a distance, and dressing a
distance up as confidence invents precision nobody measured). Smaller is
nearer.

Cost, and why every cap is reported. The pair scan is O(n squared) in the
number of chunks considered, so three caps bound it: `node_cap` bounds the
items, `chunk_cap` bounds the chunks taken per item, and `edge_cap` bounds the
rows returned. Each one that actually bit is reported in the payload. Silent
truncation reads as "that is the whole graph", which is the same class of
error as inventing edges: the reader is left believing something that was
never measured.

One consequence of `chunk_cap` that the payload states rather than hides: when
an item's chunks are truncated, its edge distance is the minimum over the
chunks that were considered, so it is an UPPER BOUND on the true minimum. The
true closest pair may have been left out of the scan.

Scoping matches `app.services.knowledge.search_knowledge` exactly (owner_id,
status = 'ready', optional project filter). A graph that showed more than
search can reach would be a wider claim than the one the estate already makes.

Read only. Nothing here writes, and nothing here embeds: the vectors are
already in the table.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caps
#
# Defaults chosen so the worst case stays reviewable: 60 nodes at 40 chunks
# each is 2400 vectors, so the self join compares at most 2400 * 2399 / 2,
# about 2.9 million pairs of 1536-dimension vectors. That is the ceiling, not
# the expectation, and it is why the maxima below are hard.
# ---------------------------------------------------------------------------

DEFAULT_NODE_CAP = 60
MAX_NODE_CAP = 200

DEFAULT_EDGE_CAP = 400
MAX_EDGE_CAP = 2000

DEFAULT_CHUNK_CAP = 40
MAX_CHUNK_CAP = 200

# Cosine distance, so 0.0 is identical and 2.0 is opposite. 0.65 keeps the
# graph readable without asserting that everything beyond it is unrelated:
# the cut is reported in the payload as `max_distance`, so a caller who wants
# the long tail can ask for it.
DEFAULT_MAX_DISTANCE = 0.65
MAX_MAX_DISTANCE = 2.0


@dataclass
class GraphNode:
    """One ready knowledge item. Chunk counts are measured, not estimated."""

    id: str
    title: str
    source: str
    source_type: str
    chunk_count: int
    embedded_chunk_count: int
    simulated_embeddings: bool
    chunks_considered: int
    chunks_truncated: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "source_type": self.source_type,
            "chunk_count": self.chunk_count,
            "embedded_chunk_count": self.embedded_chunk_count,
            "simulated_embeddings": self.simulated_embeddings,
            "chunks_considered": self.chunks_considered,
            "chunks_truncated": self.chunks_truncated,
        }


@dataclass
class GraphEdge:
    """A measured cosine distance between the closest chunks of two items."""

    source: str
    target: str
    distance: float
    # True when either endpoint had its chunks truncated by `chunk_cap`, in
    # which case `distance` is an upper bound on the true minimum rather than
    # the minimum itself. The panel needs to be able to say so.
    distance_is_upper_bound: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "distance": self.distance,
            "distance_is_upper_bound": self.distance_is_upper_bound,
        }


@dataclass
class KnowledgeGraph:
    """Nodes, edges, and the honesty fields that let a panel read them."""

    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    items_total: int = 0
    items_ready: int = 0
    items_embedded: int = 0
    items_unembedded: int = 0
    items_simulated_embeddings: int = 0

    nodes_returned: int = 0
    nodes_capped: bool = False
    node_cap: int = DEFAULT_NODE_CAP

    edges_returned: int = 0
    edges_capped: bool = False
    edge_cap: int = DEFAULT_EDGE_CAP

    chunk_cap: int = DEFAULT_CHUNK_CAP
    chunks_considered: int = 0
    chunks_truncated: bool = False

    max_distance: float = DEFAULT_MAX_DISTANCE

    embedding_provider: str = "unknown"
    embedding_model: str = "unknown"
    # Load bearing. With the mock provider the vectors are deterministic fakes
    # built from hashed bag-of-words (services/intelligence/providers/
    # embeddings.py:108-120), so every distance below is a real measurement of
    # a fake quantity. A panel that presents these as semantic distance is
    # lying on this module's behalf, so the flag travels with the data.
    embedding_provider_simulated: bool = True
    embedding_provider_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.as_dict() for n in self.nodes],
            "edges": [e.as_dict() for e in self.edges],
            "items_total": self.items_total,
            "items_ready": self.items_ready,
            "items_embedded": self.items_embedded,
            "items_unembedded": self.items_unembedded,
            "items_simulated_embeddings": self.items_simulated_embeddings,
            "nodes_returned": self.nodes_returned,
            "nodes_capped": self.nodes_capped,
            "node_cap": self.node_cap,
            "edges_returned": self.edges_returned,
            "edges_capped": self.edges_capped,
            "edge_cap": self.edge_cap,
            "chunk_cap": self.chunk_cap,
            "chunks_considered": self.chunks_considered,
            "chunks_truncated": self.chunks_truncated,
            "max_distance": self.max_distance,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_provider_simulated": self.embedding_provider_simulated,
            "embedding_provider_error": self.embedding_provider_error,
        }


# ---------------------------------------------------------------------------
# The provider, read honestly
# ---------------------------------------------------------------------------


def embedding_provider_identity() -> Dict[str, Any]:
    """Name the provider that actually embeds in this process.

    Deliberately delegates to `app.services.knowledge._embedding_provider`,
    private name and all, rather than re-reading the settings here. That
    function is the single place where the provider for this lane is resolved
    (app/services/knowledge.py:34-48), and it resolves through
    `settings.DEFAULT_AI_PROVIDER`, not `settings.EMBEDDING_PROVIDER`, because
    `DEFAULT_EMBEDDING_PROVIDER` is not a field on settings. Verified by
    running it: with DEFAULT_AI_PROVIDER=mock it returns the mock provider,
    and with DEFAULT_AI_PROVIDER=anthropic it raises ProviderConfigError,
    since only mock and openai embed. Re-deriving that expression here would
    let the two drift, and a drifted provider name is exactly the field a
    panel trusts when it decides whether the distances are real.

    Construction has no side effects: MeteredEmbeddingProvider.__init__ copies
    fields and does not touch the tenant ledger (app/services/
    provider_usage.py:276-283). Nothing is embedded here.

    A provider that cannot be built is reported, not raised: the graph itself
    is still a true reading of the stored vectors, and refusing the whole
    payload would hide it.
    """
    from app.services.knowledge import _embedding_provider

    try:
        provider = _embedding_provider()
    except Exception as exc:  # noqa: BLE001 - report it, never guess a name
        logger.warning("knowledge graph could not build the embedding provider: %s", exc)
        return {
            "embedding_provider": "unavailable",
            "embedding_model": "unavailable",
            # Unknown provenance is not the same as known real, so the
            # simulated flag stays raised. A panel that sees "unavailable"
            # must not treat the distances as verified semantic distance.
            "embedding_provider_simulated": True,
            "embedding_provider_error": str(exc)[:500],
        }

    name = getattr(provider, "name", "unknown")
    return {
        "embedding_provider": name,
        "embedding_model": getattr(provider, "default_model", "unknown"),
        "embedding_provider_simulated": name == "mock",
        "embedding_provider_error": None,
    }


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def clamp_caps(
    *,
    node_cap: Optional[int] = None,
    edge_cap: Optional[int] = None,
    chunk_cap: Optional[int] = None,
    max_distance: Optional[float] = None,
) -> Dict[str, Any]:
    """Clamp the caps into their hard range. Pure, so a test can pin it."""
    resolved_node = DEFAULT_NODE_CAP if node_cap is None else int(node_cap)
    resolved_edge = DEFAULT_EDGE_CAP if edge_cap is None else int(edge_cap)
    resolved_chunk = DEFAULT_CHUNK_CAP if chunk_cap is None else int(chunk_cap)
    resolved_distance = (
        DEFAULT_MAX_DISTANCE if max_distance is None else float(max_distance)
    )
    return {
        "node_cap": max(1, min(resolved_node, MAX_NODE_CAP)),
        "edge_cap": max(1, min(resolved_edge, MAX_EDGE_CAP)),
        "chunk_cap": max(1, min(resolved_chunk, MAX_CHUNK_CAP)),
        "max_distance": max(0.0, min(resolved_distance, MAX_MAX_DISTANCE)),
    }


def _uuid_array_literal(ids: Sequence[str]) -> str:
    """Render ids as a Postgres uuid[] literal, refusing anything that is not one.

    The ids come straight back out of the node query, so this is belt and
    braces rather than a live injection path, and the literal is interpolated
    into no SQL at all: it is bound as a single parameter and CAST to uuid[].
    Validating each element here means a malformed id fails loudly next to the
    code that built it instead of as a Postgres cast error at the driver.
    """
    for candidate in ids:
        uuid.UUID(str(candidate))
    return "{" + ",".join(str(i) for i in ids) + "}"


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# Corpus census. Scoped like search_knowledge (app/services/knowledge.py:96-99)
# except that the status filter is expressed as a FILTER clause instead of a
# WHERE, because the whole point of these numbers is to let a panel tell an
# empty graph apart from a corpus that is present but not embedded yet.
_COUNTS_SQL = text(
    """
    SELECT
        COUNT(*) AS items_total,
        COUNT(*) FILTER (WHERE ki.status = 'ready') AS items_ready,
        COUNT(*) FILTER (
            WHERE ki.status = 'ready'
              AND EXISTS (
                  SELECT 1 FROM embeddings e
                  WHERE e.knowledge_item_id = ki.id
                    AND e.embedding IS NOT NULL
              )
        ) AS items_embedded,
        COUNT(*) FILTER (
            WHERE ki.status = 'ready'
              AND ki.metadata ->> 'simulated_embeddings' = 'true'
        ) AS items_simulated
    FROM knowledge_items ki
    WHERE ki.owner_id = :owner_id
      AND (CAST(:project_id AS uuid) IS NULL
           OR ki.project_id = CAST(:project_id AS uuid))
    """
)

# Nodes. Ordered by embedded chunk count first so that, when node_cap bites,
# what it drops is the items that could carry no edge at all: an item with
# zero embedded chunks has no vector to compare and would arrive as an
# isolated dot. Ties break on recency then id, so the ordering is total and
# the same request twice returns the same nodes.
_NODES_SQL = text(
    """
    SELECT
        ki.id AS id,
        ki.title AS title,
        ki.source AS source,
        ki.source_type AS source_type,
        COUNT(e.id) AS chunk_count,
        COUNT(e.embedding) AS embedded_chunk_count,
        (ki.metadata ->> 'simulated_embeddings' = 'true') AS simulated_embeddings
    FROM knowledge_items ki
    LEFT JOIN embeddings e ON e.knowledge_item_id = ki.id
    WHERE ki.owner_id = :owner_id
      AND ki.status = 'ready'
      AND (CAST(:project_id AS uuid) IS NULL
           OR ki.project_id = CAST(:project_id AS uuid))
    GROUP BY ki.id, ki.title, ki.source, ki.source_type, ki.metadata, ki.created_at
    ORDER BY COUNT(e.embedding) DESC, ki.created_at DESC, ki.id
    LIMIT :node_probe
    """
)

# Edges. The pgvector cosine operator is <=>, the same operator the search
# route already uses (app/services/knowledge.py:93). MIN over the pair group
# is the closest point of contact between the two items.
#
# `a.item_id < b.item_id` does three jobs at once: it drops the self pairs, it
# emits each unordered pair exactly once instead of twice, and it halves the
# scan. Node ids are passed in explicitly rather than re-selected here so that
# no edge can name a node the payload does not carry, which two separate
# statements against a moving table could otherwise produce.
_EDGES_SQL = text(
    """
    WITH ranked AS (
        SELECT
            e.knowledge_item_id AS item_id,
            e.embedding AS embedding,
            ROW_NUMBER() OVER (
                PARTITION BY e.knowledge_item_id ORDER BY e.chunk_index
            ) AS rn
        FROM embeddings e
        WHERE e.knowledge_item_id = ANY(CAST(:node_ids AS uuid[]))
          AND e.embedding IS NOT NULL
    ),
    chunks AS (
        SELECT item_id, embedding FROM ranked WHERE rn <= :chunk_cap
    )
    SELECT
        a.item_id AS source_id,
        b.item_id AS target_id,
        MIN(a.embedding <=> b.embedding) AS distance
    FROM chunks a
    JOIN chunks b ON a.item_id < b.item_id
    GROUP BY a.item_id, b.item_id
    HAVING MIN(a.embedding <=> b.embedding) <= :max_distance
    ORDER BY distance ASC, source_id, target_id
    LIMIT :edge_probe
    """
)


# ---------------------------------------------------------------------------
# Assembly, pure
# ---------------------------------------------------------------------------


def assemble_graph(
    *,
    counts: Mapping[str, Any],
    node_rows: Sequence[Mapping[str, Any]],
    edge_rows: Sequence[Mapping[str, Any]],
    node_cap: int,
    edge_cap: int,
    chunk_cap: int,
    max_distance: float,
    provider: Mapping[str, Any],
) -> KnowledgeGraph:
    """Turn raw rows into the payload. No database, no clock, no provider call.

    `node_rows` and `edge_rows` are probe reads of cap + 1 rows. Receiving the
    extra row is how a cap is known to have bitten, and the extra row is
    dropped here. Reporting "capped" from the request parameter instead would
    flag a graph that merely happened to be exactly cap sized.
    """
    nodes_capped = len(node_rows) > node_cap
    kept_node_rows = list(node_rows[:node_cap])

    nodes: List[GraphNode] = []
    chunks_considered = 0
    any_truncated = False
    truncated_ids = set()

    for row in kept_node_rows:
        embedded = int(row.get("embedded_chunk_count") or 0)
        considered = min(embedded, chunk_cap)
        truncated = embedded > chunk_cap
        chunks_considered += considered
        node_id = str(row["id"])
        if truncated:
            any_truncated = True
            truncated_ids.add(node_id)
        nodes.append(
            GraphNode(
                id=node_id,
                title=(row.get("title") or "Untitled"),
                # `source` is the connector provenance column and it is
                # nullable, falling back to source_type exactly as
                # app/models/knowledge.py:35-36 documents.
                source=(row.get("source") or row.get("source_type") or "manual"),
                source_type=(row.get("source_type") or "manual"),
                chunk_count=int(row.get("chunk_count") or 0),
                embedded_chunk_count=embedded,
                simulated_embeddings=bool(row.get("simulated_embeddings")),
                chunks_considered=considered,
                chunks_truncated=truncated,
            )
        )

    kept_ids = {n.id for n in nodes}

    edges_capped = len(edge_rows) > edge_cap
    edges: List[GraphEdge] = []
    seen_pairs = set()
    for row in edge_rows[:edge_cap]:
        source_id = str(row["source_id"])
        target_id = str(row["target_id"])
        # An edge naming a node the payload does not carry would draw a line
        # to nowhere. It should be impossible, since the edge query is handed
        # the kept ids, so drop it loudly rather than shipping it.
        if source_id not in kept_ids or target_id not in kept_ids:
            logger.warning(
                "knowledge graph dropped an edge outside the node set: %s to %s",
                source_id,
                target_id,
            )
            continue
        # The graph is undirected and an item is not related to itself. The
        # SQL predicate `a.item_id < b.item_id` already guarantees both, but
        # that guarantee cannot be tested without a cluster, so the invariant
        # is enforced here too: loosening the predicate to `<>` would
        # otherwise add a self loop per item and a mirrored duplicate of every
        # edge, doubling the drawn graph with nothing measured behind it.
        # Rows arrive ordered by distance ascending, so the first sighting of
        # a pair is its minimum and later sightings add nothing.
        if source_id == target_id:
            logger.warning("knowledge graph dropped a self pair: %s", source_id)
            continue
        pair = (source_id, target_id) if source_id < target_id else (target_id, source_id)
        if pair in seen_pairs:
            logger.warning(
                "knowledge graph dropped a repeated pair: %s to %s", source_id, target_id
            )
            continue
        seen_pairs.add(pair)
        edges.append(
            GraphEdge(
                source=source_id,
                target=target_id,
                distance=float(row["distance"]),
                distance_is_upper_bound=(
                    source_id in truncated_ids or target_id in truncated_ids
                ),
            )
        )

    items_ready = int(counts.get("items_ready") or 0)
    items_embedded = int(counts.get("items_embedded") or 0)

    return KnowledgeGraph(
        nodes=nodes,
        edges=edges,
        items_total=int(counts.get("items_total") or 0),
        items_ready=items_ready,
        items_embedded=items_embedded,
        # Subtraction, not a fourth query: a ready item either has a vector or
        # does not. Floored at zero so a snapshot skew between the counts
        # cannot publish a negative count.
        items_unembedded=max(0, items_ready - items_embedded),
        items_simulated_embeddings=int(counts.get("items_simulated") or 0),
        nodes_returned=len(nodes),
        nodes_capped=nodes_capped,
        node_cap=node_cap,
        edges_returned=len(edges),
        edges_capped=edges_capped,
        edge_cap=edge_cap,
        chunk_cap=chunk_cap,
        chunks_considered=chunks_considered,
        chunks_truncated=any_truncated,
        max_distance=max_distance,
        embedding_provider=str(provider.get("embedding_provider") or "unknown"),
        embedding_model=str(provider.get("embedding_model") or "unknown"),
        embedding_provider_simulated=bool(
            provider.get("embedding_provider_simulated", True)
        ),
        embedding_provider_error=provider.get("embedding_provider_error"),
    )


# ---------------------------------------------------------------------------
# The read
# ---------------------------------------------------------------------------


async def build_knowledge_graph(
    db: AsyncSession,
    *,
    owner_id: str,
    project_id: Optional[str] = None,
    node_cap: Optional[int] = None,
    edge_cap: Optional[int] = None,
    chunk_cap: Optional[int] = None,
    max_distance: Optional[float] = None,
) -> KnowledgeGraph:
    """Read the graph. Three SELECTs, no writes, no embedding call.

    The edge query is skipped entirely when fewer than two nodes carry a
    vector, because a self join over one item's chunks can only produce the
    empty set and there is no reason to pay for it.
    """
    caps = clamp_caps(
        node_cap=node_cap,
        edge_cap=edge_cap,
        chunk_cap=chunk_cap,
        max_distance=max_distance,
    )
    params = {"owner_id": owner_id, "project_id": project_id}

    counts_result = await db.execute(_COUNTS_SQL, params)
    counts = counts_result.mappings().one()

    nodes_result = await db.execute(
        _NODES_SQL, {**params, "node_probe": caps["node_cap"] + 1}
    )
    node_rows = list(nodes_result.mappings().all())

    kept = node_rows[: caps["node_cap"]]
    vector_bearing = [
        str(row["id"]) for row in kept if int(row.get("embedded_chunk_count") or 0) > 0
    ]

    edge_rows: List[Mapping[str, Any]] = []
    if len(vector_bearing) >= 2:
        edges_result = await db.execute(
            _EDGES_SQL,
            {
                "node_ids": _uuid_array_literal(vector_bearing),
                "chunk_cap": caps["chunk_cap"],
                "max_distance": caps["max_distance"],
                "edge_probe": caps["edge_cap"] + 1,
            },
        )
        edge_rows = list(edges_result.mappings().all())

    return assemble_graph(
        counts=counts,
        node_rows=node_rows,
        edge_rows=edge_rows,
        node_cap=caps["node_cap"],
        edge_cap=caps["edge_cap"],
        chunk_cap=caps["chunk_cap"],
        max_distance=caps["max_distance"],
        provider=embedding_provider_identity(),
    )
