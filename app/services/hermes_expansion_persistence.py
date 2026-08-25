"""Durable persistence for Hermes expansion schedules and skill proposals."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import AgentScheduleRecord, AgentSkillProposalRecord
from services.agent_runtime.expansion import (
    ScheduledGoal,
    ScheduleState,
    SkillProposal,
    SkillProposalState,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HermesExpansionRepository:
    """Owner-scoped durable schedules and skill proposals."""

    async def create_schedule(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        goal: str,
        run_at: datetime,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScheduledGoal:
        clean = (goal or "").strip()
        if not clean:
            raise ValueError("scheduled goal is empty")
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        now = _utcnow()
        state = ScheduleState.DUE if run_at <= now else ScheduleState.PENDING
        schedule_id = f"SCH-{secrets.token_hex(6).upper()}"
        row = AgentScheduleRecord(
            id=f"ASR-{secrets.token_hex(8).upper()}",
            schedule_id=schedule_id,
            owner_id=owner_id,
            goal=clean,
            run_at=run_at,
            state=state.value,
            context=dict(context or {}),
            task_id=None,
            failure_reason="",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return self._schedule_from_row(row)

    async def list_schedules(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
    ) -> List[ScheduledGoal]:
        result = await db.execute(
            select(AgentScheduleRecord)
            .where(AgentScheduleRecord.owner_id == owner_id)
            .order_by(AgentScheduleRecord.run_at.asc())
        )
        return [self._schedule_from_row(row) for row in result.scalars().all()]

    async def due_schedules(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
    ) -> List[ScheduledGoal]:
        now = _utcnow()
        result = await db.execute(
            select(AgentScheduleRecord).where(
                AgentScheduleRecord.owner_id == owner_id,
                AgentScheduleRecord.state.in_(
                    [ScheduleState.PENDING.value, ScheduleState.DUE.value]
                ),
                AgentScheduleRecord.run_at <= now,
            )
        )
        rows = list(result.scalars().all())
        out: List[ScheduledGoal] = []
        for row in rows:
            if row.state == ScheduleState.PENDING.value:
                row.state = ScheduleState.DUE.value
                row.updated_at = now
            out.append(self._schedule_from_row(row))
        await db.flush()
        return out

    async def attach_task(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        schedule_id: str,
        task_id: str,
    ) -> ScheduledGoal:
        result = await db.execute(
            select(AgentScheduleRecord).where(
                AgentScheduleRecord.owner_id == owner_id,
                AgentScheduleRecord.schedule_id == schedule_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise KeyError(f"unknown schedule: {schedule_id}")
        row.task_id = task_id
        row.state = ScheduleState.RUNNING.value
        row.updated_at = _utcnow()
        await db.flush()
        return self._schedule_from_row(row)

    async def mark_from_task_outcome(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        completed: bool,
        failure_reason: str = "",
    ) -> Optional[ScheduledGoal]:
        """If a schedule is linked to this task, mark it completed or failed."""
        result = await db.execute(
            select(AgentScheduleRecord).where(
                AgentScheduleRecord.owner_id == owner_id,
                AgentScheduleRecord.task_id == task_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if row.state in {
            ScheduleState.COMPLETED.value,
            ScheduleState.CANCELLED.value,
        }:
            return self._schedule_from_row(row)
        row.state = (
            ScheduleState.COMPLETED.value if completed else ScheduleState.FAILED.value
        )
        row.failure_reason = (failure_reason or "") if not completed else ""
        row.updated_at = _utcnow()
        await db.flush()
        return self._schedule_from_row(row)

    async def save_skill_proposal(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        proposal: SkillProposal,
    ) -> SkillProposal:
        row = AgentSkillProposalRecord(
            id=f"ASP-{secrets.token_hex(8).upper()}",
            proposal_id=proposal.proposal_id,
            owner_id=owner_id,
            name=proposal.name,
            description=proposal.description,
            instructions=proposal.instructions,
            source_task_id=proposal.source_task_id,
            state=proposal.state.value,
            created_at=proposal.created_at,
            decided_at=None,
        )
        db.add(row)
        await db.flush()
        return proposal

    async def has_skill_proposal_named(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        name: str,
    ) -> bool:
        """True when any proposal for this goal slug already exists.

        A PROPOSED one is awaiting the human decision, a REJECTED one was
        already declined, and an APPROVED one is already promoted - in every
        case drafting another copy of the same goal is noise.
        """
        result = await db.execute(
            select(AgentSkillProposalRecord.id)
            .where(
                AgentSkillProposalRecord.owner_id == owner_id,
                AgentSkillProposalRecord.name == name,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_skill_proposal(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        proposal_id: str,
    ) -> Optional[SkillProposal]:
        result = await db.execute(
            select(AgentSkillProposalRecord).where(
                AgentSkillProposalRecord.owner_id == owner_id,
                AgentSkillProposalRecord.proposal_id == proposal_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._proposal_from_row(row) if row else None

    async def list_skill_proposals(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        state: Optional[str] = None,
    ) -> List[SkillProposal]:
        query = select(AgentSkillProposalRecord).where(
            AgentSkillProposalRecord.owner_id == owner_id
        )
        if state:
            query = query.where(AgentSkillProposalRecord.state == state)
        result = await db.execute(query.order_by(AgentSkillProposalRecord.created_at.asc()))
        return [self._proposal_from_row(row) for row in result.scalars().all()]

    async def decide_skill_proposal(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        proposal_id: str,
        approve: bool,
    ) -> SkillProposal:
        result = await db.execute(
            select(AgentSkillProposalRecord).where(
                AgentSkillProposalRecord.owner_id == owner_id,
                AgentSkillProposalRecord.proposal_id == proposal_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise KeyError(f"unknown skill proposal: {proposal_id}")
        if row.state != SkillProposalState.PROPOSED.value:
            raise ValueError(f"proposal already decided: {row.state}")
        row.state = (
            SkillProposalState.APPROVED.value
            if approve
            else SkillProposalState.REJECTED.value
        )
        row.decided_at = _utcnow()
        await db.flush()
        return self._proposal_from_row(row)

    @staticmethod
    def _schedule_from_row(row: AgentScheduleRecord) -> ScheduledGoal:
        return ScheduledGoal(
            schedule_id=row.schedule_id,
            owner_id=row.owner_id,
            goal=row.goal,
            run_at=row.run_at,
            state=ScheduleState(row.state),
            context=dict(row.context or {}),
            task_id=row.task_id,
            failure_reason=row.failure_reason or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _proposal_from_row(row: AgentSkillProposalRecord) -> SkillProposal:
        return SkillProposal(
            proposal_id=row.proposal_id,
            name=row.name,
            description=row.description,
            instructions=row.instructions,
            source_task_id=row.source_task_id,
            state=SkillProposalState(row.state),
            created_at=row.created_at,
        )
