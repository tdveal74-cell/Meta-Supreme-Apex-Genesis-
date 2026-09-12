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
from typing import Any, Dict, Optional

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
    """Whether asking a provider for an Area is worth a call at all.

    Normalised the same way `create_provider` normalises it
    (`services/intelligence/providers/factory.py:41`, `.strip().lower()`),
    because a gate that disagrees with the factory is worse than no gate. A
    fresh critic measured it on 2026-09-09: with `ENRICHMENT_PROVIDER=Mock` the
    unnormalised gate said enrich, the factory lowercased the name and built a
    MockProvider anyway, and every capture then spent a metered call and a cap
    check on an answer discarded on the next line. That is exactly the waste
    this gate exists to prevent.
    """
    return settings.ENRICHMENT_PROVIDER.strip().lower() not in NON_ENRICHING_PROVIDERS


#: Set the first time the factory hands back a provider, so a status route can
#: tell "configured" from "configured and reached at least once". A boolean
#: rather than a count: this is an observability signal, not a meter, and the
#: provider usage ledger already counts calls.
_provider_built = False


def status() -> Dict[str, Any]:
    """What this lane is set to do, and whether it has ever managed to.

    F4 from the 2026-09-09 critic: with `get_enrichment_provider` raising
    unconditionally, which is the production shape of a missing or invalid
    CEREBRAS_API_KEY, every enrichment test still passed and the only signal was
    one log warning per capture. A lane that can stop running silently is the
    shape of DCD-07 itself, so it gets a reading rather than a promise.

    `provider_built` False while `enrichment_configured` is True means the
    factory has never succeeded, or nothing has asked yet. It does not
    distinguish those two, and says so here rather than implying it does.
    """
    return {
        "enrichment_provider": settings.ENRICHMENT_PROVIDER,
        "enrichment_configured": enrichment_is_configured(),
        "provider_built": _provider_built,
        "note": (
            "configured names the setting, not a working key. provider_built "
            "False can mean the factory failed or that no capture has asked "
            "yet. Only a live readback settles which."
        ),
    }


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
    # The gate first, then the parse. `parse` is pure but not cheap: on 4000
    # characters that match no intent it runs the full fuzzy pass, measured at
    # 276 ms of blocking CPU by a critic on 2026-09-09. Asking the gate first
    # means the offline lane, where no provider is configured, pays nothing at
    # all rather than parsing twice per request. An injected provider still
    # bypasses the gate: a test that passes one has said which it means.
    if provider is None and not enrichment_is_configured():
        return None

    tag_this = _DEVON.area_suggestion_text(utterance)
    if tag_this is None:
        # Not a capture, or a capture whose Area the intent already fixes, or an
        # empty payload. Deciding this before the call is the point of that
        # method existing: a query costs nothing.
        return None

    if provider is None:
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
        global _provider_built
        _provider_built = True

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

    # The summary is DEBUG, not INFO, and that split is the whole point.
    #
    # A fresh critic put a card number, a password and a medical detail into a
    # capture on 2026-09-09 and read them back out of the INFO log, quoted by
    # the model inside its own summary. Before this module existed no capture
    # content reached application logs at any level. Four of the nine Areas are
    # Health, Money, Family and Learning, so "the paraphrase of every capture,
    # wherever logs aggregate" is not an acceptable default.
    #
    # What stays at INFO is everything needed to answer "is this lane running,
    # and is it any good": the Area, how it was decided, the model, the
    # provider, the cost and the latency. None of that is the capture.
    logger.info(
        "capture enrichment: area=%s provenance=%s model=%s provider=%s "
        "tokens=%d latency_ms=%d declined=%s error=%s",
        result.area_label,
        result.area_provenance,
        result.model,
        result.provider,
        result.tokens,
        result.latency_ms,
        result.declined,
        result.error,
    )
    logger.debug("capture enrichment summary: %r", result.summary)
    return result
