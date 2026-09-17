-- 021: the full text column indexes the title as well as the chunk.
--
-- `embeddings.fts` was built from `content` alone, so a knowledge item's title
-- was not searchable text anywhere in this estate, and a query made only of
-- title words matched nothing. Measured 2026-09-17 against the shipped sparse
-- signal, five documents whose distinctive word lives only in the title:
--
--     query              content only   title + content
--     sourdough          0 rows         1 row, correct
--     quiet operator     0 rows         1 row, correct
--     vespera            0 rows         1 row, correct
--     episode 14         0 rows         1 row, correct
--     pruning            0 rows         1 row, correct
--
-- Zero of five against five of five. Searching for a note or an episode by its
-- name is a real shape here, and it returned nothing.
--
-- This does NOT improve ranking, and an earlier draft of this file said it did.
-- Over twelve seeded trials and nine natural language queries it moves the
-- shipped configurations by +0.000 MRR. It lifts only the AND shaped sparse
-- signal replaced the same day. The case for this migration is the zero rows,
-- not a ranking number.
--
-- The expression below is the same one `services/knowledge/fts.py` gives the
-- two ingest paths, and `test_fts_includes_title.py` fails if they drift. A
-- backfill that indexes rows differently from the ingest that follows it is the
-- quiet kind of wrong: nothing errors, and old rows and new rows answer
-- different questions.
--
-- Re-runnable by construction: it rewrites every row from current data, so
-- running it twice gives the same result as running it once. It rewrites ALL
-- rows rather than only the NULL ones, because rows written before this change
-- carry a vector that is present and wrong, which `WHERE fts IS NULL` would
-- skip. On a large table this holds a write lock on `embeddings` for the
-- duration; this estate's table is small enough that batching is not worth it,
-- and a batched version would need its own progress marker to stay re-runnable.

UPDATE embeddings e
SET fts = to_tsvector('english', coalesce(ki.title, '') || ' ' || coalesce(e.content, ''))
FROM knowledge_items ki
WHERE ki.id = e.knowledge_item_id;

-- A chunk whose item row is gone should not exist, since the FK cascades, but
-- the UPDATE above joins, so such a row would keep a stale vector and never be
-- noticed. Give it one built from the content it does have.
UPDATE embeddings e
SET fts = to_tsvector('english', coalesce(e.content, ''))
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_items ki WHERE ki.id = e.knowledge_item_id
);
