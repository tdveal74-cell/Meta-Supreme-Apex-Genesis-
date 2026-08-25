"""DEVON Agent Runtime durable parent-child subagent links.

Revision ID: 010_agent_subagent_links
Revises: 009_agent_hermes_expansion
Create Date: 2026-08-25
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "010_agent_subagent_links"
down_revision = "009_agent_hermes_expansion"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "010_agent_subagent_links.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON subagent links schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_subagent_links CASCADE")
