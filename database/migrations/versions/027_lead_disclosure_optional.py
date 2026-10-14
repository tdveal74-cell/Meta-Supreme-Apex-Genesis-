"""A Sales draft may carry no AI disclosure.

Revision ID: 027_lead_disclosure_optional
Revises: 026_company_proposals
Create Date: 2026-10-14
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "027_lead_disclosure_optional"
down_revision = "026_company_proposals"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "027_lead_disclosure_optional.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"lead disclosure schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Restoring NOT NULL would fail on any row saved without a disclosure, so give
    # those rows a plain marker first. The marker is not a disclosure Tee wrote.
    op.execute("UPDATE company_lead_drafts SET ai_disclosure = 'No disclosure recorded' WHERE ai_disclosure IS NULL")
    op.execute("ALTER TABLE company_lead_drafts DROP CONSTRAINT IF EXISTS company_lead_drafts_disclosure_chk")
    op.execute("ALTER TABLE company_lead_drafts ALTER COLUMN ai_disclosure SET NOT NULL")
    op.execute(
        "ALTER TABLE company_lead_drafts ADD CONSTRAINT company_lead_drafts_disclosure_chk "
        "CHECK (length(btrim(ai_disclosure)) > 0)"
    )
