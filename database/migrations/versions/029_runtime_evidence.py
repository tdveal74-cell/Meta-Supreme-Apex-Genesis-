"""Durable runtime evidence and immutable skill revisions."""
import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = '029_runtime_evidence'
down_revision = '028_support_articles'
branch_labels = None
depends_on = None


def upgrade():
    path = pathlib.Path(__file__).resolve().parents[3] / 'database/schemas/029_runtime_evidence.sql'
    execute_sql_script(path.read_text())


def downgrade():
    for table in ('skill_evaluation_runs', 'agent_skill_revisions', 'agent_verifications', 'agent_tool_results'):
        op.execute(f'DROP TABLE IF EXISTS {table}')
    op.execute('DROP FUNCTION IF EXISTS refuse_runtime_evidence_update()')
    op.execute('DROP FUNCTION IF EXISTS refuse_runtime_evidence_delete()')
