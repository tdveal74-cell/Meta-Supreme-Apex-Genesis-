"""DEVON Agent Runtime durable effect intents and receipts.

Revision ID: 008_agent_effect_receipts
Revises: 007_agent_task_execution_leases
Create Date: 2026-08-24

Uses the same re-runnable DDL file as the PostgreSQL test harness so production
and CI cannot silently disagree about the effect-receipt schema.
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "008_agent_effect_receipts"
down_revision = "007_agent_task_execution_leases"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "008_agent_effect_receipts.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON effect receipts schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_effect_receipts CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_effect_intents CASCADE")
