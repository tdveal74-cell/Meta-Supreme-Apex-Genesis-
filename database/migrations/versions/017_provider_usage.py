"""A durable per-tenant ledger of provider spend: the provider_usage table.

Revision ID: 017_provider_usage
Revises: 015_devon_approval_owner
Create Date: 2026-09-02
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "017_provider_usage"
# Fix PR 14 (016_approval_row_states) was specified to precede this revision,
# but no commit of it exists in the repository, so this one chains after the
# last revision that does. When 016 lands, point this line at it.
down_revision = "015_devon_approval_owner"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "017_provider_usage.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"provider usage schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS provider_usage")
