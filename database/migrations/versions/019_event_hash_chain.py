"""The Event Bus becomes a hash chain and the Universal Receipt is signed.

Revision ID: 019_event_hash_chain
Revises: 018_schema_convergence
Create Date: 2026-09-08
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "019_event_hash_chain"
down_revision = "018_schema_convergence"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "019_event_hash_chain.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"event hash chain schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Triggers first, then the function they call, then the columns. The
    # columns are dropped because a row written under 019 carries a hash that
    # an 018 writer would leave stale on the next append, which is worse than
    # no hash at all.
    op.execute("DROP TRIGGER IF EXISTS trg_events_append_only ON events")
    op.execute("DROP TRIGGER IF EXISTS trg_events_no_delete ON events")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_universal_receipts_append_only ON universal_receipts"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_universal_receipts_no_delete ON universal_receipts"
    )
    op.execute("DROP FUNCTION IF EXISTS ledger_refuse_update()")
    op.execute("DROP FUNCTION IF EXISTS ledger_refuse_delete()")
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS prev_hash")
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS hash")
    op.execute("ALTER TABLE universal_receipts DROP COLUMN IF EXISTS head_hash")
    op.execute("ALTER TABLE universal_receipts DROP COLUMN IF EXISTS chain_length")
    op.execute("ALTER TABLE universal_receipts DROP COLUMN IF EXISTS signature")
    op.execute("ALTER TABLE universal_receipts DROP COLUMN IF EXISTS signature_key_id")
