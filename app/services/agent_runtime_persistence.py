"""Application persistence for DEVON Agent Runtime.

SQLAlchemy stays in the application layer. The framework-free runtime remains
portable and receives/restores canonical task contracts through snapshots.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import (
    AgentRuntimeMemory,
    AgentRuntimeSkill,
    AgentTaskCheckpointRecord,
    AgentTaskRecord,
)
from services.agent_runtime.contracts import AgentTask
from services.agent_runtime.learning import MemoryRecord, SkillRecord
from services.agent_runtime.serialization import task_from_dict

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


class AgentTaskRepository:
    """Owner-scoped durable task/checkpoint snapshots."""

    async def save(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task: AgentTask,
        project_id: Optional[str] = None,
    ) -> None:
        payload = task.to_dict()
        stmt = pg_insert(AgentTaskRecord).values(
            id=task.task_id,
            owner_id=owner_id,
            project_id=project_id,
            goal=task.goal,
            state=task.state.value,
            current_step=task.current_step,
            payload=payload,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AgentTaskRecord.id],
            set_={
                "project_id": project_id,
                "goal": task.goal,
                "state": task.state.value,
                "current_step": task.current_step,
                "payload": payload,
                "updated_at": task.updated_at,
            },
        )
        await db.execute(stmt)

        for checkpoint in task.checkpoints:
            cp_stmt = pg_insert(AgentTaskCheckpointRecord).values(
                id=checkpoint.checkpoint_id,
                task_id=task.task_id,
                owner_id=owner_id,
                current_step=checkpoint.current_step,
                observation_count=checkpoint.observation_count,
                reason=checkpoint.reason,
                payload=checkpoint.to_dict(),
                created_at=checkpoint.created_at,
            )
            cp_stmt = cp_stmt.on_conflict_do_nothing(
                index_elements=[AgentTaskCheckpointRecord.id]
            )
            await db.execute(cp_stmt)
        await db.flush()

    async def get_owned(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> Optional[AgentTask]:
        result = await db.execute(
            select(AgentTaskRecord).where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
            )
        )
        row = result.scalar_one_or_none()
        return task_from_dict(dict(row.payload)) if row is not None else None

    async def list_owned(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTask]:
        result = await db.execute(
            select(AgentTaskRecord)
            .where(AgentTaskRecord.owner_id == owner_id)
            .order_by(AgentTaskRecord.updated_at.desc(), AgentTaskRecord.id)
            .limit(max(1, min(int(limit), 100)))
            .offset(max(0, int(offset)))
        )
        return [task_from_dict(dict(row.payload)) for row in result.scalars().all()]

    async def delete_owned(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> bool:
        result = await db.execute(
            delete(AgentTaskRecord).where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
            )
        )
        await db.flush()
        return bool(result.rowcount)


class AgentLearningRepository:
    """Transparent owner-scoped durable memories and versioned skills."""

    async def remember(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        text: str,
        tags: Sequence[str] = (),
        source: str = "operator",
        project_id: Optional[str] = None,
    ) -> MemoryRecord:
        clean = (text or "").strip()
        if not clean:
            raise ValueError("memory text is empty")
        normalized_tags = tuple(
            sorted({tag.strip().lower() for tag in tags if tag and tag.strip()})
        )
        now = datetime.now(timezone.utc)
        row = AgentRuntimeMemory(
            id=f"MEM-{secrets.token_hex(6).upper()}",
            owner_id=owner_id,
            project_id=project_id,
            text=clean,
            tags=list(normalized_tags),
            source=(source or "operator").strip() or "operator",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return self._memory_record(row)

    async def forget(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        memory_id: str,
    ) -> bool:
        result = await db.execute(
            delete(AgentRuntimeMemory).where(
                AgentRuntimeMemory.id == memory_id,
                AgentRuntimeMemory.owner_id == owner_id,
            )
        )
        await db.flush()
        return bool(result.rowcount)

    async def list_memories(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        project_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[MemoryRecord]:
        query = select(AgentRuntimeMemory).where(AgentRuntimeMemory.owner_id == owner_id)
        if project_id:
            query = query.where(
                (AgentRuntimeMemory.project_id == project_id)
                | (AgentRuntimeMemory.project_id.is_(None))
            )
        result = await db.execute(
            query.order_by(AgentRuntimeMemory.updated_at.desc(), AgentRuntimeMemory.id).limit(
                max(1, min(int(limit), 500))
            )
        )
        return [self._memory_record(row) for row in result.scalars().all()]

    async def search_memories(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[MemoryRecord]:
        query_tokens = _tokens(query)
        if not query_tokens or limit <= 0:
            return []
        records = await self.list_memories(
            db,
            owner_id=owner_id,
            project_id=project_id,
            limit=500,
        )
        scored = []
        for record in records:
            haystack = _tokens(record.text + " " + " ".join(record.tags))
            overlap = len(query_tokens & haystack)
            if overlap:
                scored.append((overlap, record.updated_at.timestamp(), record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[: max(1, min(int(limit), 50))]]

    async def upsert_skill(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        name: str,
        description: str,
        instructions: str,
        provenance: str = "operator",
    ) -> SkillRecord:
        clean_name = (name or "").strip().lower().replace(" ", "-")
        clean_description = (description or "").strip()
        clean_instructions = (instructions or "").strip()
        if not clean_name:
            raise ValueError("skill name is empty")
        if not clean_description:
            raise ValueError("skill description is empty")
        if not clean_instructions:
            raise ValueError("skill instructions are empty")

        result = await db.execute(
            select(AgentRuntimeSkill).where(
                AgentRuntimeSkill.owner_id == owner_id,
                AgentRuntimeSkill.name == clean_name,
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = AgentRuntimeSkill(
                id=str(uuid4()),
                owner_id=owner_id,
                name=clean_name,
                description=clean_description,
                instructions=clean_instructions,
                version=1,
                provenance=(provenance or "operator").strip() or "operator",
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.description = clean_description
            row.instructions = clean_instructions
            row.version += 1
            row.provenance = (provenance or row.provenance).strip() or row.provenance
            row.updated_at = now
        await db.flush()
        return self._skill_record(row)

    async def get_skill(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        name: str,
    ) -> Optional[SkillRecord]:
        normalized = (name or "").strip().lower().replace(" ", "-")
        result = await db.execute(
            select(AgentRuntimeSkill).where(
                AgentRuntimeSkill.owner_id == owner_id,
                AgentRuntimeSkill.name == normalized,
            )
        )
        row = result.scalar_one_or_none()
        return self._skill_record(row) if row is not None else None

    async def list_skills(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
    ) -> List[SkillRecord]:
        result = await db.execute(
            select(AgentRuntimeSkill)
            .where(AgentRuntimeSkill.owner_id == owner_id)
            .order_by(AgentRuntimeSkill.name)
        )
        return [self._skill_record(row) for row in result.scalars().all()]

    async def context_for(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        goal: str,
        project_id: Optional[str] = None,
        memory_limit: int = 5,
    ) -> Dict[str, object]:
        memories = await self.search_memories(
            db,
            owner_id=owner_id,
            query=goal,
            project_id=project_id,
            limit=memory_limit,
        )
        skills = await self.list_skills(db, owner_id=owner_id)
        return {
            "memories": [item.to_dict() for item in memories],
            "skills": [item.to_dict() for item in skills],
        }

    @staticmethod
    def _memory_record(row: AgentRuntimeMemory) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row.id,
            text=row.text,
            tags=tuple(str(tag) for tag in (row.tags or [])),
            source=row.source,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _skill_record(row: AgentRuntimeSkill) -> SkillRecord:
        return SkillRecord(
            name=row.name,
            description=row.description,
            instructions=row.instructions,
            version=row.version,
            provenance=row.provenance,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
