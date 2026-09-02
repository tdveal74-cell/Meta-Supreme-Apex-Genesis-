-- 015: an approval card belongs to an account.
--
-- Before this, devon_approvals had no owner column. The API listed every
-- pending card to every caller and let any holder of a request id and token
-- rule on it, because there was nothing to scope by. Cards raised by a lane
-- that has no user in hand (the operator bridge, a presence turn that rules
-- on itself) keep an empty owner and are visible to any signed-in account.
--
-- Re-runnable. Existing rows get an empty owner.

ALTER TABLE devon_approvals
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_devon_approvals_owner_state
    ON devon_approvals(owner_id, state);
