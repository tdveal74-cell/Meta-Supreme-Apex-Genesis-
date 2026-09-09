"""The call site for capture enrichment, which is the half DCD-07 said was missing.

`services/intelligence/enrichment.py` has held `enrich_capture` and sixteen tests
since the Hermes arc, and `app/services/intelligence.py` has held
`get_enrichment_provider`, and until this module landed nothing outside those
tests called either one. So `ENRICHMENT_PROVIDER=cerebras` configured a provider
that no capture ever reached. The audit raised that on 2026-09-02 as DCD-07 and
`docs/devon/DEVON.md` was amended on 2026-09-09 to state the capability and the
behavior separately rather than let the variable imply a lane that did not run.

WHAT THIS MODULE IS FOR

One place where a suggestion is asked for, so there is one thing to reason about
rather than a copy in each lane. Two lanes call it: the chat command route in
`app/api/v1/devon.py` and `KnowledgeLoop.propose` in
`app/services/knowledge_loop.py`.

THE TWO RULES IT KEEPS

A suggestion is never an authority. Whatever comes back is handed to
`Devon.ask(..., suggested_area=...)`, which passes it to `resolve_area`, which
validates it against the nine and falls back to keywords when it does not hold
up. That ladder is unchanged by this module; all this module does is make the
first rung reachable.

A capture files whether or not enrichment works. Every failure path here returns
None and the capture proceeds on keyword classification, which is exactly what
happened before this module existed. `enrich_capture` already degrades that way
for a `ProviderError`, but the metered wrapper around a provider can raise
things that are not one: `ProviderSpendCapExceeded` extends `AppError`, the cap
check and the usage record are database round trips that can raise
`sqlalchemy.exc.DBAPIError`, and a socket can raise `ConnectionRefusedError`
straight through. So the guard here is broad on purpose. `asyncio.CancelledError`
is a `BaseException` and is deliberately not caught: a cancelled request should
stay cancelled.

NO TIMEOUT WRAPPER HERE, ON PURPOSE

`get_enrichment_provider` already builds the provider with
`min(AI_TIMEOUT_SECONDS, 30.0)`, so the bound exists one layer down. Adding an
`asyncio.wait_for` on top would time out the await while
`MeteredProvider.complete` holds its usage write inside an `asyncio.shield`
(`app/services/provider_usage.py:258`), leaving a detached database write behind
a request that has already returned. One bound, in the place that owns the
socket.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from services.devon.assistant import Devon
from services.intelligence.enrichment import EnrichmentResult, enrich_capture
from services.intelligence.providers.base import AIProvider

logger = logging.getLogger(__name__)

#: Providers whose tag would be theatre. The mock provider does not read the
#: capture: for a JSON request it fabricates a value per declared key
#: (`services/intelligence/providers/mock_provider.py:136`), so its "area" is a
#: topic string that `resolve_area` discards on the next line. Asking it costs a
#: metered call and two database round trips for an answer already known to be
#: worthless, so the offline lane is left exactly as it was before this module.
#: Gating here rather than on a new flag is also what makes DEVON.md's sentence
#: true as written: setting ENRICHMENT_PROVIDER to a real provider is what turns
#: capture tagging on.
NON_ENRICHING_PROVIDERS = frozenset({"mock"})

#: Pure. `area_suggestion_text` only parses, so one instance is shared rather
#: than built per call. It holds an ApprovalQueue it never uses on this path.
_DEVON = Devon()


def enrichment_is_configured() -> bool:
    """Whether asking a provider for an Area is worth a call at all."""
    return settings.ENRICHMENT_PROVIDER not in NON_ENRICHING_PROVIDERS


async def suggest_area(
    utterance: str, *, provider: Optional[AIProvider] = None
) -> Optional[EnrichmentResult]:
    """Ask for an Area for `utterance`, or return None having spent nothing.

    `provider` is for tests, which must not reach the cached factory: the real
    one wraps every provider in `MeteredProvider`, whose cap check and usage
    record both touch the database. Passing one also bypasses the
    NON_ENRICHING_PROVIDERS gate, because a test that injects a provider has
    said which provider it means.

    Returns None when there is nothing worth asking about, when enrichment is
    not configured, or when the call failed. None means "no suggestion", which
    is the same input `Devon.ask` received before this lane existed, so the
    caller needs no separate failure branch.
    """
    tag_this = _DEVON.area_suggestion_text(utterance)
    if tag_this is None:
        # Not a capture, or a capture whose Area the intent already fixes, or an
        # empty payload. Deciding this before the call is the point of that
        # method existing: a query costs nothing.
        return None

    if provider is None:
        if not enrichment_is_configured():
            return None
        # Imported here rather than at module import: the factory reads settings
        # and is lru_cached, and binding it at import time would freeze the
        # provider for the process before a test could touch the setting.
        from app.services.intelligence import get_enrichment_provider

        try:
            provider = get_enrichment_provider()
        except Exception:
            logger.warning(
                "enrichment provider could not be built, capture files on keywords",
                exc_info=True,
            )
            return None

    try:
        result = await enrich_capture(tag_this, provider)
    except Exception:
        # enrich_capture swallows ProviderError itself. Everything above it in
        # the metered stack can still raise, and none of it is worth losing a
        # capture over.
        logger.warning(
            "capture enrichment failed, capture files on keywords", exc_info=True
        )
        return None

    # The summary half of the result has no destination in the filing plan, so
    # it is logged here and written into the PLAN_CREATED payload by the
    # knowledge loop. Without this line a generated summary would be produced,
    # paid for and dropped on the floor with nothing recording that it existed.
    logger.info("capture enrichment: %s", result.to_dict())
    return result
