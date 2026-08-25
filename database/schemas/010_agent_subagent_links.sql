-- Durable parent→child links for Hermes subagents.

CREATE TABLE IF NOT EXISTS agent_subagent_links (
    id VARCHAR(64) PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    child_task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    subagent_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_subagent_links_owner_child UNIQUE (owner_id, child_task_id),
    CONSTRAINT uq_agent_subagent_links_owner_subagent UNIQUE (owner_id, subagent_id)
);

CREATE INDEX IF NOT EXISTS ix_agent_subagent_links_owner_parent
    ON agent_subagent_links (owner_id, parent_task_id);
