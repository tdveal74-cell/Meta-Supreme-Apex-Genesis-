"""Optional app-layer persistence adapter for read-only ARF analysis history.

STAGED, NOT HOOKED UP: calling append_history mutates ONLY an audit history
row. No user effects or AgentRuntime state changes. Do not add an automatic
call site without explicit security/owner review, migration, RLS and grants.
"""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.agent_runtime.reliability.lineage import (
    HistoryConflict,
    HistoryEvent,
    review_history,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _read_row(row):
    return HistoryEvent(
        event_id=row["event_id"], owner_id=str(row["owner_id"]),
        root_task_id=row["root_task_id"], task_id=row["task_id"],
        parent_event_id=row["parent_event_id"] or "",
        delegated_from_event_id=row["delegated_from_event_id"] or "",
        failure_fingerprint=row["failure_fingerprint"],
        outcome_digest=row["outcome_digest"],
        evidence_revision=row["evidence_revision"],
        control=row["control"], attempt_no=row["attempt_no"],
    )


async def read_history(db: AsyncSession, *, owner_id: str,
                       root_task_id: str) -> tuple[HistoryEvent, ...]:
    """Read complete lineage for a trusted owner and root, without pagination."""
    if not owner_id or not root_task_id:
        raise HistoryConflict("missing trusted recovery history owner/root")
    rows = await db.execute(text("""
        SELECT event_id, owner_id, root_task_id, task_id,
               parent_event_id, delegated_from_event_id,
               failure_fingerprint, outcome_digest, evidence_revision,
               control, attempt_no
          FROM arf_shadow_history
         WHERE owner_id = :owner_id AND root_task_id = :root_task_id
         ORDER BY recorded_sequence ASC
    """), {"owner_id": owner_id, "root_task_id": root_task_id})
    return review_history(tuple(_read_row(row) for row in rows.mappings().all()),
                          owner_id=owner_id, root_task_id=root_task_id)


async def append_history(db: AsyncSession, *, owner_id: str,
                         event: HistoryEvent, policy_digest: str,
                         shadow_audit_write_authorized: bool = False) -> None:
    """Record one event ONLY inside a pre-authorized app audit transaction.

    The caller owns commit/rollback and must hold an appropriate DB permission.
    A task, model, or web request cannot set `shadow_audit_write_authorized`.
    Never call this function from the read-only observer itself.
    """
    if not shadow_audit_write_authorized:
        raise PermissionError("ARF audit history write requires trusted app authorization")
    if owner_id != event.owner_id or not isinstance(event.event_id, str) or not _SAFE_ID.fullmatch(event.event_id) or len(event.event_id) > 80:
        raise HistoryConflict("invalid owner or event id")
    for value, limit in ((event.root_task_id, 64), (event.task_id, 64), (event.control, 80)):
        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value) or len(value) > limit:
            raise HistoryConflict("invalid task, root, or control identifier")
    for value in (event.parent_event_id, event.delegated_from_event_id):
        if not isinstance(value, str) or (value and (len(value) > 80 or not _SAFE_ID.fullmatch(value))):
            raise HistoryConflict("invalid ancestor identifier")
    if not (isinstance(policy_digest, str) and len(policy_digest) == 64 and
            all(ch in "0123456789abcdef" for ch in policy_digest)):
        raise HistoryConflict("invalid source policy digest")
    if not event.evidence_revision or len(event.evidence_revision) > 128 or not _SAFE_ID.fullmatch(event.evidence_revision):
        raise HistoryConflict("invalid evidence revision")
    history = await read_history(db, owner_id=owner_id,
                                 root_task_id=event.root_task_id)
    review_history([*history, event], owner_id=owner_id,
                   root_task_id=event.root_task_id)
    await db.execute(text("""
        INSERT INTO arf_shadow_history
            (event_id, owner_id, root_task_id, task_id,
             parent_event_id, delegated_from_event_id,
             failure_fingerprint, outcome_digest, evidence_revision,
             control, attempt_no, policy_digest)
        VALUES (:event_id, :owner_id, :root_task_id, :task_id,
                :parent, :delegated, :failure_fingerprint, :outcome_digest,
                :evidence_revision, :control, :attempt_no, :policy_digest)
    """), {
        "event_id": event.event_id, "owner_id": owner_id,
        "root_task_id": event.root_task_id, "task_id": event.task_id,
        "parent": event.parent_event_id or None,
        "delegated": event.delegated_from_event_id or None,
        "failure_fingerprint": event.failure_fingerprint,
        "outcome_digest": event.outcome_digest,
        "evidence_revision": event.evidence_revision,
        "control": event.control, "attempt_no": event.attempt_no,
        "policy_digest": policy_digest,
    })
