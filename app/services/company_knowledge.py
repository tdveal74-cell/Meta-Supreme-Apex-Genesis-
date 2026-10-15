"""Storage for the Support knowledge base.

The rules live in services/company/knowledge.py and are applied here before any
row is written. Every query is scoped to the owner account. An article id is
unique per owner. Nothing in this module posts or schedules anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.knowledge import Article, approve, create_article, reject
from services.company.marketing import DraftStatus, QueueRefusal

_COLUMNS = "article_id, title, body, status, decided_by, decision_note"


def _row_to_article(row) -> Article:
    return Article(
        article_id=row.article_id,
        title=row.title,
        body=row.body,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_article(db: AsyncSession, owner_id: str, **fields) -> Article:
    """Validate with the knowledge rules, then store as a draft.

    Raises QueueRefusal on a bad article and on an id this owner already used,
    whatever state the earlier article is in.
    """
    article = create_article(**fields)
    result = await db.execute(
        text(
            "INSERT INTO company_support_articles (owner_id, article_id, title, body) "
            "VALUES (:o, :a, :t, :b) ON CONFLICT (owner_id, article_id) DO NOTHING"
        ),
        {"o": owner_id, "a": article.article_id, "t": article.title, "b": article.body},
    )
    if result.rowcount != 1:
        raise QueueRefusal("this article id already exists")
    return article


async def list_articles(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[Article]:
    sql = f"SELECT {_COLUMNS} FROM company_support_articles WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    return [_row_to_article(r) for r in (await db.execute(text(sql), params)).all()]


async def get_article(db: AsyncSession, owner_id: str, article_id: str) -> Optional[Article]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_support_articles WHERE owner_id = :o AND article_id = :a"),
            {"o": owner_id, "a": article_id},
        )
    ).first()
    return _row_to_article(row) if row else None


async def decide_article(
    db: AsyncSession,
    owner_id: str,
    article_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[Article]:
    """Apply the rules to the stored article, then record the decision once.

    Returns None when the article does not exist for this owner. The UPDATE keeps
    the drafted-only guard in SQL so two simultaneous decisions cannot both win.
    """
    current = await get_article(db, owner_id, article_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_support_articles SET status = :st, decided_by = :by, "
            "decision_note = :n, decided_at = :at "
            "WHERE owner_id = :o AND article_id = :a AND status = 'drafted'"
        ),
        {
            "st": decided.status.value,
            "by": decided.decided_by,
            "n": decided.decision_note,
            "at": datetime.utcnow(),
            "o": owner_id,
            "a": article_id,
        },
    )
    if result.rowcount != 1:
        raise QueueRefusal("article already decided")
    return decided
