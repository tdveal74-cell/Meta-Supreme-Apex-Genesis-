-- ============================================================
-- 003 — Schedule dispatch (Phase 5.1)
--
-- SQL twin of Alembic revision 003_schedule_dispatch, for the test fixture.
-- Alembic wins if they ever disagree.
-- ============================================================

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS next_run_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_fired_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_workflows_due
    ON workflows(next_run_at)
    WHERE next_run_at IS NOT NULL AND status = 'active';
