"""
The approval gate. Every high impact action passes through here.

Modelled on the live n8n Approval Queue (workflow syRVj0G47mA1b0Xn, data table
approval_queue u6wzeN5y9LNxROsN), recorded in SYS_SPEC_context-pill_v16 section
B11 as verified across all eight paths on 2026-08-22.

Two non-negotiables meet at this module:
  Meta Supreme: automation never commits effects unattended.
  DEVON: nothing publishes without a human watching end to end, and rulings are
  Tee's, never a model's.

DESIGN NOTES CARRIED OVER FROM THE VERIFIED BUILD

`what_happens` is mandatory. A request with no stated consequence is refused at
the door. An approver cannot consent to an effect nobody described.

Fails closed by data shape, not by routing. A refusal resolves to the sentinel
NO_MATCH, which matches no record, so a mis-wired caller writes nothing rather
than writing something. Routing can be got wrong by editing a graph. Data shape
cannot.

The queue is storage-agnostic. The in-memory store remains useful for offline
and unit work, while production can supply a durable shared store through the
same protocol. A backend failure is allowed to fail the request; it must never
silently fall back to a weaker store.

Only a hash of the token is stored, never the token itself. The plaintext is
returned once, to the caller raising the request, and is not recoverable from the
queue afterwards. That keeps a store dump free of usable tokens, and it lets the
state check run after the token check without either being weakened: a genuine
holder replaying a consumed token is told the request was already decided, while
a wrong token is told only that it does not match.

Tokens are compared with hmac.compare_digest. A check that short circuits on the
first wrong byte leaks the token one character at a time.

Decision transitions are compare-and-set. A store may be shared by several
workers, but only the worker that atomically changes a row from `pending` may
report a successful ruling. A losing worker reads the authoritative final state
and refuses the replay.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Protocol

SOURCE = {
    "workflow": "syRVj0G47mA1b0Xn",
    "data_table": "approval_queue u6wzeN5y9LNxROsN",
    "recorded_in": "SYS_SPEC_context-pill_v16 section B11",
    "read": "2026-08-22",
}

EXPIRY_HOURS = 72
NO_MATCH = "NO_MATCH"
TOKEN_BYTES = 32


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REFUSED = "refused"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    """Approved, and the effect it authorised has been performed.

    Without this an approval is a standing permission rather than a permission
    to do one thing once. The capability boundary checked that a record was
    APPROVED and bound to these arguments, and both stayed true forever, so the
    same approved effect could be replayed indefinitely by anyone who kept the
    metadata. Consuming is what makes an approval single use at the boundary,
    the way `decide` already made the token single use at the gate.
    """


class Decision(str, Enum):
    APPROVE = "approve"
    REFUSE = "refuse"


class RefusalReason(str, Enum):
    """Every refusal names its reason. Silence is the failure this prevents."""

    NO_ID = "no request id supplied"
    UNKNOWN_ID = "no request with that id"
    WRONG_TOKEN = "token does not match"
    UNRECOGNISED_DECISION = "decision must be approve or refuse"
    EXPIRED = "request expired"
    ALREADY_DECIDED = "request was already decided"
    ALREADY_CONSUMED = "approved effect was already performed"
    NO_CONSEQUENCE = "request did not state what happens"
    NO_TITLE = "request did not state a title"


class ApprovalError(ValueError):
    """Raised when a request cannot be created."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    """Hash a token for storage. The plaintext never lands in the queue."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalRequest:
    """One pending high impact action awaiting a human ruling."""

    request_id: str
    title: str
    what_happens: str
    requested_by: str
    area: Optional[str] = None
    reversible: bool = False
    blast_radius: str = "unstated"
    # The account the card belongs to. Empty means raised by a lane that has no
    # user in hand (the operator bridge, a presence turn). The API scopes list
    # and decide by this value; the gate itself does not read it.
    owner_id: str = ""
    created_at: datetime = field(default_factory=_now)
    expires_at: datetime = field(default_factory=lambda: _now() + timedelta(hours=EXPIRY_HOURS))
    state: ApprovalState = ApprovalState.PENDING
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    _token_hash: str = ""

    def is_expired(self, at: Optional[datetime] = None) -> bool:
        return (at or _now()) >= self.expires_at

    def summary(self) -> str:
        """What the approver reads before ruling."""
        return "\n".join(
            [
                f"Approval requested: {self.title}",
                f"What happens: {self.what_happens}",
                f"Requested by: {self.requested_by}",
                f"Area: {self.area or 'unstated'}",
                f"Reversible: {'yes' if self.reversible else 'no'}",
                f"Blast radius: {self.blast_radius}",
                f"Expires: {self.expires_at.isoformat()}",
            ]
        )


@dataclass(frozen=True)
class DecisionResult:
    """The outcome of a decide call. Always states its reason."""

    ok: bool
    request_id: str
    state: Optional[ApprovalState] = None
    reason: Optional[RefusalReason] = None
    message: str = ""

    @property
    def approved(self) -> bool:
        return self.ok and self.state is ApprovalState.APPROVED


class ApprovalStore(Protocol):
    """Storage interface, so the gate is not tied to one backend."""

    backend_name: str

    def put(self, request: ApprovalRequest) -> None: ...

    def get(self, request_id: str) -> Optional[ApprovalRequest]: ...

    def transition_pending(self, request: ApprovalRequest) -> bool:
        """Atomically replace a pending record; false means another actor won."""
        ...

    def transition_approved(self, request: ApprovalRequest) -> bool:
        """Atomically spend an approved record; false means it was already spent.

        Separate from `transition_pending` rather than a generalisation of it
        because the guard differs: that one refuses anything not PENDING, this
        one refuses anything not APPROVED. Collapsing them into one "expected
        state" argument would let a caller pass the state it hopes to find.
        """
        ...

    def pending(self) -> List[ApprovalRequest]: ...


class InMemoryApprovalStore:
    """Process-local store for offline work and single-process tests."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRequest] = {}

    def put(self, request: ApprovalRequest) -> None:
        self._records[request.request_id] = request

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._records.get(request_id)

    def transition_pending(self, request: ApprovalRequest) -> bool:
        current = self._records.get(request.request_id)
        if current is None or current.state is not ApprovalState.PENDING:
            return False
        self._records[request.request_id] = request
        return True

    def transition_approved(self, request: ApprovalRequest) -> bool:
        current = self._records.get(request.request_id)
        if current is None or current.state is not ApprovalState.APPROVED:
            return False
        self._records[request.request_id] = request
        return True

    def pending(self) -> List[ApprovalRequest]:
        return [
            r
            for r in self._records.values()
            if r.state is ApprovalState.PENDING and not r.is_expired()
        ]

    def all(self) -> List[ApprovalRequest]:
        return list(self._records.values())


class ApprovalQueue:
    """The gate itself.

    `request` returns the record and its single use token. `decide` consumes the
    token. Nothing here performs the approved effect: the caller does that only
    after `decide` returns approved, which keeps the gate free of any capability
    it could be tricked into using.
    """

    def __init__(self, store: Optional[ApprovalStore] = None) -> None:
        self._store = store or InMemoryApprovalStore()

    @property
    def storage_backend(self) -> str:
        return getattr(self._store, "backend_name", self._store.__class__.__name__)

    def request(
        self,
        title: str,
        what_happens: str,
        requested_by: str,
        area: Optional[str] = None,
        reversible: bool = False,
        blast_radius: str = "unstated",
        owner_id: str = "",
    ) -> tuple[ApprovalRequest, str]:
        """Raise a request. Refuses at the door if the consequence is unstated."""
        if not title or not title.strip():
            raise ApprovalError(RefusalReason.NO_TITLE.value)
        if not what_happens or not what_happens.strip():
            raise ApprovalError(
                RefusalReason.NO_CONSEQUENCE.value
                + ". An approver cannot consent to an effect nobody described."
            )

        token = secrets.token_urlsafe(TOKEN_BYTES)
        record = ApprovalRequest(
            request_id=f"REQ-{secrets.token_hex(6).upper()}",
            title=title.strip(),
            what_happens=what_happens.strip(),
            requested_by=requested_by,
            area=area,
            reversible=reversible,
            blast_radius=blast_radius,
            owner_id=(owner_id or "").strip(),
            _token_hash=_hash_token(token),
        )
        self._store.put(record)
        return record, token

    def decide(
        self,
        request_id: Optional[str],
        token: Optional[str],
        decision: Optional[str],
        decided_by: str = "Tee",
        at: Optional[datetime] = None,
    ) -> DecisionResult:
        """Rule on a pending request. Single use, expiring, fails closed.

        The eight paths verified on the live queue are each handled explicitly
        and each names its reason, because a refusal nobody hears is the same as
        an approval. The store transition is atomic so this remains single-use
        when several workers share one backend.
        """
        at = at or _now()

        if not request_id:
            return DecisionResult(
                False, NO_MATCH, reason=RefusalReason.NO_ID, message="No id supplied."
            )

        record = self._store.get(request_id)
        if record is None:
            return DecisionResult(
                False,
                NO_MATCH,
                reason=RefusalReason.UNKNOWN_ID,
                message=f"No request {request_id}.",
            )

        if not token or not hmac.compare_digest(record._token_hash, _hash_token(token)):
            return DecisionResult(
                False,
                NO_MATCH,
                reason=RefusalReason.WRONG_TOKEN,
                message="Token does not match.",
            )

        if record.state is not ApprovalState.PENDING:
            return self._already_decided(record)

        if record.is_expired(at):
            expired = replace(record, state=ApprovalState.EXPIRED, decided_at=at)
            if self._store.transition_pending(expired):
                return DecisionResult(
                    False,
                    NO_MATCH,
                    state=ApprovalState.EXPIRED,
                    reason=RefusalReason.EXPIRED,
                    message=f"Expired at {record.expires_at.isoformat()}.",
                )
            return self._race_lost(record.request_id)

        normalized = (decision or "").strip().lower()
        if normalized not in (Decision.APPROVE.value, Decision.REFUSE.value):
            return DecisionResult(
                False,
                NO_MATCH,
                reason=RefusalReason.UNRECOGNISED_DECISION,
                message=f"'{decision}' is not approve or refuse.",
            )

        new_state = (
            ApprovalState.APPROVED
            if normalized == Decision.APPROVE.value
            else ApprovalState.REFUSED
        )
        decided = replace(
            record,
            state=new_state,
            decided_at=at,
            decided_by=(decided_by or "Tee").strip() or "Tee",
        )
        if not self._store.transition_pending(decided):
            return self._race_lost(record.request_id)

        return DecisionResult(
            True,
            record.request_id,
            state=new_state,
            message=f"{new_state.value} by {decided.decided_by}.",
        )

    def consume(
        self,
        request_id: Optional[str],
        consumed_by: str = "DEVON Agent Runtime",
        at: Optional[datetime] = None,
    ) -> DecisionResult:
        """Spend an approved record so its effect cannot be performed twice.

        Called by the capability boundary once it has satisfied itself that the
        record authorises exactly the effect about to run. It is deliberately
        the last thing checked and the last thing changed: everything cheap and
        non-destructive happens first, so a request refused for any other reason
        leaves the approval still spendable.

        Returns a DecisionResult rather than a bare bool so a replay attempt
        arrives with a reason attached. A refusal nobody can explain is the
        failure this queue was built to avoid.
        """
        at = at or _now()

        if not request_id:
            return DecisionResult(
                False, NO_MATCH, reason=RefusalReason.NO_ID, message="No request id."
            )

        record = self._store.get(request_id)
        if record is None:
            return DecisionResult(
                False,
                NO_MATCH,
                reason=RefusalReason.UNKNOWN_ID,
                message=f"No request {request_id}.",
            )

        if record.state is ApprovalState.CONSUMED:
            return DecisionResult(
                False,
                record.request_id,
                state=ApprovalState.CONSUMED,
                reason=RefusalReason.ALREADY_CONSUMED,
                message="This approval was already spent; raise a new one.",
            )

        if record.state is not ApprovalState.APPROVED:
            return DecisionResult(
                False,
                record.request_id,
                state=record.state,
                reason=RefusalReason.ALREADY_DECIDED,
                message=f"State is {record.state.value}, not approved.",
            )

        spent = replace(
            record,
            state=ApprovalState.CONSUMED,
            decided_at=record.decided_at or at,
            decided_by=record.decided_by or (consumed_by or "").strip() or None,
        )
        if not self._store.transition_approved(spent):
            # Another worker spent it between the read and the write. The effect
            # is running exactly once; this caller is simply not the one running it.
            return DecisionResult(
                False,
                record.request_id,
                state=ApprovalState.CONSUMED,
                reason=RefusalReason.ALREADY_CONSUMED,
                message="This approval was spent by another worker.",
            )

        return DecisionResult(
            True,
            record.request_id,
            state=ApprovalState.CONSUMED,
            message="Approval spent.",
        )

    def pending(self) -> List[ApprovalRequest]:
        return self._store.pending()

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        record = self._store.get(request_id)
        if record is None or record.state is not ApprovalState.PENDING:
            return record
        if not record.is_expired():
            return record

        expired = replace(record, state=ApprovalState.EXPIRED, decided_at=_now())
        if self._store.transition_pending(expired):
            return expired
        return self._store.get(request_id)

    @staticmethod
    def _already_decided(record: ApprovalRequest) -> DecisionResult:
        return DecisionResult(
            False,
            NO_MATCH,
            state=record.state,
            reason=RefusalReason.ALREADY_DECIDED,
            message=f"Already {record.state.value}. A token is single use.",
        )

    def _race_lost(self, request_id: str) -> DecisionResult:
        latest = self._store.get(request_id)
        if latest is None:
            return DecisionResult(
                False,
                NO_MATCH,
                reason=RefusalReason.UNKNOWN_ID,
                message=f"No request {request_id}.",
            )
        return self._already_decided(latest)
