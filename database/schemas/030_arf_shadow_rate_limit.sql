-- ARF-only security accounting. No task/evidence/approval rows are modified.
-- One row per account; database time and conditional upsert share the budget
-- across workers without a new service or a process-local reset path.
CREATE TABLE IF NOT EXISTS arf_shadow_rate_limits (
    owner_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    next_slot_at timestamptz NOT NULL,
    CONSTRAINT arf_shadow_rate_limits_finite_time CHECK (isfinite(next_slot_at))
);
