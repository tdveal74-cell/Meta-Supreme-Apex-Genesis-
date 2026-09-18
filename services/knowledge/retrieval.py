"""Hybrid retrieval with ACL and RRF fusion, and a floor that can refuse.

Signals: dense (pgvector), sparse (fts), age decay. Every one filtered by
owner, project, status=ready, acl_tokens.

IT WAS FOUR SIGNALS AND IT COULD NOT REFUSE ANYTHING.

Measured 2026-09-17. `rarity` read `metadata->>'rarity'`, which nothing in this
repository has ever written, so it was 0.0 on every row. `rank_map_from_scores`
sorts equal scores by id, so a signal carrying weight 0.35 was ranking
documents by their UUID.

`age` is real but reads no query at all: `_recent_pool` is
`ORDER BY created_at DESC LIMIT 30`. So two of the four signals never saw the
question, and together they supplied a full pool for every query. Nothing could
return empty, and `synthesize_with_cross_encoder` refuses only on an empty
pool, so its documented rule of "No candidates -> explicit refusal (never
fabricate)" was unreachable. `POST /knowledge/query` answered
`xylophone quagmire zeppelin` with `cleared: True` and three citations,
identical in shape to a question it could actually answer.

THE FLOOR IS A RULE ABOUT WHO MAY INTRODUCE A CANDIDATE, NOT A THRESHOLD.

Only a signal that read the query may put a document into the pool. `age` now
reorders what dense and sparse found and can no longer add to it, and `rarity`
is gone rather than kept at weight zero, because dead code that looks like a
working signal is how this was missed. No number had to be invented, which
matters: a threshold nobody measured is a guess, and RRF scores are not
calibrated across corpus sizes anyway.

AND DENSE ONLY COUNTS WHEN ITS PROVIDER CAN CARRY A VERDICT.

Tee ruled this on 2026-09-16 for episode coverage and the same measurement
governs here: under MockEmbeddingProvider a sourdough recipe scored 0.6406
against the jobs episode while an on topic question scored 0.6170. Distances
that rank an unrelated document higher cannot decide whether anything was
found. So `dense_is_trusted` defaults to FALSE and the dense query does not
run without it, which fails closed in the same direction as
`app.services.episodes.TRUSTED_FOR_COVERAGE`. On this estate today that leaves
the lexical signal as the only thing that can introduce a candidate, which is
an honest description of what actually works.

`query_vec` is still required even when it goes unused, and that is worth
fixing separately: it makes every query pay for an embedding call whose result
is then discarded. Left alone here to keep one behavioural change to reason
about.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.knowledge.rrf import fuse_named_signals, rank_map_from_scores

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 8
MAX_LIMIT = 40
AGE_HALFLIFE_DAYS = 90.0


@dataclass
class RetrievalCandidate:
    embedding_id: str
    knowledge_item_id: str
    title: str
    content: str
    chunk_index: int
    score: float
    signals: Dict[str, float]
    source: Optional[str] = None
    distance: Optional[float] = None


def _acl_sql() -> str:
    return """
      e.owner_id = :owner_id
      AND (e.acl_tokens = '{}' OR e.acl_tokens && CAST(:user_tokens AS text[]))
      AND (CAST(:project_id AS uuid) IS NULL
           OR e.project_id = CAST(:project_id AS uuid)
           OR ki.project_id = CAST(:project_id AS uuid))
      AND ki.status = 'ready'
    """


async def _dense_signal(
    db: AsyncSession,
    *,
    owner_id: str,
    query_vec: Sequence[float],
    project_id: Optional[str],
    user_tokens: Sequence[str],
    limit: int,
) -> List[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT
          e.id AS embedding_id,
          e.knowledge_item_id,
          ki.title,
          e.content,
          e.chunk_index,
          e.source,
          (e.embedding <=> :query_vec) AS distance
        FROM embeddings e
        JOIN knowledge_items ki ON ki.id = e.knowledge_item_id
        WHERE {_acl_sql()}
          AND e.embedding IS NOT NULL
        ORDER BY e.embedding <=> :query_vec
        LIMIT :limit
        """
    )
    result = await db.execute(
        sql,
        {
            "query_vec": str(list(query_vec)),
            "owner_id": owner_id,
            "project_id": project_id,
            "user_tokens": list(user_tokens) if user_tokens else [],
            "limit": limit,
        },
    )
    return [dict(row) for row in result.mappings().all()]


# plainto_tsquery ANDs every lexeme it produces, so `how do I fix my resume`
# becomes 'fix' & 'resum' and only matches a chunk carrying BOTH words. A
# natural language question almost never clears that bar, which is how the
# lexical leg of this retriever came to return nothing on four of five
# realistic queries while nobody noticed. Measured 2026-09-17 on a seeded
# corpus: the shipped AND form reached the known relevant chunk 1 time in 5.
#
# The fix is the operator, not the parser. plainto_tsquery still does the
# sanitising, so quotes, backslashes and tsquery operators in the user's text
# are stripped before this ever sees them; the replace then only swaps the
# conjunction. Measured against hostile input on the same day:
#   resume & ! job | (x)    ->  'resum' | 'job' | 'x'
#   resume \ job':;drop      ->  'resum' | 'job' | 'drop'
# plainto_tsquery emits no operator other than ` & ` between top level
# lexemes, including for hyphenated words, so the swap is total.
#
# OR does not cost precision here because ts_rank_cd still ranks by how much
# of the query matched and how close the matches sit, so a chunk carrying
# every term outranks one carrying a single term. RRF consumes the rank, not
# the score. Do not "tighten" this back to AND without re-running the
# measurement: AND is not stricter, it is silent.
_OR_TSQUERY = (
    "replace(plainto_tsquery('english', :query)::text, ' & ', ' | ')::tsquery"
)


async def _sparse_signal(
    db: AsyncSession,
    *,
    owner_id: str,
    query: str,
    project_id: Optional[str],
    user_tokens: Sequence[str],
    limit: int,
) -> List[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT
          e.id AS embedding_id,
          e.knowledge_item_id,
          ki.title,
          e.content,
          e.chunk_index,
          e.source,
          ts_rank_cd(e.fts, {_OR_TSQUERY}) AS rank
        FROM embeddings e
        JOIN knowledge_items ki ON ki.id = e.knowledge_item_id
        WHERE {_acl_sql()}
          AND e.fts IS NOT NULL
          AND e.fts @@ {_OR_TSQUERY}
        ORDER BY rank DESC
        LIMIT :limit
        """
    )
    result = await db.execute(
        sql,
        {
            "query": query,
            "owner_id": owner_id,
            "project_id": project_id,
            "user_tokens": list(user_tokens) if user_tokens else [],
            "limit": limit,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def _recent_pool(
    db: AsyncSession,
    *,
    owner_id: str,
    project_id: Optional[str],
    user_tokens: Sequence[str],
    limit: int,
) -> List[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT
          e.id AS embedding_id,
          e.knowledge_item_id,
          ki.title,
          e.content,
          e.chunk_index,
          e.source,
          e.created_at
        FROM embeddings e
        JOIN knowledge_items ki ON ki.id = e.knowledge_item_id
        WHERE {_acl_sql()}
        ORDER BY e.created_at DESC
        LIMIT :limit
        """
    )
    result = await db.execute(
        sql,
        {
            "owner_id": owner_id,
            "project_id": project_id,
            "user_tokens": list(user_tokens) if user_tokens else [],
            "limit": max(limit * 3, 30),
        },
    )
    return [dict(row) for row in result.mappings().all()]


def _age_score(created_at: Any, *, now: Optional[datetime] = None) -> float:
    if created_at is None:
        return 0.0
    now = now or datetime.now(timezone.utc)
    if getattr(created_at, "tzinfo", None) is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / AGE_HALFLIFE_DAYS)


async def hybrid_retrieve(
    db: AsyncSession,
    *,
    owner_id: str,
    query: str,
    query_vec: Sequence[float],
    limit: int = DEFAULT_LIMIT,
    project_id: Optional[str] = None,
    user_tokens: Optional[Sequence[str]] = None,
    signal_weights: Optional[Dict[str, float]] = None,
    dense_is_trusted: bool = False,
) -> List[RetrievalCandidate]:
    """Fuse the signals that read the query, let age reorder them, or refuse.

    Returns [] when no signal that read the query found anything, which is what
    makes the synthesizer's "never fabricate" refusal reachable. See the module
    docstring for why that was impossible until 2026-09-17.

    `dense_is_trusted` defaults False and gates the pgvector query entirely.
    The caller knows which provider produced `query_vec`; this function does
    not, and guessing in the permissive direction is what the 0.6406 against
    0.6170 measurement rules out.
    """
    query = (query or "").strip()
    if not query or not query_vec:
        return []

    limit = max(1, min(int(limit), MAX_LIMIT))
    tokens = list(user_tokens or [])
    weights = signal_weights or {
        "dense": 1.0,
        "sparse": 1.0,
        "age": 0.25,
    }

    # Not run at all on an untrusted provider, rather than run and down
    # weighted. A distance that ranks a sourdough recipe above an on topic
    # question is not a weak signal, it is a wrong one, and it also saves the
    # pgvector scan.
    dense_rows = (
        await _dense_signal(
            db, owner_id=owner_id, query_vec=query_vec, project_id=project_id,
            user_tokens=tokens, limit=limit,
        )
        if dense_is_trusted
        else []
    )
    sparse_rows = await _sparse_signal(
        db, owner_id=owner_id, query=query, project_id=project_id,
        user_tokens=tokens, limit=limit,
    )

    dense_ids = [str(r["embedding_id"]) for r in dense_rows]
    sparse_ids = [str(r["embedding_id"]) for r in sparse_rows]

    # THE FLOOR. Only a signal that read the query may introduce a candidate,
    # so when none of them found anything there is nothing to rank and the
    # honest answer is none rather than the newest thirty rows.
    introduced = set(dense_ids) | set(sparse_ids)
    if not introduced:
        return []

    pool = await _recent_pool(
        db, owner_id=owner_id, project_id=project_id,
        user_tokens=tokens, limit=limit,
    )
    age_scores = {
        str(r["embedding_id"]): _age_score(r.get("created_at"))
        for r in pool
        if str(r["embedding_id"]) in introduced
    }
    age_ids = rank_map_from_scores(age_scores)

    fused = fuse_named_signals(
        {
            "dense": dense_ids,
            "sparse": sparse_ids,
            "age": age_ids[:limit],
        },
        k=60,
        weights=weights,
    )

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in dense_rows + sparse_rows + pool:
        by_id[str(row["embedding_id"])] = row

    dense_dist = {
        str(r["embedding_id"]): float(r["distance"])
        for r in dense_rows
        if r.get("distance") is not None
    }

    candidates: List[RetrievalCandidate] = []
    for emb_id, score in fused[:limit]:
        row = by_id.get(emb_id)
        if not row:
            continue
        candidates.append(
            RetrievalCandidate(
                embedding_id=emb_id,
                knowledge_item_id=str(row["knowledge_item_id"]),
                title=row.get("title") or "Untitled",
                content=row.get("content") or "",
                chunk_index=int(row.get("chunk_index") or 0),
                score=float(score),
                signals={
                    "dense": 1.0 if emb_id in dense_ids else 0.0,
                    "sparse": 1.0 if emb_id in sparse_ids else 0.0,
                    "age": age_scores.get(emb_id, 0.0),
                },
                source=row.get("source"),
                distance=dense_dist.get(emb_id),
            )
        )
    return candidates
