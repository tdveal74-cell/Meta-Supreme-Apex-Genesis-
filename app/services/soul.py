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
    The process-wide soul layer, or None when recall cannot run.

    Switched off and switched on without a key are the same answer to a
    caller: recall is unavailable. Both return None so the API says so in
    one honest sentence that names what to set, rather than raising a
    ProviderConfigError that reaches the user as an opaque 500. This is
    also what `/soul/status` already reports, so the two agree.
    """
    if not settings.SOUL_RECALL_ENABLED or not settings.PINECONE_API_KEY:
        return None
    return SoulLayer(
        api_key=settings.PINECONE_API_KEY,
        tee_host=settings.SOUL_TEE_HOST,
        devon_host=settings.SOUL_DEVON_HOST,
    )
