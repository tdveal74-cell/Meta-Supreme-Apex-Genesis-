-- ============================================================
-- 004: FEDERATED KNOWLEDGE NARROW WAIST
-- ============================================================
-- Mirrors database/migrations/versions/004_federated_knowledge_waist.py so a
-- database built from these schema files matches the one Alembic produces.
--
-- Why this file exists: conftest.py builds the test database from
-- database/schemas/*.sql, not from Alembic. The FKR work added columns to the
-- models and to the Alembic chain but stopped at 003 here, so every test that
-- touched knowledge_items failed with
--   UndefinedColumnError: column "source" of relation "knowledge_items"
-- The models, the migrations and these files have to agree, and they now do.
--
-- One deliberate difference from the Alembic revision: it adds `updated_at` to
-- embeddings, which 001 already creates. Re-adding it here would fail. The
-- Alembic revision has the same problem against a database built from these
-- files and should be reconciled separately; this file is correct as written.
--
-- Additive only. Empty acl_tokens defaults preserve ownership-only behaviour.

-- --- knowledge_items: provenance for connectors ---
ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS source      TEXT;
ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS external_id TEXT;

CREATE INDEX IF NOT EXISTS idx_knowledge_items_source_external
    ON knowledge_items (owner_id, source, external_id);

-- --- knowledge_items: the content column the model has always declared ---
-- KnowledgeItem.content is read and written by app/services/knowledge.py, but
-- no schema file and no Alembic revision ever created it, so ingestion failed
-- against any real database with
--   UndefinedColumnError: column "content" of relation "knowledge_items"
-- The 001 schema stores content_hash only. Adding the column the model needs.
ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS content TEXT;

-- --- embeddings: narrow waist columns ---
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS source     TEXT;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS owner_id   UUID;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS project_id UUID;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS acl_tokens TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS fts        TSVECTOR;

CREATE INDEX IF NOT EXISTS idx_embeddings_owner_acl ON embeddings (owner_id) INCLUDE (acl_tokens);
CREATE INDEX IF NOT EXISTS idx_embeddings_project   ON embeddings (project_id) WHERE project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings (created_at);
CREATE INDEX IF NOT EXISTS idx_embeddings_fts       ON embeddings USING gin (fts);

-- HNSW is CONCURRENTLY in the Alembic revision because that runs against a live
-- database. A freshly built schema is empty and inside one script, so it is
-- created plainly here.
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw_cosine
    ON embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
