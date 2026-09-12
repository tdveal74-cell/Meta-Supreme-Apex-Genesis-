"""The Alembic build and the SQL build become the same database.

Revision ID: 018_schema_convergence
Revises: 017_provider_usage
Create Date: 2026-09-03
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "018_schema_convergence"
down_revision = "017_provider_usage"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "018_schema_convergence.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"schema convergence script not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # knowledge_items.content is not dropped: it holds the text of every item
    # ingested since this ran, and the model has always declared it. Only the
    # widened constraint comes back off, and any row already consumed is put
    # back to the state the narrower constraint accepts.
    op.execute("UPDATE approvals SET state = 'approved' WHERE state = 'consumed'")
    op.execute("ALTER TABLE approvals DROP CONSTRAINT IF EXISTS ck_approvals_state")
    op.execute(
        "ALTER TABLE approvals ADD CONSTRAINT ck_approvals_state CHECK (state IN ("
        "'pending', 'approved', 'refused', 'expired'))"
    )
