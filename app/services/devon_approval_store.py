"""PostgreSQL-backed shared storage for DEVON human approvals.

The framework-free gate lives in ``services.devon.approval``. This application
adapter gives that gate a durable, multi-worker store without importing database
code into DEVON core.

No plaintext approval token is accepted or persisted here. The queue supplies
only the SHA-256 token hash contained in ``ApprovalRequest``.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from services.devon.approval import (
    ApprovalQueue,
    ApprovalRequest,
    ApprovalState,
    InMemoryApprovalStore,
)


class ApprovalStoreUnavailable(RuntimeError):
    """The configured shared approval backend cannot be reached safely."""


def _normalize_dsn(value: str) -> str:
    dsn = (value or "").strip()
    if dsn.startswith("postgresql+asyncpg://"):
        return "postgresql://" + dsn.removeprefix("postgresql+asyncpg://")
    if dsn.startswith("postgres://"):
        return "postgresql://" + dsn.removeprefix("postgres://")
    return dsn


def _connect_timeout() -> float:
    raw = os.getenv("DEVON_APPROVAL_CONNECT_TIMEOUT_SECONDS", "5").strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError("DEVON_APPROVAL_CONNECT_TIMEOUT_SECONDS must be numeric") from exc


_COLUMNS = """
request_id,
title,
what_happens,
requested_by,
area,
reversible,
blast_radius,
created_at,
expires_at,
state,
decided_at,
decided_by,
token_hash
"""


class PostgresApprovalStore:
    """Durable shared store with compare-and-set decision transitions."""

    backend_name = "postgres"

    def __init__(self, dsn: str, *, connect_timeout_seconds: float = 5.0) -> None:
        self.dsn = _normalize_dsn(dsn)
        if not self.dsn:
            raise ValueError("DEVON approval database URL is empty")
        self.connect_timeout_seconds = max(1, min(int(connect_timeout_seconds), 30))

    def put(self, request: ApprovalRequest) -> None:
        sql = """
            INSERT INTO devon_approvals (
                request_id, title, what_happens, requested_by, area,
                reversible, blast_radius, created_at, expires_at, state,
                decided_at, decided_by, token_hash, updated_at
            ) VALUES (
                %(request_id)s, %(title)s, %(what_happens)s, %(requested_by)s,
                %(area)s, %(reversible)s, %(blast_radius)s, %(created_at)s,
                %(expires_at)s, %(state)s, %(decided_at)s, %(decided_by)s,
                %(token_hash)s, NOW()
            )
        """
        try:
            with self._connect() as conn:
                conn.execute(sql, self._params(request))
        except psycopg.Error:
            raise ApprovalStoreUnavailable(
                "DEVON approval database is unavailable; request was not queued"
            ) from None

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        sql = f"SELECT {_COLUMNS} FROM devon_approvals WHERE request_id = %s"
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (request_id,)).fetchone()
        except psycopg.Error:
            raise ApprovalStoreUnavailable(
                "DEVON approval database is unavailable; approval state is unknown"
            ) from None
        return self._record(row) if row else None

    def transition_pending(self, request: ApprovalRequest) -> bool:
        """Atomically let exactly one worker move a request out of pending."""
        if request.state is ApprovalState.PENDING:
            raise ValueError("transition_pending requires a terminal approval state")

        sql = """
            UPDATE devon_approvals
               SET state = %(state)s,
                   decided_at = %(decided_at)s,
                   decided_by = %(decided_by)s,
                   updated_at = NOW()
             WHERE request_id = %(request_id)s
               AND state = 'pending'
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(sql, self._params(request))
                return cursor.rowcount == 1
        except psycopg.Error:
            raise ApprovalStoreUnavailable(
                "DEVON approval database is unavailable; ruling was not recorded"
            ) from None

    def pending(self) -> list[ApprovalRequest]:
        """Return live pending requests and durably expire overdue rows."""
        expire_sql = """
            UPDATE devon_approvals
               SET state = 'expired',
                   decided_at = NOW(),
                   updated_at = NOW()
             WHERE state = 'pending'
               AND expires_at <= NOW()
        """
        select_sql = f"""
            SELECT {_COLUMNS}
              FROM devon_approvals
             WHERE state = 'pending'
               AND expires_at > NOW()
             ORDER BY created_at ASC, request_id ASC
        """
        try:
            with self._connect() as conn:
                conn.execute(expire_sql)
                rows = conn.execute(select_sql).fetchall()
        except psycopg.Error:
            raise ApprovalStoreUnavailable(
                "DEVON approval database is unavailable; pending state is unknown"
            ) from None
        return [self._record(row) for row in rows]

    def _connect(self):
        return psycopg.connect(
            self.dsn,
            connect_timeout=self.connect_timeout_seconds,
            row_factory=dict_row,
        )

    @staticmethod
    def _params(request: ApprovalRequest) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "title": request.title,
            "what_happens": request.what_happens,
            "requested_by": request.requested_by,
            "area": request.area,
            "reversible": request.reversible,
            "blast_radius": request.blast_radius,
            "created_at": request.created_at,
            "expires_at": request.expires_at,
            "state": request.state.value,
            "decided_at": request.decided_at,
            "decided_by": request.decided_by,
            "token_hash": request._token_hash,
        }

    @staticmethod
    def _record(row: dict[str, Any]) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=str(row["request_id"]),
            title=str(row["title"]),
            what_happens=str(row["what_happens"]),
            requested_by=str(row["requested_by"]),
            area=str(row["area"]) if row["area"] is not None else None,
            reversible=bool(row["reversible"]),
            blast_radius=str(row["blast_radius"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            state=ApprovalState(str(row["state"])),
            decided_at=row["decided_at"],
            decided_by=str(row["decided_by"]) if row["decided_by"] is not None else None,
            _token_hash=str(row["token_hash"]),
        )


def build_approval_queue(
    *,
    mode: Optional[str] = None,
    dsn: Optional[str] = None,
) -> ApprovalQueue:
    """Construct the configured queue without silently weakening its backend."""
    selected = (mode or os.getenv("DEVON_APPROVAL_STORE", "postgres")).strip().lower()
    if selected == "memory":
        return ApprovalQueue(InMemoryApprovalStore())
    if selected != "postgres":
        raise ValueError("DEVON_APPROVAL_STORE must be 'postgres' or 'memory'")

    database_url = dsn or os.getenv("DEVON_APPROVAL_DATABASE_URL") or settings.DATABASE_URL
    return ApprovalQueue(
        PostgresApprovalStore(
            database_url,
            connect_timeout_seconds=_connect_timeout(),
        )
    )
