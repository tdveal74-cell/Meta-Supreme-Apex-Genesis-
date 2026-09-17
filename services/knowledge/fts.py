"""The one definition of what goes into the `embeddings.fts` column.

WHY THIS FILE EXISTS

`fts` was built from the chunk's content alone, so the title was not searchable
text anywhere in this estate. A query made only of title words therefore matched
nothing at all. Measured 2026-09-17 against the shipped sparse signal, five
documents whose distinctive word lives only in the title:

    query              content only        title + content
    sourdough          0 rows              1 row, correct
    quiet operator     0 rows              1 row, correct
    vespera            0 rows              1 row, correct
    episode 14         0 rows              1 row, correct
    pruning            0 rows              1 row, correct

Zero of five against five of five. Searching for a note or an episode by its
name is a real shape here, and it returned nothing.

WHAT THIS DOES NOT BUY, BECAUSE THE FIRST DRAFT CLAIMED IT DID

It does not improve ranking. Over twelve seeded trials, nine natural language
queries and a twelve chunk corpus, folding the title in moved the shipped
configurations by +0.000 MRR, both with the mock dense signal and without it.
It lifts only the AND shaped sparse signal that was replaced the same day
(+0.096 and +0.209), which no longer runs.

An earlier draft of this file cited a lift of 0.741 to 0.767 on the no vendor
configuration. That came from ONE unseeded run, and the id ordering that breaks
ties in the rarity and age signals was doing the work. The seeded version reads
+0.000. A single draw is not a measurement, and the fact that the wobble had
already been identified in the same session did not stop it being quoted.

So the case for this change is the zero rows above, not a ranking number.

STALENESS. Nothing in this estate edits a knowledge item's title after ingest,
counted 2026-09-17: the only `.title =` assignments in `app/` and `services/`
are on conversations. If a title edit path is ever added it has to re-run the
backfill for that item, or this column goes stale silently. A trigger would
close that and is deliberately not here, because there is no path to protect
yet and an unused trigger is a thing that rots.

DRIFT. `database/schemas/021_fts_includes_title.sql` carries its own copy of
the expression below, because a migration executes SQL rather than importing
Python, and `test_fts_includes_title.py` fails if the two disagree. A backfill
that indexes rows differently from the ingest that follows it is the quiet kind
of wrong: nothing errors, and old rows and new rows answer different questions.
"""

from __future__ import annotations

#: The tsvector every row must carry. `e` is `embeddings`, `ki` is
#: `knowledge_items`. Kept as one string so the ingest paths and the backfill
#: cannot disagree about it.
FTS_VECTOR_SQL = (
    "to_tsvector('english', coalesce(ki.title, '') || ' ' || coalesce(e.content, ''))"
)

#: Fill in the rows a single ingest just wrote. Scoped to one item and to rows
#: that have no vector yet, which is what both ingest paths did before and what
#: keeps a re-ingest from rewriting chunks it did not touch.
FTS_FILL_NEW_CHUNKS_SQL = f"""
UPDATE embeddings e
SET fts = {FTS_VECTOR_SQL}
FROM knowledge_items ki
WHERE ki.id = e.knowledge_item_id
  AND e.knowledge_item_id = :kid
  AND e.fts IS NULL
"""
