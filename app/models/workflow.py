"""
Workflow models — automations and their execution history.

A `Workflow` holds a validated definition (trigger + ordered steps) in JSONB.
A `WorkflowRun` is one execution of it: the ordered step results, the
approvals a human granted, the step it is paused in front of (if any), and
what the run cost in tokens.

Runs are the audit trail for automation. Nothing a workflow did is inferred
after the fact — it is recorded here as it happened.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="draft", nullable=False
    )  # draft|active|paused|archived
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Schedule dispatch (Phase 5.1). `next_run_at` is the scheduler's entire
    # state: recomputed on every save and after every fire, NULL for anything
    # that does not fire on a parseable cadence. The dispatcher's query is an
    # indexed range scan over it, so it stays cheap when nothing is due.
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String, default="pending", nullable=False
    )  # pending|running|awaiting_approval|completed|halted|failed
    trigger: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    trigger_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step_results: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    approvals: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pending_step_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
