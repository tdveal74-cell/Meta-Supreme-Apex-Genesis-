"""Immutable skill history and server-owned held-out evaluation.

Only explicitly registered local runners can issue evaluation evidence. An LLM
score or request body can never mint a passing evaluation.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import (
    AgentRuntimeSkill,
    AgentSkillEvaluationRecord,
    AgentSkillRevisionRecord,
)
from app.services.skill_evaluation_policy import content_hash, validate_runner_evidence


def normalized_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-")




class RevisionConflict(ValueError):
    pass


# Registration is application code, never exposed through HTTP.
_RUNNERS: dict[tuple[str, str], Callable[[str, str], dict]] = {}


def register_runner(suite_id: str, version: str, runner: Callable[[str, str], dict]) -> None:
    if (suite_id, version) in _RUNNERS:
        raise ValueError("runner version already registered")
    _RUNNERS[(suite_id, version)] = runner




async def lock_skill(db: AsyncSession, owner_id: str, name: str) -> None:
    key = int.from_bytes(hashlib.sha256(f"{owner_id}:{name}".encode()).digest()[:8],
                         "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def revision_dict(row) -> dict:
    return {key: getattr(row, key) for key in ("id", "skill_name", "version", "parent_version",
            "description", "instructions", "content_hash", "provenance", "evidence", "created_at")}


async def append_revision(db, *, row, parent_version, evidence):
    db.add(AgentSkillRevisionRecord(id=str(uuid4()), owner_id=row.owner_id,
        skill_name=row.name, version=row.version, parent_version=parent_version,
        description=row.description, instructions=row.instructions,
        content_hash=content_hash(row.description, row.instructions),
        provenance=row.provenance, evidence=evidence, created_at=datetime.now(timezone.utc)))
    await db.flush()


async def preserve_current(db, row):
    existing = await db.execute(select(AgentSkillRevisionRecord).where(
        AgentSkillRevisionRecord.owner_id == row.owner_id,
        AgentSkillRevisionRecord.skill_name == row.name,
        AgentSkillRevisionRecord.version == row.version))
    if existing.scalar_one_or_none() is None:
        await append_revision(db, row=row, parent_version=None,
                              evidence={"operation": "legacy_snapshot", "verification": "UNVERIFIED"})


async def history(db, *, owner_id, name):
    result = await db.execute(select(AgentSkillRevisionRecord).where(
        AgentSkillRevisionRecord.owner_id == owner_id,
        AgentSkillRevisionRecord.skill_name == normalized_name(name))
        .order_by(AgentSkillRevisionRecord.version))
    return [revision_dict(r) for r in result.scalars()]


async def rollback(db, *, owner_id, name, target_version, expected_version):
    name = normalized_name(name)
    await lock_skill(db, owner_id, name)
    current = (await db.execute(select(AgentRuntimeSkill).where(
        AgentRuntimeSkill.owner_id == owner_id, AgentRuntimeSkill.name == name))).scalar_one_or_none()
    if current is None:
        raise KeyError(name)
    if current.version != expected_version:
        raise RevisionConflict("active version changed")
    await preserve_current(db, current)
    target = (await db.execute(select(AgentSkillRevisionRecord).where(
        AgentSkillRevisionRecord.owner_id == owner_id, AgentSkillRevisionRecord.skill_name == name,
        AgentSkillRevisionRecord.version == target_version))).scalar_one_or_none()
    if target is None:
        raise KeyError(target_version)
    previous = current.version
    current.description, current.instructions = target.description, target.instructions
    current.version += 1
    current.provenance = "operator:rollback"
    current.updated_at = datetime.now(timezone.utc)
    await append_revision(db, row=current, parent_version=previous,
        evidence={"operation": "human_rollback", "restored_version": target_version,
                  "restored_hash": target.content_hash})
    return revision_dict((await db.execute(select(AgentSkillRevisionRecord).where(
        AgentSkillRevisionRecord.owner_id == owner_id, AgentSkillRevisionRecord.skill_name == name,
        AgentSkillRevisionRecord.version == current.version))).scalar_one())


async def evaluate(db, *, owner_id, name, description, instructions, source_task_id, suite_id, suite_version):
    from app.models.agent_runtime import AgentTaskRecord
    task = (await db.execute(select(AgentTaskRecord.id).where(
        AgentTaskRecord.id == source_task_id, AgentTaskRecord.owner_id == owner_id))).scalar_one_or_none()
    if task is None:
        raise KeyError("source task not found")
    runner = _RUNNERS.get((suite_id, suite_version))
    evidence = {"evaluation_status": "FAILED",
                "candidate": {"description": description, "instructions": instructions}}
    try:
        if runner is None:
            raise ValueError("trusted evaluator suite unavailable")
        runner_evidence = runner(description, instructions)
        # Preserve failed checks as well as successful ones, but never let a
        # runner supply the authoritative attempt status or candidate snapshot.
        evidence["runner_evidence"] = runner_evidence
        validate_runner_evidence(runner_evidence, source_task_id=source_task_id)
        evidence["evaluation_status"] = "PASSED"
    except Exception as exc:
        # Runner errors are retained attempts, not permission to promote.
        evidence["error"] = {"type": type(exc).__name__, "message": str(exc)}
    row = AgentSkillEvaluationRecord(id=str(uuid4()), owner_id=owner_id,
        skill_name=normalized_name(name), content_hash=content_hash(description, instructions),
        suite_id=suite_id, suite_version=suite_version, source_task_id=source_task_id,
        evidence=evidence, created_at=datetime.now(timezone.utc))
    db.add(row)
    await db.flush()
    return row.id


async def require_evaluation(db, *, owner_id, evaluation_id, name, description, instructions, source_task_id):
    row = (await db.execute(select(AgentSkillEvaluationRecord).where(
        AgentSkillEvaluationRecord.id == evaluation_id,
        AgentSkillEvaluationRecord.owner_id == owner_id))).scalar_one_or_none()
    if row is None:
        raise ValueError("owned evaluation required")
    if (row.skill_name != normalized_name(name) or row.source_task_id != source_task_id
            or row.content_hash != content_hash(description, instructions)):
        raise ValueError("evaluation does not match exact candidate and task lineage")
    if (row.suite_id, row.suite_version) not in _RUNNERS:
        raise ValueError("evaluation suite retired or unavailable")
    now = datetime.now(timezone.utc)
    if row.created_at > now or row.created_at < now - timedelta(hours=24):
        raise ValueError("evaluation stale")
    if row.evidence.get("evaluation_status") != "PASSED":
        raise ValueError("evaluation attempt did not pass")
    validate_runner_evidence(row.evidence.get("runner_evidence", {}), source_task_id=source_task_id)
    return {"evaluation_id": row.id, "suite_id": row.suite_id, "suite_version": row.suite_version,
            "content_hash": row.content_hash, "operation": "human_proposal_promotion"}


# A concrete narrow suite is available out of the box. Other skill formats
# require independently implemented runners; operator edits remain available.
from app.services.skill_evaluation_policy import (  # noqa: E402
    SUITE_ID,
    SUITE_VERSION,
    run_receipt_policy,
)

register_runner(SUITE_ID, SUITE_VERSION, run_receipt_policy)


async def get_evaluation(db, *, owner_id, name, evaluation_id):
    row = (await db.execute(select(AgentSkillEvaluationRecord).where(
        AgentSkillEvaluationRecord.id == evaluation_id, AgentSkillEvaluationRecord.owner_id == owner_id,
        AgentSkillEvaluationRecord.skill_name == normalized_name(name)))).scalar_one_or_none()
    if row is None:
        raise KeyError(evaluation_id)
    return {key: getattr(row, key) for key in ("id", "skill_name", "content_hash", "suite_id",
        "suite_version", "source_task_id", "evidence", "created_at")}
