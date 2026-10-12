"""The Support approval queue: the company_comment_drafts table.

Revision ID: 024_company_comment_drafts
Revises: 023_company_lead_drafts
Create Date: 2026-10-12
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "024_company_comment_drafts"
down_revision = "023_company_lead_drafts"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "024_company_comment_drafts.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"company comment drafts schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_comment_drafts")
