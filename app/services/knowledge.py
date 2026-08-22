"""
Application-layer knowledge service.

Owns the knowledge pipeline for Meta Supreme Apex Genesis:

  UPLOAD / TEXT → CHUNK → EMBED → STORE (pgvector) → RETRIEVE

Public surface used by the rest of the app:

- search_knowledge(...)        — semantic search scoped to the owner
- retrieve_for_context(...)    — top-k chunks folded into Council context
- ingest_knowledge(...)        — persist + chunk + embed a knowledge item

Dependency direction: app → services. This module may import models and
services.*; the services layer never imports app.*.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge import Embedding, KnowledgeItem
from services.intelligence.providers.embeddings import create_embedding_provider
from services.knowledge.chunking import chunk_text

logger = logging.getLogger(__name__)


def _embedding_provider():
    """Build the configured embedding provider (OpenAI or deterministic mock)."""
    return create_embedding_provider(
        settings.DEFAULT_EMBEDDING_PROVIDER
        if hasattr(settings, "DEFAULT_EMBEDDING_PROVIDER")
        else settings.DEFAULT_AI_PROVIDER,
        openai_api_key=getattr(settings, "OPENAI_API_KEY", None),
        model=getattr(settings, "EMBEDDING_MODEL", None),
    )


async def search_knowledge(
    db: AsyncSession,
    *,
    owner_id: str,
    query: str,
    limit: int = 6,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search over the owner's knowledge base.

    Returns a list of hit dicts:
      {
        "knowledge_item_id": str,
        "title": str,
        "content": str,
        "chunk_index": int,
        "distance": float,
      }
    Ordered by ascending cosine distance (best match first).
    """
    query = (query or "").strip()
    if not query:
        return []

    limit = max(1, min(limit, 20))
    provider = _embedding_provider()
    embedding = await provider.embed([query])
    if not embedding.vectors:
        return []
    query_vec = embedding.vectors[0]

    # pgvector cosine distance operator: <=>
    # Scoped strictly to the owner. Optional project filter when provided.
    sql = text(
        """
        SELECT
            e.knowledge_item_id,
            ki.title,
            e.content,
            e.chunk_index,
            (e.embedding <=> :query_vec) AS distance
        FROM embeddings e
        JOIN knowledge_items ki ON ki.id = e.knowledge_item_id
        WHERE ki.owner_id = :owner_id
          AND ki.status = 'ready'
          AND (:project_id IS NULL OR ki.project_id = :project_id)
        ORDER BY e.embedding <=> :query_vec
        LIMIT :limit
        """
    )

    result = await db.execute(
        sql,
        {
            "query_vec": str(query_vec),
            "owner_id": owner_id,
            "project_id": project_id,
            "limit": limit,
        },
    )
    rows = result.mappings().all()
    return [
        {
            "knowledge_item_id": str(row["knowledge_item_id"]),
            "title": row["title"] or "Untitled",
            "content": row["content"] or "",
            "chunk_index": int(row["chunk_index"]),
            "distance": float(row["distance"]) if row["distance"] is not None else 1.0,
        }
        for row in rows
    ]


async def retrieve_for_context(
    db: AsyncSession,
    *,
    owner_id: str,
    message: str,
    project_id: Optional[str] = None,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve knowledge hits shaped for ContextPacket.retrieved_knowledge.

    Shape expected by the Executive Controller / synthesizer:
      {
        "knowledge_item_id": str,
        "source": str,          # title
        "content": str,
        "chunk_index": int,
        "distance": float,
      }
    """
    k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 6)
    hits = await search_knowledge(
        db, owner_id=owner_id, query=message, limit=k, project_id=project_id
    )
    return [
        {
            "knowledge_item_id": h["knowledge_item_id"],
            "source": h["title"],
            "content": h["content"],
            "chunk_index": h["chunk_index"],
            "distance": h["distance"],
        }
        for h in hits
    ]


async def ingest_knowledge(
    db: AsyncSession,
    *,
    owner_id: str,
    title: str,
    content: str,
    project_id: Optional[str] = None,
    source_type: str = "manual",
    source_uri: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> KnowledgeItem:
    """
    Ingest a text/markdown knowledge item end-to-end.

    On embedding failure the item is marked `failed` with the error in metadata
    — never silent.
    """
    item = KnowledgeItem(
        owner_id=owner_id,
        project_id=project_id,
        title=(title or "Untitled").strip()[:500],
        content=content or "",
        source_type=source_type,
        source_uri=source_uri,
        status="processing",
        meta=meta or {},
    )
    db.add(item)
    await db.flush()

    try:
        chunks = chunk_text(
            content or "",
            chunk_size=getattr(settings, "CHUNK_SIZE", 800),
            overlap=getattr(settings, "CHUNK_OVERLAP", 100),
        )
        if not chunks:
            item.status = "ready"
            item.meta = {**(item.meta or {}), "chunk_count": 0}
            await db.flush()
            return item

        provider = _embedding_provider()
        embedding = await provider.embed([c["text"] for c in chunks])
        vectors = embedding.vectors

        # strict=True: a provider that returns fewer vectors than chunks is a
        # bug, and an unstrict zip absorbs it silently — the tail of the document
        # never gets embedded, the item is still marked "ready", and the missing
        # content simply never turns up in a search. Better to raise here.
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                Embedding(
                    knowledge_item_id=item.id,
                    chunk_index=idx,
                    content=chunk["text"],
                    embedding=vector,
                    token_count=chunk.get("token_count"),
                )
            )

        item.status = "ready"
        item.meta = {
            **(item.meta or {}),
            "chunk_count": len(chunks),
            "embedding_provider": getattr(provider, "name", "unknown"),
        }
        await db.flush()
        return item

    except Exception as exc:  # noqa: BLE001 — surface failure, never silent
        logger.exception("knowledge ingest failed item=%s", item.id)
        item.status = "failed"
        item.meta = {
            **(item.meta or {}),
            "error": str(exc)[:1000],
        }
        await db.flush()
        return item
