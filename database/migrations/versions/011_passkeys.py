"""DEVON WebAuthn passkeys.

Revision ID: 011_passkeys
Revises: 010_agent_subagent_links
Create Date: 2026-08-26
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "011_passkeys"
down_revision = "010_agent_subagent_links"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "011_passkeys.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON passkey schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS passkey_challenges CASCADE")
    op.execute("DROP TABLE IF EXISTS passkey_credentials CASCADE")
