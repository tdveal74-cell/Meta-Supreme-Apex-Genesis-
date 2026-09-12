-- 017: a durable ledger of provider spend, one row per account per UTC day.
--
-- Before this, nothing in the deployed API bounded what one signed-in
-- account could spend against Tee's provider keys: every lane that reaches a
-- provider (councils, agent turns, workflows, enrichment, embeddings) ran
-- unmetered. The metered wrapper installed by app.services.intelligence
-- upserts one row here after every completion and reads it before every call
-- to refuse an account that has reached PROVIDER_DAILY_TOKEN_CAP.
--
-- user_id is the account's id, or the word "system" for work that no account
-- asked for (startup jobs, service-layer calls with no request in hand). It
-- is deliberately not a foreign key: a deleted account's spend was still
-- spend, and the system bucket has no users row.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS provider_usage (
    user_id VARCHAR(64) NOT NULL,
    usage_day DATE NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, usage_day)
);
