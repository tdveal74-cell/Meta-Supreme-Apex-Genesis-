"""Owner-scoped evidence kept outside conversation/task snapshots."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentToolResultRecord(Base):
    __tablename__ = 'agent_tool_results'
    __table_args__ = (UniqueConstraint('owner_id', 'task_id', 'step_id', 'generation', name='uq_agent_tool_result_step_generation'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('users.id', ondelete='CASCADE'))
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey('agent_tasks.id', ondelete='CASCADE'))
    step_id: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentVerificationRecord(Base):
    __tablename__ = 'agent_verifications'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('users.id', ondelete='CASCADE'))
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey('agent_tasks.id', ondelete='CASCADE'))
    generation: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSkillRevisionRecord(Base):
    __tablename__ = 'agent_skill_revisions'
    __table_args__ = (UniqueConstraint('owner_id', 'skill_name', 'version', name='uq_agent_skill_revision_version'),)
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('users.id', ondelete='CASCADE'))
    skill_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    parent_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSkillEvaluationRecord(Base):
    __tablename__ = 'skill_evaluation_runs'
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('users.id', ondelete='CASCADE'))
    skill_name: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    suite_id: Mapped[str] = mapped_column(String(200))
    suite_version: Mapped[str] = mapped_column(String(100))
    source_task_id: Mapped[str] = mapped_column(String(100))
    evidence: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
