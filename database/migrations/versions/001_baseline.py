"""Baseline — adopt the shipped raw-SQL schema as Alembic revision 001.

Revision ID: 001_baseline
Revises:
Create Date: 2026-08-04

The schema through Phase 4 was maintained as `database/schemas/001_initial_schema.sql`
and applied by hand. Rather than transcribing ~350 lines of DDL into Python —
where it would immediately begin drifting from the file the tests still apply —
this baseline executes that file through the migration SQL-script helper.

asyncpg prepares each Alembic statement and rejects a whole multi-command file,
so the helper splits only on top-level semicolons while preserving PostgreSQL
quoted strings, comments, and dollar-quoted PL/pgSQL bodies.

    New database:       alembic upgrade head
    Existing database:  alembic stamp 001_baseline && alembic upgrade head

From 002 onward, migrations are hand-written unless they intentionally adopt an
already-canonical re-runnable schema file.
"""

from __future__ import annotations

import pathlib

from alembic import op

from database.migrations.sql_script import execute_sql_script

revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "001_initial_schema.sql"

_BASELINE_TABLES = (
    "audit_logs",
    "feedback",
    "workflows",
    "decisions",
    "memories",
    "embeddings",
    "knowledge_items",
    "agent_runs",
    "agents",
    "messages",
    "conversations",
    "projects",
    "organization_members",
    "organizations",
    "users",
)


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(
            f"Baseline schema not found at {_SCHEMA}. If this database already "
            f"has the Phase 4 schema, run `alembic stamp 001_baseline` instead."
        )
    execute_sql_script(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    for table in _BASELINE_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")
