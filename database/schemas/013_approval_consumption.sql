-- 013: an approved effect is spent when it runs, so it cannot run twice.
--
-- Before this, ApprovalState ended at approved/refused/expired. The capability
-- boundary checked that a record was APPROVED and bound to the exact arguments
-- in hand, and both facts stayed true forever. An approval was therefore a
-- standing permission rather than permission to do one thing once: anyone
-- holding the runtime metadata could replay the same governed effect
-- indefinitely, and every replay would pass every check.
--
-- Re-runnable on purpose. This lands against a live shared table that the API
-- is reading and writing, so it drops and re-adds both constraints rather than
-- assuming their prior shape, and adds no column and no default. Existing rows
-- keep their state; nothing is rewritten.

ALTER TABLE devon_approvals
    DROP CONSTRAINT IF EXISTS ck_devon_approvals_state;

ALTER TABLE devon_approvals
    ADD CONSTRAINT ck_devon_approvals_state
        CHECK (state IN ('pending', 'approved', 'refused', 'expired', 'consumed'));

ALTER TABLE devon_approvals
    DROP CONSTRAINT IF EXISTS ck_devon_approvals_decision_shape;

-- A consumed row carries the decision it was consumed under. It reached
-- 'consumed' from 'approved', which already required decided_at, so the
-- timestamp of the human ruling is preserved rather than overwritten by the
-- moment the effect ran.
ALTER TABLE devon_approvals
    ADD CONSTRAINT ck_devon_approvals_decision_shape
        CHECK (
            (state = 'pending' AND decided_at IS NULL AND decided_by IS NULL)
            OR (state IN ('approved', 'refused') AND decided_at IS NOT NULL)
            OR (state = 'expired' AND decided_at IS NOT NULL)
            OR (state = 'consumed' AND decided_at IS NOT NULL)
        );
