"""Storage for the Support approval queue.

The rules live in services/company/support.py and are applied here before any
row is written, so a row that exists has already passed them. Every query is
scoped to the owner account. A comment is queued once per owner. Nothing in
this module posts or schedules anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.support import (
    CommentDraft,
    approve,
    create_comment_draft,
    reject,
)

_COLUMNS = (
    "draft_id, video_id, comment_id, commenter_name, comment_text, reply_text, "
    "reply_basis, ai_disclosure, status, decided_by, decision_note"
)


def _row_to_draft(row) -> CommentDraft:
    return CommentDraft(
        draft_id=row.draft_id,
        video_id=row.video_id,
        comment_id=row.comment_id,
        commenter_name=row.commenter_name,
        comment_text=row.comment_text,
        reply_text=row.reply_text,
        reply_basis=row.reply_basis,
        ai_disclosure=row.ai_disclosure,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_comment_draft(db: AsyncSession, owner_id: str, **fields) -> CommentDraft:
    """Validate with the Support rules, then store.

    Raises QueueRefusal on a bad draft, and on a comment this owner already has
    a draft for, whatever state that draft is in.
    """
    draft = create_comment_draft(draft_id=str(uuid4()), **fields)
    result = await db.execute(
        text(
            "INSERT INTO company_comment_drafts (owner_id, draft_id, video_id, comment_id, "
            "commenter_name, comment_text, reply_text, reply_basis, ai_disclosure) "
            "VALUES (:o, :d, :v, :c, :cn, :ct, :rt, :rb, :ad) "
            "ON CONFLICT (owner_id, comment_id) DO NOTHING"
        ),
        {
            "o": owner_id,
            "d": draft.draft_id,
            "v": draft.video_id,
            "c": draft.comment_id,
            "cn": draft.commenter_name,
            "ct": draft.comment_text,
            "rt": draft.reply_text,
            "rb": draft.reply_basis,
            "ad": draft.ai_disclosure,
        },
    )
    if result.rowcount != 1:
        raise QueueRefusal("this comment already has a draft")
    return draft


async def list_comment_drafts(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[CommentDraft]:
    sql = f"SELECT {_COLUMNS} FROM company_comment_drafts WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    rows = (await db.execute(text(sql), params)).all()
    return [_row_to_draft(r) for r in rows]


async def get_comment_draft(db: AsyncSession, owner_id: str, draft_id: str) -> Optional[CommentDraft]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_comment_drafts WHERE owner_id = :o AND draft_id = :d"),
            {"o": owner_id, "d": draft_id},
        )
    ).first()
    return _row_to_draft(row) if row else None


async def decide_comment_draft(
    db: AsyncSession,
    owner_id: str,
    draft_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[CommentDraft]:
    """Apply the rules to the stored draft, then record the decision once.

    Returns None when the draft does not exist for this owner. The UPDATE keeps
    the drafted-only guard in SQL so two simultaneous decisions cannot both win.
    """
    current = await get_comment_draft(db, owner_id, draft_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_comment_drafts SET status = :st, decided_by = :by, "
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
