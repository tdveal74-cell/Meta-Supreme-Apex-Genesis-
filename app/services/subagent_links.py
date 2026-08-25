"""Durable parent→child subagent links."""

from __future__ import annotations

import secrets
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import AgentSubagentLinkRecord


class SubagentLinkRepository:
    async def link(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        parent_task_id: str,
        child_task_id: str,
        subagent_id: str,
    ) -> AgentSubagentLinkRecord:
        row = AgentSubagentLinkRecord(
            id=f"ASL-{secrets.token_hex(8).upper()}",
            owner_id=owner_id,
            parent_task_id=parent_task_id,
            child_task_id=child_task_id,
            subagent_id=subagent_id,
        )
        db.add(row)
        await db.flush()
        return row

    async def list_child_ids(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        parent_task_id: str,
        limit: int = 50,
    ) -> List[str]:
        result = await db.execute(
            select(AgentSubagentLinkRecord.child_task_id)
            .where(
                AgentSubagentLinkRecord.owner_id == owner_id,
                AgentSubagentLinkRecord.parent_task_id == parent_task_id,
            )
            .order_by(AgentSubagentLinkRecord.created_at.asc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]
