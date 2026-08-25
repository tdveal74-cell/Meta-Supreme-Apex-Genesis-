-- Durable Hermes expansion tables for DEVON Agent Runtime.
-- Schedule ledger and skill proposals. Promotion remains human-gated in app code.

CREATE TABLE IF NOT EXISTS agent_schedules (
    id VARCHAR(64) PRIMARY KEY,
    schedule_id VARCHAR(64) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL,
    state VARCHAR(16) NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    task_id VARCHAR(64) NULL REFERENCES agent_tasks(id) ON DELETE SET NULL,
    failure_reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_schedules_owner_schedule UNIQUE (owner_id, schedule_id)
);

CREATE INDEX IF NOT EXISTS ix_agent_schedules_owner_run_at
    ON agent_schedules (owner_id, run_at);
CREATE INDEX IF NOT EXISTS ix_agent_schedules_state
    ON agent_schedules (state);

CREATE TABLE IF NOT EXISTS agent_skill_proposals (
    id VARCHAR(64) PRIMARY KEY,
    proposal_id VARCHAR(64) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    source_task_id VARCHAR(64) NOT NULL,
    state VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_agent_skill_proposals_owner_proposal UNIQUE (owner_id, proposal_id)
);

CREATE INDEX IF NOT EXISTS ix_agent_skill_proposals_owner_state
    ON agent_skill_proposals (owner_id, state);
