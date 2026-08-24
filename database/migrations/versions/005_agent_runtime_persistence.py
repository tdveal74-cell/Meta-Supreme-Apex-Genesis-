"""DEVON Agent Runtime durable persistence.

Revision ID: 005_agent_runtime_persistence
Revises: 004_federated_knowledge_waist
Create Date: 2026-08-24

PR #25 shipped the re-runnable SQL schema used by the PostgreSQL test harness,
but the production Alembic chain stopped at revision 004. This revision adopts
the already-merged schema file so fresh production databases and tests apply the
same DDL rather than drifting into separate definitions.
"""

from __future__ import annotations

import pathlib

from alembic import op

revision = "005_agent_runtime_persistence"
down_revision = "004_federated_knowledge_waist"
branch_labels = None
depends_on = None

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCHEMA = _REPO_ROOT / "database" / "schemas" / "005_agent_runtime_persistence.sql"


def upgrade() -> None:
    if not _SCHEMA.is_file():
        raise RuntimeError(f"Agent Runtime schema not found at {_SCHEMA}")
    op.execute(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_task_checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_runtime_memories CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_runtime_skills CASCADE")
