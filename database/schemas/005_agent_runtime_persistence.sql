-- DEVON Agent Runtime durable persistence.
-- Re-runnable incremental schema for PostgreSQL 16.

CREATE TABLE IF NOT EXISTS agent_tasks (
    id TEXT PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NULL REFERENCES projects(id) ON DELETE SET NULL,
    goal TEXT NOT NULL,
    state VARCHAR(32) NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_agent_tasks_owner_updated
    ON agent_tasks(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_tasks_owner_state
    ON agent_tasks(owner_id, state);

CREATE TABLE IF NOT EXISTS agent_task_checkpoints (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_step INTEGER NOT NULL,
    observation_count INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_agent_task_checkpoints_task_created
    ON agent_task_checkpoints(task_id, created_at);
CREATE INDEX IF NOT EXISTS ix_agent_task_checkpoints_owner
    ON agent_task_checkpoints(owner_id);

CREATE TABLE IF NOT EXISTS agent_runtime_memories (
    id TEXT PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NULL REFERENCES projects(id) ON DELETE SET NULL,
    text TEXT NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    source VARCHAR(120) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_agent_runtime_memories_owner_updated
    ON agent_runtime_memories(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_runtime_memories_project
    ON agent_runtime_memories(project_id) WHERE project_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent_runtime_skills (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    provenance VARCHAR(120) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_runtime_skill_owner_name UNIQUE(owner_id, name)
);

CREATE INDEX IF NOT EXISTS ix_agent_runtime_skills_owner_name
    ON agent_runtime_skills(owner_id, name);
