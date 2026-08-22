"""
Application-layer soul service.

Builds the configured SoulLayer from settings and hands DEVON its results as
inert data. Dependency direction is app → services; DEVON himself never
imports this — recall happens here, and `Devon.recall_answer` phrases it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.core.config import settings
from services.intelligence.soul import SoulLayer


@lru_cache
def get_soul_layer() -> Optional[SoulLayer]:
    """
    The process-wide soul layer, or None when recall is switched off.

    Misconfiguration fails loudly: enabled without a key raises rather than
    silently degrading — SoulLayer's own constructor enforces that.
    """
    if not settings.SOUL_RECALL_ENABLED:
        return None
    return SoulLayer(
        api_key=settings.PINECONE_API_KEY or "",
        tee_host=settings.SOUL_TEE_HOST,
        devon_host=settings.SOUL_DEVON_HOST,
    )
