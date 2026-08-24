"""DEVON durable shared approval authority.

Revision ID: 006_devon_approval_store
Revises: 005_agent_runtime_persistence
Create Date: 2026-08-24

Uses the same re-runnable DDL file as the PostgreSQL test harness so production
and CI cannot silently disagree about the human-approval authority schema.
"""

from __future__ import annotations

import pathlib

from alembic import op

revision = "006_devon_approval_store"
down_revision = "005_agent_runtime_persistence"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "006_devon_approval_store.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON approval schema not found at {_SCHEMA}")
    op.execute(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS devon_approvals CASCADE")
