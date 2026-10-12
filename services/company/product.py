"""The Product proposals queue rules.

Product Development drafts change proposals (a feature, a fix, a test, a doc)
and a human decides which get built. This module is the rule set for the
proposal log. It holds no store and opens no connection, and it has no way to
write code, open a pull request or run anything, so approving a proposal only
records the decision.

The house bar is "name a real, openable reference artifact" and "measure, never
assume", so a proposal cannot be an adjective. What it refuses:

  1. A title, problem or proposal with em or en dashes or look-alikes, or a NUL
     byte, or fewer than 10 visible characters (a title needs 5).
  2. A proposal with no acceptance check of at least 10 visible characters.
     The check says how anyone would measure that it works.
  3. A proposal with no reference artifact of at least 10 visible characters.
     It names the file, URL or document the work should match or extend.
  4. A size other than small, medium or large, and approving a large proposal
     without a note of at least 10 visible characters. A large build is a
     commitment, and the record should say it was taken knowingly.
  5. The same title twice for one owner, whatever its state.
  6. A decision with no human named, or one named as an automated actor, and a
     second decision on a proposal that already has one.

It never checks that the reference artifact exists or that the acceptance check
is sufficient. It only checks they were written down.
"""

from __future__ import annotations

import hashlib
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

SIZES = ("small", "medium", "large")
MIN_TEXT_CHARS = 10
MIN_TITLE_CHARS = 5
MAX_TITLE_CHARS = 200


class DuplicateProposal(QueueRefusal):
    """The owner already has a proposal with this title on record."""


@dataclass(frozen=True)
class Proposal:
    draft_id: str
    title_key: str
    title: str
    problem: str
    proposal: str
    acceptance_check: str
    reference_artifact: str
    size: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def title_key(title: str) -> str:
    """Case and whitespace insensitive identity of a title."""
    return hashlib.sha256(" ".join(title.casefold().split()).encode("utf-8")).hexdigest()


def _plain_field(value: str, label: str) -> None:
    if not value or not value.strip():
        raise QueueRefusal(f"{label} is empty")
    if "\x00" in value:
        raise QueueRefusal(f"{label} contains a NUL byte")


def _needs(value: str, label: str, floor: int = MIN_TEXT_CHARS) -> None:
    if _visible_len(value) < floor:
        raise QueueRefusal(f"{label} needs at least {floor} visible characters")


def create_proposal(
    *,
    draft_id: str,
    title: str,
    problem: str,
    proposal: str,
    acceptance_check: str,
    reference_artifact: str,
    size: str,
) -> Proposal:
    _plain_field(draft_id, "draft_id")
    _check_text(title, "title")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in title):
        raise QueueRefusal("title contains a control or invisible character")
    if len(title.strip()) > MAX_TITLE_CHARS:
        raise QueueRefusal(f"title is longer than {MAX_TITLE_CHARS} characters")
    _needs(title, "title", MIN_TITLE_CHARS)
    _check_text(problem, "problem")
    _needs(problem, "problem")
    _check_text(proposal, "proposal")
    _needs(proposal, "proposal")
    _plain_field(acceptance_check, "acceptance_check")
    _needs(acceptance_check, "acceptance_check")
    _plain_field(reference_artifact, "reference_artifact")
    _needs(reference_artifact, "reference_artifact")
    if size not in SIZES:
        raise QueueRefusal("size must be one of " + ", ".join(SIZES))
    return Proposal(
        draft_id=draft_id, title_key=title_key(title), title=title.strip(),
        problem=problem, proposal=proposal, acceptance_check=acceptance_check,
        reference_artifact=reference_artifact, size=size,
    )


def _decide(p: Proposal, status: DraftStatus, decided_by: str, note: Optional[str]) -> Proposal:
    if p.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"proposal already {p.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    if status is DraftStatus.APPROVED and p.size == "large" and _visible_len(note or "") < MIN_TEXT_CHARS:
        raise QueueRefusal(
            "approving a large proposal needs a note of at least "
            f"{MIN_TEXT_CHARS} visible characters"
        )
    return replace(p, status=status, decided_by=who, decision_note=note)


def approve(p: Proposal, decided_by: str, note: Optional[str] = None) -> Proposal:
    """Records approval. It does not build anything."""
    return _decide(p, DraftStatus.APPROVED, decided_by, note)


def reject(p: Proposal, decided_by: str, note: Optional[str] = None) -> Proposal:
    return _decide(p, DraftStatus.REJECTED, decided_by, note)
