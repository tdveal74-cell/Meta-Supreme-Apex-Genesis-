#!/usr/bin/env python3
"""Measure retrieval quality on a REAL corpus, against labelled questions.

WHY THIS EXISTS

Every retrieval number this estate has came from a twelve document corpus a
session wrote itself, with queries written to have obvious answers. That shows a
direction and it does not show a magnitude. Tee ruled on 2026-09-17 to measure
on his own material before funding an embedding vendor, and this is the thing
that measures it.

WHAT IT NEEDS FROM A HUMAN, AND WHY IT CANNOT INVENT IT

Labels. Retrieval quality is "did the right chunk come back", and only someone
who knows the corpus can say which chunk is right. So this takes a JSON file of
questions paired with what should answer them, and REFUSES to run without one.
A version that scored itself against its own guesses would produce a number
with nothing behind it, which is worse than no number.

    [
      {"query": "what did I decide about faceless branding",
       "expect_title_contains": "NCO Forge"},
      {"query": "how does the render lane make the voice",
       "expect_item_id": "3f1c...-...."}
    ]

Either key works. `expect_title_contains` is matched case insensitively against
the knowledge item's title; `expect_item_id` is exact. A label that matches no
item in the corpus is reported as a broken label rather than a miss, because
those are different problems and averaging them together hides both.

WHAT IT CANNOT TELL YOU

Whether REAL embeddings would help. Every vector already in the database was
written by whatever provider resolved at ingest, and this estate's
`EMBEDDING_PROVIDER` defaults to `mock`. So the dense signal measured here is
the mock hashed bag of words, not a semantic model. Measuring a real provider
on a real corpus requires embedding that corpus with it first, which is the
spend the measurement was meant to inform. That is a genuine circularity and
this script will not paper over it: it reports what fraction of the corpus
carries simulated vectors so the reader knows what the dense column is.

IT WRITES NOTHING. Reads only, and it never prints chunk content, only titles
and ids, so a run can be pasted into a thread without leaking the corpus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from services.intelligence.providers.embeddings import (  # noqa: E402
    create_embedding_provider,
)
from services.knowledge.retrieval import hybrid_retrieve  # noqa: E402

#: Weight sets compared on every run. `dense` at 0.0 drops the embedding signal
#: entirely, which is the no vendor configuration.
CONFIGURATIONS: Dict[str, Dict[str, float]] = {
    "all four signals": {"dense": 1.0, "sparse": 1.0, "rarity": 0.35, "age": 0.25},
    "no dense signal": {"dense": 0.0, "sparse": 1.0, "rarity": 0.35, "age": 0.25},
    "dense signal only": {"dense": 1.0, "sparse": 0.0, "rarity": 0.0, "age": 0.0},
    "lexical signal only": {"dense": 0.0, "sparse": 1.0, "rarity": 0.0, "age": 0.0},
}


def _load_labels(path: pathlib.Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f"{path} must be a non-empty JSON list of labelled queries")
    for entry in raw:
        if not entry.get("query"):
            raise SystemExit(f"a label is missing its 'query': {entry!r}")
        if not (entry.get("expect_title_contains") or entry.get("expect_item_id")):
            raise SystemExit(
                "every label needs expect_title_contains or expect_item_id: "
                f"{entry['query']!r}"
            )
    return raw


async def _corpus_shape(db, owner_id: str) -> Dict[str, Any]:
    row = (
        await db.execute(
            text(
                """
                SELECT
                  count(DISTINCT ki.id)                       AS items,
                  count(e.id)                                 AS chunks,
                  count(e.embedding)                          AS with_vector,
                  count(e.fts)                                AS with_fts,
                  count(DISTINCT ki.id) FILTER (
                      WHERE ki.metadata ->> 'simulated_embeddings' = 'true'
                  )                                           AS simulated_items,
                  count(DISTINCT ki.id) FILTER (
                      WHERE ki.status <> 'ready'
                  )                                           AS not_ready
                FROM knowledge_items ki
                LEFT JOIN embeddings e ON e.knowledge_item_id = ki.id
                WHERE ki.owner_id = CAST(:o AS uuid)
                """
            ),
            {"o": owner_id},
        )
    ).mappings().one()
    return dict(row)


async def _resolve_label(db, owner_id: str, label: Dict[str, Any]) -> Optional[str]:
    """The knowledge item a label points at, or None if it points at nothing."""
    if label.get("expect_item_id"):
        found = await db.scalar(
            text(
                "SELECT id::text FROM knowledge_items"
                " WHERE owner_id = CAST(:o AS uuid) AND id = CAST(:i AS uuid)"
            ),
            {"o": owner_id, "i": label["expect_item_id"]},
        )
        return found
    return await db.scalar(
        text(
            "SELECT id::text FROM knowledge_items"
            " WHERE owner_id = CAST(:o AS uuid) AND title ILIKE :pat"
            " ORDER BY updated_at DESC LIMIT 1"
        ),
        {"o": owner_id, "pat": f"%{label['expect_title_contains']}%"},
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=pathlib.Path, help="JSON file of labelled queries")
    parser.add_argument("--database-url", required=True, help="postgresql+asyncpg://...")
    parser.add_argument("--owner-id", required=True, help="the owner whose corpus to read")
    parser.add_argument("--limit", type=int, default=8, help="candidates per query")
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    engine = create_async_engine(args.database_url)
    session = async_sessionmaker(engine, expire_on_commit=False)
    provider = create_embedding_provider("mock")

    async with session() as db:
        shape = await _corpus_shape(db, args.owner_id)
        if not shape["chunks"]:
            print(f"REFUSED: owner {args.owner_id} has no chunks in this database.")
            print("Nothing to measure. Check the owner id and the database url.")
            return 2

        print("corpus")
        print(f"  knowledge items          {shape['items']}")
        print(f"  chunks                   {shape['chunks']}")
        print(f"  chunks with a vector     {shape['with_vector']}")
        print(f"  chunks with an fts       {shape['with_fts']}")
        print(f"  items marked simulated   {shape['simulated_items']}")
        print(f"  items not 'ready'        {shape['not_ready']}")
        if shape["simulated_items"]:
            print("  NOTE: simulated vectors are the mock hashed bag of words.")
            print("        The dense column below is not a semantic model.")
        print()

        resolved: List[Dict[str, Any]] = []
        broken: List[str] = []
        for label in labels:
            item_id = await _resolve_label(db, args.owner_id, label)
            if item_id is None:
                broken.append(label["query"])
            else:
                resolved.append({**label, "item_id": item_id})

        if broken:
            print(f"{len(broken)} label(s) point at nothing in this corpus:")
            for query in broken:
                print(f"  {query}")
            print("  A broken label is not a miss. Fix or drop these, then re-run.")
            print()
        if not resolved:
            print("REFUSED: no label resolved to an item. Nothing measured.")
            return 2

        results: Dict[str, List[Optional[int]]] = {}
        for name, weights in CONFIGURATIONS.items():
            ranks: List[Optional[int]] = []
            for label in resolved:
                vector = (await provider.embed([label["query"]])).vectors[0]
                candidates = await hybrid_retrieve(
                    db,
                    owner_id=args.owner_id,
                    query=label["query"],
                    query_vec=vector,
                    limit=args.limit,
                    signal_weights=weights,
                )
                order = [str(c.knowledge_item_id) for c in candidates]
                seen: List[str] = []
                for item in order:  # rank by item, not by chunk
                    if item not in seen:
                        seen.append(item)
                ranks.append(
                    seen.index(label["item_id"]) + 1
                    if label["item_id"] in seen
                    else None
                )
            results[name] = ranks

        width = max(len(n) for n in CONFIGURATIONS)
        print(f"{len(resolved)} labelled queries, limit {args.limit}")
        print(f"{'configuration':<{width}} {'MRR':>7} {'top1':>7} {'found':>7}")
        print("-" * (width + 24))
        for name, ranks in results.items():
            mrr = sum(1.0 / r for r in ranks if r) / len(ranks)
            top1 = sum(1 for r in ranks if r == 1)
            found = sum(1 for r in ranks if r)
            print(f"{name:<{width}} {mrr:>7.3f} {top1:>3}/{len(ranks):<3} {found:>3}/{len(ranks):<3}")
        print()
        print("per query rank, lower is better, '-' is not found in the top "
              f"{args.limit}")
        print(f"{'query':<52} " + " ".join(f"{n[:11]:>11}" for n in CONFIGURATIONS))
        for index, label in enumerate(resolved):
            cells = " ".join(
                f"{str(results[n][index] or '-'):>11}" for n in CONFIGURATIONS
            )
            print(f"{label['query'][:52]:<52} {cells}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
