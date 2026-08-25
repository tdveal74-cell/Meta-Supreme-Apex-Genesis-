"""Durable persistence models for DEVON Agent Runtime.

These records are application storage for the framework-free runtime contracts.
They do not move execution capability into ``services.devon``.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
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


class AgentTaskRecord(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_generation: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentTaskRunRecord(Base):
    __tablename__ = "agent_task_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "task_id",
            "idempotency_key",
            name="uq_agent_task_runs_owner_task_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentTaskCheckpointRecord(Base):
    __tablename__ = "agent_task_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    current_step: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRuntimeMemory(Base):
    __tablename__ = "agent_runtime_memories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="operator", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AgentRuntimeSkill(Base):
    __tablename__ = "agent_runtime_skills"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_agent_runtime_skill_owner_name"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provenance: Mapped[str] = mapped_column(String(120), default="operator", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AgentEffectIntentRecord(Base):
    __tablename__ = "agent_effect_intents"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "task_id",
            "intent_id",
            name="uq_agent_effect_intents_owner_task_intent",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentEffectReceiptRecord(Base):
    __tablename__ = "agent_effect_receipts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "intent_id",
            name="uq_agent_effect_receipts_owner_intent",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_receipt_id: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    raw_response: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    execution_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentScheduleRecord(Base):
    """Durable delayed goal for Hermes scheduler."""

    __tablename__ = "agent_schedules"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "schedule_id",
            name="uq_agent_schedules_owner_schedule",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentSkillProposalRecord(Base):
    """Durable skill proposal awaiting human promote/reject."""

    __tablename__ = "agent_skill_proposals"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "proposal_id",
            name="uq_agent_skill_proposals_owner_proposal",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    source_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
