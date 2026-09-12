"""The capture payload has a body: artifacts.body and artifacts.kind.

Revision ID: 014_artifact_body
Revises: 013_approval_consumption
Create Date: 2026-09-02

cf0d7ef added these two columns to the 012 SQL twin and to a conftest-only
014 SQL file, so a database that ran 012 before that commit never received
them from `alembic upgrade head`. This revision executes the same idempotent
SQL so an already-migrated database catches up and a fresh one is unchanged.
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "014_artifact_body"
down_revision = "013_approval_consumption"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "014_artifact_body.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"artifact body schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS kind")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS body")
