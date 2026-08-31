"""The DEVON Live State Ledger writer.

This is the application layer that performs the effect. Every rule it enforces
comes from ``services.devon.ecosystem``, which stays effect free, so the laws
cannot drift between the checker and the writer: there is one checker and this
module calls it.

What it guarantees:

* One intent per input, with a UUID minted by the doctrine rather than a caller.
* Events appended only in a legal order, gated by the same function that
  answers "is this sequence legal" to any reader.
* No action starts on an effect intent without APPROVAL_GRANTED already on the
  record, and none at all while the emergency stop holds.
* One receipt per intent, refused by a unique constraint in the database as
  well as by the check here, because a rule the database owns survives a caller
  that forgets.
* A derived intent state that is recomputed from the events on every append, so
  the summary column and the event log can never disagree.

The ledger observes the approval authority. It never grants. Approvals are
raised and ruled in ``services.devon.approval`` and its shared store; a row in
``approvals`` records which request belonged to which intent and how it ended.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_state_ledger import (
    ActionRecord,
    ArtifactRecord,
    ErrorRecord,
    EventRecord,
    IntentRecord,
    LearningCandidateRecord,
    LedgerApprovalRecord,
    SystemRecord,
    UniversalReceiptRecord,
    VerificationRecord,
)
from services.devon import ecosystem

EMERGENCY_STOP_NAME = "emergency_stop"


class LedgerRefused(RuntimeError):
    """A write the doctrine refuses. Carries every reason, never just the first."""

    def __init__(self, reasons: Sequence[str]) -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class LedgerConflict(RuntimeError):
    """Another writer got there first. The caller re-reads and decides again."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8).upper()}"


class LiveStateLedger:
    """Owner scoped reads and writes over the present tense of DEVON."""

    async def open_intent(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        channel: str,
        stated: str,
        is_effect: bool = False,
    ) -> Dict[str, Any]:
        """Mint one Universal Intent and open its record with INTENT_RECEIVED.

        The id comes from the doctrine, not from the caller, so no channel can
        collide two inputs onto one id or replay an old one. The opening event
        is written in the same transaction as the intent: an intent that exists
        without its first event would be a state nothing could legally follow.
        """
        intent = ecosystem.open_intent(channel, stated)
        record = IntentRecord(
            id=intent.intent_id,
            owner_id=owner_id,
            channel=intent.channel,
            stated=intent.stated,
            state=ecosystem.IntentState.RECEIVED.value,
            is_effect=is_effect,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(record)
        # The intent row is flushed before its first event so the foreign key
        # has something to point at. Both still land in the caller's single
        # transaction, so an intent without its opening event cannot be
        # committed: a state nothing could legally follow.
        await db.flush()
        db.add(
            EventRecord(
                intent_id=intent.intent_id,
                owner_id=owner_id,
                name="INTENT_RECEIVED",
                sequence_no=1,
                payload={"channel": intent.channel},
                occurred_at=_now(),
            )
        )
        await db.flush()
        return {
            "intent_id": intent.intent_id,
            "channel": intent.channel,
            "stated": intent.stated,
            "state": ecosystem.IntentState.RECEIVED.value,
            "is_effect": is_effect,
        }

    async def _intent(
        self, db: AsyncSession, *, owner_id: str, intent_id: str
    ) -> IntentRecord:
        result = await db.execute(
            select(IntentRecord).where(
                IntentRecord.id == intent_id, IntentRecord.owner_id == owner_id
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise LedgerRefused([f"No intent {intent_id} on this owner's record."])
        return record

    async def _event_names(
        self, db: AsyncSession, *, intent_id: str
    ) -> List[str]:
        result = await db.execute(
            select(EventRecord.name)
            .where(EventRecord.intent_id == intent_id)
            .order_by(EventRecord.sequence_no)
        )
        return [row[0] for row in result.all()]

    async def emergency_stopped(self, db: AsyncSession, *, owner_id: str) -> bool:
        """Whether the stop holds for this owner right now."""
        result = await db.execute(
            select(SystemRecord.status).where(
                SystemRecord.owner_id == owner_id,
                SystemRecord.name == EMERGENCY_STOP_NAME,
            )
        )
        status = result.scalar_one_or_none()
        return status == "stopped"

    async def append_event(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        name: str,
        action_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append one universal event, or refuse and say which law it breaks."""
        intent = await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        seen = await self._event_names(db, intent_id=intent_id)
        stopped = await self.emergency_stopped(db, owner_id=owner_id)

        violations = ecosystem.check_event(
            name,
            seen,
            effect=intent.is_effect,
            emergency_stopped=stopped,
        )
        if violations:
            raise LedgerRefused(violations)

        record = EventRecord(
            intent_id=intent_id,
            owner_id=owner_id,
            name=name,
            sequence_no=len(seen) + 1,
            action_id=action_id,
            payload=payload or {},
            occurred_at=_now(),
        )
        db.add(record)

        state = ecosystem.derive_state([*seen, name])
        # A receipted intent stays receipted: the receipt closed it, and a later
        # event does not reopen what was already accounted for.
        if intent.state != ecosystem.IntentState.RECEIPTED.value:
            intent.state = state.value
        intent.updated_at = _now()

        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise LedgerConflict(
                f"Another writer appended to intent {intent_id} first. "
                "Re-read the event log and decide again."
            ) from exc

        return {
            "intent_id": intent_id,
            "event": name,
            "sequence_no": record.sequence_no,
            "state": intent.state,
        }

    async def plan_action(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        duty: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a duty to an executor and record the planned action.

        An unrecognised duty is recorded as UNROUTED rather than guessed. The
        row still exists, because a parked action a human can see is the point.
        """
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        executor, reason = ecosystem.route_action(duty)
        action = ActionRecord(
            id=_new_id("ACT"),
            intent_id=intent_id,
            owner_id=owner_id,
            duty=duty.strip(),
            executor=executor,
            status="planned",
            detail={**(detail or {}), "routing_reason": reason},
            created_at=_now(),
        )
        db.add(action)
        await db.flush()
        return {
            "action_id": action.id,
            "executor": executor,
            "routing_reason": reason,
            "status": action.status,
        }

    async def record_approval(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        approval_request_id: str,
        state: str,
        what_happens: str,
        action_id: Optional[str] = None,
        decided_by: str = "",
    ) -> Dict[str, Any]:
        """Record what the approval authority did. This never grants anything."""
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        if state not in {"pending", "approved", "refused", "expired"}:
            raise LedgerRefused([f"'{state}' is not an approval state the ledger records."])
        if not what_happens.strip():
            raise LedgerRefused(
                ["An approval with no stated consequence cannot be recorded or consented to."]
            )
        record = LedgerApprovalRecord(
            id=_new_id("APR"),
            intent_id=intent_id,
            owner_id=owner_id,
            approval_request_id=approval_request_id,
            action_id=action_id,
            state=state,
            what_happens=what_happens.strip(),
            requested_at=_now(),
            decided_at=_now() if state != "pending" else None,
            decided_by=decided_by,
        )
        db.add(record)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise LedgerConflict(
                f"Approval request {approval_request_id} is already on the ledger."
            ) from exc
        return {"approval_id": record.id, "state": state}

    async def record_artifact(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        path: str,
        sha256: str = "",
        media_type: str = "application/octet-stream",
        action_id: Optional[str] = None,
        body: str = "",
        kind: str = "lesson",
    ) -> Dict[str, Any]:
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        payload = body or ""
        record = ArtifactRecord(
            id=_new_id("ART"),
            intent_id=intent_id,
            owner_id=owner_id,
            action_id=action_id,
            path=path,
            sha256=sha256,
            media_type=media_type,
            body=payload,
            kind=(kind or "lesson").strip().lower() or "lesson",
            created_at=_now(),
        )
        db.add(record)
        await db.flush()
        return {
            "artifact_id": record.id,
            "path": path,
            "sha256": sha256,
            "media_type": media_type,
            "body": record.body,
            "kind": record.kind,
        }

    async def record_error(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        message: str,
        intent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = ErrorRecord(
            id=_new_id("ERR"),
            intent_id=intent_id,
            owner_id=owner_id,
            action_id=action_id,
            message=message,
            detail=detail or {},
            occurred_at=_now(),
        )
        db.add(record)
        await db.flush()
        return {"error_id": record.id}

    async def record_verification(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        method: str,
        passed: bool,
        evidence: str,
        action_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a read back. Evidence is mandatory: without it there is no verification."""
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        if not evidence.strip():
            raise LedgerRefused(
                ["A verification with no evidence is a claim. Name what was read back."]
            )
        record = VerificationRecord(
            id=_new_id("VER"),
            intent_id=intent_id,
            owner_id=owner_id,
            action_id=action_id,
            method=method,
            passed=passed,
            evidence=evidence.strip(),
            verified_at=_now(),
        )
        db.add(record)
        await db.flush()
        return {"verification_id": record.id, "passed": passed}

    async def record_learning_candidate(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        summary: str,
    ) -> Dict[str, Any]:
        """Park something that might become a lesson. The learning lane rules on it."""
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        if not summary.strip():
            raise LedgerRefused(["A learning candidate with no summary teaches nothing."])
        record = LearningCandidateRecord(
            id=_new_id("LRN"),
            intent_id=intent_id,
            owner_id=owner_id,
            summary=summary.strip(),
            status="candidate",
            created_at=_now(),
        )
        db.add(record)
        await db.flush()
        return {"candidate_id": record.id, "status": "candidate"}

    async def issue_receipt(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        what_happened: str,
        verification: str,
        provenance: str,
        artifacts: Optional[Sequence[str]] = None,
        learned: str = "",
        next_steps: str = "",
    ) -> Dict[str, Any]:
        """Close an intent with its one Universal Receipt.

        Three gates, in order: the intent must have reached something a receipt
        can honestly report, the receipt must carry its required content, and
        the intent must not already hold one. The third is checked here and
        again by a unique constraint, so a race loses rather than overwrites.
        """
        intent = await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        seen = await self._event_names(db, intent_id=intent_id)

        receiptable, reason = ecosystem.intent_is_receiptable(seen, effect=intent.is_effect)
        if not receiptable:
            raise LedgerRefused([reason])

        existing = await db.execute(
            select(UniversalReceiptRecord.intent_id).where(
                UniversalReceiptRecord.intent_id == intent_id
            )
        )
        already = [row[0] for row in existing.all()]

        receipt = ecosystem.UniversalReceipt(
            intent_id=intent_id,
            what_happened=what_happened,
            verification=verification,
            provenance=provenance,
            artifacts=list(artifacts or []),
            learned=learned or None,
            next_steps=next_steps or None,
        )
        failures = ecosystem.check_receipt(receipt, already_receipted=already)
        if failures:
            raise LedgerRefused(failures)

        record = UniversalReceiptRecord(
            id=_new_id("RCP"),
            intent_id=intent_id,
            owner_id=owner_id,
            what_happened=receipt.what_happened.strip(),
            verification=receipt.verification.strip(),
            provenance=receipt.provenance.strip(),
            artifacts=list(receipt.artifacts),
            learned=learned,
            next_steps=next_steps,
            issued_at=_now(),
        )
        db.add(record)
        intent.state = ecosystem.IntentState.RECEIPTED.value
        intent.updated_at = _now()
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise LedgerConflict(
                f"Intent {intent_id} already holds its one receipt. "
                "An amendment is a new intent, never a second receipt."
            ) from exc
        return {"receipt_id": record.id, "intent_id": intent_id, "state": intent.state}

    async def engage_emergency_stop(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        reason: str,
        changed_by: str,
    ) -> Dict[str, Any]:
        """Engage the stop. Permitted from any level: a stop that needs permission is not a stop."""
        record = await self._stop_record(db, owner_id=owner_id)
        if record is None:
            record = SystemRecord(
                id=_new_id("SYS"),
                owner_id=owner_id,
                name=EMERGENCY_STOP_NAME,
                kind="control",
                status="stopped",
                reason=reason,
                changed_by=changed_by,
                updated_at=_now(),
            )
            db.add(record)
        else:
            record.status = "stopped"
            record.reason = reason
            record.changed_by = changed_by
            record.updated_at = _now()
        await db.flush()
        return {"emergency_stop": "stopped", "reason": reason, "changed_by": changed_by}

    async def release_emergency_stop(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        actor: ecosystem.Authority,
        changed_by: str,
    ) -> Dict[str, Any]:
        """Release the stop. Only Tee, because releasing lets effects run again."""
        permitted, reason = ecosystem.may_release_emergency_stop(actor)
        if not permitted:
            raise LedgerRefused([reason])
        record = await self._stop_record(db, owner_id=owner_id)
        if record is None:
            return {"emergency_stop": "ok", "reason": "the stop was not engaged"}
        record.status = "ok"
        record.reason = ""
        record.changed_by = changed_by
        record.updated_at = _now()
        await db.flush()
        return {"emergency_stop": "ok", "released_by": changed_by}

    async def _stop_record(
        self, db: AsyncSession, *, owner_id: str
    ) -> Optional[SystemRecord]:
        result = await db.execute(
            select(SystemRecord).where(
                SystemRecord.owner_id == owner_id,
                SystemRecord.name == EMERGENCY_STOP_NAME,
            )
        )
        return result.scalar_one_or_none()

    async def read_intent(
        self, db: AsyncSession, *, owner_id: str, intent_id: str
    ) -> Dict[str, Any]:
        """The present tense of one intent, with everything hanging off it."""
        intent = await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        events = await db.execute(
            select(EventRecord)
            .where(EventRecord.intent_id == intent_id)
            .order_by(EventRecord.sequence_no)
        )
        event_rows = list(events.scalars().all())
        actions = await db.execute(
            select(ActionRecord).where(ActionRecord.intent_id == intent_id)
        )
        artifacts = await db.execute(
            select(ArtifactRecord).where(ArtifactRecord.intent_id == intent_id)
        )
        receipt = await db.execute(
            select(UniversalReceiptRecord).where(
                UniversalReceiptRecord.intent_id == intent_id
            )
        )
        receipt_row = receipt.scalar_one_or_none()
        names = [row.name for row in event_rows]
        receiptable, receipt_reason = ecosystem.intent_is_receiptable(
            names, effect=intent.is_effect
        )
        return {
            "intent": {
                "intent_id": intent.id,
                "channel": intent.channel,
                "stated": intent.stated,
                "state": intent.state,
                "is_effect": intent.is_effect,
            },
            "events": [
                {
                    "name": row.name,
                    "sequence_no": row.sequence_no,
                    "action_id": row.action_id,
                    "payload": row.payload,
                }
                for row in event_rows
            ],
            "actions": [
                {
                    "action_id": row.id,
                    "duty": row.duty,
                    "executor": row.executor,
                    "status": row.status,
                }
                for row in actions.scalars().all()
            ],
            "artifacts": [
                {
                    "artifact_id": row.id,
                    "path": row.path,
                    "sha256": row.sha256,
                    "body": row.body,
                    "kind": row.kind,
                }
                for row in artifacts.scalars().all()
            ],
            "receipt": (
                {
                    "receipt_id": receipt_row.id,
                    "what_happened": receipt_row.what_happened,
                    "verification": receipt_row.verification,
                    "provenance": receipt_row.provenance,
                    "artifacts": receipt_row.artifacts,
                    "learned": receipt_row.learned,
                    "next_steps": receipt_row.next_steps,
                }
                if receipt_row is not None
                else None
            ),
            "next_legal_events": list(
                ecosystem.next_legal_events(names, effect=intent.is_effect)
            ),
            "receiptable": receiptable,
            "receiptable_reason": receipt_reason,
        }

    async def intent_id_for_approval_request(
        self, db: AsyncSession, *, owner_id: str, request_id: str
    ) -> str:
        """Find the intent that raised this approval. One request, one intent."""
        result = await db.execute(
            select(EventRecord).where(
                EventRecord.owner_id == owner_id,
                EventRecord.name == "PLAN_CREATED",
            )
        )
        for row in result.scalars().all():
            payload = row.payload or {}
            if payload.get("approval_request_id") == request_id:
                return row.intent_id
        raise LedgerRefused(
            [f"No knowledge-loop plan on this owner's record for {request_id}."]
        )

    async def search_receipted_captures(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        query: str,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Find committed captures by text. Unapproved proposals are not memories.

        Tee rulings outrank operator files, which outrank notes. Still ILIKE,
        not Pinecone soul-hierarchy recall. The artifact body is the payload;
        estate:// is a path label, not a blob store. Query * skips the text
        filter so plate/brief can list receipted files.
        """
        from services.memory import OPERATIONAL_KINDS, rank_label

        needle = (query or "").strip()
        if not needle:
            return []
        scan_all = needle in {"*", "all"}
        pattern = f"%{needle}%"
        precedence = case(
            (ArtifactRecord.kind == "ruling", 0),
            (ArtifactRecord.kind.in_(tuple(sorted(OPERATIONAL_KINDS))), 1),
            else_=2,
        )
        filters = [IntentRecord.owner_id == owner_id]
        if not scan_all:
            filters.append(
                or_(
                    IntentRecord.stated.ilike(pattern),
                    ArtifactRecord.body.ilike(pattern),
                )
            )
        wanted = (kind or "").strip().lower()
        if wanted:
            filters.append(ArtifactRecord.kind == wanted)
        result = await db.execute(
            select(IntentRecord, UniversalReceiptRecord, ArtifactRecord)
            .join(
                UniversalReceiptRecord,
                UniversalReceiptRecord.intent_id == IntentRecord.id,
            )
            .outerjoin(ArtifactRecord, ArtifactRecord.intent_id == IntentRecord.id)
            .where(*filters)
            .order_by(precedence.asc(), IntentRecord.created_at.desc())
            .limit(limit)
        )
        found: list[dict] = []
        seen: set[str] = set()
        for intent, receipt, artifact in result.all():
            if intent.id in seen:
                continue
            seen.add(intent.id)
            kind_name = artifact.kind if artifact is not None else "lesson"
            body = (artifact.body if artifact is not None else "") or intent.stated
            found.append(
                {
                    "intent_id": intent.id,
                    "text": body,
                    "body": body,
                    "kind": kind_name,
                    "rank": rank_label(kind_name),
                    "state": intent.state,
                    "artifact_path": artifact.path if artifact is not None else None,
                    "receipt_id": receipt.id,
                    "what_happened": receipt.what_happened,
                    "source": "live-state-ledger",
                    "store": "postgresql",
                    "durable": True,
                    "live": False,
                }
            )
        return found


ledger = LiveStateLedger()
