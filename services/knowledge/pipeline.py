"""FKR pipeline: ingest_and_distill + query orchestration.

Keeps pure-semantic search_knowledge alive; hybrid path is additive.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge import Embedding, KnowledgeItem
from services.intelligence.providers.embeddings import create_embedding_provider
from services.knowledge.chunking import chunk_text
from services.knowledge.distillation import distill_content
from services.knowledge.retrieval import RetrievalCandidate, hybrid_retrieve
from services.knowledge.synthesis import SynthesizedAnswer, synthesize_with_governance

logger = logging.getLogger(__name__)


def _embedding_provider():
    name = getattr(settings, "DEFAULT_EMBEDDING_PROVIDER", None) or getattr(
        settings, "DEFAULT_AI_PROVIDER", "mock"
    )
    return create_embedding_provider(
        name,
        openai_api_key=getattr(settings, "OPENAI_API_KEY", None),
        model=getattr(settings, "EMBEDDING_MODEL", None),
    )


async def ingest_and_distill(
    db: AsyncSession,
    *,
    owner_id: str,
    title: str,
    content: str,
    project_id: Optional[str] = None,
    source_type: str = "manual",
    source: Optional[str] = None,
    external_id: Optional[str] = None,
    source_uri: Optional[str] = None,
    acl_tokens: Optional[Sequence[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> KnowledgeItem:
    """Stage 1-3: register item, distill, chunk, embed, store waist fields."""
    source_value = source or source_type
    item = KnowledgeItem(
        owner_id=owner_id,
        project_id=project_id,
        title=(title or "Untitled").strip()[:500],
        content=content or "",
        source_type=source_type,
        source=source_value,
        external_id=external_id,
        source_uri=source_uri,
        status="processing",
        meta=meta or {},
    )
    db.add(item)
    await db.flush()

    try:
        distilled = distill_content(
            title=item.title,
            content=content or "",
            source=source_value,
            use_llm=False,
        )
        chunks = chunk_text(
            distilled.searchable_text,
            chunk_chars=getattr(settings, "CHUNK_SIZE", 1500),
            overlap_chars=getattr(settings, "CHUNK_OVERLAP", 200),
        )
        if not chunks:
            item.status = "ready"
            item.meta = {
                **(item.meta or {}),
                "chunk_count": 0,
                "distilled": True,
                "simulated_distillation": distilled.simulated,
            }
            await db.flush()
            return item

        provider = _embedding_provider()
        embed_result = await provider.embed([c.content for c in chunks])
        vectors = embed_result.vectors
        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"embedding batch mismatch: {len(vectors)} vectors for {len(chunks)} chunks"
            )

        tokens = list(acl_tokens or [])
        for chunk, vector in zip(chunks, vectors, strict=True):
            db.add(
                Embedding(
                    knowledge_item_id=item.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=vector,
                    source=source_value,
                    owner_id=owner_id,
                    project_id=project_id,
                    acl_tokens=tokens,
                    meta={
                        "distilled": True,
                        "simulated_embeddings": getattr(provider, "name", "") == "mock",
                        "key_facts": distilled.key_facts[:5],
                    },
                )
            )

        await db.flush()
        from sqlalchemy import text as sql_text

        await db.execute(
            sql_text(
                """
                UPDATE embeddings
                SET fts = to_tsvector('english', COALESCE(content, ''))
                WHERE knowledge_item_id = :kid AND fts IS NULL
                """
            ),
            {"kid": item.id},
        )

        item.status = "ready"
        item.meta = {
            **(item.meta or {}),
            "chunk_count": len(chunks),
            "embedding_provider": getattr(provider, "name", "unknown"),
            "simulated_embeddings": getattr(provider, "name", "") == "mock",
            "simulated_distillation": distilled.simulated,
            "summary": distilled.summary,
        }
        await db.flush()
        return item
    except Exception as exc:  # noqa: BLE001
        logger.exception("fkr ingest failed item=%s", item.id)
        item.status = "failed"
        item.meta = {**(item.meta or {}), "error": str(exc)[:1000]}
        await db.flush()
        return item


async def query_knowledge(
    db: AsyncSession,
    *,
    owner_id: str,
    query: str,
    limit: int = 6,
    project_id: Optional[str] = None,
    user_tokens: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Hybrid retrieve + synthesize. Returns answer, citations, candidates."""
    provider = _embedding_provider()
    embed_result = await provider.embed([query])
    if not embed_result.vectors:
        answer = synthesize_with_governance(
            query=query, candidates=[], owner_id=owner_id
        )
        return _pack(answer, [])

    candidates = await hybrid_retrieve(
        db,
        owner_id=owner_id,
        query=query,
        query_vec=embed_result.vectors[0],
        limit=limit,
        project_id=project_id,
        user_tokens=user_tokens,
    )
    answer = synthesize_with_governance(
        query=query, candidates=candidates, owner_id=owner_id
    )
    return _pack(answer, candidates)


def _pack(answer: SynthesizedAnswer, candidates: List[RetrievalCandidate]) -> Dict[str, Any]:
    return {
        "answer": answer.answer,
        "cleared": answer.cleared,
        "refusal_reason": answer.refusal_reason,
        "simulated": answer.simulated,
        "citations": [
            {
                "index": c.index,
                "knowledge_item_id": c.knowledge_item_id,
                "title": c.title,
                "chunk_index": c.chunk_index,
                "score": c.score,
                "excerpt": c.excerpt,
            }
            for c in answer.citations
        ],
        "candidates": [
            {
                "embedding_id": c.embedding_id,
                "knowledge_item_id": c.knowledge_item_id,
                "title": c.title,
                "chunk_index": c.chunk_index,
                "score": c.score,
                "distance": c.distance,
                "signals": c.signals,
            }
            for c in candidates
        ],
    }
