"""An approval card belongs to an account: devon_approvals.owner_id.

Revision ID: 015_devon_approval_owner
Revises: 014_artifact_body
Create Date: 2026-09-02
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "015_devon_approval_owner"
down_revision = "014_artifact_body"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "015_devon_approval_owner.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON approval owner schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_devon_approvals_owner_state")
    op.execute("ALTER TABLE devon_approvals DROP COLUMN IF EXISTS owner_id")
