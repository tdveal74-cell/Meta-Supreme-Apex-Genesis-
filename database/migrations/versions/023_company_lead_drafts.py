"""The Sales approval queue: the company_lead_drafts table.

Revision ID: 023_company_lead_drafts
Revises: 022_company_post_drafts
Create Date: 2026-10-12
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "023_company_lead_drafts"
down_revision = "022_company_post_drafts"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "023_company_lead_drafts.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"company lead drafts schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_lead_drafts")
