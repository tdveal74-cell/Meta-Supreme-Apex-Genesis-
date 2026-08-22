"""
Capture enrichment: a model suggests an Area and a summary, DEVON rules on it.

This mirrors the live lane recorded in SYS_SPEC_context-pill_v16 section B11,
where Cerebras was wired into the iPhone Inbox Capture workflow on 2026-08-22
and verified tagging a TSWS note as Podcast.

THE CONTRACT, WHICH IS THE WHOLE POINT

    A model supplied Area is never trusted.

The model is asked for an Area. Whatever it returns is validated against the
nine, and discarded if it is not one of them, falling back to keyword matching
over the same text. A confident wrong tag is worse than no tag, because a wrong
tag is permanent and silent while an absent tag is visible in the triage queue.

Verified behaviour kept: the model is allowed to decline. Given a bare UUID the
live lane returned empty and the record read that it declined, which is correct.
An enricher that always answers is an enricher that invents.

WHERE THIS LIVES AND WHY

Here, in services/intelligence, not in services/devon. The DEVON package holds a
hard guarantee that it performs no network call, enforced by a test that walks
its imports. Enrichment needs a provider, so it sits on this side of the line and
imports DEVON for validation. The dependency runs intelligence to devon, never
the reverse.

IMAGES ARE OUT OF SCOPE
Cerebras serves text models. A photo arriving as a bare identifier carries
nothing readable. That is a stated limit, not a defect, and this module refuses
rather than passing an identifier to a text model and accepting whatever comes
back.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.devon.areas import Area, canonical_labels, resolve_area
from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS = 200
MAX_INPUT_CHARS = 8000

DECLINE_TOKEN = "NONE"

ENRICHMENT_SYSTEM = f"""You tag captures for a personal knowledge system.

Return a single JSON object with exactly two keys:
  "area": one of {", ".join(canonical_labels())}, or "{DECLINE_TOKEN}"
  "summary": one short sentence, at most {MAX_SUMMARY_CHARS} characters

Rules:
- Choose the Area only when the text genuinely indicates it.
- If the text carries no usable signal, for example a bare identifier, a
  filename, or random characters, return "{DECLINE_TOKEN}" for the area.
- Never invent an Area outside the listed set.
- Declining is a correct answer. A confident wrong tag is worse than no tag.
- Reply with the JSON object and nothing else.
"""


@dataclass
class EnrichmentResult:
    """What the enricher concluded, and how it concluded it."""

    area: Optional[Area]
    area_provenance: str
    summary: str = ""
    declined: bool = False
    model_suggested_area: Optional[str] = None
    model: str = ""
    provider: str = ""
    latency_ms: int = 0
    tokens: int = 0
    error: Optional[str] = None

    @property
    def area_label(self) -> Optional[str]:
        return self.area.label if self.area else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area": self.area_label,
            "area_provenance": self.area_provenance,
            "summary": self.summary,
            "declined": self.declined,
            "model_suggested_area": self.model_suggested_area,
            "model": self.model,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "error": self.error,
        }


def _clean_summary(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    summary = " ".join(value.split())
    return summary[:MAX_SUMMARY_CHARS]


async def enrich_capture(
    text: str,
    provider: AIProvider,
    *,
    max_tokens: int = 200,
) -> EnrichmentResult:
    """Ask a provider for an Area and a summary, then rule on the answer.

    Never raises for a provider failure. A capture must still file when
    enrichment is unavailable, so a failure degrades to keyword classification
    and records the error rather than losing the capture.
    """
    body = (text or "").strip()
    if not body:
        return EnrichmentResult(
            area=None,
            area_provenance="declined, empty input",
            declined=True,
        )

    truncated = body[:MAX_INPUT_CHARS]

    request = CompletionRequest(
        messages=[ChatMessage(role="user", content=truncated)],
        system=ENRICHMENT_SYSTEM,
        max_tokens=max_tokens,
        temperature=0.0,
        json_mode=True,
    )

    try:
        response = await provider.complete(request)
    except ProviderError as exc:
        logger.warning("enrichment provider failed, falling back to keywords: %s", exc)
        area, provenance = resolve_area(None, truncated)
        return EnrichmentResult(
            area=area,
            area_provenance=f"provider failed, {provenance}",
            declined=area is None,
            error=str(exc),
        )

    suggested: Optional[str] = None
    summary = ""
    parse_failed = False
    try:
        payload = extract_json(response.text)
        raw_area = payload.get("area")
        if isinstance(raw_area, str) and raw_area.strip():
            suggested = raw_area.strip()
        summary = _clean_summary(payload.get("summary"))
    except ValueError:
        # Unparseable output is not a reason to invent a tag.
        parse_failed = True
        logger.warning("enrichment returned unparseable output, falling back to keywords")

    if suggested is None or suggested.upper() == DECLINE_TOKEN:
        # Two different facts, kept apart. A model that declined made a correct
        # judgement call. A model that produced garbage did not, and recording
        # the second as the first would hide a broken prompt or a bad model.
        area, provenance = resolve_area(None, truncated)
        if parse_failed:
            cause = "output unparseable"
        elif suggested is None:
            cause = "no area returned"
        else:
            cause = "model declined"
        return EnrichmentResult(
            area=area,
            area_provenance=f"{cause}, {provenance}",
            summary=summary,
            declined=area is None,
            model_suggested_area=None if parse_failed or suggested is None else DECLINE_TOKEN,
            model=response.model,
            provider=response.provider,
            latency_ms=response.latency_ms,
            tokens=response.usage.total_tokens,
        )

    area, provenance = resolve_area(suggested, truncated)
    return EnrichmentResult(
        area=area,
        area_provenance=provenance,
        summary=summary,
        declined=area is None,
        model_suggested_area=suggested,
        model=response.model,
        provider=response.provider,
        latency_ms=response.latency_ms,
        tokens=response.usage.total_tokens,
    )


def refuse_image_enrichment(identifier: str) -> EnrichmentResult:
    """State the limit rather than passing an identifier to a text model.

    Recorded in the pill: Cerebras cannot tag images, and a photo arriving as a
    bare UUID has nothing readable in it.
    """
    return EnrichmentResult(
        area=None,
        area_provenance=(
            f"declined, '{identifier}' is an image reference and the enrichment "
            "model is text only"
        ),
        declined=True,
    )
