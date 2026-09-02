"""Application persistence for DEVON Agent Runtime.

SQLAlchemy stays in the application layer. The framework-free runtime remains
portable and receives/restores canonical task contracts through snapshots.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import (
    AgentRuntimeMemory,
    AgentRuntimeSkill,
    AgentTaskCheckpointRecord,
    AgentTaskRecord,
    AgentTaskRunRecord,
)
from services.agent_runtime.contracts import AgentTask
from services.agent_runtime.learning import MemoryRecord, SkillRecord
from services.agent_runtime.serialization import task_from_dict

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _request_hash(*, max_steps: int) -> str:
    payload = json.dumps(
        {"max_steps": int(max_steps)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _persistable_result(result_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a run response without persisting one-time approval credentials."""
    safe = dict(result_payload)
    if "approval_token" in safe:
        safe["approval_token"] = None
    return safe


class TaskExecutionBusy(RuntimeError):
    """Another live worker owns the task execution lease."""


class TaskExecutionLeaseLost(RuntimeError):
    """A stale worker no longer owns the fencing token for this task."""


class TaskRunConflict(RuntimeError):
    """An idempotency key was reused for a different execution request."""


class TaskRunPreviouslyFailed(RuntimeError):
    """A completed idempotency record already contains a failed execution."""


class AmbiguousEffectRefusal(RuntimeError):
    """An orphan effect intent blocks the task; automatic retry is refused."""


@dataclass(frozen=True)
class AgentTaskExecutionClaim:
    run_id: str
    idempotency_key: str
    lease_token: Optional[str]
    execution_generation: int
    task: Optional[AgentTask] = None
    replay_result: Optional[Dict[str, Any]] = None


class AgentTaskRepository:
    """Owner-scoped durable task/checkpoint snapshots and execution fencing."""

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
        await self._save_checkpoints(db, owner_id=owner_id, task=task)
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

    async def get_owned_for_mutation(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> Optional[AgentTask]:
        """Lock one task row and refuse mutation while a live execution owns it."""
        result = await db.execute(
            select(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        now = datetime.now(timezone.utc)
        if row.lease_token and row.lease_expires_at and row.lease_expires_at > now:
            raise TaskExecutionBusy("agent task is currently leased by another execution")
        if row.lease_token:
            row.lease_token = None
            row.lease_owner = None
            row.lease_expires_at = None
        return task_from_dict(dict(row.payload))

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
            select(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        now = datetime.now(timezone.utc)
        if row.lease_token and row.lease_expires_at and row.lease_expires_at > now:
            raise TaskExecutionBusy("agent task is currently leased by another execution")
        await db.delete(row)
        await db.flush()
        return True

    async def acquire_execution(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        idempotency_key: str,
        max_steps: int,
        lease_owner: str,
        lease_seconds: int,
    ) -> AgentTaskExecutionClaim:
        """Acquire one fenced execution lease or replay a completed request."""
        key = (idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency key is empty")
        if len(key) > 200:
            raise ValueError("idempotency key exceeds 200 characters")
        max_steps = int(max_steps)
        if max_steps < 1 or max_steps > 100:
            raise ValueError("max_steps must be between 1 and 100")
        request_hash = _request_hash(max_steps=max_steps)

        existing_result = await db.execute(
            select(AgentTaskRunRecord).where(
                AgentTaskRunRecord.owner_id == owner_id,
                AgentTaskRunRecord.task_id == task_id,
                AgentTaskRunRecord.idempotency_key == key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise TaskRunConflict(
                    "idempotency key was already used with different run parameters"
                )
            if existing.state == "completed":
                if existing.result is None:
                    raise TaskRunConflict("completed run is missing its durable result")
                return AgentTaskExecutionClaim(
                    run_id=existing.id,
                    idempotency_key=key,
                    lease_token=None,
                    execution_generation=0,
                    replay_result=dict(existing.result),
                )
            if existing.state == "failed":
                raise TaskRunPreviouslyFailed(existing.error or "agent task run failed")

        now = datetime.now(timezone.utc)
        lease_expires_at = now + timedelta(seconds=max(5, int(lease_seconds)))
        lease_token = secrets.token_hex(24)
        claim_stmt = (
            update(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
                or_(
                    AgentTaskRecord.lease_token.is_(None),
                    AgentTaskRecord.lease_expires_at.is_(None),
                    AgentTaskRecord.lease_expires_at <= now,
                ),
            )
            .values(
                lease_token=lease_token,
                lease_owner=lease_owner,
                lease_expires_at=lease_expires_at,
                execution_generation=AgentTaskRecord.execution_generation + 1,
            )
            .returning(AgentTaskRecord.payload, AgentTaskRecord.execution_generation)
        )
        claimed_result = await db.execute(claim_stmt)
        claimed = claimed_result.mappings().one_or_none()
        if claimed is None:
            exists_result = await db.execute(
                select(AgentTaskRecord.id).where(
                    AgentTaskRecord.id == task_id,
                    AgentTaskRecord.owner_id == owner_id,
                )
            )
            if exists_result.scalar_one_or_none() is None:
                raise KeyError(f"unknown agent task: {task_id}")
            raise TaskExecutionBusy("agent task is already running on another worker")

        stale_filters = [
            AgentTaskRunRecord.owner_id == owner_id,
            AgentTaskRunRecord.task_id == task_id,
            AgentTaskRunRecord.state == "running",
        ]
        if existing is not None:
            stale_filters.append(AgentTaskRunRecord.id != existing.id)
        await db.execute(
            update(AgentTaskRunRecord)
            .where(*stale_filters)
            .values(
                state="failed",
                result=None,
                error="superseded after execution lease expired",
                lease_token=None,
                lease_owner=None,
                updated_at=now,
                completed_at=now,
            )
        )

        if existing is None:
            run_id = f"RUN-{secrets.token_hex(8).upper()}"
            db.add(
                AgentTaskRunRecord(
                    id=run_id,
                    task_id=task_id,
                    owner_id=owner_id,
                    idempotency_key=key,
                    request_hash=request_hash,
                    max_steps=max_steps,
                    state="running",
                    lease_token=lease_token,
                    lease_owner=lease_owner,
                    attempt=1,
                    result=None,
                    error=None,
                    created_at=now,
                    updated_at=now,
                    completed_at=None,
                )
            )
        else:
            run_id = existing.id
            existing.lease_token = lease_token
            existing.lease_owner = lease_owner
            existing.attempt += 1
            existing.updated_at = now
            existing.error = None

        await db.flush()
        return AgentTaskExecutionClaim(
            run_id=run_id,
            idempotency_key=key,
            lease_token=lease_token,
            execution_generation=int(claimed["execution_generation"]),
            task=task_from_dict(dict(claimed["payload"])),
        )

    async def renew_execution(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        run_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> bool:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(5, int(lease_seconds)))
        task_result = await db.execute(
            update(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
            )
            .values(lease_expires_at=expires)
        )
        if task_result.rowcount != 1:
            return False
        run_result = await db.execute(
            update(AgentTaskRunRecord)
            .where(
                AgentTaskRunRecord.id == run_id,
                AgentTaskRunRecord.owner_id == owner_id,
                AgentTaskRunRecord.lease_token == lease_token,
                AgentTaskRunRecord.state == "running",
            )
            .values(updated_at=now)
        )
        return run_result.rowcount == 1

    async def park_if_leased(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task: AgentTask,
        lease_token: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Write the task's state and payload only while this worker owns the lease.

        The lease itself is left in place; the caller's failure path releases
        it. Returns False, and writes nothing, when the lease is no longer ours.
        """
        result = await db.execute(
            update(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task.task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
            )
            .values(
                project_id=project_id,
                goal=task.goal,
                state=task.state.value,
                current_step=task.current_step,
                payload=task.to_dict(),
                updated_at=task.updated_at,
            )
        )
        if result.rowcount != 1:
            return False
        await self._save_checkpoints(db, owner_id=owner_id, task=task)
        await db.flush()
        return True

    async def complete_execution(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        run_id: str,
        lease_token: str,
        task: AgentTask,
        result_payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> None:
        """Persist a result only if this worker still owns the fencing token."""
        now = datetime.now(timezone.utc)
        task_update = await db.execute(
            update(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task.task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
            )
            .values(
                project_id=project_id,
                goal=task.goal,
                state=task.state.value,
                current_step=task.current_step,
                payload=task.to_dict(),
                updated_at=task.updated_at,
                lease_token=None,
                lease_owner=None,
                lease_expires_at=None,
            )
        )
        if task_update.rowcount != 1:
            raise TaskExecutionLeaseLost(
                "agent task execution lease was lost; stale result was not committed"
            )

        run_update = await db.execute(
            update(AgentTaskRunRecord)
            .where(
                AgentTaskRunRecord.id == run_id,
                AgentTaskRunRecord.owner_id == owner_id,
                AgentTaskRunRecord.lease_token == lease_token,
                AgentTaskRunRecord.state == "running",
            )
            .values(
                state="completed",
                result=_persistable_result(result_payload),
                error=None,
                lease_token=None,
                lease_owner=None,
                updated_at=now,
                completed_at=now,
            )
        )
        if run_update.rowcount != 1:
            raise TaskExecutionLeaseLost(
                "agent task run fencing token was lost; result was not committed"
            )
        await self._save_checkpoints(db, owner_id=owner_id, task=task)
        await db.flush()

    async def fail_execution(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        run_id: str,
        lease_token: str,
        error: str,
    ) -> bool:
        """Record a failed request only while this worker still owns the lease."""
        now = datetime.now(timezone.utc)
        run_result = await db.execute(
            update(AgentTaskRunRecord)
            .where(
                AgentTaskRunRecord.id == run_id,
                AgentTaskRunRecord.owner_id == owner_id,
                AgentTaskRunRecord.lease_token == lease_token,
                AgentTaskRunRecord.state == "running",
            )
            .values(
                state="failed",
                result=None,
                error=(error or "agent task run failed")[:8000],
                lease_token=None,
                lease_owner=None,
                updated_at=now,
                completed_at=now,
            )
        )
        task_result = await db.execute(
            update(AgentTaskRecord)
            .where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
            )
            .values(lease_token=None, lease_owner=None, lease_expires_at=None)
        )
        await db.flush()
        return run_result.rowcount == 1 and task_result.rowcount == 1

    async def _save_checkpoints(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task: AgentTask,
    ) -> None:
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
