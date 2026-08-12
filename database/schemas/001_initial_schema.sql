-- Meta Supreme Apex Genesis
-- Initial Database Schema
-- PostgreSQL + pgvector
-- Every table: UUID PK, created_at, updated_at, ownership controls

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- HELPER: updated_at trigger function
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    avatar_url      TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- ORGANIZATIONS
-- ============================================================
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'professional', 'enterprise')),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_organizations_owner ON organizations(owner_id);
CREATE INDEX idx_organizations_slug ON organizations(slug);

-- ============================================================
-- ORGANIZATION MEMBERS (Teams)
-- ============================================================
CREATE TABLE organization_members (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, user_id)
);

CREATE TRIGGER organization_members_updated_at
    BEFORE UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- PROJECTS
-- ============================================================
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_org ON projects(organization_id);

-- ============================================================
-- CONVERSATIONS
-- ============================================================
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_project ON conversations(project_id);

-- ============================================================
-- MESSAGES
-- ============================================================
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'agent')),
    content         TEXT NOT NULL,
    agent_id        UUID,  -- if role = agent
    metadata        JSONB NOT NULL DEFAULT '{}',
    token_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_messages_conversation ON messages(conversation_id);

-- ============================================================
-- AGENTS (Registry)
-- ============================================================
CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            TEXT NOT NULL UNIQUE,  -- oracle, analyst, strategist, ...
    name            TEXT NOT NULL,
    purpose         TEXT NOT NULL,
    system_instructions TEXT NOT NULL,
    capabilities    JSONB NOT NULL DEFAULT '[]',
    limitations     JSONB NOT NULL DEFAULT '[]',
    output_format   JSONB NOT NULL DEFAULT '{}',
    evaluation_criteria JSONB NOT NULL DEFAULT '{}',
    version         TEXT NOT NULL DEFAULT '1.0.0',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- AGENT RUNS
-- ============================================================
CREATE TABLE agent_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_payload   JSONB NOT NULL DEFAULT '{}',
    output_payload  JSONB,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message   TEXT,
    token_usage     JSONB,
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER agent_runs_updated_at
    BEFORE UPDATE ON agent_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_agent_runs_conversation ON agent_runs(conversation_id);
CREATE INDEX idx_agent_runs_agent ON agent_runs(agent_id);

-- ============================================================
-- KNOWLEDGE ITEMS
-- ============================================================
CREATE TABLE knowledge_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('pdf', 'docx', 'txt', 'markdown', 'url', 'manual')),
    source_uri      TEXT,
    content_hash    TEXT,
    status          TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed', 'archived')),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER knowledge_items_updated_at
    BEFORE UPDATE ON knowledge_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_knowledge_items_project ON knowledge_items(project_id);
CREATE INDEX idx_knowledge_items_owner ON knowledge_items(owner_id);

-- ============================================================
-- EMBEDDINGS (pgvector)
-- ============================================================
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),  -- OpenAI text-embedding-3-small dimension; adjust as needed
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER embeddings_updated_at
    BEFORE UPDATE ON embeddings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_embeddings_knowledge_item ON embeddings(knowledge_item_id);
-- Vector index (IVFFlat or HNSW depending on volume)
-- CREATE INDEX idx_embeddings_vector ON embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- MEMORIES
-- ============================================================
CREATE TABLE memories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    memory_type     TEXT NOT NULL CHECK (memory_type IN ('preference', 'context', 'decision', 'lesson', 'pattern', 'other')),
    content         TEXT NOT NULL,
    importance      SMALLINT NOT NULL DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_memories_user ON memories(user_id);
CREATE INDEX idx_memories_project ON memories(project_id);

-- ============================================================
-- DECISIONS
-- ============================================================
CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    options         JSONB NOT NULL DEFAULT '[]',
    recommendation  TEXT,
    chosen_option   TEXT,
    outcome         TEXT,
    outcome_notes   TEXT,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'decided', 'reviewed', 'archived')),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_decisions_user ON decisions(user_id);
CREATE INDEX idx_decisions_project ON decisions(project_id);

-- ============================================================
-- WORKFLOWS
-- ============================================================
CREATE TABLE workflows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    definition      JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'paused', 'archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER workflows_updated_at
    BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- FEEDBACK
-- ============================================================
CREATE TABLE feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL CHECK (target_type IN ('message', 'agent_run', 'decision', 'knowledge', 'system')),
    target_id       UUID,
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER feedback_updated_at
    BEFORE UPDATE ON feedback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- AUDIT LOGS
-- ============================================================
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     UUID,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- No updated_at — audit logs are immutable
);

CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_logs_org ON audit_logs(organization_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- ============================================================
-- NOTES
-- ============================================================
-- Row Level Security (RLS) policies should be added in a subsequent migration
-- once authentication context is fully defined.
-- Example:
-- ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY project_isolation ON projects
--     USING (owner_id = current_setting('app.current_user_id')::uuid
--         OR organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = current_setting('app.current_user_id')::uuid));
