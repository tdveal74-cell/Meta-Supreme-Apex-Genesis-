"""Task persistence contracts for the DEVON Agent Runtime."""

from __future__ import annotations

from threading import RLock
from typing import Dict, List, Optional, Protocol

from services.agent_runtime.contracts import AgentTask


class AgentTaskStore(Protocol):
    def put(self, task: AgentTask) -> None: ...

    def get(self, task_id: str) -> Optional[AgentTask]: ...

    def list(self) -> List[AgentTask]: ...


class InMemoryAgentTaskStore:
    """Process-local store used by the v1 runtime and deterministic tests.

    The storage interface is deliberately narrow. A PostgreSQL, Redis, or
    durable object adapter can replace this without changing planning or policy.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, AgentTask] = {}
        self._lock = RLock()

    def put(self, task: AgentTask) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[AgentTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> List[AgentTask]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda item: item.created_at)
