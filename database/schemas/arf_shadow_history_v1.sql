-- DRAFT REVIEW ONLY. Not included in Alembic or applied to a live database.
-- Separate from DEVON execution/approval tables. No automatic tool retries.
-- Apply only after owner security review and a tested rollback migration.
CREATE TABLE IF NOT EXISTS arf_shadow_history (
    event_id VARCHAR(80) PRIMARY KEY,
    recorded_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    root_task_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    parent_event_id VARCHAR(80) NULL REFERENCES arf_shadow_history(event_id),
    delegated_from_event_id VARCHAR(80) NULL REFERENCES arf_shadow_history(event_id),
    failure_fingerprint CHAR(64) NOT NULL,
    outcome_digest CHAR(64) NOT NULL,
    evidence_revision VARCHAR(128) NOT NULL,
    control VARCHAR(80) NOT NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    policy_digest CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (owner_id, root_task_id, failure_fingerprint, attempt_no),
    CHECK (parent_event_id IS NULL OR parent_event_id <> event_id),
    CHECK (delegated_from_event_id IS NULL OR delegated_from_event_id <> event_id)
);
CREATE INDEX IF NOT EXISTS ix_arf_history_owner_root
    ON arf_shadow_history (owner_id, root_task_id, created_at);
-- Add RLS and app-specific grants in a reviewed Alembic migration before use.
