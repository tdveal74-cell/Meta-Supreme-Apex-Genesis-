"""The Support knowledge base rules: articles Tee writes and approves.

Tee ruled on 2026-10-15: Support replies get their facts from approved articles
he writes, and every reply must cite one article id or it is refused. This
module is the rule set for the articles. It holds no store and opens no
connection.

What it refuses:

  1. An article id that is not a lowercase slug, so an id is a stable name and
     never free text. Matched with fullmatch for the reason support.py gives.
  2. A title or body with em or en dashes or look-alikes, a NUL byte, or no
     visible character. The reply that cites an article is delivered text, so
     the article it rests on is held to the same prose rule.
  3. A body shorter than 20 visible characters, which cannot ground an answer.
  4. A decision with no human named, one named as an automated actor, one
     that carries a banned dash in its note, or a second decision.

An article is citable only once it is approved. A drafted or rejected article
is not a source, and a reply that cites it is refused by `require_citable`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

from services.company.marketing import (
    AUTOMATED_ACTORS,
    DraftStatus,
    QueueRefusal,
    _check_note,
    _check_text,
    _visible_len,
)

ARTICLE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
MAX_TITLE_CHARS = 200
MIN_BODY_CHARS = 20


@dataclass(frozen=True)
class Article:
    article_id: str
    title: str
    body: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def check_article_id(article_id: str) -> str:
    if not ARTICLE_ID_RE.fullmatch(article_id or ""):
        raise QueueRefusal(
            "article_id must be a lowercase slug of 2 to 63 characters: letters, digits and hyphens"
        )
    return article_id


def create_article(*, article_id: str, title: str, body: str) -> Article:
    check_article_id(article_id)
    _check_text(title, "title")
    if len(title.strip()) > MAX_TITLE_CHARS:
        raise QueueRefusal(f"title is longer than {MAX_TITLE_CHARS} characters")
    if _visible_len(title) == 0:
        raise QueueRefusal("title has no visible characters")
    _check_text(body, "body")
    if _visible_len(body) < MIN_BODY_CHARS:
        raise QueueRefusal(f"body needs at least {MIN_BODY_CHARS} visible characters")
    return Article(article_id=article_id, title=title.strip(), body=body)


def _decide(article: Article, status: DraftStatus, decided_by: str, note: Optional[str]) -> Article:
    if article.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"article already {article.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    _check_note(note)
    return replace(article, status=status, decided_by=who, decision_note=note)


def approve(article: Article, decided_by: str, note: Optional[str] = None) -> Article:
    """Records approval. The article becomes citable by a Support reply."""
    return _decide(article, DraftStatus.APPROVED, decided_by, note)


def reject(article: Article, decided_by: str, note: Optional[str] = None) -> Article:
    return _decide(article, DraftStatus.REJECTED, decided_by, note)


def require_citable(article: Optional[Article], article_id: str) -> Article:
    """A reply may cite an article only if it exists for the owner and is approved."""
    if article is None:
        raise QueueRefusal(f"article {article_id!r} does not exist, so a reply cannot cite it")
    if article.status is not DraftStatus.APPROVED:
        raise QueueRefusal(
            f"article {article_id!r} is {article.status.value}, so a reply cannot cite it"
        )
    return article
