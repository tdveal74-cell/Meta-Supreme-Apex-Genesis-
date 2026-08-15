"""Federated knowledge narrow-waist evolution.

Revision ID: 004_federated_knowledge_waist
Revises: 003_schedule_dispatch
Create Date: 2026-08-15

Additive only. Evolves knowledge_items + embeddings for hybrid retrieval:
source / external_id on items; denormalized owner/project/source, fts,
acl_tokens on embeddings; HNSW + GIN + ACL indexes.

Empty acl_tokens defaults preserve ownership-only behaviour.
HNSW is created CONCURRENTLY outside the migration transaction.
Existing pure-semantic search_knowledge path is not altered by this revision.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "004_federated_knowledge_waist"
down_revision = "003_schedule_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- knowledge_items: provenance for connectors ---
    op.add_column(
        "knowledge_items",
        sa.Column("source", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_items",
        sa.Column("external_id", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE knowledge_items
        SET source = COALESCE(NULLIF(source, ''), source_type)
        WHERE source IS NULL
        """
    )
    op.create_index(
        "idx_knowledge_items_source_external",
        "knowledge_items",
        ["owner_id", "source", "external_id"],
        unique=False,
    )

    # --- embeddings: narrow waist columns ---
    op.add_column(
        "embeddings",
        sa.Column("source", sa.Text(), nullable=True),
    )
    op.add_column(
        "embeddings",
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "embeddings",
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "acl_tokens",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column("fts", postgresql.TSVECTOR(), nullable=True),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE embeddings e
        SET
          owner_id = ki.owner_id,
          project_id = ki.project_id,
          source = COALESCE(ki.source, ki.source_type)
        FROM knowledge_items ki
        WHERE e.knowledge_item_id = ki.id
          AND (e.owner_id IS NULL OR e.source IS NULL)
        """
    )

    op.execute(
        """
        UPDATE embeddings
        SET fts = to_tsvector('english', COALESCE(content, ''))
        WHERE fts IS NULL AND content IS NOT NULL AND content <> ''
        """
    )

    op.create_index(
        "idx_embeddings_owner_acl",
        "embeddings",
        ["owner_id"],
        unique=False,
        postgresql_include=["acl_tokens"],
    )
    op.create_index(
        "idx_embeddings_project",
        "embeddings",
        ["project_id"],
        unique=False,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )
    op.create_index(
        "idx_embeddings_created_at",
        "embeddings",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_embeddings_fts",
        "embeddings",
        ["fts"],
        unique=False,
        postgresql_using="gin",
    )

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embeddings_hnsw_cosine
            ON embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_embeddings_hnsw_cosine")

    op.drop_index("idx_embeddings_fts", table_name="embeddings")
    op.drop_index("idx_embeddings_created_at", table_name="embeddings")
    op.drop_index("idx_embeddings_project", table_name="embeddings")
    op.drop_index("idx_embeddings_owner_acl", table_name="embeddings")

    op.drop_column("embeddings", "updated_at")
    op.drop_column("embeddings", "fts")
    op.drop_column("embeddings", "acl_tokens")
    op.drop_column("embeddings", "project_id")
    op.drop_column("embeddings", "owner_id")
    op.drop_column("embeddings", "source")

    op.drop_index("idx_knowledge_items_source_external", table_name="knowledge_items")
    op.drop_column("knowledge_items", "external_id")
    op.drop_column("knowledge_items", "source")
