"""The Marketing approval queue: the company_post_drafts table.

Revision ID: 022_company_post_drafts
Revises: 021_fts_includes_title
Create Date: 2026-10-12
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "022_company_post_drafts"
down_revision = "021_fts_includes_title"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "022_company_post_drafts.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"company post drafts schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_post_drafts")
