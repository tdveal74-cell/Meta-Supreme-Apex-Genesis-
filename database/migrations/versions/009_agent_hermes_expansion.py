"""DEVON Agent Runtime Hermes expansion schedules and skill proposals.

Revision ID: 009_agent_hermes_expansion
Revises: 008_agent_effect_receipts
Create Date: 2026-08-24
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "009_agent_hermes_expansion"
down_revision = "008_agent_effect_receipts"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "009_agent_hermes_expansion.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON Hermes expansion schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_skill_proposals CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_schedules CASCADE")
