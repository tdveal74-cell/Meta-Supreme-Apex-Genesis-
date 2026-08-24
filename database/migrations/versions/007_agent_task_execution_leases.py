"""DEVON Agent Runtime task execution leases and idempotent run ledger.

Revision ID: 007_agent_task_execution_leases
Revises: 006_devon_approval_store
Create Date: 2026-08-24

Uses the same re-runnable DDL file as the PostgreSQL test harness so production
and CI cannot silently disagree about the multi-worker execution schema.
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "007_agent_task_execution_leases"
down_revision = "006_devon_approval_store"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "007_agent_task_execution_leases.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON task lease schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_task_runs CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_agent_tasks_lease_expiry")
    op.execute("ALTER TABLE agent_tasks DROP COLUMN IF EXISTS execution_generation")
    op.execute("ALTER TABLE agent_tasks DROP COLUMN IF EXISTS lease_expires_at")
    op.execute("ALTER TABLE agent_tasks DROP COLUMN IF EXISTS lease_owner")
    op.execute("ALTER TABLE agent_tasks DROP COLUMN IF EXISTS lease_token")
