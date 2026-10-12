"""Storage for the Product proposals queue.

The rules live in services/company/product.py and are applied here before any
row is written, so a row that exists has already passed them. Every query is
scoped to the owner account. A title is recorded once per owner. Nothing in
this module builds, commits or runs anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.product import (
    DuplicateProposal,
    Proposal,
    approve,
    create_proposal,
    reject,
)

_COLUMNS = (
    "draft_id, title_key, title, problem, proposal, acceptance_check, "
    "reference_artifact, size, status, decided_by, decision_note"
)


def _row_to_proposal(row) -> Proposal:
    return Proposal(
        draft_id=row.draft_id,
        title_key=row.title_key,
        title=row.title,
        problem=row.problem,
        proposal=row.proposal,
        acceptance_check=row.acceptance_check,
        reference_artifact=row.reference_artifact,
        size=row.size,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_proposal(db: AsyncSession, owner_id: str, **fields) -> Proposal:
    """Validate with the Product rules, then store.

    Raises QueueRefusal on a bad proposal and DuplicateProposal on a title this
    owner already has on record, whatever state it is in.
    """
    p = create_proposal(draft_id=str(uuid4()), **fields)
    result = await db.execute(
        text(
            "INSERT INTO company_proposals (owner_id, draft_id, title_key, title, problem, "
            "proposal, acceptance_check, reference_artifact, size) "
            "VALUES (:o, :d, :k, :t, :pr, :pp, :ac, :ra, :s) "
            "ON CONFLICT (owner_id, title_key) DO NOTHING"
        ),
        {
            "o": owner_id, "d": p.draft_id, "k": p.title_key, "t": p.title,
            "pr": p.problem, "pp": p.proposal, "ac": p.acceptance_check,
            "ra": p.reference_artifact, "s": p.size,
        },
    )
    if result.rowcount != 1:
        raise DuplicateProposal("a proposal with this title is already on record")
    return p


async def list_proposals(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[Proposal]:
    sql = f"SELECT {_COLUMNS} FROM company_proposals WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    rows = (await db.execute(text(sql), params)).all()
    return [_row_to_proposal(r) for r in rows]


async def get_proposal(db: AsyncSession, owner_id: str, draft_id: str) -> Optional[Proposal]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_proposals WHERE owner_id = :o AND draft_id = :d"),
            {"o": owner_id, "d": draft_id},
        )
    ).first()
    return _row_to_proposal(row) if row else None


async def decide_proposal(
    db: AsyncSession,
    owner_id: str,
    draft_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[Proposal]:
    """Apply the rules to the stored proposal, then record the decision once.

    Returns None when the proposal does not exist for this owner. The UPDATE
    keeps the drafted-only guard in SQL so two simultaneous decisions cannot
    both win.
    """
    current = await get_proposal(db, owner_id, draft_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_proposals SET status = :st, decided_by = :by, "
            "decision_note = :n, decided_at = :at "
            "WHERE owner_id = :o AND draft_id = :d AND status = 'drafted'"
        ),
        {
            "st": decided.status.value, "by": decided.decided_by,
            "n": decided.decision_note, "at": datetime.utcnow(),
            "o": owner_id, "d": draft_id,
        },
    )
    if result.rowcount != 1:
        raise QueueRefusal("proposal already decided")
    return decided
