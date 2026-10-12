"""The Research findings queue rules.

Research is a READ function: it finds things out and recommends, and a human
decides what to adopt. This module is the rule set for the findings log. It
holds no store and opens no connection, so nothing here can search, fetch or
act.

The house rule is that "unverified" beats a plausible invention, so a finding
cannot hide how well it is known. What it refuses:

  1. A claim or recommendation of fewer than 10 visible characters, or with em
     or en dashes or look-alikes, or a NUL byte. Quoted source text goes in the
     excerpt, which is only NUL checked because it is not ours to rewrite.
  2. An evidence kind other than source, measured or unverified, and an
     evidence reference of fewer than 10 visible characters.
  3. A source finding whose reference is not a plain https URL. A measured
     finding names the artifact or command that produced the number. An
     unverified finding says what check would settle it.
  4. Adopting an unverified finding without a note of at least 10 visible
     characters. Tee can adopt a lead, but the record must say it was adopted
     unverified.
  5. The same claim twice for one owner, whatever its state, so a repeated
     research pass cannot stack copies.
  6. A decision with no human named, or one named as an automated actor, and a
     second decision on a finding that already has one.

It never checks that a claim is true or that a URL says what the finding says
it does. It only checks the grounds were written down.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Optional

from services.company.marketing import (
    AUTOMATED_ACTORS,
    DraftStatus,
    QueueRefusal,
    _check_text,
    _visible_len,
)

EVIDENCE_KINDS = ("source", "measured", "unverified")
MIN_TEXT_CHARS = 10
MAX_REF_CHARS = 2000

# A plain https URL. This is a shape check and is NOT a fetch-safety filter: it
# lets through internal names that end in a letter TLD (a metadata hostname, a
# wildcard DNS name that resolves to a private address). Nothing here fetches.
# Whatever fetches a source later must resolve the host and refuse private
# ranges and redirects at connect time. No whitespace, angle brackets, quotes, control or invisible
# characters anywhere. Matched with fullmatch, since "$" also matches before a
# final newline.
_URL_RE = re.compile(
    r"https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}"
    r"(?::[0-9]{1,5})?"
    r"(?:[/?#][^\s<>\"'\x00-\x1f\x7f​-‏ - ⁠-⁯﻿]*)?"
)


class DuplicateFinding(QueueRefusal):
    """The owner already has this claim on record."""


@dataclass(frozen=True)
class Finding:
    draft_id: str
    claim_key: str
    claim: str
    evidence_kind: str
    evidence_ref: str
    evidence_excerpt: Optional[str]
    recommendation: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def claim_key(claim: str) -> str:
    """Identity of a claim, ignoring case, spacing and how it was encoded.

    NFKC folds a composed and a decomposed accent, and full-width forms, to one
    spelling. Invisible characters are dropped so a zero-width space cannot make
    a second copy of the same claim.
    """
    folded = unicodedata.normalize("NFKC", claim)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) not in ("Cf", "Cc") or ch.isspace())
    return hashlib.sha256(" ".join(folded.casefold().split()).encode("utf-8")).hexdigest()


def _plain_field(value: str, label: str) -> None:
    if not value or not value.strip():
        raise QueueRefusal(f"{label} is empty")
    if "\x00" in value:
        raise QueueRefusal(f"{label} contains a NUL byte")


def create_finding(
    *,
    draft_id: str,
    claim: str,
    evidence_kind: str,
    evidence_ref: str,
    evidence_excerpt: Optional[str],
    recommendation: str,
) -> Finding:
    _plain_field(draft_id, "draft_id")
    _check_text(claim, "claim")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in claim):
        raise QueueRefusal("claim contains a control or invisible character")
    if _visible_len(claim) < MIN_TEXT_CHARS:
        raise QueueRefusal(f"claim needs at least {MIN_TEXT_CHARS} visible characters")
    if evidence_kind not in EVIDENCE_KINDS:
        raise QueueRefusal("evidence_kind must be one of " + ", ".join(EVIDENCE_KINDS))
    _plain_field(evidence_ref, "evidence_ref")
    ref = evidence_ref.strip()
    if _visible_len(ref) < MIN_TEXT_CHARS:
        raise QueueRefusal(f"evidence_ref needs at least {MIN_TEXT_CHARS} visible characters")
    if len(ref) > MAX_REF_CHARS:
        raise QueueRefusal(f"evidence_ref is longer than {MAX_REF_CHARS} characters")
    if evidence_kind == "source" and not _URL_RE.fullmatch(ref):
        raise QueueRefusal("a source finding needs an https URL as its evidence_ref")
    if evidence_excerpt is not None and "\x00" in evidence_excerpt:
        raise QueueRefusal("evidence_excerpt contains a NUL byte")
    _check_text(recommendation, "recommendation")
    if _visible_len(recommendation) < MIN_TEXT_CHARS:
        raise QueueRefusal(f"recommendation needs at least {MIN_TEXT_CHARS} visible characters")
    return Finding(
        draft_id=draft_id, claim_key=claim_key(claim), claim=claim.strip(),
        evidence_kind=evidence_kind, evidence_ref=ref,
        evidence_excerpt=evidence_excerpt or None, recommendation=recommendation.strip(),
    )


def _decide(f: Finding, status: DraftStatus, decided_by: str, note: Optional[str]) -> Finding:
    if f.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"finding already {f.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    if note is not None and "\x00" in note:
        raise QueueRefusal("decision note contains a NUL byte")
    if status is DraftStatus.APPROVED and f.evidence_kind == "unverified":
        if _visible_len(note or "") < MIN_TEXT_CHARS:
            raise QueueRefusal(
                "adopting an unverified finding needs a note of at least "
                f"{MIN_TEXT_CHARS} visible characters saying so"
            )
    return replace(f, status=status, decided_by=who, decision_note=note)


def approve(f: Finding, decided_by: str, note: Optional[str] = None) -> Finding:
    """Records adoption. It does not act on the finding."""
    return _decide(f, DraftStatus.APPROVED, decided_by, note)


def reject(f: Finding, decided_by: str, note: Optional[str] = None) -> Finding:
    return _decide(f, DraftStatus.REJECTED, decided_by, note)
