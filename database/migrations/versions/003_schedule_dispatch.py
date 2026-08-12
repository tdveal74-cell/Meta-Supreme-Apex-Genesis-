"""Schedule dispatch columns.

Revision ID: 003_schedule_dispatch
Revises: 002_workflow_runs
Create Date: 2026-08-09

`next_run_at` is the scheduler's whole state. Keeping it on the row rather
than recomputing from `last_fired_at` at dispatch time means the query that
finds due workflows is a single indexed range scan, and a workflow whose
cadence changed picks the new schedule up on save rather than on next fire.

The partial index is what makes the dispatcher cheap: it only covers active
workflows that have a scheduled slot, which is a small fraction of the table,
and the dispatcher's query matches it exactly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_schedule_dispatch"
down_revision = "002_workflow_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflows", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "workflows",
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX idx_workflows_due ON workflows (next_run_at) "
        "WHERE next_run_at IS NOT NULL AND status = 'active'"
    )


def downgrade() -> None:
    op.drop_index("idx_workflows_due", table_name="workflows")
    op.drop_column("workflows", "last_fired_at")
    op.drop_column("workflows", "next_run_at")
