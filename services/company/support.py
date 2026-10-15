"""The Support approval queue rules.

Tee ruled on 2026-10-12: audience questions arrive as YouTube comments, the
Support agent drafts the reply, and nothing is posted without Tee. This module
is the rule set for that queue. It holds no store and opens no connection, so
nothing here can post a comment.

What it refuses:

  1. A video id or comment id that is not shaped like a YouTube one. Both are
     identifiers that a later posting step would hand to the platform, so they
     are held to the characters YouTube uses and nothing else.
  2. A drafted reply with em or en dashes or look-alikes, a NUL byte, or no
     visible character at all. Tee's
     prose rule for anything delivered. The viewer's comment is their own words
     and is only checked for NUL, because it is not ours to rewrite.
  3. A reply with no stated basis of at least 10 visible characters. The basis
     names where the answer comes from, an episode, a script or a doc. A reply
     whose source nobody wrote down is a guess, and "unverified" is a valid
     basis. It never checks that the basis is true, only that it was written.
  4. A reply with no AI disclosure of at least 10 visible characters. Tee's
     disclosure rule has no exception path, so this reuses the Marketing rule.
  5. A reply that cites no article, or an article id that is not a slug. The
     rules here check the shape only. Whether the article exists, belongs to the
     owner and is approved is checked at storage against the knowledge base
     (services/company/knowledge.py), because that needs a lookup. Ruled by Tee
     2026-10-15: every reply cites one article id or it is refused.
  6. An approval with no human named, or one named as an automated actor, and
     a second decision on a draft that already has one.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Optional

from services.company.knowledge import check_article_id
from services.company.marketing import (
    AUTOMATED_ACTORS,
    MIN_DISCLOSURE_CHARS,
    DraftStatus,
    QueueRefusal,
    _check_note,
    _check_text,
    _visible_len,
)

MIN_BASIS_CHARS = 10
MAX_NAME_CHARS = 200

# YouTube video ids are 11 characters of [A-Za-z0-9_-]. Comment ids use the same
# alphabet, and a reply id is the parent id, a dot, then a suffix. Neither id is
# ever allowed whitespace, a slash or a quote. They are matched with fullmatch:
# a "$" anchor also matches before a final newline, which would store an id the
# platform never issued and let the same comment through the unique key twice.
_VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
_COMMENT_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}(\.[A-Za-z0-9_-]{1,64})?")


@dataclass(frozen=True)
class CommentDraft:
    draft_id: str
    video_id: str
    comment_id: str
    commenter_name: str
    comment_text: str
    reply_text: str
    reply_basis: str
    ai_disclosure: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None
    # None only for a row saved before the knowledge base existed.
    article_id: Optional[str] = None


def _plain_field(value: str, label: str) -> None:
    if not value or not value.strip():
        raise QueueRefusal(f"{label} is empty")
    if "\x00" in value:
        raise QueueRefusal(f"{label} contains a NUL byte")


def create_comment_draft(
    *,
    draft_id: str,
    video_id: str,
    comment_id: str,
    commenter_name: str,
    comment_text: str,
    reply_text: str,
    reply_basis: str,
    ai_disclosure: str,
    article_id: str,
) -> CommentDraft:
    _plain_field(draft_id, "draft_id")
    check_article_id(article_id)
    if not _VIDEO_ID_RE.fullmatch(video_id or ""):
        raise QueueRefusal("video_id is not shaped like a YouTube video id")
    if not _COMMENT_ID_RE.fullmatch(comment_id or ""):
        raise QueueRefusal("comment_id is not shaped like a YouTube comment id")
    _plain_field(commenter_name, "commenter_name")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in commenter_name):
        raise QueueRefusal("commenter_name contains a control or invisible character")
    if len(commenter_name.strip()) > MAX_NAME_CHARS:
        raise QueueRefusal(f"commenter_name is longer than {MAX_NAME_CHARS} characters")
    _plain_field(comment_text, "comment_text")
    _check_text(reply_text, "reply text")
    if _visible_len(reply_text) == 0:
        raise QueueRefusal("reply text has no visible characters")
    _plain_field(reply_basis, "reply_basis")
    _check_text(reply_basis, "reply_basis")
    if _visible_len(reply_basis) < MIN_BASIS_CHARS:
        raise QueueRefusal(
            f"reply_basis needs at least {MIN_BASIS_CHARS} visible characters"
        )
    _check_text(ai_disclosure, "ai_disclosure")
    if _visible_len(ai_disclosure) < MIN_DISCLOSURE_CHARS:
        raise QueueRefusal(
            f"ai_disclosure needs at least {MIN_DISCLOSURE_CHARS} visible characters"
        )
    return CommentDraft(
        draft_id=draft_id, video_id=video_id, comment_id=comment_id,
        commenter_name=commenter_name.strip(), comment_text=comment_text,
        reply_text=reply_text, reply_basis=reply_basis, ai_disclosure=ai_disclosure,
        article_id=article_id,
    )


def _decide(draft: CommentDraft, status: DraftStatus, decided_by: str, note: Optional[str]) -> CommentDraft:
    if draft.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"draft already {draft.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    _check_note(note)
    return replace(draft, status=status, decided_by=who, decision_note=note)


def approve(draft: CommentDraft, decided_by: str, note: Optional[str] = None) -> CommentDraft:
    """Records approval. It does not post anything."""
    return _decide(draft, DraftStatus.APPROVED, decided_by, note)


def reject(draft: CommentDraft, decided_by: str, note: Optional[str] = None) -> CommentDraft:
    return _decide(draft, DraftStatus.REJECTED, decided_by, note)
