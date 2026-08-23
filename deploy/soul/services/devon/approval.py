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

No external dependency in the decision path. The live queue deliberately avoids
Airtable so the gate keeps working while the base is quota blocked. The store
here is an interface with an in-memory default for the same reason: the gate
must not fail open because a backend is down.

Only a hash of the token is stored, never the token itself. The plaintext is
returned once, to the caller raising the request, and is not recoverable from the
queue afterwards. That keeps a store dump free of usable tokens, and it lets the
state check run after the token check without either being weakened: a genuine
holder replaying a consumed token is told the request was already decided, while
a wrong token is told only that it does not match.

Tokens are compared with hmac.compare_digest. A check that short circuits on the
first wrong byte leaks the token one character at a time.
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

    def put(self, request: ApprovalRequest) -> None: ...

    def get(self, request_id: str) -> Optional[ApprovalRequest]: ...

    def update(self, request: ApprovalRequest) -> None: ...

    def pending(self) -> List[ApprovalRequest]: ...


class InMemoryApprovalStore:
    """Default store. Process local, deliberately simple.

    Suitable for a single operator assistant on one machine, which is the actual
    deployment. A durable store is a drop in replacement through the protocol.
    """

    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRequest] = {}

    def put(self, request: ApprovalRequest) -> None:
        self._records[request.request_id] = request

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._records.get(request_id)

    def update(self, request: ApprovalRequest) -> None:
        self._records[request.request_id] = request

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

    def request(
        self,
        title: str,
        what_happens: str,
        requested_by: str,
        area: Optional[str] = None,
        reversible: bool = False,
        blast_radius: str = "unstated",
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
        an approval.
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
            return DecisionResult(
                False,
                NO_MATCH,
                state=record.state,
                reason=RefusalReason.ALREADY_DECIDED,
                message=f"Already {record.state.value}. A token is single use.",
            )

        if record.is_expired(at):
            expired = replace(record, state=ApprovalState.EXPIRED, decided_at=at)
            self._store.update(expired)
            return DecisionResult(
                False,
                NO_MATCH,
                state=ApprovalState.EXPIRED,
                reason=RefusalReason.EXPIRED,
                message=f"Expired at {record.expires_at.isoformat()}.",
            )

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
            decided_by=decided_by,
        )
        self._store.update(decided)
        return DecisionResult(
            True,
            record.request_id,
            state=new_state,
            message=f"{new_state.value} by {decided_by}.",
        )

    def pending(self) -> List[ApprovalRequest]:
        return self._store.pending()

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._store.get(request_id)
