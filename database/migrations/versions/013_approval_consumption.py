"""An approved DEVON effect is spent when it runs, so it cannot run twice.

Revision ID: 013_approval_consumption
Revises: 012_live_state_ledger
Create Date: 2026-08-27
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "013_approval_consumption"
down_revision = "012_live_state_ledger"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "013_approval_consumption.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"DEVON approval consumption schema not found at {_SCHEMA}")
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    """Narrow the constraints back, after retiring any row the old shape forbids.

    A plain constraint swap would fail against a table that has consumed rows in
    it, which is exactly the state a downgrade runs in. Those rows are approvals
    that were already spent, so they are moved to 'refused' rather than back to
    'approved': re-widening a spent approval on the way down would hand back the
    replay this migration exists to close.
    """
    op.execute(
        "UPDATE devon_approvals SET state = 'refused', updated_at = NOW() "
        "WHERE state = 'consumed'"
    )
    op.execute("ALTER TABLE devon_approvals DROP CONSTRAINT IF EXISTS ck_devon_approvals_state")
    op.execute(
        "ALTER TABLE devon_approvals ADD CONSTRAINT ck_devon_approvals_state "
        "CHECK (state IN ('pending', 'approved', 'refused', 'expired'))"
    )
    op.execute(
        "ALTER TABLE devon_approvals DROP CONSTRAINT IF EXISTS ck_devon_approvals_decision_shape"
    )
    op.execute(
        "ALTER TABLE devon_approvals ADD CONSTRAINT ck_devon_approvals_decision_shape "
        "CHECK ("
        "(state = 'pending' AND decided_at IS NULL AND decided_by IS NULL) "
        "OR (state IN ('approved', 'refused') AND decided_at IS NOT NULL) "
        "OR (state = 'expired' AND decided_at IS NOT NULL)"
        ")"
    )
