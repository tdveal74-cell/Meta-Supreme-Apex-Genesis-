-- ============================================================
-- 002 — Workflow runs (Phase 5)
--
-- The SQL twin of Alembic revision 002_workflow_runs. It exists for one
-- reason: the test fixture builds its database from these files, not from
-- Alembic. Alembic remains the source of truth for real environments — if
-- these two ever disagree, the migration wins and this file is the bug.
-- ============================================================

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_workflows_owner ON workflows(owner_id);
CREATE INDEX IF NOT EXISTS idx_workflows_project ON workflows(project_id);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id     UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'awaiting_approval',
                                      'completed', 'halted', 'failed')),
    trigger         TEXT NOT NULL DEFAULT 'manual',
    trigger_input   TEXT,
    step_results    JSONB NOT NULL DEFAULT '[]',
    approvals       JSONB NOT NULL DEFAULT '{}',
    pending_step_id TEXT,
    token_usage     JSONB,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow
    ON workflow_runs(workflow_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_user
    ON workflow_runs(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_awaiting
    ON workflow_runs(workflow_id) WHERE status = 'awaiting_approval';
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_runs_idempotency
    ON workflow_runs(workflow_id, (metadata->>'idempotency_key'))
    WHERE metadata ? 'idempotency_key';

DROP TRIGGER IF EXISTS workflow_runs_updated_at ON workflow_runs;
CREATE TRIGGER workflow_runs_updated_at
    BEFORE UPDATE ON workflow_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
