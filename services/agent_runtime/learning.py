"""Transparent memory and versioned procedural skills for DEVON Agent Runtime.

This is not hidden model retraining. Every memory and skill is inspectable,
editable through replacement, and deletable. Production durability is supplied
by a future storage adapter; the default store is process local for tests and
single-process development.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from services.agent_runtime.contracts import utcnow

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    text: str
    tags: Tuple[str, ...] = ()
    source: str = "operator"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "tags": list(self.tags),
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    instructions: str
    version: int = 1
    provenance: str = "operator"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "version": self.version,
            "provenance": self.provenance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class LearningStore(Protocol):
    def remember(
        self,
        text: str,
        *,
        tags: Sequence[str] = (),
        source: str = "operator",
    ) -> MemoryRecord: ...

    def forget(self, memory_id: str) -> bool: ...

    def search_memories(self, query: str, *, limit: int = 5) -> List[MemoryRecord]: ...

    def list_memories(self) -> List[MemoryRecord]: ...

    def upsert_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        *,
        provenance: str = "operator",
    ) -> SkillRecord: ...

    def get_skill(self, name: str) -> Optional[SkillRecord]: ...

    def list_skills(self) -> List[SkillRecord]: ...


class InMemoryLearningStore:
    """Small transparent learning store with deterministic lexical recall."""

    def __init__(self) -> None:
        self._memories: Dict[str, MemoryRecord] = {}
        self._skills: Dict[str, SkillRecord] = {}
        self._lock = RLock()

    def remember(
        self,
        text: str,
        *,
        tags: Sequence[str] = (),
        source: str = "operator",
    ) -> MemoryRecord:
        clean = (text or "").strip()
        if not clean:
            raise ValueError("memory text is empty")
        normalized_tags = tuple(
            sorted({tag.strip().lower() for tag in tags if tag.strip()})
        )
        record = MemoryRecord(
            memory_id=f"MEM-{secrets.token_hex(6).upper()}",
            text=clean,
            tags=normalized_tags,
            source=(source or "operator").strip() or "operator",
        )
        with self._lock:
            self._memories[record.memory_id] = record
        return record

    def forget(self, memory_id: str) -> bool:
        with self._lock:
            return self._memories.pop(memory_id, None) is not None

    def search_memories(self, query: str, *, limit: int = 5) -> List[MemoryRecord]:
        query_tokens = _tokens(query)
        if not query_tokens or limit <= 0:
            return []
        with self._lock:
            records = list(self._memories.values())

        scored: List[tuple[int, float, MemoryRecord]] = []
        for record in records:
            haystack = _tokens(record.text + " " + " ".join(record.tags))
            overlap = len(query_tokens & haystack)
            if overlap:
                scored.append((overlap, record.updated_at.timestamp(), record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[:limit]]

    def list_memories(self) -> List[MemoryRecord]:
        with self._lock:
            return sorted(self._memories.values(), key=lambda item: item.created_at)

    def upsert_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        *,
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

        with self._lock:
            existing = self._skills.get(clean_name)
            if existing is None:
                record = SkillRecord(
                    name=clean_name,
                    description=clean_description,
                    instructions=clean_instructions,
                    provenance=(provenance or "operator").strip() or "operator",
                )
            else:
                record = replace(
                    existing,
                    description=clean_description,
                    instructions=clean_instructions,
                    version=existing.version + 1,
                    provenance=(provenance or existing.provenance).strip()
                    or existing.provenance,
                    updated_at=utcnow(),
                )
            self._skills[clean_name] = record
            return record

    def get_skill(self, name: str) -> Optional[SkillRecord]:
        normalized = (name or "").strip().lower().replace(" ", "-")
        with self._lock:
            return self._skills.get(normalized)

    def list_skills(self) -> List[SkillRecord]:
        with self._lock:
            return sorted(self._skills.values(), key=lambda item: item.name)

    def context_for(self, goal: str, *, memory_limit: int = 5) -> Dict[str, object]:
        memories = self.search_memories(goal, limit=memory_limit)
        skills = self.list_skills()
        return {
            "memories": [item.to_dict() for item in memories],
            "skills": [item.to_dict() for item in skills],
        }
