"""
GET /knowledge/graph: the real edge graph over the caller's knowledge.

Read only, authenticated exactly like its neighbours in
`app/api/v1/knowledge.py`. It reads vectors that are already stored, embeds
nothing, and writes nothing, so it needs no approval gate.

Why this lives in its own module rather than beside the other knowledge
routes: `app/api/v1/knowledge.py:183` declares `GET /knowledge/{item_id}`,
which matches the literal path segment "graph" just as happily as it matches a
uuid. FastAPI resolves in registration order, so this router MUST be included
BEFORE that one or every graph request is served as a lookup for an item named
"graph" and comes back 404. `test_knowledge_graph.py` demonstrates that
shadowing against a real app rather than asserting it in prose, and checks the
composed v1 router for the ordering once this router is registered there.

The honesty fields are the point of the payload, not decoration. A panel
reading this needs to tell three states apart that all render as an empty
canvas: nothing ingested (`items_total` is 0), ingested but not embedded
(`items_unembedded` is high), and embedded but nothing within `max_distance`.
And `embedding_provider` decides whether the distances mean anything at all:
with the mock provider they are exact measurements of deterministic fake
vectors, so `embedding_provider_simulated` is the flag that tells the panel to
refuse to present them as real.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services.knowledge_graph import (
    DEFAULT_CHUNK_CAP,
    DEFAULT_EDGE_CAP,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_NODE_CAP,
    MAX_CHUNK_CAP,
    MAX_EDGE_CAP,
    MAX_MAX_DISTANCE,
    MAX_NODE_CAP,
    build_knowledge_graph,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


class KnowledgeGraphNode(BaseModel):
    id: str
    title: str
    source: str
    source_type: str
    chunk_count: int
    embedded_chunk_count: int
    simulated_embeddings: bool
    chunks_considered: int
    chunks_truncated: bool


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    # Cosine distance from pgvector's <=> operator. Smaller is nearer. Not a
    # score, not a percentage: the database measured a distance.
    distance: float
    distance_is_upper_bound: bool


class KnowledgeGraphResponse(BaseModel):
    nodes: List[KnowledgeGraphNode]
    edges: List[KnowledgeGraphEdge]

    items_total: int
    items_ready: int
    items_embedded: int
    items_unembedded: int
    items_simulated_embeddings: int

    nodes_returned: int
    nodes_capped: bool
    node_cap: int

    edges_returned: int
    edges_capped: bool
    edge_cap: int

    chunk_cap: int
    chunks_considered: int
    chunks_truncated: bool

    max_distance: float

    embedding_provider: str
    embedding_model: str
    embedding_provider_simulated: bool
    embedding_provider_error: Optional[str] = None


@router.get("/graph", response_model=KnowledgeGraphResponse)
async def knowledge_graph(
    current_user: CurrentUser,
    project_id: Optional[str] = None,
    node_cap: int = Query(DEFAULT_NODE_CAP, ge=1, le=MAX_NODE_CAP),
    edge_cap: int = Query(DEFAULT_EDGE_CAP, ge=1, le=MAX_EDGE_CAP),
    chunk_cap: int = Query(DEFAULT_CHUNK_CAP, ge=1, le=MAX_CHUNK_CAP),
    max_distance: float = Query(DEFAULT_MAX_DISTANCE, ge=0.0, le=MAX_MAX_DISTANCE),
    db: AsyncSession = Depends(get_db),
):
    """Nodes and measured edges for the caller's ready knowledge items.

    Every cap is validated here and clamped again inside the service, because
    the service is also callable directly and a bound that only exists at the
    HTTP edge is not a bound.
    """
    graph = await build_knowledge_graph(
        db,
        owner_id=current_user.id,
        project_id=project_id,
        node_cap=node_cap,
        edge_cap=edge_cap,
        chunk_cap=chunk_cap,
        max_distance=max_distance,
    )
    return KnowledgeGraphResponse(**graph.as_dict())
