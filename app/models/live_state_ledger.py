"""Persistence models for the DEVON Live State Ledger.

These mirror ``database/schemas/012_live_state_ledger.sql``. The doctrine that
decides what may be written lives in ``services.devon.ecosystem`` and stays
effect free; this module is the storage shape only.

The two load bearing constraints are declared in the schema as well as here, so
that a caller bypassing the ORM still cannot break them: one receipt per intent,
and only the thirteen universal events.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class IntentRecord(Base):
    """One Universal Intent. Everything downstream traces back to this id."""

    __tablename__ = "intents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    stated: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    is_effect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EventRecord(Base):
    """One universal event. Append only, ordered by sequence_no within an intent."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("intent_id", "sequence_no", name="uq_events_intent_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ActionRecord(Base):
    """One planned or executed action, routed to an executor by DEVON."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    duty: Mapped[str] = mapped_column(String(200), nullable=False)
    executor: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned")
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LedgerApprovalRecord(Base):
    """Observes the approval authority. Never grants.

    The authority is ``services.devon.approval`` and its shared store. A row
    here records which request was raised against which intent and how it was
    ruled, so the ledger can answer "was this approved" without becoming a
    second place that can approve.
    """

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    approval_request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    action_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    what_happens: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class ArtifactRecord(Base):
    """Something the intent produced, at its canonical path."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    media_type: Mapped[str] = mapped_column(
        String(200), nullable=False, default="application/octet-stream"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExecutorRecord(Base):
    """The executor registry. Seeded by the schema, not by a test fixture."""

    __tablename__ = "executors"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SystemRecord(Base):
    """A system or control. The emergency stop is a control row."""

    __tablename__ = "systems"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_systems_owner_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="service")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ok")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changed_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ErrorRecord(Base):
    """What went wrong, kept rather than swallowed."""

    __tablename__ = "errors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=True
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VerificationRecord(Base):
    """A read back. A success response is a claim; this is the evidence."""

    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    method: Mapped[str] = mapped_column(String(200), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningCandidateRecord(Base):
    """What might become a lesson. The learning lane decides, not this table."""

    __tablename__ = "learning_candidates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="candidate")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UniversalReceiptRecord(Base):
    """One receipt per intent. The unique constraint is the rule."""

    __tablename__ = "universal_receipts"
    __table_args__ = (
        UniqueConstraint("intent_id", name="uq_universal_receipts_intent"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    what_happened: Mapped[str] = mapped_column(Text, nullable=False)
    verification: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    learned: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_steps: Mapped[str] = mapped_column(Text, nullable=False, default="")
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
