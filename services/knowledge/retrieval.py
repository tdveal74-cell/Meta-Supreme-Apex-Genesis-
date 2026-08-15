"""Hybrid 4-signal retrieval with ACL and RRF fusion.

Signals: dense (pgvector), sparse (fts), rarity, age decay.
Every signal filtered by owner, project, status=ready, acl_tokens.
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
      AND (:project_id IS NULL OR e.project_id = :project_id OR ki.project_id = :project_id)
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
          ts_rank_cd(e.fts, plainto_tsquery('english', :query)) AS rank
        FROM embeddings e
        JOIN knowledge_items ki ON ki.id = e.knowledge_item_id
        WHERE {_acl_sql()}
          AND e.fts IS NOT NULL
          AND e.fts @@ plainto_tsquery('english', :query)
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


async def _rarity_and_age_pool(
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
          e.created_at,
          COALESCE((e.metadata->>'rarity')::float, 0.0) AS rarity
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
) -> List[RetrievalCandidate]:
    """Run four signals, fuse with RRF k=60, return typed candidates."""
    query = (query or "").strip()
    if not query or not query_vec:
        return []

    limit = max(1, min(int(limit), MAX_LIMIT))
    tokens = list(user_tokens or [])
    weights = signal_weights or {
        "dense": 1.0,
        "sparse": 1.0,
        "rarity": 0.35,
        "age": 0.25,
    }

    dense_rows = await _dense_signal(
        db, owner_id=owner_id, query_vec=query_vec, project_id=project_id,
        user_tokens=tokens, limit=limit,
    )
    sparse_rows = await _sparse_signal(
        db, owner_id=owner_id, query=query, project_id=project_id,
        user_tokens=tokens, limit=limit,
    )
    pool = await _rarity_and_age_pool(
        db, owner_id=owner_id, project_id=project_id,
        user_tokens=tokens, limit=limit,
    )

    dense_ids = [str(r["embedding_id"]) for r in dense_rows]
    sparse_ids = [str(r["embedding_id"]) for r in sparse_rows]
    rarity_scores = {str(r["embedding_id"]): float(r.get("rarity") or 0.0) for r in pool}
    age_scores = {str(r["embedding_id"]): _age_score(r.get("created_at")) for r in pool}
    rarity_ids = rank_map_from_scores(rarity_scores)
    age_ids = rank_map_from_scores(age_scores)

    fused = fuse_named_signals(
        {
            "dense": dense_ids,
            "sparse": sparse_ids,
            "rarity": rarity_ids[:limit],
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
                    "rarity": rarity_scores.get(emb_id, 0.0),
                    "age": age_scores.get(emb_id, 0.0),
                },
                source=row.get("source"),
                distance=dense_dist.get(emb_id),
            )
        )
    return candidates
