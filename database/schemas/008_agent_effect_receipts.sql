-- DEVON Agent Runtime durable effect intents and receipts.
-- Re-runnable incremental schema for PostgreSQL 16.
-- Closes the remaining reliability window after multi-worker leases.

CREATE TABLE IF NOT EXISTS agent_effect_intents (
    id VARCHAR(64) PRIMARY KEY,
    intent_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    step_id VARCHAR(64) NOT NULL,
    tool_name VARCHAR(200) NOT NULL,
    arguments_hash VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    execution_generation BIGINT NOT NULL,
    lease_token VARCHAR(64) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_effect_intents_owner_task_intent
        UNIQUE(owner_id, task_id, intent_id)
);

CREATE INDEX IF NOT EXISTS ix_agent_effect_intents_intent_id
    ON agent_effect_intents(intent_id);
CREATE INDEX IF NOT EXISTS ix_agent_effect_intents_task_created
    ON agent_effect_intents(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_effect_receipts (
    id VARCHAR(64) PRIMARY KEY,
    intent_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL,
    provider_receipt_id VARCHAR(200) NOT NULL DEFAULT '',
    raw_response JSONB NOT NULL DEFAULT '{}',
    execution_generation BIGINT NOT NULL,
    lease_token VARCHAR(64) NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_effect_receipts_owner_intent
        UNIQUE(owner_id, intent_id),
    CONSTRAINT ck_agent_effect_receipts_status
        CHECK (status IN ('succeeded', 'failed', 'ambiguous'))
);

CREATE INDEX IF NOT EXISTS ix_agent_effect_receipts_intent_id
    ON agent_effect_receipts(intent_id);
CREATE INDEX IF NOT EXISTS ix_agent_effect_receipts_task_recorded
    ON agent_effect_receipts(task_id, recorded_at DESC);
