"""Storage for the Research findings queue.

The rules live in services/company/research.py and are applied here before any
row is written, so a row that exists has already passed them. Every query is
scoped to the owner account. A claim is recorded once per owner. Nothing in
this module searches, fetches or acts on a finding.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.research import (
    DuplicateFinding,
    Finding,
    approve,
    create_finding,
    reject,
)

_COLUMNS = (
    "draft_id, claim_key, claim, evidence_kind, evidence_ref, evidence_excerpt, "
    "recommendation, status, decided_by, decision_note"
)


def _row_to_finding(row) -> Finding:
    return Finding(
        draft_id=row.draft_id,
        claim_key=row.claim_key,
        claim=row.claim,
        evidence_kind=row.evidence_kind,
        evidence_ref=row.evidence_ref,
        evidence_excerpt=row.evidence_excerpt,
        recommendation=row.recommendation,
        status=DraftStatus(row.status),
        decided_by=row.decided_by,
        decision_note=row.decision_note,
    )


async def insert_finding(db: AsyncSession, owner_id: str, **fields) -> Finding:
    """Validate with the Research rules, then store.

    Raises QueueRefusal on a bad finding and DuplicateFinding on a claim this
    owner already has on record, whatever state it is in.
    """
    f = create_finding(draft_id=str(uuid4()), **fields)
    result = await db.execute(
        text(
            "INSERT INTO company_findings (owner_id, draft_id, claim_key, claim, "
            "evidence_kind, evidence_ref, evidence_excerpt, recommendation) "
            "VALUES (:o, :d, :k, :c, :ek, :er, :ex, :r) "
            "ON CONFLICT (owner_id, claim_key) DO NOTHING"
        ),
        {
            "o": owner_id, "d": f.draft_id, "k": f.claim_key, "c": f.claim,
            "ek": f.evidence_kind, "er": f.evidence_ref, "ex": f.evidence_excerpt,
            "r": f.recommendation,
        },
    )
    if result.rowcount != 1:
        raise DuplicateFinding("this claim is already on record")
    return f


async def list_findings(
    db: AsyncSession, owner_id: str, status: Optional[str] = None, limit: int = 100
) -> List[Finding]:
    sql = f"SELECT {_COLUMNS} FROM company_findings WHERE owner_id = :o"
    params = {"o": owner_id, "n": max(1, min(limit, 500))}
    if status:
        sql += " AND status = :st"
        params["st"] = status
    sql += " ORDER BY created_at DESC LIMIT :n"
    rows = (await db.execute(text(sql), params)).all()
    return [_row_to_finding(r) for r in rows]


async def get_finding(db: AsyncSession, owner_id: str, draft_id: str) -> Optional[Finding]:
    row = (
        await db.execute(
            text(f"SELECT {_COLUMNS} FROM company_findings WHERE owner_id = :o AND draft_id = :d"),
            {"o": owner_id, "d": draft_id},
        )
    ).first()
    return _row_to_finding(row) if row else None


async def decide_finding(
    db: AsyncSession,
    owner_id: str,
    draft_id: str,
    *,
    approved: bool,
    decided_by: str,
    note: Optional[str],
) -> Optional[Finding]:
    """Apply the rules to the stored finding, then record the decision once.

    Returns None when the finding does not exist for this owner. The UPDATE
    keeps the drafted-only guard in SQL so two simultaneous decisions cannot
    both win.
    """
    current = await get_finding(db, owner_id, draft_id)
    if current is None:
        return None
    decided = (approve if approved else reject)(current, decided_by, note)
    result = await db.execute(
        text(
            "UPDATE company_findings SET status = :st, decided_by = :by, "
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
        raise QueueRefusal("finding already decided")
    return decided
