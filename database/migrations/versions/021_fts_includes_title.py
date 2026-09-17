"""Fold the knowledge item's title into the full text column.

Revision ID: 021_fts_includes_title
Revises: 020_episode_transcripts
Create Date: 2026-09-17
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "021_fts_includes_title"
down_revision = "020_episode_transcripts"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "021_fts_includes_title.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"fts backfill schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Back to content only, which is what every row carried before 021. This
    # rebuilds rather than restoring, because the pre-021 vector was not kept
    # anywhere; rebuilding from `content` reproduces it exactly, since that is
    # all the old expression ever read.
    op.execute(
        "UPDATE embeddings SET fts = to_tsvector('english', coalesce(content, ''))"
    )
