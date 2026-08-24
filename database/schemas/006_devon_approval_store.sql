-- DEVON durable/shared human approval authority.
-- Re-runnable incremental schema for PostgreSQL 16.

CREATE TABLE IF NOT EXISTS devon_approvals (
    request_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    what_happens TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    area TEXT NULL,
    reversible BOOLEAN NOT NULL DEFAULT FALSE,
    blast_radius TEXT NOT NULL DEFAULT 'unstated',
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    state VARCHAR(16) NOT NULL,
    decided_at TIMESTAMPTZ NULL,
    decided_by TEXT NULL,
    token_hash CHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_devon_approvals_state
        CHECK (state IN ('pending', 'approved', 'refused', 'expired')),
    CONSTRAINT ck_devon_approvals_token_hash
        CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_devon_approvals_expiry_after_create
        CHECK (expires_at > created_at),
    CONSTRAINT ck_devon_approvals_decision_shape
        CHECK (
            (state = 'pending' AND decided_at IS NULL AND decided_by IS NULL)
            OR (state IN ('approved', 'refused') AND decided_at IS NOT NULL)
            OR (state = 'expired' AND decided_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS ix_devon_approvals_state_expiry
    ON devon_approvals(state, expires_at);

CREATE INDEX IF NOT EXISTS ix_devon_approvals_created
    ON devon_approvals(created_at DESC);
