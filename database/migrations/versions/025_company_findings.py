"""The Research findings queue: the company_findings table.

Revision ID: 025_company_findings
Revises: 024_company_comment_drafts
Create Date: 2026-10-12
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "025_company_findings"
down_revision = "024_company_comment_drafts"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "025_company_findings.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"company_findings schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_findings")
