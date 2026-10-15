"""The Support knowledge base and the article every reply cites.

Revision ID: 028_support_articles
Revises: 027_lead_disclosure_optional
Create Date: 2026-10-15
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "028_support_articles"
down_revision = "027_lead_disclosure_optional"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "028_support_articles.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"support articles schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("ALTER TABLE company_comment_drafts DROP CONSTRAINT IF EXISTS company_comment_drafts_article_fk")
    op.execute("ALTER TABLE company_comment_drafts DROP COLUMN IF EXISTS article_id")
    op.execute("DROP TABLE IF EXISTS company_support_articles")
