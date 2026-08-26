"""DEVON Live State Ledger, Event Bus, and Universal Receipt.

Revision ID: 012_live_state_ledger
Revises: 011_passkeys
Create Date: 2026-08-26
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "012_live_state_ledger"
down_revision = "011_passkeys"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "012_live_state_ledger.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON live state ledger schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Children before parents: every table below references intents or users.
    op.execute("DROP TABLE IF EXISTS universal_receipts CASCADE")
    op.execute("DROP TABLE IF EXISTS learning_candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS verifications CASCADE")
    op.execute("DROP TABLE IF EXISTS errors CASCADE")
    op.execute("DROP TABLE IF EXISTS systems CASCADE")
    op.execute("DROP TABLE IF EXISTS executors CASCADE")
    op.execute("DROP TABLE IF EXISTS artifacts CASCADE")
    op.execute("DROP TABLE IF EXISTS approvals CASCADE")
    op.execute("DROP TABLE IF EXISTS actions CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.execute("DROP TABLE IF EXISTS intents CASCADE")
