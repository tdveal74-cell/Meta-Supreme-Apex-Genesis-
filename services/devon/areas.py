"""
DEVON Area vocabulary, canonical.

Source of truth on Drive: AREAS.md (Drive id 1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg),
titled "DEVON AREA VOCABULARY, canonical". ACX was ruled the ninth Area on
2026-08-20. Filename codes come from SYS_SPEC_naming-convention_v4_2026-08-22
(Drive id 1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL). Both read 2026-08-22.

Two vocabularies name the same nine Areas and they are not identical:

    vocabulary label    the word used in prose, receipts, Notion and Airtable
    filename code       the segment used in AREA_TYPE_slug_vN_DATE filenames

They diverge in exactly two places. The Podcast Area files as TSWS. The Systems
Area files as SYS. Every other Area uses one token for both. Code that assumes a
single vocabulary silently misfiles those two, which is the drift this module
exists to stop.

THE LOAD BEARING RULE
A model supplied Area is never trusted. Validate against the nine, discard
anything else, then fall back to keyword matching. Decline rather than guess: a
confident wrong tag is worse than no tag. Recorded in context pill v16 section
B11 after the enrichment lane was wired into the capture workflow, where a bare
UUID correctly produced no Area instead of an invented one.

Never add an Area without Tee's ruling. The cost of an extra Area is not the
label, it is the four place update (Notion, Airtable, the thread log skill,
Drive) and the permanent risk that one surface gets missed and the index
quietly fractures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SOURCE = {
    "drive_id": "1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg",
    "title": "AREAS.md, DEVON AREA VOCABULARY, canonical",
    "ruled": "2026-08-20",
    "read": "2026-08-22",
    "naming_codes_from": "1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL",
}


class AreaError(ValueError):
    """Raised when a token is offered as an Area and is not one of the nine."""


@dataclass(frozen=True)
class Area:
    """One of the nine canonical Areas.

    `keywords_are_canon` records whether the hint list was ruled or derived.
    Only ACX carries ruled keywords, added to two live workflows on 2026-08-22
    after ACX tagged captures were being discarded as unknown. The rest were
    derived here from the "Covers" column of AREAS.md and are a convenience for
    the fallback classifier, not canon. Treat them as adjustable.
    """

    label: str
    code: str
    covers: str
    keywords: Tuple[str, ...] = ()
    keywords_are_canon: bool = False
    ruled: str = ""


AREAS: Tuple[Area, ...] = (
    Area(
        label="TQO",
        code="TQO",
        covers="The Quiet Operator: channel, content engine, monetization",
        keywords=("tqo", "quiet operator", "the quiet operator", "monetization"),
        ruled="original",
    ),
    Area(
        label="Podcast",
        code="TSWS",
        covers="The Shadow We Share: episodes, guests, pipeline",
        keywords=(
            "podcast",
            "tsws",
            "shadow we share",
            "the shadow we share",
            "episode",
            "guest",
            "auren",
            "vespera",
        ),
        ruled="original",
    ),
    Area(
        label="NCO",
        code="NCO",
        covers="NCO Forge: military leadership channel, checklists, product line",
        keywords=("nco", "nco forge", "sergeant", "military leadership", "noncommissioned"),
        ruled="2026-08-05",
    ),
    Area(
        label="ACX",
        code="ACX",
        covers="Ascension Caudex: the micro drama IP, its canon, assets, pipeline",
        keywords=("acx", "ascension", "caudex", "archivist", "orchestrator", "folio"),
        keywords_are_canon=True,
        ruled="2026-08-20",
    ),
    Area(
        label="Health",
        code="HEALTH",
        covers="fitness, energy, medical, raw data feeds",
        keywords=("health", "fitness", "medical", "sleep", "workout", "nutrition"),
        ruled="original",
    ),
    Area(
        label="Money",
        code="MONEY",
        covers="personal finances, separate from TQO revenue",
        keywords=("money", "finance", "finances", "budget", "credit", "invoice", "tax"),
        ruled="original",
    ),
    Area(
        label="Family",
        code="FAMILY",
        covers="people and relationships",
        keywords=("family", "karrie", "relationship", "birthday", "anniversary"),
        ruled="original",
    ),
    Area(
        label="Learning",
        code="LEARNING",
        covers="skills being built, courses, study",
        keywords=("learning", "course", "study", "tutorial", "training"),
        ruled="original",
    ),
    Area(
        label="Systems",
        code="SYS",
        covers="the brain itself: Devon, the vault, the automations",
        keywords=(
            "systems",
            "devon",
            "vault",
            "n8n",
            "airtable",
            "notion",
            "automation",
            "workflow",
            "webhook",
            "pinecone",
            "doctrine",
            "filing",
        ),
        ruled="original",
    ),
)

AREA_COUNT = 9

_BY_LABEL: Dict[str, Area] = {a.label.lower(): a for a in AREAS}
_BY_CODE: Dict[str, Area] = {a.code.lower(): a for a in AREAS}

# Short forms recorded as already in use and valid by naming convention v4.
# These resolve to an Area; RES and INBOX do not, they are filing prefixes and
# are handled by services.devon.naming rather than here.
_SHORT_FORMS: Dict[str, str] = {
    "fam": "FAMILY",
    "mon": "MONEY",
    "lrn": "LEARNING",
}


def canonical_labels() -> List[str]:
    """The nine vocabulary labels, in canon order."""
    return [a.label for a in AREAS]


def canonical_codes() -> List[str]:
    """The nine filename codes, in canon order."""
    return [a.code for a in AREAS]


def get_area(token: str) -> Optional[Area]:
    """Resolve a label, a filename code, or a known short form to an Area.

    Returns None for anything else. Returning None is the correct answer for an
    invented Area and callers must treat it as a refusal, never as a default.
    """
    if not token:
        return None
    key = token.strip().lower()
    if key in _BY_LABEL:
        return _BY_LABEL[key]
    if key in _BY_CODE:
        return _BY_CODE[key]
    expanded = _SHORT_FORMS.get(key)
    if expanded:
        return _BY_CODE.get(expanded.lower())
    return None


def is_valid_area(token: str) -> bool:
    """True only for one of the nine, by label, code, or known short form."""
    return get_area(token) is not None


def normalize_label(token: str) -> Optional[str]:
    """Return the canonical vocabulary label, or None if the token is not an Area."""
    area = get_area(token)
    return area.label if area else None


def normalize_code(token: str) -> Optional[str]:
    """Return the canonical filename code, or None if the token is not an Area."""
    area = get_area(token)
    return area.code if area else None


def require_area(token: str) -> Area:
    """Resolve an Area or raise loudly.

    Used on the parsing path for receipts and captures. Canon is explicit that a
    parser must reject an unknown Area loudly rather than dropping the record
    into an untagged void.
    """
    area = get_area(token)
    if area is None:
        raise AreaError(
            f"'{token}' is not one of the nine DEVON Areas. "
            f"Valid labels: {', '.join(canonical_labels())}. "
            "Never invent a tenth. An Area is added only by Tee's ruling."
        )
    return area


def classify_with_scores(text: str) -> List[Tuple[Area, int]]:
    """Score every Area against the text by keyword hits, highest first.

    Scoring counts distinct matched keywords rather than occurrences, so a note
    repeating one word does not outrank a note touching several signals.
    """
    if not text:
        return []
    haystack = text.lower()
    scored: List[Tuple[Area, int]] = []
    for area in AREAS:
        hits = sum(1 for kw in area.keywords if kw in haystack)
        if hits:
            scored.append((area, hits))
    scored.sort(key=lambda pair: (-pair[1], pair[0].label))
    return scored


def classify(text: str) -> Optional[Area]:
    """Fallback keyword classifier. Declines rather than guesses.

    Returns None when nothing matches and when the top two Areas tie, because a
    tie carries no information and a coin flip here writes a wrong tag into the
    index permanently.
    """
    scored = classify_with_scores(text)
    if not scored:
        return None
    if len(scored) > 1 and scored[0][1] == scored[1][1]:
        return None
    return scored[0][0]


def resolve_area(supplied: Optional[str], text: str = "") -> Tuple[Optional[Area], str]:
    """The full trust ladder for an Area on an inbound capture or receipt.

    Order: a supplied Area is honoured only if it validates against the nine.
    Anything else is discarded and the text is classified by keyword. A decline
    is a legitimate outcome and is reported as such.

    Returns the Area (or None) and the provenance string naming how it was
    decided, so the caller can record it rather than assert it.
    """
    if supplied:
        area = get_area(supplied)
        if area is not None:
            return area, "supplied and validated"
        if text:
            fallback = classify(text)
            if fallback is not None:
                return fallback, f"supplied '{supplied}' rejected, keyword fallback"
            return None, f"supplied '{supplied}' rejected, keyword fallback declined"
        return None, f"supplied '{supplied}' rejected, no text to classify"
    area = classify(text)
    if area is not None:
        return area, "keyword classification"
    return None, "declined, no signal"
