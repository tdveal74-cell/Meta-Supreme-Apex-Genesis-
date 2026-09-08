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

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import case, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
from services.devon import provenance as hashchain

EMERGENCY_STOP_NAME = "emergency_stop"


#: Every state an approval row may hold. 'consumed' is the state 013 taught the
#: DEVON queue and 018 taught this table: an approved effect that has run. The
#: ledger records the outcome; it never grants anything.
_APPROVAL_STATES = ("pending", "approved", "consumed", "refused", "expired")

#: The states settle_approval may move a row into, and the states a row must
#: already hold for that move to be lawful. A move that is not listed here is
#: refused rather than silently applied.
_SETTLEMENTS = {
    "consumed": ("approved",),
    "refused": ("pending",),
    "expired": ("pending",),
}


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


def _signing_key() -> str:
    """The key that signs receipts. Read at call time so a rotation takes
    effect without a restart of this module's state.

    A dedicated RECEIPT_SIGNING_KEY when set; otherwise a key derived from
    SECRET_KEY, so a receipt is never signed under the JWT key itself.
    """
    dedicated = (settings.RECEIPT_SIGNING_KEY or "").strip()
    if dedicated:
        return dedicated
    return hashchain.derive_receipt_key(settings.SECRET_KEY)


def _signing_ring() -> List[str]:
    """The current key first, then every key a receipt may still have been
    signed under.

    The key derived from the current SECRET_KEY is always in the ring, so
    moving from the derived default to a dedicated key keeps every earlier
    receipt verifying. Entries in RECEIPT_SIGNING_KEYS_PREVIOUS are raw keys,
    or ``secret:<old SECRET_KEY>`` for a secret that was rotated while no
    dedicated key was set, which the ring derives the same way the writer did.
    """
    ring: List[str] = [_signing_key()]
    if settings.SECRET_KEY:
        ring.append(hashchain.derive_receipt_key(settings.SECRET_KEY))
    for entry in (settings.RECEIPT_SIGNING_KEYS_PREVIOUS or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if entry.startswith("secret:"):
            old_secret = entry[len("secret:"):].strip()
            if old_secret:
                ring.append(hashchain.derive_receipt_key(old_secret))
        else:
            ring.append(entry)
    seen: List[str] = []
    for key in ring:
        if key not in seen:
            seen.append(key)
    return seen


def _link(row: EventRecord) -> hashchain.ChainLink:
    """One stored event as the verifier sees it. Nothing inferred."""
    return hashchain.ChainLink(
        sequence_no=row.sequence_no,
        name=row.name,
        prev_hash=row.prev_hash or "",
        hash=row.hash or "",
        action_id=row.action_id,
        payload=dict(row.payload or {}),
        occurred_at=hashchain.format_time(row.occurred_at),
    )


async def _as_stored(db: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """The payload as the database will hand it back, decoded the way the ORM
    decodes the stored column.

    PostgreSQL renders jsonb numerics its own way (``1e16`` becomes
    ``10000000000000000``, ``-0.0`` becomes ``0.0``), so a hash over Python's
    rendering never matches the stored row. One round trip through
    ``CAST(... AS jsonb)`` before the insert makes the writer and the verifier
    hash the same bytes. The refusal for NaN, infinity and unencodable text
    lands here, before the insert, with a reason the caller can read.
    """
    problem = hashchain.check_payload(payload)
    if problem is not None:
        raise LedgerRefused([problem])
    rendered = await db.execute(
        text("SELECT CAST(CAST(:payload AS jsonb) AS text)"),
        {"payload": hashchain.canonical(payload)},
    )
    return json.loads(rendered.scalar_one())


async def _hashed_event(
    db: AsyncSession,
    *,
    intent_id: str,
    owner_id: str,
    name: str,
    sequence_no: int,
    prev_hash: str,
    action_id: Optional[str],
    payload: Dict[str, Any],
) -> EventRecord:
    """Build one event with its hash computed over exactly what will be stored.

    ``occurred_at`` is minted here rather than left to the database default,
    because the hash covers it and the verifier recomputes from the stored
    value: the two have to be the same instant to the microsecond. The payload
    is hashed as stored, for the same reason.
    """
    stored = await _as_stored(db, payload)
    occurred_at = _now()
    digest = hashchain.event_hash(
        prev_hash=prev_hash,
        intent_id=intent_id,
        sequence_no=sequence_no,
        name=name,
        action_id=action_id,
        payload=stored,
        occurred_at=hashchain.format_time(occurred_at),
    )
    return EventRecord(
        intent_id=intent_id,
        owner_id=owner_id,
        name=name,
        sequence_no=sequence_no,
        action_id=action_id,
        payload=stored,
        occurred_at=occurred_at,
        prev_hash=prev_hash,
        hash=digest,
    )


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
            await _hashed_event(
                db,
                intent_id=intent.intent_id,
                owner_id=owner_id,
                name="INTENT_RECEIVED",
                sequence_no=1,
                prev_hash=hashchain.GENESIS,
                action_id=None,
                payload={"channel": intent.channel},
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

    async def _event_rows(
        self, db: AsyncSession, *, intent_id: str
    ) -> List[EventRecord]:
        result = await db.execute(
            select(EventRecord)
            .where(EventRecord.intent_id == intent_id)
            .order_by(EventRecord.sequence_no)
        )
        return list(result.scalars().all())

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
        rows = await self._event_rows(db, intent_id=intent_id)
        seen = [row.name for row in rows]
        stopped = await self.emergency_stopped(db, owner_id=owner_id)

        violations = ecosystem.check_event(
            name,
            seen,
            effect=intent.is_effect,
            emergency_stopped=stopped,
        )
        if violations:
            raise LedgerRefused(violations)

        # Nothing is appended to a chain that does not verify. A broken link,
        # an altered row or an unhashed row planted after hashed ones is named
        # here, before a new event could link to it and lend it legitimacy.
        verdict = hashchain.verify_chain(intent_id, [_link(row) for row in rows])
        if not verdict.intact:
            raise LedgerRefused(
                [
                    "The event chain on this intent does not verify, so nothing can be "
                    "appended to it: " + "; ".join(verdict.findings)
                ]
            )

        # The new event links to the hash of the last one. A last event with no
        # hash was written before 019 (the verdict above has just proved every
        # unhashed row is a prefix), and the chain starts from genesis here
        # rather than linking to a hash that never existed.
        prev_hash = rows[-1].hash if rows and rows[-1].hash else hashchain.GENESIS
        record = await _hashed_event(
            db,
            intent_id=intent_id,
            owner_id=owner_id,
            name=name,
            sequence_no=len(seen) + 1,
            prev_hash=prev_hash,
            action_id=action_id,
            payload=dict(payload or {}),
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
            "hash": record.hash,
            "prev_hash": record.prev_hash,
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
        if state not in _APPROVAL_STATES:
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

        Four gates, in order: the intent must have reached something a receipt
        can honestly report, the chain of events it would certify must be
        intact, the receipt must carry its required content, and the intent
        must not already hold one. The last is checked here and again by a
        unique constraint, so a race loses rather than overwrites.

        The receipt binds to the chain head and is signed under the estate key,
        so a later reader can prove that this text was issued over exactly
        these events and has not been touched since.
        """
        intent = await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        rows = await self._event_rows(db, intent_id=intent_id)
        seen = [row.name for row in rows]

        receiptable, reason = ecosystem.intent_is_receiptable(seen, effect=intent.is_effect)
        if not receiptable:
            raise LedgerRefused([reason])

        verdict = hashchain.verify_chain(intent_id, [_link(row) for row in rows])
        if not verdict.intact:
            raise LedgerRefused(
                [
                    "The event chain on this intent does not verify, so no receipt can "
                    "honestly certify it: " + "; ".join(verdict.findings)
                ]
            )

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

        issued_at = _now()
        key = _signing_key()
        digest = hashchain.receipt_digest(
            intent_id=intent_id,
            head_hash=verdict.head_hash,
            chain_length=verdict.length,
            what_happened=receipt.what_happened.strip(),
            verification=receipt.verification.strip(),
            provenance=receipt.provenance.strip(),
            artifacts=list(receipt.artifacts),
            learned=learned,
            next_steps=next_steps,
            issued_at=hashchain.format_time(issued_at),
        )
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
            issued_at=issued_at,
            head_hash=verdict.head_hash,
            chain_length=verdict.length,
            signature=hashchain.sign(digest, key),
            signature_key_id=hashchain.key_id(key),
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
        return {
            "receipt_id": record.id,
            "intent_id": intent_id,
            "state": intent.state,
            "head_hash": record.head_hash,
            "chain_length": record.chain_length,
            "digest": digest,
            "signature": record.signature,
            "signature_key_id": record.signature_key_id,
        }

    async def verify_provenance(
        self, db: AsyncSession, *, owner_id: str, intent_id: str
    ) -> Dict[str, Any]:
        """The signed verification payload: walk the chain and check the receipt.

        Everything here is recomputed from the stored rows. The chain verdict
        needs no key; the signature check needs the estate key and says
        whether the receipt was signed under the key this process holds, so a
        receipt from before a rotation reads as ``signed_with_current_key``
        false rather than as forged.
        """
        await self._intent(db, owner_id=owner_id, intent_id=intent_id)
        rows = await self._event_rows(db, intent_id=intent_id)
        verdict = hashchain.verify_chain(intent_id, [_link(row) for row in rows])

        receipt = await db.execute(
            select(UniversalReceiptRecord).where(
                UniversalReceiptRecord.intent_id == intent_id
            )
        )
        row = receipt.scalar_one_or_none()
        ring = _signing_ring()
        current_key_id = hashchain.key_id(ring[0])
        receipt_report: Dict[str, Any]
        if row is None:
            receipt_report = {
                "present": False,
                "verified": False,
                "findings": ["the intent holds no receipt yet; nothing certifies this chain"],
            }
        else:
            digest = hashchain.receipt_digest(
                intent_id=intent_id,
                head_hash=row.head_hash,
                chain_length=row.chain_length,
                what_happened=row.what_happened,
                verification=row.verification,
                provenance=row.provenance,
                artifacts=list(row.artifacts or []),
                learned=row.learned,
                next_steps=row.next_steps,
                issued_at=hashchain.format_time(row.issued_at),
            )
            findings: List[str] = []
            signed_by = hashchain.find_signing_key(digest, row.signature, ring)
            if not row.signature:
                findings.append("the receipt carries no signature (issued before 019)")
            elif signed_by is None:
                findings.append(
                    "the receipt's signature verifies under none of the keys this "
                    "process holds (the current key and the rotation ring): either "
                    "the receipt text was altered after issue, or it was signed under "
                    f"key {row.signature_key_id or 'unknown'}, which is not in the ring"
                )
            if row.head_hash != verdict.head_hash:
                findings.append(
                    f"the receipt certifies chain head {row.head_hash[:12] or 'none'} "
                    f"but the chain now ends at {verdict.head_hash[:12] or 'none'}: "
                    "events were added, removed or altered after the receipt was issued"
                )
            if row.chain_length != verdict.length:
                findings.append(
                    f"the receipt certifies {row.chain_length} events but the intent "
                    f"holds {verdict.length}"
                )
            receipt_report = {
                "present": True,
                "receipt_id": row.id,
                "issued_at": hashchain.format_time(row.issued_at),
                "head_hash": row.head_hash,
                "chain_length": row.chain_length,
                "digest": digest,
                "signature": row.signature,
                "signature_algorithm": hashchain.SIGNATURE_ALGORITHM,
                "signature_key_id": row.signature_key_id,
                "verified_with_key_id": hashchain.key_id(signed_by) if signed_by else "",
                "signed_with_current_key": signed_by is not None
                and hashchain.key_id(signed_by) == current_key_id,
                "verified": not findings,
                "findings": findings,
            }

        # ``verified`` is the whole claim: a complete chain (every row hashed,
        # every link sound) AND a receipt that certifies exactly that chain.
        # An intent with no receipt is not verified, and neither is one whose
        # prefix predates the chain: the verifier cannot tell pre 019 history
        # from rows planted to look like it, so it does not claim to.
        # ``receipted`` and ``chain.complete`` say which half is missing.
        if verdict.intact and not verdict.complete and verdict.length:
            receipt_report.setdefault("findings", [])
            receipt_report["findings"].append(
                f"{verdict.unhashed} event(s) predate the chain and carry no hash; "
                "the receipt certifies them on trust, not on proof"
            )
        return {
            "intent_id": intent_id,
            "verified": verdict.complete and row is not None and receipt_report["verified"],
            "receipted": row is not None,
            "chain": verdict.to_dict(),
            "receipt": receipt_report,
            "verified_at": hashchain.format_time(_now()),
        }

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
                    "occurred_at": hashchain.format_time(row.occurred_at),
                    "prev_hash": row.prev_hash,
                    "hash": row.hash,
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
                    "issued_at": hashchain.format_time(receipt_row.issued_at),
                    "head_hash": receipt_row.head_hash,
                    "chain_length": receipt_row.chain_length,
                    "signature": receipt_row.signature,
                    "signature_key_id": receipt_row.signature_key_id,
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

    async def approval_binding(
        self, db: AsyncSession, *, owner_id: str, request_id: str
    ) -> Dict[str, Any]:
        """The ledger's own record of which intent raised this approval and how
        it was ruled.

        Written at propose by the knowledge loop and changed only by
        ``rule_approval``. UNIQUE(approval_request_id) makes the binding
        permanent: a later PLAN_CREATED that names the same request id, on
        this intent or any other, cannot redirect approve or commit. The
        generic ``/approvals`` route can insert an observation for a request
        id the ledger has never seen, but never a second row for one it has,
        and it changes nothing.
        """
        result = await db.execute(
            select(LedgerApprovalRecord).where(
                LedgerApprovalRecord.owner_id == owner_id,
                LedgerApprovalRecord.approval_request_id == request_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            raise LedgerRefused(
                [
                    f"No approval binding on this owner's record for {request_id}. "
                    "The knowledge loop binds a request to its intent at propose; "
                    "a request proposed before that binding existed cannot be "
                    "ruled or committed. Propose it again."
                ]
            )
        return {
            "intent_id": str(row.intent_id),
            "state": row.state,
            "decided_by": row.decided_by,
            "decided_at": row.decided_at,
        }

    async def intent_id_for_approval_request(
        self, db: AsyncSession, *, owner_id: str, request_id: str
    ) -> str:
        """Find the intent that raised this approval. One request, one intent."""
        binding = await self.approval_binding(
            db, owner_id=owner_id, request_id=request_id
        )
        return binding["intent_id"]

    async def settle_approval(
        self,
        db: AsyncSession,
        *,
        request_id: str,
        state: str,
        decided_by: str = "",
        owner_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Write what became of an approval the authority already decided.

        The three settlements the ledger could not record before 018: an
        approved effect that ran ('consumed'), a card the operator refused
        ('refused'), and a card that timed out ('expired'). Callers reach this
        holding a request id and nothing else, so the row is found by its
        unique approval_request_id; pass owner_id to scope the lookup when the
        caller has an account in hand.

        Returns None when no ledger row exists for the request. That is the
        normal case, not an error: only the knowledge loop opens ledger
        approvals, and every other lane's cards live in the DEVON queue alone.
        Idempotent on a row that already holds the target state, so a retried
        commit or a second sweep does not raise.
        """
        if state not in _SETTLEMENTS:
            raise LedgerRefused([f"'{state}' is not a settlement the ledger writes."])
        conditions = [LedgerApprovalRecord.approval_request_id == request_id]
        if owner_id is not None:
            conditions.append(LedgerApprovalRecord.owner_id == owner_id)
        result = await db.execute(select(LedgerApprovalRecord).where(*conditions))
        row = result.scalars().first()
        if row is None:
            return None
        if row.state == state:
            return {"approval_id": row.id, "state": row.state, "changed": False}
        if row.state not in _SETTLEMENTS[state]:
            raise LedgerRefused(
                [
                    f"Approval {request_id} is {row.state} on the ledger and "
                    f"cannot become {state} now."
                ]
            )
        row.state = state
        row.decided_at = _now()
        if decided_by:
            row.decided_by = decided_by.strip()[:120]
        await db.flush()
        return {"approval_id": row.id, "state": row.state, "changed": True}

    async def rule_approval(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        request_id: str,
        decided_by: str,
    ) -> Dict[str, Any]:
        """Move the ledger's approval row from pending to approved.

        Service-only: no route reaches this, so the row's state is the
        knowledge loop's own word that the ruling-key lane ruled. Commit
        reads this state, never an event name. Idempotent on a row that is
        already approved, which is the repair path after a commit that died.
        """
        result = await db.execute(
            select(LedgerApprovalRecord).where(
                LedgerApprovalRecord.owner_id == owner_id,
                LedgerApprovalRecord.approval_request_id == request_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            raise LedgerRefused(
                [f"No approval binding on this owner's record for {request_id}."]
            )
        if row.state == "approved":
            return {"approval_id": row.id, "state": row.state, "changed": False}
        if row.state != "pending":
            raise LedgerRefused(
                [
                    f"Approval {request_id} is {row.state} on the ledger and "
                    "cannot be approved now."
                ]
            )
        row.state = "approved"
        row.decided_at = _now()
        row.decided_by = (decided_by or "").strip()[:120]
        await db.flush()
        return {"approval_id": row.id, "state": row.state, "changed": True}

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
        filter so plate/brief can list receipted files. ILIKE metacharacters
        in the query are escaped, so a literal % or _ is searched for rather
        than rewriting the match. Rows are paged until `limit` DISTINCT
        intents are collected: an intent can carry several artifacts, and
        limiting the raw join let multi-artifact intents crowd matching
        captures out of the window. Labeling (store, source, rank) belongs to
        services.memory, not here.
        """
        from services.memory import OPERATIONAL_KINDS

        needle = (query or "").strip()
        if not needle:
            return []
        scan_all = needle in {"*", "all"}
        escaped = (
            needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        precedence = case(
            (ArtifactRecord.kind == "ruling", 0),
            (ArtifactRecord.kind.in_(tuple(sorted(OPERATIONAL_KINDS))), 1),
            else_=2,
        )
        filters = [IntentRecord.owner_id == owner_id]
        if not scan_all:
            filters.append(
                or_(
                    IntentRecord.stated.ilike(pattern, escape="\\"),
                    ArtifactRecord.body.ilike(pattern, escape="\\"),
                )
            )
        wanted = (kind or "").strip().lower()
        if wanted:
            filters.append(ArtifactRecord.kind == wanted)
        base_query = (
            select(IntentRecord, UniversalReceiptRecord, ArtifactRecord)
            .join(
                UniversalReceiptRecord,
                UniversalReceiptRecord.intent_id == IntentRecord.id,
            )
            .outerjoin(ArtifactRecord, ArtifactRecord.intent_id == IntentRecord.id)
            .where(*filters)
            .order_by(precedence.asc(), IntentRecord.created_at.desc())
        )
        found: list[dict] = []
        seen: set[str] = set()
        page = max(limit * 2, 40)
        offset = 0
        while len(found) < limit:
            result = await db.execute(base_query.offset(offset).limit(page))
            rows = result.all()
            if not rows:
                break
            offset += len(rows)
            for intent, receipt, artifact in rows:
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
                        "state": intent.state,
                        "artifact_path": artifact.path if artifact is not None else None,
                        "receipt_id": receipt.id,
                        "what_happened": receipt.what_happened,
                        "durable": True,
                    }
                )
                if len(found) >= limit:
                    break
        return found


ledger = LiveStateLedger()
