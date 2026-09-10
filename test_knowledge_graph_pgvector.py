"""
The graph's edge query, executed against real pgvector.

WHY THIS FILE EXISTS SEPARATELY

test_knowledge_graph.py is 42 tests and every one of them is offline: it proves
the assembly, the caps, the payload shape and the router ordering without a
database. That is the right lane for those, and it leaves the load bearing claim
of the whole piece unproven, because the claim is "every edge is a measured
pgvector cosine distance" and the distance comes out of raw SQL:

    MIN(a.embedding <=> b.embedding) AS distance

`<=>` is a pgvector operator. Nothing in an offline suite can tell you whether
that statement parses, whether `ANY(CAST(:node_ids AS uuid[]))` binds, whether
the `a.item_id < b.item_id` self join emits each pair once, or whether the number
that comes back is cosine distance rather than something else. CLAUDE.md's line
is "green is not correct"; forty two offline passes over a query no database has
ever run is exactly that shape.

So this file runs the real function against the real cluster with vectors whose
cosine distances are known by hand, and checks the arithmetic that comes back.

WHY THE VECTORS ARE WHAT THEY ARE

Cosine distance is 1 minus cosine similarity. With 1536 dimensions the fixtures
put all the weight in the first two so the expected answers are exact:

    A = (1, 0, 0, ...)        B = (1, 0, 0, ...)     identical, distance 0
    C = (0, 1, 0, ...)        orthogonal to A,       distance 1

An orthogonal pair and an identical pair bracket the operator's whole range, so a
query returning L2 distance, inner product, or similarity instead of cosine
distance cannot satisfy both at once.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.services.knowledge_graph import build_knowledge_graph

DIMS = 1536


def _vector(*leading: float) -> str:
    """A pgvector literal: the leading components, then zeros."""
    values = list(leading) + [0.0] * (DIMS - len(leading))
    assert len(values) == DIMS
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"graph-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


async def _item(db, owner_id: str, title: str, vectors: list[str]) -> str:
    """A ready knowledge item carrying one embedding row per vector."""
    item_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO knowledge_items"
            " (id, owner_id, title, source_type, source, status, metadata)"
            " VALUES (CAST(:id AS uuid), CAST(:owner AS uuid), :title, 'manual',"
            " 'test', 'ready', '{}'::jsonb)"
        ),
        {"id": item_id, "owner": owner_id, "title": title},
    )
    for index, literal in enumerate(vectors):
        await db.execute(
            text(
                "INSERT INTO embeddings"
                " (id, knowledge_item_id, chunk_index, content, embedding)"
                " VALUES (CAST(:id AS uuid), CAST(:item AS uuid), :ix, :content,"
                " CAST(:vec AS vector))"
            ),
            {
                "id": str(uuid.uuid4()),
                "item": item_id,
                "ix": index,
                "content": f"{title} chunk {index}",
                "vec": literal,
            },
        )
    return item_id


@pytest.mark.asyncio
async def test_the_edge_query_returns_real_cosine_distance(db_session):
    """The whole claim of the piece, executed rather than asserted."""
    owner = await _owner(db_session)
    a = await _item(db_session, owner, "A", [_vector(1.0, 0.0)])
    b = await _item(db_session, owner, "B", [_vector(1.0, 0.0)])
    c = await _item(db_session, owner, "C", [_vector(0.0, 1.0)])
    await db_session.flush()

    graph = await build_knowledge_graph(db_session, owner_id=owner)
    payload = graph.as_dict()

    ids = {node["id"] for node in payload["nodes"]}
    assert ids == {a, b, c}, "every ready item carrying a vector must be a node"

    edges = {
        frozenset((edge["source"], edge["target"])): edge["distance"]
        for edge in payload["edges"]
    }

    # Identical vectors: cosine distance 0. This is the pair that a query
    # returning similarity instead of distance would report as 1.
    assert frozenset((a, b)) in edges, "the identical pair produced no edge"
    assert edges[frozenset((a, b))] == pytest.approx(0.0, abs=1e-6)

    # Orthogonal vectors: cosine distance exactly 1. An L2 distance over these
    # unit vectors would be sqrt(2), which this refuses.
    orthogonal = [
        edges[key] for key in (frozenset((a, c)), frozenset((b, c))) if key in edges
    ]
    for distance in orthogonal:
        assert distance == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_each_unordered_pair_appears_exactly_once(db_session):
    """`a.item_id < b.item_id` has to drop self pairs and mirrored duplicates."""
    owner = await _owner(db_session)
    await _item(db_session, owner, "A", [_vector(1.0, 0.0)])
    await _item(db_session, owner, "B", [_vector(0.9, 0.1)])
    await _item(db_session, owner, "C", [_vector(0.8, 0.2)])
    await db_session.flush()

    payload = (await build_knowledge_graph(db_session, owner_id=owner)).as_dict()
    pairs = [frozenset((e["source"], e["target"])) for e in payload["edges"]]

    assert all(len(p) == 2 for p in pairs), "an item was joined against itself"
    assert len(pairs) == len(set(pairs)), "a pair came back mirrored as well"
    assert len(pairs) == 3, f"three items make three unordered pairs, got {len(pairs)}"


@pytest.mark.asyncio
async def test_the_distance_is_the_minimum_over_chunk_pairs(db_session):
    """MIN over the group is the closest point of contact, not an average."""
    owner = await _owner(db_session)
    # A carries one chunk far from B's, and one chunk identical to B's. The
    # closest contact is 0, and any averaging would report something larger.
    a = await _item(db_session, owner, "A", [_vector(0.0, 1.0), _vector(1.0, 0.0)])
    b = await _item(db_session, owner, "B", [_vector(1.0, 0.0)])
    await db_session.flush()

    payload = (await build_knowledge_graph(db_session, owner_id=owner)).as_dict()
    edges = {
        frozenset((e["source"], e["target"])): e["distance"] for e in payload["edges"]
    }
    assert frozenset((a, b)) in edges
    assert edges[frozenset((a, b))] == pytest.approx(0.0, abs=1e-6), (
        "the edge reported more than the closest chunk pair, so it is an average "
        "or a first match rather than the MIN the SQL claims"
    )


@pytest.mark.asyncio
async def test_an_item_with_no_vector_is_a_node_and_carries_no_edge(db_session):
    """A dot with no vector must not silently acquire a relationship."""
    owner = await _owner(db_session)
    a = await _item(db_session, owner, "A", [_vector(1.0, 0.0)])
    b = await _item(db_session, owner, "B", [_vector(1.0, 0.0)])
    lonely = str(uuid.uuid4())
    await db_session.execute(
        text(
            "INSERT INTO knowledge_items"
            " (id, owner_id, title, source_type, source, status, metadata)"
            " VALUES (CAST(:id AS uuid), CAST(:owner AS uuid), 'Lonely', 'manual',"
            " 'test', 'ready', '{}'::jsonb)"
        ),
        {"id": lonely, "owner": owner},
    )
    await db_session.flush()

    payload = (await build_knowledge_graph(db_session, owner_id=owner)).as_dict()
    assert lonely in {n["id"] for n in payload["nodes"]}
    touched = {e["source"] for e in payload["edges"]} | {
        e["target"] for e in payload["edges"]
    }
    assert lonely not in touched, "an item with no embedding was given an edge"
    assert frozenset((a, b)) in {
        frozenset((e["source"], e["target"])) for e in payload["edges"]
    }


@pytest.mark.asyncio
async def test_the_graph_is_scoped_to_its_owner(db_session):
    """Another owner's items must not appear as nodes or edges."""
    mine = await _owner(db_session)
    theirs = await _owner(db_session)
    a = await _item(db_session, mine, "Mine A", [_vector(1.0, 0.0)])
    b = await _item(db_session, mine, "Mine B", [_vector(1.0, 0.0)])
    stranger = await _item(db_session, theirs, "Theirs", [_vector(1.0, 0.0)])
    await db_session.flush()

    payload = (await build_knowledge_graph(db_session, owner_id=mine)).as_dict()
    assert {n["id"] for n in payload["nodes"]} == {a, b}
    assert stranger not in {n["id"] for n in payload["nodes"]}
    touched = {e["source"] for e in payload["edges"]} | {
        e["target"] for e in payload["edges"]
    }
    assert stranger not in touched
