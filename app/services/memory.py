"""
Application-layer memory service.

Memory in Meta Supreme is transparent, editable, pausable, and hard-deletable.
It is never a black box.

Public surface used by the rest of the app:

- recall_memories(...)              — lexical recall into Council context
- persist_memory_candidates(...)    — write Council-suggested memories after an exchange

CRUD endpoints live in the API layer and operate on the Memory model directly;
this module owns the intelligence-facing recall and persistence paths.

Recall scoring (Phase 5 lexical):
  score = keyword_overlap × importance × recency_factor

Embedding-based recall is a documented Phase 6+ upgrade (needs a vector column
on memories via migration).
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.memory import Memory
from services.intelligence import SynthesisResult

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _recency_factor(created_at: Optional[datetime], now: datetime) -> float:
    """
    Soft exponential decay over ~30 days.
    Fresh memories stay near 1.0; 30-day-old memories ~0.5; older still usable.
    """
    if created_at is None:
        return 0.7
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return math.exp(-age_days / 30.0)


async def recall_memories(
    db: AsyncSession,
    *,
    user_id: str,
    message: str,
    project_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Lexical recall of active memories relevant to the current message.

    Returns a list shaped for ContextPacket.retrieved_memories:
      {
        "memory_id": str,
        "content": str,
        "memory_type": str,
        "importance": int,
        "score": float,
      }
    """
    top_k = limit or getattr(settings, "MEMORY_RECALL_TOP_K", 5)
    query_tokens = _tokenize(message)
    if not query_tokens:
        return []

    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id)
        .where(Memory.is_active.is_(True))
    )
    if project_id:
        # Prefer project-scoped memories, but still allow user-global ones
        stmt = stmt.where(
            (Memory.project_id == project_id) | (Memory.project_id.is_(None))
        )

    result = await db.execute(stmt.order_by(Memory.created_at.desc()).limit(200))
    candidates = list(result.scalars().all())
    if not candidates:
        return []

    now = datetime.now(timezone.utc)
    scored: List[tuple[float, Memory]] = []

    for mem in candidates:
        mem_tokens = _tokenize(mem.content)
        if not mem_tokens:
            continue
        overlap = len(query_tokens & mem_tokens)
        if overlap == 0:
            continue
        importance = max(1, min(10, int(mem.importance or 5)))
        recency = _recency_factor(mem.created_at, now)
        score = overlap * (importance / 10.0) * recency
        scored.append((score, mem))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    out: List[Dict[str, Any]] = []
    for score, mem in scored[:top_k]:
        out.append(
            {
                "memory_id": str(mem.id),
                "content": mem.content,
                "memory_type": mem.memory_type,
                "importance": int(mem.importance or 5),
                "score": round(score, 4),
            }
        )
    return out


#: The memories.memory_type CHECK constraint, mirrored — anything else is
#: recorded as 'other' rather than failing the whole exchange.
_ALLOWED_MEMORY_TYPES = frozenset(
    {"preference", "context", "decision", "lesson", "pattern", "other"}
)


async def persist_memory_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: Optional[str],
    conversation_id: Optional[str],
    message: str,
    result: SynthesisResult,
) -> List[Memory]:
    """
    Persist the Council's memory-update candidates as real Memory rows.

    Candidates come from SynthesisResult.memory_updates (list of dicts or strings).
    Each is stored with origin metadata so the user can see, edit, pause, or delete it.
    """
    candidates = getattr(result, "memory_updates", None) or []

    written: List[Memory] = []
    for raw in candidates[:5]:  # hard ceiling per exchange
        if isinstance(raw, str):
            content = raw.strip()
            memory_type = "context"
            importance = 5
        elif isinstance(raw, dict):
            content_raw = raw.get("content") or raw.get("text")
            if not isinstance(content_raw, str):
                # Structured machine summaries (e.g. the controller's
                # interaction_summary candidate carries a dict) are not
                # user-readable memories — never persist their repr.
                continue
            content = content_raw.strip()
            memory_type = str(raw.get("memory_type") or raw.get("type") or "context")
            try:
                importance = int(raw.get("importance", 5))
            except (TypeError, ValueError):
                importance = 5
        else:
            continue

        if not content:
            continue
        if memory_type not in _ALLOWED_MEMORY_TYPES:
            memory_type = "other"  # the schema CHECK is the vocabulary

        importance = max(1, min(10, importance))
        memory = Memory(
            user_id=user_id,
            project_id=project_id,
            memory_type=memory_type[:64],
            content=content[:4000],
            importance=importance,
            is_active=True,
            meta={
                "origin": "council_interaction",
                "conversation_id": conversation_id,
                "request_id": getattr(result, "request_id", None),
                "intent": getattr(getattr(result, "intent", None), "value", None),
            },
        )
        db.add(memory)
        written.append(memory)

    if not written:
        # Fallback: still capture a light context memory from the exchange so
        # future recall has something to work with. Low-importance, labeled.
        snippet = (message or "").strip()
        if not snippet:
            return []
        memory = Memory(
            user_id=user_id,
            project_id=project_id,
            memory_type="context",
            content=f"Discussed: {snippet[:280]}",
            importance=4,
            is_active=True,
            meta={
                "origin": "council_interaction",
                "conversation_id": conversation_id,
                "request_id": getattr(result, "request_id", None),
                "intent": getattr(getattr(result, "intent", None), "value", None),
            },
        )
        db.add(memory)
        written.append(memory)

    if written:
        await db.flush()
        for m in written:
            await db.refresh(m)

    return written
