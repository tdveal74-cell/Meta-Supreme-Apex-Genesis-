-- DEVON Agent Runtime multi-worker execution leases and idempotent run ledger.
-- Re-runnable incremental schema for PostgreSQL 16.

ALTER TABLE agent_tasks
    ADD COLUMN IF NOT EXISTS lease_token VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(200) NULL,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS execution_generation BIGINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_agent_tasks_lease_expiry
    ON agent_tasks(lease_expires_at)
    WHERE lease_expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent_task_runs (
    id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(200) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    max_steps INTEGER NOT NULL,
    state VARCHAR(16) NOT NULL,
    lease_token VARCHAR(64) NULL,
    lease_owner VARCHAR(200) NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    result JSONB NULL,
    error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_agent_task_runs_owner_task_key
        UNIQUE(owner_id, task_id, idempotency_key),
    CONSTRAINT ck_agent_task_runs_state
        CHECK (state IN ('running', 'completed', 'failed')),
    CONSTRAINT ck_agent_task_runs_max_steps
        CHECK (max_steps >= 1 AND max_steps <= 100),
    CONSTRAINT ck_agent_task_runs_attempt
        CHECK (attempt >= 1)
);

CREATE INDEX IF NOT EXISTS ix_agent_task_runs_task_created
    ON agent_task_runs(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_task_runs_owner_state
    ON agent_task_runs(owner_id, state, updated_at DESC);
