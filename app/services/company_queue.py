"""Storage for the Marketing approval queue.

The rules live in services/company/marketing.py and are applied here before any
row is written, so a row that exists has already passed them. Every query is
scoped to the owner account. Nothing in this module sends, schedules or
publishes anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.marketing import (
    DraftStatus,
    PostDraft,
    QueueRefusal,
    approve,
    create_draft,
    reject,
)

_COLUMNS = (
    "draft_id, show, episode_ref, platform, text, ai_disclosure, status, "
    "decided_by, decision_note"
)


def _row_to_draft(row) -> PostDraft:
    return PostDraft(
        draft_id=row.draft_id,
        show=row.show,
        episode_ref=row.episode_ref,
        platform=row.platform,
        text=row.text,
        ai_disclosure=row.ai_disclosure,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_draft(
    db: AsyncSession,
    owner_id: str,
    *,
    show: str,
    episode_ref: str,
    platform: str,
    post_text: str,
    ai_disclosure: str,
) -> PostDraft:
    """Validate with the queue rules, then store. Raises QueueRefusal on a bad draft."""
    draft = create_draft(
        draft_id=str(uuid4()),
        show=show,
        episode_ref=episode_ref,
        platform=platform,
        text=post_text,
        ai_disclosure=ai_disclosure,
    )
    await db.execute(
        text(
            "INSERT INTO company_post_drafts "
            "(owner_id, draft_id, show, episode_ref, platform, text, ai_disclosure) "
            "VALUES (:o, :d, :s, :e, :p, :t, :a)"
        ),
        {
            "o": owner_id,
            "d": draft.draft_id,
            "s": draft.show,
            "e": draft.episode_ref,
            "p": draft.platform,
            "t": draft.text,
            "a": draft.ai_disclosure,
        },
    )
    return draft


async def list_drafts(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[PostDraft]:
    sql = f"SELECT {_COLUMNS} FROM company_post_drafts WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    rows = (await db.execute(text(sql), params)).all()
    return [_row_to_draft(r) for r in rows]


async def get_draft(db: AsyncSession, owner_id: str, draft_id: str) -> Optional[PostDraft]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_post_drafts WHERE owner_id = :o AND draft_id = :d"),
            {"o": owner_id, "d": draft_id},
        )
    ).first()
    return _row_to_draft(row) if row else None


async def decide_draft(
    db: AsyncSession,
    owner_id: str,
    draft_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[PostDraft]:
    """Apply the rules to the stored draft, then record the decision once.

    Returns None when the draft does not exist for this owner. The UPDATE keeps
    the drafted-only guard in SQL so two simultaneous decisions cannot both win.
    Raises QueueRefusal for an automated or unnamed decider or an already
    decided draft.
    """
    current = await get_draft(db, owner_id, draft_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_post_drafts SET status = :st, decided_by = :by, "
            "decision_note = :n, decided_at = :at "
            "WHERE owner_id = :o AND draft_id = :d AND status = 'drafted'"
        ),
        {
            "st": decided.status.value,
            "by": decided.decided_by,
            "n": decided.decision_note,
            "at": datetime.utcnow(),
            "o": owner_id,
            "d": draft_id,
        },
    )
    if result.rowcount != 1:
        raise QueueRefusal("draft already decided")
    return decided
