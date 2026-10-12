"""The Product proposals queue: the company_proposals table.

Revision ID: 026_company_proposals
Revises: 025_company_findings
Create Date: 2026-10-12
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "026_company_proposals"
down_revision = "025_company_findings"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "026_company_proposals.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"company_proposals schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_proposals")
