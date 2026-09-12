"""
GET /knowledge/graph, pinned without a database.

Every test here is offline: no PostgreSQL, no pgvector, no network, no keys.
The session is a fake that dispatches on the identity of the SQL constants in
`app.services.knowledge_graph`, so it cannot drift with the text of a query,
and it records every statement it was handed so the read-only claim is checked
rather than asserted in a docstring.

What this file does NOT verify, stated plainly rather than implied by a green
run. The SQL itself is not executed anywhere in this file, so the semantics of
the edge query are UNVERIFIED here: that `MIN(a.embedding <=> b.embedding)`
really is the minimum over chunk pairs, that `a.item_id < b.item_id` really
yields one row per unordered pair, that `ROW_NUMBER() ... <= :chunk_cap` really
bounds the scan, and that `HAVING ... <= :max_distance` really cuts the tail.
Those need a cluster with pgvector, which is the `api` CI job, not the
`standalone` one. An integration test belongs there and this file is not a
substitute for it.

What this file does verify is the part that lives in Python: the payload shape,
that a cap which bit is reported rather than swallowed, that a truncated chunk
scan is labelled as an upper bound, that self and duplicate pairs cannot reach
the payload even if the SQL ever loosened, that the provider name is read from
the same place the vectors were actually written from, and that the route is
authenticated, bounded, and shadowed by nothing.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.knowledge as knowledge_routes
import app.api.v1.knowledge_graph as graph_routes
import app.services.knowledge as knowledge_service
import app.services.knowledge_graph as kg
from app.db.session import get_db
from app.security.deps import get_current_user
from services.intelligence.providers.base import ProviderConfigError
from services.intelligence.providers.embeddings import (
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
)

OWNER = "11111111-1111-1111-1111-111111111111"
ITEM_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ITEM_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ITEM_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

# The exact payload surface. Pinned as a set so a field that is quietly
# renamed or dropped fails here instead of in a panel that then has no way to
# tell an empty graph from a broken one.
EXPECTED_KEYS = {
    "nodes",
    "edges",
    "items_total",
    "items_ready",
    "items_embedded",
    "items_unembedded",
    "items_simulated_embeddings",
    "nodes_returned",
    "nodes_capped",
    "node_cap",
    "edges_returned",
    "edges_capped",
    "edge_cap",
    "chunk_cap",
    "chunks_considered",
    "chunks_truncated",
    "max_distance",
    "embedding_provider",
    "embedding_model",
    "embedding_provider_simulated",
    "embedding_provider_error",
}

EXPECTED_NODE_KEYS = {
    "id",
    "title",
    "source",
    "source_type",
    "created_at",
    "chunk_count",
    "embedded_chunk_count",
    "simulated_embeddings",
    "chunks_considered",
    "chunks_truncated",
}

EXPECTED_EDGE_KEYS = {"source", "target", "distance", "distance_is_upper_bound"}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def counts(
    total: int = 0, ready: int = 0, embedded: int = 0, simulated: int = 0
) -> Dict[str, Any]:
    return {
        "items_total": total,
        "items_ready": ready,
        "items_embedded": embedded,
        "items_simulated": simulated,
    }


def node_row(
    item_id: str,
    *,
    title: str = "A document",
    source: Optional[str] = "drive",
    source_type: str = "markdown",
    chunks: int = 3,
    embedded: Optional[int] = None,
    simulated: bool = True,
    created_at: Any = "2026-09-01T12:00:00+00:00",
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "source": source,
        "source_type": source_type,
        # A real date by default. The panel sorts by this and reads it out to a
        # screen reader, and until 2026-09-10 the SELECT list omitted it, so the
        # panel said "created date not reported" on every successful read while
        # every test passed. A default of None here would have let that back in.
        "created_at": created_at,
        "chunk_count": chunks,
        "embedded_chunk_count": chunks if embedded is None else embedded,
        "simulated_embeddings": simulated,
    }


def edge_row(source: str, target: str, distance: float) -> Dict[str, Any]:
    return {"source_id": source, "target_id": target, "distance": distance}


MOCK_PROVIDER = {
    "embedding_provider": "mock",
    "embedding_model": "mock-embed-v1",
    "embedding_provider_simulated": True,
    "embedding_provider_error": None,
}


class FakeResult:
    """Just enough of a SQLAlchemy Result for the three reads this makes."""

    def __init__(
        self,
        *,
        rows: Optional[Sequence[Mapping[str, Any]]] = None,
        one: Optional[Mapping[str, Any]] = None,
        scalar: Any = None,
    ) -> None:
        self._rows = list(rows or [])
        self._one = one
        self._scalar = scalar

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> List[Mapping[str, Any]]:
        return list(self._rows)

    def one(self) -> Mapping[str, Any]:
        if self._one is None:
            raise AssertionError("one() called on a result with no single row")
        return self._one

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalar_one(self) -> Any:
        return self._scalar


class FakeSession:
    """A session that answers the graph's three SELECTs and records everything.

    Dispatch is on the identity of the SQL constants rather than on substrings
    of the rendered text, so renaming a column inside a query cannot silently
    reroute a fake and turn a broken query into a green test.
    """

    def __init__(
        self,
        *,
        count_row: Optional[Mapping[str, Any]] = None,
        node_rows: Sequence[Mapping[str, Any]] = (),
        edge_rows: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.count_row = count_row if count_row is not None else counts()
        self.node_rows = list(node_rows)
        self.edge_rows = list(edge_rows)
        self.executed: List[Any] = []
        self.params: List[Any] = []
        self.mutations: List[str] = []

    async def execute(self, statement: Any, params: Any = None) -> FakeResult:
        self.executed.append(statement)
        self.params.append(params)
        if statement is kg._COUNTS_SQL:
            return FakeResult(one=self.count_row)
        if statement is kg._NODES_SQL:
            return FakeResult(rows=self.node_rows)
        if statement is kg._EDGES_SQL:
            return FakeResult(rows=self.edge_rows)
        # Anything else is a neighbouring route reaching the same fake, which
        # the shadowing test relies on: no row found.
        return FakeResult(scalar=None)

    async def commit(self) -> None:
        self.mutations.append("commit")

    async def flush(self) -> None:
        self.mutations.append("flush")

    async def delete(self, _obj: Any) -> None:
        self.mutations.append("delete")

    def add(self, _obj: Any) -> None:
        self.mutations.append("add")

    def sql_texts(self) -> List[str]:
        return [str(s) for s in self.executed]


class FakeUser:
    def __init__(self, user_id: str = OWNER) -> None:
        self.id = user_id
        self.is_active = True


def build_app(
    session: FakeSession,
    *,
    authenticated: bool = True,
    knowledge_first: bool = False,
) -> TestClient:
    """A minimal app carrying only the routers under test.

    `knowledge_first` reproduces the registration order that shadows the graph
    route behind `GET /knowledge/{item_id}`, which is the hazard the
    integration note about `app/api/v1/router.py` exists to prevent.
    """
    application = FastAPI()
    if knowledge_first:
        application.include_router(knowledge_routes.router)
        application.include_router(graph_routes.router)
    else:
        application.include_router(graph_routes.router)
        application.include_router(knowledge_routes.router)

    async def _db() -> Any:
        yield session

    application.dependency_overrides[get_db] = _db
    if authenticated:
        application.dependency_overrides[get_current_user] = lambda: FakeUser()
    return TestClient(application)


# ---------------------------------------------------------------------------
# Payload shape
# ---------------------------------------------------------------------------


def test_payload_carries_every_honesty_field():
    graph = kg.assemble_graph(
        counts=counts(total=9, ready=4, embedded=3, simulated=3),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.21)],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    payload = graph.as_dict()

    assert set(payload) == EXPECTED_KEYS
    assert set(payload["nodes"][0]) == EXPECTED_NODE_KEYS
    assert set(payload["edges"][0]) == EXPECTED_EDGE_KEYS

    assert payload["items_total"] == 9
    assert payload["items_ready"] == 4
    assert payload["items_embedded"] == 3
    # Measured by subtraction from two counts in the same statement, so the
    # panel can say "one ready item has no vector" instead of showing a dot
    # that can carry no edge and explaining nothing.
    assert payload["items_unembedded"] == 1
    assert payload["items_simulated_embeddings"] == 3
    assert payload["edges_returned"] == 1
    assert payload["max_distance"] == 0.65


def test_an_empty_corpus_is_distinguishable_from_a_broken_one():
    graph = kg.assemble_graph(
        counts=counts(),
        node_rows=[],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    payload = graph.as_dict()
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["items_total"] == 0
    assert payload["nodes_capped"] is False
    assert payload["edges_capped"] is False
    # Zero nodes with a named provider is an empty corpus. The panel needs the
    # provider even then, because zero and unreadable look identical on canvas.
    assert payload["embedding_provider"] == "mock"


def test_unembedded_count_never_goes_negative():
    # A snapshot skew between the two FILTER counts must not publish a
    # negative number, which would read as a corrupt corpus.
    graph = kg.assemble_graph(
        counts=counts(total=3, ready=2, embedded=5),
        node_rows=[],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.items_unembedded == 0


def test_null_source_falls_back_to_source_type():
    graph = kg.assemble_graph(
        counts=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A, source=None, source_type="url", title="")],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.nodes[0].source == "url"
    assert graph.nodes[0].title == "Untitled"


# ---------------------------------------------------------------------------
# Cap reporting
# ---------------------------------------------------------------------------


def test_node_cap_that_bit_is_reported_and_the_probe_row_is_dropped():
    rows = [node_row(str(uuid.uuid4())) for _ in range(4)]
    graph = kg.assemble_graph(
        counts=counts(total=4, ready=4, embedded=4),
        node_rows=rows,
        edge_rows=[],
        node_cap=3,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.nodes_capped is True
    assert graph.nodes_returned == 3
    assert len(graph.nodes) == 3
    assert graph.node_cap == 3


def test_a_graph_exactly_cap_sized_is_not_reported_as_capped():
    # The probe read is cap + 1 rows. Reporting "capped" from the parameter
    # instead of from the probe would flag a complete graph as truncated,
    # which is the opposite lie to a silent truncation and just as wrong.
    rows = [node_row(str(uuid.uuid4())) for _ in range(3)]
    graph = kg.assemble_graph(
        counts=counts(total=3, ready=3, embedded=3),
        node_rows=rows,
        edge_rows=[],
        node_cap=3,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.nodes_capped is False
    assert graph.nodes_returned == 3


def test_edge_cap_that_bit_is_reported_and_the_probe_row_is_dropped():
    ids = [str(uuid.uuid4()) for _ in range(4)]
    rows = [node_row(i) for i in ids]
    edges = [
        edge_row(ids[0], ids[1], 0.10),
        edge_row(ids[0], ids[2], 0.20),
        edge_row(ids[1], ids[2], 0.30),
    ]
    graph = kg.assemble_graph(
        counts=counts(total=4, ready=4, embedded=4),
        node_rows=rows,
        edge_rows=edges,
        node_cap=10,
        edge_cap=2,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.edges_capped is True
    assert graph.edges_returned == 2
    assert graph.edge_cap == 2
    # Rows arrive ordered by distance ascending, so a cap keeps the nearest
    # pairs rather than an arbitrary slice.
    assert [e.distance for e in graph.edges] == [0.10, 0.20]


def test_exactly_cap_many_edges_is_not_reported_as_capped():
    ids = [str(uuid.uuid4()) for _ in range(3)]
    graph = kg.assemble_graph(
        counts=counts(total=3, ready=3, embedded=3),
        node_rows=[node_row(i) for i in ids],
        edge_rows=[edge_row(ids[0], ids[1], 0.1), edge_row(ids[0], ids[2], 0.2)],
        node_cap=10,
        edge_cap=2,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.edges_capped is False
    assert graph.edges_returned == 2


def test_chunk_truncation_is_reported_and_marks_the_distance_an_upper_bound():
    # ITEM_A has 50 embedded chunks and the cap is 5, so the pair scan saw 5
    # of them. The minimum over a subset can only be larger than or equal to
    # the true minimum, so the published distance is an upper bound and the
    # payload has to say so.
    graph = kg.assemble_graph(
        counts=counts(total=2, ready=2, embedded=2),
        node_rows=[
            node_row(ITEM_A, chunks=50, embedded=50),
            node_row(ITEM_B, chunks=2, embedded=2),
        ],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.42)],
        node_cap=10,
        edge_cap=10,
        chunk_cap=5,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.chunks_truncated is True
    assert graph.chunk_cap == 5
    # 5 considered for A (capped) plus 2 for B.
    assert graph.chunks_considered == 7
    node_a = next(n for n in graph.nodes if n.id == ITEM_A)
    node_b = next(n for n in graph.nodes if n.id == ITEM_B)
    assert node_a.chunks_truncated is True
    assert node_a.chunks_considered == 5
    assert node_b.chunks_truncated is False
    assert node_b.chunks_considered == 2
    assert graph.edges[0].distance_is_upper_bound is True


def test_an_untruncated_scan_publishes_an_exact_minimum():
    graph = kg.assemble_graph(
        counts=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A, chunks=3, embedded=3), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.42)],
        node_cap=10,
        edge_cap=10,
        chunk_cap=40,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.chunks_truncated is False
    assert graph.edges[0].distance_is_upper_bound is False


# ---------------------------------------------------------------------------
# Edge integrity
# ---------------------------------------------------------------------------


def test_an_edge_naming_a_node_outside_the_payload_is_dropped():
    # The node cap dropped ITEM_C, so an edge touching it would be a line to
    # nowhere. The edge query is handed only the kept ids so this should be
    # unreachable, which is exactly why it is checked rather than assumed.
    graph = kg.assemble_graph(
        counts=counts(total=3, ready=3, embedded=3),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B), node_row(ITEM_C)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.1), edge_row(ITEM_A, ITEM_C, 0.2)],
        node_cap=2,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert {n.id for n in graph.nodes} == {ITEM_A, ITEM_B}
    assert [(e.source, e.target) for e in graph.edges] == [(ITEM_A, ITEM_B)]
    assert graph.edges_returned == 1


def test_self_pairs_and_repeated_pairs_cannot_reach_the_payload():
    # The SQL predicate `a.item_id < b.item_id` already excludes both, so this
    # pins the invariant one layer lower where it can be tested without a
    # cluster: if that predicate were ever loosened to `<>`, the payload would
    # otherwise gain a self loop and a mirrored duplicate of every edge.
    graph = kg.assemble_graph(
        counts=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[
            edge_row(ITEM_A, ITEM_A, 0.0),
            edge_row(ITEM_A, ITEM_B, 0.1),
            edge_row(ITEM_B, ITEM_A, 0.1),
        ],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert [(e.source, e.target) for e in graph.edges] == [(ITEM_A, ITEM_B)]
    assert graph.edges_returned == 1


# ---------------------------------------------------------------------------
# Caps, clamped
# ---------------------------------------------------------------------------


def test_caps_default_and_clamp_to_their_hard_range():
    assert kg.clamp_caps() == {
        "node_cap": kg.DEFAULT_NODE_CAP,
        "edge_cap": kg.DEFAULT_EDGE_CAP,
        "chunk_cap": kg.DEFAULT_CHUNK_CAP,
        "max_distance": kg.DEFAULT_MAX_DISTANCE,
    }
    wide = kg.clamp_caps(
        node_cap=10**6, edge_cap=10**6, chunk_cap=10**6, max_distance=99.0
    )
    assert wide == {
        "node_cap": kg.MAX_NODE_CAP,
        "edge_cap": kg.MAX_EDGE_CAP,
        "chunk_cap": kg.MAX_CHUNK_CAP,
        "max_distance": kg.MAX_MAX_DISTANCE,
    }
    narrow = kg.clamp_caps(node_cap=0, edge_cap=-5, chunk_cap=0, max_distance=-1.0)
    assert narrow == {
        "node_cap": 1,
        "edge_cap": 1,
        "chunk_cap": 1,
        "max_distance": 0.0,
    }


def test_the_node_id_array_param_is_a_list_and_refuses_a_non_uuid():
    """A LIST, because asyncpg binds arrays natively and rejects a literal str.

    This test asserted the "{a,b}" literal form until 2026-09-10, and it passed
    while the edge query could not execute against a real database at all: the
    driver raised DataError before Postgres saw the statement. That is why
    test_knowledge_graph_pgvector.py exists. Asserting the type here is what
    keeps a well meaning simplification back to a literal from shipping green.
    """
    param = kg._uuid_array_param([ITEM_A, ITEM_B])
    # A SIZED ITERABLE, which is what the driver needs and what the message says.
    # The first version asserted `isinstance(param, list)` while its message spoke
    # of a sized iterable, so it would have failed a correct refactor to a tuple.
    # An adversary measured that tuples and sets both work against real pgvector.
    # What must never pass is a str, which is also sized and iterable, so it is
    # excluded by name rather than by asserting one concrete type.
    assert not isinstance(param, (str, bytes)), (
        "asyncpg binds arrays natively, so a str is the one sized iterable it "
        "rejects. This is the bug that shipped: a Postgres array literal"
    )
    assert hasattr(param, "__len__"), "asyncpg needs a sized iterable"
    assert list(param) == [ITEM_A, ITEM_B]
    with pytest.raises(ValueError):
        kg._uuid_array_param([ITEM_A, "'); drop table embeddings; --"])


# ---------------------------------------------------------------------------
# Provider surfacing, the load bearing field
# ---------------------------------------------------------------------------


def test_provider_identity_reads_the_lane_that_actually_embedded():
    # Drift guard. The vectors in the table were written by whatever
    # `app.services.knowledge._embedding_provider()` builds, so the graph must
    # report that and nothing re-derived from settings. Hardcoding a name here
    # would let the report and the reality separate silently.
    reported = kg.embedding_provider_identity()
    try:
        provider = knowledge_service._embedding_provider()
    except Exception as exc:
        assert reported["embedding_provider"] == "unavailable"
        assert reported["embedding_provider_error"]
        assert str(exc)[:80] in reported["embedding_provider_error"]
        return
    assert reported["embedding_provider"] == provider.name
    assert reported["embedding_model"] == provider.default_model
    assert reported["embedding_provider_simulated"] is (provider.name == "mock")
    assert reported["embedding_provider_error"] is None


def test_mock_vectors_are_reported_as_simulated(monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "_embedding_provider",
        lambda: MockEmbeddingProvider(),
    )
    reported = kg.embedding_provider_identity()
    assert reported["embedding_provider"] == "mock"
    assert reported["embedding_model"] == "mock-embed-v1"
    # With EMBEDDING_PROVIDER=mock the vectors are deterministic hashed
    # bag-of-words fakes, so every distance is an exact measurement of a
    # meaningless quantity. This flag is what lets the panel refuse to draw.
    assert reported["embedding_provider_simulated"] is True
    assert reported["embedding_provider_error"] is None


def test_real_vectors_are_not_reported_as_simulated(monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "_embedding_provider",
        lambda: OpenAIEmbeddingProvider(api_key="not-used-offline"),
    )
    reported = kg.embedding_provider_identity()
    assert reported["embedding_provider"] == "openai"
    assert reported["embedding_provider_simulated"] is False


def test_an_unbuildable_provider_is_reported_not_raised(monkeypatch):
    def _boom():
        raise ProviderConfigError("Unknown embedding provider 'anthropic'.")

    monkeypatch.setattr(knowledge_service, "_embedding_provider", _boom)
    reported = kg.embedding_provider_identity()
    assert reported["embedding_provider"] == "unavailable"
    assert "anthropic" in reported["embedding_provider_error"]
    # Unknown provenance is not the same as known real. The flag stays raised
    # so nothing downstream reads "unavailable" as permission to trust.
    assert reported["embedding_provider_simulated"] is True


def test_the_graph_carries_the_provider_it_was_handed():
    graph = kg.assemble_graph(
        counts=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A)],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=10,
        max_distance=0.65,
        provider={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_provider_simulated": False,
            "embedding_provider_error": None,
        },
    )
    assert graph.embedding_provider == "openai"
    assert graph.embedding_model == "text-embedding-3-small"
    assert graph.embedding_provider_simulated is False


# ---------------------------------------------------------------------------
# The read, against a fake session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_read_issues_three_selects_and_no_writes():
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.3)],
    )
    graph = await kg.build_knowledge_graph(session, owner_id=OWNER)

    assert session.executed == [kg._COUNTS_SQL, kg._NODES_SQL, kg._EDGES_SQL]
    assert session.mutations == []
    for sql in session.sql_texts():
        head = sql.strip().split(None, 1)[0].upper()
        assert head in {"SELECT", "WITH"}, sql
        upper = sql.upper()
        for verb in ("INSERT", "UPDATE ", "DELETE", "TRUNCATE", "ALTER", "DROP"):
            assert verb not in upper, (verb, sql)
    assert graph.edges_returned == 1


@pytest.mark.asyncio
async def test_every_bind_parameter_is_supplied_exactly_once():
    # The fake session accepts any params dict, so a bind name typed one way in
    # the SQL and another way at the call site would pass every other test here
    # and fail only against a real driver. This compares the two directly.
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.2)],
    )
    await kg.build_knowledge_graph(session, owner_id=OWNER)
    for statement, params in zip(session.executed, session.params, strict=True):
        assert set(statement._bindparams) == set(params or {}), statement


@pytest.mark.asyncio
async def test_the_read_is_scoped_to_the_owner_and_the_project():
    session = FakeSession(
        count_row=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A)],
    )
    await kg.build_knowledge_graph(session, owner_id=OWNER, project_id=ITEM_C)
    for params in session.params[:2]:
        assert params["owner_id"] == OWNER
        assert params["project_id"] == ITEM_C


@pytest.mark.asyncio
async def test_the_edge_query_is_skipped_when_nothing_can_pair():
    # One vector bearing node cannot produce an edge, and neither can a node
    # whose chunks are all unembedded. Paying for the O(n squared) scan to
    # learn that is waste, so the query is not issued at all.
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=1),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B, chunks=4, embedded=0)],
    )
    graph = await kg.build_knowledge_graph(session, owner_id=OWNER)
    assert kg._EDGES_SQL not in session.executed
    assert graph.edges == []
    assert graph.nodes_returned == 2


@pytest.mark.asyncio
async def test_the_edge_query_receives_only_the_kept_vector_bearing_nodes():
    session = FakeSession(
        count_row=counts(total=3, ready=3, embedded=2),
        node_rows=[
            node_row(ITEM_A),
            node_row(ITEM_B),
            node_row(ITEM_C, chunks=2, embedded=0),
        ],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.2)],
    )
    await kg.build_knowledge_graph(session, owner_id=OWNER, node_cap=3, chunk_cap=7)
    edge_params = session.params[2]
    # A list, not a literal string: asyncpg binds array parameters natively and
    # rejects a str outright, which is how the edge query shipped unable to run
    # against any real database while this file was green. Asserting the type is
    # what keeps a simplification back to a literal from passing here again.
    assert edge_params["node_ids"] == [ITEM_A, ITEM_B]
    assert isinstance(edge_params["node_ids"], list)
    assert ITEM_C not in edge_params["node_ids"]
    assert edge_params["chunk_cap"] == 7
    assert edge_params["max_distance"] == kg.DEFAULT_MAX_DISTANCE


@pytest.mark.asyncio
async def test_the_reads_probe_one_row_past_every_cap():
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.2)],
    )
    await kg.build_knowledge_graph(session, owner_id=OWNER, node_cap=5, edge_cap=9)
    assert session.params[1]["node_probe"] == 6
    assert session.params[2]["edge_probe"] == 10


@pytest.mark.asyncio
async def test_the_service_clamps_even_when_the_http_edge_is_bypassed():
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.2)],
    )
    graph = await kg.build_knowledge_graph(
        session,
        owner_id=OWNER,
        node_cap=10**9,
        edge_cap=10**9,
        chunk_cap=10**9,
        max_distance=10**9,
    )
    assert graph.node_cap == kg.MAX_NODE_CAP
    assert graph.edge_cap == kg.MAX_EDGE_CAP
    assert graph.chunk_cap == kg.MAX_CHUNK_CAP
    assert graph.max_distance == kg.MAX_MAX_DISTANCE
    assert session.params[1]["node_probe"] == kg.MAX_NODE_CAP + 1


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------


def test_the_route_returns_the_graph():
    session = FakeSession(
        count_row=counts(total=3, ready=2, embedded=2, simulated=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.33)],
    )
    client = build_app(session)
    response = client.get("/knowledge/graph")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == EXPECTED_KEYS
    assert len(payload["nodes"]) == 2
    assert payload["edges"] == [
        {
            "source": ITEM_A,
            "target": ITEM_B,
            "distance": 0.33,
            "distance_is_upper_bound": False,
        }
    ]
    assert payload["items_unembedded"] == 0
    # Read honestly from the lane that embeds, not asserted as a literal.
    assert payload["embedding_provider"] == (
        kg.embedding_provider_identity()["embedding_provider"]
    )


def test_the_route_requires_authentication():
    session = FakeSession()
    client = build_app(session, authenticated=False)
    response = client.get("/knowledge/graph")
    assert response.status_code == 401
    # Nothing was read on an unauthenticated request.
    assert session.executed == []


@pytest.mark.parametrize(
    "query",
    [
        "node_cap=0",
        f"node_cap={kg.MAX_NODE_CAP + 1}",
        "edge_cap=0",
        f"edge_cap={kg.MAX_EDGE_CAP + 1}",
        "chunk_cap=0",
        f"chunk_cap={kg.MAX_CHUNK_CAP + 1}",
        "max_distance=-0.1",
        f"max_distance={kg.MAX_MAX_DISTANCE + 0.1}",
    ],
)
def test_the_route_refuses_an_out_of_range_cap(query):
    session = FakeSession()
    client = build_app(session)
    response = client.get(f"/knowledge/graph?{query}")
    assert response.status_code == 422, response.text
    assert session.executed == []


def test_the_route_passes_its_caps_through():
    session = FakeSession(
        count_row=counts(total=2, ready=2, embedded=2),
        node_rows=[node_row(ITEM_A), node_row(ITEM_B)],
        edge_rows=[edge_row(ITEM_A, ITEM_B, 0.2)],
    )
    client = build_app(session)
    response = client.get(
        "/knowledge/graph?node_cap=7&edge_cap=11&chunk_cap=3&max_distance=0.9"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["node_cap"] == 7
    assert payload["edge_cap"] == 11
    assert payload["chunk_cap"] == 3
    assert payload["max_distance"] == 0.9
    assert session.params[1]["node_probe"] == 8


def test_the_route_writes_nothing():
    session = FakeSession(
        count_row=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A)],
    )
    client = build_app(session)
    assert client.get("/knowledge/graph").status_code == 200
    assert session.mutations == []


def test_only_get_reaches_the_graph():
    # Measured, not assumed. POST, PUT and PATCH on this path find no method,
    # so the router answers 405. DELETE is different and it is worth pinning:
    # `DELETE /knowledge/{item_id}` in the neighbouring router matches the
    # literal segment "graph", so the request lands in the item delete handler
    # and comes back 404 from its ownership lookup. Nothing is deleted, since
    # no item is owned under that id, and the graph handler is never reached.
    # This is a property of the neighbouring router that predates this route
    # and is out of scope to change here.
    session = FakeSession()
    client = build_app(session)
    for call in (client.post, client.put, client.patch):
        assert call("/knowledge/graph").status_code == 405
    deleted = client.delete("/knowledge/graph")
    assert deleted.status_code == 404
    assert deleted.json()["detail"] == "Knowledge item not found"
    assert session.mutations == []


# ---------------------------------------------------------------------------
# Registration order, the shadowing hazard
# ---------------------------------------------------------------------------


def flatten_route_paths(routes) -> List[str]:
    """Route paths in the order the router will try them.

    FastAPI 0.141.1 wraps an included router in a `_IncludedRouter` that
    carries no `path` of its own (measured: `app.routes` on a two-router app
    returns four default routes and two wrappers), so a checker that only read
    `route.path` would find nothing and pass vacuously. This walks into
    `original_router.routes` instead. Route paths already carry their router's
    prefix, so nothing is prepended here.
    """
    paths: List[str] = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            paths.extend(flatten_route_paths(inner.routes))
            continue
        nested = getattr(route, "routes", None)
        if nested is not None and not hasattr(route, "path"):
            paths.extend(flatten_route_paths(nested))
            continue
        path = getattr(route, "path", None)
        if path is not None:
            paths.append(path)
    return paths


def graph_route_precedes_item_lookup(routes) -> bool:
    """True when nothing registered earlier can swallow /knowledge/graph.

    Inspects the app's real route objects rather than the text of a router
    file, so a registration that moves cannot slip past by keeping the same
    source line. Returns True when the graph route is absent, because a router
    that has not been included yet is the integrator's next step and not a
    regression.
    """
    paths = flatten_route_paths(routes)
    graph_index = None
    item_index = None
    # ANY single-segment parameter under /knowledge, not the literal {item_id}.
    #
    # This matched `endswith("/knowledge/{item_id}")` until 2026-09-10, when an
    # adversary added a plausible future route `@router.get("/{fkr_id}")` to
    # knowledge_fkr.py and registered it above the graph. The literal check found
    # graph at index 31 and {item_id} at 35, reported True, and all 42 tests
    # passed while a real TestClient request to /api/v1/knowledge/graph was served
    # by the fkr lookup. So the guard covered today's two lines, spelled against
    # one parameter name, rather than the rule.
    parameterised = re.compile(r"/knowledge/\{[^}/]+\}$")
    for index, path in enumerate(paths):
        if path.endswith("/knowledge/graph") and graph_index is None:
            graph_index = index
        elif parameterised.search(path) and item_index is None:
            item_index = index
    if graph_index is None or item_index is None:
        return True
    return graph_index < item_index


def test_the_route_flattener_actually_finds_routes():
    # Guards the guard. A flattener that returned an empty list would make
    # every ordering check below pass while measuring nothing, which is the
    # failure mode a `_IncludedRouter` with no `path` walks straight into.
    session = FakeSession()
    paths = flatten_route_paths(build_app(session).app.routes)
    assert "/knowledge/graph" in paths
    assert "/knowledge/{item_id}" in paths


def test_the_item_lookup_shadows_the_graph_when_registered_first():
    # Demonstrated, not asserted in prose. `GET /knowledge/{item_id}` matches
    # the literal segment "graph" perfectly happily, and FastAPI resolves in
    # registration order, so the wrong order serves a 404 item lookup instead
    # of the graph. This is the whole reason the router.py integration note
    # names an order.
    session = FakeSession(
        count_row=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A)],
    )
    shadowed = build_app(session, knowledge_first=True)
    response = shadowed.get("/knowledge/graph")
    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge item not found"
    assert graph_route_precedes_item_lookup(shadowed.app.routes) is False

    correct = build_app(session, knowledge_first=False)
    assert correct.get("/knowledge/graph").status_code == 200
    assert graph_route_precedes_item_lookup(correct.app.routes) is True


def test_the_composed_v1_router_registers_the_graph_route_at_all():
    """Absence, not order. The likelier regression, and it used to be invisible.

    `graph_route_precedes_item_lookup` returns True when the graph route is
    ABSENT, deliberately, because the piece was handed over unregistered and the
    ordering helper had nothing to compare. That made the ordering test pass in
    two very different worlds: correct registration, and no registration.

    A critic removed the `include_router` line AND its now unused import on
    2026-09-10 and measured the result: 42 offline passed, 5 pgvector passed,
    ruff clean. With only the include line gone, ruff catches the unused import
    as F401, which is what a careless deletion looks like; a tidy one removes
    both and nothing notices. Since an unregistered route is exactly the stranded
    capability this whole arc was convened to end, absence gets its own assertion
    ahead of the ordering one.
    """
    from app.api.v1.router import api_router

    paths = flatten_route_paths(api_router.routes)
    assert any(path.endswith("/knowledge/graph") for path in paths), (
        "GET /knowledge/graph is not registered on the composed v1 router, so the "
        "route does not answer and the panel reading it draws nothing. Add "
        "api_router.include_router(knowledge_graph.router) BEFORE knowledge.router"
    )


def test_the_composed_v1_router_keeps_the_graph_ahead_of_the_item_lookup():
    # Goes red the moment the graph router is registered in app/api/v1/
    # router.py behind the knowledge router. Absence is covered by the test
    # above, which is why this one may still treat it as a pass.
    from app.api.v1.router import api_router

    assert graph_route_precedes_item_lookup(api_router.routes) is True


def test_created_at_reaches_the_payload_populated_and_serialised():
    """The field is present AND carries a value, and a datetime becomes a string.

    The key-set assertion above proves only that `created_at` is a key. A field
    that is always None satisfies it and is exactly the failure this closes: from
    the route's first commit until 2026-09-10 `ki.created_at` sat in the node
    query's GROUP BY and ORDER BY but not in its SELECT list, so the panel parsed
    `created_at`, sorted by it, and read "created date not reported" to every
    screen reader on every successful read. Its sibling `degree` had the same
    shape and was caught; this one was not, because nothing asserted a value.

    The datetime arm matters because asyncpg returns `timestamptz` as a datetime
    while a stub session can hand back a plain string. Both have to serialise,
    and neither may reach JSON as a repr.
    """
    from datetime import datetime, timezone

    graph = kg.assemble_graph(
        counts=counts(total=2, ready=2, embedded=2),
        node_rows=[
            node_row(ITEM_A, created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)),
            node_row(ITEM_B, created_at="2026-09-02T08:30:00+00:00"),
        ],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=5,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    payload = graph.as_dict()
    dates = {node["id"]: node["created_at"] for node in payload["nodes"]}

    for item_id, value in dates.items():
        assert value is not None, (
            f"node {item_id} reached the payload with created_at None. A key that is "
            "always None passes the key-set assertion and tells every reader the "
            "date was not reported"
        )
        assert isinstance(value, str), f"created_at must serialise to a string, got {type(value)}"
        assert "datetime" not in value and "tzinfo" not in value, (
            f"created_at reached the payload as a repr rather than a date: {value!r}"
        )

    assert dates[ITEM_A].startswith("2026-09-01T12:00:00"), dates[ITEM_A]
    assert dates[ITEM_B] == "2026-09-02T08:30:00+00:00"


def test_a_row_with_no_date_stays_absent_rather_than_becoming_a_guess():
    """None in, None out. A missing date must never become today's."""
    graph = kg.assemble_graph(
        counts=counts(total=1, ready=1, embedded=1),
        node_rows=[node_row(ITEM_A, created_at=None)],
        edge_rows=[],
        node_cap=10,
        edge_cap=10,
        chunk_cap=5,
        max_distance=0.65,
        provider=MOCK_PROVIDER,
    )
    assert graph.as_dict()["nodes"][0]["created_at"] is None


def test_the_node_query_selects_every_column_assemble_graph_reads():
    """The SELECT list must carry every column the builder reads off a row.

    This is the guard for the class, not the instance. `created_at` was read by
    `assemble_graph` and absent from the SELECT list for the route's whole life,
    and no test noticed because a stub row supplied it. Reading the real SQL is
    the only thing that catches the next one.
    """
    import re

    from app.services.knowledge_graph import _NODES_SQL

    sql = str(_NODES_SQL)
    select_block = sql[sql.index("SELECT") : sql.index("FROM")]
    aliased = set(re.findall(r"AS\s+(\w+)", select_block))

    # Every key assemble_graph pulls off a node row, read from the source rather
    # than listed by hand here.
    read_by_builder = {
        "id",
        "title",
        "source",
        "source_type",
        "created_at",
        "chunk_count",
        "embedded_chunk_count",
        "simulated_embeddings",
    }
    missing = sorted(read_by_builder - aliased)
    assert not missing, (
        f"_NODES_SQL does not select {missing}, but assemble_graph reads those keys off "
        "each row, so they arrive as None on every real request while stub rows in this "
        "file supply them and every test passes"
    )
