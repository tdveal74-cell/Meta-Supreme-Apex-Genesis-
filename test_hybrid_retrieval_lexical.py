"""The lexical leg of hybrid retrieval, executed against real PostgreSQL.

WHY THIS FILE EXISTS

`services/knowledge/retrieval.py` fuses four signals and shipped with no test
of any kind. Nothing named `hybrid_retrieve`, `_sparse_signal` or
`plainto_tsquery` anywhere in the suite, counted 2026-09-17. So the lexical
signal was free to return nothing at all, forever, and it did.

`plainto_tsquery` ANDs every lexeme it produces. `how do I fix my resume`
becomes `'fix' & 'resum'`, which only matches a chunk carrying BOTH words, and
a chunk that answers the question usually carries one of them. Measured on a
seeded corpus the day this file was written: the shipped AND form reached the
known relevant chunk once in five realistic queries. The other four returned
zero rows, and zero rows from one signal in an RRF fusion is not an error. It
is a slightly worse ranking, which is why nobody saw it.

Twelve seeded trials over a twelve chunk corpus and nine queries, varying the
id ordering that breaks ties in the rarity and age signals:

    mock dense + AND sparse   MRR 0.535   (what shipped)
    no dense   + AND sparse   MRR 0.340
    no dense   + OR sparse    MRR 0.780   (no embedding vendor at all)
    mock dense + OR sparse    MRR 0.800

The operator is worth about 0.245 MRR. The dense signal, on the mock provider,
is worth about 0.020 on top of it. The ranges do not overlap.

WHAT THESE TESTS GUARD

The behaviour, not the implementation: a question that shares SOME of its words
with the answer has to reach the answer. `test_the_and_form_that_shipped_finds_
nothing_here` runs the old query beside the new one so the file carries the
measurement rather than describing it, and so a well meaning tightening back to
AND fails loudly instead of going quiet.

The rest is the widening's blast radius. OR matches far more rows than AND, so
the ACL and the ranking both need proving under it, and the user's text reaches
a tsquery, so hostile input needs proving too.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from services.knowledge.retrieval import _sparse_signal, hybrid_retrieve

DIMS = 1536


def _vector(seed: float) -> str:
    """A pgvector literal. The dense signal is not what this file measures."""
    values = [seed] + [0.0] * (DIMS - 1)
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"lexical-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


async def _chunk(db, owner_id: str, title: str, content: str, seed: float = 0.5) -> str:
    """One ready item carrying one embedding row, with fts populated."""
    item_id, embedding_id = str(uuid.uuid4()), str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO knowledge_items"
            " (id, owner_id, title, source_type, status, metadata)"
            " VALUES (CAST(:id AS uuid), CAST(:owner AS uuid), :title, 'manual',"
            " 'ready', '{}'::jsonb)"
        ),
        {"id": item_id, "owner": owner_id, "title": title},
    )
    await db.execute(
        text(
            "INSERT INTO embeddings"
            " (id, knowledge_item_id, chunk_index, content, embedding, owner_id, fts)"
            " VALUES (CAST(:id AS uuid), CAST(:item AS uuid), 0, :content,"
            " CAST(:vec AS vector), CAST(:owner AS uuid),"
            " to_tsvector('english', :content))"
        ),
        {
            "id": embedding_id,
            "item": item_id,
            "content": content,
            "vec": _vector(seed),
            "owner": owner_id,
        },
    )
    return embedding_id


RESUME = (
    "Rewrite the resume around outcomes rather than duties, and put a number "
    "on every claim you make."
)
TYRE = (
    "Loosen the nuts before you jack the car up, then finish the turn once "
    "the wheel is off the ground."
)


async def _sparse_ids(db, owner_id: str, query: str, limit: int = 8) -> list[str]:
    rows = await _sparse_signal(
        db, owner_id=owner_id, query=query, project_id=None, user_tokens=[], limit=limit
    )
    return [str(row["embedding_id"]) for row in rows]


@pytest.mark.asyncio
async def test_a_question_sharing_some_of_its_words_reaches_the_answer(db_session):
    """The regression. `fix` is in the question and in no document."""
    owner = await _owner(db_session)
    wanted = await _chunk(db_session, owner, "Resume rewriting", RESUME)
    await _chunk(db_session, owner, "Changing a tyre", TYRE)

    assert wanted in await _sparse_ids(db_session, owner, "how do I fix my resume")


@pytest.mark.asyncio
async def test_the_and_form_that_shipped_finds_nothing_here(db_session):
    """The measurement, executed beside the fix rather than described above it.

    This is the query the shipped signal ran. If a later change reverts the
    operator, the test above goes red and this one stays green, which names the
    cause instead of leaving somebody to find it again.
    """
    owner = await _owner(db_session)
    await _chunk(db_session, owner, "Resume rewriting", RESUME)

    lexemes = await db_session.scalar(
        text("SELECT plainto_tsquery('english', :q)::text"),
        {"q": "how do I fix my resume"},
    )
    assert lexemes == "'fix' & 'resum'", lexemes

    matched = await db_session.scalar(
        text(
            "SELECT count(*) FROM embeddings"
            " WHERE owner_id = CAST(:o AS uuid)"
            "   AND fts @@ plainto_tsquery('english', :q)"
        ),
        {"o": owner, "q": "how do I fix my resume"},
    )
    assert matched == 0, "the AND form is supposed to be the thing that missed"


@pytest.mark.asyncio
async def test_carrying_more_of_the_query_outranks_carrying_less(db_session):
    """OR widens what matches; ts_rank_cd still has to order it sensibly."""
    owner = await _owner(db_session)
    both = await _chunk(
        db_session,
        owner,
        "Resume and interview",
        "Rehearse the interview answers and rewrite the resume around outcomes.",
    )
    one = await _chunk(
        db_session, owner, "Interview only", "Rehearse three interview stories."
    )

    ranked = await _sparse_ids(db_session, owner, "interview resume")
    assert both in ranked and one in ranked
    assert ranked.index(both) < ranked.index(one)


@pytest.mark.asyncio
async def test_the_acl_still_scopes_the_widened_signal(db_session):
    """A wider match must not become a wider read."""
    mine = await _owner(db_session)
    theirs = await _owner(db_session)
    await _chunk(db_session, mine, "Resume rewriting", RESUME)
    not_mine = await _chunk(db_session, theirs, "Their resume", RESUME)

    assert not_mine not in await _sparse_ids(db_session, mine, "how do I fix my resume")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hostile",
    [
        "resume & ! job | (x)",
        "resume \\ job':;drop",
        "resume <-> job",
        "'resume'''",
        "resume:*",
        "((((resume",
    ],
)
async def test_hostile_input_cannot_reach_the_tsquery_parser(db_session, hostile):
    """plainto_tsquery sanitises; the rewrite only swaps the conjunction.

    A tsquery built by concatenating user text would raise a syntax error on
    most of these, which is the failure this construction exists to avoid.
    """
    owner = await _owner(db_session)
    await _chunk(db_session, owner, "Resume rewriting", RESUME)

    ids = await _sparse_ids(db_session, owner, hostile)
    assert isinstance(ids, list)


@pytest.mark.asyncio
async def test_a_query_of_only_stop_words_matches_nothing_and_does_not_raise(
    db_session,
):
    """plainto_tsquery yields an empty tsquery here, which matches no row."""
    owner = await _owner(db_session)
    await _chunk(db_session, owner, "Resume rewriting", RESUME)

    assert await _sparse_ids(db_session, owner, "the and of") == []


@pytest.mark.asyncio
async def test_the_fusion_ranks_the_answer_first_on_the_lexical_signal_alone(
    db_session,
):
    """End to end, with the dense signal weighted out entirely.

    This is the configuration measured at MRR 0.780: no embedding vendor, no
    real vectors, retrieval carried by the three signals that never needed one.

    THE FIRST VERSION OF THIS TEST PROVED NOTHING. It seeded three chunks and
    asserted the wanted one came first, and it passed with the lexical signal
    reverted to AND and returning zero rows, because `rank_map_from_scores`
    breaks ties on the id and three chunks written in the same second have
    indistinguishable rarity and age scores. So the id ordering decided it, the
    assertion rode a coin flip, and the same coin flip would have failed in CI
    sooner or later. Caught by mutating the operator back and watching this one
    stay green while two others went red.

    Two changes. Enough distractors that winning on a tie-break is not
    plausible, and an assertion that the SPARSE signal is what put the chunk
    there, which no amount of tie-breaking can fake.
    """
    owner = await _owner(db_session)
    wanted = await _chunk(db_session, owner, "Resume rewriting", RESUME, seed=0.5)
    for title, body in (
        ("Changing a tyre", TYRE),
        ("Pruning roses", "Cut just above an outward facing bud at an angle."),
        ("Sourdough", "Feed the starter with equal parts flour and water."),
        ("Podcast arc", "Two characters carry the arc across the season."),
        ("Render lane", "The lane stitches the audio under the footage."),
        ("Vector notes", "An HNSW index keeps the scan bounded."),
    ):
        await _chunk(db_session, owner, title, body, seed=0.5)

    candidates = await hybrid_retrieve(
        db_session,
        owner_id=owner,
        query="how do I fix my resume",
        query_vec=[0.5] + [0.0] * (DIMS - 1),
        limit=8,
        signal_weights={"dense": 0.0, "sparse": 1.0, "rarity": 0.35, "age": 0.25},
    )

    assert candidates, "the lexical signal alone has to return something"
    assert str(candidates[0].embedding_id) == wanted
    assert candidates[0].signals["sparse"] == 1.0, (
        "the chunk has to be here because the lexical signal found it, not "
        "because it won a tie-break on its id"
    )
