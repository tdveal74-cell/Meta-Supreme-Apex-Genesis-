"""Workflow runs, workflow metadata, and the indexes both need.

Revision ID: 002_workflow_runs
Revises: 001_baseline
Create Date: 2026-08-04

Three things, all required before Workflows can run:

1. `workflow_runs` — the audit trail. One row per execution, carrying the
   ordered step results, the approvals a human granted (with actor and
   timestamp), the step the run is paused in front of, and its token cost.
2. `workflows.metadata` — the model maps a `metadata` JSONB column that the
   baseline schema never created. Inserting a Workflow today raises
   `UndefinedColumn`.
3. Indexes. `workflows` shipped with none: every list view filters by owner,
   and the run history sorts by `started_at DESC` per workflow.

Two of the indexes back guards rather than queries. The partial index on
awaiting-approval runs supports the check that refuses to start a second run
while one is still sitting in front of a gate. The unique index on
`metadata->>'idempotency_key'` is the idempotency guarantee itself: a repeated
key cannot create a second run even if two requests race past the application
check, because the database refuses the insert. Both lookups happen on every
manual run.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_workflow_runs"
down_revision = "001_baseline"
branch_labels = None
depends_on = None

_RUN_STATUSES = (
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "halted",
    "failed",
)


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("idx_workflows_owner", "workflows", ["owner_id"])
    op.create_index("idx_workflows_project", "workflows", ["project_id"])

    op.create_table(
        "workflow_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column(
            "trigger", sa.Text(), nullable=False, server_default=sa.text("'manual'")
        ),
        sa.Column("trigger_input", sa.Text(), nullable=True),
        sa.Column(
            "step_results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "approvals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("pending_step_id", sa.Text(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _RUN_STATUSES) + ")",
            name="workflow_runs_status_check",
        ),
    )

    op.create_index(
        "idx_workflow_runs_workflow",
        "workflow_runs",
        ["workflow_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "idx_workflow_runs_user",
        "workflow_runs",
        ["user_id", sa.text("started_at DESC")],
    )
    op.execute(
        "CREATE INDEX idx_workflow_runs_awaiting ON workflow_runs (workflow_id) "
        "WHERE status = 'awaiting_approval'"
    )
    # Unique, not merely fast: this is what makes a retried POST safe under a
    # race. Partial, so the vast majority of runs (no key supplied) are exempt.
    op.execute(
        "CREATE UNIQUE INDEX idx_workflow_runs_idempotency ON workflow_runs "
        "(workflow_id, (metadata->>'idempotency_key')) "
        "WHERE metadata ? 'idempotency_key'"
    )

    op.execute(
        "CREATE TRIGGER workflow_runs_updated_at "
        "BEFORE UPDATE ON workflow_runs "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS workflow_runs_updated_at ON workflow_runs")
    op.drop_index("idx_workflow_runs_idempotency", table_name="workflow_runs")
    op.drop_index("idx_workflow_runs_awaiting", table_name="workflow_runs")
    op.drop_index("idx_workflow_runs_user", table_name="workflow_runs")
    op.drop_index("idx_workflow_runs_workflow", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("idx_workflows_project", table_name="workflows")
    op.drop_index("idx_workflows_owner", table_name="workflows")
    op.drop_column("workflows", "metadata")
