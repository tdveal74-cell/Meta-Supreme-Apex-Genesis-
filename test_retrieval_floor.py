"""Retrieval can refuse, executed against real PostgreSQL.

WHY THIS FILE EXISTS

Until 2026-09-17 `hybrid_retrieve` could not return an empty list for any non
empty query, so `synthesize_with_cross_encoder`'s documented rule, "No
candidates -> explicit refusal (never fabricate)", was unreachable. Measured
end to end through the real `query_knowledge`, these two came back identical:

    'xylophone quagmire zeppelin'     cleared True   3 citations
    'how do I recover from burnout'   cleared True   3 citations

Same shape, same citations, same order. The endpoint could not tell a question
it could answer from three words that appear nowhere in the corpus.

TWO SIGNALS NEVER READ THE QUERY, WHICH IS WHY.

`rarity` read `metadata->>'rarity'`, which nothing in this repository writes, so
it was 0.0 on every row and `rank_map_from_scores` ordered it by UUID at weight
0.35. `age` is real but `_recent_pool` is `ORDER BY created_at DESC LIMIT 30`
and takes no query at all. Between them they supplied a full pool for every
query, and that pool was the whole of the fusion's output whenever dense and
sparse found nothing.

THE FIX IS A RULE ABOUT INTRODUCING CANDIDATES, NOT A THRESHOLD, which is why
these tests assert emptiness and membership rather than any number. A floor
nobody measured is a guess, and RRF scores are not comparable across corpus
sizes anyway.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from services.intelligence.providers.embeddings import (
    TRUSTED_FOR_RETRIEVAL,
    dense_signal_is_trusted,
)
from services.knowledge.fts import FTS_VECTOR_SQL
from services.knowledge.retrieval import hybrid_retrieve

DIMS = 1536


def _vector(seed: float) -> str:
    return "[" + ",".join(repr(float(v)) for v in [seed] + [0.0] * (DIMS - 1)) + "]"


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"floor-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


async def _chunk(db, owner_id: str, title: str, content: str, seed: float = 0.5) -> str:
    item_id, embedding_id = str(uuid.uuid4()), str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO knowledge_items (id, owner_id, title, source_type, status)"
            " VALUES (CAST(:id AS uuid), CAST(:o AS uuid), :t, 'manual', 'ready')"
        ),
        {"id": item_id, "o": owner_id, "t": title},
    )
    await db.execute(
        text(
            "INSERT INTO embeddings"
            " (id, knowledge_item_id, chunk_index, content, embedding, owner_id)"
            " VALUES (CAST(:id AS uuid), CAST(:k AS uuid), 0, :c,"
            " CAST(:v AS vector), CAST(:o AS uuid))"
        ),
        {"id": embedding_id, "k": item_id, "c": content, "v": _vector(seed), "o": owner_id},
    )
    await db.execute(
        text(
            f"UPDATE embeddings e SET fts = {FTS_VECTOR_SQL} FROM knowledge_items ki"
            " WHERE ki.id = e.knowledge_item_id AND e.id = CAST(:i AS uuid)"
        ),
        {"i": embedding_id},
    )
    return embedding_id


async def _seed(db, owner_id: str) -> dict[str, str]:
    return {
        "burnout": await _chunk(
            db, owner_id, "Recovering from burnout",
            "Cut one commitment entirely rather than trimming five.",
        ),
        "render": await _chunk(
            db, owner_id, "Render lane notes",
            "The lane converts the script to speech and stitches the audio.",
        ),
        "voice": await _chunk(
            db, owner_id, "Voice and identity rule",
            "Voice and identity owned, never rented.",
        ),
    }


async def _retrieve(db, owner_id: str, query: str, **kw):
    return await hybrid_retrieve(
        db, owner_id=owner_id, query=query,
        query_vec=[0.5] + [0.0] * (DIMS - 1), limit=8, **kw,
    )


@pytest.mark.asyncio
async def test_a_query_matching_nothing_returns_nothing(db_session):
    """The floor. These three words appear in no chunk and in no title."""
    owner = await _owner(db_session)
    await _seed(db_session, owner)

    assert await _retrieve(db_session, owner, "xylophone quagmire zeppelin") == []


@pytest.mark.asyncio
async def test_a_query_that_does_match_still_returns(db_session):
    """A floor that refuses everything would pass the test above and be useless."""
    owner = await _owner(db_session)
    ids = await _seed(db_session, owner)

    got = await _retrieve(db_session, owner, "how do I recover from burnout")
    assert [str(c.embedding_id) for c in got] == [ids["burnout"]]


@pytest.mark.asyncio
async def test_age_cannot_introduce_a_candidate(db_session):
    """The whole mechanism, stated as one assertion.

    Every chunk here is in the recent pool, because that pool is the newest
    thirty rows regardless of the query. Only one of them matches the query, so
    only one may come back. Before 2026-09-17 all three did, in created_at
    order, for this query and for every other.
    """
    owner = await _owner(db_session)
    ids = await _seed(db_session, owner)

    got = [str(c.embedding_id) for c in await _retrieve(db_session, owner, "burnout")]
    assert got == [ids["burnout"]]
    assert ids["render"] not in got and ids["voice"] not in got


@pytest.mark.asyncio
async def test_the_dense_signal_is_refused_by_default(db_session):
    """`dense_is_trusted` fails closed.

    The vector passed here is identical to every chunk's, so an ungated dense
    signal returns all three at distance 0. The floor holds anyway because the
    caller did not vouch for the provider.
    """
    owner = await _owner(db_session)
    await _seed(db_session, owner)

    assert await _retrieve(db_session, owner, "xylophone quagmire zeppelin") == []


@pytest.mark.asyncio
async def test_a_vouched_for_dense_signal_may_introduce(db_session):
    """And the gate is a gate rather than a deletion.

    Same query, same corpus, same identical vectors. The only difference is the
    caller saying the distances can be believed, and now they introduce.
    """
    owner = await _owner(db_session)
    await _seed(db_session, owner)

    got = await _retrieve(
        db_session, owner, "xylophone quagmire zeppelin", dense_is_trusted=True
    )
    assert len(got) == 3


@pytest.mark.asyncio
async def test_no_candidate_carries_a_rarity_signal(db_session):
    """Deleted rather than kept at weight zero.

    A dead signal that still appears in the payload is how this survived: a
    reader sees `rarity` and assumes something computes it.
    """
    owner = await _owner(db_session)
    await _seed(db_session, owner)

    got = await _retrieve(db_session, owner, "burnout")
    assert got, "the fixture is supposed to match"
    for candidate in got:
        assert "rarity" not in candidate.signals
        assert set(candidate.signals) == {"dense", "sparse", "age"}


@pytest.mark.parametrize(
    "name, trusted",
    [
        ("openai", True),
        ("OpenAI", True),
        ("  openai  ", True),
        ("mock", False),
        ("cerebras", False),
        ("", False),
        (None, False),
    ],
)
def test_the_trust_list_is_an_allowlist(name, trusted):
    """Anything unrecognised refuses, so a new provider is measured first.

    A denylist of ("mock",) would let a provider nobody has measured decide
    whether a document was found. `app.services.episodes` learned that on
    2026-09-16 and the comment there says so.
    """
    assert dense_signal_is_trusted(name) is trusted


def test_the_mock_provider_is_not_on_the_trust_list():
    """The measurement that put it there: 0.6406 against 0.6170, inverted."""
    assert "mock" not in TRUSTED_FOR_RETRIEVAL
    assert "openai" in TRUSTED_FOR_RETRIEVAL
