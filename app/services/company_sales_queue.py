"""Storage for the Sales approval queue.

The rules live in services/company/sales.py and are applied here before any row
is written, so a row that exists has already passed them. Every query is scoped
to the owner account, because a row holds a lead's contact details. Nothing in
this module sends or schedules anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.sales import (
    LeadDraft,
    Qualification,
    approve,
    create_lead_draft,
    reject,
)

_COLUMNS = (
    "draft_id, source, contact_name, contact_email, inbound_excerpt, qualification, "
    "qualification_reason, reply_text, ai_disclosure, status, decided_by, decision_note"
)


def _row_to_draft(row) -> LeadDraft:
    return LeadDraft(
        draft_id=row.draft_id,
        source=row.source,
        contact_name=row.contact_name,
        contact_email=row.contact_email,
        inbound_excerpt=row.inbound_excerpt,
        qualification=Qualification(row.qualification),
        qualification_reason=row.qualification_reason,
        reply_text=row.reply_text,
        ai_disclosure=row.ai_disclosure,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_lead_draft(db: AsyncSession, owner_id: str, **fields) -> LeadDraft:
    """Validate with the Sales rules, then store. Raises QueueRefusal on a bad draft."""
    draft = create_lead_draft(draft_id=str(uuid4()), **fields)
    await db.execute(
        text(
            "INSERT INTO company_lead_drafts (owner_id, draft_id, source, contact_name, "
            "contact_email, inbound_excerpt, qualification, qualification_reason, "
            "reply_text, ai_disclosure) VALUES (:o, :d, :s, :cn, :ce, :ie, :q, :qr, :rt, :ad)"
        ),
        {
            "o": owner_id,
            "d": draft.draft_id,
            "s": draft.source,
            "cn": draft.contact_name,
            "ce": draft.contact_email,
            "ie": draft.inbound_excerpt,
            "q": draft.qualification.value,
            "qr": draft.qualification_reason,
            "rt": draft.reply_text,
            "ad": draft.ai_disclosure,
        },
    )
    return draft


async def list_lead_drafts(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[LeadDraft]:
    sql = f"SELECT {_COLUMNS} FROM company_lead_drafts WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    rows = (await db.execute(text(sql), params)).all()
    return [_row_to_draft(r) for r in rows]


async def get_lead_draft(db: AsyncSession, owner_id: str, draft_id: str) -> Optional[LeadDraft]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_lead_drafts WHERE owner_id = :o AND draft_id = :d"),
            {"o": owner_id, "d": draft_id},
        )
    ).first()
    return _row_to_draft(row) if row else None


async def decide_lead_draft(
    db: AsyncSession,
    owner_id: str,
    draft_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[LeadDraft]:
    """Apply the rules to the stored draft, then record the decision once.

    Returns None when the draft does not exist for this owner. The UPDATE keeps
    the drafted-only guard in SQL so two simultaneous decisions cannot both win.
    """
    current = await get_lead_draft(db, owner_id, draft_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_lead_drafts SET status = :st, decided_by = :by, "
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
