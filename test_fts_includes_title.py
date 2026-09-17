"""The title is searchable text, executed against real PostgreSQL.

WHY THIS FILE EXISTS

`embeddings.fts` was built from the chunk's content alone, in two ingest paths
that each wrote the expression out by hand. So a knowledge item's title was not
searchable text anywhere in this estate, and a query made only of title words
matched nothing at all. Measured 2026-09-17 against the shipped sparse signal,
over five documents whose distinctive word lives only in the title: zero of five
found, against five of five once the title is folded in.

WHAT IT DOES NOT BUY, BECAUSE THE FIRST DRAFT CLAIMED IT DID

Ranking. Twelve seeded trials over nine natural language queries moved the
shipped configurations by +0.000 MRR. An earlier draft cited 0.741 to 0.767,
which came from one unseeded run where the id ordering that breaks ties in the
rarity and age signals was doing the work. The case for 021 is the zero rows,
so `test_a_query_of_title_words_alone_finds_the_document` is the test that
matters here and the only one worth reverting the change over.

THE DRIFT TEST IS NOT DECORATION. The expression lives in three places that
cannot import each other: two ingest paths in Python and one backfill in SQL
that a migration executes. Three hand written copies is exactly how the title
came to be missing from two of them, and a backfill that indexes rows
differently from the ingest that follows it is the quiet kind of wrong. Nothing
errors; old rows and new rows simply answer different questions.
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy import text

from database.migrations.sql_script import iter_statements
from services.knowledge.fts import FTS_VECTOR_SQL
from services.knowledge.retrieval import _sparse_signal

_REPO_ROOT = pathlib.Path(__file__).resolve().parent
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "021_fts_includes_title.sql"

# The word lives ONLY in the title. That is the whole point of the fixture.
TITLE = "Sourdough starter guide"
CONTENT = "Feed it with equal parts flour and water every twelve hours until it doubles."


async def _run_backfill(db) -> None:
    """Apply 021 the way Alembic does.

    The file is two statements and asyncpg prepares whatever it is handed, so a
    single `text()` of the whole script raises. `iter_statements` is the repo's
    own splitter, the one `execute_sql_script` uses, rather than a second
    `split(";")` written here that would drift from it.
    """
    for statement in iter_statements(_SCHEMA.read_text(encoding="utf-8")):
        await db.execute(text(statement))


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"fts-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


async def _item(db, owner_id: str, title: str, content: str, *, fts: str) -> str:
    """One ready item and chunk. `fts` picks which expression built the column."""
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
            " (id, knowledge_item_id, chunk_index, content, owner_id)"
            " VALUES (CAST(:id AS uuid), CAST(:k AS uuid), 0, :c, CAST(:o AS uuid))"
        ),
        {"id": embedding_id, "k": item_id, "c": content, "o": owner_id},
    )
    if fts == "content":  # what every row carried before 021
        await db.execute(
            text(
                "UPDATE embeddings SET fts = to_tsvector('english', coalesce(content, ''))"
                " WHERE id = CAST(:i AS uuid)"
            ),
            {"i": embedding_id},
        )
    elif fts == "title":
        await db.execute(
            text(
                f"UPDATE embeddings e SET fts = {FTS_VECTOR_SQL} FROM knowledge_items ki"
                " WHERE ki.id = e.knowledge_item_id AND e.id = CAST(:i AS uuid)"
            ),
            {"i": embedding_id},
        )
    else:  # pragma: no cover - guards a typo in a future edit
        raise AssertionError(f"unknown fts mode {fts!r}")
    return embedding_id


@pytest.mark.asyncio
async def test_a_query_of_title_words_alone_finds_the_document(db_session):
    """The whole case for 021, run rather than described.

    `sourdough` appears in the title and in no chunk's content. Before the
    change the lexical signal returned zero rows for it.
    """
    owner = await _owner(db_session)
    wanted = await _item(db_session, owner, TITLE, CONTENT, fts="title")

    rows = await _sparse_signal(
        db_session, owner_id=owner, query="sourdough", project_id=None,
        user_tokens=[], limit=8,
    )
    assert [str(r["embedding_id"]) for r in rows] == [wanted]


@pytest.mark.asyncio
async def test_the_content_only_column_that_shipped_finds_nothing_here(db_session):
    """The measurement, executed beside the fix rather than asserted above it.

    If a later change drops the title again, the test above goes red and this
    one stays green, which names the cause instead of leaving somebody to find
    it a second time.
    """
    owner = await _owner(db_session)
    await _item(db_session, owner, TITLE, CONTENT, fts="content")

    rows = await _sparse_signal(
        db_session, owner_id=owner, query="sourdough", project_id=None,
        user_tokens=[], limit=8,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_the_backfill_repairs_a_row_written_before_021(db_session):
    """A pre-021 row carries a vector that is present and wrong.

    `WHERE fts IS NULL` would skip it, which is why the backfill rewrites every
    row instead.
    """
    owner = await _owner(db_session)
    stale = await _item(db_session, owner, TITLE, CONTENT, fts="content")

    before = await db_session.scalar(
        text(
            "SELECT fts @@ plainto_tsquery('english', 'sourdough') FROM embeddings"
            " WHERE id = CAST(:i AS uuid)"
        ),
        {"i": stale},
    )
    assert before is False, "the fixture is supposed to start broken"

    await _run_backfill(db_session)

    after = await db_session.scalar(
        text(
            "SELECT fts @@ plainto_tsquery('english', 'sourdough') FROM embeddings"
            " WHERE id = CAST(:i AS uuid)"
        ),
        {"i": stale},
    )
    assert after is True


@pytest.mark.asyncio
async def test_the_backfill_is_idempotent(db_session):
    """It is in _INCREMENTAL_SCHEMAS, so it runs on every test session start."""
    owner = await _owner(db_session)
    row = await _item(db_session, owner, TITLE, CONTENT, fts="content")

    await _run_backfill(db_session)
    once = await db_session.scalar(
        text("SELECT fts::text FROM embeddings WHERE id = CAST(:i AS uuid)"), {"i": row}
    )
    await _run_backfill(db_session)
    twice = await db_session.scalar(
        text("SELECT fts::text FROM embeddings WHERE id = CAST(:i AS uuid)"), {"i": row}
    )
    assert once == twice


def test_the_backfill_and_the_ingest_build_the_same_vector():
    """Three copies that cannot import each other, so assert they agree.

    Checked against the JOINED statement specifically, not against the file.
    The first version searched the whole script, and the file's second
    statement is the orphan row fallback, whose expression is literally
    `to_tsvector('english', coalesce(e.content, ''))`. So dropping the title
    from `FTS_VECTOR_SQL` left a canonical string that the fallback still
    contained, and this test passed the mutation. Caught by running it.

    Whitespace is collapsed because the SQL file wraps across its own lines.
    """
    statements = [
        " ".join(s.split())
        for s in iter_statements(_SCHEMA.read_text(encoding="utf-8"))
    ]
    # Both statements mention knowledge_items; the orphan fallback does so
    # inside its NOT EXISTS subquery. The joined backfill is the one that is
    # not that.
    joined = [
        s for s in statements
        if "FROM knowledge_items ki" in s and "NOT EXISTS" not in s
    ]
    assert len(joined) == 1, (
        f"expected exactly one joined backfill statement, found {len(joined)}"
    )
    canonical = " ".join(FTS_VECTOR_SQL.split())
    assert canonical in joined[0], (
        "database/schemas/021_fts_includes_title.sql no longer builds the vector "
        "that services/knowledge/fts.py hands the ingest paths"
    )


def test_both_ingest_paths_use_the_shared_expression():
    """No hand written copy may come back; that is what caused this."""
    for path in ("app/services/knowledge.py", "services/knowledge/pipeline.py"):
        source = (_REPO_ROOT / path).read_text(encoding="utf-8")
        assert "FTS_FILL_NEW_CHUNKS_SQL" in source, path
        assert "to_tsvector" not in source, (
            f"{path} builds its own tsvector again; use services.knowledge.fts"
        )
