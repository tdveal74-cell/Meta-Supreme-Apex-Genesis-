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

AND THE FIRST VERSION OF THIS FILE DID NOT ACTUALLY CHECK THAT.

A critic found it on 2026-09-10, in the file written to demonstrate that green is
not correct. The orthogonal pair sits at distance 1.0, `DEFAULT_MAX_DISTANCE` is
0.65, and the edge query ends `HAVING MIN(...) <= :max_distance`. So the route
filtered the orthogonal pair out before the test ever saw it, `orthogonal` was an
empty list, `for distance in orthogonal:` never executed once, and the only
distance this file asserted was 0.0 for the identical pair. Zero is the identity
for cosine and for L2 alike, so substituting the L2 operator `<->` for `<=>`
passed all five tests. Measured, both halves: a probe printing
`len(orthogonal)` printed 0 on unmutated source, and the L2 substitution
returned `5 passed`.

Two changes stop it coming back. Every graph read that wants the orthogonal pair
now passes `max_distance=1.5`, above 1.0 and inside `MAX_MAX_DISTANCE` of 2.0.
And the count is asserted BEFORE the loop, so an empty list fails loudly instead
of passing silently. A loop over a possibly-empty collection is not an assertion,
and this file is the reason to say that out loud.
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

    # max_distance above 1.0, or HAVING drops the orthogonal pair and the
    # assertions below become vacuous. That is exactly what happened.
    graph = await build_knowledge_graph(db_session, owner_id=owner, max_distance=1.5)
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
    assert len(orthogonal) == 2, (
        f"expected both orthogonal pairs as edges, got {len(orthogonal)}. A loop over "
        "an empty list asserts nothing, and this file passed for a day because of it"
    )
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
async def test_the_self_join_predicate_is_what_drops_self_and_mirrored_pairs(db_session):
    """The predicate's job, tested where the Python backstop cannot hide it.

    `a.item_id < b.item_id` is documented as doing three jobs: drop self pairs,
    emit each unordered pair once, and halve the scan. An adversary changed it to
    `<=` and to `!=` on 2026-09-10 and all forty seven tests passed, because
    `assemble_graph` drops self and mirrored rows in Python afterwards and logs a
    warning nobody asserts on.

    That backstop stops WRONG edges. It cannot stop MISSING ones. Self pairs are
    distance 0 and mirrored pairs duplicate real distances, so under
    `ORDER BY distance ASC ... LIMIT :edge_probe` they sort to the front and spend
    the caller's budget before the real pairs are reached. The adversary measured
    the loss at 29 percent with a generous cap and 100 percent with a tight one,
    and the payload reported `edges_capped: true`, which a panel reads as "there
    are more edges past the cap" rather than "a third of your graph was discarded".

    So this pins the exact edge count with the cap set AT the true pair count.
    Three items make three unordered pairs; with `<=` the three self pairs arrive
    first and the real ones fall off the end.
    """
    owner = await _owner(db_session)
    a = await _item(db_session, owner, "A", [_vector(1.0, 0.0)])
    b = await _item(db_session, owner, "B", [_vector(0.99, 0.01)])
    c = await _item(db_session, owner, "C", [_vector(0.98, 0.02)])
    await db_session.flush()

    payload = (
        await build_knowledge_graph(
            db_session, owner_id=owner, edge_cap=3, max_distance=1.5
        )
    ).as_dict()

    pairs = {frozenset((e["source"], e["target"])) for e in payload["edges"]}
    assert pairs == {
        frozenset((a, b)),
        frozenset((a, c)),
        frozenset((b, c)),
    }, (
        f"expected all three unordered pairs at edge_cap=3, got {len(pairs)}. A "
        "predicate that also emits self or mirrored rows spends the cap on them "
        "and drops real edges, and the Python guard downstream cannot put them back"
    )
    assert payload["edges_capped"] is False, (
        "the cap is reported as having bitten at exactly the true pair count, which "
        "means rows this graph does not need were counted against it"
    )


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
