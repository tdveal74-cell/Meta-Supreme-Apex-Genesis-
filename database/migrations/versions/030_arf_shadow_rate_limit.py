"""Shared per-account ARF diagnostic request budget."""

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "030_arf_shadow_rate_limit"
down_revision = "029_runtime_evidence"
branch_labels = None
depends_on = None


def upgrade():
    path = pathlib.Path(__file__).resolve().parents[3] / "database/schemas/030_arf_shadow_rate_limit.sql"
    execute_sql_script(path.read_text())


def downgrade():
    # This discards security counters only. Leave the diagnostic flag off
    # through a downgrade; absent accounting makes the new handler refuse.
    op.execute("DROP TABLE IF EXISTS arf_shadow_rate_limits")
