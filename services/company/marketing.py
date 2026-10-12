"""The Marketing approval queue rules.

Tee ruled on 2026-10-12: the Marketing agent drafts and queues, and never
schedules or publishes. This module is the rule set for that queue. It holds no
store and opens no connection, so nothing here can reach a platform.

What it refuses, because each is a compliance item with no exception path:

  1. A draft with no AI disclosure. Platform policy and AI disclosure are
     Tee's hard rules, so a draft cannot enter the queue without one.
  2. Em or en dashes in post text. Tee's prose rule for anything delivered.
  3. An approval with no human named, or one named as an automated actor.
  4. A second decision on a draft that already has one.

It does not check platform character limits, because none were verified here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

BANNED_DASHES = ("—", "–")
AUTOMATED_ACTORS = {"claude", "agent", "auto", "bot", "system", "marketing", "devon"}


class DraftStatus(str, Enum):
    DRAFTED = "drafted"
    APPROVED = "approved"
    REJECTED = "rejected"


class QueueRefusal(ValueError):
    """Every refusal names its reason. A refusal nobody hears is an approval."""


@dataclass(frozen=True)
class PostDraft:
    draft_id: str
    show: str
    episode_ref: str
    platform: str
    text: str
    ai_disclosure: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def _check_text(text: str, label: str) -> None:
    if not text or not text.strip():
        raise QueueRefusal(f"{label} is empty")
    if "\x00" in text:
        raise QueueRefusal(f"{label} contains a NUL byte")
    if any(d in text for d in BANNED_DASHES):
        raise QueueRefusal(f"{label} contains an em or en dash")


def create_draft(*, draft_id: str, show: str, episode_ref: str, platform: str,
                 text: str, ai_disclosure: str) -> PostDraft:
    for label, value in (("draft_id", draft_id), ("show", show),
                         ("episode_ref", episode_ref), ("platform", platform)):
        if not value or not value.strip():
            raise QueueRefusal(f"{label} is empty")
        if "\x00" in value:
            raise QueueRefusal(f"{label} contains a NUL byte")
    _check_text(text, "post text")
    if not ai_disclosure or not ai_disclosure.strip():
        raise QueueRefusal("no AI disclosure: a draft cannot be queued without one")
    _check_text(ai_disclosure, "ai_disclosure")
    return PostDraft(draft_id=draft_id, show=show, episode_ref=episode_ref,
                     platform=platform, text=text, ai_disclosure=ai_disclosure)


def _decide(draft: PostDraft, status: DraftStatus, decided_by: str, note: Optional[str]) -> PostDraft:
    if draft.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"draft already {draft.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    return replace(draft, status=status, decided_by=who, decision_note=note)


def approve(draft: PostDraft, decided_by: str, note: Optional[str] = None) -> PostDraft:
    """Records approval. It does not schedule or publish anything."""
    return _decide(draft, DraftStatus.APPROVED, decided_by, note)


def reject(draft: PostDraft, decided_by: str, note: Optional[str] = None) -> PostDraft:
    return _decide(draft, DraftStatus.REJECTED, decided_by, note)
