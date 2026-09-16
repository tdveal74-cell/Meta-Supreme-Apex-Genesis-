"""Let a knowledge item be an episode transcript.

Revision ID: 020_episode_transcripts
Revises: 019_event_hash_chain
Create Date: 2026-09-16
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "020_episode_transcripts"
down_revision = "019_event_hash_chain"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "020_episode_transcripts.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"episode transcript schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Back to the six document formats 001 declared. Any episode transcript
    # row would violate the narrowed CHECK, so they go first: a downgrade that
    # leaves the table unable to satisfy its own constraint is not a
    # downgrade, it is a broken database that reports success.
    op.execute("DELETE FROM knowledge_items WHERE source_type = 'episode_transcript'")
    op.execute(
        "DROP INDEX IF EXISTS knowledge_items_episode_fingerprint_key"
    )
    op.execute(
        "ALTER TABLE knowledge_items "
        "DROP CONSTRAINT IF EXISTS knowledge_items_source_type_check"
    )
    op.execute(
        "ALTER TABLE knowledge_items "
        "ADD CONSTRAINT knowledge_items_source_type_check "
        "CHECK (source_type IN ('pdf', 'docx', 'txt', 'markdown', 'url', 'manual'))"
    )
